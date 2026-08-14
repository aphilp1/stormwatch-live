# Spec 04 — Clip · Zip · Ship (StormWatch Snapshot)

*Written by Fable 2026-07-07. Target file: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` (single-file Leaflet app, ~9,443 lines).*
*All line numbers verified against the current file on 2026-07-07. Library findings in §1 verified by live web research the same day.*

---

## 0. What this adds — the one-paragraph version

A **📸 Snapshot** button in the header (right of ↻ Refresh). One click captures exactly what the user is
looking at — map view, active layers, the open detail card (alert / fire / perimeter / gauge / station),
and the live wind readout — and packages it into a branded **"situation card"** produced in two formats
at once: a **self-contained .html** (zero external requests, zero JavaScript — opens offline on any
phone or computer) and a **.pdf**. A small "Snapshot ready" modal then offers **📤 Share…** (Web Share
API Level 2 → straight into Mail / Messages / WhatsApp on mobile) with plain download buttons as the
universal fallback. Clip → zip → ship, three seconds, no server.

Flow:

```
[📸 Snapshot click]
   → snapCollectState()        read view/layers/card/wind from the live DOM + Leaflet API
   → snapCaptureMap()          rasterize #map to PNG (dom-to-image-more primary, modern-screenshot fallback)
   → snapBuildHtml()           compose the situation-card .html (PNG inlined as data URI)
   → snapBuildPdf()            draw the same card natively in jsPDF (crisp vector text + the PNG)
   → snapShowModal()           preview + [Share…] [⬇ .html] [⬇ .pdf]
        Share… click (fresh user gesture — required by navigator.share)
   → navigator.canShare({files}) combos: [html+pdf] → [pdf] → [html] → download-both fallback
```

---

## 1. Research & decisions

### 1.1 Map capture library — **dom-to-image-more 3.10.0 primary, modern-screenshot 4.7.0 fallback**

> **Decision reversed after verification (2026-07-07).** The intuitive pick — html2canvas — is the
> *wrong* tool for a Leaflet map. html2canvas re-implements its own renderer and has a long-standing
> bug class with Leaflet's `translate3d`-positioned tile/pane transforms → shifted or missing tiles
> and **dropped SVG overlays** (Leaflet/Leaflet#3991, niklasvh/html2canvas#567). Our alert/perimeter
> polygons are SVG in the overlay pane, so html2canvas would silently mangle exactly the content that
> matters. Chosen library flipped accordingly.

What the capture has to survive in this app: CARTO raster tiles (`<img>` in the tile pane, CSS
`translate3d` transforms), **SVG** alert/perimeter polygons in the overlay pane, **multiple `<canvas>`
overlays** (the `L.canvas` renderers used by VIIRS/RAWS/wind markers, plus the `leaflet-velocity`
particle canvas), divIcon markers, and Leaflet controls.

| Candidate | Verdict | Why |
|---|---|---|
| **leaflet-image 0.4.0** | ❌ reject | Tile + `L.canvas` paths only; re-draws layers itself instead of reading the DOM. Explicitly does **not** render SVG overlays, divIcons, or HTML markers → our alert polygons vanish. Dead since 2016. |
| **html2canvas 1.4.1** (or the active fork **html2canvas-pro 2.2.3**) | ❌ reject as primary | Custom-renderer architecture → the documented Leaflet CSS-transform bug class (dropped tiles + dropped SVG panes). html2canvas itself is also unmaintained (last release 2022). Only worth keeping in a back pocket as a *different-architecture* last resort. |
| **dom-to-image-more 3.10.0** | ✅ **primary** | The `foreignObject` approach: serializes the live DOM into an SVG `<foreignObject>` and lets the **browser's own engine** rasterize it — so Leaflet's CSS transforms, mixed `<img>` tiles, the SVG overlay pane, and the canvas overlays all render with **native fidelity** (this family handles mixed SVG+canvas+img best). Actively maintained (published 2026-06-12, ~1 open issue), CDN UMD global `domtoimage`. It fetch-and-inlines each tile image (needs tile CORS — satisfied, §1.2) and inlines each `<canvas>` via `toDataURL` (needs the canvas untainted — satisfied: the velocity/marker canvases draw only shapes/particles, no cross-origin images). |
| **modern-screenshot 4.7.0** | ✅ **fallback** | Same `foreignObject` family (a faster fork of html-to-image; a monday.com benchmark clocked it ~3× faster than html2canvas). Different implementation, so it dodges any library-specific bug in the primary. Actively maintained; CDN global `modernScreenshot`. |

Both are `foreignObject`-based. **Known caveat of the whole family: Safari/iOS occasionally renders the
first `foreignObject` pass blank or partial** (WebKit bug 23113; html-to-image#361/#461). Mitigation is
baked into `snapCaptureMap()` (§3d): the primary runs a **double render** (call twice, keep the second),
and if it still fails or returns an all-blank frame, it falls through to modern-screenshot. Both are
CDN-loadable (pinned URLs §3a); the capture is isolated behind one function so re-ordering is trivial.

### 1.2 Tile CORS / canvas taint — why this works without touching `initMap()`

A tainted canvas throws `SecurityError` on `toDataURL()` — the classic map-screenshot killer. The
`foreignObject` family avoids the tile-`<img>` version of this because it **fetches each image itself
and inlines it as a data URI** (independent of whatever `crossOrigin` the live `<img>` had) — but the
fetch still needs the server to allow cross-origin reads, and any **existing `<canvas>`** it inlines
via `toDataURL` must be untainted. Verified by direct header inspection (curl with an `Origin:` header,
2026-07-07):

- **CARTO basemaps** (`basemaps.cartocdn.com` — the app's default light/dark, lines 2539–2547):
  `Access-Control-Allow-Origin: *`. ✅
- **OpenStreetMap** (`tile.openstreetmap.org`): `access-control-allow-origin: *`. ✅
- **Esri + USGS** (`server.arcgisonline.com`, `basemap.nationalmap.gov`, `opentopomap.org`): send
  `ACAO: *` (Esri/USGS confirmed on other USGS specs in this folder). ✅
- The app's canvas overlays are safe to inline: the `L.canvas` marker renderers draw only
  circles/paths and the `leaflet-velocity` canvas draws only particles — **no cross-origin images**, so
  none of them is tainted.
- **Residual risk**: third-party WMS overlays (IEM mesonet radar/MRMS, FEMA NFHL, NAQFC). If one lacks
  CORS, dom-to-image-more's inline fetch for that image fails → that layer is dropped from the capture
  (or, worst case, the whole primary render throws and the modern-screenshot fallback runs). Either way
  the snapshot still exports. Flagged in §4 and the build-time checklist (§5).
- If **both** captures return blank/throw, `snapCaptureMap()` throws → the user gets a red toast and
  nothing else breaks.

### 1.3 Self-contained HTML — inline everything, ship zero JavaScript

The generated `.html` is **pure HTML + inline CSS + one `data:image/png;base64` map image**:

- No `<script>` at all → renders in every mail-client webview, survives corporate mail filters better,
  and trivially works offline (nothing to fetch).
- No web fonts (system font stack, same as the app), no external images (the logo is an inline SVG —
  the same bolt already used for the app favicon, line 7), no external CSS.
- Light/dark via `@media (prefers-color-scheme: dark)`; single-column at phone widths via one media
  query; `@media print` rules so the .html itself prints cleanly (a free second path to PDF).
- Size: base64 costs +33% over the raw PNG. A full-screen 2× capture is ~1–4 MB of PNG → a 1.5–5.5 MB
  .html. Fine for email (Gmail 25 MB) and Messages. The capture scale is capped (§3d) to keep it there.

### 1.4 PDF — **jsPDF (UMD), drawing the card natively** (not html2pdf.js)

- **html2pdf.js** = html2canvas + jsPDF glued together: it would rasterize the *entire* card, giving
  blurry text, and it drags in its own bundled (older) html2canvas — a second copy of a dependency we
  already load. Its maintenance is intermittent. ❌
- **Browser print-to-PDF** needs user steps (Ctrl-P, choose printer) — not "one tap", and mobile Safari
  buries it. Kept only as the implicit bonus path via the .html's print CSS. ❌ as primary.
- **jsPDF 4.2.1** ✅ (published 2026-03-17, actively maintained): `doc.addImage()` embeds the map and
  the header / data rows / footer are drawn as **real vector text** — crisp at any zoom, tiny file.
  ~70 lines (§3f), one pinned UMD build. US Letter format (the user's locale). **Embed the JPEG, not
  the PNG** — jsPDF stores PNGs uncompressed and its pure-JS PNG decoder is slow on multi-megapixel
  captures (parallax/jsPDF#1787); the `pngToJpeg()` helper in §3d hands `addImage(..., 'JPEG')` a
  small 0.85-quality image while the offline .html keeps the lossless PNG.

### 1.5 Ship — Web Share API Level 2, with graceful degradation

- `navigator.share({ files })` + capability check `navigator.canShare({ files })` is the only way to
  hand an actual **file** to the OS share sheet from the web. Supported: Chrome/Edge Android,
  iOS/iPadOS Safari 15+, Chrome/Edge on Windows desktop; **not** Firefox desktop. Requirements we
  satisfy: **secure context** (GitHub Pages HTTPS ✓, `http://localhost:8001` counts as secure ✓) and a
  **transient user activation** — which is why sharing happens on the modal's *Share* button click,
  never automatically after the async capture (the original gesture would have expired).
