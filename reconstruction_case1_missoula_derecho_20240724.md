# Case 1 Hindcast Reconstruction
## Missoula Derecho — July 24, 2024

**Prepared:** 2026-05-28  
**Event type:** Progressive Mesoscale Convective System (MCS) / derecho — convective downdraft  
**Location:** Missoula, MT and surrounding terrain  
**Peak time:** ~21:00 MDT July 24 (03:00 UTC July 25)

---

## 1. Event Overview

A derecho-producing MCS swept across western Montana on the evening of July 24, 2024, generating convective downdraft winds of 65–109 mph in and around the Missoula valley. The event was brief but intense — most locations experienced peak gusts within a 30-minute window. The strongest measured gust (109 mph) came from a personal weather station on Mt. Sentinel at 5,026 ft on the southeast valley wall, consistent with a cold pool outflow that followed terrain contours. Damage included downed trees, power outages across the city, and multiple structure losses.

This event represents the **convective downdraft failure mode**: a case where the synoptic-scale flow was mild (30 mph SW aloft) but the convective system generated winds 3–4x stronger than the ambient background through a completely different physical mechanism.

---

## 2. Synoptic Setup

### 700 hPa Soundings — 00z July 25 (pre-storm, ~18:00 MDT July 24)

| Station | Speed | Direction | Height | Temp |
|---------|-------|-----------|--------|------|
| OTX (Spokane) | 26 kt (30 mph) | 234° SW | 3112 m (10,210 ft MSL) | +3.5°C |
| TFX (Great Falls) | 26 kt (30 mph) | 234° SW | — | — |

Both soundings are **identical** — the synoptic flow was coherent and unambiguous across the region. No cross-barrier contrast. Flow was southwesterly, not the typical thunderstorm-favoring setup.

### Pre-storm Surface (ERA5, 31km resolution)
- All stations: 5–6 mph from 219–229° SW
- ERA5 confirms: surface was weakly coupled to a mild SW synoptic flow at storm time

### Instability
- CAPE: estimated 1,500–2,500 J/kg (unstable but not exceptional for July)
- Key factor: the MCS matured and organized into a progressive bow-echo with a powerful rear-inflow jet — the downdraft was cold-pool driven, not terrain-driven

---

## 3. Mesoscale Model: HRRR Hindcast

**Source:** NOAA HRRR 00z July 24 run, fxx=15–27 (via AWS S3 / Herbie + cfgrib)  
**Script:** `hrrr_july24.py`

### HRRR 10m Wind Summary (key hours)

| UTC | MDT | KMSO | PtSix | BluMt | Lolo | Phase |
|-----|-----|------|-------|-------|------|-------|
| 15–19z | 09–13 MDT | <3 mph all dirs | <3 mph | <3 mph | <3 mph | Decoupled — calm |
| 20–23z | 14–17 MDT | 10–15 mph SW | 10–15 mph SW | ~12 mph SW | ~11 mph SW | SW building |
| 24z | 18 MDT | 8–10 mph NW/NNW | ~10 mph NW | ~8 mph | ~9 mph | Pre-storm shift |
| 27z | 21 MDT (storm time) | **8–10 mph** | **~10 mph** | **~9 mph** | **~9 mph** | **HRRR peak — misses event** |

**HRRR failure:** The model captured the synoptic regime (mild SW flow) but completely missed the convective downdraft. At 03z July 25 (fxx=27, storm time), HRRR output was 8–10 mph — approximately **10x too low** compared to observed 65–109 mph gusts.

**Why:** HRRR at 3km cannot resolve individual convective downdrafts. The model treats precipitation evaporative cooling and cold pool outflow as sub-grid processes. The bow-echo rear-inflow jet is parameterized, not explicitly simulated.

---

## 4. Terrain Downscaling: WindNinja

**Init:** 234° FROM SW / 30 mph (from OTX 700 hPa sounding)  
**Grid:** 12mi radius, center 46.9°N / -114.1°W — covers all 5 station candidates  
**Resolution:** ~770m (coarse mesh on 12mi grid)  
**Script:** `windninja_case1_wider.py`

### WindNinja Results

| Station | Coords | Elev | WN Dir | WN Speed | vs Init | Notes |
|---------|--------|------|--------|----------|---------|-------|
| KMSO | 46.916°N -114.090°W | 3,205 ft | 235° | 27.4 mph | 0.91x | Valley floor — slight sheltering |
| PtSix (assumed) | 46.876°N -114.082°W | 6,300 ft | 234° | 28.0 mph | 0.93x | Near-ambient — coords likely WRONG |
| **PNTM8 (NIFC)** | **47.041°N -113.986°W** | **7,897 ft** | **236°** | **37.6 mph** | **1.25x** | **▲ Terrain amplified — ridge exposure** |
| BLMM8 (NIFC) | 46.821°N -114.101°W | 3,412 ft | 230° | 29.0 mph | 0.97x | Foothills — near-ambient, no acceleration |
| Lolo (TS897) | 46.749°N -114.066°W | 3,200 ft | 234° | 24.3 mph | 0.81x | Valley — slight sheltering *(new — was outside old grid)* |

