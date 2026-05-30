---
name: Feedback and preferences
description: Confirmed patterns, corrections, and style preferences from the user
type: feedback
originSessionId: 12ddcaa0-0958-45bc-84d2-2f764a3351bd
---
## Response style
Always discuss and get agreement before making changes — user said "before you make any changes, let's think about it."
**Why:** User wants to understand tradeoffs before committing. Present options (A/B/C) for significant changes.
**How to apply:** For any change that affects behavior, layout, or architecture, describe options first. Only proceed immediately for clearly-requested small fixes.

## Color on white vs dark backgrounds
Use `cfg.color` (darker shade) for text on white/light backgrounds; `cfg.fill` (bright color) only for text on dark backgrounds or for fills.
**Why:** `cfg.fill` for action stage = `#ffee33` (bright yellow) — nearly invisible on white. The FIM popup and detail panel use white backgrounds.
**How to apply:** FIM popup, NWS alert detail panel → use `cfg.color`. The `#ugc` gauge card (dark glass) → `cfg.fill` is fine.

## FEMA layer specifics
- Use `NFHLWMS/MapServer/WMSServer` (NOT `NFHL/MapServer/WMSServer` which returns 400)
- Layer `12` = Flood Hazard Zones. Layer `28` = LOMAs (wrong).
- minZoom:14 — confirmed by user, data only meaningful at neighborhood scale
- CSS `filter:saturate(6) contrast(1.4)` required to make tiles visible

## NWS riv_gauges threshold fields
The `action`, `flood`, `moderate`, `major` fields in riv_gauges MapServer do NOT contain real stage thresholds. They return small decimals (~0.10-0.30). Real thresholds must be fetched from NWPS per-gauge API.
**Why:** Spent time displaying garbage values before discovering this.
**How to apply:** Always fetch `api.water.noaa.gov/nwps/v1/gauges/${lid}` for real thresholds.

## USGS vs NWS gauges
The NWS riv_gauges layer is NOT USGS data — it's NWS AHPS multi-agency network. User was surprised by this.
**Why:** We originally labeled it "USGS Stream Gauges" which was wrong. Corrected to "NWS Stream Gauges."
**How to apply:** Keep these two layers clearly distinct in UI and conversation. True USGS data comes from api.waterdata.usgs.gov.

## USGS OGC API requires HTTP server
`api.waterdata.usgs.gov` and `waterservices.usgs.gov` both block file:// (null origin). Must serve from localhost.
**Why:** CORS restriction on null origin.
**How to apply:** Always remind user to run the Python server when USGS features are involved.

## NIFC ArcGIS org is reliable for fire data
NIFC's public ArcGIS org (`services3.arcgis.com/T4QMspbfLg3qTGWY`) hosts both RAWS stations and fire incidents/perimeters and returns valid CORS-enabled GeoJSON. Confirmed working on first load.
**Why:** IEM RAWS network endpoint returned empty results; NIFC FeatureServer was the correct alternative.
**How to apply:** For any RAWS or NIFC fire data need, go to this ArcGIS org first.

## SPC fire weather is a separate MapServer from convective outlooks
`fire_weather/SPC_firewx/MapServer` — not in the convective outlook service. Layers 1/2=D1, 4/5=D2.
**Why:** Initially tried the convective MapServer and found no fire weather layers there.
**How to apply:** Use the `fire_weather/SPC_firewx` service path for any SPC fire weather work.

## Use plain fetch() for NWS API station lookups, not fetchJson()
`fetchJson()` sends a custom `Accept` header that causes the NWS `api.weather.gov/stations/{id}` endpoint to fail silently. Use plain `fetch(url).then(r => r.json())` instead.
**Why:** Discovered when station name lookups returned nothing; switching to bare fetch fixed it immediately.
**How to apply:** Any new NWS API call that doesn't need the custom User-Agent/Accept headers should use plain fetch. `fetchJson` is fine for IEM, NIFC, and other APIs that work with it.

## Scrollable panels: single container, wide scrollbar
Never nest two scroll regions (`overflow-y:auto` inside another `overflow-y:auto`). Remove inner scroll constraints and let the outer container handle all scrolling. Scrollbar width should be at least 7px with a hover state.
**Why:** The detail panel had `#det-desc` with `max-height:200px;overflow-y:auto` nested inside `#det-body` which also scrolls — the 3px scrollbar on the inner region was nearly impossible to grab. Removing the inner constraint and widening the outer bar was confirmed "way better."
**How to apply:** Any new scrollable panel or content area in StormWatch: one scroll container, 7px scrollbar, `scrollbar-width:thin` for Firefox, hover highlight on thumb.

