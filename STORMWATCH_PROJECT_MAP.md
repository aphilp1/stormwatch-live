# StormWatch — Project Map (start here)

**This is the front door to the whole project.** It lists every piece, what it does,
where it lives, and where to read more. When something is confusing, come back here.

*Last updated: 2026-07-07. Live commit: 2d6c9d7 · site: HTTP 200 · git in sync (0/0).*

StormWatch has **two halves** that share a folder:

- **Part 1 — The Product:** the weather website people actually use.
- **Part 2 — The Research:** the fire-wind science that powers the "HindC / Fire Winds" tab.

Plus a few **support pieces** (recovery, day-to-day notes) and one **separate project**
(RapidWatch) that is easy to confuse with StormWatch but is NOT part of it.

---

## Part 1 — The Product (the website + its brains)

| Piece | What it is | Where it lives | Status |
|-------|-----------|----------------|--------|
| **The web app** | The whole StormWatch site — one big file (~9,000 lines): maps, alerts, radar, Fire Winds/HindC tab, the agents | `weather-alerts.html` | Live & stable |
| **Public site** | The version anyone on the internet can visit | https://aphilp1.github.io/stormwatch-live/ (GitHub Pages, MIT license) | Live |
| **Local MCP server** | The "brains" on your laptop: 4 agents, WindNinja, smoke, air quality. Talks to Claude Desktop (32 MCP tools) *and* to the app over port **:3456**. Started by Claude Desktop. Full registry + plan: memory `stormwatch-mcp-servers-plan` | `mcp-server/` (`index.js`) | Rebuildable; runs when Claude Desktop is open |
| **Cloud backend** | A copy of the brains that runs in the cloud so the **public** site can use the agents (not just your laptop). Fire agent proven; not deployed (needs a free Cloudflare account) | `stormwatch-cloud/` (Cloudflare Worker) | Proof-of-concept |
| **Alert Trend Monitor** | A robot that checks the national alert feed every 15 min and pings you when something is unusual | `alerts_monitor.py` + a GitHub Action | Built |

**Key idea to remember:** the *public* site can't run your laptop's brains. The 7
localhost-only features (agents, WindNinja, smoke, air quality) quietly switch off for
public visitors via a flag called `MCP_LOCAL`. The **cloud backend** above is how we're
starting to bring those to the public. WindNinja stays laptop-only for now (too heavy).

**Read more:**
- `mcp-server/README.md` — how the local brains are wired.
- `stormwatch-cloud/README.md` — the new cloud piece + how to test/deploy it.
- `ALERT_MONITOR_SYSTEM.md` — the alert robot.
- `FIRE_DATA_CATALOG.md` — verified fire data sources + Fable's ranked "Top 6" additions.
- `README.md` — the public project readme.

---

## The Wildland Fire experience (overhauled 2026-07-05→07, all LIVE)

The flagship. Everything below is on the public site (uses free government feeds, no
laptop needed):

| Layer / feature | What it does |
|---|---|
| **Active Fire Incidents** | Real wildfires only, sized by acreage + colored by containment (red=uncontained → brown=contained); rich click card (personnel, cost, structures, cause) |
| **Fire Perimeters** | Current significant still-burning fires; click → full report (county, cost, cause, discovery/containment dates, mapping method, fire ID). On a dedicated top pane so clicks always work. Turning this on auto-hides the incident dots |
| **VIIRS Fire Hotspots** | Crisp clickable satellite detections, age-colored (<6h/12h/24h); works at every zoom; covers AK + HI |
| **Observed Surface Winds** | Live measured wind arrows from real RAWS stations, colored by speed, pointing downwind |
| **Animated Wind Flow** | Flowing streamlines built by interpolating the observed station winds (CONUS + AK + HI); hover = exact speed/direction readout; on-panel speed color legend |
| **🎯 Fire Watchlist** (added 2026-07-27) | Daily-refreshed ranked list (1-15) of CONUS places where an active fire-weather trigger (Red Flag/SPC/NIFC 7-day potential), dry fuels (USGS WFPI/WLFP/WFSP), and population converge — predicts WHERE a dangerous event is likely, not just where weather is bad. Detail card breaks down trigger/fuels/wind-mechanism per place. Spec + formula: `Storm_info/fable_specs/06_fire_watchlist.md` |

Report cards: dark, readable, dates as **military time + timezone** (e.g. `3/13/2026, 08:14 MDT`).

