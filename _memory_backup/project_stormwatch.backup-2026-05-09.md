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

---

## Local HTTP Server (required for USGS APIs)

Python is installed (3.14.4). To run:
```
cd C:\Users\aphil\Documents\Stormwatch
python -m http.server 8000
```
Then open: `http://localhost:8000/weather-alerts.html`

File:// still works for everything except USGS Stream Gauges layer.

---

## All Layers (as of 2026-05-08)

### Weather / Alerts
- **NWS Active Alerts** — GeoJSON polygons from api.weather.gov, severity-colored, detail panel on click
- **NEXRAD Radar** — RainViewer animated tiles, NOAA Level-III colors (scheme 5), floating legend
- **GOES IR Satellite** — IEM tile cache, 5-min refresh
- **NEXRAD Stations** — NOAA RIDGE II WMS, reflectivity + velocity toggle, opacity control, color key
- **SPC Day 1 & 2 Outlooks** — NOAA MapServer GeoJSON

### Wildland Fire (sidebar section name as of 2026-05-07)
- **Active Fire Incidents** — NIFC WFIGS `EGP_Active_Incidents_Prod_Public_View` FeatureServer 0, GeoJSON points, log-scale radius by acres, orange/red dots. Click opens shared detail panel (Discovered / Size / % contained). Tooltip includes discovery date.
- **Fire Perimeters** — NIFC WFIGS `WFIGS_Interagency_Perimeters_YearToDate` FeatureServer 0, uncontained only (`attr_PercentContained < 100 OR NULL`). Fields: `poly_IncidentName`, `poly_GISAcres`, `attr_POOState`, `attr_PercentContained`. Orange fill polygons.
- **VIIRS Fire Hotspots** — NASA GIBS **WMS** (not WMTS — WMTS tiles are MVT vector, not PNG). Endpoint: `https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi`, layer `VIIRS_NOAA20_Thermal_Anomalies_375m_All`. Date selector (Today / Yesterday / 2d Ago) via `viirsDaysBack` state var and `initViirs()` / `setViirsDate(daysBack)`. Default: Yesterday.
- **Red Flag Warning** — Filtered from NWS alerts array (event contains "Red Flag Warning"), rendered into `redFlagGroup` via `addAlertPolygon()`. Auto-synced with every alert refresh via `renderFireAlertLayers()`.
- **Fire Weather Watch** — Filtered from NWS alerts (event contains "Fire Weather Watch"), rendered into `fwxWatchGroup`. Same sync mechanism.
- **SPC Fire Wx Outlook D1** — SPC `fire_weather/SPC_firewx/MapServer` layers 1 (categorical) + 2 (dry thunderstorm). dn field: 5=Elevated #E69800, 8=Critical #FF0000, 10=Extreme #E600A9. Group: `fwxD1Group`. Legend: `#fwx-legend` at `left:345px, bottom:34px`.
- **SPC Fire Wx Outlook D2** — Same MapServer layers 4 + 5. Group: `fwxD2Group`.
- **ASOS / METAR Stations** — IEM `cgi-bin/request/asos.py` CSV endpoint, ~2,200 CONUS-area stations, color by temperature. 90-minute rolling window with dynamic ISO 8601 timestamps. Data pre-converted to °F and inHg by IEM. Fields: `station, lat, lon, valid, tmpf, dwpf, sknt, drct, vsby, alti`. `showMetarCard()` displays in `#detail` using per-element access (not innerHTML). AWC API abandoned — no CORS header. Station name fetched on-click via plain `fetch('https://api.weather.gov/stations/K{id}')` (not `fetchJson` — custom headers cause issues); cached in `metarNameMap`. Lat/lon shown in description.
- **Montana Mesonet** — MT Climate Office `mesonet.climate.umt.edu/api/v2/`, two parallel fetches: stations (lat/lon/name/county) + latest obs, joined by `station` key. Fields include `Air Temperature @ 2 m [°F]`, `Wind Speed @ 10 m [mi/h]`, `Wind Direction @ 10 m [deg]`, `Gust Speed @ 10 m [mi/h]`, `Relative Humidity [%]`, `Precipitation [in]`, `Snow Depth [in]`, `Solar Radiation [W/m²]`. ~215 stations. `showMontanaCard()` displays in `#detail`.
- **RAWS Weather Stations** — NIFC ArcGIS `PublicView_RAWS/FeatureServer/1`. ~5000 stations. Color by RelativeHumidity: <15%=red, 15-25%=orange, 25-40%=yellow, >40%=blue. Click opens `#detail` panel via `showRawsCard()`. Fields: StationName, AirTempStandPlace, WindSpeedMPH, WindDirDegrees, RelativeHumidity, FuelMoisture, ObservedDate, MesoWestURL.
- **KBDI Drought Index** — NOAA/NC State Climate Office XYZ tiles `https://www.ncei.noaa.gov/pub/data/nidis/tile/ncsu-meas-kbdi/{z}/{x}/{y}.png`. maxNativeZoom:7, opacity slider. Updates daily.

