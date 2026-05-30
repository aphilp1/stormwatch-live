---
name: hindcast-bc-framework
description: NeuralGCM-informed design for learned HRRR→WindNinja BC correction pipeline — the forecasting layer that hindcasts are building toward
metadata: 
  node_type: memory
  type: project
  originSessionId: 2ee07a89-8f8b-4d9c-a701-6f15f45f66fd
---

# HRRR→WindNinja BC Learning Pipeline

**Why:** The hindcast library's ultimate purpose is to train a learned map from HRRR synoptic state → WindNinja boundary conditions, replacing hand-tuned BCs (like Camp Fire's 35 mph NE at 700 hPa) with a systematic, generalizable method for forecasting erratic wildland fire winds.

## Why 700 hPa is the Right BC Reference Level
700 hPa (~3000m geometric, but variable) is above HRRR's terrain-blindness (corrupted 10m field)
but low enough to interact with western US mountains. It's the classic fire-weather level for
downslope/offshore events (Diablo, Santa Ana, foehn). The 8 mph HRRR 10m wind at Jarbo Gap is
the *wrong field*; the 25 mph 700 hPa wind is the *honest driver*. That contrast is the
conceptual spine of the whole pipeline.

**Pressure-surface vs fixed height — critical nuance:**
700 hPa breathes with the airmass: cold column ~2700m, warm column ~3200m. Where domain terrain
approaches that altitude, HRRR extrapolates 700 hPa values below-ground — physically meaningless.
- Camp Fire domain (~1000m max): SAFE, 2000m margin
- Missoula (ridges ~2300-2500m): MARGINAL — check HGT:700 mb, especially in cold airmass
- Santa Ana (San Gorgonio 3506m): HIGH PEAKS ABOVE 700 hPa — guard required, exclude high cells

**Standard guard for high-terrain domains (implement in all Case 8+ scripts):**
Pull HGT:700 mb alongside UGRD/VGRD. Flag/exclude domain cells where 700 hPa
geopotential height is within 200m of terrain. Report fraction of excluded cells.

**Long-term refinement (Phase 2+):**
Physically correct BC = "free-atmosphere wind at ridgetop geometric height," not "700 hPa."
When 700 hPa gives systematic BC errors in a domain, sample HRRR at the model level
nearest actual ridgetop elevation instead. Feature name: `ridgetop_level_wind` (replaces
`w700_speed_mph` for steep terrain domains). Not needed for Camp Fire; relevant for Missoula/SoCal.

## HYDRAULIC-JUMP METHOD BOUNDARY (Brewer & Clements 2020 — from Camp Fire paper)

WindNinja is a mass-conserving DIAGNOSTIC solver. It does NOT produce hydraulic
jumps or rotors (non-hydrostatic, transient features). This defines a hard method
boundary that is separate from BC quality.

**Testable prediction:** Stations WN cannot fit should cluster spatially with where
WN/WRF shows jump/rotor structure. Stations in smooth flow should fit; stations
under rotors will structurally never fit regardless of how good the BC is.

**Station-QC rule:** "Near modeled hydraulic jump" = METHOD-OUT-OF-SCOPE, not a
fit failure. The residual at such a station cannot be closed. Do not chase it.
Example: Stirling City (Camp Fire) sits under a documented rotor — explicitly dropped.

**Implication for mechanism_classifier:** "Near modeled hydraulic jump" is a
diagnostic that explains low evidence_fraction or unfittable stations, distinguishing
"method is wrong" from "station is in genuinely erratic flow no steady-state solver
can capture." This should inform future classifier extensions.

**For erratic-wind forecasting thesis:** The paper confirms the sub-grid jump/rotor
structure is real, co-locates with where surface observations go haywire, and is
precisely the scale HRRR cannot resolve. This IS the thesis, stated in peer-reviewed
literature. WindNinja resolves the smooth terrain amplification; hydraulic jumps are
out of scope for any diagnostic solver and require WRF/WRF-SFIRE.