**Infra:** `.nojekyll` fixed the Pages build failures → deploys land in ~10-15s.

---

## 🧭 Roadmap — the open plan (nothing urgent; all remembered)

1. **Wind-flow animation speed** — studied 2026-07-07: slow winds look too fast because
   leaflet-velocity's pace isn't tied to ground scale/time. Fix path: lower
   `velocityScale` (~0.0075→0.005) + shorter trails first; non-linear speed map
   (wind^~1.3, needs a separate readout grid) for best feel. See memory
   `stormwatch-fire-section`.
2. **Fire Risk — Part 2 (not started).** Click anywhere → fire risk, pulled from
   **authoritative gov fire-danger data** (USGS WFPI + NIFC 7-day potential), NOT a
   homemade score (user's explicit rule).
3. **Fable's Top-6 fire additions** — 7-day fire potential, fresher (IR-flight)
   perimeters, InciWeb links, fire-danger WMS, IMSR + AirNow. Endpoints verified in
   `FIRE_DATA_CATALOG.md`.
4. **MCP servers — 3-layer plan** (see `stormwatch-cloud/` + memory
   `stormwatch-mcp-servers-plan`): (a) preserve/rebuild-from-Git — DONE; (b) run
   reliably locally; (c) **publish** the fetch-and-math agents to a cloud function so
   the PUBLIC site's agents work (POC = `stormwatch-cloud/` Cloudflare Worker, Fire
   agent proven, needs user's free Cloudflare account). WindNinja stays local (heavy).

---

## Part 2 — The Research (the fire-wind science)

The "Fire Winds / HindC" tab isn't a toy — it's backed by real hindcast science:
*HRRR under-forecasts wind at exposed fire-weather ridges; can WindNinja recover it?*

| Piece | What it is | Where |
|-------|-----------|-------|
| **Plain summary** | The science in plain English — read this first | `stormwatch_plain_summary.md` |
| **Authoritative status** | The findings ledger — the single source of truth for results | `Storm_info/STORMWATCH_MASTER_STATUS.md` |
| **Method / rules** | How tests are run (pre-registration, conventions) | `Storm_info/stormwatch_test_protocol.md` |
| **Event library** | All 12 fire-weather events + their stations | `Storm_info/hindcast_event_library.md` |
| **The dataset** | The main results table (164 active rows) | `hrrr_error_dataset.csv` |
| **Case write-ups** | Per-event reconstructions | `reconstruction_case1..7.md` |
| **Scripts** | The Python that builds it all | `two_level_wn_test.py`, `donoharm_gate.py`, and many `*.py` in the root |

**One-line state of the science:** the two-level BC correction *direction* is solved and
validated; the remaining work is *magnitude calibration*. (Details in the status ledger.)

---

## Support pieces (day-to-day)

| File | Purpose |
|------|---------|
| `Storm_info/CLAUDE_CODE_RESTART.md` | Read-first on restart — current next steps |
| `PICKUP_TOMORROW.md` | Where the last session stopped |
| `Storm_info/PENDING_ACTIONS.md` | Open to-dos |
| `Storm_info/REVIEW_HANDOFF.md` | Kept in sync for Claude Web reviews |
| `RECOVERY.md` | "My laptop died" — full rebuild steps (app + brains) |

---

## ⚠️ Not part of StormWatch (don't mix them up)

- **RapidWatch** — a *separate* project (Gulf hurricane rapid-intensification map, its own
  GitHub repo). Different folder: `C:\Users\aphil\Documents\...RapidWatch`. If you see
  "Gulf", "hurricane", "OHC", "Helene/Milton/Katrina" — that's RapidWatch, not this.
- **Earth2 / CorrDiff / BSB lab bench** — separate AI-downscaling research projects.

---

## How the pieces connect (the simple picture)

```
        YOU (laptop)                          THE PUBLIC (internet)
        ────────────                          ────────────────────
  weather-alerts.html  ──▶ mcp-server    aphilp1.github.io/stormwatch-live
   (open on :8001)          (:3456 brains)   (same web app, brains switched off…
                                 │                      …until the cloud backend
                          Claude Desktop                 is live → stormwatch-cloud)
                          (MCP, 32 tools)
```

## Safety rules for this project

- The public repo is public — **no real email / no secrets** in committed files (placeholders only).
- **Don't push** without explicit OK (pushing updates the live public site).
- The local app + local brains and the public site are independent — a change to one need not touch the other.
