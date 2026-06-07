# StormWatch — All Next Steps Handoff
> **RESUME COMMAND:** When the user types "resume", start Track 1 (Tubbs → Kincade → Labor Day OR), then Track 2 (RRFS), then Track 3 (do-no-harm gate). Raise the Tubbs direction-mismatch decision before building any rows.
**Date recorded:** 2026-06-07  
**Pipeline state:** Two-level BC correction architecture validated end-to-end (commit 3f5b0af).  
**Database:** 166 station-events across 12 events in `hrrr_error_dataset.csv`.

---

## What Has Been Validated (do not re-litigate)

- **Phase A COMPLETE:** Offshore-vs-continental regime signal confirmed. Offshore underbias = −6.89 mph at coupled stations. Terrain/mixing mechanism supported.
- **Outer trainer SIGNAL:** LOEO RMSE 10.54 vs 21.08 baseline. Features: [w700, mslp_grad, hrrr_coupling_frac].
- **Inner threshold rule:** 80.9% accuracy, zero terrain-arm false positives. Rule: `(relief > 330m AND slope > 10%) OR (coupling_ratio > 1.08)`.
- **Two-level architecture VALIDATED end-to-end (commit 3f5b0af):** WMSC1/thomas: flat err=−32.1 → two-level err=+10.5 mph. Architecture correctly flips the one sign disagreement.
- **Phase B magnitude calibration FAIL (commit e397939):** station_deficit is not a reliable UP-correction magnitude predictor. Two-level event-magnitude is the validated ceiling.
- **WRCC + Synoptic validation COMPLETE:** All tested stations EXACT. Database obs-side confirmed sound.
- **CUUC1/woolsey_2018 added (commit 2b0e81a):** Above-inversion station (5280 ft). obs NNE, bc/HRRR ESE both events — consistent above-Santa-Ana-inversion behavior. Not yet in Phase B N=68 (NEEDS_DEM).

**Permanently parked:** Single-station and multi-station BC corrections (both falsified). Do not re-run Camp Fire to chase a pass.

---

## Track 1 — More Hindcast Events (Testing Track — user's stated direction)

**Why:** The outer trainer has 3 failure folds (boulder_chin, kincade_run, woolsey) where the event delta ≈ 0 (bc ≈ obs, coupled BL). More events, especially active Santa Ana runs, give the trainer more training examples and reduce over-correction at near-zero events.

**Priority order:**
1. **Tubbs 2017 destructive run (Oct 9, 2017)** — large Diablo event, strong underbias expected. Blocked on: (a) Hawkeye (HWKC1) sustained obs from RAWS, (b) local 700 hPa sounding reference (OAK IEM returns CWMJ alias — use Wyoming wsgi). See station registry for details. **Pre-start decision required: decide whether to clear the Tubbs direction mismatch first or run with known caveat — see Track 5.**
2. **Kincade 2019 destructive run (Oct 27, 2019)** — `era5_pl_kincade_run_2019.nc` is MISSING (not yet pulled). Same domain as kincade_2019. Downward-propagating Diablo at 850 hPa by 12Z Oct 27. Pull ERA5 then run alignment.
3. **Labor Day Oregon 2020** — 35 active stations, Downslope_Oregon regime (mean +1.71 mph, opposite sign from CA). Validates that outer trainer generalizes across regime sign. Pull RAWS via Synoptic API (same pattern as `wrcc_synoptic_pull.py`, NWS WRH token).

**Conventions:**
- RAWS pulls: NWS WRH token `7c76618b66c74aee913bdbae4b448bdd` + `Referer: https://www.weather.gov/wrh/timeseries?site=STID` header
- BC level: 700 hPa for continental/frontal; 850 hPa for offshore/Santa Ana (see bc_level rule §2.4)
- Use `wyoming_soundings.json` as canonical sounding source — never IEM (CWMJ alias bug)
- Time-align bc per station at its own peak hour, not event-median