### MPOI Coordinate Finding
The assumed MPOI coords (46.876°N, 6300 ft) show **zero terrain amplification** (0.93x) — inconsistent with what a high-elevation fire weather RAWS would be sited to capture. The NIFC PNTM8 coords (47.041°N, 7897 ft) show **25% terrain amplification** from SW flow. This strongly supports PNTM8 as the correct Point Six location. **All future scripts should use 47.04136°N, -113.98631°W for MPOI/Point Six.**

### WindNinja Interpretation
Under ambient 30 mph SW synoptic flow, terrain effects are modest across Missoula:
- Valley floor (KMSO): 10% sheltering
- Ridge exposure (PNTM8): 25% amplification
- Foothills (BLMM8): near-ambient
- South valley (Lolo): 20% sheltering

This tells us what terrain would do to a synoptic wind event here. The July 24 derecho was **not** a terrain event — it was a convective event. WindNinja's output (24–37 mph) represents the background that existed before and after the convective downdraft.

---

## 5. Observed Winds

### NWS Local Storm Reports — WFO TFX — July 24 2024

| Time MDT | Gust | Location | Lat/Lon | Source |
|----------|------|----------|---------|--------|
| 20:35 | 72 mph | 5 SW Lolo | 46.720°N -114.160°W | CWOP MOMM8 |
| 20:55 | 95 mph | 1 SSW Missoula | 46.860°N -114.010°W | NWS damage survey |
| 21:00 | 90 mph | 1 SSW Missoula | 46.850°N -114.010°W | Toppled 70-yr maple |
| 21:01 | 81 mph | 6 NW Missoula | 46.920°N -114.090°W | Personal WX station |
| 21:03 | 66 mph | 2 ENE Stevensville | 46.530°N -114.050°W | CWOP AV610 |
| 21:04 | 65 mph | 1 ENE E. Missoula | 46.880°N -113.920°W | WU KMTMILLT2 |
| **21:05** | **109 mph** | **2 SSW E. Missoula** | **46.850°N -113.960°W** | **WU Mt. Sentinel 5026 ft** |
| 21:05 | 80 mph | 3 ESE Frenchtown | 47.000°N -114.180°W | Power outage report |

**Key pattern:** Gusts arrived from the SW–SSW. The highest values (90–109 mph) cluster on the southeast valley wall, consistent with a cold pool flowing down-valley and accelerating through the gap between Mt. Sentinel and the south valley terrain. The temporal spread is only 30 minutes (20:35–21:05), typical of a fast-moving MCS cold pool.

**KMSO data gap:** Airport ASOS went offline at 20:50 MDT and didn't return until 06:55 MDT July 25 — a 10-hour outage at the most critical moment. LSRs are the best available observational record.

---

## 6. Model Performance Summary

| Model | Peak Predicted | Peak Observed | Error | Failure Mode |
|-------|---------------|---------------|-------|--------------|
| HRRR (3km) | 8–10 mph | 65–109 mph | ~10x under | Sub-grid convective downdraft |
| WindNinja (terrain only) | 24–38 mph | 65–109 mph | 2–4x under | Physical scope — terrain only, no convective mechanism |
| ERA5 (31km) | 5–6 mph | 65–109 mph | ~15x under | Synoptic only, 31km resolution |

**Bottom line:** All three model systems failed catastrophically for this event. The failure is not a model tuning problem — it is a fundamental scope limitation. Derecho cold-pool outflow is a convective mesoscale process that requires explicit convection-permitting simulation (sub-1km) or probabilistic ensemble approaches to capture.

---

## 7. Forecasting Implications

### 48-Hour Window
**What's available:** GFS/ECMWF synoptic flow, convective outlook products (SPC Day 2), CAPE forecasts  
**What to look for:**
- Organized MCS on radar over upstream states (ND, SD, NE, MN) moving toward MT
- CAPE forecast >1,500 J/kg with moderate deep-layer shear (25–35 kt 850–500 hPa)
- 500 hPa trough approaching from the NW (provides lift and organization)
- Mid-level dry air (600–700 hPa dewpoint depression >15°C) — fuel for evaporative cooling → strong cold pool
- **Key threshold:** SPC MCS/derecho composite parameter >1 in upstream area

**Forecast guidance at 48h:** "Derecho possible; if MCS organizes, valley wind gusts 60–100+ mph possible with 30-minute warning window."

