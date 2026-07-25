# Fire Winds — full review handoff (for Claude Web / Opus)

**HEAD to review:** the latest `origin/master` — run `git log -1` (or read the newest commit
on GitHub). This handoff is always committed as the repo tip, so reviewing the newest commit
guarantees you see the state described here. (Pinning an exact hash here is self-invalidating:
committing this doc creates a newer HEAD than any hash written in it.) Verify against the
**committed** files, never a local cache. Claude Code (on the Windows machine) can run
WindNinja and pull HRRR; this sandbox cannot — flag re-runs back to Claude Code.

## Latest session — 2026-07-25: NIFC/ArcGIS 429 quota outage made honest + auto-retry
User report: "Fresh Perimeters (72 h)" showed nothing on the live site. Root cause is
EXTERNAL: NIFC's ArcGIS Online org is exceeding its shared request-unit quota
(57,600 units/min, all public consumers nationwide — peak fire season); the service
returns `{"error":{"code":429,…}}` **inside an HTTP 200 body**, so `fetchJson` resolved
fine and the layer read the missing `features` as "none in last 72 h" (silent-fake — and
`dailyPerimLoaded=true` meant re-toggling never refetched). Fixes in `weather-alerts.html`:
(1) `fetchJson` now throws on an ArcGIS error body (`/arcgis/i` URLs only) so every
NIFC/WFIGS layer fails honestly ("unavailable") instead of drawing nothing;
(2) `loadDailyPerims` detects ArcGIS 429 → note "NIFC busy — retry n/5 in 70 s", auto-retries
up to 5× (quota resets each minute), resets counter on success, and no longer latches the
loaded flag on failure so re-toggling retries. Browser-verified on :8001 (real click →
honest note + 70 s retries observed in console). NOTE: 6-h health monitor's daily-perims
probe is a 1-record no-geometry query — too cheap to trip the quota, so it passed at
14:06 UTC during the same outage; and **NTFY_TOPIC secret is still unset** (workflow log
shows empty), so no alert could have reached the user — user action still pending.

