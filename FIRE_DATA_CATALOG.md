# StormWatch — Wildland Fire Data Catalog & Upgrade Plan

*Researched & endpoint-verified by Fable, 2026-07-05. CORS tested with `Origin: https://aphilp1.github.io`.*
*Companion to the Fire section overhaul — see memory `stormwatch-fire-section`.*

## Already in StormWatch (build on, don't duplicate)
- NIFC/WFIGS `EGP_Active_Incidents` (points) + `WFIGS_Interagency_Perimeters_YearToDate` (polygons) — **improved 2026-07-05** (wildfire-only, size∝acreage, color by containment, current-active perimeter filter).
- NASA GIBS VIIRS thermal-anomaly raster tiles · NOAA HMS smoke · NOAA NAQFC smoke forecast (WMS) · SPC Day 1/2 fire-weather outlook · NWS Red Flag / Fire Weather Watch alerts.

---

## TOP 6 RECOMMENDED ADDITIONS (ranked by value/effort)

1. **NIFC VIIRS/MODIS Heat Detections (vector points)** — clickable satellite hot spots with FRP, confidence, sensor, age → time-color (<6h red / <12h orange / <24h yellow). Covers **AK+HI**. Effort **Low**. Must filter `AgeInHours<=24` + bbox (layer holds ~7 days / 177k pts).
   - `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/VIIRS_Heat_Detections/FeatureServer/0/query?where=AgeInHours<=24&outFields=*&f=geojson`
   - `.../Modis_Heat_Detections/FeatureServer/0/query?...&f=geojson`
   - CORS ✅ · key none · ~4-min-fresh. (Data `Latitude`/`Longitude` labels are swapped — use geometry.)

2. **Predictive Services 7-Day Significant Fire Potential** — forward-looking "where fire will be a problem this week" polygons; pairs with existing SPC outlook (SPC=weather, PSP=fire potential). Effort **Low**.
   - `https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer/{0..6}/query?where=1=1&outFields=*&f=geojson` (0=Day1…6=Day7)
   - CORS ✅ (echoed our origin) · key none · CONUS+AK · daily · Day-1 ~84 KB.

3. **Freshest operational perimeters** — `WFIGS_Daily_Perimeters_Public` (IR-flight / hand-sketch shapes with `poly_MapMethod`, `poly_DateCurrent` — "mapped by infrared flight 03:12 today") and `WFIGS_Interagency_Perimeters_Current` (current-going only, lighter). Effort **Low**, drop-in beside current perimeter layer. CORS ✅ · key none.

4. **InciWeb RSS join** — official per-fire narrative + evacuation/closure pointers + link, inside the fire popup; also a standalone "incident news" panel. Effort **Medium** (XML parse + name/IrwinID match).
   - `https://inciweb.wildfire.gov/incidents/rss.xml` — CORS `*` ✅ · key none · continuous.

5. **USGS Fire Danger WMS (Days 1–7)** — national daily fire-danger raster the tab currently lacks; day slider like NAQFC. Effort **Low**. CONUS-only.
   - WFPI: `https://dmsdata.cr.usgs.gov/geoserver/firedanger_wfpi-forecast-1_conus_day_data/wms` (layer `wfpi-forecast-1_conus_day_data`; swap `-1_` → `-2_`…`-7_` for later days)
   - Also Large-Fire-Prob (`wlfp`) and Fire-Spread-Prob (`wfsp`). `L.tileLayer.wms` pattern.

6. **IMSR large-incident layer + AirNow PM2.5** — (a) `IMSR_Incident_Locations_Most_Recent_View` = national sitrep points (IMT type, GACC, "new to IMSR") for a "National Fire Situation" strip; (b) `POST https://airnowgovapi.com/reportingarea/get_state` (body `state_code=CA`) = ground-truth PM2.5 under HMS smoke. Effort **Medium**. AirNow endpoint is undocumented → build with graceful degradation.

## Other verified layers (same NIFC ArcGIS org — CORS ✅, no key, `f=geojson`)
- `WFIGS_Incident_Locations_Current` — authoritative IRWIN incident points (richer than EGP).
- `WFIGS_Incident_Locations_Last24h` — new starts in last 24 h ("new fires" pulse).

## Skip / not viable
- **Raw NASA FIRMS API** — free MAP_KEY but **no CORS** from browser; #1 delivers the same detections without key or proxy. (Keyless static CSVs exist but also no CORS.)
- **National evacuation feed** — none exists publicly; handle via InciWeb links + `protect.genasys.com` per incident.
- **GACC situation reports / WFAS station maps** — PDF/image only; IMSR ArcGIS view (#6) and USGS WFPI WMS (#5) are the data-shaped substitutes.

**Cross-cutting:** items #1–3 and #5 live on infrastructure StormWatch already talks to (ArcGIS `f=geojson` / `L.tileLayer.wms`) — no proxies, no keys, no build changes, just attribution lines. All US-government public-domain data.