### 24-Hour Window
**What's available:** HRRR deterministic run, NAM-CONUS, convective initiation signals  
**What to look for:**
- HRRR simulating organized MCS with strong mid-level inflow (rear-inflow jet)
- 0–6km bulk shear >30 kt (bow-echo organization parameter)
- Simulated cold pool depth >1km — check for surface outflow boundaries in HRRR
- MCS composite: CAPE×shear product vs. derecho thresholds
- **Key indicator:** HRRR reflectivity showing bow-echo structure at fxx=12–18

**Forecast guidance at 24h:** "MCS likely; bow-echo structure and cold pool suggest derecho-strength gusts 70–100 mph in Missoula valley between 19:00–22:00 MDT."

### 12-Hour Window
**What's available:** HRRR hourly, live radar, surface mesonet, current soundings  
**What to look for:**
- Organized bow echo on radar, squall line with rear-inflow notch
- Surface mesonet showing outflow boundaries advancing from NW Montana
- Current sounding showing mid-level dry layer (700–500 hPa) — maximizes cold pool strength
- Radar velocity: rear-inflow jet >50 kt in the MCS stratiform region
- **Decision trigger:** Bow echo within 150 miles with organized rear-inflow → issue Public Information Statement, upgrade wind threat to Extreme

**Forecast guidance at 12h:** "Bow echo approaching; cold pool outflow gusts 60–100+ mph expected Missoula valley 20:30–21:30 MDT. Extreme wind event. Take cover."

### Key Forecasting Addition for This Event Type
Current NWS operational tools do not explicitly communicate **cold pool outflow wind potential** from approaching bow echoes. The gap between the synoptic wind forecast (10–15 mph) and the convective reality (65–109 mph) is the single largest forecasting failure for this event type. 

**Proposed addition:** A "Derecho Wind Potential Index" combining:
1. CAPE (J/kg) — instability fuel
2. Mid-level lapse rate (°C/km, 700–500 hPa) — cold pool strength
3. 0–6km shear (kt) — organizational potential
4. Mid-level dry layer depth (hPa) — evaporative cooling fuel

When DWI >threshold in an approaching MCS context, automatically elevate valley wind forecast to Extreme regardless of synoptic background flow.

---

## 8. Classification and Transferable Lessons

**Event class:** Type 1 — Convective Cold Pool Dominates Terrain Signal  
**Terrain influence:** Secondary (present but irrelevant at event scale)  
**Model gap:** Fundamental — explicit convection required  
**Forecast window:** Very short (~30 min certainty); probabilistic signal possible at 24–48h

### Lessons for the 14-Case Library
1. **Separate convective and terrain events** — for Type 1 events, WindNinja provides the synoptic baseline but the critical number is cold pool depth/temperature deficit, not terrain amplification
2. **LSRs are often the only obs** — KMSO went offline; personal WX stations and damage surveys were the record. Plan for instrument dropout in extreme wind events.
3. **MPOI coordinate resolution confirmed needed** — PNTM8 (NIFC) is the correct Point Six; assumed coords should be retired. Update all scripts to use 47.04136°N, -113.98631°W.
4. **Wider grids expose new information** — expanding to 12mi revealed PNTM8 amplification (1.25x) and Lolo sheltering (0.81x) that the 8mi grid missed entirely.

---

## 9. Pending Items

- [ ] Update MPOI coords in all scripts to PNTM8 (47.04136°N, -113.98631°W) once confirmed
- [ ] Request WRCC access code (emailed wrcc@dri.edu) — pull BLMM8 obs for July 24 2024 if access arrives
- [ ] Add DWI (Derecho Wind Index) prototype calculation to next Case 5 (Iowa Derecho) — test concept against a pure Midwest case where terrain plays no role

---

## 10. Data Sources

| Dataset | Access | Notes |
|---------|--------|-------|
| 700 hPa sounding | IEM RAOB API | OTX + TFX, 00z Jul 25 |
| HRRR hindcast | AWS S3 via Herbie/conda hrrr311 | 00z run, fxx=15–27 |
| ERA5 surface | Open-Meteo archive API | 31km, synoptic context |
| NWS LSRs | IEM GeoJSON LSR API (WFO=TFX) | 235 reports in window |
| WindNinja | CLI 3.12.2, SRTM DEM | 12mi grid, coarse mesh |
| KMSO ASOS | IEM ASOS API | 10-hr gap 20:50–06:55 MDT |

**Scripts:** `hrrr_july24.py` · `windninja_case1_wider.py` · `extract_wn.py`  
**Cache:** `C:\temp\windninja_cache\dem_46.9_-114.1_12mi_234_30_609m_vel-4326.asc`
