---
name: StormWatch Live project
description: Weather mapping app — active development context
type: project
relatedFiles:
  - stormwatch_architecture_notes.md
  - stormwatch_mcp_plan.md
---
Single-file HTML/JS/CSS app at `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html`, backed by a companion MCP server at `mcp-server\index.js`.

> **See also `stormwatch_architecture_notes.md`** for scaling decisions and the "consume APIs, don't operate infrastructure" philosophy.
> **See also `stormwatch_mcp_plan.md`** for the MCP buildout history and remaining optional steps.

## Next session pickup

- **WindNinja visual polish** — arrows work and look realistic; possible future tweaks: click-to-show speed label, zoom-responsive arrow size, denser/sparser subsampling control.
- **Chat panel** — deferred. Option B (HTML app POSTs to MCP HTTP server at localhost:3456) is the preferred approach when ready.
- **Tool 9 re-test** — `fltcat` computed fallback added 2026-05-09; worth confirming KOKC/KTIK now show correct flight category after Claude Desktop restart with new code.
- **More MCP tools** — could add: `get_lightning_activity` (Blitzortung), marine forecast (NWS marine zones), UV index (Open-Meteo), or upgrade agent tools.

## Session changes 2026-05-16

- **Tool 17 `get_drought_conditions`** — NOAA US Drought Monitor D0–D4 county and statewide percentages. Pipeline: FCC census geocoder → county FIPS → USDM REST API. Updated weekly (Tuesdays).
- **Tool 18 `get_seasonal_outlook`** — Open-Meteo 16-day daily forecast summarized by week (avg high/low, total precip, rain chance, temperature character) + CPC 30-day text narrative when available.
- **Tool 19 `compare_model_forecasts`** — 5 parallel Open-Meteo calls (GFS, ECMWF IFS, ECMWF AIFS, GEM, ICON); per-day high/low/precip table with spread analysis and agreement/confidence rating.
- **Version bumped to 4.0.0** — MCP server and HTTP `/health` endpoint.

## Session changes 2026-05-09 (second pass — stability)

- **EADDRINUSE crash fixed** — added `.on('error', ...)` handler to HTTP server; no longer crashes entire MCP process when port 3456 is held by a prior Claude Desktop session.
- **Geocoding progressive fallback** — now tries full string → strip comma suffix → strip last word → strip last 2 words; handles "Dallas TX", "Memphis Tennessee", "Albuquerque New Mexico", etc. Previously failed on any "City State" format.
- **Tool 9 flight category computed fallback** — `computeFlightCategory(m)` derives VFR/MVFR/IFR/LIFR from cloud layers + visibility per FAA rules; used when `fltcat` is absent in API response (was causing ⚪ Unknown for KOKC/KTIK).
- **Startup diagnostics** — MCP server now writes to stderr on start: WindNinja CLI found/missing, HTTP server bound or EADDRINUSE skip. Visible in Claude Desktop MCP log.
- **HTTP veg validation** — `/windninja` endpoint now validates `veg` against allowed set (grass/brush/trees); invalid values default to "grass" instead of passing through to WindNinja CLI.
- **HTTP error logging** — `/windninja` 500 errors now logged to stderr for easier debugging.
- **Plan table updated** — Step 7e marked ✅.

## Session changes 2026-05-09 (first pass)

