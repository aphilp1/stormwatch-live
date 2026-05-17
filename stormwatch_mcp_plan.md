# StormWatch MCP — Step-by-Step Buildout Guide

A printable, offline reference for building your first weather MCP server. Written so you can read it cold, away from any Claude conversation, and know what's coming.

You don't need to do any of this tonight. When you're ready, work through the steps one at a time, at whatever pace feels comfortable. **Each step is meant to be a separate session.** Don't try to do them all at once.

---

## Background — What is an MCP server, in plain language?

An MCP (Model Context Protocol) server is a small program that runs on your computer and exposes a set of **tools** — like little functions — that any AI assistant (Claude Desktop, Claude Code, Cowork) can call.

Think of it like this:

- The **HTML app** (`weather-alerts.html`) is a *dashboard* for **humans**. It paints maps, draws polygons, shows colors.
- An **MCP server** is a *phone line* for **AI assistants**. It has no UI. Nobody opens it in a browser. It just sits there, ready to answer questions like "what alerts are active in Oklahoma?" with structured data.

Both pull from the same underlying weather APIs (NWS, SPC, HRRR, etc.). They just serve completely different audiences — one for your eyes, one for the LLM's brain.

**Why bother?** Because once a StormWatch MCP exists, every Claude conversation you have — anywhere — can talk weather. Trip planning, severe weather check-ins for family, model intercomparisons, severe-threat narratives. None of those are possible today; all of them become possible the moment the MCP is installed.

---

## The full journey — seven steps

1. **Understand what we're building** (mental model) — done if you've read the Background above
2. **Check prerequisites** on your computer
3. **Build the smallest possible MCP** — just one tool, just one feature
4. **Hook it up to Claude** — a small config edit
5. **Test it** — have your first weather conversation
6. **Expand** — add more tools, one at a time
7. **WindNinja terrain wind tool** — sub-kilometer fire weather winds via local simulation

Steps 1–5 take you from zero to a working weather MCP with one tool. Step 6 is a repeating pattern. Step 7 is a special focused session that adds terrain-resolved wind forecasting at 100–500m resolution — the thing no public API can give you.

---

## Step 2 — Prerequisites check

