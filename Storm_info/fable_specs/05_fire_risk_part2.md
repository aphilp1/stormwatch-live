# Spec 05 — Fire Risk Part 2: "Fire Risk at a Point" click-anywhere probe

*Implementation spec by Fable, 2026-07-08. Target file: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` (single-file Leaflet app).*
*Feature: user toggles **Fire Risk at a Point** in the Wildland Fire group, then clicks ANYWHERE on the map → a dark popup card reports the fire risk at that exact point.*
*Hard rule honored: **no homemade composite score**. Every line on the card is a value served by a government system (USGS EROS, NIFC Predictive Services, NWS, NIFC/WFIGS), shown verbatim with its source named.*

*All anchors below are **quoted text**, not line numbers — the file was under active edit in another session while this spec was written (2026-07-08); quoted anchors were re-read from the live file the same day and include the already-implemented spec-01 code (`psp` layer), so they are current.*

---

## 0. Endpoint verification (live-tested 2026-07-08 with curl)

### 0.1 NIFC PSP 7-day outlook — point lookup: BOTH `query` and `identify` work → use `query`

**Query (recommended).** Exact request tested:

```
https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer/0/query
  ?geometry=-116.23,43.38&geometryType=esriGeometryPoint&inSR=4326
  &spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=false&f=json
```

Observed response (HTTP 200, typed JSON attributes):

```json
{"features":[{"attributes":{"drynesscode":3,"symbol":"W","timestampdate":1783468800000,
  "forecastdatapointid":9465435,"type":"CRITICAL","isvalid":0,"nat_code":"GB03","gacc":"Great Basin"}}]}
```

**Identify (works too, not used).** Tested `MapServer/identify?geometry=-116.23,43.38&geometryType=esriGeometryPoint&sr=4326&layers=all:0&tolerance=1&mapExtent=-117,43,-115,44&imageDisplay=400,400,96&returnGeometry=false&f=json` → HTTP 200, same feature, **but all attributes come back stringified** (`"isvalid":"0"`, `"timestampdate":"7/8/2026"`) and it needs `mapExtent`/`imageDisplay` boilerplate. `query` is strictly better here — typed values, no fake extent.

**Key data-model facts confirmed at a live CRITICAL point:**
- The PSP polygons **do not stack**: a point returns ONE polygon, and a risk polygon carries **both** `type` (`CRITICAL`/`IGNITION`) **and** its `drynesscode` — so one query yields dryness *and* significant-potential in one feature. (Handle >1 feature anyway for PSA-boundary clicks.)
- Layer index = day − 1 (`0` = Day 1). `timestampdate` = epoch ms, UTC midnight of the valid day (`1783468800000` = 2026-07-08 00:00 UTC).
- **`isvalid` semantics decoded from the service's own renderer** (`MapServer/0?f=json`, uniqueValue renderer on `drynesscode,type,isvalid`):
  - Risk polygons (`type` non-null) are painted orange/red **for BOTH isvalid=0 and isvalid=1** — validation state does not hide them.
  - Dryness polygons with `isvalid=0` are painted **black** (pending/withdrawn); `isvalid=1` gets the official dryness color; `drynesscode=0` grey.
  - The official viewer bundle (`application.min.js`) contains **no isvalid logic** — it renders via the MapServer image, so the renderer above IS the official presentation.
- Live distribution at test time (12:14 UTC): layer 0 had `CRITICAL×12, IGNITION×1` — **all 13 with isvalid=0** — plus 123 dryness polygons isvalid=0 and 98 isvalid=1. Early in the UTC day most PSAs are simply not yet validated. → The probe must NOT drop risk polygons on `isvalid=0`, and should label unvalidated dryness as provisional.
- **CORS confirmed for both app origins** — `Access-Control-Allow-Origin` echoes the request Origin: tested `https://aphilp1.github.io` ✓ and `http://localhost:8001` ✓. No key.

