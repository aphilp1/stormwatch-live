#!/usr/bin/env node
// Smoke test for weather-alerts.html: loads the app in a fixed-UTC-6 browser
// context (America/Regina — no DST, so it reproduces off-UTC bugs like the
// 2026-08-01 NAQFC timezone bug year-round), sweeps every top-level tab, then
// clicks every layer toggle on and off. Fails if any console error or
// uncaught exception fires during the run.
//
// Catches JS-crash-class regressions (e.g. the 2026-07-08 Montana Mesonet
// null-sensor crash). Does NOT catch silent-wrong-output bugs where the code
// runs without error but produces the wrong result — those need a human or a
// value-level check, not this script.
//
// Usage: node Storm_info/smoketest_layers.js [url]
// The caller is responsible for serving weather-alerts.html first, e.g.:
//   python -m http.server 8123 &
//   node Storm_info/smoketest_layers.js http://localhost:8123/weather-alerts.html

const { chromium } = require('playwright');

const URL = process.argv[2] || 'http://localhost:8123/weather-alerts.html';
const TABS = ['alerts', 'stats', 'layers', 'models', 'maps', 'agents', 'eventwatch', 'experiments'];

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ timezoneId: 'America/Regina' });
  const page = await context.newPage();

  // Chrome logs a generic "Failed to load resource: ... 404/403/etc" console.error
  // for EVERY failed network request — missing map tiles at ocean edges, an
  // optional data feed that's momentarily down, a CORS-blocked third-party API.
  // That's expected noise in a map app hitting a dozen live government feeds, not
  // a code bug — filtering it out is what makes this test usable instead of
  // permanently red. Real JS bugs (TypeError, ReferenceError, "Cannot read
  // properties of undefined", etc.) don't match this pattern and still fail loudly,
  // as does anything caught by pageerror (uncaught exceptions).
  const NETWORK_NOISE = /Failed to load resource/i;
  const errors = [];
  let currentStep = 'page load';
  page.on('console', msg => {
    if (msg.type() === 'error' && !NETWORK_NOISE.test(msg.text())) errors.push({ step: currentStep, text: msg.text() });
  });
  page.on('pageerror', err => errors.push({ step: currentStep, text: err.message }));
  page.on('dialog', d => d.dismiss().catch(() => {}));

  await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(1500);

  for (const tab of TABS) {
    currentStep = `tab: ${tab}`;
    const found = await page.evaluate((name) => {
      if (typeof showTab === 'function') { showTab(name); return true; }
      return false;
    }, tab);
    if (!found) { errors.push({ step: currentStep, text: 'showTab() not found on page' }); break; }
    await page.waitForTimeout(300);
  }

  await page.evaluate(() => showTab('layers'));
  await page.waitForTimeout(300);
  const toggleIds = await page.evaluate(() =>
    Array.from(document.querySelectorAll('input[type=checkbox][id^="lyr-"]')).map(el => el.id)
  );
  if (toggleIds.length === 0) errors.push({ step: 'enumerate toggles', text: 'no lyr-* checkboxes found on the page — selector may be stale' });

  for (const id of toggleIds) {
    currentStep = `toggle ON: ${id}`;
    await page.evaluate((elId) => document.getElementById(elId)?.click(), id);
    await page.waitForTimeout(700);
    currentStep = `toggle OFF: ${id}`;
    await page.evaluate((elId) => document.getElementById(elId)?.click(), id);
    await page.waitForTimeout(200);
  }

  await browser.close();

  if (errors.length) {
    console.error(`\n✗ Smoke test FAILED — ${errors.length} console error(s):\n`);
    errors.forEach(e => console.error(`  [${e.step}] ${e.text}`));
    process.exit(1);
  }
  console.log(`✓ Smoke test passed — ${toggleIds.length} layer toggles + ${TABS.length} tabs, zero console errors.`);
}

main().catch(err => { console.error('Smoke test crashed:', err); process.exit(1); });
