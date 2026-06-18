# WindNinja Hindcast Series — HindC Tab v1.0
**Review document for external audit · 2026-06-17**
**12 fire events · 164 RAWS station-observations · 2017–2025 · Western US**

This file contains the full narrative content of the HindC tab in StormWatch Live,
extracted for readability. All numbers trace to `hrrr_error_dataset.csv` (164 active rows).
The authoritative findings ledger is `STORMWATCH_MASTER_STATUS.md`.

---

## The Challenge

HRRR is driven by synoptic systems, not local terrain. Its 3 km grid resolves large-scale
wind patterns well but is blind to sub-kilometer terrain — the canyon channeling, ridge
amplification, and gap flow that shape wind where fires actually burn. The result is
systematic wind-speed errors at complex-terrain fire-weather stations, and they are worst
exactly when conditions are most dangerous.

WindNinja resolves those features with a mass-consistent, terrain-following solver at 30 m.
It is **diagnostic, not prognostic**: it applies terrain physics to a supplied boundary
condition but generates no forecast of its own. Any error in the boundary condition —
speed, direction, or timing — propagates directly into every grid point of the output.
A flawed boundary condition yields a flawed answer wearing the right terrain shape:
detailed, plausible, and wrong.

**Goal:** design and validate a reliable HRRR → WindNinja pipeline — the end-to-end
workflow: synoptic model (HRRR or GFS) → extract the boundary condition → run WindNinja →
30 m terrain-resolved wind. The design problem is to determine which model level, which
hour, and which correction yield a boundary condition that lets WindNinja's terrain physics
recover the error HRRR cannot resolve.

---

## What We Found — 12 Events · 164 Stations

### Finding 1 (signal): The error is set by synoptic regime, not by station terrain

Offshore-gradient events (Diablo, Santa Ana): HRRR systematically undershoots — mean
**−3.9 mph** (N=6 events). Continental downslope (Front Range, Cascades, Chinook): mean
**+0.5 mph** — essentially unbiased (N=3). Convective outflow (Iowa derecho, Missoula Jul
2024): near-zero mean, high station variance — included as contrast cases, not pipeline
targets.

Terrain class — exposed ridge, canyon, valley, open — does **not** predict the error
(structured-vs-white ratio 0.013; all class means within the ~10 mph station noise). Which
weather pattern is driving the event tells you nearly everything; where the station sits
tells you little.

### Finding 2 (causal): The cause is unresolved sub-grid terrain, not a model physics fault

The offshore underbias is a resolution limit shared across models. ERA5 at 0.25° undershoots
the same events more than HRRR at 3 km (−8.9 vs −4.1 mph) — coarser grid, larger miss.
The synoptic wind is real; the terrain that channels and accelerates it to the surface lives
below the model grid. This is exactly the gap a 30 m terrain solver is built to close.

### Finding 3 (confirmed): At exposed ridges, WN closes the gap when HRRR genuinely undershot the BC

The key test: does routing the raw 850 hPa HRRR boundary condition through WindNinja's terrain
solver recover the speed error at exposed-ridge stations? Camp Fire provides the answer with
two held-out stations that tell opposite sides of the same story.

Camp Fire, two held-out exposed-ridge stations (never used in fitting):
- **CBXC1** (Colby Mtn): HRRR undershot obs by 3.6 mph (HRRR/obs 0.875); 850 hPa BC was
  32.9 mph; WN terrain-resolved to 29.2 mph — WN/obs **1.007**. The clean recovery: a real
  synoptic gap, closed by terrain physics. No correction, no fitting.
- **SLEC1** (Saddleback): HRRR 10m undershot obs by 18 mph (HRRR/obs 0.477) — but the 850 hPa
  BC was already 33.5 mph, just 1.5 mph below obs (bc/obs 0.96). WN's ridge amplification
  carried it to 39.5 mph, +4.5 above obs — WN/obs **1.128**, a mild overshoot. SLEC1 is the
  bc/obs ≈ 1 boundary case: BC already near-right, terrain amplification not needed.