- **MIME caveat**: some platforms (iOS notably) accept `application/pdf` files but refuse `text/html`
  files in the share sheet. So the share logic tries file combos in order — `[html, pdf]` → `[pdf]` →
  `[html]` — using `canShare` before each attempt, and falls back to downloading both.
- **mailto: cannot attach files** — full stop, no workaround exists. Never offer it; the share sheet's
  Mail target is the correct route (the OS attaches the file itself).
- Desktop fallback: classic `URL.createObjectURL` + `<a download>` — works everywhere including
  Firefox; the user attaches the file to email manually.

---

## 2. App state the snapshot reads (verified ids / globals, no new bookkeeping needed)

| What | Where it already lives | Line refs |
|---|---|---|
| Map view | `map.getCenter()`, `map.getZoom()` — `map` is a global set in `initMap()` | 2537 |
| Active basemap | `Object.entries(baseLayers).find(([,l]) => l && map.hasLayer(l))` — keys `light/dark/satellite/topo/dem/hillshade`; `setBase()` keeps exactly one on the map | 2539–2567, 4070 |
| Enabled overlay layers | Layers-tab checkboxes `#layers-tab input[type=checkbox]:checked`; human label = sibling `.layer-label` text (e.g. `id="lyr-alerts"` → "NWS Active Alerts") | 938–1406 |
| Open detail card | `#detail` (`style.display` = `'flex'`, or `'block'` for the Montana-mesonet card at 8246). One reused DOM serves **all** card types — alert (`showDetail`, 2902), fire incident (`showFireCard`, 6251), perimeter (`showFirePerimCard`, 6299), gauges, stations — so one generic scrape covers everything: title `#det-event`, chips `#det-chips .det-chip`, label/value pairs `.df > .dl/.dv` inside `#det-body`, long text `#det-desc` | 178–211, 2902–2949 |
| Wind readout | `leaflet-velocity`'s `displayValues` control → `document.querySelector('.leaflet-control-velocity')` (bottom-left; exists only while the Wind Flow layer is on) | 6936–6947 |
| National alert counts | Header chips `#count-bar .chip` (e.g. "3 Tornado Warning") | 876 |
| Timestamp format | `fmtDT()` — military time (`hourCycle:'h23'`) + timezone abbrev; the snapshot uses the **same function** so times match the app everywhere | 5480 |
| Escaping | `esc()` — used on every string interpolated into the generated HTML | 5495 |
| Attribution | `map.attributionControl._container.textContent` (live union of whatever layers are on) | — |
| Toasts / disabled states | `toast(msg,color,ms)` 5211; button-disable pattern like `#refresh-btn` 36–38 | |