- **Tool 9 (Aviation METAR) fixed** — aviationweather.gov JSON API uses different field names than the old XML API. Fixed: `flight_category`→`fltcat`, `obs_time`→`obsTime`, `wind_speed_kt`→`wspd`, `wind_dir_degrees`→`wdir`, `wind_gust_kt`→`wgst`, `visibility`→`visib`, ceiling from `cloud_base_ft_agl`→`cldBas1/cldCvg1` (lowest BKN/OVC layer), `altim_in_hg`→`altim/33.8639` (hPa→inHg), `wx_string`→`wxString`, `raw_text`→`rawOb`. TAF: `raw_text`→`rawTAF`.
- **MCP HTTP server added** — `index.js` now starts an HTTP server on `localhost:3456` alongside the stdio MCP. Endpoints: `GET /health` (status check), `GET /windninja?lat&lon&speed&dir&radius&veg` (runs WindNinja, returns subsampled vector grid). CORS open for file:// and localhost.
- **WindNinja shared core** — extracted `runWindNinjaCore()` helper used by both the MCP tool (Tool 15) and the HTTP endpoint. Parses both `_vel-4326.json` (speed) and `_ang-4326.json` (direction) grids. HTTP endpoint subsamples to ≤15×15 arrows.
- **WindNinja HTML layer (Step 7e)** — added to Layers tab → Wildland Fire section. Toggle shows input panel (speed, direction, vegetation). "Run Simulation" fetches from `localhost:3456/windninja` at map center. Arrows rendered as `L.divIcon` with CSS rotation; colored by speed (blue<5 → green<10 → yellow<15 → orange<20 → red 20+). Legend shows after first run. Error message if MCP server not running.
- **All 16 tools tested** — complete showcase in Claude Desktop 2026-05-09. All passed. WindNinja confirmed working (Tahlequah, OK; DEM cached; 0.81s sim).
- **stormwatch_mcp_plan.md updated** — summary table now reflects all steps complete through 7d.

## Session changes 2026-05-08

- Fixed NEXRAD RIDGE II WMS tile disappearance at high zoom (`maxNativeZoom: 12`)
- Added HRRR REFP legend warning about pink color collision with Winter Storm Warning
- Rewrote ASOS/METAR layer: IEM `asos.py` CSV endpoint, ~2,200 stations, 90-min window
- Added ASOS station name (NWS API on-click, cached) and lat/lon to detail card
- Improved detail panel scrollbar: single container on `#det-body`, 7px width

## Session changes 2026-05-07

- Renamed "Fire Ecology" → "Wildland Fire" in sidebar
- Added 6 new Wildland Fire layers: Red Flag Warning, Fire Weather Watch, SPC Fire Wx D1/D2, RAWS, KBDI
- Added VIIRS date selector; renamed sidebar sections; added 8 individual alert type toggles
- Fixed NEXRAD toggle-off→on bug; fixed detail panel style bleed; fixed fire perimeter title

---

## Stack

**HTML app:** Leaflet.js, NWS API, RainViewer NEXRAD composite (animated), SPC GeoJSON, NWS FIM ArcGIS, NWPS gauge API, IEM GOES IR tile, NOAA RIDGE II WMS, aviationweather.gov (METAR/TAF via MCP).

**MCP server:** Node.js, `@modelcontextprotocol/sdk`, Open-Meteo, USGS, NHC, SPC, WindNinja 3.12.2.

**Running the HTTP server (for WindNinja layer + future chat):**
```
cd C:\Users\aphil\Documents\Stormwatch\mcp-server
node index.js
```
Then `GET http://localhost:3456/health` to verify. Claude Desktop also launches the MCP server automatically via its own stdio connection.

---

## MCP Server — v4.0 (19 tools + HTTP server)

