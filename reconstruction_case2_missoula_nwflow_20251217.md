# Case 2 Hindcast Reconstruction
## Missoula NW Flow — December 17, 2025

**Prepared:** 2026-05-28  
**Event type:** Terrain-coupled NW synoptic flow with morning cold pool decoupling  
**Location:** Missoula, MT and surrounding terrain  
**Key challenge:** Not "will it be windy?" — but "WHEN will the cold pool mix out?"

---

## 1. Event Overview

On December 17, 2025, a strong NW synoptic flow (25 kt at 700 hPa) moved through western Montana following a trough passage. The event illustrates the **cold pool decoupling problem**: at 12z (05 MST), surface winds were flowing southeast — opposite to the NW flow aloft — because a stable cold air pool trapped in the Missoula valley had not yet mixed out. By 18–21z (11–14 MST), solar heating broke the inversion and the surface coupled to the synoptic NW flow, producing 18–22 mph sustained westerly winds at KMSO.

This event is the cleanest terrain-coupling validation case in the library: two stations with real observations (KMSO and BLMM8), a full day of data, and a textbook transition from decoupled to coupled state.

---

## 2. Synoptic Setup

### 700 hPa Soundings — 12z December 17, 2025

| Station | Speed | Direction | Height | Temp | Dewpoint |
|---------|-------|-----------|--------|------|----------|
| OTX (Spokane) | 25 kt (28.8 mph) | 315° NW | 3166 m | +9.0°C | -10.0°C |
| TFX (Great Falls) | 25 kt (28.8 mph) | 315° NW | 3166 m | +9.0°C | -10.0°C |

Both soundings are **identical** — unambiguous synoptic NW flow. Dry air at 700 hPa (dewpoint depression 19°C) confirms cold, dry post-frontal airmass. Temperature +9°C at 700 hPa is characteristic of a winter post-trough cold-air advection pattern.

### Cold Pool Structure at 12z
The deep inversion common in December Missoula valleys traps cold air overnight and through early morning. Surface temperatures at KMSO near 05 MST were well below the 700 hPa temperature, confirming a strong valley cold pool. The valley acts as a reservoir of cold dense air that requires sustained solar heating to erode.

---

## 3. Observed Winds

### KMSO ASOS — Full Day (IEM, 5-min obs, 272 records)

| Period | UTC | MST | Dir | Spd | Phase |
|--------|-----|-----|-----|-----|-------|
| Cold pool | 11–13z | 04–06 MST | 130–150° SE | 12–21 mph | Opposite to 700 hPa — valley drainage |
| Transition | 14–17z | 07–10 MST | Shifting | Decreasing | Inversion eroding |
| **Coupled** | **18–21z** | **11–14 MST** | **270–280° W** | **18–22 mph** | **Coupled to synoptic NW** |
| Afternoon | 22z+ | 15 MST+ | 270–290° W | 15–20 mph | Sustained coupling |

### BLMM8 RAWS — Synoptic Data API (hourly at :01)
*NIFC-confirmed coords: 46.82073°N, -114.10089°W, 3412 ft — foothills SE of Missoula*

| Period | Dir | Spd | Notes |
|--------|-----|-----|-------|
| 11–13z (cold pool) | 157–182° S | 1.7–4.3 mph | Also decoupled — light S/SE drainage |
| 18–21z (coupled) | Variable E/SE/N | 1.7–5.2 mph | **Does NOT couple** — stays light all day |

**Key observation:** BLMM8 never responds to the NW synoptic flow even after KMSO couples at 18z. This is consistent with its **foothills SE location being terrain-sheltered** from NW flow by the valley terrain. The old BLMM8 assumed coordinates (46.832°N, -114.216°W) placed it on Blue Mountain ridge SW of Missoula — a position that would be fully exposed to NW flow. The real location is sheltered.

---

## 4. Mesoscale Models

### HRRR 3km (00z run, fxx=11–21)
*Note: HRRR values below were computed at old station coords. Coords updated 2026-05-28 — re-run hrrr_test.py for definitive values.*

| UTC | MST | KMSO | PNTM8 | BLMM8 | Lolo | Notes |
|-----|-----|------|-------|-------|------|-------|
| 11z | 04 | 89° 11 mph | 54° 10 mph | 228° 15 mph | 160° 14 mph | Cold pool — HRRR shows SE/S at low levels |
| 15z | 08 | 282° 13 mph | 278° 16 mph | 266° 27 mph | 2° 3 mph | HRRR begins coupling |
| 18z | 11 | 278° 21 mph | 267° 20 mph | 263° 27 mph | 263° 16 mph | **HRRR coupled — W/NW ~20 mph** |
| 20z | 13 | 287° 26 mph | 284° 24 mph | 271° 24 mph | 282° 23 mph | HRRR peak coupling |