What the two stations demonstrate is terrain geometry, not a bc/obs threshold. The same
near-obs BC was decelerated at CBXC1 (slope 5.96°, relief 224m) and amplified at SLEC1
(slope 11.2°, relief 434m) — opposite movements, same fire, same input range. bc/obs tells
you whether the BC is in a workable range; the station's terrain amplification factor
determines which way WN moves it. That factor is computable from the DEM and is the next
variable needed to bound the pipeline's per-station uncertainty.

### Finding 4 (architecture): Where correction is required, direction is solved; magnitude is bounded

A two-level correction sets the boundary condition for stations the raw BC mis-sizes:

- **Outer layer**: event-level correction magnitude estimated from obs-free synoptic features
  (700 hPa wind, MSLP gradient, boundary-layer coupling fraction)
- **Inner layer**: station-level correction direction from terrain geometry (relief, slope)
  — **zero false positives**: when geometry indicates amplification, the rule never sends
  the correction the wrong way

Hardest case — **Thomas Fire, WMSC1** (HRRR −35.7 mph at anchor station): the two-level
correction flips the error from **−32 to +11 mph**, recovering the sign.

**Direction is solved.** The +11 mph residual is the current magnitude ceiling —
event-calibrated, not per-station. Closing it requires each station's WindNinja
terrain-amplification factor, which is a computable terrain property but not yet
derivable from obs-free features at the present event count.

A **do-no-harm gate** suppresses corrections where the raw BC is already right: at Woolsey,
the gate correctly blocks a learned adjustment that would otherwise overshoot by +9.2 mph.

---

## Current State

**Validated as a direction-correcting mechanism and at the exposed-ridge niche.**

- **Niche (raw BC):** at above-inversion exposed ridges where HRRR genuinely undershot the BC,
  raw-HRRR-driven WindNinja matches station observations — Camp Fire held-out CBXC1: WN/obs
  1.007 (gentle slope 5.96°, WN decelerated to obs). SLEC1: WN/obs 1.128 (steeper slope
  11.2°, WN amplified past near-obs BC — terrain geometry, not bc/obs, explains the overshoot).
- **Correction (two-level):** direction solved across regimes, zero false positives from the
  terrain-override rule; magnitude event-calibrated, overshooting complex-terrain stations
  by ~10 mph — a bounded, documented residual.
- **Deployable** with a stated uncertainty band: a corrected estimate of "46 mph ± 12" is
  materially more useful than a raw HRRR reading of 10 mph that is off by 36.

Remaining work: magnitude precision (per-station WindNinja amplification factor, computable
offline from terrain) and generalization to new events and higher model resolutions
(RRFS 3 km → 1.5 km ladder).

---

## HRRR Error by Event

**Note on figures below:** these are the **anchor-station** HRRR error, not the event mean.
The two diverge sharply in composite events — ridge stations undershoot while sheltered
valley stations overshoot, and the event mean averages toward zero.

**Regime means (event-level):**

| Regime | N events | Mean HRRR error |
|--------|----------|-----------------|
| Offshore-gradient (Diablo, Santa Ana) | 6 | −3.9 mph |
| Continental downslope (Front Range, Cascades, Chinook) | 3 | +0.5 mph |
| Convective outflow (Iowa, Missoula Jul) | 2 | near-zero, high variance |

**Per-event anchor-station figures:**