## Step-by-step for setup tasks
User needed very detailed step-by-step guidance for installing Python and starting the HTTP server.
**Why:** Non-technical user, first time doing this.
**How to apply:** For any command-line or system task, give numbered steps with exact commands, explain what each does, and ask them to report back what they see.

## WindNinja browser layer requires Claude Desktop to be open
The HTML app's WindNinja layer calls `localhost:3456/windninja` directly. That port only exists when the MCP server Node process is running, which only happens when Claude Desktop is open.
**Why:** User was confused when WindNinja stopped working after closing Claude Desktop — expected it to be self-contained in the browser.
**How to apply:** Always remind user that WindNinja (and any future localhost:3456 features) require Claude Desktop running. If the layer fails, check health endpoint first.

## Do not run `node index.js` manually while Claude Desktop is open
Claude Desktop auto-starts the MCP server. Running it manually creates a second process that hits EADDRINUSE on port 3456.
**Why:** User tried this during debugging and it caused confusion about which process was authoritative.
**How to apply:** If user reports port conflicts or double processes, ask if they ran node manually. The fix is to kill the manual process and let Claude Desktop manage it.

## Killing old Node process before MCP server restart
When `index.js` changes need to take effect, run `Stop-Process -Name node -Force -ErrorAction SilentlyContinue` in ANY PowerShell window BEFORE reopening Claude Desktop.
**Why:** The EADDRINUSE error handler silently skips rebinding if port 3456 is already held by a previous Node process. Claude Desktop reopens fine but the OLD code keeps serving — new code is never loaded. User will see no difference.
**How to apply:** Any session where `index.js` was changed: always kill node first, then reopen Claude Desktop, then verify with `Invoke-RestMethod "http://localhost:3456/health"` before testing.

## Always check health endpoint before debugging WindNinja
`Invoke-RestMethod "http://localhost:3456/health"` is the fastest way to confirm the MCP HTTP server is up. If it fails, the issue is always that Claude Desktop isn't running — not a code bug.
**Why:** Spent session time on this diagnostic path.
**How to apply:** When user reports WindNinja not working, run the health check first before looking at code.

## CRITICAL: Back up weather-alerts.html at the END of every session
Always create a dated backup (`weather-alerts.backup-YYYY-MM-DD.html`) at the end of every working session, not just at the start.
**Why:** On 2026-05-16 I only backed up at 11:00 AM but continued working for hours without saving again — the entire afternoon's work was unbacked.
**How to apply:** Before closing a session where any edits were made to weather-alerts.html, copy it to a backup file with today's date (append b/c/d if multiple backups in one day). Update project_stormwatch.md with the new backup entry. Do not assume the user will remind you.

## Every new clickable vector layer needs its own Leaflet pane above overlayPane
Any L.geoJSON polyline or polygon layer added to the default overlayPane (z:400) becomes unclickable whenever alert polygons call bringToFront() — the alert SVG paths rise to the top of the shared SVG element and intercept all clicks in their area. This applies to LINES, not just filled polygons.
**Why:** The NHD stream layer was unclickable whenever NWS alerts were active because alertGroup.bringToFront() pushed alert SVG paths above the river polylines. Took two debugging sessions to diagnose — the root cause is SVG DOM order within a shared pane.
**How to apply:** Create a named pane (e.g., `nhdPane` at z:420) in `initMap()` and pass `pane: 'nhdPane'` to the L.geoJSON options. Current pane stack: overlayPane (z:400) → nhdPane (z:420) → markerLayerPane (z:450). Any future clickable vector layer that overlaps with alert zones: assign it to nhdPane or a new pane above 400.

## Use a dedicated det-custom container for non-alert detail cards
When a non-alert feature (waterway, custom card) uses the shared `#detail` panel, never inject content into `#det-desc` directly. The parent `.df` wrapper div has a "Description" label that always shows — creating a confusing header.
**Why:** The waterway card showed "DESCRIPTION" and "DETAILS" as redundant empty section headers because content was injected into det-desc (which has a visible .dl "Description" label sibling). User said: "This really sucks. Where is the description? Where are the details? This is crappy crappy work."
**How to apply:** Add `id="det-desc-row"` to the Description wrapper so it can be hidden. Add `<div id="det-custom" style="display:none">` as a sibling — this is the injection target for all non-alert cards. `ensureDetStandard()` shows det-desc-row and clears det-custom. Non-alert cards: hide det-desc-row, show det-custom, write content there.