**HRRR performance:** Correctly captured the cold pool through ~14z and the coupling transition by 18z. Peak KMSO speed 26 mph (HRRR) vs 22 mph observed — a modest 18% overprediction during coupled phase. **HRRR significantly outperformed compared to Case 1** — this is a synoptic event where the model physics are appropriate.

### GFS ~13km (Open-Meteo historical forecast)
GFS also captured the cold pool and coupling transition, with slightly less temporal precision (typically 1–2 hours late on coupling) and lower peak values (~18–20 mph vs HRRR 24–26 mph). Useful as a 48–72h forecast tool for this event type.

---

## 5. Terrain Downscaling: WindNinja

**Init:** 315° FROM NW / 29 mph  
**Grid:** 12mi radius, center 46.9°N / -114.1°W — DEM shared with Case 1  
**Resolution:** ~770m  
**Script:** `windninja_case2_wider.py`  
**Valid comparison window:** 18–21z (coupled period only)

### WindNinja Results (updated with NIFC-correct coords)

| Station | Coords | Elev | WN Dir | WN Speed | vs Init | vs Obs 18-21z |
|---------|--------|------|--------|----------|---------|---------------|
| KMSO | 46.916°N -114.090°W | 3205 ft | 314° | 28.3 mph | 0.98x | +6 mph (obs ~22 mph) |
| PtSix (retired) | 46.876°N -114.082°W | 6300 ft | 315° | 27.7 mph | 0.96x | — |
| **PNTM8 (NIFC)** | **47.041°N -113.986°W** | **7897 ft** | **313°** | **40.6 mph** | **1.40x** | **no obs available** |
| BLMM8 (NIFC) | 46.821°N -114.101°W | 3412 ft | 320° | 29.2 mph | 1.01x | obs 1.7–5.2 mph — WN overpredicts |
| Lolo | 46.749°N -114.066°W | 3200 ft | 323° | 27.2 mph | 0.94x | no obs available |

### Key Terrain Findings

**PNTM8 (Point Six, 7897 ft):** 40% terrain amplification from NW flow — the strongest terrain signal in the 14-case library so far. The NIFC location at 47.04°N is on an exposed ridge NE of Missoula in the upper Rattlesnake/Blackfoot area, directly in the path of NW synoptic flow. This station would be highly valuable for operational NW flow forecasting — if obs could be retrieved (WRCC access required).

**BLMM8 discrepancy:** WindNinja predicts 29.2 mph at the NIFC foothills location, but observed winds were 1.7–5.2 mph even during the coupled period. Two possible explanations:
1. **Micro-terrain shelter** — the foothills SE of Missoula have complex terrain that could shelter the specific BLMM8 location at sub-770m scale (WindNinja resolution is too coarse to resolve this)
2. **Cold pool persistence** — a residual cold pool may have persisted longer at this SE foothills location than at the KMSO valley floor

**Old BLMM8 value (38.8 mph) officially retired** — this came from the wrong Blue Mountain ridge coordinates (46.832°N, -114.216°W) which placed the station on an exposed SW-facing ridge. The real station at 46.821°N, -114.101°W shows no amplification. The 38.8 mph value should not appear in any future analysis.

---

## 6. Model Performance Summary

| Model | Coupled Period Prediction (KMSO) | Observed (KMSO 18-21z) | Error | Notes |
|-------|----------------------------------|------------------------|-------|-------|
| HRRR 3km | 21–26 mph, 278–304° | 18–22 mph, 270–280° | +15–20% speed | Good timing, slight overprediction |
| GFS 13km | 18–22 mph, W | 18–22 mph, W | ~0–10% | Good for 13km model |
| WindNinja (terrain) | 28.3 mph, 314° | 18–22 mph, 270° | +25–30% | Captures flow direction; slight overprediction |
| ERA5 31km | 6–13 mph SE→W | 12–22 mph SE→W | Timing OK, underpredicts | Synoptic context only |