## HONEST PROGRAM ASSESSMENT (Opus 2026-05-30)

Four headline candidate findings, zero survivors:
  1.42x amplification constant -- withdrawn (coordinate artifact)
  +9.8 mph speed bias -- collapsed to +3, then consistent-with-zero
  Timing thesis -- broken on Camp Fire anchor, all candidates killed
  Cross-case "all catastrophic at 25 mph" -- selection effect

THIS IS NOT FAILURE. Each killed finding taught something real:
  - Coordinates dominate amplification (spatial gradients are huge)
  - HRRR is a good BC for low-terrain downslope (VALIDATES pipeline premise)
  - Timing mechanism lives in surface-vs-aloft lag, not 700 hPa
  - Method has hard boundary at hydraulic jumps

THE SINGULAR TEST THAT MATTERS:
Does BC-corrected WindNinja beat raw HRRR at terrain stations out-of-sample?
This is RAWS-gated. Currently unrunnable. Everything else is infrastructure.

CRITICAL PATH: RAWS access (Synoptic research tier, WRCC outreach) is the
actual gate between "impressive apparatus" and "validated science." Treat
this as the most important unresolved item, not another engineering build.

Confidence engine + surrogate WindNinja = real, valuable, build them.
But they are INFRASTRUCTURE FOR TESTING, not the test itself.

## AUDIT FINDINGS — 2026-05-30 (coordinate correction)

**The 1.4x terrain amplification "constant" is WITHDRAWN.**
All three data points had problems:
- Camp Fire Jarbo 1.42x: wrong coordinates (39.977 → correct 39.736). At correct coords: 1.12x.
- Missoula PNTM8 1.40x: had coord correction (46.876→47.041). Ratio not re-derived at correct coords yet. Could move either direction.
- Thomas Topa Topa 1.44x: unobserved prediction, BC from assumed ratio. Never validated.
Do NOT cite this as a finding until re-derived at verified coords with consistent conventions.
Amplification ratio is EXTREMELY sensitive to coordinates (huge spatial gradients are the premise).
Coordinate verification is a permanent precondition for every ratio reported.

**The +9.8 mph HRRR speed bias is largely withdrawn.**
At correct Jarbo coords with correct gust-factor convention (sustained vs sustained):
- WN at 35 mph BC → Jarbo sustained 39.3 mph vs observed 32 mph (+23% overshoot)
- WN at 25 mph BC → Jarbo sustained 28.8 mph vs observed 32 mph (-10% undershoot)
- Optimal BC ≈ 28 mph. HRRR 700 hPa domain mean = 25.2 mph. Real gap ≈ +3 mph.
Treat +3 mph as consistent-with-zero: one station, one event, interpolated result.

**CORRECTED thesis (stronger, not weaker):**
"HRRR 700 hPa is a near-unbiased BC for LOW-TERRAIN downslope events; WindNinja adds
real sub-1km terrain structure that HRRR structurally cannot resolve." Both BAMS papers
independently confirm this. Value-add was never fixing broken HRRR — it's the terrain detail.
Where real BC bias may still exist: HIGH-TERRAIN regime (Missoula, Thomas) where 700 hPa
breaks down. That's where the terrain-height guard lives. Camp Fire tells us where the
correction ISN'T needed, which is equally valuable.

**Next step for amplification:** Pull Brewer & Clements 2020 Table 1 (open access:
mdpi.com/2073-4433/11/1/47) for the 7-station network with verified coords + observed values.
Re-derive Camp Fire ratio at those coords. Then re-derive Missoula and Thomas independently.

## The Core Principle (from NeuralGCM analogy)
Correct WindNinja's *inputs* (BCs), not its *outputs*. Keep the mass-conservation solver as backbone. The learned layer predicts the forcing; WN solves the terrain field. This ensures every corrected field is mass-consistent by construction.

**What does NOT transfer from NeuralGCM:** WN is diagnostic/steady-state, not prognostic. No online training through the solver. The BC correction is trained offline.