Code: `C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js`
Config: `C:\Users\aphil\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
HTTP: `localhost:3456` — `/health`, `/windninja`
WindNinja: `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe` | DEM cache: `C:\temp\windninja_cache\`

### Tools
1. `get_active_alerts(state)` — NWS alerts by state
2. `get_severe_outlook(day)` — SPC Day 1/2 text product
3. `get_nearest_gauge(location)` — nearest NWS flood gauge + NWPS detail
4. `get_point_forecast(location, hours)` — Open-Meteo hourly forecast
5. `get_fire_weather_outlook(day)` — SPC fire weather text (graceful 404 handling)
6. `get_storm_reports(state?)` — SPC today.csv tornado/hail/wind reports
7. `get_air_quality(location)` — Open-Meteo AQI, PM2.5, PM10, ozone
8. `get_tropical_weather()` — NHC CurrentStorms.json, all active cyclones
9. `get_aviation_weather(airport)` — aviationweather.gov METAR + TAF; field names: `fltcat`, `obsTime`, `wspd`, `wdir`, `wgst`, `visib`, `altim` (hPa), `rawOb`; TAF: `rawTAF`
10. `get_historical_weather(location, date)` — Open-Meteo archive API
11. `get_earthquake_activity(location, ...)` — USGS FDSN earthquake search
12. `get_weather_briefing(location)` — AGENT: alerts + SPC + 6hr forecast
13. `get_river_summary(location, radius_miles)` — AGENT: multi-gauge regional flood picture
14. `get_all_hazards_briefing(location)` — AGENT: all threats in one report
15. `get_terrain_wind(location, wind_speed, wind_direction, radius_miles, vegetation)` — WindNinja SRTM terrain simulation; uses `runWindNinjaCore()` shared with HTTP endpoint
16. `get_fire_weather_environment(location)` — 90-day precip deficit, dry days, moisture deficit, soil moisture, RH; severity NORMAL/ELEVATED/HIGH/EXTREME; Camp Fire analog flag
17. `get_drought_conditions(location)` — NOAA US Drought Monitor D0–D4 county + statewide percentages; FCC geocoder → county FIPS → USDM REST API; updated weekly (Tuesdays)
18. `get_seasonal_outlook(location)` — Open-Meteo 16-day grouped by week (avg high/low, total precip, rain chance) + CPC 30-day text narrative
19. `compare_model_forecasts(location, days)` — GFS vs ECMWF IFS vs ECMWF AIFS vs GEM vs ICON; per-day high/low/precip with spread analysis and agreement rating

---

## UI structure

- Header: logo, status dot/message, alert count chips, clock, manual refresh button.
- Collapsible left sidebar — three tabs:
  - **Alerts:** filter pills (`All`, `Tornado`, etc.), scrollable alert cards sorted by severity (`SEV_ORDER`: Extreme→Severe→Moderate→Minor→Unknown).
  - **Layers:** toggle rows with opacity sliders. Sections: Alerts (8 individual alert type toggles), Weather / Radar, Hydrology, Wildland Fire, Weather Stations, Base Map. Radar player embedded (Play/Pause, speed, scrubber, frame timestamp).
  - **Stats:** breakdowns by severity, top event types, by region.
- Map area: sidebar collapse button (`◀`), zoom badge (bottom center), bottom-right NEXRAD station card.

### Layer sections (Layers tab)
- **Alerts** — NWS Active Alerts + 8 individual alert type toggles (Tornado Warning/Watch, SVR TSTM, Flash Flood, Winter Storm, Blizzard, Red Flag, Other)
- **Weather / Radar** — NEXRAD Radar (animated), GOES IR Satellite, HRRR (REFD/REFP), SPC D1/D2, FIM Gauges
- **Hydrology** — NWS Stream Gauges, USGS Stream Gauges (~14k), USGS Flow, MRMS 24h QPE, FEMA Flood Zones
- **Wildland Fire** — Active Fire Incidents, Fire Perimeters, VIIRS Hotspots (date picker), Red Flag Warning, Fire Weather Watch, SPC Fire Wx D1/D2, RAWS, KBDI, **WindNinja Terrain Wind** (new 2026-05-09)
- **Weather Stations** — NEXRAD Stations, RAWS, ASOS/METAR (~2,200), Montana Mesonet
- **Base Map** — Light/Dark/Satellite/Topographic

---

## Key constants / timers
- `ALERT_REFRESH_MS = 120_000` (2 min)
- `RADAR_REFRESH_MS = 300_000` (5 min)
- `SPC_REFRESH_MS = 1_800_000` (30 min)
- `ZONE_BATCH = 20` (NWS zone geometry fetch batch size)
- GOES IR auto-refreshes every 5 min via `setInterval`

## Rendering rules
- Alert polygons rendered lowest-severity-first so most severe ends up on top.
- Per-event styling in `ESTYLES` with `pulse:true` for most severe. Falls back to `SEV_FB` by severity.
- SPC styling uses `LABEL || LABEL2`.
- Inundation group renders FIM polygons below alerts, loaded on demand per gauge.
- WindNinja arrows: `L.divIcon` with `.wn-arrow` CSS class, `transform:rotate(Xdeg)` where X = `(windFromDir + 180) % 360` (arrow points direction wind blows TO).

## Key API notes
- **aviationweather.gov METAR JSON** (`/api/data/metar?ids=KOKC&format=json`): field names are `fltcat`, `obsTime` (Unix seconds), `temp/dewp` (°C), `wspd/wdir/wgst` (kt/°), `visib` (SM), `altim` (hPa — divide by 33.8639 for inHg), `wxString`, `rawOb`. Ceiling: `cldBas1/cldCvg1` through `cldBas3/cldCvg3` — find lowest BKN/OVC. TAF: `/api/data/taf`, field `rawTAF`.
- **NWPS gauge API**: `status.observed.primary` is plain number, unit is `status.observed.primaryUnit`, flood thresholds are `flood.categories.minor.stage`, `state` is `{abbreviation, name}` object.
- **SPC GeoJSON**: Day 1 = `/SPC_wx_outlks/MapServer/1`, Day 2 = `/SPC_wx_outlks/MapServer/9`. Must use `LABEL || LABEL2`.
- **NWS alerts API**: endpoint `api.weather.gov/alerts/active?status=actual` (no `message_type` filter).
- **NEXRAD RIDGE II WMS**: `opengeo.ncep.noaa.gov/geoserver/{sid}/ows`, `maxNativeZoom:12`.
- **GOES IR**: IEM tile cache, no animation available from free public sources.
- **ASOS/METAR**: IEM `asos.py` CSV, 90-min window, `report_type=3`. Do not use AWC (no CORS). Station names via `api.weather.gov/stations/K{id}` (plain fetch, not fetchJson).
- **USGS OGC API**: requires HTTP server (not file://). Bulk gauges paginate via `links[rel=next]`.
- **SPC Fire Wx**: MapServer layers 1+2 (D1), 4+5 (D2). `dn` field: 5=Elevated, 8=Critical, 10=Extreme.
- **WindNinja HTTP** (`localhost:3456/windninja`): `lat`, `lon`, `speed` (mph), `dir` (FROM degrees), `radius` (miles), `veg` (grass/brush/trees). Returns `{ input, stats, vectors:[{lat,lon,speed,dir}] }`. Subsampled to ≤15×15 grid. DEM cached by 0.1° grid at `C:\temp\windninja_cache\`.

## State variables (key globals)
`map`, `alertGroup`, `spc1Group`, `spc2Group`, `fimGroup`, `inundationGroup`, `windninjaGroup`, `windninjaEnabled`, `baseLayers`, `satLayer`, `nexradStationsEnabled`, `nexradMarkersGroup`, `nexradStations`, `activeNexradStation`, `nexradReflLayer`, `nexradVelLayer`, `nexradActiveProduct`, `alerts`, `prevAlertIds`, `fimGauges`, `selectedGaugeId`, `zoneCache`, `geomCache`, `activeFilter`, `selectedId`, `radarFrames`, `radarLayers`, `radarIdx`, `radarPlaying`, `currentTab`, `kbdiLayer`, `kbdiEnabled`. Also `STAGE_CFG` (gauge stage config) and `REGION_LABELS` (state grouping).

## Known issues / watch items
- `min=0.0` in WindNinja stats — edge-of-domain artifact; fix by filtering speed < 0.1 mph.
- FEMA data visible only at zoom 14+.
- Winter Storm Warning fill (`#ff69b4`) = HRRR Freezing Rain tile color — cannot fix at source; documented with ⚠ in REFP legend.
- NEXRAD RIDGE II WMS tiles at zoom >12: fixed with `maxNativeZoom:12`.
- USGS OGC API `monitoring-locations` endpoint sometimes returns null geometry.

## Possible future work
- Filter WindNinja edge-cell zeros (speed < 0.1 mph)
- FEMA zone legend (AE = 100-yr floodplain, X = moderate/low risk, VE = coastal high-risk)
- FEMA flood zone click-to-identify
- Cross-reference USGS gauges with NWS AHPS (via `usgsId` in NWPS response) for flood thresholds on USGS cards
- Historical streamflow sparkline (7-day mini chart) on USGS gauge card
- Chat panel (Option B — HTML POSTs to `localhost:3456`)