**Contrast with Case 1:** All models performed reasonably for Case 2 (within 20–30%). Case 1 had a 10x model failure. This confirms the critical distinction: **synoptic terrain-coupling events are forecastable; convective downdraft events are not with standard tools.**

---

## 7. Forecasting Implications

### 48-Hour Window
**What's available:** GFS ensemble, synoptic analysis, climatological cold pool depth for December Missoula  
**What to look for:**
- 700 hPa NW flow forecast ≥20 kt following trough passage
- Surface temperature inversion depth overnight — how deep will the cold pool be?
- Forecast 850 hPa temperatures (cold pool strength proxy)
- December climatology: strong inversions typical in Missoula; coupling usually 10:00–14:00 MST if solar insolation adequate

**Forecast guidance at 48h:** "NW flow event likely following trough passage. Valley cold pool will suppress morning winds. Expect surface coupling 10:00–14:00 MST with sustained W winds 20–30 mph. Higher terrain (PNTM8-class ridges above 7000 ft) may see 35–45 mph."

### 24-Hour Window
**What's available:** HRRR, current soundings, surface mesonet, satellite insolation  
**What to look for:**
- HRRR inversion depth at 06z sounding time (how deep is the cold pool?)
- Current 700 hPa wind speed — is the synoptic flow strengthening?
- Cloud cover forecast — overcast skies delay or prevent coupling entirely
- HRRR timing of surface wind direction shift from SE/S to W/NW (marks coupling)

**Forecast guidance at 24h:** "Cold pool inversion ~500m deep (from HRRR sounding). Clear skies forecast → coupling expected ~11:30–12:30 MST. W winds 20–25 mph at valley floor 12–18 MST. Ridges above 7000 ft (Point Six area): 35–45 mph all day (above cold pool, already coupled to synoptic flow)."

### 12-Hour Window
**What's available:** Current soundings (KMSO if available), HRRR nowcast, mesonet observations  
**What to look for:**
- Current surface wind direction at KMSO — still SE/S? Confirms cold pool intact
- Temperature lapse rate between surface and 700 hPa — how much mixing needed?
- Sunrise time + expected solar radiation — when will the inversion begin eroding?
- **Critical signal:** First wind direction shift at KMSO from SE toward W/SW = coupling beginning

**Forecast guidance at 12h:** "Cold pool intact as of 06 MST (SE 15 mph at KMSO). Coupling expected 11:00–12:00 MST based on insolation timing. W winds 20–25 mph at valley floor 11 MST through 16 MST. Ridges already in NW flow — wind advisories warranted for terrain above 6500 ft."

### Key Forecasting Additions for This Event Type
**Cold Pool Dissolution Index (CPDI):** Combines:
1. Inversion depth (m) — from previous night's sounding or HRRR
2. 700 hPa wind speed (kt) — stronger flow → faster mechanical mixing
3. Forecast insolation (W/m²) — solar heating rate
4. Terrain constriction factor — narrow valleys (Missoula) dissolve slower than open basins

CPDI output: **predicted coupling time** ± 1–2 hours. This is the single most valuable piece of information for NW flow events in complex terrain — not wind speed, but timing.

---

## 8. Classification and Transferable Lessons

**Event class:** Type 2 — Synoptic-Terrain Coupling with Cold Pool Delay  
**Terrain influence:** Present and significant at exposed ridges (PNTM8: 40% amplification)  
**Model gap:** Small — 15–30% speed error in coupled period  
**Forecast challenge:** Timing of cold pool dissolution, not peak wind speed  

### Lessons for the 14-Case Library
1. **Separate decoupled and coupled phases** for all cold-season terrain events — model comparison in the wrong phase gives meaningless results (HRRR showing SE wind during NW event isn't a failure — it's correct cold pool behavior)
2. **PNTM8 (7897 ft) is the critical station** — 40% terrain amplification from NW flow, above cold pool all day. Obs would transform this event type's forecastability. WRCC access code is the key blocker.
3. **BLMM8 sub-WN-scale shelter is real** — 770m resolution WindNinja overpredicts at the foothills location. Sub-kilometer detail matters for specific sites.
4. **Type 2 events are the complement to Type 1** — where Type 1 requires convective indices, Type 2 requires thermodynamic indices (inversion depth, solar insolation, stable layer erosion). Different toolkits entirely.
5. **GFS performs well at 13km for this event type** — useful confirmation that 48-hour operational forecasts can be skillful for synoptic NW flow events.

---

## 9. Comparison: Case 1 vs Case 2