## OSM wikipedia tag format: parse it, don't display it raw
The OSM `wikipedia` property uses the format `"en:Article Name"` (lang prefix + colon + title). Displaying this raw string looks like a bug to the user.
**Why:** The waterway card displayed "Wikipedia en:Neosho River" as plain text — no link, no description. The tag is a reference, not display text.
**How to apply:** Parse with `tag.match(/^([a-z]{2,3}):(.+)$/)` → lang and article. Build: Wikipedia URL = `https://${lang}.wikipedia.org/wiki/${article.replace(/ /g,'_')}`. Fetch description via REST API: `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${article_underscored}` → `data.extract`. Always show the actual description text + a clickable link button, never the raw tag.

## Nowcast SPC level must come from client-side polygon check, NOT server national text
The MCP server parses the SPC Day 1 text product and returns the highest risk level mentioned anywhere nationally (e.g., "ENHANCED" for the Central Plains). This gets applied to every location regardless of where you click — Oregon shows Enhanced risk even with no SPC polygons nearby.
**Why:** NWS SPC text products describe the national picture. A point in Oregon has nothing to do with an Enhanced risk in Iowa.
**How to apply:** Populate `spc1Cache` (array of `{cat, geom}`) when SPC Day 1 layer loads. In `ncGetMapAlerts`, query `spc1Cache` using `ptInGeom`/bbox the same way NWS alerts are checked. Pass `spcLevel` in the return object. In `ncApplyMapAlerts`, use `ma.spcLevel` instead of `d.spc?.level`. Also override `d.spc` with the location-specific level and suppress national text when `spcLevel === 'NONE'`.

## Leaflet polygon clicks do NOT propagate to the map — intercept at polygon handler
When `nowcastMode` is active and user clicks a Leaflet vector layer (alert polygon, fire perimeter, etc.), the layer's own click handler fires and `L.DomEvent.stopPropagation(e)` kills the map click event. Nowcast never runs.
**Why:** Discovered when clicking inside a Tornado Warning polygon in Nowcast mode opened the alert detail panel instead.
**How to apply:** In every polygon/marker click handler that calls `stopPropagation`, add: `if (nowcastMode && nowcastInputMode === 'point') { runNowcast(e.latlng.lat, e.latlng.lng); return; }` BEFORE the normal handler. Currently applied to `addAlertPolygon`. Any new clickable layer added to the map needs the same intercept.

## Leaflet interactive layers override the map cursor — use CSS !important to lock crosshair
Setting `map.getContainer().style.cursor = 'crosshair'` is overridden by Leaflet's `.leaflet-interactive` CSS class (sets cursor:pointer) on any vector layer the user hovers over. The crosshair disappears and users think Nowcast mode turned off.
**Why:** Confusing UX — user sees pointer cursor and stops clicking, or clicks and gets wrong behavior.
**How to apply:** Add a CSS class (`nc-mode`) to `#map-wrap` when Nowcast is active. CSS rule: `#map-wrap.nc-mode, #map-wrap.nc-mode .leaflet-container, #map-wrap.nc-mode .leaflet-interactive { cursor: crosshair !important }`. Toggle the class in `toggleNowcastMode` and `closeNowcast`. Remove `map.getContainer().style.cursor` assignment (the CSS handles it).

## Nowcast SPC text was truncated in two places — always check both server and client
Server (`index.js`): `lines.slice(s, s+4).join(" ").slice(0,400)` — only 4 lines, 400-char cap. Fix: slice to first `&&` section terminator or s+20 lines, no char limit.
Client (`renderNowcast`): `d.spc.excerpt.slice(0,280) + '…'` — 280-char display cap. Fix: removed entirely.
**Why:** SPC narrative sections are typically 10-20 lines. Both limits cut the text mid-sentence.
**How to apply:** When adding any new text display in Nowcast or other agents, don't add arbitrary char limits if the panel already scrolls.

