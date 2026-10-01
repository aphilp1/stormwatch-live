#!/usr/bin/env node
// Functional layer test for weather-alerts.html.
//
// Loads the app in a fixed-UTC-6 browser context (America/Regina — no DST, so
// it reproduces off-UTC bugs like the 2026-08-01 NAQFC timezone bug year-round),
// sweeps every top-level tab, then switches every layer toggle on, WAITS FOR
// THAT LAYER'S STATUS NOTE TO SETTLE, and records what it said. A layer whose
// note ends in an error state ("load error", "unavailable", "err", "stream
// servers busy", ...) is a DATA FAILURE. Any real console error or uncaught
// exception is a CODE FAILURE. Either one fails the run.
//
// Layers that answer "zoom in ..." at the national view are re-tested in a
// second pass zoomed to a real place (Missoula, zoom 10), so zoom-gated feeds
// such as Stream Network (Overpass) actually get exercised instead of skipped.
//
// What this still does NOT catch: silent-wrong-output bugs where the code runs,
// the note says something normal, but the drawn result is wrong (wrong colour,
// wrong timestamp, wrong place). Those need a human or a value-level assertion.
//
// Usage:
//   node Storm_info/smoketest_layers.js [url] [--out results.json]
// The caller serves weather-alerts.html first (or passes the live site URL):
//   python -m http.server 8123 &
//   node Storm_info/smoketest_layers.js http://localhost:8123/weather-alerts.html
//   node Storm_info/smoketest_layers.js https://aphilp1.github.io/stormwatch-live/weather-alerts.html --out data/layer_test.json

const fs = require('fs');
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const OUT = outIdx >= 0 ? args[outIdx + 1] : null;
const URL = args.find(a => !a.startsWith('--') && a !== OUT) || 'http://localhost:8123/weather-alerts.html';

const TABS = ['alerts', 'stats', 'layers', 'models', 'maps', 'agents', 'eventwatch', 'experiments'];
const SETTLE_MS = 20000;          // max wait for one layer's note to leave "loading…"
const MIRROR_SETTLE_MS = 120000;  // ... unless it is working through fallback mirrors
const OFF_GRACE_MS = 3000;        // how long "off" may persist after switching ON before it counts as "no status"
const ZOOM_CENTER = { lat: 46.87, lon: -113.99 };   // Missoula, MT
const DEFAULT_ZOOM_PASS = 10;     // zoom used when a note just says "zoom in"

