# Spec 02 — USGS Fire Danger Forecast (WFPI) WMS Layer

*Written by Fable 2026-07-07. Target file: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` (single-file Leaflet app).*
*Pattern mirrored: the NAQFC smoke-forecast WMS layer (opacity slider + `viirs-day-btn` button row + `usgs-key` legend).*
*All endpoints verified live 2026-07-07 with curl — see §7 Verification Log.*

---

## 1. What this adds

One new toggle in the **Wildland Fire** layer group: **"Fire Danger Forecast (USGS)"** — the USGS EROS
national daily fire-danger raster, with:

- **Day 1–7 forecast buttons** (each day is a *separate GeoServer workspace* — day switching swaps the WMS URL + layer name, NOT a `TIME` param).
- **Product sub-toggle** (3 buttons): **WFPI** (Wildland Fire Potential Index, 0–247 index), **Large Fire %** (`wlfp`, probability a fire ≥ 500 ac occurs), **Spread %** (`wfsp`, probability an existing large fire spreads). All three share identical URL grammar and day structure.
- Opacity slider (default 70%) + a per-product color legend with **exact server colors** (extracted pixel-by-pixel from the live `GetLegendGraphic` PNGs — do not substitute).

Key endpoint facts (verified):

| Fact | Value |
|---|---|
| URL grammar | `https://dmsdata.cr.usgs.gov/geoserver/firedanger_{product}-forecast-{day}_conus_day_data/wms` |
| WMS layer name | `{product}-forecast-{day}_conus_day_data` (e.g. `wfpi-forecast-1_conus_day_data`) |
| `{product}` | `wfpi` \| `wlfp` \| `wfsp` — `{day}` = `1`…`7`. All 21 combinations return HTTP 200. |
| CRS offered | `EPSG:3857` + `CRS:84` only → perfect for Leaflet default (3857); WMS version **1.3.0** |
| Coverage | **CONUS only** — bbox lon −128.54…−65.39, lat 22.48…51.78 |
| TIME dimension | exists, `default="current"` → **omit TIME entirely**; server auto-serves today's issuance (archive back to 2008-08-01 available if a history scrubber is ever wanted) |
| Cadence | daily; latest granule on test date = same-day |
| Auth / CORS | no key; `Access-Control-Allow-Origin: *` (not even needed — plain `<img>` tiles) |
| License | US-government **public domain** (USGS EROS) |

---

## 2. Block (a) — HTML: toggle row + opacity + product/day buttons + legend

**Insertion anchor** — in the *Wildland Fire* layer group (starts line ~1144 `<div class="layer-group-title">Wildland Fire</div>`), insert **between the end of the KBDI legend and the WindNinja row**. The existing code reads (lines ~1330–1339):

```html
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ffd700;border-color:#aa9000"></div>200–400 Moderate</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff7700;border-color:#cc4400"></div>400–600 High</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#cc0000;border-color:#880000"></div>600–800 Extreme</div>
          </div>

          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-windninja" onchange="toggleLayer('windninja',this.checked)"><span class="toggle-slider"></span></label>
```

