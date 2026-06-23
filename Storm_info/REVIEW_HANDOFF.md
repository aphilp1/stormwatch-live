# Fire Winds — full review handoff (for Claude Web / Opus)

**HEAD to review:** `origin/master` @ `23d6d6a`. Verify against the **committed** files,
never a local cache. Claude Code (on the Windows machine) can run WindNinja and pull HRRR;
this sandbox cannot — flag re-runs back to Claude Code.

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
1. **Four-way scoring** (119 scorable stns, obs>=5 AND bc/obs<=3): WN10m best 39, HRRR10m 33,
   WN850 26, HRRR850 21; WN10m beats WN850 73/119, beats raw HRRR10m 65/119. Recompute from
   raw fields and confirm the exclusion rule.
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
- labor_day_or2020: 29/34 stations valued (5 far outliers across ~200 mi, beyond the domains).
- tubbs_2017: WN not run (direction-mismatch HOLD); HGT/BC present.
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
