# CLAUDE CODE RESTART — Current Next Steps & Session Handoff

**Read order on restart:** THIS file → `STORMWATCH_MASTER_STATUS.md` (authoritative findings
ledger) → `stormwatch_test_protocol.md` (method). Update this file whenever work lands.

**Last updated:** 2026-06-25 · latest commit: (see below)

---

## ✅ RESOLVED — Agents "broke" was a stale-port issue, not code (2026-06-26)

**Outcome:** Agents tab works on the correct port (:8001). User confirmed Combined Threat **Area**
mode drew a box over MT and returned a valid 5-sample-point panel; reported "things are working."
**Root cause = the page was loaded from the dead :8000 server** (shut down the night before), so all
agent fetch() calls failed silently while the cached page still rendered. NOT a code regression.

**LESSON: check the browser is on the live port (:8001) BEFORE diagnosing any layer/agent as broken.**

**Latent (not breaking):** point-mode dispatch is duplicated across ~4 `map.on('click')` handlers
(lines ~2469-2473, 2651-2652, 3631-3632, 3742-3743) — fine to consolidate someday, but not the cause.

<details><summary>Original 2026-06-25 diagnosis (kept for reference)</summary>

**User report:** Nowcast/Fire/Flood agent **point + area** clicks not working.

**Diagnosis (2026-06-25):**
- **Backend is HEALTHY** — not the cause. Live tests on localhost:3456: `/health` 200,
  `/fire-agent?lat=34.05&lon=-118.25` returns valid JSON (riskScore 3 MODERATE),
  `/flood-agent?lat=29.76&lon=-95.36` returns valid JSON (15 gauges). MCP server is fine.
- **Regression is in the FRONTEND** (`weather-alerts.html`), in the map-click routing.
- **PRIME SUSPECT: duplicated/competing `map.on('click')` handlers.** The point-mode dispatch
  (`if (fireMode && fireInputMode==='point') runFireAgent(...)`) is copy-pasted in FOUR places:
  lines ~2469-2473, ~2651-2652, ~3631-3632, ~3742-3743. Multiple click handlers + the newer
  alert/dot handlers likely intercept or `return` early before the agent dispatch runs, or
  double-fire. Area (box) handlers: `fwOnMouseDown`/`flOnMouseDown` (~6658/6680),
  `setFireInputMode`/`setFloodInputMode` (~6645/6680) — verify a newer `map.on('mousedown')`
  (dot drag / box draw) isn't shadowing them.
- **NEXT STEP tomorrow:** open the page on :8001, open DevTools console, click in Fire point mode,
  watch for which handler fires / any error. Consolidate the 4 duplicate click dispatchers into ONE
  ordered handler so agent point-mode isn't pre-empted. Add a regression guard.

**If not figured out quickly: REMIND THE USER** (their explicit request).

</details>

---

## ONE-LINE STATE

**StormWatch Live is PUBLISHED to the public web (2026-06-27): https://aphilp1.github.io/stormwatch-live/**
**— GitHub Pages, MIT licensed, README in .md/.html/.pdf. Public visitors get the full map + Fire**
**Winds hindcasts (incl. new trajectory popup chart); the 7 localhost-only features (4 agents,**
**WindNinja, HMS smoke, AirNow) are gracefully gated via MCP_LOCAL. Local :8001 unchanged.**
**Remaining major areas: Chat Panel, MCP bug fixes; optional phase-2 = cloud backend so agents work publicly.**

### Session 2026-06-27 shipped (all committed + pushed, HEAD 1df115d)
- Fire Winds station popup: hourly **trajectory chart** + timing metrics (f3bc481)
- **Published to GitHub Pages** w/ public-mode graceful degradation (da9e793); `index.html` redirect
- **MIT LICENSE** added, GitHub-detected (0d74f56)
- README generated to **.html + .pdf** (regenerate from .md whenever it changes)
- Removed `_memory_backup/` from repo (private notes, kept local; 496f269)
- User's own commit 11be779 removed the Outlook tab from the web app

---

## HOW TO RESUME

When user types "resume," present the full StormWatch Live v1.0 picture:

> **StormWatch Live — where we are (as of 2026-06-19):**
>
> **BUILT AND STABLE**
> - Core weather map (alerts, layers, USGS Topo + 30m Hillshade, radar, NSSL CAMs viewer)
> - Alert polygon click → dark detail popup (fromMap flag, no tab hijack)
> - NSSL Verification Overlays — LSR Reports + NWS Warnings mini-map on Maps tab, time-filtered ±3 h
> - MCP server — 19 tools, live (known bugs, lower priority)
> - HindC tab — WindNinja hindcast series, 12 events, audit-clean (Claude Web 7/7 checks pass)
> - GitHub — public repo, version history, Claude Web access
>
> **NOT YET BUILT (v1.0 remaining major pieces)**
> - Chat Panel — in-app MCP chat so you can ask weather questions without leaving StormWatch
> - Forecasting Agents — click a point on the map → Claude synthesizes a full briefing
>
> **BUILT THIS SESSION (2026-06-19)**
> - Alert polygon click → dark detail popup (no sidebar tab hijack)
> - USGS Topo (3DEP) + 30m Hillshade as base map options
> - NSSL Verification Overlays — LSR Reports + NWS Warnings mini-map on Maps tab, time-filtered ±3 h
>
> **LOWER PRIORITY (can do anytime)**
> - MCP bug fixes: BUG-007, 012, 013, 016, 021 + cosmetics
> - HindC WN runs: 8 events still In Progress (Kincade, Labor Day OR, Marshall, etc.)
> - Tubbs direction mismatch decision
>
> What would you like to work on?

---

## WHAT IS DONE — DO NOT REDO

### HindC Tab v1.0 + Popup Overhaul (complete 2026-06-17)

**Commits: 439677c → e93f4ca (latest)**

**Tab v1.0 (earlier same day):**
- Tab renamed EXPTS → HindC; 4 finding chips; challenge text; WN framing fixed
- Four logic fixes: chart anchor-vs-mean, Finding 3 bc/obs conditioned, convective regime,
  Kincade Ignition +4.13 mph

**Evening session popup overhaul:**
- **SLEC1 reframe:** bc/obs=0.96, WN/obs=1.128 (+4.5 overshoot) — boundary case NOT a win.
  CBXC1 (bc/obs=1.135, WN/obs=1.007) is the clean niche. Finding 3 rewritten accordingly.
- **4-bar popup:** Camp Fire CBXC1/SLEC1 now show obs/HRRR/BC input/WN output (amber).
  WN output stored in `wn_stations` object in EXPT_EVENTS. All other events: 3-bar.
- **Three popup flags:**
  1. obs < 5 mph → suppress direction + "calm/sheltered — do-no-harm" error label (grey)
  2. bc/obs > 3 → orange ⚠ banner "BC much stronger; do-no-harm gate required"
  3. Near-calm: error value color grey, not directional
- **SLEC1 HRRR ratio:** 0.525 (stale) → 0.477 everywhere (CSV authoritative: 16.7/34.99)
- **Documents:** HINDC_REVIEW.md fully updated + SESSION_REVIEW_2026-06-17.md created

**Review documents for Claude Web:**
- `Storm_info/HINDC_REVIEW.md` — findings + narratives
- `Storm_info/SESSION_REVIEW_2026-06-17.md` — session changes + 6 audit check items
  URL: https://raw.githubusercontent.com/aphilp1/stormwatch-live/master/Storm_info/SESSION_REVIEW_2026-06-17.md

### Database (all complete)
- `hrrr_error_dataset.csv`: 318 rows, 164 active (KEEP/CAUTION)
- All BC columns: bc_speed, bc_dir, bc_level populated; 850 hPa offshore, 700 hPa continental
- All DEM columns: slope, aspect, relief_1km, repr_error_flag, terrain_class
- Phase B terrain gate: FAILED (ratio=0.013) — terrain class does NOT predict error
- Regime signal: offshore mean −3.9 mph, continental +0.5 mph, Δ=4.4 mph (SOLID)
- Two-level BC architecture: validated at 4 anchors; direction solved, magnitude bounded
- Camp Fire held-out test: WN+rawBC IS the product at exposed ridges with bc/obs ≤ ~1