Paste this **into the blank line between the KBDI key's closing `</div>` and the WindNinja `<div class="layer-row">`**:

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-wfpi" onchange="toggleLayer('wfpi',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">Fire Danger Forecast (USGS)</span>
            <span class="layer-note" id="wfpi-note">off</span>
          </div>
          <div class="opacity-row" id="wfpi-opacity-row" style="display:none">
            <input type="range" min="10" max="100" value="70" oninput="setWfpiOpacity(this.value)">
            <span id="wfpi-opacity-val">70%</span>
          </div>
          <div id="wfpi-product-row" style="display:none;padding-left:44px;margin-top:-4px;margin-bottom:6px">
            <div class="usgs-key-hdr" style="margin-bottom:5px">Product</div>
            <div style="display:flex;gap:3px;flex-wrap:wrap">
              <button class="viirs-day-btn active" data-product="wfpi" onclick="setWfpiProduct('wfpi')">Fire Potential</button>
              <button class="viirs-day-btn" data-product="wlfp" onclick="setWfpiProduct('wlfp')">Large Fire %</button>
              <button class="viirs-day-btn" data-product="wfsp" onclick="setWfpiProduct('wfsp')">Spread %</button>
            </div>
          </div>
          <div id="wfpi-day-row" style="display:none;padding-left:44px;margin-top:0;margin-bottom:6px">
            <div class="usgs-key-hdr" style="margin-bottom:5px">Forecast Day</div>
            <div style="display:flex;gap:3px;flex-wrap:wrap">
              <button class="viirs-day-btn active" data-day="1" onclick="setWfpiDay(1)">D1</button>
              <button class="viirs-day-btn" data-day="2" onclick="setWfpiDay(2)">D2</button>
              <button class="viirs-day-btn" data-day="3" onclick="setWfpiDay(3)">D3</button>
              <button class="viirs-day-btn" data-day="4" onclick="setWfpiDay(4)">D4</button>
              <button class="viirs-day-btn" data-day="5" onclick="setWfpiDay(5)">D5</button>
              <button class="viirs-day-btn" data-day="6" onclick="setWfpiDay(6)">D6</button>
              <button class="viirs-day-btn" data-day="7" onclick="setWfpiDay(7)">D7</button>
            </div>
          </div>
          <div class="usgs-key" id="wfpi-key" style="display:none">
            <div id="wfpi-legend-wfpi">
              <div class="usgs-key-hdr">USGS EROS · Wildland Fire Potential Index · Daily · CONUS only</div>
              <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin:6px 0 3px;border:1px solid rgba(0,0,0,0.12)">
                <div style="flex:1;background:#004500"></div>
                <div style="flex:1;background:#006100"></div>
                <div style="flex:1;background:#0f8208"></div>
                <div style="flex:1;background:#40a621"></div>
                <div style="flex:1;background:#7ad445"></div>
                <div style="flex:1;background:#c2ff6e"></div>
                <div style="flex:1;background:#ffff19"></div>
                <div style="flex:1;background:#cf703d"></div>
                <div style="flex:1;background:#961900"></div>
                <div style="flex:1;background:#bf0000"></div>
                <div style="flex:2;background:#ff8000"></div>
                <div style="flex:2;background:#ff00ff"></div>
                <div style="flex:2;background:#ff0000"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text3)">
                <span>0</span><span>50</span><span>70</span><span>100</span><span>140</span><span>247</span>
              </div>
              <div style="font-size:9px;color:var(--text3);margin-top:3px">WFPI index · higher = greater fire potential · grey = agriculture/barren (non-burnable)</div>
            </div>
            <div id="wfpi-legend-wlfp" style="display:none">
              <div class="usgs-key-hdr">USGS EROS · Large Fire Probability · Daily · CONUS only</div>
              <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin:6px 0 3px;border:1px solid rgba(0,0,0,0.12)">
                <div style="flex:1;background:#00008f"></div>
                <div style="flex:1;background:#005ae1"></div>
                <div style="flex:1;background:#00bdff"></div>
                <div style="flex:1;background:#87ff78"></div>
                <div style="flex:1;background:#ecff13"></div>
                <div style="flex:1;background:#ffad00"></div>
                <div style="flex:1;background:#ff4a00"></div>
                <div style="flex:1;background:#e40000"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text3)">
                <span>0</span><span>.1</span><span>.5</span><span>1</span><span>2</span><span>3</span><span>5</span><span>7+%</span>
              </div>
              <div style="font-size:9px;color:var(--text3);margin-top:3px">% chance a large fire (≥500 ac) occurs · grey = non-burnable mask</div>
            </div>
            <div id="wfpi-legend-wfsp" style="display:none">
              <div class="usgs-key-hdr">USGS EROS · Fire Spread Probability · Daily · CONUS only</div>
              <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin:6px 0 3px;border:1px solid rgba(0,0,0,0.12)">
                <div style="flex:1;background:#00008f"></div>
                <div style="flex:1;background:#005aff"></div>
                <div style="flex:1;background:#00bdff"></div>
                <div style="flex:1;background:#87ff78"></div>
                <div style="flex:1;background:#ecff13"></div>
                <div style="flex:1;background:#ffad00"></div>
                <div style="flex:1;background:#ff4a00"></div>
                <div style="flex:1;background:#e40000"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text3)">
                <span>0</span><span>.5</span><span>1</span><span>2</span><span>5</span><span>10</span><span>20</span><span>30+%</span>
              </div>
              <div style="font-size:9px;color:var(--text3);margin-top:3px">% chance an existing fire spreads · grey = non-burnable mask</div>
            </div>
          </div>

