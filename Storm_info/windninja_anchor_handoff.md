# WindNinja Anchor Test Handoff

**Date:** 2026-06-07  
**Purpose:** Determine whether WindNinja-on-HRRR recovers the ~−7 mph underbias
at coupled terrain-exposed stations in offshore wind events.  
**Upstream:** phase_a_finding.md — benchmark locked at −6.89 mph (coupled offshore, N=20)

---

## The test in one sentence

Run WindNinja on the HRRR analysis grid at the event peak hour for each anchor event,
extract the modeled wind at the anchor station lat/lon, and compare to RAWS obs truth.
The question is not "does WN match obs" — it is "does WN close the HRRR gap."

---

## Benchmark (from Phase A)

| Stratum | N | HRRR mean err | neg% |
|---|---|---|---|
| coupled, offshore | 20 | **−6.89 mph** | 75% |
| intermediate, offshore | 48 | −4.62 mph | 58% |
| sheltered, offshore | 15 | +3.14 mph | 33% |

The WindNinja benchmark is **−7 mph at coupled ridge stations in offshore events.**
Do not compare against the −3.91 event-level mean — that figure is 2.9× diluted
by composite averaging of ridge + valley stations.

---

## Anchor stations

### Anchor 1 — CBXC1 / camp_2018 (offshore, primary)

| Field | Value |
|---|---|
| Station name | COLBY MOUNTAIN |
| STID | CBXC1 |
| Event | camp_2018 / diablo_offshore |
| Lat / Lon | 40.14564 / −121.5225 |
| Elev (m) | 1830 |
| terrain_class | exposed_ridge |
| flow_coupling | coupled |
| RAWS obs (sus mph) | 28.99 |
| RAWS dir (°) | 69.3 (ENE) |
| HRRR 10m (mph) | 25.37 |
| **HRRR speed_err** | **−3.62 mph** |
| bc_dir (flow) | 85.8° |
| existing bc_speed | 32.93 mph |

CBXC1 sits slightly below the coupled-station mean (−3.62 vs −6.89); it is
conservative as an anchor. WN at 32.93 would give WN_err = +3.94 (slight overshoot) —
if that value is correct, WN overcorrects here. Worth checking.

### Anchor 2 — PNTM8 / missoula_dec2025 (continental, secondary)

| Field | Value |
|---|---|
| Station name | POINT 6 |
| STID | PNTM8 |
| Event | missoula_dec2025 / continental_downslope |
| Lat / Lon | 47.04136 / −113.98631 |
| Elev (m) | 2407 |
| terrain_class | exposed_ridge |
| flow_coupling | coupled |
| RAWS obs (sus mph) | 46.06 |
| RAWS dir (°) | 255.0 (WSW) |
| HRRR 10m (mph) | 40.22 |
| **HRRR speed_err** | **−5.84 mph** |
| bc_dir (flow) | 275.4° |
| existing bc_speed | **84.18 mph ← ANOMALOUS** |

**PNTM8 bc_speed=84.18 is almost certainly wrong.** An 84 mph WN output against
46 mph obs (WN_err = +38) at a ridge station is implausible; likely an erroneous
automated calculation when the missoula_dec2025 rows were added. Do not treat this
as a prior WN result. Re-run WindNinja for this event from scratch; use the fresh
WN output, not the bc_speed field.

Continental-regime is a secondary test (only 2 continental events in Phase A,
finding exploratory). CBXC1/camp_2018 is the primary benchmark case.

---

## Test procedure

### Step 1 — Identify the event peak hour
For each anchor event, identify the analysis hour with the maximum RAWS sustained
wind speed. This is the WN input hour.

- camp_2018: Camp Fire ignition was ~0600 PST Nov 8, 2018. Peak Diablo typically
  mid-morning. Use the HRRR analysis run whose valid time best brackets the obs.
- missoula_dec2025: Dec 17 2025, obs window 0000–2300 local. Peak was identified
  during the fix_missoula_dec.py pull — confirm against the raw timeseries.

### Step 2 — Acquire HRRR analysis grid
Download the HRRR f00 (analysis) run for the event peak hour. Variables needed:
- `UGRD_10maboveground`, `VGRD_10maboveground` — surface wind
- `HGT_surface` — terrain height (for WN DEM consistency check)
- Optionally `UGRD_850mb`, `VGRD_850mb` — upper-level input if WN uses it