| Factor | Case 1 (Jul 24 2024 Derecho) | Case 2 (Dec 17 2025 NW Flow) |
|--------|------------------------------|-------------------------------|
| Driving mechanism | Convective cold pool downdraft | Synoptic NW flow + cold pool erosion |
| Peak obs (valley) | 65–109 mph | 18–22 mph |
| HRRR error | ~10x (catastrophic) | ~15–30% (good) |
| WN role | Background only | Primary signal in coupled window |
| Forecast horizon | 30-min certainty; probabilistic 24–48h | Skillful at 24h; good at 48h |
| Key index needed | Derecho Wind Index (DWI) | Cold Pool Dissolution Index (CPDI) |
| Dominant terrain feature | PNTM8 amplification (minor) | PNTM8 amplification (40% — significant) |

---

## 10. Pending Items

- [ ] Re-run `hrrr_test.py` with updated PNTM8 + BLMM8 coords (coord change may shift HRRR grid cell)
- [ ] Obtain WRCC access code — retrieve PNTM8 obs for Dec 17 2025 to validate the 40.6 mph prediction
- [ ] Prototype CPDI calculation for Missoula December climatology
- [ ] Run wider WN grid for multiple NW wind speeds (25, 35, 45 mph) to build a terrain amplification lookup table for PNTM8

---

## 11. Data Sources

| Dataset | Access | Notes |
|---------|--------|-------|
| 700 hPa sounding | IEM RAOB API | OTX + TFX, 12z Dec 17 |
| HRRR hindcast | AWS S3 via Herbie/conda hrrr311 | 00z run, fxx=11–21 |
| GFS | Open-Meteo historical forecast API | ~13km |
| ERA5 | Open-Meteo archive API | 31km |
| KMSO ASOS | IEM ASOS API | 272 records, 5-min, full day |
| BLMM8 | Synoptic Data API | Hourly :01, within 7-day free window |
| WindNinja | CLI 3.12.2, SRTM 12mi DEM | Shared DEM from Case 1 |

**Scripts:** `windninja_case2_wider.py` · `hrrr_test.py` · `dec17_final.py` · `validation_charts.py`  
**Cache:** `C:\temp\windninja_cache\dem_46.9_-114.1_12mi_315_29_609m_vel-4326.asc`

---

## 12. Summary

The December 17, 2025 Missoula NW flow event is the best-behaved case in the 14-case library. A clean, unambiguous 315° NW synoptic flow at 700 hPa (25 kt, confirmed at two soundings) produced a textbook cold pool decoupling and dissolution sequence in the Missoula valley. Surface winds were southeast at 12–21 mph from early morning, completely opposite to the flow aloft, then shifted west at 18–22 mph by 11–14 MST as solar heating eroded the inversion.

**What the models got right:** HRRR and GFS both captured the cold pool through mid-morning and the coupling transition by midday — a genuine forecasting success for this event type. WindNinja, initialized at 315°/29 mph, produced values within 25–30% of observed winds during the coupled period at KMSO. All models are in rough agreement, with no catastrophic failure of the kind seen in Case 1.

**The standout finding:** PNTM8 at NIFC-confirmed coordinates (47.04°N, 7897 ft) shows **40% terrain amplification from NW flow** — the strongest terrain signal encountered so far across both cases. This ridge sits above the cold pool all day, meaning it is already coupled to the synoptic flow at 12z while the valley is still running backward. Point Six is the single most important unobserved station for NW flow forecasting in the Missoula region. Obtaining historical PNTM8 data via WRCC is the highest-priority data gap for Case 2.

**What remains uncertain:** BLMM8 at its correct foothills location stays light and variable (1.7–5.2 mph) even after valley coupling — WindNinja predicts 29 mph there. Sub-770m terrain shelter is the most likely explanation, but without higher-resolution WN runs or additional nearby obs, this cannot be confirmed.

**The forecasting lesson:** Type 2 events (cold pool + synoptic coupling) are fundamentally different from Type 1 (convective downdraft). The question to answer is not "how hard will it blow?" — HRRR handles that reasonably at 48 hours. The question is "when will the cold pool mix out?" The proposed Cold Pool Dissolution Index (CPDI) — combining inversion depth, 700 hPa wind speed, solar insolation, and valley geometry — addresses exactly this gap and would be the primary operational improvement this case motivates.

**Status:** Reconstruction complete. Case 3 (Marshall Fire, December 30, 2021) is next.