| Event | Date | Regime | Stations | Anchor | Anchor HRRR err | Status |
|-------|------|--------|----------|--------|-----------------|--------|
| Camp Fire | Nov 8, 2018 | Diablo | 12 | CBXC1/SLEC1 | −3.6 (CBXC1) · −18.3 (SLEC1) — range across 2 anchors | WN Niche |
| Tubbs Fire | Oct 8, 2017 | Diablo | 7 | HWKC1 | −0.3 mph | HRRR OK |
| Kincade (Ignition) | Oct 23–24, 2019 | Diablo/NW | 10 | HWKC1 | +4.13 mph | Control Case |
| Kincade (Run Day) | Oct 27, 2019 | Diablo/NE | 12 | HWKC1 | +0.1 mph | Control Case |
| Thomas Fire | Dec 4–7, 2017 | Santa Ana | 26 | WMSC1 | −35.7 mph | WN Corrects |
| Woolsey Fire | Nov 9, 2018 | Santa Ana | 16 | WMSC1 | −27.0 mph | WN Nails It |
| Labor Day OR | Sep 7–8, 2020 | Continental | 35 | Multiple | +2.0 mph (event mean) | In Progress |
| Marshall Fire | Dec 30, 2021 | Continental | 8 | BTAC2/SOPC2 | +19.1 / +16.7 mph | In Progress |
| Boulder Chinook | Feb 2021 | Continental | 9 | Front Range | +1.5 mph (event mean) | In Progress |
| Missoula Dec | Dec 17, 2025 | Continental (foehn) | 8 | PNTM8 | −5.8 mph | In Progress |
| Missoula Jul | Jul 2024 | Convective outflow | 18 | Multiple | +0.8 mph (event mean) | In Progress |
| Iowa Derecho | Aug 10, 2020 | Convective outflow | 2 | Iowa RAWS | +0.5 mph | Control Case |

**Note on Kincade Ignition:** anchor HWKC1 shows +4.13 mph (slight HRRR overshoot);
event mean across 10 stations is −3.79 mph. The divergence confirms that gradient
orientation within the offshore regime — not the regime label alone — determines where
the underbias appears.

---

## Per-Event Detail (Card Narratives)

**Camp Fire** — Nov 8, 2018 · Diablo · 12 stations · CBXC1/SLEC1
Two held-out ridge stations, two different stories.

CBXC1 (Colby Mtn): HRRR undershot by 3.6 mph (HRRR/obs 0.875). The 850 hPa BC was 32.9 mph;
WN terrain-resolved it to 29.2 mph — nearly matching obs (WN/obs 1.007). That is the clean
niche: a real HRRR gap, closed by terrain physics.

SLEC1 (Saddleback): HRRR 10m surface undershot by 18 mph (HRRR/obs 0.477) — but the 850 hPa
BC was already 33.5 mph, just 1.5 mph below obs. WN amplified it to 39.5 mph, overshooting
by 4.5 mph (WN/obs 1.128). bc/obs at SLEC1 = 0.96 — right at the ≈1 boundary where the
do-no-harm logic would flag amplification as unnecessary. SLEC1 shows the mechanism's edge,
not its success.

Numbers: CBXC1 obs 29.0 · HRRR 25.4 · BC 32.9 · WN 29.2 · HRRR err −3.6
         SLEC1 obs 35.0 · HRRR 16.7 · BC 33.5 · WN 39.5 · HRRR err −18.3

**Tubbs Fire** — Oct 8, 2017 · Diablo · 7 stations · HWKC1
HRRR resolves Hawkeye Ridge accurately (HRRR/obs ratio 0.997) — no WindNinja correction
needed at this station. A separate finding: a systematic 25–44° direction offset at inland
valley-bottom stations (WISC1, KNXC1), where surface flow channels more northerly than the
850 hPa synoptic flow. Speed is sound at the anchor; inland direction is a documented open
issue. [STATUS: withheld pending direction-mismatch resolution]

**Kincade (Ignition)** — Oct 23–24, 2019 · Diablo/NW · 10 stations · HWKC1
HRRR slightly overshoots anchor Hawkeye Ridge (+4.13 mph at HWKC1) under NW Diablo flow,
while the event mean across 10 stations is −3.79 mph — most valley and canyon stations
undershooting. Demonstrates that the offshore regime alone does not guarantee HRRR underbias
at the anchor — gradient orientation within the regime matters.

**Kincade (Run Day)** — Oct 27, 2019 · Diablo/NE · 12 stations · HWKC1
Strongest control case: pure NE return flow, HRRR error +0.1 mph. HRRR performs well when
the offshore forcing aligns with terrain — the counterpoint that sharpens the
gradient-orientation hypothesis.

