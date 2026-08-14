# Spec 03 — InciWeb links · IMSR national sitrep layer · public AirNow PM2.5

*Written by Fable, 2026-07-07. All three endpoints curl-verified live this session, including CORS with `Origin: https://aphilp1.github.io`. Target file: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` (single-file Leaflet app). Line numbers are as of today's file and will drift — **match on the quoted anchor text, not the numbers.***

Companion doc: `FIRE_DATA_CATALOG.md` items #4 (InciWeb) and #6 (IMSR + AirNow).

---

## Endpoint verification results (live, 2026-07-07)

| Endpoint | Status | CORS | Key | Notes |
|---|---|---|---|---|
| `GET https://inciweb.wildfire.gov/incidents/rss.xml` | 200, 95 KB | `Access-Control-Allow-Origin: *` ✅ | none | RSS 2.0, ~50 items, Drupal 10, `no-cache` headers |
| `GET https://services3.arcgis.com/T4QMspbfLg3qTGWY/.../IMSR_Incident_Locations_Most_Recent_View/FeatureServer/0/query?...&f=geojson` | 200 | `Access-Control-Allow-Origin: *` ✅ | none | **38 records** today; `cacheMaxAge: 300`; geometry wkid 4269 |
| `POST https://airnowgovapi.com/reportingarea/get_state` (body `state_code=CA`) | 200, 314 KB | `Access-Control-Allow-Origin: *` ✅ (with `Vary: Origin`) | none | **UNDOCUMENTED** — plain JSON array; unknown state returns `200 []` (fails soft) |

### InciWeb RSS item shape (real sample)

```xml
<item>
  <title>COPSF Willow Fire</title>
  <link>http://inciweb.wildfire.gov/incident-information/copsf-willow-fire</link>
  <description>Last updated: 2026-07-07
--- 
The type of incident is Wildfire and involves the following unit(s) Pike and San Isabel National Forest. 
--- 
State: Colorado
--- 
Coordinates: Latitude: 39° 14 00  Longitude: 106° 26 25 
--- 
NOTE: All fire perimeters and points are approximations. 
--- 
Incident Overview: The Willow Fire, located approximately 6 miles west of Leadville, CO, started on June 28, 2026. ... please follow Lake County Office of Emergency Management. ...&amp;nbsp;</description>
  <pubDate>Mon, 29 Jun 2026 03:22:44 EDT</pubDate>
  <dc:creator>dsanchez</dc:creator>
  <guid isPermaLink="false">328323</guid>
</item>
```

Parsing facts (all observed live):
- `<title>` = **unit code prefix + fire name**, e.g. `COPSF Willow Fire`, `NVWID Dutch Flat Fire`, `NENMS Log Road Fire`. The unit code is a single leading ALL-CAPS token (4–7 chars) — strip it for matching.
- `<description>` is plain text with `---` separators. Reliable extractable fields: `Last updated: YYYY-MM-DD` (sometimes empty), `State: <full state name>`, and `Incident Overview: <narrative>` (this is where evacuation/closure language lives, e.g. the Willow item above). Contains literal `&amp;nbsp;` entities — clean them.
- `<link>` is `http://` — upgrade to `https://` before rendering.
- NIFC EGP names for the same fires are bare (`Shell`, `PACE CT (54)`), `POOState` is `US-FL` style; perimeter fields are `poly_IncidentName` / `attr_POOState`. So the join is *normalized-name (+ state when possible)*.

### IMSR real field names (confirmed via `outFields=*` + layer metadata)

```json
{"OBJECTID":2615, "latitude":38.019, "longitude":-105.071,
 "initial_imsr_date":1782691200000,            // epoch ms
 "fire_name":"Aspen Acres", "incident_id":"CO-CUX-001160",
 "x100pct":"", "imt_type":"C", "gacc":"RMCC", "new_to_imsr":"",
 "post_date_isoformat":20260707,               // integer YYYYMMDD
 "IrwinID":"1cdf5e5a-...", "IrwinFireDiscoveryDateTime":"6/29/2026 12:04:46 PM",
 "IsLatest":"x", "Occurrence":"LAST", "size":91982,
 "UniqueFireIdentifier":"2026-COCUX-001160"}
```

- `imt_type` coded-value domain (from layer metadata): `"1"` = Type 1 IMT, `"2"` = Type 2 IMT, `"C"` = Complex IMT, `"N"` = NIMO. Empty string = no team. Today's distribution: 29 blank, 9 `C`.
- `size` = acres (integer). `new_to_imsr` = flag string (empty when not new). `incident_id` starts with the 2-letter state (`CO-CUX-…`) — free state abbreviation for the InciWeb join.
- The view is already "most recent": 38 rows total, no `IsLatest` filter needed. Use geometry for position (the `latitude`/`longitude` attributes match here, but geometry is authoritative; NAD83/wkid 4269 ≈ WGS84 for display).
- ⚠️ `resultRecordCount` small values return `"exceededTransferLimit":true` — harmless; with 500 you get all 38.

### AirNow `get_state` record shape (real sample)

```json
[{"validDate":"07/07/26","timezone":"PDT","time":"12:00","dataType":"O",
  "reportingArea":"San Lorenzo Valley","latitude":37.0881,"longitude":-122.0844,
  "parameter":"PM2.5","aqi":16,"category":"Good"},
 {"validDate":"07/06/26","timezone":"PDT","time":"","dataType":"F",
  "reportingArea":"San Lorenzo Valley", ... "parameter":"OZONE","category":"Good"}]
```