No new persistent state; one module-level `snapLast` holds the most recent snapshot for the modal.

---

## 3. Implementation — ready-to-paste blocks

### 3a. CDN scripts

**Anchor** — the existing script block at lines 2247–2249:

```html
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/leaflet-velocity@1.7.0/dist/leaflet-velocity.min.js"></script>
```

**Insert immediately after the leaflet-velocity line** (all three verified HTTP 200 on jsdelivr
2026-07-07):

```html
<script src="https://cdn.jsdelivr.net/npm/dom-to-image-more@3.10.0/dist/dom-to-image-more.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/modern-screenshot@4.7.0/dist/index.js"></script>
<script src="https://cdn.jsdelivr.net/npm/jspdf@4.2.1/dist/jspdf.umd.min.js"></script>
```

Globals exposed: **`domtoimage`** (dom-to-image-more), **`modernScreenshot`** (modern-screenshot —
note the verified path is `dist/index.js`; `dist/index.global.js` is a 404), and **`jspdf.jsPDF`**
(destructured in §3f). All plain UMD globals — matches the app's static-tag convention (no modules, no
build step). **Build-time check:** after adding, open DevTools console and confirm `typeof domtoimage`,
`typeof modernScreenshot`, and `typeof jspdf` are all `object`/`function` before wiring the button.
If page weight ever matters these can be lazy-injected on first click; static tags are simpler and
recommended.

### 3b. Trigger UI — the 📸 Snapshot button

**Anchor** — the header, lines 872–880. Existing code:

```html
  <span id="clock"></span>
  <button id="refresh-btn" onclick="manualRefresh()">↻ Refresh</button>
</div>
```

**Insert a new line between the refresh button and `</div>`** (placing Snapshot to the *right* of
Refresh keeps `#refresh-btn{margin-left:auto}` doing the right-alignment work untouched — zero layout
risk):

```html
  <button id="refresh-btn" onclick="manualRefresh()">↻ Refresh</button>
  <button id="snap-btn" onclick="takeSnapshot()" title="Clip · Zip · Ship — capture this view as a shareable file">📸 Snapshot</button>
</div>
```

**Button CSS anchor** — immediately after line 38 (`#refresh-btn:disabled{opacity:0.35;cursor:default}`):

```css
#snap-btn{background:var(--bg3);border:1px solid var(--border);color:var(--text2);padding:4px 11px;border-radius:6px;cursor:pointer;font-size:12px;flex-shrink:0;transition:all 0.15s}
#snap-btn:hover{background:#2a2a55;color:#fff}
#snap-btn:disabled{opacity:0.35;cursor:default}
```

(Mirrors `#refresh-btn` exactly, including its dark hover.)

### 3c. Modal HTML + CSS

**HTML anchor** — line 2098, `<div id="toasts"></div>` inside `#map-wrap`. **Insert immediately after it:**

```html
    <!-- SNAPSHOT MODAL — Clip · Zip · Ship -->
    <div id="snap-modal" onclick="if(event.target===this)closeSnapModal()">
      <div id="snap-card-ui">
        <div id="snap-hdr">📸 Snapshot ready <button id="snap-close" onclick="closeSnapModal()" title="Close">✕</button></div>
        <img id="snap-preview" alt="Snapshot preview">
        <div id="snap-meta"></div>
        <div id="snap-actions">
          <button id="snap-share-btn" class="snap-act primary" onclick="shipSnapshot()">📤 Share…</button>
          <button class="snap-act" onclick="downloadSnapshot('html')">⬇ .html</button>
          <button class="snap-act" onclick="downloadSnapshot('pdf')">⬇ .pdf</button>
        </div>
        <div id="snap-note"></div>
      </div>
    </div>
```

