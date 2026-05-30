---
name: hindcast-missoula-cases
description: "Cases 1 & 2 — Missoula July 2024 derecho and Dec 2025 NW flow. Station coords, HRRR/WN results, data access, scripts."
metadata: 
  node_type: memory
  lastUpdated: 2026-05-28
  type: project
  originSessionId: 87c6a09e-433b-4598-993a-d7973fdfb100
---

# Case 1 — Missoula Derecho, July 24 2024

## Status: RECONSTRUCTION COMPLETE (2026-05-28)
- Script: `windninja_case1_wider.py` — 12mi grid, all 5 station candidates
- Reconstruction: `reconstruction_case1_missoula_derecho_20240724.md`
- Committed: f12ce38

## Event
- Time: 21:00 MDT July 24 (03:00 UTC July 25)
- Type: Progressive MCS / bow-echo derecho — convective cold pool
- Peak gusts: 65–109 mph (LSRs); 109 mph at WU Mt. Sentinel 5026 ft

## 700 hPa Sounding (OTX + TFX, 00z July 25 — both identical)
- Speed: 26 kt (30 mph) | Direction: 234° SW | Height: 3112 m | Temp: +3.5°C
- WindNinja init: 234° / 30 mph

## HRRR Result
- Captured: 8–10 mph SW at storm time (fxx=27)
- Missed: convective cold pool downdraft entirely (~10x under)
- Phases: decoupled 15–19z (<3 mph); SW builds 20–23z (10–15 mph); pre-storm shift 24–26z (NW/NNW 8–12 mph)

## WindNinja — 12mi Grid Results (new 2026-05-28)
Center: 46.9°N / -114.1°W | Init: 234° / 30 mph | Res: ~770m
Cache: `dem_46.9_-114.1_12mi_234_30_609m_vel-4326.asc`

| Station | Coords | Elev | WN Speed | vs Init | Notes |
|---------|--------|------|----------|---------|-------|
| KMSO | 46.916°N -114.090°W | 3205 ft | 27.4 mph | 0.91x | Valley — slight sheltering |
| PtSix_assum | 46.876°N -114.082°W | 6300 ft | 28.0 mph | 0.93x | Near-ambient — coords likely WRONG |
| **PNTM8_NIFC** | **47.041°N -113.986°W** | **7897 ft** | **37.6 mph** | **1.25x** | **Ridge — terrain amplified** |
| BLMM8 | 46.821°N -114.101°W | 3412 ft | 29.0 mph | 0.97x | Foothills — near-ambient |
| Lolo/TS897 | 46.749°N -114.066°W | 3200 ft | 24.3 mph | 0.81x | Valley — sheltered (new — was outside 8mi) |

## MPOI Coordinate — RESOLVED (2026-05-28)
- **PNTM8 (NIFC) = correct Point Six**: 47.04136°N, -113.98631°W, 7897 ft
  - Shows 1.25x terrain amplification from SW flow — consistent with exposed ridgetop RAWS
- **Assumed coords RETIRED**: 46.876°N, -114.082°W, 6300 ft — shows 0.93x (no amplification)
- **ACTION: Update all scripts** to use 47.04136°N, -113.98631°W for MPOI/Point Six

## NWS LSRs (best obs — KMSO went offline 20:50–06:55 MDT)
- 20:35: 72 mph — 5 SW Lolo
- 20:55: 95 mph — 1 SSW Missoula (NWS damage survey)
- 21:01: 81 mph — 6 NW Missoula (personal WX)
- 21:05: **109 mph** — 2 SSW E. Missoula (WU Mt. Sentinel 5026 ft)
- 21:05: 80 mph — 3 ESE Frenchtown

## Key Findings
- **Model gap: ~10x** — HRRR+WN 8–37 mph vs obs 65–109 mph
- **Failure mode: Type 1 — Convective Cold Pool Dominates** — terrain irrelevant at event scale
- **Forecasting concept: Derecho Wind Index (DWI)** = CAPE × mid-level lapse rate × 0–6km shear × dry layer depth. Test on Case 5 (Iowa Derecho, no terrain).