```

Notes:
- Legend gradient bars follow the **NAQFC AQI-bar precedent** (`#naqfc-key`, lines ~1263–1277) rather than 13 `usgs-key-row` dots — the WFPI scale has 13 classes and rows would dominate the panel.
- All bar hexes were **pixel-sampled from the live GetLegendGraphic PNGs** (§7). The WFPI ramp is genuinely non-monotonic at the top (orange `#ff8000` → magenta `#ff00ff` → red `#ff0000` for 101–247); that is the server's SLD, reproduce as-is so the on-panel legend matches the map.
- Mask classes shared by all 3 products (mention only in the caption text, don't swatch them): Outside US `#d2d2d2`, Snow/Ice white, Ag Land `#4f4f4f`, Barren `#408080`, Marsh `#8ba58f`, Water `#e0edff`. The dark-grey Ag-Land band is very visible across the Plains — hence the "grey = non-burnable" caption.
- Text colors use `var(--text3)` / `usgs-key-hdr` exactly like the NAQFC key (contrast vars already darkened per project rule).

---

## 3. Block (b) — JS state variables

**Insertion anchor** — in the layer-state `let` block (~line 2515). Existing lines:

```js
let naqfcLayer = null, naqfcEnabled = false, naqfcOpacity = 0.70, naqfcForecastHours = 0;
let windninjaGroup = L.layerGroup(), windninjaEnabled = false;
```

Insert **between those two lines**:

```js
let wfpiLayer = null, wfpiEnabled = false, wfpiOpacity = 0.70, wfpiDay = 1, wfpiProduct = 'wfpi';
```

---

## 4. Block (c) — `toggleLayer` branch

**Insertion anchor** — inside `toggleLayer()`, immediately after the `kbdi` branch and before the `windninja` branch (~lines 3732–3736). Existing code:

```js
    } else {
      if (kbdiLayer) kbdiLayer.remove();
      document.getElementById('kbdi-note').textContent = 'off';
    }
  } else if (name === 'windninja') {
```

Replace the middle line `  } else if (name === 'windninja') {` region by inserting the new branch **between the kbdi branch's closing `}` and the windninja `else if`**:

```js
  } else if (name === 'wfpi') {
    wfpiEnabled = on;
    document.getElementById('wfpi-opacity-row').style.display = on ? 'flex' : 'none';
    document.getElementById('wfpi-product-row').style.display = on ? 'block' : 'none';
    document.getElementById('wfpi-day-row').style.display = on ? 'block' : 'none';
    document.getElementById('wfpi-key').style.display = on ? 'block' : 'none';
    if (on) {
      wfpiDay = 1;
      wfpiProduct = 'wfpi';
      document.querySelectorAll('#wfpi-day-row .viirs-day-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.day === '1'));
      document.querySelectorAll('#wfpi-product-row .viirs-day-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.product === 'wfpi'));
      updateWfpiLegend();
      buildWfpiLayer();
    } else {
      if (wfpiLayer) { wfpiLayer.remove(); wfpiLayer = null; }
      document.getElementById('wfpi-note').textContent = 'off';
    }
```

(So the file then reads `…'off'; } } else if (name === 'wfpi') { … } else if (name === 'windninja') {` — same chain style as every other branch.)

---

## 5. Block (d) — WMS build/update functions + handlers

**Insertion anchor** — directly after `setNaqfcTime()` and before `showHmsCard()` (~lines 6753–6762). Existing code:

```js
  if (naqfcLayer) naqfcLayer.setParams({ TIME: getNaqfcTimeStr(hours) });
}

function showHmsCard(f) {
```

Insert **between the closing `}` of `setNaqfcTime` and `function showHmsCard(f) {`**:

```js
// ── USGS Fire Danger Forecast (WFPI / WLFP / WFSP) ──────────────────
// Each forecast day is its own GeoServer workspace — day/product switching
// rebuilds the layer with a new URL + layer name. No TIME param: the WMS
// time dimension defaults to "current", so the server always returns the
// latest daily issuance. CONUS only. Public domain (USGS EROS).
const WFPI_PRODUCT_LABEL = { wfpi: 'WFPI', wlfp: 'Large Fire', wfsp: 'Spread' };

function buildWfpiLayer() {
  if (wfpiLayer) { wfpiLayer.remove(); wfpiLayer = null; }
  const name = `${wfpiProduct}-forecast-${wfpiDay}_conus_day_data`;
  wfpiLayer = L.tileLayer.wms(
    `https://dmsdata.cr.usgs.gov/geoserver/firedanger_${name}/wms`,
    { layers: name, format: 'image/png', transparent: true,
      version: '1.3.0', opacity: wfpiOpacity, zIndex: 139,
      attribution: 'USGS EROS Fire Danger Forecast (public domain)' }
  );
  // Graceful degradation: WMS has no JSON to probe — flag tile failures in the note.
  wfpiLayer.on('tileerror', () => {
    document.getElementById('wfpi-note').textContent = 'unavailable';
  });
  wfpiLayer.addTo(map);
  document.getElementById('wfpi-note').textContent =
    `${WFPI_PRODUCT_LABEL[wfpiProduct]} · Day ${wfpiDay}`;
}