**CSS anchor** — append to the `#snap-btn` rules added in §3b (all text is dark-on-white per the
standing contrast rule — no #777/#888/#999 greys):

```css
/* ── SNAPSHOT MODAL (Clip · Zip · Ship) ──────────────────────────── */
#snap-modal{position:fixed;inset:0;background:rgba(10,15,28,0.55);z-index:3000;display:none;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
#snap-card-ui{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;width:min(430px,92vw);max-height:88vh;overflow-y:auto;box-shadow:0 12px 48px rgba(0,0,0,0.35)}
#snap-hdr{font-size:14px;font-weight:800;color:#1a1d2e;display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
#snap-close{background:none;border:none;color:#4f5666;cursor:pointer;font-size:15px;padding:2px 6px;border-radius:4px}
#snap-close:hover{color:#1a1d2e}
#snap-preview{width:100%;border-radius:8px;border:1px solid var(--border);display:block;margin-bottom:10px;max-height:240px;object-fit:cover;object-position:center top;background:#eef0f5}
#snap-meta{font-size:11px;color:#2d333e;line-height:1.6;margin-bottom:12px}
#snap-actions{display:flex;gap:8px;flex-wrap:wrap}
.snap-act{flex:1;min-width:96px;background:var(--bg3);border:1px solid var(--border);color:#1a1d2e;padding:8px 10px;border-radius:7px;cursor:pointer;font-size:12px;font-weight:700;transition:all 0.15s}
.snap-act:hover{background:#dfe3ee}
.snap-act.primary{background:#d42b2b;border-color:#d42b2b;color:#fff}
.snap-act.primary:hover{background:#b82222}
#snap-note{font-size:10px;color:#4f5666;margin-top:10px;line-height:1.5}
```

### 3d. Capture + compose + package (main JS block)

**Anchor** — insert as a new section **immediately before** the REFRESH section header at lines
5243–5247:

```js
// ═══════════════════════════════════════════════════════════════════
// REFRESH
// ═══════════════════════════════════════════════════════════════════

async function manualRefresh() {
```

**Paste this entire block above that header:**

```js
// ═══════════════════════════════════════════════════════════════════
// SNAPSHOT — Clip · Zip · Ship  (📸 header button)
// Captures the current view + open card + wind readout into a branded,
// self-contained .html (offline-capable) and a .pdf, then shares or
// downloads them. No server, no external requests in the output file.
// ═══════════════════════════════════════════════════════════════════

let snapLast = null;   // { state, png:{dataUri,w,h}, htmlFile, pdfFile }

async function takeSnapshot() {
  const btn = document.getElementById('snap-btn');
  if (btn.disabled) return;
  btn.disabled = true; btn.textContent = '📸 Capturing…';
  try {
    const state = snapCollectState();
    const png   = await snapCaptureMap();
    const html  = snapBuildHtml(state, png);
    const pdf   = snapBuildPdf(state, png);
    const base  = 'StormWatch_' + state.fileStamp;
    snapLast = {
      state, png,
      htmlFile: new File([html], base + '.html', { type: 'text/html' }),
      pdfFile:  new File([pdf],  base + '.pdf',  { type: 'application/pdf' }),
    };
    snapShowModal();
  } catch (e) {
    console.error('takeSnapshot:', e);
    toast('Snapshot failed — see console for details', '#ff4444', 6000);
  } finally {
    btn.disabled = false; btn.textContent = '📸 Snapshot';
  }
}

// ── 1. Read everything the app already knows ──────────────────────
function snapCollectState() {
  const now = new Date(), iso = now.toISOString();
  const c = map.getCenter(), z = map.getZoom();
  const BASE_NAMES = { light:'Light', dark:'Dark', satellite:'Satellite',
                       topo:'Topographic', dem:'USGS Topo', hillshade:'Hillshade' };
  const baseKey = (Object.entries(baseLayers).find(([,l]) => l && map.hasLayer(l)) || ['light'])[0];

  const layers = [...document.querySelectorAll('#layers-tab input[type=checkbox]:checked')]
    .map(cb => cb.closest('.layer-row')?.querySelector('.layer-label')?.textContent.trim())
    .filter(Boolean);

  const natChips = [...document.querySelectorAll('#count-bar .chip')]
    .map(el => el.textContent.trim()).filter(Boolean);

  // The one reused #detail DOM serves alert / fire / perimeter / gauge /
  // station cards alike, so a single generic scrape covers every card type.
  // NOTE: pair on .dl labels, NOT .df wrappers — the Effective/Expires row
  // (#det-dates-row, line 2086; repurposed by fire cards as Discovered/Size
  // and Size/Contained) is a plain flex div, not a .df, and would be missed.
  let card = null;
  const det = document.getElementById('detail');
  if (det && det.style.display && det.style.display !== 'none') {
    const fields = [...det.querySelectorAll('#det-body .dl')]
      .filter(dl => dl.offsetParent !== null &&
                    !dl.closest('#det-desc-row') && !dl.closest('#det-instr-wrap'))
      .map(dl => ({ l: dl.textContent.trim(),
                    v: dl.parentElement.querySelector('.dv')?.textContent.trim() || '' }))
      .filter(f => f.v && f.v !== '—');
    const instrWrap = document.getElementById('det-instr-wrap');
    card = {
      title: document.getElementById('det-event')?.textContent.trim() || 'Detail',
      color: document.getElementById('det-event')?.style.color || '#d42b2b',
      sub:   document.getElementById('det-sev-desc')?.textContent.trim() || '',
      chips: [...det.querySelectorAll('#det-chips .det-chip')]
               .map(el => el.textContent.trim().replace(/\s+/g, ' ')),
      fields,
      instr: (instrWrap && instrWrap.offsetParent !== null)
               ? (document.getElementById('det-instr')?.textContent || '').trim().slice(0, 600) : '',
      desc: (document.getElementById('det-desc')?.textContent || '').trim().slice(0, 900),
    };
    // Cards that replace #det-body wholesale (e.g. Montana mesonet, line 8244)
    if (!card.fields.length && !card.desc)
      card.desc = (det.querySelector('#det-body')?.innerText || '')
                    .trim().replace(/\n{3,}/g, '\n\n').slice(0, 900);
  }

  const wind = document.querySelector('.leaflet-control-velocity')?.textContent.trim() || null;
  const attrib = map.attributionControl?._container?.textContent.trim()
              || '© OpenStreetMap © CARTO · data NOAA / NWS / NIFC / USGS';

  return {
    tsText: fmtDT(now),                                             // same clock format as the app
    fileStamp: iso.slice(0,10) + '_' + iso.slice(11,16).replace(':','') + 'Z',
    lat: c.lat.toFixed(3), lon: c.lng.toFixed(3), zoom: z,
    baseName: BASE_NAMES[baseKey] || baseKey,
    layers, natChips, card, wind, attrib,
    url: location.href.split('#')[0],
  };
}

// ── 2. Rasterize the map (foreignObject primary + fallback) ───────
// dom-to-image-more lets the browser engine paint the DOM, so Leaflet's
// translate3d panes + SVG overlays + canvas overlays come through cleanly
// (html2canvas mangles those transforms). The whole foreignObject family
// can render blank on Safari's FIRST pass, so the primary renders twice.
async function snapCaptureMap() {
  const mapEl = document.getElementById('map');
  const cw = mapEl.clientWidth, ch = mapEl.clientHeight;
  // Retina-crisp but bounded twice over: ≤2600px wide (email-sized .html)
  // AND ≤16.7M px total (Safari's hard canvas-area cap — above it = black).
  let scale = Math.min(2, Math.max(1, window.devicePixelRatio || 1), 2600 / cw);
  if (cw * ch * scale * scale > 16000000) scale = Math.sqrt(16000000 / (cw * ch));

  const looksBlank = uri => !uri || uri.length < 3000;   // empty foreignObject → tiny data URI

  // Primary: dom-to-image-more, hi-res via width/height + CSS scale, double render.
  const opts = {
    bgcolor: '#eef0f5',
    width: cw * scale, height: ch * scale,
    style: { transform: 'scale(' + scale + ')', transformOrigin: 'top left' },
    cacheBust: true, imagePlaceholder: undefined,
  };
  let dataUri = '';
  try {
    dataUri = await domtoimage.toPng(mapEl, opts);          // warm-up pass (may be blank on Safari)
    dataUri = await domtoimage.toPng(mapEl, opts);          // keep the second
  } catch (e) { console.warn('snapshot: dom-to-image-more failed', e); }

  // Fallback: modern-screenshot (different foreignObject impl).
  if (looksBlank(dataUri)) {
    try {
      dataUri = await modernScreenshot.domToPng(mapEl, { scale, backgroundColor: '#eef0f5' });
    } catch (e) { console.warn('snapshot: modern-screenshot fallback failed', e); }
  }
  if (looksBlank(dataUri)) throw new Error('map capture produced no image');

  const w = Math.round(cw * scale), h = Math.round(ch * scale);
  // Derive a JPEG for the PDF (PNG in a PDF bloats the file + decodes slowly in
  // jsPDF's pure-JS path). One canvas re-encode from the same-origin data URI.
  const jpegUri = await pngToJpeg(dataUri, w, h);
  return { dataUri, jpegUri, w, h };
}

function pngToJpeg(pngUri, w, h) {
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement('canvas'); c.width = w; c.height = h;
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#eef0f5'; ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL('image/jpeg', 0.85));
      } catch (_) { resolve(pngUri); }     // fall back to PNG if anything trips
    };
    img.onerror = () => resolve(pngUri);
    img.src = pngUri;
  });
}

// ── 5. Modal / ship / download ────────────────────────────────────
function snapShowModal() {
  const { state, png, htmlFile, pdfFile } = snapLast;
  document.getElementById('snap-preview').src = png.dataUri;
  document.getElementById('snap-meta').innerHTML =
    `<b>${esc(state.card ? state.card.title : 'Current view')}</b> · ${esc(state.tsText)}<br>` +
    `${esc(state.lat)}, ${esc(state.lon)} · zoom ${esc(String(state.zoom))} · ` +
    `${(htmlFile.size/1048576).toFixed(1)} MB html · ${(pdfFile.size/1048576).toFixed(1)} MB pdf`;
  let canShare = false;
  try {
    canShare = !!(navigator.canShare &&
      (navigator.canShare({ files: [pdfFile] }) || navigator.canShare({ files: [htmlFile] })));
  } catch (_) {}
  document.getElementById('snap-share-btn').style.display = canShare ? '' : 'none';
  document.getElementById('snap-note').textContent = canShare
    ? 'Share hands the file straight to Mail / Messages. The .html opens offline on any phone or computer.'
    : 'This browser can’t share files directly — download, then attach to an email. The .html opens offline on any phone or computer.';
  document.getElementById('snap-modal').style.display = 'flex';
}
function closeSnapModal() { document.getElementById('snap-modal').style.display = 'none'; }

async function shipSnapshot() {
  if (!snapLast) return;
  const { htmlFile, pdfFile, state } = snapLast;
  const meta = { title: 'StormWatch snapshot',
                 text: 'StormWatch Live snapshot — ' + state.tsText };
  // Some platforms (iOS) refuse text/html files in the share sheet → try combos.
  const combos = [[htmlFile, pdfFile], [pdfFile], [htmlFile]];
  for (const files of combos) {
    let ok = false;
    try { ok = navigator.canShare && navigator.canShare({ files }); } catch (_) {}
    if (!ok) continue;
    try { await navigator.share({ ...meta, files }); return; }
    catch (err) { if (err.name === 'AbortError') return; }   // user closed the sheet — done
  }
  downloadSnapshot('html'); downloadSnapshot('pdf');
  toast('Direct share unavailable here — both files downloaded instead', '#4488ff', 6000);
}

function downloadSnapshot(kind) {
  if (!snapLast) return;
  const f = kind === 'pdf' ? snapLast.pdfFile : snapLast.htmlFile;
  const url = URL.createObjectURL(f);
  const a = document.createElement('a');
  a.href = url; a.download = f.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
```

(§3e `snapBuildHtml` and §3f `snapBuildPdf` below complete this block — paste them directly after
`snapCaptureMap()`, i.e. where the "── 5." comment sits, keeping the numbered order 1-capture,
2-raster, 3-html, 4-pdf, 5-ship.)

### 3e. The generated situation card — `snapBuildHtml()`

This is the "beautiful, compelling" part: a branded card, not a bare screenshot. Pure HTML+CSS, zero
JS, everything inlined. All dynamic strings pass through the app's own `esc()`.

```js
// ── 3. Compose the self-contained situation-card .html ────────────
function snapBuildHtml(s, png) {
  const pills = (s.layers.length ? s.layers : ['Base map only'])
    .map(l => `<span class="pill">${esc(l)}</span>`).join('');
  const nat = s.natChips.length
    ? `<div class="nat">${s.natChips.map(x => `<span class="natchip">${esc(x)}</span>`).join('')}</div>` : '';
  let cardHtml = '';
  if (s.card) {
    const chips  = s.card.chips.map(x => `<span class="chip">${esc(x)}</span>`).join('');
    const rows   = s.card.fields.map(f =>
      `<div class="row"><span class="k">${esc(f.l)}</span><span class="v">${esc(f.v)}</span></div>`).join('');
    const instr  = s.card.instr ? `<div class="instr">⚠ ${esc(s.card.instr)}</div>` : '';
    const desc   = s.card.desc ? `<p class="desc">${esc(s.card.desc)}</p>` : '';
    cardHtml = `
  <section class="card" style="border-left-color:${esc(s.card.color)}">
    <h2 style="color:${esc(s.card.color)}">${esc(s.card.title)}</h2>
    ${s.card.sub ? `<p class="sub">${esc(s.card.sub)}</p>` : ''}
    ${chips ? `<div class="chips">${chips}</div>` : ''}
    ${rows ? `<div class="rows">${rows}</div>` : ''}
    ${instr}
    ${desc}
  </section>`;
  }
  const windHtml = s.wind ? `
  <section class="wind"><span class="wlbl">Wind readout</span> ${esc(s.wind)}</section>` : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StormWatch Snapshot — ${esc(s.card ? s.card.title : s.tsText)}</title>
<style>
:root{--bg:#eef0f5;--panel:#ffffff;--border:#d4d8e4;--text:#1a1d2e;--text2:#2d333e;--muted:#4f5666;--accent:#d42b2b}
@media (prefers-color-scheme: dark){
  :root{--bg:#0b1020;--panel:#101a2c;--border:#243248;--text:#dce7f5;--text2:#c6d4ea;--muted:#9db2d2}
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);padding:18px 12px;line-height:1.5}
.wrap{max-width:680px;margin:0 auto}
header{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.brand{font-size:19px;font-weight:800;color:var(--accent);letter-spacing:-0.3px;white-space:nowrap}
.brand .k{display:block;font-size:9px;font-weight:700;letter-spacing:2.2px;color:var(--muted);text-transform:uppercase;margin-top:1px}
.ts{font-size:12px;font-weight:700;color:var(--text2);font-variant-numeric:tabular-nums;text-align:right}
figure{background:var(--panel);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 3px 16px rgba(10,15,28,0.10)}
figure img{width:100%;display:block}
figcaption{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:8px 12px;font-size:11px;color:var(--muted);border-top:1px solid var(--border);font-variant-numeric:tabular-nums}
section{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-top:12px}
.card{border-left:4px solid var(--accent)}
.card h2{font-size:16px;font-weight:800;margin-bottom:8px;line-height:1.3}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.chip{border:1px solid var(--border);border-radius:6px;padding:3px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text2)}
.rows{margin-bottom:6px}
.row{display:flex;justify-content:space-between;gap:14px;padding:5px 0;border-bottom:1px solid var(--border);font-size:13px}
.row:last-child{border-bottom:none}
.k{color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;padding-top:2px;white-space:nowrap}
.v{color:var(--text);font-weight:600;text-align:right}
.sub{font-size:11.5px;color:var(--muted);margin:-4px 0 8px}
.instr{background:rgba(255,140,0,0.12);border-left:3px solid #e8720c;border-radius:0 6px 6px 0;padding:8px 11px;font-size:12.5px;color:var(--text2);white-space:pre-wrap;line-height:1.6;margin:8px 0}
.desc{font-size:12.5px;color:var(--text2);white-space:pre-wrap;line-height:1.65;margin-top:6px}
.wind{font-size:13px;font-weight:600;color:var(--text)}
.wlbl{display:inline-block;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.8px;color:var(--accent);margin-right:8px}
.lyr h3,.natwrap h3{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px}
.pills{display:flex;gap:6px;flex-wrap:wrap}
.pill{background:var(--bg);border:1px solid var(--border);border-radius:20px;padding:3px 11px;font-size:11px;font-weight:600;color:var(--text2)}
.nat{display:flex;gap:6px;flex-wrap:wrap}
.natchip{border:1px solid var(--border);border-radius:20px;padding:3px 11px;font-size:11px;font-weight:700;color:var(--text2)}
footer{margin-top:14px;font-size:10px;color:var(--muted);line-height:1.7;text-align:center}
footer a{color:var(--accent);text-decoration:none;font-weight:700}
.disclaim{margin-top:4px;font-style:italic}
@media (max-width:480px){body{padding:10px 8px}.row{flex-direction:column;gap:1px}.v{text-align:left}}
@media print{body{background:#fff;padding:0}.wrap{max-width:100%}figure,section{box-shadow:none;break-inside:avoid}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">&#9889; Storm<span style="font-style:normal">Watch</span> Live<span class="k">Situation snapshot</span></div>
    <div class="ts">${esc(s.tsText)}</div>
  </header>
  <figure>
    <img src="${png.dataUri}" alt="Map snapshot" width="${png.w}" height="${png.h}">
    <figcaption><span>${esc(s.lat)}, ${esc(s.lon)} &middot; zoom ${esc(String(s.zoom))}</span><span>${esc(s.baseName)} basemap</span></figcaption>
  </figure>
${cardHtml}${windHtml}
  ${nat ? `<section class="natwrap"><h3>Active US alerts</h3>${nat}</section>` : ''}
  <section class="lyr"><h3>Layers shown</h3><div class="pills">${pills}</div></section>
  <footer>
    ${esc(s.attrib)}<br>
    Captured from <a href="${esc(s.url)}">StormWatch Live</a> &middot; works offline &middot; Clip &middot; Zip &middot; Ship
    <div class="disclaim">Snapshot of live data at capture time — verify current conditions at weather.gov before acting.</div>
  </footer>
</div>
</body>
</html>`;
}
```

Design notes: matches the app's brand (accent `#d42b2b`, same font stack, same military-time
`fmtDT`), obeys the standing **contrast rule** (body text `#1a1d2e` on white; the lightest ink used is
`#4f5666` and only for captions), single-column on phones (`max-width:480px` collapses the key/value
rows), dark-mode via `prefers-color-scheme`, print-friendly. The template contains **no** literal
`</script>` sequence, so it is safe to build inside the app's own inline script.