### Scripts written
- `donoharm_gate.py`, `rrfs_extract.py`, `fetch_cuuc1_dem.py`, `merge_all_remaining_dem.py`
- `two_level_wn_test.py`, `bc_outer_trainer.py`, `merge_dem_and_gate.py`

---

## NEXT ACTIONS

### Priority 1 — MCP bug fixes (no data needed, pure code)
BUG-007 (briefing fires for non-US), BUG-012 (marine accepts inland),
BUG-013 (air quality accepts ocean), BUG-016 (alert formatting), BUG-021 (duplicate alerts)
Plus cosmetics: BUG-006, 014, 015, 018, 019, 020, 022–024

### Priority 2 — WN runs on 8 In Progress events
Kincade Ignition, Kincade Run Day, Labor Day OR, Marshall Fire, Boulder Chinook,
Missoula Dec 2025, Missoula Jul 2024
(Iowa Derecho = Control Case — flat terrain, no WN needed)

### Priority 3 — Tubbs direction mismatch (decision needed)
25–44° ENE structural offset at inland stations — withheld.
Decide: run WN with known caveat, or resolve direction first.

### Blocked
- RRFS resolution ladder: needs NOAA RDHPCS sponsor (rrfs_extract.py ready)
- ERA5 cross-check: needs Copernicus CDS registration (~/.cdsapirc)

---

## CONVENTIONS — DO NOT DRIFT

- `vec_avg`: mean u/v components THEN atan2. NEVER average raw degrees.
- Direction: meteorological FROM (0=N, 90=E, 180=S, 270=W)
- Speed: mph = m/s × 2.23694
- Slope: stored in DEGREES in hrrr_error_dataset.csv (NOT percent)
- BC level: 850 hPa offshore/Santa Ana; 700 hPa continental (see §2.4)
- Soundings: Wyoming wsgi (src=FM35) only. NEVER IEM (CWMJ alias bug)
- Synoptic token: NWS WRH public `7c76618b66c74aee913bdbae4b448bdd` + correct Referer header
- Security: `~/.cdsapirc` and `~/.ecmwfapirc` gitignored. Repo is PUBLIC. No credentials in code.
- WN framing: NEVER say "WN beats HRRR." Two comparisons only: HRRR vs. station obs,
  and WN hindcast vs. station obs.

---

## ENVIRONMENT

```powershell
# hrrr311 env (primary):
$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\hrrr311"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"
& "$CONDA_ENV\python.exe" <script.py>

# dem env (DEM fetching only):
conda run -n dem python <script.py>

# WindNinja CLI:
C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe

# StormWatch Live dev server (run from Stormwatch folder):
python -m http.server 8080
# then: http://localhost:8080/weather-alerts.html
```

---

## KEY FILES

| File | Purpose |
|------|---------|
| `hrrr_error_dataset.csv` | Main DB — 164 active rows, all columns complete |
| `HINDC_REVIEW.md` | Clean narrative extract for Claude Web review |
| `STORMWATCH_MASTER_STATUS.md` | Full findings ledger (authoritative) |
| `stormwatch_test_protocol.md` | Method + pre-registration rules |
| `hindcast_event_library.md` | All 12 events, dates, anchor stations |
| `two_level_wn_test.py` | WN battery — 4 anchors |
| `donoharm_gate.py` | Gate function + test harness |
| `rrfs_extract.py` | RRFS GRIB2 extraction (HPC-blocked) |
| `wyoming_soundings.json` | Canonical sounding values — READ only |

---

## WITHHELD / PARKED (do not cite, do not revive)

- **Tubbs direction:** WISC1/KNXC1 carry 25–44° ENE structural offset. Withheld.
- **WMSC1 Thomas elevation:** Registry 4930 ft, DEM ~3750 ft → sub-inversion; excluded from niche.
- **Single-station BC correction:** Falsified. Do not re-run.
- **Multi-station BC correction:** Falsified. Do not re-run.
- **Camp Fire corrBC:** CBXC1 ratio 0.830, SLEC1 ratio 0.717 — correction DEGRADES. Do not re-run.

---

*Authoritative findings: STORMWATCH_MASTER_STATUS.md*
*HindC review doc: HINDC_REVIEW.md*
*Memory index: C:\Users\aphil\.claude\projects\C--Users-aphil\memory\MEMORY.md*