### Hydrology
- **FIM Flood Gauges** — NOAA api.water.noaa.gov/nwps, ~209 gauges with inundation mapping. Click opens FIM detail panel with Low/Minor/Moderate/Major inundation polygon buttons. In Hydrology section of sidebar.
- **NWS Stream Gauges** — NWS riv_gauges MapServer, ~4,000 gauges, flood-stage colored dots (STAGE_CFG). Click opens `#ugc` card, fetches NWPS per-gauge for real thresholds + forecast + impact statements.
- **USGS Stream Gauges** — USGS OGC API (api.waterdata.usgs.gov), ~14,000 gauges, CFS-magnitude color-coded blue dots. Click opens enriched card (4 parallel fetches: name, trend, stage height, historical percentile). Requires HTTP server.
- **MRMS 24h QPE** — IEM mrms_nn.cgi layer mrms_p24h
- **FEMA Flood Zones** — NFHLWMS layer 12, minZoom:14, CSS saturate(6) filter

---

## Key Technical Notes

### APIs
- RainViewer: `${radarHost}${frame.path}/512/{z}/{x}/{y}/5/1_1.png`
- NOAA RIDGE II WMS: `https://opengeo.ncep.noaa.gov/geoserver/${sid}/ows`
- HRRR WMS: IEM `hrrr/refd.cgi` and `hrrr/refp.cgi`
- MRMS QPE WMS: `https://mesonet.agron.iastate.edu/cgi-bin/wms/us/mrms_nn.cgi`, layer `mrms_p24h`
- NWS Stream Gauges: `mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query`
  - outFields: `gaugelid,location,observed,status,units,waterbody,state,obstime,action,flood,moderate,major,secvalue,secunit,url`
  - status field: major/moderate/minor/action/no_flooding → STAGE_CFG keys
  - The `action/flood/moderate/major` fields do NOT contain real thresholds — they return small decimals. Real thresholds come from NWPS per-gauge fetch.
- NWPS per-gauge: `https://api.water.noaa.gov/nwps/v1/gauges/${lid}` — returns flood.categories (real thresholds), status.forecast (predicted stage/floodCategory/validTime), flood.impacts (plain-language statements)
- FIM WMS: `mapservices.weather.noaa.gov/static/rest/services/NWS_FIM/FIM_${lid}/MapServer/${layerId}/query`
- FEMA WMS: `https://hazards.fema.gov/arcgis/services/public/NFHLWMS/MapServer/WMSServer`
  - Layer 12 = Flood Hazard Zones. Layer 28 = LOMAs (wrong). Use NFHLWMS not NFHL.