### 3f. PDF — `snapBuildPdf()`

```js
// ── 4. Draw the same card natively in jsPDF (vector text + JPEG map) ─
function snapBuildPdf(s, png) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: 'pt', format: 'letter' });          // 612 × 792 pt
  const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight(), M = 42;
  let y = M;
  const pageBreak = need => { if (y + need > H - M) { doc.addPage(); y = M; } };
  // helvetica is Latin-1 only. Scraped alert text is full of smart punctuation
  // (— ' ' " " … •) that would render as tofu — normalize to ASCII, drop the rest.
  const P = t => String(t == null ? '' : t)
    .replace(/[‘’‚]/g, "'").replace(/[“”„]/g, '"')
    .replace(/[–—―]/g, '-').replace(/…/g, '...')
    .replace(/[•·]/g, '·')                       // bullets → middot (Latin-1, OK)
    .replace(/[^\x00-\xFF]/g, '');                          // strip anything still non-Latin-1

  // jsPDF's built-in helvetica is Latin-1 only — NO emoji (⚡/⚠ render as tofu).
  // Keep all PDF text plain ASCII; the ⚡ brand mark lives only in the .html + UI.
  doc.setFont('helvetica', 'bold'); doc.setFontSize(17); doc.setTextColor(212, 43, 43);
  doc.text('StormWatch Live', M, y);
  doc.setFontSize(8); doc.setTextColor(79, 86, 102); doc.setFont('helvetica', 'normal');
  doc.text('SITUATION SNAPSHOT  ·  ' + P(s.tsText), M, y + 13);
  y += 26;

  // Map image (JPEG — small + fast in jsPDF), fit to page width, aspect preserved
  let iw = W - 2 * M, ih = iw * (png.h / png.w);
  if (ih > 400) { ih = 400; iw = ih * (png.w / png.h); }
  doc.addImage(png.jpegUri, 'JPEG', M, y, iw, ih);
  y += ih + 12;
  doc.setFontSize(8); doc.setTextColor(79, 86, 102);
  doc.text(`${s.lat}, ${s.lon}  ·  zoom ${s.zoom}  ·  ${P(s.baseName)} basemap`, M, y);
  y += 18;

  if (s.card) {
    pageBreak(40);
    doc.setDrawColor(212, 43, 43); doc.setLineWidth(2); doc.line(M, y - 10, M, y + 6);
    doc.setFont('helvetica', 'bold'); doc.setFontSize(13); doc.setTextColor(26, 29, 46);
    doc.text(P(s.card.title), M + 10, y); y += 16;
    doc.setFont('helvetica', 'normal'); doc.setFontSize(9.5);
    for (const f of s.card.fields) {
      pageBreak(14);
      doc.setTextColor(79, 86, 102); doc.text(P(f.l) + ':', M + 10, y);
      doc.setTextColor(26, 29, 46);  doc.text(P(f.v), M + 110, y, { maxWidth: W - M - 110 - M });
      y += 14;
    }
    if (s.card.instr) {
      const il = doc.splitTextToSize('! ' + P(s.card.instr), W - 2 * M - 10);   // ASCII-only (no ⚠ in PDF)
      pageBreak(il.length * 11 + 10);
      doc.setTextColor(196, 92, 10); doc.setFont('helvetica', 'bold');
      doc.text(il, M + 10, y + 4); y += il.length * 11 + 10;
      doc.setFont('helvetica', 'normal');
    }
    if (s.card.desc) {
      const lines = doc.splitTextToSize(P(s.card.desc), W - 2 * M - 10);
      pageBreak(Math.min(lines.length, 8) * 11 + 8);
      doc.setTextColor(45, 51, 62);
      doc.text(lines, M + 10, y + 4); y += lines.length * 11 + 12;
    }
  }
  if (s.wind) { pageBreak(16); doc.setTextColor(26,29,46); doc.setFont('helvetica','bold');
    doc.setFontSize(9.5); doc.text('Wind readout:  ' + P(s.wind), M, y); y += 16; }
  if (s.layers.length) { pageBreak(24);
    doc.setFont('helvetica','normal'); doc.setFontSize(8.5); doc.setTextColor(79,86,102);
    const ll = doc.splitTextToSize('Layers: ' + P(s.layers.join('  ·  ')), W - 2 * M);
    doc.text(ll, M, y); y += ll.length * 11 + 6; }

  doc.setFontSize(7); doc.setTextColor(120, 126, 140);
  doc.text(doc.splitTextToSize(P(s.attrib) + '  ·  Snapshot of live data at capture time - verify at weather.gov.', W - 2 * M),
           M, H - M + 14);
  return doc.output('blob');
}
```

