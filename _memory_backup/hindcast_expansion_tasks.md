---
name: hindcast-expansion-tasks
description: "14-case hindcast library for synoptic-to-local wind reconstruction — goal is a validated methodology for improved forecasting"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4554217c-598d-4df8-9ee6-f90d75430f79
---

# Hindcast Reconstruction Library — All 14 Cases

**Goal**: For each event, reconstruct the full synoptic-to-local wind chain (sounding → HRRR → WindNinja → obs), document where models succeed/fail, and build transferable forecasting improvements.

**Why:** Confirmed 2026-05-28. User wants unique hindcast reconstruction across all 14 cases to develop a method for improved forecasting.

## Reconstruction Methodology (framework v2, 2026-05-30)
1. **Mechanism classification** — run mechanism_classifier.py first; determines WN scope and bust axis
2. **BC audit** — pull HRRR 700 hPa (hrrr_700hpa_*.py); compare to WN init BC; document gap
3. **Synoptic setup** — 700 hPa soundings pre/during/post event (IEM RAOB API)
4. **Mesoscale model** — HRRR hindcast at 3km (Herbie/conda hrrr311)
5. **Terrain downscaling** — WindNinja at ~100–500m from HRRR init (SYNOPTIC_TERRAIN only; PARTIAL for PBL_TRANSIENT)
6. **Observations** — ASOS, RAWS, NWS LSRs, damage surveys
7. **Gap analysis** — where did HRRR + WN fail, and why (missing mechanism)
8. **Reconstruction doc** — case*_reconstruction.py with mechanism block + BC audit + findings

**BC audit scope rule (established 2026-05-30):**
- SYNOPTIC_TERRAIN: use HRRR 700 hPa domain-mean as BC reference (ridgetop flow)
- PBL_TRANSIENT: use sounding at upwind post-frontal station (OTX/TFX); HRRR domain-mean straddles front
- CONVECTIVE_OUTFLOW / FIRE_GENERATED: WN out of scope; document mechanism only

---

## Event Library
Authoritative source: `hindcast_event_library.md` (committed 60408be).
Supersedes the original numbered 14-case list.
Tier 1 anchors complete (Camp Fire, Missoula Dec 17, Thomas Fire).
Recommended next order: Tubbs → Kincade+Glass → Labor Day 2020 OR → Woolsey+North Complex → Yarnell+Carr.

## Case Status Table (original 14-case list, partially superseded)

| # | Event | Date | Type | Status |
|---|-------|------|------|--------|
| 1 | Missoula Derecho | Jul 24, 2024 | Convective downdraft | ✅ COMPLETE — 12mi WN grid, reconstruction doc, committed f12ce38 |
| 2 | Missoula NW Flow | Dec 17, 2025 | PBL_TRANSIENT cold frontal | ✅ COMPLETE — mechanism classified, BC audit, WN 1.40x PNTM8, committed 4126893 |
| 3 | Marshall Fire | Dec 30, 2021 | Boulder Chinook / hydraulic jump | ✅ COMPLETE — HRRR+WN+LSRs, reconstruction doc, committed 3cca269 |
| 4 | Camp Fire | Nov 8, 2018 | Type 4 surface pressure gap/canyon flow | ✅ COMPLETE — 3 WN runs, HRRR, reconstruction, committed 499d33a |
| 5 | Iowa Derecho | Aug 10, 2020 | Type 1b organized MCS / rear-inflow jet | ✅ COMPLETE — DWI calibration, HRRR 27x error, WN 1.0x flat terrain, committed 944a055 |
| 6 | Boulder Windstorm | Jan 11, 1972 | Type 3b resonant trapped lee wave | ✅ COMPLETE — ERA5 2-3x, WN 0x, MWAI=8.0, committed 67573c1 |
| 7 | Oakland Hills Fire | Oct 20, 1991 | Type 4b — small ridge Diablo wind | ✅ COMPLETE — 3 soundings, ERA5, WN 1.0x, committed ffd2899 |
| 8 | Thomas Fire | Dec 4, 2017 | SYNOPTIC_TERRAIN | ✅ COMPLETE (data-limited) — 1.44x Topa Topa, 700hPa 28.8@310, terrain guard clean, committed e8668f4 |
| 9 | Tubbs Fire | Oct 2017 | Diablo NE winds, NorCal | No script |
| 10 | Kincade Fire | Oct 2019 | Diablo NE winds, NorCal | No script |
| 11 | Boulder Chinook | Jan 2021 | Downslope, 100+ mph gusts | No script |
| 12 | Ohio Valley Derecho | Jul 1, 2012 | Convective bow echo | No script |
| 13 | Washoe Zephyr | Various | Eastern Sierra terrain jet | No script; event date TBD |
| 14 | Columbia Gorge East Wind | Various | Gap/channel flow, Portland OR | No script; event date TBD |

## Event Type Groupings
- **Derechos**: #1, #5, #12
- **Downslope / Chinook**: #2, #3, #6, #11
- **Fire-wind (terrain + offshore)**: #4, #7, #8, #9, #10
- **Gap / channel flow**: #13, #14

## Data Gap Issues (carry forward to every new case)
| Station | Gap | Workaround |
|---------|-----|------------|
| MPOI (Point Six) | Not in Synoptic; NIFC coords show PNTM8 at 47.04°N/-113.99°W | Needs resolution |
| TS897 (Lolo Portable) | Synoptic returns wrong station (Ashland MT, ~250 mi away) | Use IEM or WRCC |
| BLMM8 (Blue Mtn) | Synoptic: only 7-day free window | WRCC (needs access code) |
| KMSO ASOS | 10-hr gap during Jul 24 2024 derecho | Use LSRs as proxy |
| WRCC general | >30-day wall without access code | User emailed wrcc@dri.edu |

**Alternative data sources:**
- IEM RAWS archive: `https://mesonet.agron.iastate.edu/request/raws/`
- NIFC RAWS portal: `https://fam.nwcg.gov/fam-web/`
- IEM ASOS: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`

## Key Technical Notes
- HRRR: run via conda `hrrr311` — `& "C:\Users\aphil\miniforge3\Scripts\conda.exe" run -n hrrr311 python script.py`
- WindNinja CLI: `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe`
- WN cache: `C:\temp\windninja_cache\`
- lon360 fix: HRRR uses 0-360° — always convert `lon360 = lon_neg + 360`
- IEM RAOB API: `https://mesonet.agron.iastate.edu/json/raob.json?airport=OTX&ts=...&fmt=json`
- Open-Meteo hist-forecast (GFS): `https://historical-forecast-api.open-meteo.com/v1/forecast?models=gfs_global`

## How to apply
When user asks about hindcasting — start at Case 1, work in order. For each new case, check data access against the gap table before writing scripts to avoid WRCC/Synoptic dead-ends.
