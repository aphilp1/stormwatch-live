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

## Always check health endpoint before debugging WindNinja
`Invoke-RestMethod "http://localhost:3456/health"` is the fastest way to confirm the MCP HTTP server is up. If it fails, the issue is always that Claude Desktop isn't running — not a code bug.
**Why:** Spent session time on this diagnostic path.
**How to apply:** When user reports WindNinja not working, run the health check first before looking at code.