> ⚠️ **Related observation for the spec-01 owner (not part of this spec's paste blocks):** `loadPspOutlook` currently skips `isvalid === 0` features entirely. Per the renderer above, that filter is only correct for dryness fills — on the test date it would have hidden **all 13** live CRITICAL/IGNITION areas. Suggested one-line fix in that function: skip `isvalid===0` only when `p.type` is null.

### 0.2 USGS fire-danger WMS — `GetFeatureInfo` VERIFIED for all 3 products (no ImageServer fallback needed)

The layer is `queryable="1"` in capabilities and offers `application/json` as a GetFeatureInfo format. Exact request tested (same URL grammar as the spec-02 map layer; `CRS:84` keeps lon,lat axis order under WMS 1.3.0; 101×101 px window ±0.01°, `I=50&J=50` = the exact click pixel):

```
https://dmsdata.cr.usgs.gov/geoserver/firedanger_wfpi-forecast-1_conus_day_data/wms
  ?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo
  &LAYERS=wfpi-forecast-1_conus_day_data&QUERY_LAYERS=wfpi-forecast-1_conus_day_data
  &CRS=CRS:84&BBOX=-116.24,43.37,-116.22,43.39
  &WIDTH=101&HEIGHT=101&I=50&J=50&INFO_FORMAT=application/json
```

Observed responses (all HTTP 200, `Access-Control-Allow-Origin: *`):

| Point | Product | Response `properties` |
|---|---|---|
| Boise foothills −116.23, 43.38 | wfpi | `{"PALETTE_INDEX":94}` |
| same | wlfp | `{"GRAY_INDEX":4.412400245666504}` |
| same | wfsp | `{"GRAY_INDEX":13.640336990356445}` |
| same, `wfpi-forecast-4` (grammar check) | wfpi D4 | `{"PALETTE_INDEX":95}` |
| Lake Tahoe (water) | wfpi / wlfp | `254` / `2540` |
| Central Iowa (ag land) | wfpi / wlfp | `251` / `2510` |
| Bonneville flats (barren) | wfpi | `252` |
| Mt. Rainier (snow/ice) | wfpi | `250` |
| N. Mexico (in bbox, outside US) | wfpi | `255` |
| −130, 40 (outside CONUS bbox) | wfpi | `{"features":[]}` — **empty array = no coverage** |

**Value semantics, confirmed against the server's own JSON legend** (`GetLegendGraphic&format=application/json`):
- **WFPI** `PALETTE_INDEX`: `0–247` = the WFPI value itself. Masks: `248–249` Outside US, `250` Snow/Ice, `251` Ag Land, `252` Barren, `253` Marsh, `254` Water, `255` no data. Legend bands: 0–10, 11–20, 21–30, 31–40, 41–50, 51–60, 61–70, 71–80, 81–90, 91–100, 101–120, 121–140, 141–247 (colors in the constant below = the server's own hexes, matching the spec-02 legend bar).
- **WLFP / WFSP** `GRAY_INDEX`: float **percent** (WLFP = chance a fire ≥500 ac occurs; WFSP = chance an existing large fire spreads). Masks are the same class codes **×10** (`2490` outside US … `2540` water) — anything `≥ 2480` is a mask, real probabilities are `< 1000`.

`GetFeatureInfo` works, so the "ImageServer identify" fallback mentioned in the task brief was **not needed and was not hunted for** — if USGS ever turns GetFeatureInfo off, the row degrades to `unavailable` (already handled below).

### 0.3 NIFC active incidents — point + distance query VERIFIED (nearest-fire context)

Same `services3.arcgis.com/T4QMspbfLg3qTGWY` org the app already uses (`NIFC_INCIDENTS`). Exact request tested:

```
https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/EGP_Active_Incidents_Prod_Public_View/FeatureServer/0/query
  ?geometry=-116.23,43.38&geometryType=esriGeometryPoint&inSR=4326
  &distance=100&units=esriSRUnit_StatuteMile&spatialRel=esriSpatialRelIntersects
  &where=Incident_Type_Kind LIKE '%WF%'
  &outFields=Name,DailyAcres,PercentContained,POOState&returnGeometry=true&f=geojson
```

Observed: HTTP 200, `Access-Control-Allow-Origin: *`, 8 features; sorted client-side by haversine the nearest was `RA 6 ADA CO CLAREMONT · 17.8 mi · 4,420 ac · 0% contained`. **Gotchas verified:**
- `Incident_Type_Kind` distinct values are `'FI / WF'`, `'FI / RX'`, `'FM / CX'` → filter with `LIKE '%WF%'` (mirrors the app's existing `/WF/.test(...)` in `loadFireIncidents`). A `LIKE 'WF%'` prefix match returns **0 rows**.
- The service does not sort by distance — compute haversine client-side and keep the minimum.

### 0.4 Red Flag Warning / Fire Weather Watch at the point — zero network

The app already holds every active NWS alert in the globals `alerts` + `geomCache`, loaded at startup regardless of layer toggles, and already has the point-in-polygon helpers `ptInRing`/`ptInGeom` (used by `mostSevereAlertAt`). The probe reuses them directly — no fetch.

---

## 1. Design

**Explicit probe mode, not a passive map-click listener.** Two facts about the current click architecture (studied in the live file) force this:

1. `map.on('click', …)` (in `initMap`) is a dispatcher for the four agent point-modes, falling through to `onModMapClick`. Editing it would violate "zero changes to existing lines".
2. Alert polygons, fire perimeters, and every marker call `L.DomEvent.stopPropagation(e)` in their own click handlers — a passive second `map.on('click')` would **never fire over a Red Flag polygon**, exactly where a fire-risk probe matters most.

So: an on/off toggle adds a **transparent world-covering rectangle** in a dedicated pane at z-index **620** — above `firePerimPane` (460) and every marker canvas (450), below `tooltipPane` (650) and `popupPane` (700). While the probe is ON, that rectangle catches every click first (map drag / scroll-zoom are unaffected — Leaflet drag lives on the container, not on paths). Its handler stops propagation and forwards agent point-modes with the exact 4-line block the alert-polygon handler uses, so the agents keep priority even with the probe on. Toggling OFF removes the rectangle and every layer behaves exactly as before — the existing dispatcher is never touched.

Result card = a Leaflet popup at the clicked point, dark-themed like the existing `.expt-popup` (hindcast station popup) precedent. Four independent sections, each fetched with `Promise.allSettled` so any one source failing degrades that row to `unavailable` without killing the card:

1. **USGS Fire Danger · today** — WFPI value + server band, large-fire %, spread % (Day-1 rasters, `GetFeatureInfo`).
2. **NIFC 7-Day Fire Potential · Day 1** — Significant Fire Potential (CRITICAL/IGNITION) if present, fuel dryness, GACC/PSA, valid date.
3. **NWS Fire Weather Alerts** — any Red Flag Warning / Fire Weather Watch polygon containing the point (client-side, from already-loaded alerts).
4. **Nearest Active Wildfire · NIFC** — name, distance + compass direction, acres, containment, within 100 mi.

Everything is public-CORS (verified §0) → **no `MCP_LOCAL` gating**; works identically on the GitHub Pages build.

---

## 2. Block (a) — CSS

**Anchor** — the Combined Threat panel crosshair rule. Existing lines:

```css
/* ── COMBINED THREAT PANEL ───────────────────────────────────────── */
#map-wrap.ct-mode,#map-wrap.ct-mode .leaflet-container,
#map-wrap.ct-mode .leaflet-interactive{cursor:crosshair !important}
```

**Insert immediately AFTER the `#map-wrap.ct-mode … crosshair` rule** (before the `#ct-panel{…}` line):

```css
/* ── FIRE RISK PROBE (click-anywhere point report) ───────────────── */
#map-wrap.frp-mode,#map-wrap.frp-mode .leaflet-container,
#map-wrap.frp-mode .leaflet-interactive{cursor:crosshair !important}
.frp-popup .leaflet-popup-content-wrapper{background:#0e1a2e;border:1px solid rgba(255,150,70,0.45);box-shadow:0 4px 18px rgba(0,0,0,0.7);border-radius:8px}
.frp-popup .leaflet-popup-content{margin:10px 12px;line-height:1.45;min-width:230px}
.frp-popup .leaflet-popup-tip{background:#0e1a2e}
.frp-popup .leaflet-popup-close-button{color:#7aa0c0!important;font-size:16px!important}
.frp-hdr{font-size:10px;font-weight:700;color:#ffb066;letter-spacing:1.1px;text-transform:uppercase}
.frp-coords{font-size:9px;color:#8fa8c0;margin-bottom:2px}
.frp-sec{margin-top:7px;padding-top:6px;border-top:1px solid rgba(120,160,200,0.18)}
.frp-src{font-size:8.5px;color:#7a95b0;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:2px}
.frp-val{font-size:11px;color:#e8f0f8;font-weight:600}
.frp-sub{font-size:9.5px;color:#a8bcd0}
.frp-alert{color:#ff7a55}
.frp-chip{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:-1px;border:1px solid rgba(255,255,255,0.25)}
.frp-loading{font-size:10px;color:#9fb4c8;font-style:italic;margin-top:6px}
.frp-unavail{font-size:10px;color:#8fa8c0;font-style:italic}
.frp-foot{font-size:8px;color:#7a95b0;margin-top:8px;padding-top:5px;border-top:1px solid rgba(120,160,200,0.14)}
```

*Contrast note: the card is light-text-on-dark (`#0e1a2e` panel, same as `.expt-popup`), so the app's "no light-grey on white" rule is not in play; the dimmest text used (`#7a95b0` on `#0e1a2e`) is ≈4.6:1. Nothing in this feature draws grey text on a white background.*

## 3. Block (b) — HTML: toggle row + explainer key

**Anchor** — in the Wildland Fire group, between the end of the 7-Day Fire Potential legend and the SPC row. Existing lines:

```html
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#5fb336;border-radius:2px;border-color:#3d7a20"></div>Fuels: Moist</div>
          </div>

          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-fwx-d1" onchange="toggleLayer('fwx-d1',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">SPC Fire Wx Outlook D1</span>
```

**Insert into the blank line between the `psp-key` closing `</div>` and the `lyr-fwx-d1` layer-row:**

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-fire-probe" onchange="toggleLayer('fire-probe',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">Fire Risk at a Point</span>
            <span class="layer-note" id="fire-probe-note">off</span>
          </div>
          <div class="usgs-key" id="fire-probe-key" style="display:none">
            <div class="usgs-key-hdr">Click anywhere on the map · government point data</div>
            <div style="font-size:9px;color:var(--text3);line-height:1.5">
              Reports for the clicked point: USGS fire-danger indices (WFPI · large-fire % · spread %),
              NIFC 7-day significant fire potential + fuel dryness, any Red Flag Warning or Fire Weather
              Watch, and the nearest active wildfire within 100 mi. Values are shown exactly as served —
              no blended score. While on, map clicks probe instead of opening features.
            </div>
          </div>
```

## 4. Block (c) — JS state variables

**Anchor** — the fire-layer state block. Existing lines:

```js
let firePerimEnabled = false, firePerimGroup = null, firePerimLoaded = false;
let pspGroup = null, pspEnabled = false, pspDay = 1;
let dailyPerimGroup = null, dailyPerimEnabled = false, dailyPerimLoaded = false;
let smokeLayer = null, smokeEnabled = false, smokeOpacity = 0.80;
```

**Insert after the `dailyPerimGroup` line** (before the `smokeLayer` line):

```js
let frpEnabled = false, frpRect = null, frpPopup = null, frpSeq = 0;
```

## 5. Block (d) — `toggleLayer` branch

**Anchor** — the end of the existing `'psp'` branch. Existing lines:

```js
  } else if (name === 'psp') {
    pspEnabled = on;
    document.getElementById('psp-day-row').style.display = on ? 'block' : 'none';
    document.getElementById('psp-key').style.display = on ? 'block' : 'none';
    if (on) {
      pspGroup.addTo(map);
      loadPspOutlook(pspDay);
    } else {
      pspGroup.remove();
      document.getElementById('psp-note').textContent = 'off';
    }
  } else if (name === 'smoke') {
```

**Insert a new branch between the psp branch's closing `}` and `} else if (name === 'smoke') {`** (the smoke line shown below is the EXISTING line — splice point only, don't duplicate it):

```js
  } else if (name === 'fire-probe') {
    frpEnabled = on;
    document.getElementById('fire-probe-key').style.display = on ? 'block' : 'none';
    document.getElementById('map-wrap').classList.toggle('frp-mode', on);
    if (on) {
      if (!frpRect) {
        // Transparent click-catcher over every feature layer: alert polygons and
        // markers stopPropagation in their own handlers, so a plain map-click
        // listener would never fire over them. Pane 620 sits above firePerimPane
        // (460) and the marker canvases (450), below tooltips (650) and popups (700).
        // Map drag and scroll-zoom pass through unaffected.
        if (!map.getPane('frpPane')) {
          map.createPane('frpPane');
          map.getPane('frpPane').style.zIndex = 620;
          map.getPane('frpPane').style.pointerEvents = 'auto';
        }
        frpRect = L.rectangle([[-85, -360], [85, 360]],
          { pane: 'frpPane', stroke: false, fill: true, fillOpacity: 0, interactive: true });
        frpRect.on('click', onFireProbeClick);
      }
      frpRect.addTo(map);
      document.getElementById('fire-probe-note').textContent = 'click the map';
      toast('Fire risk probe on — click anywhere on the map', '#ff8800');
    } else {
      if (frpRect) frpRect.remove();
      if (frpPopup) { map.closePopup(frpPopup); frpPopup = null; }
      document.getElementById('fire-probe-note').textContent = 'off';
    }
  } else if (name === 'smoke') {
```

## 6. Block (e) — probe functions

**Anchor** — between the end of `setPspDay` and the RED FLAG section header. Existing lines:

```js
function setPspDay(day) {
  pspDay = day;
  document.querySelectorAll('#psp-day-row .viirs-day-btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.day) === day));
  if (pspEnabled) loadPspOutlook(day);
}

// ═══════════════════════════════════════════════════════════════════
// RED FLAG / FIRE WEATHER WATCH (filtered from NWS alerts)
// ═══════════════════════════════════════════════════════════════════
```

**Insert between the closing `}` of `setPspDay` and the RED FLAG header:**

```js
// ═══════════════════════════════════════════════════════════════════
// FIRE RISK PROBE (click anywhere → authoritative point report)
// ═══════════════════════════════════════════════════════════════════
// Hard rule: every row is a value served by a government system, shown
// verbatim with its source — no blended/homemade composite score.
// USGS GetFeatureInfo semantics (verified live, spec 05 §0):
//   WFPI  → PALETTE_INDEX: 0–247 = index value, ≥248 = non-burnable mask
//   WLFP/WFSP → GRAY_INDEX: percent; ≥2480 = mask code ×10
//   empty features array = outside the CONUS raster.
const FRP_USGS_BASE = 'https://dmsdata.cr.usgs.gov/geoserver';
const FRP_MASK = { 248:'Outside US mapping', 249:'Outside US mapping', 250:'Snow / ice',
                   251:'Agricultural land', 252:'Barren', 253:'Marsh', 254:'Water', 255:'No data' };
// WFPI bands + colors exactly as the layer's own JSON legend serves them.
const FRP_WFPI_BANDS = [
  { max:10,  label:'0–10',    c:'#004500' }, { max:20,  label:'11–20',   c:'#006100' },
  { max:30,  label:'21–30',   c:'#0f8208' }, { max:40,  label:'31–40',   c:'#40a621' },
  { max:50,  label:'41–50',   c:'#7ad445' }, { max:60,  label:'51–60',   c:'#c2ff6e' },
  { max:70,  label:'61–70',   c:'#ffff19' }, { max:80,  label:'71–80',   c:'#cf703d' },
  { max:90,  label:'81–90',   c:'#961900' }, { max:100, label:'91–100',  c:'#bf0000' },
  { max:120, label:'101–120', c:'#ff8000' }, { max:140, label:'121–140', c:'#ff00ff' },
  { max:247, label:'141–247', c:'#ff0000' },
];
const FRP_PSP_DRY   = { 0:'No data', 1:'Moist', 2:'Dry', 3:'Very Dry' };
const FRP_PSP_DRY_C = { 1:'#5fb336', 2:'#ffd900', 3:'#d9a45e' };
const FRP_PSP_TYPE  = {
  CRITICAL: { label:'Critical burn environment (wind-driven)', c:'#ff8c00' },
  IGNITION: { label:'Lightning ignition risk',                 c:'#ff1a00' },
};

function frpGfiUrl(product, lat, lon) {
  // 101×101 px window ±0.01° around the point; I/J=50 = the exact click pixel.
  // CRS:84 keeps lon,lat axis order under WMS 1.3.0.
  const name = `${product}-forecast-1_conus_day_data`;
  const d = 0.01;
  return `${FRP_USGS_BASE}/firedanger_${name}/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo`
    + `&LAYERS=${name}&QUERY_LAYERS=${name}&CRS=CRS:84`
    + `&BBOX=${(lon - d).toFixed(4)},${(lat - d).toFixed(4)},${(lon + d).toFixed(4)},${(lat + d).toFixed(4)}`
    + '&WIDTH=101&HEIGHT=101&I=50&J=50&INFO_FORMAT=application%2Fjson';
}

function frpMiles(lat1, lon1, lat2, lon2) {
  const R = 3958.8, rad = x => x * Math.PI / 180;
  const h = Math.sin(rad(lat2 - lat1) / 2) ** 2
          + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function frpCompass(lat1, lon1, lat2, lon2) {  // 8-point direction from point 1 toward point 2
  const rad = x => x * Math.PI / 180;
  const y = Math.sin(rad(lon2 - lon1)) * Math.cos(rad(lat2));
  const x = Math.cos(rad(lat1)) * Math.sin(rad(lat2))
          - Math.sin(rad(lat1)) * Math.cos(rad(lat2)) * Math.cos(rad(lon2 - lon1));
  const b = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  return ['N','NE','E','SE','S','SW','W','NW'][Math.round(b / 45) % 8];
}

function frpPct(v) { return v < 0.1 ? '&lt;0.1%' : (v < 10 ? v.toFixed(1) : Math.round(v)) + '%'; }
function frpChip(c) { return `<span class="frp-chip" style="background:${c}"></span>`; }

function onFireProbeClick(e) {
  L.DomEvent.stopPropagation(e);
  // Agent point-modes keep priority — same forwarding block as the alert-polygon handler.
  if (nowcastMode    && nowcastInputMode    === 'point') { runNowcast(e.latlng.lat, e.latlng.lng); return; }
  if (fireMode       && fireInputMode       === 'point') { runFireAgent(e.latlng.lat, e.latlng.lng); return; }
  if (floodMode      && floodInputMode      === 'point') { runFloodAgent(e.latlng.lat, e.latlng.lng); return; }
  if (combinedMode   && combinedInputMode   === 'point') { runCombinedAgent(e.latlng.lat, e.latlng.lng); return; }
  probeFireRisk(e.latlng.lat, e.latlng.lng);
}

async function probeFireRisk(lat, lon) {
  const seq = ++frpSeq;
  const hdr = '<div class="frp-hdr">Fire Risk at Point</div>'
            + `<div class="frp-coords">${lat.toFixed(4)}, ${lon.toFixed(4)}</div>`;
  frpPopup = L.popup({ className: 'frp-popup', maxWidth: 330 })
    .setLatLng([lat, lon])
    .setContent(hdr + '<div class="frp-loading">Checking USGS · NIFC · NWS…</div>')
    .openOn(map);

  // PSP layer 0 = Day 1 of the 7-day significant fire potential outlook.
  const pspUrl = `${PSP_OUTLOOK_BASE}/0/query`
    + `?geometry=${lon.toFixed(5)}%2C${lat.toFixed(5)}`
    + '&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects'
    + '&outFields=*&returnGeometry=false&f=json';
  // Active wildfires within 100 statute miles (client-side nearest; the service can't sort by distance).
  const incUrl = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/EGP_Active_Incidents_Prod_Public_View/FeatureServer/0/query'
    + `?geometry=${lon.toFixed(5)}%2C${lat.toFixed(5)}`
    + '&geometryType=esriGeometryPoint&inSR=4326'
    + '&distance=100&units=esriSRUnit_StatuteMile&spatialRel=esriSpatialRelIntersects'
    + '&where=' + encodeURIComponent("Incident_Type_Kind LIKE '%WF%'")   // values are 'FI / WF' etc.
    + '&outFields=Name,DailyAcres,PercentContained,POOState'
    + '&returnGeometry=true&f=geojson&resultRecordCount=1000';

  const [wfpi, wlfp, wfsp, psp, inc] = await Promise.allSettled([
    fetchJson(frpGfiUrl('wfpi', lat, lon), 15000),
    fetchJson(frpGfiUrl('wlfp', lat, lon), 15000),
    fetchJson(frpGfiUrl('wfsp', lat, lon), 15000),
    fetchJson(pspUrl, 15000),
    fetchJson(incUrl, 15000),
  ]);
  if (seq !== frpSeq || !frpEnabled || !frpPopup) return;   // stale: newer click or toggled off

  frpPopup.setContent(hdr
    + '<div class="frp-sec"><div class="frp-src">USGS Fire Danger · today</div>' + frpUsgsRows(wfpi, wlfp, wfsp) + '</div>'
    + '<div class="frp-sec"><div class="frp-src">NIFC 7-Day Fire Potential · Day 1</div>' + frpPspRows(psp) + '</div>'
    + '<div class="frp-sec"><div class="frp-src">NWS Fire Weather Alerts</div>' + frpAlertRows(lat, lon) + '</div>'
    + '<div class="frp-sec"><div class="frp-src">Nearest Active Wildfire · NIFC</div>' + frpIncidentRow(inc, lat, lon) + '</div>'
    + '<div class="frp-foot">USGS EROS · NIFC Predictive Services · NWS · NIFC/WFIGS — values as served, no composite score</div>');
}

function frpUsgsRows(wfpi, wlfp, wfsp) {
  const px = r => (r.status === 'fulfilled' && r.value?.features?.length)
    ? r.value.features[0].properties : null;
  const w = px(wfpi);
  if (wfpi.status === 'fulfilled' && !w)
    return '<div class="frp-sub">Outside CONUS raster coverage (USGS fire-danger grids are CONUS-only)</div>';
  const rows = [];
  if (w && w.PALETTE_INDEX != null) {
    const v = w.PALETTE_INDEX;
    if (v <= 247) {
      const band = FRP_WFPI_BANDS.find(b => v <= b.max);
      rows.push(`<div class="frp-val">${frpChip(band.c)}Fire Potential Index (WFPI): ${v}`
              + ` <span class="frp-sub">/ 247 · band ${band.label}</span></div>`);
    } else {
      rows.push(`<div class="frp-val">Not rated: ${esc(FRP_MASK[v] || 'No data')}</div>`
              + '<div class="frp-sub">non-burnable or unmapped cell in the USGS grid</div>');
    }
  } else {
    rows.push('<div class="frp-unavail">WFPI unavailable</div>');
  }
  const l = px(wlfp);
  if (l && l.GRAY_INDEX != null && l.GRAY_INDEX < 2480)
    rows.push(`<div class="frp-sub">Chance a large fire (≥500 ac) occurs: <b>${frpPct(l.GRAY_INDEX)}</b></div>`);
  const s = px(wfsp);
  if (s && s.GRAY_INDEX != null && s.GRAY_INDEX < 2480)
    rows.push(`<div class="frp-sub">Chance an existing fire spreads: <b>${frpPct(s.GRAY_INDEX)}</b></div>`);
  return rows.join('');
}

function frpPspRows(psp) {
  if (psp.status === 'rejected') return '<div class="frp-unavail">unavailable</div>';
  const feats = psp.value?.features ?? [];
  if (!feats.length) return '<div class="frp-sub">No outlook polygon at this point</div>';
  // Risk polygons carry BOTH the significant-potential type and the dryness code (verified live).
  // The service renderer paints risk areas regardless of isvalid — do NOT drop them on isvalid=0.
  const risk = feats.find(f => FRP_PSP_TYPE[f.attributes?.type]);
  const a = (risk || feats[0]).attributes || {};
  const rows = [];
  if (risk) {
    const t = FRP_PSP_TYPE[risk.attributes.type];
    rows.push(`<div class="frp-val frp-alert">${frpChip(t.c)}Significant Fire Potential: ${esc(t.label)}</div>`);
  }
  const dc = a.drynesscode;
  rows.push(`<div class="frp-sub">${FRP_PSP_DRY_C[dc] ? frpChip(FRP_PSP_DRY_C[dc]) : ''}`
          + `Fuel dryness: <b>${esc(FRP_PSP_DRY[dc] ?? 'No data')}</b>`
          + (!risk && a.isvalid === 0 ? ' · not yet validated today (provisional)' : '')
          + '</div>');
  const where = [a.gacc, a.nat_code].filter(Boolean).map(esc).join(' · ');
  const vd = a.timestampdate ? new Date(a.timestampdate) : null;
  const vStr = vd && !isNaN(vd)
    ? ' · valid ' + vd.toLocaleDateString('en-US', { month:'short', day:'numeric', timeZone:'UTC' }) : '';
  if (where || vStr) rows.push(`<div class="frp-sub">${where}${vStr}</div>`);
  return rows.join('');
}

function frpAlertRows(lat, lon) {
  const ll = { lat: lat, lng: lon };
  const hits = alerts.filter(a =>
    (a.properties.event === 'Red Flag Warning' || a.properties.event === 'Fire Weather Watch') &&
    ptInGeom(ll, geomCache[a.id]));
  if (!hits.length) return '<div class="frp-sub">No Red Flag Warning or Fire Weather Watch here</div>';
  return hits.map(a => {
    const p = a.properties;
    const d = p.ends || p.expires ? new Date(p.ends || p.expires) : null;
    return `<div class="frp-val frp-alert">${esc(p.event)}</div>`
         + (d && !isNaN(d) ? `<div class="frp-sub">until ${fmtDT(d)}</div>` : '');
  }).join('');
}

function frpIncidentRow(inc, lat, lon) {
  if (inc.status === 'rejected') return '<div class="frp-unavail">unavailable</div>';
  const feats = (inc.value?.features ?? []).filter(f => f.geometry?.coordinates);
  if (!feats.length) return '<div class="frp-sub">No active wildfires within 100 mi</div>';
  let best = null, bestMi = Infinity;
  for (const f of feats) {
    const mi = frpMiles(lat, lon, f.geometry.coordinates[1], f.geometry.coordinates[0]);
    if (mi < bestMi) { bestMi = mi; best = f; }
  }
  const p = best.properties;
  const acres = p.DailyAcres ? Math.round(p.DailyAcres).toLocaleString() + ' ac' : 'size n/a';
  const pct = p.PercentContained != null ? ` · ${p.PercentContained}% contained` : '';
  return `<div class="frp-val">${esc(p.Name || 'Unnamed fire')}</div>`
       + `<div class="frp-sub">${bestMi < 1 ? '&lt;1' : Math.round(bestMi)} mi `
       + `${frpCompass(lat, lon, best.geometry.coordinates[1], best.geometry.coordinates[0])}`
       + ` · ${acres}${pct}${p.POOState ? ' · ' + esc(p.POOState) : ''}</div>`;
}
```

*Conventions matched: `fetchJson` with explicit timeouts; `esc()` on every feed-sourced string (event names, GACC/PSA, incident names, states); `toast()` on mode entry; per-row `unavailable` degradation; stale-guard via sequence counter (same idea as `loadPspOutlook`'s `day !== pspDay` guard); the agent-forwarding block is byte-compatible with the one in `addAlertPolygon`; `PSP_OUTLOOK_BASE` already exists in the constants block (added with the 7-Day Fire Potential layer) — the probe reuses it, no new PSP constant needed. `timeZone:'UTC'` on the valid date for the same UTC-midnight reason documented in `loadPspOutlook`.*

---

## 7. Post-paste verification checklist (StormWatch regression watch)

1. **JS parses** — DevTools console clean on load (single-file app: one bad brace kills every layer).
2. **Alerts layer still ON by default** and alert-polygon click still opens the detail card **with the probe OFF** (standing regression check).
3. Toggle **Fire Risk at a Point** ON → cursor becomes crosshair, toast appears, note reads `click the map`.
4. Click open country (e.g. SW Idaho) → popup shows: WFPI value + band chip, large-fire % and spread % lines, NIFC Day-1 dryness (+ Significant Fire Potential row if inside a CRITICAL/IGNITION area), NWS line, nearest-fire line with distance/direction/acres.
5. Turn on **Red Flag Warning** layer, probe a point INSIDE a warning polygon → the **probe card** opens (not the alert card) and its NWS row names the Red Flag Warning with an "until" time. Toggle probe OFF → clicking the same polygon opens the alert detail card again.
6. Click the ocean (~40 N, 130 W) → USGS row reads "Outside CONUS raster coverage", PSP row "No outlook polygon at this point", incidents row "No active wildfires within 100 mi" — card still renders.
7. Click Lake Tahoe → USGS row reads "Not rated: Water"; probability lines absent.
8. Rapid double-click → only one card populated (stale-guard); toggling probe off mid-fetch strands nothing.
9. With probe ON, enable the Fire Weather agent in point mode and click → the **agent** runs (probe defers); close agent, click again → probe card returns.
10. DevTools offline → every row degrades to `unavailable` / its empty-state text; no console spam beyond fetch errors.
11. Zoom/drag with probe ON → map pans and scroll-zooms normally (capture rectangle passes drag through).
12. Public-build check: all four sources verified public-CORS (`aphilp1.github.io` and `localhost:8001` both accepted by fsapps; USGS and services3 send `*`) — **no `MCP_LOCAL` gating**; feature must work identically on GitHub Pages.
13. Commit promptly after verification (per regression-watch rule).

## 8. Honest limitations

- **Day 1 only.** The card reports today's USGS rasters (`*-forecast-1`) and PSP outlook Day 1 (`MapServer/0`). Both grammars are day-parameterized (verified `wfpi-forecast-4` and PSP layers 0–6 live), so a Day selector is a straightforward extension — omitted to keep the card small.
- **USGS rows are CONUS-only** (grid bbox lon −128.5…−65.4, lat 22.5…51.8); Alaska/Hawaii clicks get the honest "outside coverage" line. The **NIFC PSP row does cover Alaska** (live AK04 IGNITION polygon observed), and the NWS + incidents rows are nationwide.
- **Probe mode blocks feature interaction while ON** — the capture rectangle sits above markers/polygons, so hover tooltips and feature cards don't fire until the probe is toggled off. This is deliberate (it is what makes "click anywhere" true) and is stated in the key text.
- **Double-click** fires two probe clicks before the double-click zoom; the sequence guard makes the second win — cosmetic only.
- **`isvalid` handling is renderer-derived, not documented by NIFC**: risk polygons are reported regardless of `isvalid` (matches the service's own renderer); unvalidated dryness is labeled "provisional". Early in the UTC day most PSAs are unvalidated (observed 12:14 UTC: 123/234 dryness + all 13 risk polygons `isvalid=0`).
- **Nearest-fire distance is point-to-incident-origin**, not to the perimeter edge — a 100,000-ac fire's edge can be much closer than its origin point. The perimeter datasets could refine this later; the card names its meaning ("Nearest Active Wildfire") rather than implying edge distance.
- **No probability interpretation is added.** WFPI is shown as value + the server's own band; WLFP/WFSP are self-describing percentages. Wording like "high/extreme danger" was deliberately NOT added — the sources don't say it at point level, so neither does the card.
- The `identify` endpoint and a hypothetical USGS ImageServer fallback are documented (§0) but unused — `query` and `GetFeatureInfo` are the verified, cleaner paths.
