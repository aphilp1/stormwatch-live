# Fire Winds — full review handoff (for Claude Web / Opus)

**HEAD to review:** the latest `origin/master` — run `git log -1` (or read the newest commit
on GitHub). This handoff is always committed as the repo tip, so reviewing the newest commit
guarantees you see the state described here. (Pinning an exact hash here is self-invalidating:
committing this doc creates a newer HEAD than any hash written in it.) Verify against the
**committed** files, never a local cache. Claude Code (on the Windows machine) can run
WindNinja and pull HRRR; this sandbox cannot — flag re-runs back to Claude Code.

## Latest session — 2026-06-24 (read first; TRAJECTORY SCORING added — Camp Fire only)
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