## Previous session — 2026-07-19: badge scrub + MCP bug backlog closed · PROJECT PARKED
Project parked for a while per user; resume anchor = `PICKUP_TOMORROW.md` (repo root, local).
(1) Fire Winds badge scrub (`7697325`): last two "niche" badges relabeled per the 2026-06-22
niche re-quote directive — camp_2018 → "WN Corrects", kincade_ign_2019 → "WN edge" (matching
each event's status class taxonomy). Browser-verified on :8001 before push.
(2) MCP server bug backlog CLOSED (`5b0aeb0`, `mcp-server/index.js`): all remaining
2026-05-28 QA-sweep bugs fixed — US-coverage gate (CONUS/AK/HI/PR/VI/GU) on the three
briefing tools + drought; geocoder honors explicit country suffixes and PR/VI/GU territory
codes, and fails honestly on wrong-state matches instead of returning a same-named town
elsewhere; marine inland guard; all-hazards severity taxonomy unified + duplicate line
removed; river summary Unknown-gauge noise collapsed; friendly validation (no raw Zod JSON);
assorted cosmetics (10-yr range label, rain-recency grammar, County dedupe, source labels,
AirNow-vs-model note). Verified by driving the real server over stdio: 17/17 bug repros +
8/8 geocoder regressions pass. Sandbox note: re-verification requires Claude Code (spawns
the node MCP server locally).

## Previous session — 2026-07-18 (later): cloud backend live · probe card redesign · diagnostics
(1) Cloudflare Worker (`stormwatch-cloud/`) deployed to
https://stormwatch.stormwatch-live.workers.dev — /health + /fire-agent verified byte-equivalent
to the local :3456 backend; root URL now serves a friendly landing page. Public site NOT yet
wired to it (user holding as a plan; wire with graceful fallback when approved).
(2) Fire Risk probe redesigned per user feedback: Leaflet popup → fixed draggable dark card
top-right of the map (reuses makeDraggable; close button; orange ring marker at the probed
point), fonts enlarged + contrast raised (`acbcf80`). Verified: card clear of zoom control,
drag/close/reopen, live Red Flag row, no console errors.
(3) NEW diagnostics stack: `diagnostics.html` — 33 grouped live service checks (every endpoint
the app uses: NWS, NIFC/WFIGS, PSP, USGS fire+water, IEM, RainViewer, FEMA, Mesonet, CDNs,
Worker, local :3456 when local) with latency, problems filter, summary banner;
`health_monitor.py` (stdlib-only, 20 checks, ntfy push on down/recover transitions) +
`health-monitor.yml` Action every 6 h committing `data/health_status.json`, which the page
displays as "last automated check-in". NWS gotcha: /alerts/active rejects `limit` (400) —
use /alerts/active/count as the probe.

## Previous session — 2026-07-18: Fire Risk at a Point (spec 05) applied + live (`877a539`)
Applied `Storm_info/fable_specs/05_fire_risk_part2.md` to `weather-alerts.html` (+262 lines,
additive). New Wildland Fire toggle "Fire Risk at a Point": while on, a transparent
click-catcher rectangle in a dedicated pane (z620, above firePerimPane 460/marker canvases
450, below tooltips/popups) captures every map click → dark popup card with four
government-sourced sections: USGS fire danger (WFPI value+band chip via WMS GetFeatureInfo,
large-fire %, spread %), NIFC PSP Day-1 (significant fire potential + fuel dryness +
GACC/PSA/valid date), Red Flag/Fire Wx Watch containment (client-side ptInGeom, zero
network), and nearest active NIFC wildfire ≤100 mi (haversine + compass). No composite
score — values verbatim per source (hard user rule). Agent point-modes keep priority via
the same forwarding block as alert polygons. All endpoints public-CORS → works identically
on Pages, no MCP_LOCAL gating. **Spec bug found during browser verify:** WFSP serves water
mask as ×1 code (254) unlike WLFP's ×10 (2540) → "spreads: 254%" leaked at Lake Tahoe;
both probability rows now guard `GRAY_INDEX < 248` (genuine percentages ≤100). Verified
end-to-end on :8001: clean console, live cards (SW Idaho WFPI 79; live Oregon Red Flag
Warning probe w/ until-time; ocean + Tahoe empty/mask states), stale-guard on rapid
clicks, toggle-off restores alert-card clicks (regression check passed), alerts layer
still on by default. Deploy verified live on Pages via curl marker.

## Previous session — 2026-07-08 (later): Snapshot REBUILT after user feedback (`5ceb542`)
User rejected the first Clip·Zip·Ship output ("greatly improve; better layer info, basic
cartographic info"). Root causes found by generating + opening the real .html end-to-end:
modern-screenshot mangles Leaflet pane transforms (tiles missing, polygons misplaced);
dom-to-image-more is correct but 60–90 s (45 s+ even on a tiny control — unusable per-call
in this page). **Replaced with a purpose-built compositor** in `snapComposite()`: tile
<img>s CORS-refetched from HTTP cache → ImageBitmap, marker <canvas>es drawn directly,
vector panes serialized whole via XMLSerializer; scale bar (1/2/5×10ⁿ at center lat),
north arrow, attribution drawn natively on the canvas. **0.5 s capture measured** (was 90).
dom-to-image kept only as last-resort fallback; modern-screenshot CDN tag removed; HTML/
divIcon markers are NOT drawn (all current marker layers are canvas/SVG — noted in code).
Export card upgraded: cartography block (center, ≈1:N scale + zoom, view width, S–N/W–E
extent, basemap, Web Mercator, local+UTC), Active Layers with live status notes, Map Keys
reproducing every enabled layer's legend (incl. NWS alert types; keys no longer dropped
when the Layers tab is hidden — filter is the key's own inline display, not offsetParent),
severity-dotted alert stat tiles, chip label/value join fix; PDF carries the same info.
Verified: real .html opened at zoom-7 fire view — map correct, Babylon card, 3 legend
groups, layer notes. Note: an app-boot behavior resets the map view when the initial
alert load lands (racing scripted setView) — user-facing impact nil, not investigated.

## Previous session — 2026-07-08: Fire layers + Clip·Zip·Ship snapshot + Montana Mesonet fixes
All in `weather-alerts.html`, pushed through `ba91573`, live on Pages. (1) **New Wildland
Fire layers** (Fable spec 01): "7-Day Fire Potential" — NIFC Predictive Services outlook,
D1–D7 buttons, official dryness fills + CRITICAL/IGNITION risk polygons (simplified geometry
45 MB→0.5 MB/day); "Fresh Perimeters (72 h)" — WFIGS daily IR/GPS shapes, newest per fire,
age-colored, opens the existing perimeter card. **Gotcha fixed post-spec:** live PSP data
carries `isvalid=0` on ALL risk polygons — the official renderer paints risk regardless, so
risk features bypass the isvalid filter (else "no risk areas" forever). (2) **📸 Snapshot /
Clip·Zip·Ship flagship** (Fable spec 04): header button → captures map+layers+open card+wind
readout → branded self-contained offline `.html` + vector-text `.pdf` → Web Share sheet or
download. dom-to-image-more primary, modern-screenshot fallback, jsPDF; ~420 additive lines;
national-view capture takes ~30–60 s (cache-busted tile refetch) — phone-side share still
untested. (3) **Montana Mesonet was dead** ("error"): feed now sends `null` for offline
sensors (87/216 stations) → `.toFixed(null)` crash; all guards now `!= null`. Station card
was ALSO dark-on-dark (built pre-theme-darkening) and overwrote `#det-body` wholesale,
destroying the shared card internals — now renders into `#det-custom` with the panel's
`.dl`/`.dv` classes; `ensureDetStandard()` now restores the zoom button label/handler that
custom cards override. (4) Wind-flow animation slowed (velocityScale 0.005, particleAge 110).
**Ready next:** `Storm_info/fable_specs/05_fire_risk_part2.md` — click-anywhere fire risk
from USGS WFPI GetFeatureInfo + NIFC PSP point query (all endpoints live-verified, no
homemade score), not yet applied. MCP cloud publish still blocked on user's Cloudflare account.

## Previous session — 2026-06-28: WindNinja BC driver switched 850/700 hPa → HRRR 10 m
The long-open question "what should drive WindNinja?" is settled. The gate (the real
`hindcast_wn_runner.py` with offset domains ≥10 km, all 12 events, 125 clean stations)
shows **HRRR 10 m beats the aloft 850/700 hPa driver at every terrain class, and beats raw
HRRR 10 m overall** (mean |err| 7.3 vs 7.7 mph; closest source 72/125 vs 53). Policy locked.

**What was changed (all reversible — backups noted):**
- `set_bc_10m.py`: bc_speed/bc_dir = hrrr_10m, bc_level="10m" on 165 rows of
  `hrrr_error_dataset.csv` (backup `.bak_pre10m`).
- `hindcast_wn_runner.py --all`: re-ran all 12 events. Every `_reality_a_domain.json` +
  `_station_results.json` is now 10 m-driven (backup dir `hindcast_grids_bak_pre10m/`).
- Because the BC *is* 10 m now, the four-way collapses: HRRR10m ≡ HRRR850, WN10m ≡ WN850.
  Per-terrain mean |err|: exposed_ridge 9.8→**8.8** (WN wins), canyon 7.6→**7.4**,
  valley 5.2→**5.0**, open **6.1** tie. Aggregate via `Earth2/aggregate_fourway.py`.
- `weather-alerts.html` (backup `.bak_pre10m_labels`): **minimal label fix only** (user
  choice). The dynamic four-way table headers, station-popup rows, and trajectory legend
  no longer say "aloft/850"; they read "(BC)", with a note that the BC columns now equal
  the 10 m columns. No structural redesign.

**REVIEWER — two known inconsistencies left open (NOT bugs, deferred by user):**
1. The 12 hand-written per-event `narrative`/`note` strings in `weather-alerts.html` still
   describe the **850 method with 850-era numbers** (e.g. Camp: "feeds WindNinja HRRR's 850
   hPa aloft wind… 35.4 mph at CBXC1" — live 10 m run now gives 28.5). The live table/map/
   popups are correct (10 m); only this prose is stale. Rewriting it is the bigger reframe
   the user declined for now.
2. `hrrr_bc_pull.py` still pulls 850/700 hPa. A future BC re-pull would revert bc_level to
   aloft unless that script is pointed at 10 m. Flagged, not yet changed.

This is also the actionable output of the Earth-2 WindNinja-emulator gate — see
`Earth2/GATE_AND_PLAN_AC.md` (emulator = speed-only; its 0.75 mph copy error exceeds WN's
~0.4–1 mph margin over raw HRRR, so only worth building for fast-many-WN use cases).

## Latest session — 2026-06-24 (later): TRAJECTORY SCORING rolled out to ALL 12 events
Committed + pushed (commit `300305e`). Camp was the template (`ac8279a`, below); the same
`trajectory_pull.py` (dem env) → `--trajectory` path now covers all 12 events, **162 stations**.

**§8 recompute, all events:** `verify_trajectory.py --all` → **1296 checks (162 stations × 4
models × 2 metrics) ALL MATCH** — every persisted `rmse`/`peak_offset_h` reproduces from the raw
committed `trajectory.curves`. YOUR TASK: confirm independently against the committed files.

**Additive-only / app untouched:** each `<event>_station_results.json` only gained a `trajectory`
block (every deleted diff line is a prior field gaining a trailing comma; no peak-hour value,
four-way score, or WN value changed). All `_reality_a_domain.json` display fields were reverted,
so the live Fire Winds arrow field is byte-identical.

**KEY RESULT — the Camp "WN inherits its input timing" claim is REFINED, not universal:**
- `wn10m` peak_offset == `hrrr_10m` at **127/162** (78%); `wn850` == `hrrr_bc` at **135/162** (83%).
  (A handful of the mismatches are OUT_OF_DOMAIN labor_day stations where wn is null, not a shift.)
- So WindNinja PRESERVES the input's peak hour ~80% of the time but GENUINELY SHIFTS it (1–11 h)
  at ~20% — concentrated in complex terrain (thomas canyons, woolsey, kincade_ign) and continental
  downslope (e.g. missoula CONM8: input −6 h → WN −1 h, a 5 h reorder). Camp's clean 12/12 was the
  exception, not the rule. Honest statement: timing is *mostly* set by the BC level choice, but
  terrain amplification can reorder near-equal hourly peaks.
- **10 m level still times + shapes better:** median |peak_offset| h10=2 h / wn10=2 h vs hbc=4 h /
  wn850=3 h; `wn10` RMSE < `wn850` RMSE at **128/157** (82%). Consistent with the peak-hour 2×2.
- CHECK FOR US: are the ~20% WN timing-shifts physical (terrain reordering) or artifacts of
  near-calm / window-edge argmax? The ±6 h edge cases flagged for Camp apply across all events.

## Latest session — 2026-06-24 (earlier; TRAJECTORY SCORING added — Camp Fire only)
Committed + pushed to origin/master as commit `ac8279a`.

**What it is:** a new hourly-curve layer that grades *timing*, added ALONGSIDE the peak-hour
pipeline (four_way_scoring + peak values are byte-identical — additive only). Per station, per
model, two metrics vs the obs curve over a window bracketing each station's obs peak (±6 h,
clipped to obs coverage):
- **curve RMSE** = sqrt(mean((model-obs)^2)) over hours where both exist (pairwise drop nulls) — shape fit.
- **peak_offset_h** = argmax(model) − argmax(obs) on the 1-hour grid — timing (+late / −early / 0).

Five sources, all hourly: `obs`, `hrrr_10m`, `hrrr_bc` (850/700 aloft), `wn10m` (WN from 10m),
`wn850` (WN from aloft). HRRR = f00 analysis at EACH window hour (sfc 10m + prs 850/700), not a
forecast lead. Obs floored to its analysis hour (RAWS report at HH:27).

**Files (Storm_info/):**
- `trajectory_pull.py` (run in the `dem` conda env — hrrr311 is broken) → `<event>_hourly_hrrr.json`
  (per-station window + obs/hrrr_10m/hrrr_bc hourly curves).
- `hindcast_wn_runner.py` `--trajectory` flag → runs WN at each window hour for both inputs
  (integer cache collapses repeats), computes the two metrics, writes the additive `trajectory`
  block into `<event>_station_results.json`.
- `verify_trajectory.py` → the §8 independent recompute.

**YOUR §8 VERIFICATION TASK (Camp):** From the committed `camp_2018_station_results.json`,
independently recompute `rmse` and `peak_offset_h` for each station straight from the raw
`trajectory.curves` arrays, and confirm they match the persisted `trajectory.rmse` /
`trajectory.peak_offset_h`. Same contract as the four-way recompute — committed files, never a
summary. Claude Code ran `verify_trajectory.py` locally: **96 checks (12 stations × 4 models ×
2 metrics) ALL MATCH.** Confirm independently and flag any mismatch.

**Camp finding to sanity-check:** WindNinja INHERITS its input's peak timing — `wn10m`
peak_offset == `hrrr_10m`, and `wn850` == `hrrr_bc`, at every station (lone exception CDEC1,
where terrain amplification nudged the aloft peak by 1 h). I.e. downscaling sets magnitude, not
*when* the peak lands; timing is a property of the BC level choice, not the solver — the
trajectory analog of "the level was the big lever, not the downscaling." 10m level both times
and shapes better than aloft 850 at most stations. CAVEAT: ±6 h offsets (e.g. PSWC1, CICC1) are
window-width-limited / near-calm edge cases, not necessarily true offsets.

**STILL OPEN:** the other 11 events (rollout pending — Camp is the validated template). Tab
wiring (showing trajectory in Fire Winds) is a separate later step; the live app is untouched.

## Latest session — 2026-06-23 (what changed before the trajectory work)
All four items below are committed + pushed to origin/master.
1. **Tubbs WN run DONE** (commit `741bf9d`) — was on HOLD, now run *with-caveat*. 7 stations.
   WN does NOT beat HRRR here (closest-of-four HRRR10m=3/HRRR850=2/WN10m=1/WN850=1; anchor
   HWKC1 WN_err=-18.6 because BC 28 mph << obs 48). Status stays "HRRR OK". **All 12 events
   now have a WN run.** Direction caveat OPEN: NVHC1/WISC1/KELC1/KNXC1 obs 25-66° more
   northerly than the synoptic BC — speed scoring is direction-independent so it's unaffected.
2. **Station arrow convention fixed** (commit `f02d53a`) — the in-circle obs arrows were drawn
   at the raw FROM bearing while the green field arrows are drawn TOWARD (dir+180), so they
   pointed ~180° opposite even when they agreed. Station arrows now use the same TOWARD
   convention; the popup keeps its "from <compass>" label.
3. **Station arrow redesigned** (commit `0f16d29`) — bold shaft+arrowhead spanning the circle,
   dark casing under a white core so it reads on any circle fill colour.
4. **labor_day full-area display field** (commit `93b874f`) — `DISPLAY_DOMAINS` now accepts a
   LIST of tiles, stitched on a shared grid. labor_day = 3 overlapping 45mi tiles → one
   continuous field 41.9-45.2 lat (10,545 vectors) covering N (Salem) + S clusters, not just
   the central band. Per-station values byte-identical (29/34), four-way unchanged.

## What the tab does now
For each of 12 fire-weather events, score four wind inputs against each RAWS station's
time-aligned peak-hour observation: **HRRR 10m**, **HRRR {bc_level}** (850 offshore / 700
continental), **WN(10m)** = WindNinja from the 10m wind, **WN(850/700)** = WindNinja from the
aloft wind. Closest-to-obs is marked. Map shows a grid-snapped WindNinja surface field.

## Data to verify (Storm_info/)
- `hindcast_grids/<event>_station_results.json` — per station: obs_sus, hrrr_10m, bc_speed,
  wn_speed_a (=WN850/700), wn_speed_b_10m (=WN10m), wn_err_*, terrain_class, domain, offset.
  Plus `four_way_scoring` block.
- `hindcast_grids/<event>_reality_a_domain.json` — the display field: `bc` (speed = median
  10m, dir = aloft synoptic mean), `vectors`, stats.
- `hrrr_error_dataset.csv` / `_dem.csv` — bc_speed/bc_dir/bc_level, **bc_level_height_m**
  (HGT of the BC level), hrrr_10m_mph/dir, peak_dt_utc, obs_sus_mph/dir, qc_flag, terrain_class.
- `FOUR_WAY_SCORING_VERIFY.md` — per-station |error| recompute, ALL MATCH vs persisted.

## Claims to check (and where they could be wrong)
1. **Four-way scoring** — UPDATED 2026-06-23 to include Tubbs (now 12 events). **126 scorable
   stns** (obs>=5 AND bc/obs<=3): closest-of-four **WN10m 40, HRRR10m 36, WN850 27, HRRR850 23**;
   WN10m beats WN850 **77/126**, beats raw HRRR10m **69/126**. (Was 119 scorable before Tubbs
   added 7.) Recompute from raw fields and confirm the exclusion rule.
2. **Niche re-quote** (master status): n=1 by 25% tolerance (CBXC1 +22%); clean coupling win
   (ratio~1.0) is n=0 on the production domain. SLEC1 39.5 NOT reproducible (recorded DEM is
   geographic; WN won't run it). Confirm no "n=2 / NICHE WIN" language survives anywhere.
3. **HGT:bc_level** persisted per station, pulled from the same f00 file/hour as the wind.
   Camp 850 = 1549 m; the high ridges (CBXC1 1825, HMRC1 2048, SLEC1 2025) sit above it.
4. **Field direction** = aloft (BC) synoptic mean, NOT the 10m surface mean (which averaged to
   a bogus easterly for the Iowa derecho). Spot-check a few events' field `bc.dir` vs the
   regime (offshore NE, derecho W, etc.).
5. **Physics cross-tab is UNCONFIRMED** — "station above the BC level -> WN10m wins" did NOT
   hold (above 50% vs below 70%, n only 49/119 joined, join bug). Do not treat as established;
   the HGT values are sound but this hypothesis is open.

## Known limits (not bugs)
- labor_day_or2020: display field now covers the full ~320 km extent (3 stitched tiles), but
  **5 per-station outliers still unvalued** (C5507/OD110/OD140/ODT50 = OUT_OF_DOMAIN ~44.4N;
  TCFO3 = NODATA_AT_POINT). The green field passes over them; their circles have no WN value.
- tubbs_2017: **WN now run (with direction caveat)** — see Latest session #1. Not a HOLD anymore.
- Flat-terrain events (Iowa) show a near-uniform field by physics, not a render bug.
- hrrr311 conda env is broken (numpy); WN runner uses system python; HRRR pulls use the `dem`
  env via `conda run -n dem`.

## Apparatus
- `hindcast_wn_runner.py` — WN runs, four-way scoring, display field (10m speed / aloft dir).
- `hrrr_hgt_pull.py` — HGT:bc_level pull (dem env). `hrrr_bc_pull.py` — bc wind pull.
- `weather-alerts.html` — Fire Winds tab: comparison table, popup, grid-snap field, perimeter.

## What to send back
Per finding: the file + line/station, what's wrong, and whether it needs a re-run (-> Claude
Code) or just an edit. Greying/labels/wording are presentation calls; data provenance and the
scoring/recompute are correctness calls — prioritize those.