## NWS alert geometry: always use `geomCache[alert.id]`, never `alert.geometry`
NWS alert GeoJSON features (`alerts` array in the HTML app) have `f.geometry === null` for zone-based alerts. The actual rendered polygon is stored async in `geomCache[f.id]` after zone geometry fetch.
**Why:** Wasted multiple debugging iterations using `f.geometry` which was always null. Every time a geometry check returned false for all alerts, it was because I was reading the wrong property.
**How to apply:** Any code that needs the polygon boundary of an NWS alert: use `geomCache[f.id]`, check for null, then pass to `ptInGeom` or bbox math. Never reference `f.geometry` or `alert.geometry`.

## NWS `?point=lat,lon` API is zone-based, not geometry-based — do not trust it for geographic filtering
`api.weather.gov/alerts/active?point=lat,lon` returns all alerts active in the same county/zone as the point — even if the tornado warning polygon is miles away from the clicked location. It cannot be used to determine whether an alert polygon actually covers a specific point.
**Why:** This was the root cause of the Nowcast false-tornado-warning bug. The server correctly called the NWS API and received "Tornado Warning active" — because there was a tornado warning somewhere in the same zone. But the warning polygon was nowhere near the queried area.
**How to apply:** For any geographic filter ("does alert X cover this point/area?"), always use client-side `geomCache` polygon intersection via `ptInGeom` or bbox check. The NWS zone API can only tell you if an alert type exists in a zone, not whether a polygon covers a specific location.

## WindNinja `parseWindNinjaOutput` — grid[] for indexing, data[] for stats (FIXED 2026-05-19)
`parseWindNinjaOutput` returns two arrays: `grid[]` (full nrows×ncols, `null` for nodata — preserves 2D addressing) and `data[]` (valid values only — for min/max/mean/p10/p90 stats). The `/windninja` endpoint uses `vel.grid[idx]` for per-cell lookup and `angData` is also `.grid`. `vel.data` is used only for stats.
**Why:** Original code filtered nodata into a compacted `data[]` array, then indexed it with `r * ncols + c` — wrong for any cell after a nodata gap. Fixed 2026-05-19.
**How to apply:** Any future changes to WindNinja output parsing: never index the filtered data[] array with 2D grid math. grid[] is the source of truth for spatial lookups; data[] is stats-only.

## flex:1 on a child requires parent to have explicit height — max-height alone is NOT enough
`flex:1` (flex-grow:1, flex-basis:0) distributes extra space only when the parent has a definite height. A parent with only `max-height` (no `height`) does NOT give flex children a definite space to fill — the body collapses to 0.
**Why:** Spent many attempts trying to get Nowcast panel to scroll with flex layout. The duplicate CSS rule removal, display:flex fix, etc. all failed because the panel had no explicit height.
**How to apply:** For "header pinned + body scrolls" layouts: either give the container an explicit `height`, OR skip flex entirely and give the body a direct `max-height:calc(...)` with `overflow-y:auto`. The direct max-height approach is simpler and more reliable.

## Duplicate CSS rules later in the file silently override earlier rules
A later `#nowcast-body{padding:12px 13px}` rule in the stylesheet was overriding the earlier `#nowcast-body{overflow-y:auto;flex:1;...}` rule — stripping out the scroll and flex properties entirely.
**Why:** This was invisible and took many attempts to find. The scroll looked completely broken despite correct JS.
**How to apply:** When scroll or layout properties appear to have no effect, grep for duplicate CSS rules targeting the same element. Check the ENTIRE stylesheet, not just the area you're editing.

## App #header has z-index:900 — fixed panels need z-index > 900 and top > 46px
The StormWatch `#header` element has `z-index:900` (as a flex item, this creates a stacking context). Any `position:fixed` panel with `z-index < 900` or `top < 46px` will be partially hidden behind the app header.
**Why:** Nowcast panel header was invisible — z-index:790 and top:10px put it behind the 46px-tall app header.
**How to apply:** Any new fixed panel: use `top:55px` minimum and `z-index:950` to clear the app header safely.

## CRITICAL: Read project_stormwatch.md AND hindcast_missoula_derecho.md at session start
At the start of any session in C:\Users\aphil\Documents\Stormwatch\, read BOTH memory files immediately before doing anything else. Do not rely solely on the session summary.
**Why:** In 2026-05-09 session I failed to read project_stormwatch.md and consequently didn't know WindNinja was installed, the MCP server was built, or the cache existed — despite all of it being documented there. I suggested downloading software the user had already built and searched for files in front of me. User called this a "major fail" and said it "scared them a lot."
**How to apply:** First action in any new session: Read both memory files. The session summary is a lossy compression — it missed months of project state. The files are the ground truth.