---

## 4. Honest limitations (tell the user these up front)

1. **The wind-flow animation freezes.** `leaflet-velocity` paints particles to a canvas; the capture
   copies whatever trails are on screen that instant — a genuinely nice static frame, but motion is
   not shippable in a static file. Same for animating radar: the current frame only.
2. **Safari can blank the first `foreignObject` render** (WebKit bug 23113) — the entire dom-to-image /
   modern-screenshot family shares this. Mitigated by the **double render** in the primary (§3d) plus
   the modern-screenshot fallback; the `looksBlank()` guard turns a silent blank into a caught failure.
   Must be tested on a real iPhone (§5), not just desktop.
3. **CORS-less overlay images vanish silently.** dom-to-image-more inlines images via its own fetch; a
   host that doesn't answer CORS drops that layer from the capture. The default basemaps
   (CARTO/OSM/Esri/USGS) all send `ACAO:*`; the WMS overlays (IEM radar/MRMS, FEMA, NAQFC) must be
   spot-checked at build time (§5) — if one is missing from captures, that's why.
4. **What's outside `#map` isn't in the image** — the north arrow, zoom badge, legends, and detail
   panel are siblings in `#map-wrap`, so the raster is a clean map; their *information* travels as
   crisp text in the card instead (by design — a screenshot of a panel is worse than its text).