---

## Track 2 — RRFS Resolution Ladder

**Question:** Does the offshore ridge underbias shrink monotonically as resolution increases (3km → 1.5km → sub-100m WN)?  
**This is a new data point alongside the database — does NOT modify `hrrr_error_dataset.csv`.**

### Resolution ladder target:
```
HRRR 3km  →  RRFS 3km  →  RRFS 1.5km nest  →  WindNinja (sub-100m)  →  RAWS obs
```

### Events and anchor stations:

| Event | Anchor | Station-aligned peak hour |
|---|---|---|
| camp_2018 | CBXC1 | Nov 8 2018 ~12Z |
| thomas_2017 | WMSC1 | Dec 7 2017 ~03Z |
| woolsey_2018 | WMSC1 | Nov 9 2018 ~05Z |

WMSC1 in two events = key consistency test.

### Phase 0 — Build (start independent of everything else)
- Clone and build **UFS Short-Range Weather App (RRFSv1 release)** on target system.
- Confirm build completes and workflow runs on bundled test case before touching event data.
- Report: build success, SRW version/tag.
- This is the long pole. Start immediately; does not wait on event selection.

### Phase 1 — Initial / Boundary Conditions per event
- Source: GFS/GDAS analysis from NOAA archive on AWS (matches RRFSv1's operational LBC source; covers 2017–2018).
- Pull analysis at cycles bracketing each station's peak window.
- Report coverage per event before configuring.

### Phase 2 — Domain / Nest Configuration
- Regional **3km** SRW domain over each event's station footprint.
- **1.5km nest** covering the anchor station and surrounding coupled/exposed stations.
- **Show proposed nest box for approval before running** (same approval step as DEM domains).
- RRFSv1 physics suite, identical across all three events.
- Hourly output covering peak windows.

### Phase 3 — Extraction Harness (write now, runs post-model)
- Read 3km and 1.5km output; extract 10m u/v at each target station's lat/lon and aligned peak hour.
- **Conventions (must match departure-database pipeline):**
  - `vec_avg` — u/v mean then atan2, never average raw degrees
  - Meteorological FROM-direction
  - mph = m/s × 2.23694
- Write `rrfs_hindcast.csv`, keyed stid + event_id + resolution:
  - columns: `rrfs3km_speed`, `rrfs3km_dir`, `rrfs15km_speed`, `rrfs15km_dir`, `rrfs3km_err`, `rrfs15km_err`
- **New file. Do NOT edit `hrrr_error_dataset.csv`.**

### Phase 4 — RUN
- Blocked on compute decision (cloud HPC vs institutional cluster).
- All of Phases 0–3 complete independently. Only this step waits.

### Integration output (one table per anchor):

| | obs | HRRR_err | rrfs3km_err | rrfs15km_err | wn_err |
|---|---|---|---|---|---|
| CBXC1 / camp | | | | | |
| WMSC1 / thomas | | | | | |
| WMSC1 / woolsey | | | | | |

**Interpretation flag:** The 3km RRFS rung will likely resemble HRRR — that is a result, not a problem. It isolates whether FV3 physics alone changes anything. The 1.5km rung is the resolution hypothesis test. If error drops meaningfully only at 1.5km and below, that confirms the miss is resolution-driven and quantifies what resolution alone buys before WindNinja.

---

## Track 3 — Deferred from Claude Desktop (explicitly deferred — return here when ready)

User said: "I do want to do more testing, and then come back to these other suggestions from Claude Desktop."

1. **Do-no-harm gate:** Suppress BC correction when raw WN is already within ±5 mph of obs. Prevents degrading stations that WN already recovers. Pre-condition before any app deployment.
2. **Deploy with disclosed uncertainty band:** StormWatch Live integration. Show ± band from outer trainer RMSE.
3. **WN amplification lookup (optional):** Per-station terrain amplification factor for better UP-correction magnitude calibration. Requires full per-station WN sweep — only worthwhile after more events are in the trainer.

---

## Track 4 — DEM Work (unblocks CUUC1 and woolsey stations in Phase B)

Several stations have `NEEDS_DEM` for slope/aspect/relief_1km and thus cannot enter the Phase B N=68 analysis:
- CUUC1 (both thomas and woolsey)
- All 16 woolsey_2018 stations (including WMSC1)
- Many others across events

Once DEM features are filled in:
- CUUC1/woolsey enters `flow_coupling_draft.csv` → enters Phase B N=68 set
- WMSC1 terrain_class confirmed at corrected elevation (3779.5 ft, not 4930 ft)
- `repr_error_flag` can be set for all NEEDS_DEM stations

DEM source: same pipeline as existing dem_verified stations. Use UTM projection at 90m for WindNinja compatibility.

---

## Track 5 — Withheld Findings (do not cite until resolved)

- **Tubbs Fire:** Withheld pending (a) Hawkeye HWKC1 sustained obs from RAWS, (b) local 700 hPa OAK sounding from Wyoming (not IEM). Inversion and coordinate findings are solid; wind obs not yet closed.
- **Thomas Fire direction mismatch:** bc direction 43–94° off from observed NNE. Root cause not yet diagnosed. (Note: CUUC1 above-inversion behavior is now characterized but does not explain the WMSC1 mismatch — WMSC1 is intermediate elevation, not above-inversion.)

---

## Environment / Critical Gotchas

- **conda:** `C:\Users\aphil\miniforge3\Scripts\conda.exe` — NOT in PATH; use full path
- **Run from:** `C:\Users\aphil\Documents\Stormwatch\Storm_info`
- **ERA5 files:** `C:\Users\aphil\Documents\Stormwatch\era5\` (NOT in Storm_info/era5/)
- **ERA5 missing:** `era5_pl_kincade_run_2019.nc` and `era5_sl_kincade_run_2019.nc` — not yet pulled
- **Synoptic token:** NWS WRH public `7c76618b66c74aee913bdbae4b448bdd` + weather.gov Referer. Personal Synoptic token = 403 on historical data.
- **IEM sounding alias bug (DO NOT USE IEM):** IEM silently returns Canadian station CWMJ for any missing Western US station. Use `wyoming_soundings.json` (Wyoming wsgi src=FM35) exclusively.
- **Credentials:** `~/.cdsapirc` and `~/.ecmwfapirc` are gitignored. Repo is PUBLIC. Never commit SYNOPTIC_TOKEN or credentials.
- **Herbie HRRR cache:** `C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_bc_cache\`
- **WindNinja:** `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe`; cache at `C:\temp\windninja_cache`
- **vec_avg always:** Never average raw wind directions. Always u/v → atan2.
- **bc_speed in DB vs aligned:** `hrrr_error_dataset.csv` bc_speed = event-median pull. `time_aligned_bc.csv` bc_speed_aligned = station's own peak hour. Phase B analyses use the aligned values.
- **Do not overwrite `hrrr_error_dataset.csv` with `flow_coupling_draft.csv`** — they serve different purposes.

---

## Latest Commits (as of 2026-06-07)

```
e945ad0  Add WRCC reference data and Synoptic raws_obs CSVs
2b0e81a  Add CUUC1/woolsey_2018 to departure database and time_aligned_bc.csv
cb198d5  Add wrcc_synoptic_pull.py: Synoptic API substitute for WRCC second pull
c8a064a  Add wrcc_validate.py: WRCC cross-validation script
e397939  Phase B Step 1-3: station-magnitude gate + WN battery (FAIL)
3f5b0af  two_level_wn_test.py: two-level architecture end-to-end validation (PASS)
0fabff7  threshold_rule_test.py: inner rule 80.9% accuracy
127d862  Station separation check: GATE PASS 71% Thomas
```