## Forecasting Framework (48/24/12-hour)
- **48h**: SPC MCS composite >1 upstream; CAPE >1500 + shear >25kt; mid-level dry air
- **24h**: HRRR bow-echo structure at fxx=12–18; 0–6km shear >30kt; cold pool depth >1km
- **12h**: Bow echo within 150mi + rear-inflow notch on radar; issue Extreme wind threat

---

# Case 2 — Missoula NW Flow, December 17 2025

## Status: RECONSTRUCTION COMPLETE (scripts/charts done, write-up pending)
- Master table: `dec17_final.py`
- Charts: `validation_charts.py`

## 700 hPa (OTX + TFX, 12z — both identical)
- Speed: 25 kt (28.8 mph) | Direction: 315° NW | Height: 3166 m | Temp: +9.0°C
- WindNinja init: 315° / 29 mph

## Key Finding: Valley Cold Pool Decoupling
- 12z (05 MST): Surface completely decoupled — KMSO 130–150° SE at 12–21 mph (opposite of NW aloft)
- 18–21z (11–14 MST): Daytime mixing couples flow — KMSO shifts to 270–280° W at 18–22 mph
- BLMM8: Stays light/variable all day — consistent with sheltered foothills location (coords confirmed)

## WindNinja Results (315°/29mph, center 46.9/-114.1)
- KMSO 3205 ft: 314° / 28.9 mph — near-ambient, valley floor
- PNTM8 7897 ft: (not in old 8mi grid — needs new run with wider grid)
- BluMt 3412 ft (NIFC): 315° / 26.8 mph — near-ambient at correct coords
- Lolo 3200 ft: outside old grid — needs wider run
- **Key: NO strong terrain acceleration at confirmed coords for Dec 17 NW event**

## Pending for Case 2
- [ ] Run wider 12mi grid (315°/29mph) to capture Lolo + PNTM8
- [ ] Write reconstruction document (same format as Case 1)
- [ ] Update MPOI coords to PNTM8 in all Dec 17 scripts

---

# Station Reference (authoritative as of 2026-05-28)

| Station | Lat | Lon | Elev | Network | Notes |
|---------|-----|-----|------|---------|-------|
| KMSO | 46.916°N | -114.090°W | 3205 ft | IEM ASOS | 10-hr gap Jul 24 2024 |
| **PNTM8 (Point Six)** | **47.04136°N** | **-113.98631°W** | **7897 ft** | NIFC RAWS | Correct MPOI coords — replaces assumed |
| BLMM8 (Blue Mtn) | 46.82073°N | -114.10089°W | 3412 ft | NIFC RAWS | Foothills SE — confirmed |
| TS897 (Lolo) | 46.749°N | -114.066°W | 3200 ft | Synoptic portable | Wrong station in Synoptic; use IEM/WRCC |

# Data Access
- HRRR: conda `hrrr311` — `& "C:\Users\aphil\miniforge3\Scripts\conda.exe" run -n hrrr311 python script.py`
- WRCC: >30-day wall without access code (user emailed wrcc@dri.edu)
- Synoptic token: `<SYNOPTIC_TOKEN - see synoptic_config.py>` (regenerate from key `<SYNOPTIC_API_KEY - see synoptic_config.py>` if expired)
- lon360 fix: HRRR uses 0–360° — always `lon360 = lon_neg + 360`

# Scripts (C:\Users\aphil\Documents\Stormwatch\)
- `windninja_case1_wider.py` — 12mi grid, all stations, July 24 2024 init
- `hrrr_july24.py` — HRRR Jul 24 2024, fxx=15–27
- `dec17_final.py` — master table Dec 17 2025 (Obs+HRRR+GFS+WN)
- `validation_charts.py` — final clean charts (3 charts)
- `extract_wn.py` — reads WN ASC cache, extracts point values
- `marshall_fire_20211230.py` — Case 3 starter script (in progress)