5. **iOS share sheets may refuse `text/html` files** — *unverified* (Apple publishes no allowlist).
   Handled by the `[pdf]`-only combo fallback in `shipSnapshot()`; the .html remains downloadable
   (lands in the Files app) on iOS regardless. Chromium *does* allow `.html` + `application/pdf`
   (confirmed in its permitted-extensions doc), so Android/desktop share both.
6. **Firefox desktop has no Web Share** — the Share button hides itself; downloads always work.
7. **`mailto:` cannot attach files** — never offered; the OS share sheet's Mail target attaches.
8. **File size / Safari canvas cap** — a full-screen 2× PNG is ~1–4 MB → .html ~1.5–5.5 MB (base64
   +33%; the PDF is far smaller thanks to the JPEG). Capture is capped at 2600 px wide **and** at
   Safari's hard 16.7-Mpx canvas-area limit (above it Safari returns black) — both enforced in §3d.
9. **iOS share promise can misreport on first invocation** (Apple dev forums 662629) — `shipSnapshot()`
   treats `AbortError` as "user done" and otherwise falls through to download, so a flaky resolve never
   strands the user.

## 5. Build-time test checklist

1. Desktop Chrome, Light base, several alert polygons visible + one alert card open → snapshot →
   .html opens offline (disconnect Wi-Fi), dark-mode toggle of the OS flips the card theme.
