---
name: StormWatch Live project
description: Active weather mapping app — canonical file path, all layers, serving setup, and session history
type: project
originSessionId: 12ddcaa0-0958-45bc-84d2-2f764a3351bd
---
## Canonical File

**`C:\Users\aphil\Documents\Stormwatch\weather-alerts.html`**

Always write to this path. Never write to OneDrive\Desktop or the user root.
Backup as of 2026-05-03: `weather-alerts.backup-2026-05-03.html` (same folder)
Backup as of 2026-05-07: `weather-alerts.backup-2026-05-07.html` (same folder)
Backup as of 2026-05-09: `weather-alerts.backup-2026-05-09.html` (same folder)
Backup as of 2026-05-16: `weather-alerts.backup-2026-05-16.html` (same folder) — includes all May 16 session work (Maps tab crash fix, RAWS fix, HRRR unit fix, NSSL CAMs viewer)
Backup as of 2026-05-17: `weather-alerts.backup-2026-05-17.html` (same folder, 276,070 bytes) — CAMS viewer fully working + Maps tab sidebar context panel (Option B) + overflow/scrollbar fixes
Backup as of 2026-05-17b: `weather-alerts.backup-2026-05-17b.html` (same folder) — Nowcast agent false-tornado-warning fix (client-side geomCache polygon check)
MCP server backup as of 2026-05-17b: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-index-2026-05-17b.js`
Backup as of 2026-05-17c: `weather-alerts.backup-2026-05-17c.html` (same folder) — Nowcast SPC location-specific level, full SPC text, cursor fix, polygon click-through fix
MCP server backup as of 2026-05-17c: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-index-2026-05-17c.js`
GitHub commit 2026-05-17c: `8fac61a`
Backup as of 2026-05-17d: `weather-alerts.backup-2026-05-17d.html` (same folder) — Agents tab, draggable panels/legends, Nowcast scroll fixed
GitHub commit 2026-05-17d: `caf7d04`
Backup as of 2026-05-19: `weather-alerts.backup-2026-05-19.html` (same folder) — Winter Storm Warning color → teal (#00bbcc); WindNinja indexing bug fix
MCP server backup as of 2026-05-19: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-index-2026-05-19.js`
GitHub commit 2026-05-19: `a0ab57b`
Backup as of 2026-05-20: `weather-alerts.backup-2026-05-20.html` (same folder) — no HTML changes this session
MCP server pre-v5 backup 2026-05-20: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-index-2026-05-20-pre-v5.js`
GitHub commit 2026-05-20 (v5.0): `ee29eb5` — MCP server 19→29 tools
Backup as of 2026-05-20b: `weather-alerts.backup-2026-05-20b.html` (same folder) — Fire Weather Agent + Flood Agent + NHD+ layer
MCP server pre-agents backup 2026-05-20: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-index-2026-05-20-pre-agents.js`
GitHub commit 2026-05-20 (agents): `019b346` — Fire Weather Agent, Flood Agent, NHD+ stream layer
GitHub commit 2026-05-20 (agents bug fixes): `861fc4a` — agent panel stacking fix, TSTM Nowcast fix, Fire/Flood panel naming
Backup as of 2026-05-20c: `weather-alerts.backup-2026-05-20c.html` (same folder) — NHD+ vector layer (replaced WMS with FeatureServer)
GitHub commit 2026-05-20 (NHD vector): `af2aabb` — NHD+ vector FeatureServer, blue polylines, zoom 9+, click-to-identify
Backup as of 2026-05-20d: `weather-alerts.backup-2026-05-20d.html` — Fire/Flood Point+Area mode parity with Nowcast (commit 8f6a2af)
Backup as of 2026-05-20e: `weather-alerts.backup-2026-05-20e.html` — NHD switched from USGS FeatureServer to OSM Overpass API (commit 658fd9e)
Backup as of 2026-05-20f: `weather-alerts.backup-2026-05-20f.html` — Waterway detail card first redesign (commit 5644a4b)
Backup as of 2026-05-20g: `weather-alerts.backup-2026-05-20g.html` — Gauge markers moved to markerLayerPane (commit 665932f)
Backup as of 2026-05-20h: `weather-alerts.backup-2026-05-20h.html` — Waterway card full rewrite with Wikipedia fetch (commit e07814a)
Backup as of 2026-05-20i: `weather-alerts.backup-2026-05-20i.html` (340,501 bytes) — NHD rivers in nhdPane; clickable through alert polygons (commit 9e5e429) — END OF SESSION
Backup as of 2026-05-26: `weather-alerts.backup-2026-05-26b.html` (same folder) — Experimental FNN Dry Lightning layer + draggable detail card — END OF SESSION
Backup as of 2026-05-27: `weather-alerts.backup-2026-05-27.html` — Bug fixes (NWS gauge -9999 threshold, #ugc card top-anchor, VIIRS UTC date bug, fire incidents canvas pane fix, NIFC field names, Discovery_Date parser)
Backup as of 2026-05-27b: `weather-alerts.backup-2026-05-27b.html` — Three smoke layers added: HMS Smoke Plumes, Smoke Forecast (NAQFC), AirNow PM2.5 Stations — END OF SESSION
MCP server backup as of 2026-05-27b: `mcp-server/backup-index-2026-05-27b.js` — Added /hms-smoke and /airnow proxy endpoints
Backup as of 2026-05-27c: `weather-alerts.backup-2026-05-27c.html` — Alert click fix; showHmsCard/showAirnowCard card bugs fixed — END OF SESSION
MCP server backup as of 2026-05-27c: `mcp-server/backup-index-2026-05-27c.js` — no changes this session
GitHub commit 2026-05-27c: `e0ddba3` — Smoke layers (HMS/NAQFC/AirNow), bug fixes, alert click fix
Backup as of 2026-05-27d: `weather-alerts.backup-2026-05-27d.html` — no HTML changes
MCP server backup as of 2026-05-27d: `mcp-server/backup-index-2026-05-27d.js` — Tools 28/29/30 (get_hms_smoke, get_airnow_stations, get_smoke_situation); fixed HMS URL from stale 2022 sample to current-day NESDIS satepsanone server with yesterday fallback
GitHub commit 2026-05-27d: `195cf2b` — Add smoke MCP tools (28/29/30); fix HMS URL to current-day NESDIS server

---

## GitHub Repository

**https://github.com/aphilp1/stormwatch-live** (public)
Set up 2026-05-17. To push changes after a session:
```
git -C "C:\Users\aphil\Documents\Stormwatch" add .
git -C "C:\Users\aphil\Documents\Stormwatch" commit -m "description"
git -C "C:\Users\aphil\Documents\Stormwatch" push
```
Claude Chat URLs (blob works, raw 404s for Claude Chat):
- `https://github.com/aphilp1/stormwatch-live/blob/master/weather-alerts.html`
- `https://github.com/aphilp1/stormwatch-live/blob/master/mcp-server/index.js`
Note: blob URL truncates at ~1000 lines for Claude Chat — point it at specific sections for later parts of the file.

---

## Local HTTP Server (required for USGS APIs and FNN data file)

Python is installed (3.14.4). To run:
```
cd C:\Users\aphil\Documents\Stormwatch
python -m http.server 8000
```
Then open: `http://localhost:8000/weather-alerts.html`

File:// still works for everything except USGS Stream Gauges layer and FNN Dry Lightning layer (both require fetch()).

---

## All Layers (current as of 2026-05-26)

### Weather / Alerts
- **NWS Active Alerts** — GeoJSON polygons from api.weather.gov, severity-colored, detail panel on click
- **NEXRAD Radar** — RainViewer animated tiles, NOAA Level-III colors (scheme 5), floating legend
- **GOES IR Satellite** — IEM tile cache, 5-min refresh
- **NEXRAD Stations** — NOAA RIDGE II WMS, reflectivity + velocity toggle, opacity control, color key
- **SPC Day 1 & 2 Outlooks** — NOAA MapServer GeoJSON

### Wildland Fire
- **Active Fire Incidents** — NIFC WFIGS `EGP_Active_Incidents_Prod_Public_View` FeatureServer 0, GeoJSON points, log-scale radius by acres, orange/red dots. Click opens shared detail panel (Discovered / Size / % contained). Tooltip includes discovery date.
- **Fire Perimeters** — NIFC WFIGS `WFIGS_Interagency_Perimeters_YearToDate` FeatureServer 0, uncontained only (`attr_PercentContained < 100 OR NULL`). Fields: `poly_IncidentName`, `poly_GISAcres`, `attr_POOState`, `attr_PercentContained`. Orange fill polygons.
- **VIIRS Fire Hotspots** — NASA GIBS **WMS** (not WMTS). Endpoint: `https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi`, layer `VIIRS_NOAA20_Thermal_Anomalies_375m_All`. Date selector (Today / Yesterday / 2d Ago).
- **Red Flag Warning** — Filtered from NWS alerts array, rendered into `redFlagGroup` via `addAlertPolygon()`. Auto-synced with every alert refresh via `renderFireAlertLayers()`.
- **Fire Weather Watch** — Filtered from NWS alerts (event contains "Fire Weather Watch"), rendered into `fwxWatchGroup`. Same sync mechanism.
- **SPC Fire Wx Outlook D1** — SPC `fire_weather/SPC_firewx/MapServer` layers 1 + 2. dn field: 5=Elevated, 8=Critical, 10=Extreme. Group: `fwxD1Group`.
- **SPC Fire Wx Outlook D2** — Same MapServer layers 4 + 5. Group: `fwxD2Group`.
- **ASOS / METAR Stations** — IEM `cgi-bin/request/asos.py` CSV endpoint, ~2,200 CONUS-area stations, color by temperature. 90-minute rolling window. Station name fetched on-click via plain `fetch('https://api.weather.gov/stations/K{id}')` (NOT fetchJson — custom headers break this endpoint); cached in `metarNameMap`.
- **Montana Mesonet** — MT Climate Office `mesonet.climate.umt.edu/api/v2/`, ~215 stations.
- **RAWS Weather Stations** — NIFC ArcGIS `PublicView_RAWS/FeatureServer/1`. ~5000 stations. Color by RelativeHumidity.
- **KBDI Drought Index** — NOAA/NC State Climate Office XYZ tiles. maxNativeZoom:7, opacity slider.
- **WindNinja Terrain Wind** — WindNinja CLI via MCP server HTTP endpoint.

### Hydrology
- **FIM Flood Gauges** — NOAA api.water.noaa.gov/nwps, ~209 gauges with inundation mapping.
- **NWS Stream Gauges** — NWS riv_gauges MapServer, ~4,000 gauges, flood-stage colored dots (STAGE_CFG). Click opens `#ugc` card, fetches NWPS per-gauge for real thresholds + forecast + impact statements.
- **USGS Stream Gauges** — USGS OGC API (api.waterdata.usgs.gov), ~14,000 gauges, CFS-magnitude color-coded blue dots. Requires HTTP server.
- **MRMS 24h QPE** — IEM mrms_nn.cgi layer mrms_p24h
- **FEMA Flood Zones** — NFHLWMS layer 12, minZoom:14, CSS saturate(6) filter
- **NHD+ Stream Network** — OpenStreetMap Overpass API. POST to `overpass-api.de/api/interpreter`. Waterway types load progressively by zoom: z9=river, z10=+canal, z11=+stream, z12+=+drain/ditch. minZoom:9, 700ms debounce. Blue polylines (#1a65c0). **Rendered in `nhdPane` (z-index 420).** Click opens `showNHDCard()` (async) with Wikipedia extract, OSM tags, source footer.

### Smoke / Air Quality (added 2026-05-27)
- **HMS Smoke Plumes** — NOAA/NESDIS Hazard Mapping System KML via MCP proxy (`localhost:3456/hms-smoke`). Polygon layer colored by density: Light (#ffee88), Medium (#ff8800), Heavy (#cc2200). Click opens detail card via `showHmsCard()`. Group: `hmsGroup`. Key: `AIRNOW_CAT` constants. Parser: `parseHmsKml()` reads `<description>` text for `Density:` and `Start Time:` values. CSS: `.naqfc-tiles` filter for NAQFC only.
- **Smoke Forecast (NAQFC)** — NOAA NAQFC surface PM2.5 WMS. Endpoint: `mapservices.weather.noaa.gov/raster/services/air_quality/ndgd_smoke_sfc_1hr_avg_time/ImageServer/WMSServer`, layer `ndgd_smoke_sfc_1hr_avg_time`. CSS class `naqfc-tiles` applies `filter:saturate(5) contrast(1.8) brightness(1.05)`. Time selector buttons (Now/+6h/+12h/+24h/+48h) use `setNaqfcTime()` → `layer.setParams({TIME:...})`. TIME format: ISO 8601 from `getNaqfcTimeStr(offsetHours)` using LOCAL date. 48-hr forecast, updated 6Z & 12Z. Legend: AQI gradient bar (0/12/35/55/150/250+ µg/m³).
- **AirNow PM2.5 Stations** — EPA AirNow `reportingarea.dat` via MCP proxy (`localhost:3456/airnow`). Pipe-delimited text, filtered for `field[11]==='PM2.5'` and `field[5]==='O'` (observed). Dedup by lat/lon. Colored by AQI category (`AIRNOW_CAT` constants). `L.circleMarker` in `markerLayerPane` with canvas renderer. Click opens `showAirnowCard()` via `det-custom`. ~500 US stations.

### Experimental
- **Dry Lightning Strikes** — FNN (Fire Neural Network) sample data. File: `data/day_fl_det.geojson` (1,296 strikes, FL, May 11–12 2026). **Requires HTTP server.** Fields: `ltg_lat`, `ltg_lon`, `kbdi` (15–658), `erc`, `hrl` (hrs since rain), `precip24h`, `relh_min`, `relh_max`, `polarity`, `lcc` (non-null = predicted fire ignition, 16 strikes). Colored by KBDI: green 0–200, yellow 200–400, orange 400–600, red 600+. Purple dots = LCC ignitions. Click opens detail card (KBDI, ERC, hours dry, precip, RH, location, polarity, LCC if applicable). Attribution: "Sample Data Provided by Fire Neural Network™". **Future:** validate LCC ignitions against FL state fire records or other fire start archives.

---

## Key Technical Notes

### APIs
- RainViewer: `${radarHost}${frame.path}/512/{z}/{x}/{y}/5/1_1.png`
- NOAA RIDGE II WMS: `https://opengeo.ncep.noaa.gov/geoserver/${sid}/ows`
- HRRR WMS: IEM `hrrr/refd.cgi` and `hrrr/refp.cgi`
- MRMS QPE WMS: `https://mesonet.agron.iastate.edu/cgi-bin/wms/us/mrms_nn.cgi`, layer `mrms_p24h`
- NWS Stream Gauges: `mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query`
  - The `action/flood/moderate/major` fields do NOT contain real thresholds — they return small decimals. Real thresholds come from NWPS per-gauge fetch.
- NWPS per-gauge: `https://api.water.noaa.gov/nwps/v1/gauges/${lid}` — returns flood.categories, status.forecast, flood.impacts
- FIM WMS: `mapservices.weather.noaa.gov/static/rest/services/NWS_FIM/FIM_${lid}/MapServer/${layerId}/query`
- FEMA WMS: `https://hazards.fema.gov/arcgis/services/public/NFHLWMS/MapServer/WMSServer`
  - Layer 12 = Flood Hazard Zones. Use NFHLWMS not NFHL.
- USGS OGC API (requires HTTP server):
  - Bulk gauges: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items?f=json&parameter_code=00060&limit=10000`
  - Site name: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items/${lid}?f=json`
  - Historical percentiles: `https://waterservices.usgs.gov/nwis/stat/?format=rdb&sites=${siteNum}&statReportType=daily&statType=P10,P25,P75,P90&parameterCd=00060`
- OSM Overpass API: `https://overpass-api.de/api/interpreter` (POST, text/plain body, full CORS support)
  - Returns HTTP 429 on rate limit — handle with `if (res.status === 429) throw new Error('rate-limited')`
- Wikipedia REST API (CORS-enabled, no key): `https://{lang}.wikipedia.org/api/rest_v1/page/summary/{article_underscored}`
- SPC Fire Weather Outlooks: `https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer`
  - Layer 1 = D1 categorical, Layer 2 = D1 Dry Thunderstorm, Layer 4 = D2 categorical, Layer 5 = D2 Dry Thunderstorm
- RAWS: `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/PublicView_RAWS/FeatureServer/1/query`
- KBDI Tiles: `https://www.ncei.noaa.gov/pub/data/nidis/tile/ncsu-meas-kbdi/{z}/{x}/{y}.png` (zoom 2–7)
- NIFC WFIGS Perimeters YTD: `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query` — confirmed working with `where=attr_POOState='US-FL'` (~74 FL records as of May 2026, latest May 4)

### UI Components
- `#ugc` card — shared card for NWS Stream Gauges and USGS Stream Gauges (two modes)
- `#detail` panel — shared card for NWS alerts, FIM gauges, NWS/USGS gauges, fire incidents/perimeters, RAWS, METAR, Montana, waterways, dry lightning strikes. **Now draggable** — drag by the `#det-head` header. Uses CSS `transform: translate(dx, dy)` accumulation. Position persists across card opens in same session.
  - `det-custom` div — dedicated container for non-alert card content (waterway, dry lightning); replaces det-desc to avoid "Description" label conflict
  - `ensureDetStandard()` — restores panel to alert layout: shows det-area-row, det-dates-row, det-desc-row; hides+clears det-custom
- `cfsStyle(cfs)` — returns {fill, stroke, r} for log-scale CFS coloring
- `fetchText(url, ms)` — like fetchJson but returns text (used for RDB stats)
- `addAlertPolygon(alert, geom, targetGroup=alertGroup)` — accepts optional targetGroup for reuse by Red Flag / FWX Watch layers
- `renderFireAlertLayers()` — called from `renderAlerts()` on every alert refresh; populates redFlagGroup and fwxWatchGroup
- `showNHDCard(p)` — async; fetches Wikipedia extract; renders to det-custom
- `showDryLtgCard(p)` — renders FNN dry lightning strike card to det-custom
- Agent panels: Nowcast (#nowcast-panel, right:10px), Fire (#fire-panel, left:270px), Flood (#flood-panel, left:595px). All draggable, position:fixed, top:55px, z-index:950.

### Leaflet Pane Architecture
Three custom panes above the default overlayPane (z-index 400):
- `overlayPane` (z:400, Leaflet default) — alert polygons (alertGroup, torWarnGroup, etc.), SPC polygons, fire perimeters
- `nhdPane` (z:420, pointer-events:auto) — NHD stream polylines; above alert polygons so rivers are clickable even when alerts call bringToFront()
- `markerLayerPane` (z:450) — all gauge/station markers (NWS gauges, USGS gauges, FIM gauges, fire incidents, RAWS, METAR, Montana, FNN dry lightning strikes)

**Critical rule:** Any new clickable vector layer (not just point markers) that might overlap with alert polygons should be assigned to `nhdPane` or higher. If bringToFront() is ever called on alert layers, SVG elements in the overlayPane get re-ordered — only pane separation guarantees click priority.

**SVG polygon clicks in custom panes are unreliable** — Leaflet 1.9.4 SVG renderer in custom panes does not reliably fire click events on polygon fills. Canvas-rendered L.circleMarker clicks work. For clickable area features, use overlayPane (default, no pane: option) and ensure L.DomEvent.stopPropagation(e) is called.

### Colors / Constants
- CAP severity colors: Extreme `#ff2020`, Severe `#ff8000`, Moderate `#ffcc00`, Minor `#1a88ff`, Unknown `#778899`
- STAGE_CFG action color: `#7a6600` (darkened for readability on white — FIM popup uses light background)
- FEMA tiles: CSS `.fema-tiles{filter:saturate(6) contrast(1.4)}`, minZoom:14
- FWX_DN: `{5:{label:'Elevated',f:'#E69800'}, 8:{label:'Critical',f:'#FF0000'}, 10:{label:'Extreme',f:'#E600A9'}}`
- RAWS RH colors: <15% red (#cc2200), 15-25% orange (#ff8800), 25-40% yellow (#ccaa00), >40% blue (#2255cc)
- NHD stream colors: all #1a65c0 (blue); weight varies by waterway type
- FNN KBDI colors: 0–200 green (#98d600), 200–400 yellow (#ffd700), 400–600 orange (#ff7700), 600+ red (#cc0000), LCC ignition purple (#dd00dd)

### Layer Z-order (bringToFront — called on basemap change)
`[hmsGroup, fwxD2Group, fwxD1Group, spc2Group, spc1Group, firePerimGroup, metarGroup, mtGroup, rawsGroup, usgsFlowGroup, usgsGroup, inundationGroup, fimGroup, fireIncidentsGroup, airnowGroup, redFlagGroup, fwxWatchGroup, torWarnGroup, torWatchGroup, svrTstmGroup, flfWarnGroup, winStmGroup, blizzGroup, redFlagAlrtGroup, otherAlvGroup, alertGroup]`
Note: nhdGroup is NOT in this list (it's in nhdPane, above all of these).

---

## Known Issues / Watch Items
- WaterWatch decommissioned (end 2025) — USGS percentile colors not available via single API call; workaround is historical stats API (implemented)
- USGS OGC API `monitoring-locations` endpoint sometimes returns null geometry — name fetch may fail gracefully
- FEMA data only visible at zoom 14+
- NEXRAD RIDGE II WMS tiles at zoom >12: fixed with `maxNativeZoom: 12` (confirmed stable)
- **DEM cache cleanup needed:** `C:\temp\windninja_cache\` contains ~306 orphaned `.asc` + `.prj` files. Cleanup: `Get-ChildItem "C:\temp\windninja_cache\" -Include "*.asc","*.prj","*.json" -Recurse | Remove-Item -Force`. Keep the 32 `.tif` DEM files.
- **Last full diagnostics:** 2026-05-19 — all services online, all APIs healthy
- Overpass API has rate limits — if a user pans/zooms rapidly, the NHD layer shows "rate limit — retry". This is expected behavior; user must wait a few seconds and pan/zoom again.
- **FNN Dry Lightning layer** requires HTTP server (`python -m http.server 8000`) — fetch() to data/day_fl_det.geojson blocked on file://

## StormWatch MCP Server — v5.1 (29 tools + 2 agent HTTP endpoints)
- Code at `C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js` (Node.js, `@modelcontextprotocol/sdk`)
- Config at `C:\Users\aphil\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
- WindNinja CLI: `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe` | DEM cache: `C:\temp\windninja_cache\`
- **HTTP server (localhost:3456):** `/health`, `/windninja`, `/fire-agent`, `/flood-agent`. Starts automatically with Claude Desktop. Do NOT run `node index.js` manually while Claude Desktop is open.
- **Two Node processes when Claude Desktop open = normal** — one is Electron's internal Node runtime, one is the MCP server.

### HTTP Agent Endpoints (v5.1)
- `/fire-agent?lat=&lon=` → fire weather risk score, fuel/drought, RH/wind, SPC fire wx, fire alerts, Camp Fire analog flag
- `/flood-agent?lat=&lon=` → NWS gauges 75mi, flood alerts, 24h/48h precip, soil moisture

### Tool List (v5.0, 29 tools)
1. `get_active_alerts(state)` — NWS alerts by state
2. `get_severe_outlook(day)` — SPC Day 1/2 text product
3. `get_nearest_gauge(location)` — nearest NWS flood gauge + NWPS detail
4. `get_point_forecast(location, hours)` — Open-Meteo hourly forecast
5. `get_fire_weather_outlook(day)` — SPC fire weather text
6. `get_storm_reports(state?)` — SPC today.csv tornado/hail/wind reports
7. `get_air_quality(location)` — Open-Meteo AQI, PM2.5, PM10, ozone
8. `get_tropical_weather()` — NHC CurrentStorms.json
9. `get_aviation_weather(airport)` — aviationweather.gov METAR + TAF
10. `get_historical_weather(location, date)` — Open-Meteo archive API
11. `get_earthquake_activity(location, ...)` — USGS FDSN earthquake search
12. `get_weather_briefing(location)` — AGENT: alerts + SPC + 6hr forecast
13. `get_river_summary(location, radius_miles)` — AGENT: multi-gauge regional flood picture
14. `get_all_hazards_briefing(location)` — AGENT: all threats in one report
15. `get_terrain_wind(location, ...)` — WindNinja SRTM terrain simulation
16. `get_fire_weather_environment(location)` — 90-day precip deficit, KBDI analog, RH, drought severity
17. `get_drought_conditions(location)` — NOAA US Drought Monitor D0–D4
18. `get_seasonal_outlook(location)` — Open-Meteo 16-day + CPC 30-day text
19. `compare_model_forecasts(location, days)` — 5 parallel Open-Meteo models (GFS, ECMWF IFS, ECMWF AIFS, GEM, ICON)

## NOAA NSSL CAMs — Verified URL Formats (May 16 2026)

**Model images:**
`https://cams.nssl.noaa.gov/graphics/models/{model}/{YYYY}/{MM}/{DD}/0000/{fhr_token}/{product}.{sector}.{fhr_token}.mp.png`
- fhr_token = `f` + (fhr × 100) zero-padded to 5 digits

**MRMS observations:**
`https://cams.nssl.noaa.gov/graphics/obs/mrms/{YYYY}/{MM}/{DD}/mrms.{field}.{sector}.{YYYYMMDD_HHMMSS}.mp.png`

**Standalone viewer:** `C:\Users\aphil\Documents\Stormwatch\nssl_cams_viewer.html`

---

## Session Changes 2026-05-27c (this session)

### Bug Fixes
- **Alert polygon click broken** — map's `click` handler called `closeDetail()` on every map click, slamming the detail panel shut immediately after `showDetail()` opened it. Fixed by removing `closeDetail()` from the map click handler. Detail now closes only via the ✕ button or `setFilter()`.
- **`showHmsCard` crash** — referenced non-existent `det-title` and `det-dates` elements → TypeError. Fixed: uses `det-event` for title, hides standard rows, shows `det-custom` for card body (same pattern as other custom cards).
- **`showAirnowCard` crash** — same wrong element IDs as HMS card. Fixed with same approach.

---

## Session Changes 2026-05-26

### Experimental Layer: FNN Dry Lightning Strikes
- New "Experimental" section added to Layers tab
- Data file `data/day_fl_det.geojson` copied from Desktop — 1,296 FL dry lightning strike features, May 11–12 2026
- KBDI-based color coding for dots (green/yellow/orange/red), purple for LCC ignition predictions (16 strikes)
- Click opens `showDryLtgCard(p)` in det-custom: shows KBDI, ERC, hours dry, 24h precip, RH range, location, polarity, LCC score
- Attribution: "Sample Data Provided by Fire Neural Network™" in legend and card
- Layer requires HTTP server (fetch() to local file)
- **Hindcast button built and then removed** — NIFC YTD data only goes to May 4; no fire records exist yet for May 11–12 period. To be revisited with FL state fire records or other archives.
- **Future:** validate FNN `lcc` predictions (16 ignition candidates) against FL Division of Forestry fire start records

### Detail Panel — Now Draggable
- `#det-head` has `cursor:move; user-select:none`
- IIFE at bottom of script: mousedown on header captures anchor offset; mousemove on document applies `transform: translate(dx, dy)` to `#detail`; mouseup releases. Close button excluded from drag trigger.
- Position persists within session; resets to default top-right on page reload.

### nhdPane — pointer-events fix
- Added `map.getPane('nhdPane').style.pointerEvents = 'auto'` in initMap() — custom panes default to pointer-events:none which blocked Leaflet SVG click events

---

## Session Changes 2026-05-20 (second batch — this session)

### Agents tab: Fire + Flood Point/Area mode parity (commit 8f6a2af)
- Fire Forecast and Flood Forecast agent sidebar cards now match Nowcast exactly: Point/Area mode buttons + Activate button
- Box-drawing implemented for both agents: mousedown→start, mousemove→L.rectangle, mouseup→run agent at center of box
- Fire box color: #ff7733 (orange). Flood box color: #3388ff (blue)
- State vars: `fireInputMode` ('point'|'box'), `floodInputMode` ('point'|'box')
- Functions: `setFireInputMode(mode)`, `setFloodInputMode(mode)`, `fwOnMouseDown/Move/Up`, `flOnMouseDown/Move/Up`

### NHD+ stream layer: switched from USGS to OpenStreetMap (commit 658fd9e)
- POST queries to `https://overpass-api.de/api/interpreter` using OSM Overpass QL
- Waterway types loaded progressively by zoom level
- Handles rate-limiting (HTTP 429) with user-visible note

### Waterway detail card complete redesign (commits 5644a4b + e07814a)
- `showNHDCard(p)` is async: fetches Wikipedia extract; card: description → Wikipedia link → optional OSM attribute rows → source footer
- All content in det-custom (NOT det-desc)

---

## Planned Next Steps (Priority Order — as of 2026-05-26)

### 1. FNN Ignition Validation (Experimental layer future work)
Validate the 16 FNN LCC ignition predictions (purple dots, May 11–12 2026 FL) against:
- Florida Division of Forestry fire records
- Any FL state fire archive with exact dates and coordinates
NIFC WFIGS is not suitable — data only goes to May 4 for that period.

### 2. Built-in Chat Panel (high value)
Chat input inside StormWatch that POSTs to `/chat` endpoint on localhost:3456. User types weather questions, MCP server runs tools, response renders in a panel. Closes the loop between seeing conditions and understanding them — no need to switch to Claude Desktop.
- POST to `localhost:3456/chat` with `{ question: "...", lat: ..., lon: ... }`
- MCP server routes to appropriate tool(s), returns plain-text response
- Chat history panel in sidebar (Agents tab or new Chat tab)
- Contextually aware of map center and active layers

### 3. NSSL CAMs Verification Overlays
Add LSR (tornado, wind, hail) and NWS Warning overlays to the 4-panel CAMs viewer.
First step: open NSSL site with overlays active, capture URL patterns from browser DevTools Network tab.

### 4. DEM cache cleanup
`Get-ChildItem "C:\temp\windninja_cache\" -Include "*.asc","*.prj","*.json" -Recurse | Remove-Item -Force`
Removes ~306 orphaned files (6.9 MB); keeps the 32 .tif DEMs (51.2 MB).

### 5. FEMA zone click-to-identify
FEMA flood zones are visible at zoom 14+ but not clickable. Add a WMS GetFeatureInfo call or point query to show zone type.

### 6. Cross-reference USGS gauges with NWS AHPS
Use the `usgsId` field in NWPS response to show NWS flood thresholds on USGS gauge cards.

---

## Claude Code ↔ Claude Chat Collaboration

GitHub is live: `https://github.com/aphilp1/stormwatch-live`
- Claude Code commits + pushes after each session
- Claude Chat reads via GitHub blob URL
- blob URL truncates at ~1000 lines — point Claude Chat at specific line ranges for large file sections