**What you need:**
- **Node.js** installed on your computer. MCP servers are typically written in JavaScript/TypeScript and need Node to run. (Python is also possible but Node is more common.)
- **Claude Desktop or Claude Code** already on your computer (you have these).
- **The Stormwatch project folder** (you have this: `C:\Users\aphil\Documents\Stormwatch\`).

**How to check whether Node is installed:**
Open PowerShell and type:
```
node --version
```
If it returns something like `v20.10.0`, you're good. If it says "command not recognized," you need to install Node.

**How to install Node (if needed):**
Go to https://nodejs.org and download the LTS version. Run the installer. Accept defaults. Done.

**What to tell Claude Code at this step:**
> *"Check that Node.js is installed and tell me the version. If it's not installed, walk me through installing it on Windows."*

That's it for this step. Don't proceed to Step 3 until Node is working.

---

## Step 3 — Build the smallest first MCP

**The principle:** start with one tool, not five. Get one thing working end-to-end before adding more.

**The first tool we'll build:** `get_active_alerts(state)` — given a US state code (like "OK" or "TX"), return a list of currently active NWS weather alerts.

That's the entire first MCP. One tool. Nothing else.

**What you'll need:**
- A subfolder inside `Stormwatch/` for the MCP code (e.g., `Stormwatch/mcp-server/`)
- A few files Claude Code will create: `package.json`, `index.js` (or `index.ts`), maybe a `README.md`
- The MCP SDK from npm (`@modelcontextprotocol/sdk`)

**What to tell Claude Code:**
> *"I want to build the smallest possible MCP server for StormWatch. Read project_stormwatch.md and stormwatch_mcp_plan.md for context. Create a new folder `mcp-server` inside C:\Users\aphil\Documents\Stormwatch. Set up a Node.js MCP server with one tool called `get_active_alerts` that takes a US state code (like 'OK') and returns the active NWS alerts for that state. Use the NWS API endpoint `https://api.weather.gov/alerts/active?area={state}`. Test that the server starts. Don't add any other tools yet."*

**What success looks like:**
- A new `mcp-server/` folder exists with the code in it
- Running the server doesn't crash
- The server reports "ready" on stdout

You don't need to "use" it yet — that's Step 4.

---

## Step 4 — Hook it up to Claude

The MCP server exists, but Claude doesn't know about it yet. We tell Claude where to find it via a config file.

**Where the config file lives (Windows):**
- For Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json` (i.e., `C:\Users\aphil\AppData\Roaming\Claude\claude_desktop_config.json`)
- For Claude Code: a similar config file specific to Claude Code

**What gets added to the config:**
A small JSON entry pointing at the MCP server, telling Claude "this is a tool source called `stormwatch`, launch it like this when you want to use it."

**What to tell Claude Code:**
> *"Now connect the MCP server to Claude Desktop. Edit the config file at C:\Users\aphil\AppData\Roaming\Claude\claude_desktop_config.json and add a `stormwatch` entry that points to the MCP server we just built. If the config file doesn't exist, create it. Show me the change before applying."*

After Claude Code makes the edit, **restart Claude Desktop** (close and reopen). The new MCP won't load until you do this.

---

## Step 5 — Test it

Open a fresh Claude Desktop conversation and ask something simple:

> *"What active weather alerts are there in Oklahoma right now?"*

If everything is wired up, Claude will:
1. Recognize this as a weather question
2. Call your `get_active_alerts` tool with `state="OK"`
3. Receive the alerts data
4. Summarize them in plain language

**If it works:** congratulations, you have a functioning weather MCP. The lights are on. From here, every new tool is just a repeat of the same pattern.

**If it doesn't work:**
- Check that Claude Desktop was restarted after the config change
- Look for errors in Claude Desktop's logs (Settings → Developer)
- Tell Claude Code: *"My MCP server isn't showing up in Claude Desktop. Help me debug."*

---

## Step 6 — Expand

Once Step 5 works, adding tools is a repeating pattern. Each new tool is the same recipe:
1. Decide what data the tool returns
2. Tell Claude Code to add it to the MCP server
3. Restart Claude Desktop
4. Test it in conversation

**Suggested order of new tools** (priority based on usefulness):

1. `get_severe_outlook(day)` — SPC Day 1 / Day 2 / Day 3 outlooks. Already have the endpoints from the HTML app's code.
2. `get_nearest_gauge(lat, lon)` — find the closest NWPS flood gauge. Useful for "is the river in my area rising?" questions.
3. `get_hrrr_forecast(lat, lon, variable, hour)` — point query for HRRR forecast variables (temperature, precip, reflectivity).
4. `compare_forecasts(lat, lon, variable, horizon)` — model intercomparison via Open-Meteo (returns AIFS, GFS, ICON, GraphCast for the same point).
5. `summarize_threat(region, timeframe)` — the LLM-synthesis tool. Pulls alerts + outlook + HRRR + radar trends and lets the calling Claude write a natural-language threat summary.

Each of these takes one focused session with Claude Code. You don't have to build them all. Pick whichever sounds most useful, build it, use it for a while, then decide what's next.

---

## Step 7 — WindNinja terrain wind tool

This step is different from the others in Step 6. Instead of calling a web API, the MCP runs a local simulation program — WindNinja — and returns its output as structured data. The result is something no public API can offer: terrain-resolved wind forecasts at 100–500 meter resolution, tuned specifically for fire weather in complex terrain.

**What this unlocks:** Ask any Claude conversation "what are the terrain winds near this fire?" and get a real answer, accounting for ridges, canyons, and slope flows that 3km HRRR completely misses.

**Why it fits the architecture:** WindNinja runs in seconds on a laptop, requires no cloud infrastructure, and its CLI outputs geographic GeoJSON directly. The MCP is just a thin wrapper that calls the CLI and hands the result back to Claude. No servers. No backend. Fits the "consume, don't build" philosophy because WindNinja itself is the infrastructure — and it already lives on your machine.

---

### Step 7a — Install WindNinja (before you open Claude Code)

This is the one prereq you handle yourself, outside of Claude Code.

1. Go to: **https://research.fs.usda.gov/firelab/products/dataandtools/windninja**
2. Download the Windows installer (look for the latest version — 3.12.x as of mid-2025)
3. Run the installer, accept all defaults
4. After install, open PowerShell and verify the CLI is accessible:

```
WindNinja_cli --version
```

If that returns a version number, you're ready. If it says "not recognized," the CLI isn't in your PATH — tell Claude Code and it will help you fix it.

> **Note:** WindNinja installs a GUI app and a CLI tool (`WindNinja_cli.exe`). The MCP uses the CLI only. You don't need to use the GUI.

---

### Step 7b — Understand what the tool does (mental model)

Before asking Claude Code to build anything, it helps to know what's actually happening under the hood.

**The simulation pipeline:**

```
Input bbox + forecast hour
        ↓
MCP fetches HRRR wind data for that area (already know how to do this from Step 6)
        ↓
MCP calls WindNinja_cli with:
  - A small DEM (elevation file) for the bbox — WindNinja downloads this itself
  - The HRRR wind as initialization input
  - Output format: GeoJSON, geographic coordinates (EPSG:4326), U/V components
        ↓
WindNinja runs in ~5–30 seconds
        ↓
MCP reads the output GeoJSON
        ↓
Returns wind vectors to Claude as structured data
```

**What the output looks like:** A grid of wind vectors — each one has a lat/lon location, a speed (m/s), and a direction (degrees). Claude can describe these in plain language ("winds from the southwest at 12 mph near the ridge, shifting to westerly in the canyon below"), or the StormWatch HTML app can render them as arrows on the map.

**Resolution:** WindNinja defaults to ~100m grid spacing for domains up to 50km × 50km. For a typical fire area of 10km × 10km, that's about 10,000 wind vectors — enough spatial detail to see how terrain is steering the fire.

---

### Step 7c — Build the tool

**What to tell Claude Code:**

> *"I want to add a WindNinja terrain wind tool to my StormWatch MCP server. Read project_stormwatch.md and stormwatch_mcp_plan.md for full context — pay special attention to Step 7.*
>
> *Add a new MCP tool called `get_terrain_wind(lat, lon, radius_km, forecast_hour)` that:*
> *1. Takes a center point (lat/lon), a radius in km (default 10), and a forecast hour (0–18, default 0 for current)*
> *2. Runs WindNinja_cli.exe in forecast mode, initialized with HRRR data for that area*
> *3. Outputs GeoJSON with geographic coordinates (ascii_out_geog=true) and U/V wind components (ascii_out_uv=true)*
> *4. Reads the output files and returns a summary: bounding box, grid resolution, and an array of wind vectors (lat, lon, speed_ms, direction_deg)*
> *5. Handles errors gracefully — if WindNinja isn't installed or the CLI fails, return a clear error message rather than crashing the MCP*
>
> *WindNinja_cli.exe should be at its default install location. Use Node's `child_process.spawn` to call it. Don't add any other tools in this session."*

**What success looks like:**
- The MCP starts without errors
- Calling the tool with a lat/lon returns wind vector data (even if it takes 30 seconds)
- Errors (WindNinja not found, bad bbox, etc.) come back as readable messages, not crashes

---

### Step 7d — Test it in conversation

Once the tool is built and Claude Desktop is restarted, open a fresh conversation and try:

> *"What are the terrain-resolved winds right now near latitude 34.05, longitude -118.25?" (that's the LA area — good complex terrain test)*

Claude should call `get_terrain_wind`, wait for WindNinja to run, and then describe what the terrain is doing to the wind in that area.

**If it works:** you now have something genuinely rare — a conversational interface to sub-kilometer fire weather wind forecasts. No fire agency tool currently offers this in a chat interface.

**If it doesn't work:**
- Check that WindNinja_cli is in PATH (`WindNinja_cli --version` in PowerShell)
- Look at the MCP server logs for the exact error WindNinja returned
- Tell Claude Code: *"The WindNinja tool is failing. Here's the error: [paste it]. Help me debug."*

---

### Step 7e — Wire it into the StormWatch HTML app (optional, later)

Once the MCP tool works in conversation, you can optionally add a button to the HTML app that calls the MCP and renders the wind vectors as arrows on the Leaflet map. This is a separate session and not required — the conversational version is already useful on its own.

**What to tell Claude Code when you're ready:**
> *"I want to add a WindNinja wind layer to weather-alerts.html. The MCP tool `get_terrain_wind` already works. Add a button to the Layers tab that, when clicked, calls the MCP for the current map center and renders the returned wind vectors as directional arrows on the map. Use Leaflet's built-in arrow/marker support. Add a legend showing the speed scale."*

---

### What you DON'T need to do for Step 7

- **You do not need to understand C++ or WindNinja's internals.** The CLI handles everything — you just call it and read the output.
- **You do not need to download elevation data manually.** WindNinja fetches the DEM for you automatically when given a bounding box.
- **You do not need a GPU or supercomputer.** WindNinja's conservation-of-mass solver runs in seconds on a laptop. (There's a fancier OpenFOAM solver that takes minutes — don't use that one for the MCP.)
- **You do not need to set up any web server.** The MCP calls WindNinja locally via subprocess, exactly like any other command-line tool.

---

## What you DON'T need to do (overall)

A few things that sound scary but aren't part of this:

- **You do not need to host the MCP anywhere.** It runs locally on your computer. No servers, no cloud, no GCP.
- **You do not need to learn JavaScript or Node.js.** Claude Code writes the code. You just direct it.
- **You do not need a domain name, SSL cert, or any web infrastructure.** MCP servers communicate with Claude over local pipes, not HTTP.
- **You do not need to share it with anyone.** This is just for you, on your machine. Sharing later (publishing to the MCP registry) is optional and easy when you're ready.

---

## When stuck

If anything in this guide feels confusing when you come back to it, just paste the relevant step into a new Claude conversation along with this guide and `project_stormwatch.md`, and ask:

> *"I'm at Step N of the StormWatch MCP buildout. Help me think through it."*

Both files give Claude full context, so any conversation can pick up exactly where the last one left off.

---

## Summary card

| Step | What | Status |
|------|------|--------|
| 1 | Understand what an MCP is | ✅ Done |
| 2 | Check / install Node.js | ✅ Done (Node v24.15.0) |
| 3 | Build first MCP (one tool) | ✅ Done (`get_active_alerts`) |
| 4 | Connect to Claude Desktop | ✅ Done (Store app config path discovered) |
| 5 | Test in a real conversation | ✅ Done (live TX/OK alerts confirmed) |
| 6 | Add more tools + agents | ✅ All 16 tools built and working |
| 7a | Install WindNinja | ✅ Done (v3.12.2 at C:\WindNinja\) |
| 7b | Understand the pipeline | ✅ Done |
| 7c | Build the WindNinja tool | ✅ Done (get_terrain_wind, tool 15) |
| 7d | Test in conversation | ✅ Done 2026-05-09 — all 16 tools passed full showcase test |
| 7e | Wire into HTML app (optional) | ✅ Done 2026-05-09 — WindNinja arrow layer in Layers tab |
| 8 | New API integrations (tools 17–19) | ✅ Done 2026-05-16 — drought, seasonal outlook, model comparison |

**All 19 tools (16 tested 2026-05-09; tools 17–19 added 2026-05-16):**
1. `get_active_alerts(state)` — NWS active alerts by state
2. `get_severe_outlook(day)` — SPC Day 1/2 text outlook with geographic narrative
3. `get_nearest_gauge(location)` — nearest NWS river gauge, flood thresholds + forecast
4. `get_point_forecast(location, hours)` — hourly forecast via Open-Meteo
5. `get_fire_weather_outlook(day)` — SPC fire weather text (graceful 404 handling)
6. `get_storm_reports(state?)` — SPC today.csv tornado/hail/wind
7. `get_air_quality(location)` — AQI, PM2.5, PM10, ozone via Open-Meteo
8. `get_tropical_weather()` — NHC active cyclones
9. `get_aviation_weather(airport)` — METAR + TAF; **field names fixed 2026-05-09** (see project_stormwatch.md API notes)
10. `get_historical_weather(location, date)` — Open-Meteo archive
11. `get_earthquake_activity(location, ...)` — USGS FDSN
12. `get_weather_briefing(location)` — AGENT
13. `get_river_summary(location, radius_miles)` — AGENT
14. `get_all_hazards_briefing(location)` — AGENT
15. `get_terrain_wind(...)` — WindNinja; uses shared `runWindNinjaCore()` with HTTP endpoint
16. `get_fire_weather_environment(location)` — fuel drought severity
17. `get_drought_conditions(location)` — NOAA US Drought Monitor D0–D4 county + statewide percentages
18. `get_seasonal_outlook(location)` — 16-day extended forecast (weekly summaries) + CPC 30-day narrative
19. `compare_model_forecasts(location, days)` — GFS vs ECMWF IFS vs ECMWF AIFS vs GEM vs ICON with spread/confidence analysis

**HTTP server (added 2026-05-09):** `localhost:3456`
- `GET /health` — status check
- `GET /windninja?lat&lon&speed&dir&radius&veg` — terrain wind grid for HTML map layer

**Key technical lessons:**
- Claude Desktop Store app config: `C:\Users\aphil\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
- NWPS bbox API does not work — use NWS riv_gauges MapServer with distance query instead
- SPC text product at `spc.noaa.gov/products/outlook/day{N}otlk.txt` is far richer than MapServer attributes
- Geocoding: `geocoding-api.open-meteo.com/v1/search` — free, no key, returns lat/lon from city name
- aviationweather.gov JSON API uses short field names (`fltcat`, `wspd`, `wdir`, etc.) — not the old XML/ADDS field names

You are in charge of the pace. There is no deadline. The MCP doesn't need to exist tomorrow, next week, or next month. It just needs to exist *eventually*, and when it does, every Claude conversation you have gains weather superpowers — including terrain-resolved fire weather winds that no public API can provide.

---

## Future idea — Chat panel in StormWatch Live

Discussed 2026-05-08. Two options recorded for a future session:

**Option A — Chat built into the HTML app (simpler, start here)**
Add a chat panel to `weather-alerts.html`. The app gathers its currently loaded alert/weather data, sends it + the user's question to the Claude API, displays the response. Requires an Anthropic API key stored in the HTML file (acceptable for personal local use). Does not require the MCP server. Fast to build.

**Option B — HTML app talks to MCP server over HTTP (more powerful)**
Extend the MCP server to also run a local HTTP server (e.g. `localhost:3456`). The chat panel POSTs questions there. The server calls weather tools + Claude API and returns answers. API key lives server-side (more secure). Allows the chat to use tools the HTML doesn't have (HRRR point queries, WindNinja, etc.). MCP server must be running for chat to work.

**Recommendation when ready:** Start with Option A to get chat working quickly. Upgrade to Option B later when more MCP tools exist and the added power is worth the complexity.