Source: NOAA HRRR archive (AWS s3://noaa-hrrr-bdp-pds/ or Herbie library).

### Step 3 — Run WindNinja on the HRRR grid
Run WindNinja in "forecast" mode using the HRRR grid as the wind input.
- Domain: center on anchor station, ~20 km radius minimum
- Output resolution: ≤ 90m (finer than DEM cell containing station)
- Extract: windspeed and direction at anchor lat/lon (nearest output cell)

If WN atmospheric mode is used (preferred): feed the full HRRR analysis field.
If WN point-initiation mode: use bc_dir as the inflow direction and HRRR speed
as the input speed — but note this is a weaker test (no mesoscale structure).

### Step 4 — Compute WN error
```
WN_err = WN_speed_at_station - RAWS_obs_sus_mph
HRRR_err = HRRR_10m_mph - RAWS_obs_sus_mph  (already in db as speed_err)
recovery = HRRR_err - WN_err  (positive = WN moved toward obs)
```

### Step 5 — Compare against benchmark
| Outcome | Criterion |
|---|---|
| Full recovery | WN_err within ±2 mph of 0 |
| Partial recovery | WN_err between HRRR_err and 0 (correct direction, incomplete) |
| No recovery | WN_err ≈ HRRR_err (WN adds nothing) |
| Overcorrection | WN_err has opposite sign, magnitude > 2 mph |

For CBXC1: HRRR_err = −3.62. Partial recovery threshold is WN_err > −3.62.
For PNTM8: HRRR_err = −5.84. Partial recovery threshold is WN_err > −5.84.

---

## What success looks like

**Strong case for WN adoption:** WN_err at both anchors within ±3 mph of 0, and
WN_err significantly less negative than HRRR_err. This means WN is recovering
most of the ~7 mph coupled-station gap.

**Partial case:** WN closes the gap by 3–5 mph at CBXC1 but less at PNTM8 (or
vice versa). Worth investigating whether the regime difference (offshore vs
continental) is driving the divergence before concluding.

**Failure:** WN_err ≈ HRRR_err at both anchors (WN doesn't help), or WN strongly
overcorrects (bc_speed=32.93 at CBXC1 → WN_err=+3.94 would be marginal overshoot —
check whether that's real or a bc calculation artifact).

---

## What to watch for

1. **Direction error at CBXC1.** RAWS obs = 69.3°, HRRR/bc_dir = 85.8° (16.5° rightward
   bias). If WN corrects direction toward 69°, that's a separate positive finding.

2. **PNTM8 bc_speed anomaly.** Whatever WN returns, discard the existing 84.18 field
   and record the fresh WN output. If WN still comes back >70 mph, check whether the
   HRRR analysis field at that hour has a realistic NW jet — PNTM8 is at 2407m on
   a high ridge and may genuinely see very strong wind, but 84 mph needs verification.

3. **Resolution sensitivity.** Camp Ridge (CBXC1) and Point Six (PNTM8) are both on
   narrow ridge features. If WN output changes substantially between 90m and 200m
   resolution, note it — that is terrain representation error from a different angle.

4. **WMSC1 as a lee-side contrast.** WMSC1 (thomas/woolsey) is classified intermediate
   (lee-facing) with errors of −35.6 / −27.0. If the same WN run covers WMSC1, check
   WN_err there. If WN also misses badly at WMSC1, that supports the lee-wave/rotor
   interpretation (WN doesn't model that physics). If WN recovers at WMSC1 but not
   at coupled stations, that's surprising and worth investigating.

---

## Files

| File | Role |
|---|---|
| `hrrr_error_dataset.csv` | Source of truth for RAWS obs, HRRR values, bc_speed/bc_dir |
| `flow_coupling_draft.csv` | flow_coupling tag (read-only derived frame) |
| `phase_a_finding.md` | Phase A benchmark this test is evaluated against |
| `dem_features.csv` | Station elevation, slope, aspect, terrain_class for context |

---

*"geometry sets coupling, error never does"*  
*flow_coupling must be applied within-regime; offshore and continental results reported separately*