- Mixed array of **observations (`dataType:"O"`) and forecasts (`dataType:"F"`)** across several `validDate`s and parameters (`PM2.5`, `OZONE`, `PM10`, `CO`). Filter to `dataType==='O' && parameter==='PM2.5'`.
- ⚠️ **`aqi` is ABSENT on some records** (seen live on forecast rows) — must null-check.
- `category` strings match the app's existing `AIRNOW_CAT` keys (`Good`, `Moderate`, …). Unknown → grey fallback.
- Bonus, also verified live: `POST https://airnowgovapi.com/reportingarea/get` with body `latitude=39.76&longitude=-121.62&stateCode=CA&maxDistance=50` returns richer records (`stateCode`, `reportingAgency`, `isPrimary`, `issueDate`). Not used below (per-state is a better fit for a layer) but it's the fallback if `get_state` ever disappears.
- **Risk**: this API backs the airnow.gov site itself but is unofficial. It can change shape or drop CORS without notice. Everything below validates shape hard and degrades to the note text `unavailable` — never a broken layer.

---

## PASTE BLOCK 0 — shared constants (used by all three features)

**Anchor** — the fire constants block. Find (currently ~line 2280):

```js
const NIFC_HIST_PERIMS = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_AllYears/FeatureServer/0/query';
const SPC_FWX_BASE    = 'https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer';
```

Insert **between those two lines**:

```js
// InciWeb official incident pages — RSS 2.0, CORS *, no key (verified 2026-07-07)
const INCIWEB_RSS = 'https://inciweb.wildfire.gov/incidents/rss.xml';
// NICC IMSR national sitrep — most-recent view, ~40 large incidents, CORS *, no key
const IMSR_URL = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/IMSR_Incident_Locations_Most_Recent_View/FeatureServer/0/query'
  + '?where=1%3D1'
  + '&outFields=' + encodeURIComponent('fire_name,incident_id,size,imt_type,gacc,new_to_imsr,post_date_isoformat,IrwinFireDiscoveryDateTime,UniqueFireIdentifier')
  + '&returnGeometry=true&orderByFields=' + encodeURIComponent('size DESC')
  + '&f=geojson&resultRecordCount=500';
// AirNow reporting-area feed — UNDOCUMENTED endpoint behind airnow.gov (CORS *).
// May change without notice: every caller validates the shape and fails soft.
const AIRNOW_STATE_URL = 'https://airnowgovapi.com/reportingarea/get_state';

// IMSR incident-management-team styling (imt_type coded values from layer metadata)
const IMSR_IMT = {
  '1': { label:'Type 1 IMT',        letter:'1', fill:'#e02020', stroke:'#8f0f00' },
  '2': { label:'Type 2 IMT',        letter:'2', fill:'#ff8400', stroke:'#a34400' },
  'C': { label:'Complex IMT',       letter:'C', fill:'#8f3f97', stroke:'#5c1b66' },
  'N': { label:'NIMO',              letter:'N', fill:'#7e0023', stroke:'#550011' },
  '':  { label:'No team assigned',  letter:'',  fill:'#b08050', stroke:'#5f4a34' },
};
```

**State variables anchor** — find (currently ~line 2514):

```js
let airnowGroup = null, airnowEnabled = false, airnowLoaded = false;
```

Insert **directly after** it:

```js
let imsrGroup = null, imsrEnabled = false, imsrLoaded = false;
let inciwebIndex = null, inciwebFetchedAt = 0, _inciwebPromise = null, _detCardSeq = 0;
let _airnowMoveTimer = null, _airnowLoadSeq = 0;
const _airnowStateCache = new Map();   // stateCode → { at: ms, recs: [...] }
```

**initMap anchor** — find (currently ~line 2585):

```js
  airnowGroup   = L.layerGroup();          // EPA AirNow PM2.5 stations
```

Insert **directly after** it:

```js
  imsrGroup     = L.layerGroup();          // NICC IMSR national sitrep incidents
```

**bringToFront list anchor** — find the long array (currently ~line 4074) and add `imsrGroup` after `fireIncidentsGroup`:

```js
  [hmsGroup,fwxD2Group,fwxD1Group,spc2Group,spc1Group,firePerimGroup,metarGroup,mtGroup,rawsGroup,usgsFlowGroup,usgsGroup,inundationGroup,fimGroup,fireIncidentsGroup,imsrGroup,airnowGroup,redFlagGroup,fwxWatchGroup,torWarnGroup,torWatchGroup,svrTstmGroup,flfWarnGroup,winStmGroup,blizzGroup,redFlagAlrtGroup,otherAlvGroup,alertGroup].forEach(g=>{ if(map.hasLayer(g)) g.bringToFront(); });
```

(Only change: `fireIncidentsGroup,imsrGroup,airnowGroup` — one identifier inserted.)

---

# FEATURE 1 — InciWeb links + latest narrative in the fire cards

One RSS fetch (cached 15 min, deduped across concurrent callers) enriches **both** existing fire cards and powers an optional "Fire Incident News" list. Zero changes to how the cards render today — the InciWeb block lands asynchronously in the already-existing `#det-custom` div (which `ensureDetStandard()` clears on every card open, so there is never stale content).

## 1.1 Core functions

**Anchor** — insert the whole block **between `showFirePerimCard` and `setSmokeOpacity`**. Find (currently ~line 6345):

```js
  document.getElementById('detail').style.display = 'flex';
}

function setSmokeOpacity(val) {
```

Insert between the closing `}` and `function setSmokeOpacity(val) {`:

```js
// ═══════════════════════════════════════════════════════════════════
// INCIWEB RSS — official incident pages, joined to fire cards by name
// Feed: inciweb.wildfire.gov/incidents/rss.xml (CORS *, no key).
// Titles look like "COPSF Willow Fire" — leading token is the unit code.
// ═══════════════════════════════════════════════════════════════════
const INCIWEB_TTL = 15 * 60 * 1000;

function inciwebNorm(name) {
  return String(name || '').toLowerCase()
    .replace(/\(.*?\)/g, ' ')            // "PACE CT (54)" → "pace ct"
    .replace(/\b(fire|complex)\b/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

async function getInciweb() {
  if (inciwebIndex && Date.now() - inciwebFetchedAt < INCIWEB_TTL) return inciwebIndex;
  if (_inciwebPromise) return _inciwebPromise;        // de-dupe concurrent callers
  _inciwebPromise = (async () => {
    const xml = await fetchText(INCIWEB_RSS, 15000);
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.querySelector('parsererror')) throw new Error('InciWeb RSS parse error');
    const items = [];
    for (const it of doc.querySelectorAll('item')) {
      const title = it.querySelector('title')?.textContent?.trim() || '';
      const link  = it.querySelector('link')?.textContent?.trim() || '';
      const desc  = it.querySelector('description')?.textContent || '';
      if (!title || !link) continue;
      const state    = (desc.match(/State:\s*([A-Za-z .]+?)\s*(?:---|$)/) || [])[1]?.trim() || '';
      const updated  = (desc.match(/Last updated:\s*(\d{4}-\d{2}-\d{2})/) || [])[1] || '';
      const overview = (desc.match(/Incident Overview:\s*([\s\S]+)$/) || [])[1]
                         ?.replace(/&(amp;)?nbsp;/g, ' ').replace(/\s+/g, ' ').trim() || '';
      items.push({
        title,
        name: title.replace(/^[A-Z0-9]{4,7}\s+/, ''),     // drop unit-code prefix
        link: link.replace(/^http:/, 'https:'),
        state, updated, overview,
      });
    }
    // Two lookups: exact "name|state", and name-only (null on collision = ambiguous).
    const byNameState = new Map(), byName = new Map();
    for (const rec of items) {
      const n = inciwebNorm(rec.name);
      if (!n) continue;
      byNameState.set(n + '|' + rec.state.toLowerCase(), rec);
      byName.set(n, byName.has(n) ? null : rec);
    }
    inciwebIndex = { items, byNameState, byName };
    inciwebFetchedAt = Date.now();
    return inciwebIndex;
  })().finally(() => { _inciwebPromise = null; });
  return _inciwebPromise;
}

// stateAbbr accepts "US-CO", "CO", or null (NIFC POOState is "US-CO" style).
function inciwebMatch(idx, fireName, stateAbbr) {
  const n = inciwebNorm(fireName);
  if (!n || !idx) return null;
  const ab = String(stateAbbr || '').replace(/^US-/, '').toUpperCase();
  const full = (REGION_LABELS[ab] || '').toLowerCase();
  return (full && idx.byNameState.get(n + '|' + full)) || idx.byName.get(n) || null;
}

// Async card enrichment — fills #det-custom once the RSS lookup lands.
// Guards: sequence counter AND the card title still on screen (so a slow fetch
// can never scribble on a different card the user opened meanwhile).
async function enrichCardWithInciweb(fireName, stateAbbr, cardTitle) {
  const seq = ++_detCardSeq;
  let rec = null;
  try { rec = inciwebMatch(await getInciweb(), fireName, stateAbbr); }
  catch (e) { console.warn('InciWeb unavailable:', e); return; }   // graceful: card simply has no link
  if (!rec || seq !== _detCardSeq) return;
  if (document.getElementById('det-event')?.textContent !== cardTitle) return;
  const custom = document.getElementById('det-custom');
  if (!custom) return;
  const ov = rec.overview.length > 300 ? rec.overview.slice(0, 300) + '…' : rec.overview;
  custom.style.display = 'block';
  custom.innerHTML =
    `<div style="border-top:1px solid #eee;margin-top:10px;padding-top:9px">
       <a href="${esc(rec.link)}" target="_blank" rel="noopener"
          style="font-size:12px;font-weight:700;color:#a33c00;text-decoration:none">Official InciWeb page →</a>
       ${rec.updated ? `<span style="font-size:10px;color:#444;margin-left:8px">updated ${esc(rec.updated)}</span>` : ''}
       ${ov ? `<div style="font-size:11px;color:#333;line-height:1.55;margin-top:6px">${esc(ov)}</div>` : ''}
       <div style="margin-top:7px;font-size:10px;color:#565d6c">Source: InciWeb · inciweb.wildfire.gov</div>
     </div>`;
}
```

Notes: `fetchText` (line ~2661) and `REGION_LABELS` (line ~2400, `AL:'Alabama',…`) already exist — no new helpers needed. Colors follow the contrast rule: `#333`/`#444` body text on the white card, no light greys.

## 1.2 Hook into `showFireCard` (incident dots)

**Anchor** — the end of `showFireCard`. Current code (~line 6294):

```js
  document.getElementById('det-zoom').textContent = '⊕ Zoom to Fire';
  document.getElementById('det-zoom').onclick = () => map.setView([lat, lon], 10);
  document.getElementById('detail').style.display = 'flex';
}
```

Becomes (one line added before the display line):

```js
  document.getElementById('det-zoom').textContent = '⊕ Zoom to Fire';
  document.getElementById('det-zoom').onclick = () => map.setView([lat, lon], 10);
  enrichCardWithInciweb(name, state, name);   // async — official InciWeb link + latest narrative
  document.getElementById('detail').style.display = 'flex';
}
```

(`name` and `state` are already in scope — lines 3–6 of the function: `const name = p.Name || p.IncidentName || …` and `const state = p.POOState || p.State || p.state || null;`. Third arg matches the `det-event` title the function sets.)

## 1.3 Hook into `showFirePerimCard` (perimeter polygons)

**Anchor** — the end of `showFirePerimCard`. Current code (~line 6341):