function setWfpiDay(day) {
  wfpiDay = day;
  document.querySelectorAll('#wfpi-day-row .viirs-day-btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.day) === day));
  if (wfpiEnabled) buildWfpiLayer();
}

function setWfpiProduct(product) {
  wfpiProduct = product;
  document.querySelectorAll('#wfpi-product-row .viirs-day-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.product === product));
  updateWfpiLegend();
  if (wfpiEnabled) buildWfpiLayer();
}

function updateWfpiLegend() {
  ['wfpi', 'wlfp', 'wfsp'].forEach(p =>
    document.getElementById('wfpi-legend-' + p).style.display =
      p === wfpiProduct ? 'block' : 'none');
}

function setWfpiOpacity(val) {
  wfpiOpacity = val / 100;
  document.getElementById('wfpi-opacity-val').textContent = val + '%';
  if (wfpiLayer) wfpiLayer.setOpacity(wfpiOpacity);
}
```

Design decisions (match to file conventions):
- **Rebuild-on-change** (remove + recreate) rather than `setParams` — the *URL itself* changes per day/product, unlike NAQFC where only `TIME` changes. Rebuild is the same approach the naqfc branch uses on toggle-on and is foolproof.
- `zIndex: 139` — sits just **below** KBDI (140) and well below NAQFC smoke (152), so the two danger rasters and the smoke forecast stack predictably if co-enabled.
- **No `TIME` param** — capabilities declare `<Dimension name="time" default="current">`; omitting TIME always serves the newest granule (verified latest = request date). This also means no clock math and no empty-tile risk at UTC-day rollover.
- **No `className`/CSS filter** — the NAQFC layer needs `.naqfc-tiles{filter:saturate(5)…}` because its source imagery is washed out; the WFPI server style is already fully saturated (verified GetMap renders vivid green→red). Do not add a filter.
- `fetchJson` is not applicable (raster tiles, no JSON fetch); graceful degradation = the `tileerror` note above, mirroring the app's "note tells you the state" convention.

---

## 6. Block (e) — CSS

**None required.** Every class used above already exists:
`.opacity-row` (line ~97), `.usgs-key`/`.usgs-key-hdr` (~105–106), `.viirs-day-btn`/`.viirs-day-btn.active` (~347–348), `.layer-row`/`.toggle`/`.layer-note` (existing panel framework). The product/day rows reuse the exact inline-style pattern of `#naqfc-time-row` (line ~1253).

---

## 7. Verification log (all curl, 2026-07-07)

| Check | Result |
|---|---|
| `GET .../firedanger_wfpi-forecast-1_conus_day_data/wms?request=GetCapabilities&version=1.3.0` | **200**, 376,698 B XML; layer `wfpi-forecast-1_conus_day_data`; CRS EPSG:3857 + CRS:84; time dimension 6,048 dates 2008-08-01 → **2026-07-07** (request day), `default="current"` |
| GetCapabilities for `wfpi`/`wlfp`/`wfsp` × day `2` and `7` (6 combos) | all **200** |
| `wlfp-forecast-1` capabilities layer name | `wlfp-forecast-1_conus_day_data` (grammar confirmed for siblings) |
| Sample `GetMap` day-1 WFPI (EPSG:3857, CONUS bbox, 512×305, png, transparent) | **200**, `image/png`, 31,339 B, renders correct national fire-danger map |
| `GetMap` `wfsp-forecast-7` and `wlfp-forecast-4` | both **200** `image/png` |
| `GetLegendGraphic` (URL from capabilities `<LegendURL>`) for all 3 products | **200** `image/png`; all hex colors above pixel-sampled from these PNGs |
| CORS header on GetMap | `Access-Control-Allow-Origin: *` |

Canonical legend URL (works per product/day, useful for future debugging):
`https://dmsdata.cr.usgs.gov/geoserver/firedanger_wfpi-forecast-1_conus_day_data/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image%2Fpng&layer=wfpi-forecast-1_conus_day_data`

Exact server palette (pixel-sampled), for reference if the legend is ever restyled:

- **WFPI**: 0–10 `#004500` · 11–20 `#006100` · 21–30 `#0f8208` · 31–40 `#40a621` · 41–50 `#7ad445` · 51–60 `#c2ff6e` · 61–70 `#ffff19` · 71–80 `#cf703d` · 81–90 `#961900` · 91–100 `#bf0000` · 101–120 `#ff8000` · 121–140 `#ff00ff` · 141–247 `#ff0000`
- **WLFP** (%): 0–0.1 `#00008f` · 0.1–0.5 `#005ae1` · 0.5–1 `#00bdff` · 1–2 `#87ff78` · 2–3 `#ecff13` · 3–5 `#ffad00` · 5–7 `#ff4a00` · >7 `#e40000`
- **WFSP** (%): 0–0.5 `#00008f` · 0.5–1 `#005aff` · 1–2 `#00bdff` · 2–5 `#87ff78` · 5–10 `#ecff13` · 10–20 `#ffad00` · 20–30 `#ff4a00` · >30 `#e40000`
- Masks (all products): Outside US `#d2d2d2` · Snow/Ice white · Ag Land `#4f4f4f` · Barren `#408080` · Marsh `#8ba58f` · Water `#e0edff`

## 8. Post-edit checklist (per regression-watch memory)

1. Load on `:8001`, open Wildland Fire group, toggle "Fire Danger Forecast (USGS)" — raster appears over CONUS, note reads `WFPI · Day 1`.
2. Click D4 → tiles reload (different pattern), note `WFPI · Day 4`; click "Large Fire %" → legend swaps to the blue→red % bar, note `Large Fire · Day 4`.
3. Opacity slider live-updates; toggle off → layer removed, note `off`, all sub-rows hidden.
4. Verify alert-layer default + polygon click still work (standing regression check), and JS parses (no console errors).
5. Zoom to Alaska/Hawaii — expect *no tiles* (CONUS-only, by design; the note/legend already says "CONUS only").