## Pipeline Structure

### Inner Loop — Label Generation (per event)
Automated version of the Camp Fire hand-tuning:
1. Sweep WN BCs (speed × direction × stability class)
2. Score each candidate against RAWS network (gust-factor-aware, regularized toward HRRR prior)
3. Optimal BC = label y* for that event-hour

### Outer Loop — Learned Map
Train regressor f: HRRR state → y* (residual, not raw BC)
- At inference: HRRR → f predicts BC → WN solves → terrain wind field
- Observations only used for label generation and evaluation — no circularity

## Residual Target (critical design choice)
Learn the *gap* between raw HRRR 700 hPa wind and optimal BC:
- Δspeed = optimal_speed − HRRR_700hPa_speed
- Δdir = encode as (sin, cos) pair, recover with atan2 — NEVER regress raw degrees (0/360 wrap)
- Optionally: stability class output (since WN's stability flag directly affects momentum solve)
- Baseline: Δ=0, i.e., "just use raw HRRR 700 hPa as BC" — every learned version must beat this

## Feature Set (HRRR synoptic state, ordered by expected importance)
1. 700/850/500 hPa wind speed + direction — primary driver and residual baseline
2. MSLP gradient + 700 hPa geopotential-height gradient — pressure-gradient force for gap/downslope
3. Low-level stability — lapse rate, ridgetop inversion, dimensionless mountain height/Froude proxy — critical for amplification and hydraulic jumps
4. Cross-level shear (700–850, 700–500) — well-mixed vs decoupled
5. Temperature advection / frontal signature + BL height — Missoula cold-frontal case
6. **Spatial gradients of all fields** (NeuralGCM gradient-input lesson): feed derivatives across domain, not point values

## Small-N Constraints
- Only 7 fires = 7 events. Mitigations:
  1. Per-hour slicing: each forecast hour = separate training example
  2. Non-fire strong-wind events with RAWS coverage count (hundreds available)
  3. Start linear: Δspeed ~ linear(700hPa speed, MSLP gradient, stability) — probably 80% of value

## Scoring Subtleties
- **Gust factor:** WN outputs sustained; RAWS reports gusts. Apply gust factor (≈1.3–1.7 terrain/stability dependent) consistently. Camp Fire used ~1.0 implicitly — this is unresolved and is the biggest lever on recovered BC speed.
- **Regularize inner solve:** Penalize BCs that drift far from HRRR 700 hPa prior to prevent overfitting sparse station networks.

## Validation
Leave-one-event-out: hold out whole events (hourly slices within events are correlated — random splits leak).

## How Each Hindcast Case Contributes
| Case | BC-correction role |
|------|-------------------|
| Camp Fire (4) | One labeled (HRRR→BC) pair already — the 35 mph hand-tune IS the label |
| Marshall Fire (3) | BC was implicitly right — need to record WHAT in HRRR state produced good BC |
| Oakland Hills (7) | Low terrain amplification — lower bound on Δ |
| Iowa Derecho (5) | Flat terrain, Δ≈0 — confirms function behavior at low terrain complexity |
| Boulder 1972 (6) | WN=0x (resonant trapped waves) — OUTSIDE BC-correction envelope; failure-mode classification, not training |

## Concrete First Step
Pull HRRR 700 hPa archive for Camp Fire via herbie. Compare raw HRRR aloft wind vs hand-tuned 35 mph NE:
- If close → residual framing validated; build linear map
- If far → gap is the finding; stability/gradient features carry signal → prioritize those features

## BC Sweep Code Status
Inner-loop BC sweep label generator was designed and built in a separate Claude.ai session — **NOT saved to local filesystem**. Needs to be rebuilt at `C:\Users\aphil\Documents\Stormwatch\bc_sweep.py`.

**How to apply:** Each new hindcast case should include a BC audit section: what HRRR-state variables were present, what BC was used, what gap remained. This is the structured label for the training set.