// Note text that means the layer's data did NOT arrive.
const NOTE_FAIL = /error|unavailable|\berr\b|fail|busy|rate limit|offline/i;
// Note text that means "still working" — keep waiting.
const NOTE_PENDING = /loading|checking|fetching/i;
// Note text that means the layer needs a closer zoom before it will load.
const NOTE_ZOOM = /zoom/i;

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ timezoneId: 'America/Regina', viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();

  // Chrome logs a generic "Failed to load resource" console.error for EVERY
  // failed network request (ocean-edge tiles, a momentarily-down optional feed,
  // a CORS-blocked third party). That is expected noise in a map app hitting
  // a dozen live government feeds, not a code bug. Real JS bugs (TypeError,
  // ReferenceError, ...) don't match it and still fail loudly, as does anything
  // caught by pageerror. Data-level failures are caught via the notes instead.
  const NETWORK_NOISE = /Failed to load resource/i;
  const codeErrors = [];
  let currentStep = 'page load';
  page.on('console', msg => {
    if (msg.type() === 'error' && !NETWORK_NOISE.test(msg.text())) codeErrors.push({ step: currentStep, text: msg.text().slice(0, 300) });
  });
  page.on('pageerror', err => codeErrors.push({ step: currentStep, text: err.message.slice(0, 300) }));
  page.on('dialog', d => d.dismiss().catch(() => {}));

  const started = new Date();
  await page.goto(URL, { waitUntil: 'load', timeout: 45000 });
  await page.waitForTimeout(2000);

  for (const tab of TABS) {
    currentStep = `tab: ${tab}`;
    const found = await page.evaluate((name) => {
      if (typeof showTab === 'function') { showTab(name); return true; }
      return false;
    }, tab);
    if (!found) { codeErrors.push({ step: currentStep, text: 'showTab() not found on page' }); break; }
    await page.waitForTimeout(300);
  }

  await page.evaluate(() => showTab('layers'));
  await page.waitForTimeout(300);
  const toggleIds = await page.evaluate(() =>
    Array.from(document.querySelectorAll('input[type=checkbox][id^="lyr-"]')).map(el => el.id)
  );
  if (toggleIds.length === 0) codeErrors.push({ step: 'enumerate toggles', text: 'no lyr-* checkboxes found on the page — selector may be stale' });

  // Read a layer's status note. lyr-X maps to X-note or X-status-note.
  const readNote = (id) => page.evaluate((elId) => {
    const base = elId.replace(/^lyr-/, '');
    const el = document.getElementById(base + '-note') || document.getElementById(base + '-status-note');
    return el ? el.textContent.trim() : null;
  }, id);

  const waitForNote = async (id) => {
    const t0 = Date.now();
    let note = await readNote(id);
    while (true) {
      if (note === null) return null;
      const elapsed = Date.now() - t0;
      // A layer walking through fallback mirrors (Stream Network: up to 4 x 25 s)
      // is legitimately still working — give it the full chain before calling it.
      const budget = /mirror/i.test(note) ? MIRROR_SETTLE_MS : SETTLE_MS;
      // "off" right after switching ON means the handler hasn't written a status
      // yet (or never does) — give it a moment, then treat it as "no status".
      const pending = NOTE_PENDING.test(note) || (note === 'off' && elapsed < OFF_GRACE_MS);
      if (!pending || elapsed >= budget) return note;
      await page.waitForTimeout(500);
      note = await readNote(id);
    }
  };

  const results = [];
  const runPass = async (passName, ids) => {
    for (const id of ids) {
      currentStep = `${passName} toggle ON: ${id}`;
      const t0 = Date.now();
      await page.evaluate((elId) => document.getElementById(elId)?.click(), id);
      await page.waitForTimeout(700);
      const note = await waitForNote(id);
      const ms = Date.now() - t0;
      let status;
      if (note === null || note === 'off') status = 'no-note';
      else if (NOTE_PENDING.test(note)) status = 'timeout';
      else if (NOTE_FAIL.test(note)) status = 'fail';
      else if (NOTE_ZOOM.test(note)) status = 'zoom-gated';
      else status = 'ok';
      results.push({ layer: id, pass: passName, status, note, ms });
      currentStep = `${passName} toggle OFF: ${id}`;
      await page.evaluate((elId) => document.getElementById(elId)?.click(), id);
      await page.waitForTimeout(200);
    }
  };

  currentStep = 'pass 1 (national view)';
  await runPass('national', toggleIds);

  // Further passes, zoomed in, for everything that asked for a closer zoom.
  // "zoom 14+ to see zones" -> zoom 14; a plain "zoom in to see" -> DEFAULT_ZOOM_PASS.
  const zoomOf = (note) => { const m = /zoom\s*(\d+)/i.exec(note || ''); return m ? Number(m[1]) : DEFAULT_ZOOM_PASS; };
  const byZoom = {};
  for (const r of results) if (r.status === 'zoom-gated') (byZoom[zoomOf(r.note)] ??= []).push(r.layer);
  for (const zoom of Object.keys(byZoom).map(Number).sort((a, b) => a - b)) {
    currentStep = `zoom to Missoula z${zoom}`;
    await page.evaluate(({ lat, lon, zoom }) => { if (typeof map !== 'undefined') map.setView([lat, lon], zoom); }, { ...ZOOM_CENTER, zoom });
    await page.waitForTimeout(1500);
    await runPass(`zoom${zoom}`, byZoom[zoom]);
  }

  await browser.close();

  // One row per layer: the zoomed result replaces the "zoom-gated" placeholder.
  const final = {};
  for (const r of results) {
    if (!final[r.layer] || final[r.layer].status === 'zoom-gated') final[r.layer] = r;
  }
  const rows = Object.values(final);
  const dataFails = rows.filter(r => r.status === 'fail' || r.status === 'timeout');
  const okCount = rows.filter(r => r.status === 'ok').length;

  const summary = {
    checked_utc: started.toISOString(),
    url: URL,
    layers_total: rows.length,
    layers_ok: okCount,
    layers_no_note: rows.filter(r => r.status === 'no-note').length,
    layers_zoom_gated: rows.filter(r => r.status === 'zoom-gated').length,
    data_failures: dataFails.map(r => ({ layer: r.layer, note: r.note, status: r.status })),
    code_errors: codeErrors,
    layers: rows
  };
  if (OUT) {
    fs.writeFileSync(OUT, JSON.stringify(summary, null, 2) + '\n');
    console.log(`wrote ${OUT}`);
  }

  console.log(`\nLayer results (${rows.length} toggles, ${TABS.length} tabs):`);
  for (const r of rows) {
    const mark = r.status === 'ok' ? '✓' : (r.status === 'fail' || r.status === 'timeout') ? '✗' : '·';
    console.log(`  ${mark} ${r.layer.padEnd(22)} ${r.status.padEnd(10)} ${(r.note ?? '(no status note)').slice(0, 60)}`);
  }

  if (codeErrors.length || dataFails.length) {
    if (codeErrors.length) {
      console.error(`\n✗ CODE FAILURE — ${codeErrors.length} console error(s)/exception(s):`);
      codeErrors.forEach(e => console.error(`  [${e.step}] ${e.text}`));
    }
    if (dataFails.length) {
      console.error(`\n✗ DATA FAILURE — ${dataFails.length} layer(s) did not load:`);
      dataFails.forEach(r => console.error(`  ${r.layer}: "${r.note}" (${r.status})`));
    }
    process.exit(1);
  }
  console.log(`\n✓ Layer test passed — ${okCount} of ${rows.length} layers loaded data, zero console errors.`);
}

main().catch(err => { console.error('Layer test crashed:', err); process.exit(1); });
