# Spec 01 — 7-Day Significant Fire Potential + Fresh Operational Perimeters

*Implementation spec by Fable, 2026-07-07. Target file: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` (single-file Leaflet app). Both layers go in the existing **Wildland Fire** layer group. All code below matches the file's existing conventions (`toggleLayer` chain, `fetchJson`, `esc()`, `.usgs-key` legends, `viirs-day-btn` buttons, graceful `unavailable` degradation).*

*Line numbers cited are as of 2026-07-07 — use the **quoted anchor text**, not the numbers, when pasting.*

---

## 0. Endpoint verification (live-tested 2026-07-07 with curl)

### 0.1 NIFC Predictive Services 7-Day Outlook — VERIFIED, with two critical gotchas

```
https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer/{0..6}/query
```

- **HTTP 200** on all 7 layers. Service layer list confirmed: `0=Day 1 … 6=Day 7` (so **layer index = day − 1**).
- **CORS confirmed**: `Access-Control-Allow-Origin: https://aphilp1.github.io` echoed back. No key.
- All 7 layers currently return **234 polygon features each** (national PSA polygons), `geometry.type = MultiPolygon`.
- **Actual attribute fields** (inspected, do NOT guess): `drynesscode`, `symbol`, `timestampdate`, `forecastdatapointid`, `type`, `isvalid`, `nat_code`, `gacc`.
  - There is **no "Elevated/Critical/Extreme" risk field** — the original guess was wrong. The real data model (confirmed from the layer renderer AND the official PSP viewer's own JS, which contains `drynessValueToText: 1→"Moist", 2→"Dry", 3→"Very Dry", default→"No Data"`):
    - `drynesscode` = **fuel dryness level** painted over the whole country: `1` Moist (official green `#5fb336`), `2` Dry (yellow `#ffff40`), `3` Very Dry (tan `#d9b46f`), `0` No Data (grey).
    - `type` = the actual **Significant Fire Potential overlay**, only present on risk polygons: `'CRITICAL'` (critical burn environment — wind-driven, official orange `#ff8c00`, `symbol='W'`) or `'IGNITION'` (lightning ignition risk, official red `#ff0000`, `symbol='L'`). `null` for plain dryness polygons.
    - `isvalid` = 0/1; the official renderer paints `isvalid=0` black (withdrawn/invalid) → **skip `isvalid === 0` features**.
    - `timestampdate` = epoch **ms** valid date (Day 1 today = `1783382400000` = 2026-07-07 00:00 UTC).
    - `gacc` = e.g. `"California North Ops"`, `nat_code` = PSA code e.g. `"NC03B"`.
  - Live Day-1 distribution at test time: 198 dryness polygons (codes 1/2/3), 6 × CRITICAL, 9 × IGNITION, 21 × `isvalid=0`.
- **GOTCHA 1 — payload size.** A plain `f=geojson` query returns **45.4 MB** (full-precision PSA boundaries). Adding `maxAllowableOffset=0.01&geometryPrecision=3` cuts it to **~482 KB** with no visible loss at national/regional zooms (0.01° ≈ 1 km). **The simplification params are mandatory.**
- **GOTCHA 2 — trimmed `outFields` lists 400 on some layers.** `outFields=drynesscode,type,…` intermittently returned `{"error":{"code":400,"message":"Failed to execute query."}}` on layers 1–6 while `outFields=*` worked on all 7 every time. Attributes are tiny (8 fields), geometry dominates → **use `outFields=*`**.
- Updates daily (product of the national Predictive Services 7-day forecast). Public-domain US-government data. Attribution: **NIFC Predictive Services**.

### 0.2 WFIGS Daily Fire Perimeters — VERIFIED, needs a date filter

```
https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Daily_Perimeters_Public/FeatureServer/0/query
```

- **HTTP 200**, `f=geojson` works, CORS OK (same NIFC ArcGIS org the app already uses for incidents/perimeters/VIIRS/RAWS). `maxRecordCount = 2000`.
- **GOTCHA — the layer is an archive, not a "current" view.** Total feature count is **56,230**, going back to 2023 (first record returned is a May-2023 Minnesota fire). Unfiltered it is unusable. Verified live counts with `poly_DateCurrent >= CURRENT_TIMESTAMP - N`:
  - last 1 day: **89** · last 3 days: **195** · last 7 days: **554**
  - → **filter to the last 72 h** (`CURRENT_TIMESTAMP - 3`), well under the 2000 record cap even in peak season.
- **Actual fields** (full dump inspected): `poly_IncidentName`, `poly_MapMethod`, `poly_DateCurrent` (epoch ms), `poly_PolygonDateTime`, `poly_GISAcres`, `poly_FeatureCategory` (`'Wildfire Daily Fire Perimeter'`), `poly_IRWINID`, plus the full `attr_*` IRWIN set the existing perimeter layer already consumes (`attr_IncidentTypeCategory`, `attr_PercentContained`, `attr_POOState`, `attr_POOCounty`, `attr_FireDiscoveryDateTime`, `attr_UniqueFireIdentifier`, …). **`showFirePerimCard()` works on these properties unchanged** — same schema family as `WFIGS_Interagency_Perimeters_YearToDate`.
- **End-to-end 72-h geojson query verified** (HTTP 200, 200 features, geometry `Polygon` ×124 + `MultiPolygon` ×76). Live `poly_MapMethod` distribution in the window: `Mixed Methods` 82, `Auto-generated for InFORM` 47, `IR Image Interpretation` 31, `Image Interpretation` 13, `GPS-Walked` 7, `Hand Sketch` 5, `Phone/Tablet` 5, `GPS-Driven` 4, plus `GPS-Walked/Driven`, `GPS-Flight` — this is the "how was this shape mapped" payoff of the layer.
- **GOTCHA — payload size.** The IR shapes are vertex-heavy: the plain 72-h query is **10.9 MB**. With `maxAllowableOffset=0.0001` (~10 m tolerance — ≈1 px at zoom 14, only theoretically visible at z16+) + `geometryPrecision=5` it drops to **3.7 MB** with the shapes still reading as sharp. **Both params are required** (see constant below).
- **Duplicates**: the feed carries multiple burn-period rows and occasional exact duplicate rows per incident (observed live: "Goose Lake" twice, identical timestamp). → order by `poly_DateCurrent DESC` and **keep only the newest shape per `poly_IRWINID`**.
- **Rate limiting**: the whole `services3.arcgis.com/T4QMspbfLg3qTGWY` org shares a public request-unit quota; during test bursts it returned HTTP 429 (`Retry after 60 sec`). Normal app usage is fine (the app already lives on this org), but the load function must degrade to `unavailable` on failure — `fetchJson` throwing on `!r.ok` already handles this.
- Attribution: **NIFC/WFIGS**. Public domain.

---

## 1. LAYER 1 — "7-Day Fire Potential" (`psp`)

Design: one layer group + a Day 1–7 button row (reuses the `.viirs-day-btn` CSS class, same as the NAQFC forecast-hour row). Dryness levels render as a quiet base fill (matching the official PSP viewer colors so users cross-referencing fsapps see the same map); `CRITICAL`/`IGNITION` risk polygons render hot on top. Reloads on each enable + on day click, exactly like `loadSPCFireWx`.

### 1(a) HTML — toggle row + day buttons + legend

**Anchor:** inside the Wildland Fire group, between the **Fire Weather Watch** row and the **SPC Fire Wx Outlook D1** row. Existing lines 1300–1310:

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-fwx-watch" onchange="toggleLayer('fwx-watch',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">Fire Weather Watch</span>
            <span class="layer-note" id="fwx-watch-note">off</span>
          </div>

          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-fwx-d1" onchange="toggleLayer('fwx-d1',this.checked)"><span class="toggle-slider"></span></label>
```

**Insert between those two blocks** (i.e. after the `</div>` that closes the fwx-watch layer-row, before the blank line + fwx-d1 row):

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-psp" onchange="toggleLayer('psp',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">7-Day Fire Potential</span>
            <span class="layer-note" id="psp-note">off</span>
          </div>
          <div id="psp-day-row" style="display:none;padding-left:44px;margin-top:-4px;margin-bottom:6px">
            <div class="usgs-key-hdr" style="margin-bottom:5px">Outlook Day</div>
            <div style="display:flex;gap:3px">
              <button class="viirs-day-btn active" data-day="1" onclick="setPspDay(1)">D1</button>
              <button class="viirs-day-btn" data-day="2" onclick="setPspDay(2)">D2</button>
              <button class="viirs-day-btn" data-day="3" onclick="setPspDay(3)">D3</button>
              <button class="viirs-day-btn" data-day="4" onclick="setPspDay(4)">D4</button>
              <button class="viirs-day-btn" data-day="5" onclick="setPspDay(5)">D5</button>
              <button class="viirs-day-btn" data-day="6" onclick="setPspDay(6)">D6</button>
              <button class="viirs-day-btn" data-day="7" onclick="setPspDay(7)">D7</button>
            </div>
          </div>
          <div class="usgs-key" id="psp-key" style="display:none">
            <div class="usgs-key-hdr">NIFC Predictive Services · Significant Fire Potential · Daily</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff1a00;border-radius:2px;border-color:#8f0f00"></div>Significant potential · lightning ignition</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff8c00;border-radius:2px;border-color:#a34400"></div>Significant potential · critical burn environment</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#d9a45e;border-radius:2px;border-color:#7d5a24"></div>Fuels: Very Dry</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ffd900;border-radius:2px;border-color:#8a7400"></div>Fuels: Dry</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#5fb336;border-radius:2px;border-color:#3d7a20"></div>Fuels: Moist</div>
          </div>
```

*Notes: `data-day` (not `data-days` — that attribute is scoped to the VIIRS row's `setViirsDate`, and `setPspDay` selects only inside `#psp-day-row` so there is no cross-talk). Square dots (`border-radius:2px`) = polygon layer, matching the fire-perimeters key. Dryness fills match the official PSP viewer; legend borders are darkened for contrast per app convention.*

### 1(b) JS `let` declarations

**Anchor:** the fire-layer state block, existing lines 2475–2477:

```js
let fireIncidentsEnabled = false, fireIncidentsGroup = null, fireIncidentsLoaded = false;
let firePerimEnabled = false, firePerimGroup = null, firePerimLoaded = false;
let smokeLayer = null, smokeEnabled = false, smokeOpacity = 0.80;
```

**Insert after the `firePerimEnabled` line** (covers BOTH new layers — layer 2's vars included here so there is one insertion point):

```js
let pspGroup = null, pspEnabled = false, pspDay = 1;
let dailyPerimGroup = null, dailyPerimEnabled = false, dailyPerimLoaded = false;
```

### 1(c) Constants (endpoint + style maps)

**Anchor 1:** the endpoint constants block, existing lines 2280–2282:

```js
const NIFC_HIST_PERIMS = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_AllYears/FeatureServer/0/query';
const SPC_FWX_BASE    = 'https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer';
```

**Insert after the `SPC_FWX_BASE` line** (both new endpoints together):

```js
// NIFC Predictive Services 7-day significant fire potential — layer index = day-1 (0=Day1 … 6=Day7).
const PSP_OUTLOOK_BASE = 'https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer';
// Freshest operational perimeter uploads (IR flights / GPS-walked shapes). The service
// is a running archive back to 2023 (~56k polygons) — the 72-h date filter is what makes
// it a "fresh shapes" layer. Newest shape per fire is kept at render time (feed has dupes).
const NIFC_DAILY_WHERE = "poly_DateCurrent >= CURRENT_TIMESTAMP - 3 AND attr_IncidentTypeCategory = 'WF'";
const NIFC_DAILY_PERIMS = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Daily_Perimeters_Public/FeatureServer/0/query'
  + '?where=' + encodeURIComponent(NIFC_DAILY_WHERE)
  + '&outFields=*'
  // ~10 m simplification: 10.9 MB → 3.7 MB, invisible at perimeter-viewing zooms.
  + '&returnGeometry=true&maxAllowableOffset=0.0001&geometryPrecision=5'
  + '&orderByFields=' + encodeURIComponent('poly_DateCurrent DESC')
  + '&f=geojson&resultRecordCount=2000';
```

**Anchor 2:** the fire-weather style maps, existing lines 2369–2374:

```js
const FWX_DN = {
  5:  { label:'Elevated',        c:'#a86600', f:'#E69800', fo:0.20, w:1.5 },
  8:  { label:'Critical',        c:'#cc0000', f:'#FF0000', fo:0.30, w:2.0 },
  10: { label:'Extreme',         c:'#990066', f:'#E600A9', fo:0.38, w:2.5 },
};
const FWX_DT = { label:'Dry Thunderstorm', c:'#4433aa', f:'#7766ee', fo:0.15, w:1.5 };
```

**Insert after the `FWX_DT` line:**

```js
// Predictive Services 7-day outlook — field semantics from the official PSP viewer:
// drynesscode 1/2/3 = fuel dryness base fill (official colors); type CRITICAL/IGNITION
// = the actual Significant Fire Potential risk polygons, drawn on top.
const PSP_DRYNESS = {
  1: { label:'Moist',    c:'#3d7a20', f:'#5fb336', fo:0.14, w:1.0 },
  2: { label:'Dry',      c:'#8a7400', f:'#ffd900', fo:0.22, w:1.0 },
  3: { label:'Very Dry', c:'#7d5a24', f:'#d9a45e', fo:0.28, w:1.0 },
};
const PSP_SFP = {
  CRITICAL: { label:'Critical burn environment (wind)', c:'#a34400', f:'#ff8c00', fo:0.45, w:2.2 },
  IGNITION: { label:'Lightning ignition risk',          c:'#8f0f00', f:'#ff1a00', fo:0.45, w:2.2 },
};
```

### 1(d) `L.layerGroup()` init

**Anchor:** the group-init section inside `initMap()`, existing lines 2576–2578:

```js
  fireIncidentsGroup = L.layerGroup();      // NIFC active fire incidents
  firePerimGroup     = L.layerGroup();      // NIFC fire perimeters
  fwxD1Group   = L.layerGroup();           // SPC fire weather outlook Day 1
```

**Insert after the `firePerimGroup` line** (both new groups):

```js
  dailyPerimGroup    = L.layerGroup();      // WFIGS daily ops perimeters (fresh IR/GPS shapes)
  pspGroup           = L.layerGroup();      // Predictive Services 7-day fire potential
```

### 1(e) `toggleLayer` branch

**Anchor:** the end of the `'fire-perimeters'` branch, existing lines 3592–3605:

```js
  } else if (name === 'fire-perimeters') {
    firePerimEnabled = on;
    document.getElementById('fire-perimeters-key').style.display = on ? 'block' : 'none';
    if (on) {
      // Turn off Active Fire Incidents so the fire polygon isn't hidden under the dots.
      const incCb = document.getElementById('lyr-fire-incidents');
      if (incCb && incCb.checked) { incCb.checked = false; toggleLayer('fire-incidents', false); }
      firePerimGroup.addTo(map);
      if (!firePerimLoaded) loadFirePerimeters();
    } else {
      firePerimGroup.remove();
      document.getElementById('fire-perimeters-note').textContent = 'off';
    }
  } else if (name === 'smoke') {
```

**Insert between the closing `}` of the fire-perimeters branch and `} else if (name === 'smoke') {`** — i.e. paste these two branches so the chain reads `…fire-perimeters…} else if (name === 'daily-perims') {…} else if (name === 'psp') {…} else if (name === 'smoke') {`:

```js
  } else if (name === 'daily-perims') {
    dailyPerimEnabled = on;
    document.getElementById('daily-perims-key').style.display = on ? 'block' : 'none';
    if (on) {
      // Sharper alternative to Fire Perimeters — turn off the overlapping layers so the
      // fresh shapes aren't buried under the year-to-date polygons or the incident dots.
      const perCb = document.getElementById('lyr-fire-perimeters');
      if (perCb && perCb.checked) { perCb.checked = false; toggleLayer('fire-perimeters', false); }
      const incCb = document.getElementById('lyr-fire-incidents');
      if (incCb && incCb.checked) { incCb.checked = false; toggleLayer('fire-incidents', false); }
      dailyPerimGroup.addTo(map);
      if (!dailyPerimLoaded) loadDailyPerims();
    } else {
      dailyPerimGroup.remove();
      document.getElementById('daily-perims-note').textContent = 'off';
    }
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

*(The final `} else if (name === 'smoke') {` line above is the EXISTING line — shown so the splice point is unambiguous; don't duplicate it.)*

### 1(f) Load/render functions

**Anchor:** immediately after the end of `loadSPCFireWx`, existing lines 6390–6396:

```js
    document.getElementById(noteId).textContent = count ? `${count} zones` : 'none issued';
  } catch(e) {
    document.getElementById(noteId).textContent = 'unavailable';
  }
}

// ═══════════════════════════════════════════════════════════════════
// RED FLAG / FIRE WEATHER WATCH (filtered from NWS alerts)
// ═══════════════════════════════════════════════════════════════════
```

**Insert between the closing `}` of `loadSPCFireWx` and the RED FLAG section header:**

```js
// ═══════════════════════════════════════════════════════════════════
// PREDICTIVE SERVICES 7-DAY FIRE POTENTIAL
// ═══════════════════════════════════════════════════════════════════

async function loadPspOutlook(day) {
  const note = document.getElementById('psp-note');
  note.textContent = 'loading…';
  pspGroup.clearLayers();
  try {
    // maxAllowableOffset + geometryPrecision are load-bearing: the raw PSA polygons
    // are 45 MB per day; simplified (~1 km tolerance) the same query is ~0.5 MB.
    const url = `${PSP_OUTLOOK_BASE}/${day - 1}/query`
      + '?where=' + encodeURIComponent('1=1')
      + '&outFields=*'                                      // trimmed field lists 400 on this server
      + '&maxAllowableOffset=0.01&geometryPrecision=3'
      + '&returnGeometry=true&f=geojson';
    const data = await fetchJson(url, 20000);
    if (!pspEnabled || day !== pspDay) return;              // stale — user toggled off or changed day
    pspGroup.clearLayers();
    // Skip withdrawn polygons (isvalid=0); draw dryness fills first, risk areas on top.
    const feats = (data?.features ?? []).filter(f => f.geometry && f.properties?.isvalid !== 0);
    feats.sort((a, b) => (a.properties.type ? 1 : 0) - (b.properties.type ? 1 : 0));
    let risk = 0, zones = 0, valid = null;
    for (const feat of feats) {
      const p = feat.properties;
      const sfp = PSP_SFP[p.type];
      const s = sfp || PSP_DRYNESS[p.drynesscode];
      if (!s) continue;                                     // drynesscode 0 = no data — skip
      if (!valid && p.timestampdate) { const d = new Date(p.timestampdate); if (!isNaN(d)) valid = d; }
      const where = [p.gacc, p.nat_code].filter(Boolean).map(esc).join(' · ');
      const tip = sfp
        ? `<b>Significant Fire Potential — Day ${day}</b><br>${esc(s.label)}` + (where ? `<br>${where}` : '')
        : `<b>Day ${day} Fuels: ${esc(s.label)}</b>` + (where ? `<br>${where}` : '');
      L.geoJSON(feat, {
        style: { color:s.c, fillColor:s.f, weight:s.w, opacity:0.85, fillOpacity:s.fo },
        attribution: 'NIFC Predictive Services',
      }).bindTooltip(tip, { sticky:true }).addTo(pspGroup);
      sfp ? risk++ : zones++;
    }
    const vStr = valid ? valid.toLocaleDateString('en-US', { month:'short', day:'numeric', timeZone:'UTC' }) : '';
    note.textContent = (zones + risk)
      ? `Day ${day}${vStr ? ' · ' + vStr : ''} · ${risk ? `${risk} risk area${risk > 1 ? 's' : ''}` : 'no risk areas'}`
      : 'none issued';
  } catch(e) {
    console.error('loadPspOutlook:', e);
    note.textContent = 'unavailable';
  }
}

function setPspDay(day) {
  pspDay = day;
  document.querySelectorAll('#psp-day-row .viirs-day-btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.day) === day));
  if (pspEnabled) loadPspOutlook(day);
}
```

*Conventions matched: `fetchJson` with explicit timeout, `esc()` on all feed-sourced tooltip text, sticky tooltips, `unavailable` on failure, day-button scoping copied from `setNaqfcTime` (`#psp-day-row .viirs-day-btn`), reload-on-toggle like `loadSPCFireWx` (no loaded-flag — outlook updates daily). `timeZone:'UTC'` on the valid date because `timestampdate` is a UTC midnight stamp — local rendering would show the previous day in the US.*

### 1(g) CSS

**None required.** The day buttons reuse `.viirs-day-btn` / `.viirs-day-btn.active` (existing lines 347–348), the legend reuses `.usgs-key`, `.usgs-key-hdr`, `.usgs-key-row`, `.usgs-dot` (lines 105–107).

---

## 2. LAYER 2 — "Fresh Perimeters (72 h)" (`daily-perims`)

Design: the freshest operational shape per fire from the last 72 h, colored by **shape age** using the same red→orange→yellow freshness language as the VIIRS hotspot layer (`viirsColor`). Renders in the existing `firePerimPane` (z-index 460) so polygons stay clickable under marker canvases. Click opens the existing `showFirePerimCard` — the WFIGS daily schema is the same `poly_*`/`attr_*` family, so "Perimeter mapped: IR Image Interpretation" and "Perimeter updated: <date>" rows populate for free.

### 2(a) HTML — toggle row + legend

**Anchor:** inside the Wildland Fire group, between the **Fire Perimeters** legend and the **VIIRS Fire Hotspots** row. Existing lines 1197–1207:

```html
          <div class="usgs-key" id="fire-perimeters-key" style="display:none">
            <div class="usgs-key-hdr">NIFC/WFIGS · Active Burn Boundaries · ≥100 ac</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff3300;border-radius:2px;border-color:#8f0f00"></div>Uncontained (&lt;30%)</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff8400;border-radius:2px;border-color:#a34400"></div>Partial (30–70%)</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ffc021;border-radius:2px;border-color:#7d5e00"></div>Mostly held (70–99%)</div>
          </div>

          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-smoke" onchange="toggleLayer('smoke',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">VIIRS Fire Hotspots</span>
```

**Insert between the closing `</div>` of `fire-perimeters-key` and the VIIRS layer-row:**

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-daily-perims" onchange="toggleLayer('daily-perims',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">Fresh Perimeters (72 h)</span>
            <span class="layer-note" id="daily-perims-note">off</span>
          </div>
          <div class="usgs-key" id="daily-perims-key" style="display:none">
            <div class="usgs-key-hdr">NIFC/WFIGS Daily Ops · IR flight / GPS shapes · newest per fire</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff2b00;border-radius:2px;border-color:#8f1400"></div>Mapped &lt; 12 h ago</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff7a00;border-radius:2px;border-color:#a34400"></div>12–24 h ago</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ffca28;border-radius:2px;border-color:#8a6a00"></div>24–72 h ago</div>
          </div>
```

*Freshness colors are byte-identical to `viirsColor()`'s <6h / 6–12h / 12–24h palette so the map speaks one "how fresh" language.*

### 2(b) JS `let` declarations — **already covered in 1(b)** (single insertion holds both layers' vars).

### 2(c) `L.layerGroup()` init — **already covered in 1(d)**.

### 2(d) `toggleLayer` branch — **already covered in 1(e)** (`'daily-perims'` branch).

### 2(e) Load/render function

**Anchor:** immediately after the end of `loadFirePerimeters`, existing lines 6243–6251:

```js
    firePerimLoaded = true;
    note.textContent = count ? `${count} active perimeters` : 'none active';
  } catch(e) {
    console.error('loadFirePerimeters:', e);
    note.textContent = 'unavailable';
  }
}

function showFireCard(p, lat, lon) {
```

**Insert between the closing `}` of `loadFirePerimeters` and `function showFireCard`:**

```js
// Freshest operational shape per fire — IR-flight / GPS-walked daily uploads, last 72 h.
// Colored by shape age (same freshness palette as the VIIRS hotspot layer).
function dailyPerimColor(ageH) {
  if (ageH < 12) return { stroke:'#8f1400', fill:'#ff2b00' };  // mapped < 12 h ago
  if (ageH < 24) return { stroke:'#a34400', fill:'#ff7a00' };  // 12–24 h
  return { stroke:'#8a6a00', fill:'#ffca28' };                 // 24–72 h
}

async function loadDailyPerims() {
  const note = document.getElementById('daily-perims-note');
  note.textContent = 'loading…';
  dailyPerimGroup.clearLayers();
  try {
    const data = await fetchJson(NIFC_DAILY_PERIMS, 25000);
    const seen = new Set();
    let count = 0;
    for (const feat of (data?.features ?? [])) {
      if (!feat.geometry) continue;
      const p = feat.properties;
      // Feed is ordered poly_DateCurrent DESC and carries multiple burn-period rows
      // (and occasional exact duplicates) per incident — keep only the newest shape per fire.
      const key = p.poly_IRWINID || p.attr_IrwinID || p.attr_UniqueFireIdentifier || p.poly_IncidentName;
      if (key && seen.has(key)) continue;
      if (key) seen.add(key);
      const updated = p.poly_DateCurrent || p.poly_PolygonDateTime || 0;
      const ageH = updated ? (Date.now() - updated) / 3.6e6 : 99;
      const col = dailyPerimColor(ageH);
      const name  = p.poly_IncidentName || p.attr_IncidentName || 'Fire Perimeter';
      const acresN = p.poly_GISAcres || p.attr_IncidentSize || 0;
      const acres = acresN ? Math.round(acresN).toLocaleString() : '?';
      const method = p.poly_MapMethod || 'Unknown method';
      const ageStr = updated ? (ageH < 1 ? '<1 h ago' : `${Math.round(ageH)} h ago`) : '';
      const lyr = L.geoJSON(feat, {
        pane: 'firePerimPane',
        style: { color:col.stroke, fillColor:col.fill, weight:2.2, opacity:0.95, fillOpacity:0.30 },
        attribution: 'NIFC/WFIGS Daily Perimeters',
      });
      lyr.bindTooltip(
        `<b>${esc(name)}</b><br>${acres} acres · mapped by ${esc(method)}` +
        (ageStr ? `<br>Shape updated ${ageStr}` : '') +
        (p.attr_POOState ? `<br>${esc(p.attr_POOState)}` : ''),
        { sticky: true }
      );
      lyr.on('click', e => { L.DomEvent.stopPropagation(e); showFirePerimCard(p, lyr); });
      dailyPerimGroup.addLayer(lyr);
      count++;
    }
    dailyPerimLoaded = true;
    note.textContent = count ? `${count} fresh shapes` : 'none in last 72 h';
  } catch(e) {
    console.error('loadDailyPerims:', e);
    note.textContent = 'unavailable';
  }
}
```

*Conventions matched: mirrors `loadFirePerimeters` structure exactly (note → clearLayers → fetchJson → per-feature `L.geoJSON` in `firePerimPane` → sticky tooltip → click → `showFirePerimCard` → loaded flag → count note → `unavailable` catch). `showFirePerimCard` is reused untouched — the daily schema carries the same `poly_MapMethod` / `poly_DateCurrent` / `attr_*` fields it reads.*

### 2(f) CSS

**None required** — reuses `.usgs-key*` legend classes and the existing `firePerimPane` (created at init, z-index 460; no new pane needed).

---

## 3. Post-paste verification checklist (StormWatch regression watch)

1. **JS parses** — open DevTools console on load; zero syntax errors (single-file app: one bad brace kills every layer).
2. **Alerts layer still ON by default** and alert polygon click still opens the detail card (known recurring regression).
3. `7-Day Fire Potential` ON → note shows `Day 1 · <date> · N risk areas`; D1–D7 buttons swap polygons; button highlight follows; toggling OFF mid-load doesn't strand polygons (stale-guard).
4. `Fresh Perimeters (72 h)` ON → auto-unchecks `Fire Perimeters` + `Active Fire Incidents`; polygons clickable (detail card shows "Perimeter mapped: …" and "Perimeter updated: …"); tooltip shows map method + age.
5. Kill network (DevTools offline) → both notes read `unavailable`, no console spam beyond the one logged error.
6. Layer list on the public GitHub Pages build: both layers are pure public-CORS feeds — **no `MCP_LOCAL` gating needed**.
7. Commit promptly after verification (per regression-watch rule).

## 4. Attribution

Both feeds are US-government public domain. Leaflet attribution strings are set in the layer options above (`NIFC Predictive Services`, `NIFC/WFIGS Daily Perimeters`) and will appear in the map's attribution control while the layers are on.