**Thomas Fire** — Dec 4–7, 2017 · Santa Ana · 26 stations · WMSC1
Largest single-station error in the database: HRRR undershoots anchor WMSC1 by −35.7 mph.
The two-level correction flips the error from −32 to +11 mph, recovering the sign the flat
correction reversed. Confirms the architecture works in the hardest case. The +11 mph
residual is the magnitude ceiling, not a direction failure.

**Woolsey Fire** — Nov 9, 2018 · Santa Ana · 16 stations · WMSC1
Raw WindNinja reaches near-zero error at WMSC1 with no correction applied. The do-no-harm
gate correctly blocks a learned adjustment that would otherwise overshoot by +9.2 mph —
the case that motivated the gate.

**Labor Day OR** — Sep 7–8, 2020 · Continental · 35 stations · Multiple anchors
Largest event in the database: east-Cascades downslope across three concurrent Oregon fires.
HRRR slightly overshoots (event mean +2.0 mph) — opposite sign to the offshore cases, and
the strongest large-N confirmation of the continental side of the regime split.

**Marshall Fire** — Dec 30, 2021 · Continental · 8 stations · BTAC2/SOPC2
Front Range downslope; HRRR overshoots ridge stations (BTAC2 +19.1 mph, SOPC2 +16.7 mph).
Same terrain-coupling geometry as the offshore ridges, but the bias sign inverts by regime —
confirming that flow coupling must be applied within-regime, not globally.

**Boulder Chinook** — Feb 2021 · Continental · 9 stations · Front Range
Front Range Chinook; near-zero mean HRRR error (+1.5 mph) but high station-to-station
variance. HRRR captures the large-scale Chinook wave structure well but averages over the
elevation-dependent structure along the Dakota Hogback.

**Missoula Dec** — Dec 17, 2025 · Continental foehn · 8 stations · PNTM8
A composite cold-pool-decoupled windstorm. Ridge PNTM8 (7,897 ft) undershoots −5.8 mph
(ridge amplification above the cold pool), while sheltered valley stations overshoot +10 to
+13 mph (HRRR cannot resolve the cold pool). A rare continental case where the ridge
undershoots — a clean demonstration that event means hide opposing terrain responses.

**Missoula Jul** — Jul 2024 · Convective outflow · 18 stations · Multiple anchors
Convective outflow from an afternoon thunderstorm complex. Near-zero mean error (+0.8 mph)
but high station variance — HRRR struggles with the transient outflow boundary. The hardest
regime for terrain downscaling, included as a contrast case, not a primary pipeline target.

**Iowa Derecho** — Aug 10, 2020 · Convective outflow · 2 stations · Iowa RAWS
Flat-terrain negative control. Near-zero HRRR error (+0.5 mph); WindNinja also matches
station observations — no terrain correction needed where there is no sub-grid terrain.
Anchors the baseline and confirms the method does not invent corrections where none are
warranted.

---

## Known Open Issues

- **Tubbs direction mismatch:** 25–44° ENE structural offset at inland stations. Withheld
  pending resolution.
- **Magnitude ceiling:** +11 mph residual at Thomas WMSC1. Requires per-station WN
  amplification factor (terrain-computable, not yet obs-free).
- **8 events In Progress:** Kincade Ign/Run, Labor Day OR, Marshall, Boulder Chinook,
  Missoula Dec/Jul still awaiting WN runs.
- **RRFS resolution ladder:** blocked pending NOAA RDHPCS access.
- **SLEC1 HRRR ratio reconciliation:** earlier analyses (STORMWATCH_MASTER_STATUS.md, hglc1_stage2.py)
  report SLEC1 HRRR/obs = 0.525; the current authoritative CSV gives hrrr_10m_mph=16.7 /
  obs_sus_mph=34.99 = **0.477**. This document uses 0.477. The older scripts predate the
  current peak-hour extraction and should not be cited without reconciliation.

---

*Source: `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html`*
*Database: `Storm_info\hrrr_error_dataset.csv` — 164 active rows*
*Authoritative findings: `Storm_info\STORMWATCH_MASTER_STATUS.md`*
*Version: HindC v1.0 · Commit 1909b35 · 2026-06-17*