```js
  document.getElementById('det-zoom').textContent = '⊕ Zoom to Perimeter';
  document.getElementById('det-zoom').onclick = () => {
    try { map.fitBounds(lyr.getBounds(), { padding:[50,50], maxZoom:12 }); } catch(_){}
  };
  document.getElementById('detail').style.display = 'flex';
}
```

Becomes:

```js
  document.getElementById('det-zoom').textContent = '⊕ Zoom to Perimeter';
  document.getElementById('det-zoom').onclick = () => {
    try { map.fitBounds(lyr.getBounds(), { padding:[50,50], maxZoom:12 }); } catch(_){}
  };
  enrichCardWithInciweb(p.poly_IncidentName || p.attr_IncidentName, p.attr_POOState,
                        p.poly_IncidentName || 'Fire Perimeter');   // official InciWeb link
  document.getElementById('detail').style.display = 'flex';
}
```

(Third arg must equal what the function put in `det-event`: `p.poly_IncidentName || 'Fire Perimeter'`.)

## 1.4 Optional — standalone "Fire Incident News" list

Reuses the same cached feed and the detail panel; no new panel infrastructure.

**HTML anchor** — end of the Wildland Fire group, after the WindNinja row (currently ~line 1335):

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-windninja" onchange="toggleLayer('windninja',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">WindNinja Terrain Wind</span>
            <span class="layer-note" id="windninja-note">off</span>
          </div>
```

Insert **directly after** that `</div>`:

```html
          <div class="layer-row" style="padding-left:44px">
            <button class="viirs-day-btn" onclick="showFireNews()">📰 Fire Incident News</button>
          </div>
```

**JS** — paste directly after `enrichCardWithInciweb` (end of block 1.1):

```js
// Standalone InciWeb news list in the detail panel (same cached feed).
async function showFireNews() {
  ['det-area-row','det-dates-row','det-hl-wrap','det-instr-wrap','det-zoom','det-desc-row']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
  document.getElementById('det-event').textContent = 'Fire Incident News';
  document.getElementById('det-event').style.color = '#a33c00';
  document.getElementById('det-chips').innerHTML = '';
  document.getElementById('det-sev-desc').textContent = 'InciWeb · latest official incident updates';
  const custom = document.getElementById('det-custom');
  custom.style.display = 'block';
  custom.innerHTML = '<div style="padding:12px 0;font-size:11px;color:#444">Loading InciWeb feed…</div>';
  document.getElementById('detail').style.display = 'flex';
  ++_detCardSeq;                       // cancel any in-flight card enrichment
  try {
    const idx = await getInciweb();
    const items = idx.items.slice()
      .sort((a, b) => (b.updated || '').localeCompare(a.updated || ''))
      .slice(0, 20);
    custom.innerHTML = items.map(r =>
      `<div style="border-bottom:1px solid #eee;padding:8px 0">
         <a href="${esc(r.link)}" target="_blank" rel="noopener"
            style="font-size:12px;font-weight:700;color:#a33c00;text-decoration:none">${esc(r.name)}</a>
         <span style="font-size:10px;color:#444;margin-left:6px">${esc(r.state)}${r.updated ? ' · updated ' + esc(r.updated) : ''}</span>
         ${r.overview ? `<div style="font-size:11px;color:#333;line-height:1.5;margin-top:3px">${esc(r.overview.slice(0, 180))}${r.overview.length > 180 ? '…' : ''}</div>` : ''}
       </div>`).join('')
      + '<div style="margin-top:8px;font-size:10px;color:#565d6c">Source: InciWeb · inciweb.wildfire.gov</div>';
  } catch (e) {
    custom.innerHTML = '<div style="padding:12px 0;font-size:11px;color:#444">InciWeb feed unavailable right now — try again in a minute.</div>';
  }
}
```

**Failure modes handled**: feed down / parse error → card shows nothing extra (enrichment) or a plain "unavailable" line (news list); ambiguous fire names (two fires called "Willow") match only when the state also agrees, otherwise no link rather than a wrong link; `http:` links upgraded; `&nbsp;` entities cleaned; long narratives truncated.

---

# FEATURE 2 — IMSR "National Fire Situation" point layer

Mirrors the VIIRS/`loadFireIncidents` canvas-marker pattern exactly: `L.canvas` renderer in `markerLayerPane` (z 450 — stays **below** `firePerimPane` at z 460, so perimeter polygons remain clickable when both layers are on; same reasoning as the existing pane comment in `initMap`). 38 points today, one fetch, no bbox handling needed. Points are **sized by acreage** and **colored by IMT type**, with a letter label (1/2/C/N) centered on team-managed incidents. Click → detail card, which also gets the Feature-1 InciWeb link (the state comes free from `incident_id`, e.g. `CO-CUX-001160`).

## 2.1 HTML toggle + legend

**Anchor** — between the Fire Perimeters key and the VIIRS row. Find (currently ~lines 1197–1205):

```html
          <div class="usgs-key" id="fire-perimeters-key" style="display:none">
            <div class="usgs-key-hdr">NIFC/WFIGS · Active Burn Boundaries · ≥100 ac</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff3300;border-radius:2px;border-color:#8f0f00"></div>Uncontained (&lt;30%)</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff8400;border-radius:2px;border-color:#a34400"></div>Partial (30–70%)</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ffc021;border-radius:2px;border-color:#7d5e00"></div>Mostly held (70–99%)</div>
          </div>

          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-smoke" onchange="toggleLayer('smoke',this.checked)"><span class="toggle-slider"></span></label>
```

Insert **between the closing `</div>` of the perimeters key and the VIIRS `layer-row`**:

```html
          <div class="layer-row">
            <label class="toggle"><input type="checkbox" id="lyr-imsr" onchange="toggleLayer('imsr',this.checked)"><span class="toggle-slider"></span></label>
            <span class="layer-label">National Sitrep (IMSR)</span>
            <span class="layer-note" id="imsr-note">off</span>
          </div>
          <div class="usgs-key" id="imsr-key" style="display:none">
            <div class="usgs-key-hdr">NIFC/NICC · IMSR large incidents · size ∝ acreage · letter = team type</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#e02020;border-color:#8f0f00"></div>Type 1 IMT — highest complexity</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#ff8400;border-color:#a34400"></div>Type 2 IMT</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#8f3f97;border-color:#5c1b66"></div>Complex IMT</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#7e0023;border-color:#550011"></div>NIMO — national organization</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#b08050;border-color:#5f4a34"></div>No team assigned</div>
            <div class="usgs-key-row"><div class="usgs-dot" style="background:transparent;border:2px solid #0a7a3c"></div>Bold ring = new to today's sitrep</div>
          </div>
```

## 2.2 CSS for the centered team letters

**Anchor** — the wind-arrow rules. Find (currently ~line 349):

```css
/* Observed surface-wind arrows (station wind barbs) */
.wind-arrow{background:none;border:none}
```

Insert **directly before** that comment line:

```css
/* IMSR team-letter labels — bare text centered on the canvas circle */
.imsr-lbl{background:transparent;border:none;box-shadow:none;color:#fff;font-weight:800;font-size:10px;text-shadow:0 1px 2px rgba(0,0,0,0.75);pointer-events:none;padding:0}
.imsr-lbl::before{display:none}
```

## 2.3 toggleLayer branch

**Anchor** — the existing `airnow` branch. Find (currently ~lines 3645–3649):

```js
  } else if (name === 'airnow') {
    airnowEnabled = on;
    document.getElementById('airnow-key').style.display = on ? 'block' : 'none';
    if (on) { airnowGroup.addTo(map); if (!airnowLoaded) loadAirnow(); }
    else { airnowGroup.remove(); document.getElementById('airnow-note').textContent = 'off'; }
```

Insert **directly after** that `else` line (before `} else if (name === 'red-flag') {`):

```js
  } else if (name === 'imsr') {
    imsrEnabled = on;
    document.getElementById('imsr-key').style.display = on ? 'block' : 'none';
    if (on) { imsrGroup.addTo(map); if (!imsrLoaded) loadImsr(); }
    else { imsrGroup.remove(); document.getElementById('imsr-note').textContent = 'off'; }
```

(Note: Feature 3 below **replaces** the quoted `airnow` branch — apply 3.3 first if doing both, then add this after it. The two edits are adjacent but independent.)

## 2.4 Loader + card

**Anchor** — insert directly after the Feature-1 block (i.e., still between `showFirePerimCard`'s helpers and `function setSmokeOpacity(val) {`):

```js
// ═══════════════════════════════════════════════════════════════════
// IMSR NATIONAL SITREP — NICC large-incident points (daily in season)
// Pattern mirrors loadFireIncidents/initViirs: L.canvas in markerLayerPane.
// ═══════════════════════════════════════════════════════════════════

async function loadImsr() {
  const note = document.getElementById('imsr-note');
  note.textContent = 'loading…';
  imsrGroup.clearLayers();
  try {
    const data = await fetchJson(IMSR_URL, 15000);
    // Smallest first so the biggest incidents draw on top.
    const feats = (data?.features ?? []).slice()
      .sort((a, b) => (Number(a.properties?.size) || 0) - (Number(b.properties?.size) || 0));
    const canvas = L.canvas({ padding: 0.5, pane: 'markerLayerPane' });
    let count = 0, teams = 0;
    for (const feat of feats) {
      const c = feat.geometry?.coordinates;
      if (!c) continue;
      const lon = c[0], lat = c[1];
      if (lat == null || isNaN(lat)) continue;
      const p = feat.properties || {};
      const t = IMSR_IMT[(p.imt_type || '').trim()] || IMSR_IMT[''];
      const size = Number(p.size) || 0;
      const r = size > 0 ? Math.min(18, Math.max(5, Math.log10(size) * 3.6)) : 5;
      const isNew = String(p.new_to_imsr || '').trim() !== '';
      const m = L.circleMarker([lat, lon], {
        renderer: canvas, pane: 'markerLayerPane', radius: Math.round(r),
        color: isNew ? '#0a7a3c' : t.stroke, fillColor: t.fill,
        weight: isNew ? 2.6 : 1.6, opacity: 1, fillOpacity: 0.85,
      });
      if (t.letter) {
        // Team-managed incidents get a permanent letter centered on the dot.
        m.bindTooltip(t.letter, { permanent: true, direction: 'center', className: 'imsr-lbl' });
        teams++;
      } else {
        m.bindTooltip(
          `<b>${esc(p.fire_name || 'Incident')}</b>` +
          (size ? `<br>${size.toLocaleString()} acres` : '') +
          (p.gacc ? `<br>${esc(p.gacc)}` : ''),
          { sticky: true });
      }
      m.on('click', e => { L.DomEvent.stopPropagation(e); showImsrCard(p, lat, lon); });
      imsrGroup.addLayer(m);
      count++;
    }
    imsrLoaded = true;
    note.textContent = count ? `${count} incidents · ${teams} teams` : 'none reported';
  } catch (e) {
    console.error('loadImsr:', e);
    note.textContent = 'unavailable';
  }
}

function showImsrCard(p, lat, lon) {
  ensureDetStandard();
  const t = IMSR_IMT[(p.imt_type || '').trim()] || IMSR_IMT[''];
  const title = p.fire_name || 'IMSR Incident';
  document.getElementById('det-event').textContent = title;
  document.getElementById('det-event').style.color = '#c23b10';
  const chips = document.getElementById('det-chips');
  chips.innerHTML = '';
  [[t.label, t.stroke === '#5f4a34' ? '#6b4f2e' : t.stroke],
   [p.gacc, '#6b4f2e'],
   [String(p.new_to_imsr || '').trim() ? 'NEW to sitrep' : null, '#0a7a3c']]
    .forEach(([lbl, clr]) => {
      if (!lbl) return;
      const c = document.createElement('div'); c.className = 'det-chip';
      c.style.cssText = `background:${clr}22;border-color:${clr}80;color:${clr}`;
      c.innerHTML = `<span class="chip-val">${esc(lbl)}</span>`;
      chips.appendChild(c);
    });
  document.getElementById('det-sev-desc').textContent =
    'NICC Incident Management Situation Report — national large-incident summary';
  document.getElementById('det-area').textContent = p.incident_id || '—';
  document.getElementById('det-eff-lbl').textContent = 'Discovered';
  document.getElementById('det-exp-lbl').textContent = 'Size';
  const disco = p.IrwinFireDiscoveryDateTime ? new Date(p.IrwinFireDiscoveryDateTime) : null;
  document.getElementById('det-eff').textContent = disco && !isNaN(disco) ? fmtDT(disco) : '—';
  document.getElementById('det-exp').textContent =
    p.size ? Number(p.size).toLocaleString() + ' acres' : '—';
  const pd = String(p.post_date_isoformat || '');
  document.getElementById('det-hl').textContent = pd.length === 8
    ? `In the ${pd.slice(0,4)}-${pd.slice(4,6)}-${pd.slice(6,8)} national sitrep` : '—';
  document.getElementById('det-hl-wrap').style.display = 'block';
  document.getElementById('det-instr-wrap').style.display = 'none';
  document.getElementById('det-desc').textContent = [
    t.letter ? `Incident management: ${t.label}` : 'No overhead team assigned (locally managed)',
    p.gacc ? `Coordination center: ${p.gacc}` : null,
    p.UniqueFireIdentifier ? `Fire ID: ${p.UniqueFireIdentifier}` : null,
    'Source: NIFC/NICC IMSR via WFIGS (public domain)',
  ].filter(Boolean).join('\n');
  document.getElementById('det-zoom').textContent = '⊕ Zoom to Incident';
  document.getElementById('det-zoom').onclick = () => map.setView([lat, lon], 9);
  // Feature-1 synergy: incident_id starts with the state ("CO-CUX-001160").
  enrichCardWithInciweb(p.fire_name, p.incident_id ? p.incident_id.slice(0, 2) : null, title);
  document.getElementById('detail').style.display = 'flex';
}
```

Implementation notes:
- Fields used are exactly the curl-verified names above — no `attr_`/`poly_` prefixes here.
- `IrwinFireDiscoveryDateTime` is a plain `M/D/YYYY h:mm:ss AM` string → native `Date` parses it (unlike NIFC's odd `18:2600` format, so `parseNifcDate` is not needed).
- If Feature 1 is skipped, delete the single `enrichCardWithInciweb(...)` line — everything else stands alone.
- The service updates daily during fire season (weekly/as-needed off-season); `post_date_isoformat` on the card makes staleness visible instead of hiding it.

---

# FEATURE 3 — public AirNow PM2.5 stations (graceful degradation)

**Current state (confirmed)**: the `airnow` layer exists but is hard-gated to localhost — `loadAirnow()` starts with `if (!MCP_LOCAL) { note.textContent = 'local only'; return; }` and reads a pipe-delimited file from `http://localhost:3456/airnow`; `initPublicMode()` also stamps `airnow-note` with "local only" on page load. This feature keeps the local path **unchanged** and adds a browser-direct public path via `airnowgovapi.com`.

Design: `get_state` is one POST per state, so the public loader fetches only states intersecting the current view (approximate bboxes, hard-capped at 15 requests), caches each state 15 min, and reloads on debounced `moveend` — same viewport pattern as `initViirs`. At national zoom (≤4) it loads a fixed fire-country preset instead of all 50 states. Because the endpoint is **undocumented**, the shape is validated hard and every failure lands on the note text, never a broken layer.

## 3.1 State bounding boxes + priority preset

**Anchor** — paste directly after the `AIRNOW_STATE_URL`/`IMSR_IMT` constants from Paste Block 0:

```js
// Approximate state bboxes [W,S,E,N] — only used to pick which states to
// request from AirNow for the current view (one POST per state).
const AIRNOW_STATE_BBOX = {
  AL:[-88.5,30.1,-84.9,35.0], AK:[-170.0,51.2,-129.9,71.4], AZ:[-114.8,31.3,-109.0,37.0],
  AR:[-94.6,33.0,-89.6,36.5], CA:[-124.5,32.5,-114.1,42.0], CO:[-109.1,36.9,-102.0,41.0],
  CT:[-73.7,40.9,-71.8,42.1], DE:[-75.8,38.4,-75.0,39.8],  FL:[-87.6,24.5,-80.0,31.0],
  GA:[-85.6,30.4,-80.8,35.0], HI:[-160.3,18.9,-154.8,22.3], ID:[-117.2,42.0,-111.0,49.0],
  IL:[-91.5,36.9,-87.5,42.5], IN:[-88.1,37.8,-84.8,41.8],  IA:[-96.6,40.4,-90.1,43.5],
  KS:[-102.1,37.0,-94.6,40.0],KY:[-89.6,36.5,-81.9,39.1],  LA:[-94.0,28.9,-88.8,33.0],
  ME:[-71.1,43.1,-66.9,47.5], MD:[-79.5,37.9,-75.0,39.7],  MA:[-73.5,41.2,-69.9,42.9],
  MI:[-90.4,41.7,-82.4,48.2], MN:[-97.2,43.5,-89.5,49.4],  MS:[-91.7,30.2,-88.1,35.0],
  MO:[-95.8,36.0,-89.1,40.6], MT:[-116.1,44.4,-104.0,49.0],NE:[-104.1,40.0,-95.3,43.0],
  NV:[-120.0,35.0,-114.0,42.0],NH:[-72.6,42.7,-70.6,45.3], NJ:[-75.6,38.9,-73.9,41.4],
  NM:[-109.1,31.3,-103.0,37.0],NY:[-79.8,40.5,-71.9,45.0], NC:[-84.3,33.8,-75.5,36.6],
  ND:[-104.1,45.9,-96.6,49.0],OH:[-84.8,38.4,-80.5,42.0],  OK:[-103.0,33.6,-94.4,37.0],
  OR:[-124.6,42.0,-116.5,46.3],PA:[-80.5,39.7,-74.7,42.3], RI:[-71.9,41.1,-71.1,42.0],
  SC:[-83.4,32.0,-78.5,35.2], SD:[-104.1,42.5,-96.4,45.9], TN:[-90.3,35.0,-81.6,36.7],
  TX:[-106.7,25.8,-93.5,36.5],UT:[-114.1,37.0,-109.0,42.0],VT:[-73.4,42.7,-71.5,45.0],
  VA:[-83.7,36.5,-75.2,39.5], WA:[-124.8,45.5,-116.9,49.0],WV:[-82.6,37.2,-77.7,40.6],
  WI:[-92.9,42.5,-86.8,47.1], WY:[-111.1,41.0,-104.1,45.0],DC:[-77.1,38.8,-76.9,39.0],
};
// National-zoom preset — fire country first; zoom in for other regions.
const AIRNOW_PRIORITY = ['CA','OR','WA','ID','NV','MT','AZ','NM','UT','CO','WY','TX'];
```

## 3.2 Public loader

**Anchor** — insert directly **after the existing `showAirnowCard` function** (which is reused as-is). Find its closing (currently ~line 6631):

```js
      </div>
    </div>`;
  document.getElementById('detail').style.display = 'flex';
}

// ═══════════════════════════════════════════════════════════════════
// NOAA HMS SMOKE PLUMES
// ═══════════════════════════════════════════════════════════════════
```

Insert between the `}` and the HMS banner comment:

```js
// ─── Public-web AirNow path (no localhost) ──────────────────────────
// UNDOCUMENTED endpoint behind airnow.gov: POST reportingarea/get_state,
// form body "state_code=CA", CORS * (verified 2026-07-07). It may change
// or vanish without notice — every path below fails soft to the note text.
const AIRNOW_TTL = 15 * 60 * 1000;

async function airnowFetchState(st) {
  const hit = _airnowStateCache.get(st);
  if (hit && Date.now() - hit.at < AIRNOW_TTL) return hit.recs;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 12000);
  try {
    const res = await fetch(AIRNOW_STATE_URL, {
      method: 'POST', signal: ctrl.signal,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },  // simple request → no CORS preflight
      body: 'state_code=' + encodeURIComponent(st),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (!Array.isArray(json)) throw new Error('unexpected response shape'); // shape guard — undocumented API
    // Keep the newest OBSERVED PM2.5 record per reporting area.
    // (dataType "O"=observation, "F"=forecast; aqi can be ABSENT — skip those.)
    const best = new Map();
    for (const r of json) {
      if (!r || r.dataType !== 'O' || r.parameter !== 'PM2.5') continue;
      if (typeof r.latitude !== 'number' || typeof r.longitude !== 'number') continue;
      if (r.aqi == null || isNaN(r.aqi)) continue;
      const k = r.reportingArea || `${r.latitude},${r.longitude}`;
      const stamp = `${r.validDate || ''} ${r.time || ''}`;    // MM/DD/YY — lexicographic OK within a season
      const prev = best.get(k);
      if (!prev || stamp > prev._stamp) best.set(k, Object.assign({ _stamp: stamp, _state: st }, r));
    }
    const recs = [...best.values()];
    _airnowStateCache.set(st, { at: Date.now(), recs });
    return recs;
  } finally { clearTimeout(t); }
}

function airnowStatesInView() {
  if (map.getZoom() <= 4) return AIRNOW_PRIORITY.slice();     // national view: fire-country preset
  const b = map.getBounds();
  const states = [];
  for (const [st, bb] of Object.entries(AIRNOW_STATE_BBOX)) {
    if (bb[0] <= b.getEast() && bb[2] >= b.getWest() &&
        bb[1] <= b.getNorth() && bb[3] >= b.getSouth()) states.push(st);
  }
  return states.slice(0, 15);   // hard cap — be polite to the free endpoint
}

async function loadAirnowPublic() {
  const note = document.getElementById('airnow-note');
  if (note) note.textContent = 'loading…';
  const seq = ++_airnowLoadSeq;
  const states = airnowStatesInView();
  const results = await Promise.allSettled(states.map(airnowFetchState));
  if (seq !== _airnowLoadSeq || !airnowEnabled) return;        // superseded by a newer pan/zoom
  airnowGroup.clearLayers();
  const canvas = L.canvas({ padding: 0.5, pane: 'markerLayerPane' });
  let count = 0, failed = 0;
  results.forEach((res, i) => {
    if (res.status !== 'fulfilled') { failed++; console.warn('AirNow', states[i], res.reason); return; }
    for (const r of res.value) {
      const cat = String(r.category || '');
      const s = AIRNOW_CAT[cat] || { fill:'#8a8a8a', stroke:'#3a3a3a', label:cat || 'Unknown', aqi:'–' };
      const props = { city: String(r.reportingArea || '').trim(), state: r._state,
                      aqi: Math.round(r.aqi), cat, s,
                      time: String(r.time || '').trim(), tz: String(r.timezone || '').trim() };
      const marker = L.circleMarker([r.latitude, r.longitude], {
        radius: 5, color: s.stroke, fillColor: s.fill,
        weight: 1.2, opacity: 1, fillOpacity: 0.85,
        pane: 'markerLayerPane', renderer: canvas,
      });
      marker.bindTooltip(
        `<b>${esc(props.city)}, ${esc(props.state)}</b><br>PM2.5 AQI: ${props.aqi} · ${esc(cat)}`,
        { sticky: true });
      marker.on('click', () => showAirnowCard(props));         // existing card, unchanged
      marker.addTo(airnowGroup);
      count++;
    }
  });
  airnowLoaded = true;
  if (note) note.textContent = count
    ? `${count} areas · ${states.length} states${failed ? ' · partial' : ''}`
    : (failed === states.length && states.length ? 'unavailable' : 'none in view');
}

// Debounced reload when the public-site view changes (mirrors viirsOnMove).
function airnowOnMove() {
  if (_airnowMoveTimer) clearTimeout(_airnowMoveTimer);
  _airnowMoveTimer = setTimeout(() => { if (airnowEnabled && !MCP_LOCAL) loadAirnowPublic(); }, 700);
}
```

## 3.3 Un-gate `loadAirnow` (local path untouched)

**Anchor** — the top of `loadAirnow` (currently ~lines 6559–6562):

```js
async function loadAirnow() {
  const note = document.getElementById('airnow-note');
  if (!MCP_LOCAL) { if (note) note.textContent = 'local only'; return; }
  note.textContent = 'loading…';
```

Becomes:

```js
async function loadAirnow() {
  const note = document.getElementById('airnow-note');
  if (!MCP_LOCAL) return loadAirnowPublic();   // public site: browser-direct AirNow (fails soft)
  note.textContent = 'loading…';
```

Everything below that line (the `localhost:3456` pipe-format parser) stays exactly as-is.

## 3.4 toggleLayer: hook the moveend reload

**Anchor** — the `airnow` branch quoted in 2.3. Replace it with:

```js
  } else if (name === 'airnow') {
    airnowEnabled = on;
    document.getElementById('airnow-key').style.display = on ? 'block' : 'none';
    if (on) {
      airnowGroup.addTo(map);
      if (!MCP_LOCAL) map.on('moveend', airnowOnMove);   // public path reloads per view
      if (!airnowLoaded) loadAirnow();
    } else {
      map.off('moveend', airnowOnMove);
      airnowGroup.remove(); document.getElementById('airnow-note').textContent = 'off';
    }
```

## 3.5 Remove the public-mode "local only" stamp

**Anchor** — inside `initPublicMode()` (currently ~lines 7323–7325):

```js
  ['windninja-note','hms-note','airnow-note'].forEach(id => {
    const n = document.getElementById(id); if (n) n.textContent = 'local only';
  });
```

Becomes (AirNow is now public — only WindNinja and HMS stay local-only):

```js
  ['windninja-note','hms-note'].forEach(id => {
    const n = document.getElementById(id); if (n) n.textContent = 'local only';
  });
```

Also update the stale block comment a few lines above it. Find:

```js
// The agents (Nowcast/Fire/Flood/Combined), WindNinja, and the HMS-smoke / AirNow
// layers reach a local analysis server at localhost:3456 that only exists when the
```

Becomes:

```js
// The agents (Nowcast/Fire/Flood/Combined), WindNinja, and the HMS-smoke
// layers reach a local analysis server at localhost:3456 that only exists when the
```

## 3.6 Legend footnote (undocumented-source disclosure)

**Anchor** — the existing AirNow key. Find its last row (currently ~lines 1291–1292):

```html
            <div class="usgs-key-row"><div class="usgs-dot" style="background:#7e0023;border-color:#550011"></div>Hazardous (301+)</div>
          </div>
```

Insert **before the closing `</div>`** of `#airnow-key`:

```html
            <div style="font-size:9px;color:var(--text3);margin-top:4px">Public feed via airnowgovapi.com (unofficial endpoint — may change) · Zoom/pan loads states in view</div>
```

**Failure modes handled**: endpoint gone/CORS revoked → all states reject → note `unavailable`; some states fail → markers for the rest + note `· partial`; shape drift (non-array, missing `aqi`, non-numeric coords) → records skipped or state rejected, never a JS error into the layer; unknown `category` string → grey marker with dark stroke (contrast-safe); rapid panning → `_airnowLoadSeq` discards stale responses; per-state cache means panning around one state costs zero extra requests for 15 min.

---

## Attribution summary (all three)

- **InciWeb**: "Source: InciWeb · inciweb.wildfire.gov" footer in every enriched card and the news list (built into the code above). US government, public domain.
- **IMSR**: legend header "NIFC/NICC · IMSR large incidents" + card source line "NIFC/NICC IMSR via WFIGS (public domain)".
- **AirNow**: existing card footer "Source: EPA AirNow · airnow.gov" (unchanged) + new legend footnote disclosing the unofficial endpoint.

## Post-edit checklist (per `stormwatch_regression_watch` memory)

1. Alerts layer still on by default; click an alert polygon → card opens.
2. Fire Incidents dot → card shows, InciWeb block appears ~1 s later (or not at all — never an error).
3. Fire Perimeters polygon click still works (IMSR markers live in `markerLayerPane` z450, *below* `firePerimPane` z460 — pattern preserved).
4. Toggle IMSR on/off twice; toggle AirNow on, pan the map (public build), toggle off — no orphan `moveend` handlers (the `map.off` in 3.4 covers it).
5. JS parse check (open console on load).
6. Test **both** origins: `http://localhost:8001` (AirNow must still use localhost:3456 pipe feed) and the GitHub Pages URL (AirNow must go public-path; WindNinja/HMS still say "local only").
7. Commit promptly after verification.