2. Repeat on Dark base + Satellite base (Esri) — confirm tiles render in the capture (CORS ✓).
3. Fire view: perimeters + incidents + a fire card open (name/acres/containment rows appear in card
   and PDF).
4. Wind Flow layer on → readout line appears; captured frame shows particle trails.
5. Radar + MRMS + FEMA on → check the capture for blank layers (CORS spot-check, §4.2); note results
   in the commit message.
6. PDF opens in Chrome, Edge, and Acrobat; map aspect correct; long alert description paginates.
7. **Real iPhone Safari** (not simulator): 📸 → confirm the map image is NOT blank (the double-render
   + fallback should prevent it) → Share… → expect the PDF-only combo → confirm .html download lands
   in Files and opens offline. This is the highest-risk path (foreignObject blank-render).
8. Android Chrome (GitHub Pages URL): 📸 → Share… → Gmail — both files attach.
9. Firefox desktop: Share button hidden, downloads work.
10. Regression sweep per the standing checklist: alert layer still on by default, polygon click still
    opens the card, no JS parse errors on load (the new block contains template literals — load the
    file once with DevTools console open); the three new CDN scripts resolve (Network tab, no 404).

## 6. Effort estimate

~370 new lines (3 script tags, 1 button, ~30 lines CSS, ~15 lines modal HTML, ~310 lines JS), all
additive — **zero changes to existing lines**, so regression risk is confined to (a) header flex
layout (mitigated by inserting after `#refresh-btn`) and (b) global-namespace collisions (all new
identifiers are `snap*` / `takeSnapshot` / `shipSnapshot` / `downloadSnapshot` / `closeSnapModal` /
`pngToJpeg` — grep-verified unused in the current file, 2026-07-07).

## 7. Verified facts log (research 2026-07-07)

| Claim | Verified how | Result |
|---|---|---|
| html2canvas mangles Leaflet CSS-transform panes / drops SVG | Leaflet/Leaflet#3991, niklasvh/html2canvas#567 | ✅ → rejected as primary |
| `foreignObject` family best for mixed SVG+canvas+img | library docs + monday.com engineering benchmark | ✅ chosen |
| dom-to-image-more latest = **3.10.0** (active, ~1 issue) | npm registry + GitHub `pushed_at` | ✅ |
| modern-screenshot latest = **4.7.0** (active) | npm + GitHub | ✅ (fallback) |
| jsPDF latest = **4.2.1**, UMD global `jspdf.jsPDF` | npm; jsdelivr URL HTTP 200 | ✅ |
| CARTO `basemaps.cartocdn.com` sends `ACAO: *` | curl with `Origin:` header | ✅ |
| OSM `tile.openstreetmap.org` sends `ACAO: *` | curl | ✅ |
| `share({files})`: iOS Safari 14+, Chrome Android 76+, desktop Chrome 128+ | MDN browser-compat-data, caniuse | ✅ |
| Chromium share allowlist includes `.html` + `application/pdf` | Chromium permitted-extensions doc | ✅ |
| iOS Safari accepts `text/html` File in share | no Apple allowlist published | ⚠ **unverified** → gate with `canShare`, PDF-first fallback |
| Safari canvas hard cap 16,777,216 px | blueimp/JavaScript-Load-Image#133 | ✅ → enforced in §3d |
| jsPDF core helvetica = Latin-1 only (no emoji/em-dash) | jsPDF docs | ✅ → `P()` sanitizer + ASCII PDF text |
| "SnapSaveState" capture library | web search | ❌ appears not to exist — not used |

Full source list is in the research thread (agent `Research capture/PDF/share libs`).