- USGS OGC API (requires HTTP server, not file://):
  - Bulk gauges: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items?f=json&parameter_code=00060&limit=10000` — paginate via links[rel=next]
  - Site name: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items/${lid}?f=json`
  - Recent trend: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/continuous/items?monitoring_location_id=${lid}&parameter_code=00060&f=json&limit=12`
  - Stage height: `https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items?monitoring_location_id=${lid}&parameter_code=00065&f=json&limit=1`
  - Historical percentiles: `https://waterservices.usgs.gov/nwis/stat/?format=rdb&sites=${siteNum}&statReportType=daily&statType=P10,P25,P75,P90&parameterCd=00060` — returns RDB (tab-delimited text), parse for today's month/day row
- SPC Fire Weather Outlooks: `https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer`
  - Layer 1 = D1 categorical, Layer 2 = D1 Dry Thunderstorm, Layer 4 = D2 categorical, Layer 5 = D2 Dry Thunderstorm
  - dn field values: 5=Elevated, 8=Critical, 10=Extreme
- RAWS: `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/PublicView_RAWS/FeatureServer/1/query`
  - Same NIFC ArcGIS org as fire incidents/perimeters
- KBDI Tiles: `https://www.ncei.noaa.gov/pub/data/nidis/tile/ncsu-meas-kbdi/{z}/{x}/{y}.png` (zoom 2–7)

### UI Components
- `#ugc` card — shared card for both NWS Stream Gauges and USGS Stream Gauges. NWS mode shows stage bar + thresholds + forecast + impacts. USGS mode shows discharge + stage height + trend + historical percentile. Card has two modes controlled by show/hide of elements.
- `#ugc-stage-lbl` — relabeled "Stage" (NWS) or "Discharge" (USGS)
- `#ugc-flow-lbl` — relabeled "Discharge" (NWS) or "Stage Ht." (USGS)
- `cfsStyle(cfs)` — returns {fill, stroke, r} for log-scale CFS coloring
- `fetchText(url, ms)` — like fetchJson but returns text (used for RDB stats)
- `addAlertPolygon(alert, geom, targetGroup=alertGroup)` — accepts optional targetGroup for reuse by Red Flag / FWX Watch layers
- `renderFireAlertLayers()` — called from `renderAlerts()` on every alert refresh; populates redFlagGroup and fwxWatchGroup
- `initViirs()` / `setViirsDate(daysBack)` — VIIRS layer creation with date offset
- `loadRAWS()` / `showRawsCard(p, lat, lon)` — RAWS station load + click card
- `toggleFwxLegend()` — collapse/expand `#fwx-legend`

### Colors / Constants
- All legends: `.leg`/`.lsw` CSS; positions: Alert `left:10px`, SPC `left:175px`, HRRR `left:320px`, Radar `left:480px`
- Hydrology legends: `#usgs-legend{left:635px}` `#mrms-legend{left:808px}` `#fema-legend{left:981px}`
- SPC FWX legend: `#fwx-legend{left:345px, bottom:34px}` (collapsible)
- CAP severity colors: Extreme `#ff2020`, Severe `#ff8000`, Moderate `#ffcc00`, Minor `#1a88ff`, Unknown `#778899`
- STAGE_CFG action color: `#7a6600` (darkened for readability on white — FIM popup uses light background)
- FEMA tiles: CSS `.fema-tiles{filter:saturate(6) contrast(1.4)}`, minZoom:14
- FWX_DN: `{5:{label:'Elevated',f:'#E69800'}, 8:{label:'Critical',f:'#FF0000'}, 10:{label:'Extreme',f:'#E600A9'}}`
- FWX_DT (Dry Thunderstorm): `{f:'#7766ee'}`
- RAWS RH colors: <15% red (#cc2200), 15-25% orange (#ff8800), 25-40% yellow (#ccaa00), >40% blue (#2255cc)

### FIM Detail Panel
- Uses the main `#detail` panel (same as NWS alerts), repurposed for gauge data
- `showGaugeDetail(g)` — uses `cfg.color` (not `cfg.fill`) for title + chip text on white background
- Action stage chip/title: uses `cfg.color` = `#7a6600` for legibility on white

### Layer Z-order (bringToFront)
`[fwxD2Group, fwxD1Group, spc2Group, spc1Group, firePerimGroup, rawsGroup, usgsFlowGroup, usgsGroup, inundationGroup, fimGroup, fireIncidentsGroup, redFlagGroup, fwxWatchGroup, alertGroup]`

---

## Known Issues / Watch Items
- WaterWatch decommissioned (end 2025) — USGS percentile colors not available via single API call; workaround is historical stats API (implemented)
- USGS OGC API `monitoring-locations` endpoint sometimes returns null geometry — name fetch may fail gracefully
- FEMA data only visible at zoom 14+
- Winter Storm Warning fill (`#ff69b4`) = HRRR Freezing Rain tile color — cannot change IEM tile colors; documented with ⚠ warning in REFP legend. Low priority to change Warning polygon fill to a distinct shade.
- NEXRAD RIDGE II WMS tiles at zoom >12: fixed with `maxNativeZoom: 12` (confirmed stable)

## StormWatch MCP Server — v3.0 (16 tools)
- Code at `C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js` (Node.js, `@modelcontextprotocol/sdk`)
- Backup v3: `C:\Users\aphil\Documents\Stormwatch\mcp-server\backup-2026-05-09\` (index.js + package files)
- Config at `C:\Users\aphil\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` (Store app path — NOT `%APPDATA%\Claude\`)
- WindNinja CLI: `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe` | DEM cache: `C:\temp\windninja_cache\`
- **All steps 1–7e complete as of 2026-05-09.**
- **All 16 tools fully tested and working.**
- **Tool 9 (aviation METAR):** `fltcat`, `obsTime`, `wspd`, `wdir`, `wgst`, `visib`, `altim` (hPa÷33.8639=inHg), `rawOb`; TAF uses `rawTAF`. `computeFlightCategory(m)` fallback added for stations where `fltcat` is absent.
- **HTTP server (localhost:3456):** `/health` and `/windninja`. Starts automatically with MCP process (Claude Desktop). Do NOT run `node index.js` manually while Claude Desktop is open.
- **Step 7e:** WindNinja layer in Layers tab → Wildland Fire section. Fetches from `localhost:3456/windninja` at map center. Arrows: L.divIcon + CSS rotate, colored by speed (blue<5, green<10, yellow<15, orange<20, red 20+). **Requires Claude Desktop to be open** — port 3456 only exists when Claude Desktop is running.
- **EADDRINUSE fix:** HTTP server has `.on('error')` handler — no longer crashes MCP process when port already held by prior session. Logs skip to stderr instead.
- **Geocoding progressive fallback:** tries full string → strip comma suffix → strip last word → strip last 2 words. Handles "Dallas TX", "Memphis Tennessee", "Albuquerque New Mexico", etc.
- **Startup stderr logging:** MCP server logs WindNinja CLI found/missing and HTTP bind success/skip on every start. Visible in Claude Desktop MCP log.
- **HTTP veg validation:** `/windninja` validates veg against {grass, brush, trees}; invalid defaults to grass.
- **Two Node processes when Claude Desktop open = normal** — one is Electron's internal Node runtime, one is the MCP server. Not a problem.
- **All plan/project docs updated 2026-05-09** — stormwatch_mcp_plan.md, project_stormwatch.md, stormwatch_architecture_notes.md all current.
- **Fire weather 404 handled gracefully:** tries two URL patterns, returns informational message if neither works.
- **Remaining optional items:** WindNinja arrow visual polish (click labels, zoom-responsive size); chat panel (Option B — HTML POSTs to localhost:3456).

### Tool List (v3.0)
1. `get_active_alerts(state)` — NWS alerts by state
2. `get_severe_outlook(day)` — SPC Day 1/2 text product
3. `get_nearest_gauge(location)` — nearest NWS flood gauge + NWPS detail
4. `get_point_forecast(location, hours)` — Open-Meteo hourly forecast
5. `get_fire_weather_outlook(day)` — SPC fire weather text (graceful 404 handling)
6. `get_storm_reports(state?)` — SPC today.csv tornado/hail/wind reports
7. `get_air_quality(location)` — Open-Meteo AQI, PM2.5, PM10, ozone
8. `get_tropical_weather()` — NHC CurrentStorms.json, all active cyclones
9. `get_aviation_weather(airport)` — aviationweather.gov METAR + TAF
10. `get_historical_weather(location, date)` — Open-Meteo archive API
11. `get_earthquake_activity(location, ...)` — USGS FDSN earthquake search
12. `get_weather_briefing(location)` — AGENT: alerts + SPC + 6hr forecast
13. `get_river_summary(location, radius_miles)` — AGENT: multi-gauge regional flood picture
14. `get_all_hazards_briefing(location)` — AGENT: all threats in one report (alerts + severe + fire + tropical + AQ + floods)
15. `get_terrain_wind(location, wind_speed, wind_direction, radius_miles, vegetation)` — WindNinja SRTM terrain simulation; output in mph; DEM cached by 0.1° grid; flags: `--output_path --write_ascii_output true --ascii_out_json 1 --ascii_out_4326 1 --mesh_choice coarse`; terrain acceleration: >1.5x=STRONG, >1.25=MODERATE, >1.1=MILD
16. `get_fire_weather_environment(location)` — 90-day precip deficit, dry days, moisture deficit (ET₀−precip), soil moisture, RH; severity: NORMAL/ELEVATED/HIGH/EXTREME; primary driver = precip total, dry days secondary; RH <15% forces EXTREME; Camp Fire analog flag at ≥60 dry days + EXTREME

## Session Changes 2026-05-08
- Fixed NEXRAD RIDGE II WMS tile disappearance at high zoom (`maxNativeZoom: 12`)
- Added HRRR REFP legend warning about pink color collision with Winter Storm Warning (documented, not fixable at source)
- Rewrote ASOS/METAR layer: abandoned AWC (no CORS) and IEM `recent_metar.py` (~4 stations); now uses IEM `asos.py` CSV endpoint — ~2,200 stations, 90-min window, data in °F/inHg
- Added ASOS station name (NWS API on-click, cached) and lat/lon coordinates to detail card
- Improved detail panel scrollbar: removed nested `#det-desc` scroll, single container on `#det-body`, 7px scrollbar width
- Verified complete: RainViewer already scheme 5 + floating legend; NEXRAD station card color key already done; HRRR REFD/REFP legends complete
- Color collision audit: only real collision is Winter Storm Warning = Freezing Rain pink (#ff69b4); Tornado Watch is yellow, SPC TSTM is blue — no other collisions

## Session Changes 2026-05-07
- Renamed "Fire Ecology" → "Wildland Fire" in sidebar
- Added 6 new Wildland Fire layers: Red Flag Warning, Fire Weather Watch, SPC Fire Wx D1/D2, RAWS, KBDI
- Added VIIRS date selector (Today/Yesterday/2d Ago)
- Renamed "Weather Data" → "Observations and Forecasts"
- Moved NEXRAD Stations + RAWS to new "Weather Stations" section
- Added "Alerts" as its own sidebar section with 8 individual alert type toggles (color-dotted)
- Added ASOS/METAR Stations and Montana Mesonet to Weather Stations
- Fixed NEXRAD note-staying-"off" bug (toggle off → on cycle)
- Fixed detail panel style bleed (FIM → NWS alert sequence)
- Fixed fire perimeter title (poly_IncidentName field)
- Fixed VIIRS opacity mismatch

## Possible Future Work
- FEMA zone legend (AE = 100-yr floodplain, X = moderate/low risk, VE = coastal high-risk)
- FEMA flood zone click-to-identify
- Cross-reference USGS gauges with NWS AHPS (via `usgsId` field in NWPS response) to show flood thresholds on USGS gauge cards
- Historical streamflow sparkline (7-day mini chart) on USGS gauge card
