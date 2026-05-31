# Stormwatch — Erratic-Wind Hindcast Toolkit: Claude Code Handoff

## What this is

Three standalone Python modules that form the analysis backbone for a research
program: **using hindcasts of extreme fire-wind events to improve sub-1km wind
forecasts that drive erratic/explosive fire behavior.** They were written and
self-tested in a sandbox that CANNOT run herbie, WindNinja, or the HRRR data
buckets. Your job in Claude Code is to replace the three mock/stub "seams" with
real data and solver calls. The logic is done and tested; the I/O is not.

Files (all in this directory):
- `mechanism_classifier.py`   — sorts each event into one of 4 physical mechanisms
- `bc_label_generator.py`     — inner loop: finds the optimal WindNinja boundary condition per event
- `bc_outer_trainer.py`       — outer loop: learns HRRR-state → boundary-condition, validated leave-one-event-out

Dependencies: classifier = stdlib only; trainer = numpy only; label generator =
stdlib only. No other installs needed for the logic itself (herbie/WindNinja are
separate, called through the seams).

---

## The program in one paragraph

Wind is the weakest input to fire-spread models, and the dangerous wind errors
are forecast BUSTS decomposed into three channels: **timing** (shift arrives
early/late), **speed** (over forecast), **direction** (outside forecast). The
achievable improvement depends on the EVENT MECHANISM, so every event is first
sorted into one of four bins. Only the first two are in scope for the WindNinja
terrain-downscaling approach:

1. SYNOPTIC_TERRAIN  — gradient flow channeled by terrain. WindNinja: HIGH. Bust axis: speed.
2. PBL_TRANSIENT     — frontal shift / LLJ mix-down. WindNinja: PARTIAL. Bust axis: timing+direction.
3. CONVECTIVE_OUTFLOW— downburst/derecho. WindNinja: NONE. (out of scope)
4. FIRE_GENERATED    — pyroconvection/plume. WindNinja: NONE. (coupled-model problem)

Core methodology (unchanged from the existing Stormwatch philosophy):
**synoptic models say WHEN dangerous flow arrives; WindNinja says WHERE on the
terrain it will be worst.** Hindcasting known events is the learning loop:
validate on the past to earn trust in the future.

Key architectural decision behind the two-loop design (the "NeuralGCM lesson"):
correct the INPUT to the physics solver (the boundary condition), not its
OUTPUT. A learned map predicts the BC; WindNinja then solves, keeping every
field mass-consistent on the terrain. Do NOT replace WindNinja with a neural net.

---

## Reference facts the tools are built around (from prior hindcast work)

- Camp Fire ignition: Pulga/Poe Dam (39.56, -121.44), 2018-11-08.
- Camp Fire RAWS: Jarbo Gap observed 52 mph gust. HRRR 10m ~8 mph (blind to canyon).
- Hand-tuned optimal BC: 35 mph NE at 700 hPa. WindNinja then gave Jarbo 49.7 (+42%),
  Concow 67.3 (+92%), Paradise 53.8 (+54%), Pulga 60.5 (+73%). Concow +92% is an
  open finding (strongest amplification, no station to validate against).
- Missoula network: KMSO (valley ASOS), Point Six (ridge RAWS NE), Lolo TS897
  (valley RAWS SW), Blue Mountain BLMM8 (ridge RAWS SW).
- Missoula Dec 17 2025 cold-frontal = the PBL_TRANSIENT validation case.
- Missoula Jul 2024 derecho = CONVECTIVE_OUTFLOW, correctly ruled OUT for WindNinja.

Data-access lessons already learned (save yourself the rediscovery):
- GCS & AWS HRRR buckets are BLOCKED in the Claude.ai sandbox → herbie must run
  in Claude Code. This is the whole reason these are stubs.
- Synoptic free tier: no historical RAWS. WRCC blocks data >30 days without an
  access code (wrcc@dri.edu). ERA5 at 31km is too coarse for terrain jets.

---

## FILE 1 — mechanism_classifier.py

**What it does:** rule-based (NOT ML — N is tiny and you need explainability)
classifier. Input is an `EventDiagnostics` dataclass; output is a `MechanismResult`
with the primary mechanism, per-mechanism scores in [0,1], an `evidence_fraction`
(how much of each signature was actually evaluable), MIXED and LOW_CONFIDENCE
flags, the WindNinja applicability verdict, and the primary bust axis.

**The seam to replace:** the `EventDiagnostics` fields. Currently hand-set in
`_archetypes()`. Each field has an inline comment naming its data source. Fill
them from:
- HRRR / HRRRCast: `w700_speed_ms`, `pgf_norm`, `cross_ridge_flow`, `forcing_sustained`
- sounding or HRRR pseudo-sounding: `low_level_lapse_ckm`, `critical_level`
- MRMS / HRRR / lightning: `max_reflectivity_dbz`, `max_cape`, `lightning_present`
- RAWS time series: `wind_shift_deg`, `shift_duration_min`, `temp_drop_c`,
  `pres_rise_hpa`, `shift_near_sunrise`, `gust_to_sustained`, `blast_duration_min`
- GOES + exclusion logic: `goes_cloud_top_c`, `plume_collocated_with_fire`, `local_wind_violent`

**Leave fields None if you don't have them** — the classifier skips missing
evidence rather than guessing, and reports lower evidence_fraction.

**Calibration:** every number lives in the `THRESHOLDS` dict at the top. They are
physically-motivated STARTING values, not truth. Tune against the real library.

**Integration output:** `to_hindcast_block(result)` returns a dict to attach to
each HindcastEvent record (P2 schema).

**Verify after wiring:** the four `_archetypes()` must still classify as labeled
(camp→SYNOPTIC_TERRAIN, missoula_front→PBL_TRANSIENT, derecho→CONVECTIVE_OUTFLOW,
plume→FIRE_GENERATED). Note the pyroCb subtlety: convective indicators are gated
on `plume_collocated_with_fire` so fire-made convection doesn't read as an
ambient storm.

---

## FILE 2 — bc_label_generator.py  (INNER LOOP)

**What it does:** for ONE event, sweeps WindNinja boundary conditions
(speed × direction × stability), scores each against the RAWS network, and
returns the BC that best reproduces observations. That optimal BC is the
training LABEL for File 3. It emits labels in RESIDUAL form (delta vs the raw
HRRR 700 hPa wind) via `as_label_dict()`.

**The seam to replace:** `mock_solver(speed, direction, stability)`. Replace with
a function that calls your `get_terrain_wind` MCP tool with that BC and returns
`{station_id: sustained_mph}`. Pass it as `solver=` to `sweep_bcs`. Delete
`mock_solver` and `_self_test` once real.

**Also fill in:**
- `OBSERVED_GUSTS` — real RAWS peak gusts per station (only Jarbo Gap=52 is in
  now; the other three are None and excluded from scoring). **You need the other
  stations' gusts or the optimum is poorly constrained.**
- `HRRR_PRIOR_SPEED` / `HRRR_PRIOR_DIR` — the raw HRRR 700 hPa wind over the
  domain, from herbie. (Placeholder is the 35 mph / NE hand value.)

**Two judgment calls flagged in-file — decide consciously, don't accept defaults:**
1. `GUST_FACTOR` defaults to **1.0**, which reproduces the existing "Jarbo 49.7 vs
   52, within 4%" result (sustained output compared directly to observed gust). A
   physical gust factor for exposed ridges is ~1.3–1.7. If that's correct, the
   recovered BC speed drops. **This is the single biggest lever on the answer.**
2. `REG_SPEED`/`REG_DIR` regularize the optimum toward the HRRR prior so a sparse
   station net doesn't overfit the BC to where sensors sit. Set 0 to disable.

**The day-one experiment:** once herbie pulls the Camp Fire 700 hPa field, run
`day_one_experiment(...)`. It compares raw-HRRR-as-BC against the swept optimum.
Small residual → residual framing validated, build the linear map. Large residual
→ the gap IS the finding (aloft wind alone doesn't explain terrain channeling;
prioritize stability/pressure-gradient features). Either outcome is informative.

**Caveat:** the mock's amplification factors are reverse-engineered from your own
35 mph result, so the self-test recovering 35 is partly circular — it proves the
SEARCH works, not that 35 is right. Real WindNinja confirms the latter.

---

## FILE 3 — bc_outer_trainer.py  (OUTER LOOP)

**What it does:** learns f: HRRR synoptic features → BC residual
(delta_speed, delta_dir_sin, delta_dir_cos). Validates with LEAVE-ONE-EVENT-OUT
(LOEO) — holds out whole events, never random splits (hourly slices within an
event are correlated and would leak). Always compares against the **delta=0
baseline** ("just use raw HRRR aloft wind as the BC"); the learned map must beat
that baseline by a MARGIN to count as signal.

**The seam to replace:** the `"features"` dict on each record. Currently
synthetic (`_make_synthetic`). Populate from real HRRR fields via herbie. The
feature schema is `ALL_FEATURES` (priority-ordered); `DEFAULT_FEATURES` is the
deliberately-small starting subset (700hPa speed, MSLP gradient, lapse rate).
**Do not add features faster than you add events** — that overfits at small N.

**Input format** (what `load_samples` expects per record):
```
{
  "event": "camp_fire_2018",            # LOEO grouping key
  "features": {"w700_speed_mph": ..., "mslp_grad": ..., "lapse_rate": ...},
  "delta_speed_mph": ...,               # from as_label_dict (File 2)
  "delta_dir_sin": ..., "delta_dir_cos": ...,
  "hrrr_prior_speed_mph": ..., "hrrr_prior_dir_deg": ...
}
```
So the pipeline is: File 2 emits the label dict → you add `"event"` and
`"features"` → list of these → File 3.

**Direction handling:** never regress raw degrees. sin/cos targets, atan2
reconstruction, unit-renormalized at inference. (Already implemented.)

**Calibration:** `verdict()` margins (0.5 mph, 2°) define "bigger than noise."
Tune to your label RMSE floor.

**Verify after wiring:** the two self-tests must still behave — planted signal →
SIGNAL verdict; pure noise → NO SIGNAL. A trainer that doesn't pass the noise
test is dangerous at this N.

**Honest limitation to keep in mind:** 7 events under LOEO means train-on-6,
test-on-1. A SIGNAL verdict means "promising, gather more events," not "deploy."
Non-fire strong-wind events are valid training data and the cheapest way to grow N.

---

## Recommended build order in Claude Code

1. **herbie/HRRR data-pull layer first.** It feeds two of the three files and is
   the thing the sandbox couldn't do. Get HRRR 700 hPa archive winds over the
   Camp Fire domain (2018-11-08). This is the existing "immediate next step."
2. **Wire File 2's solver seam** to `get_terrain_wind`; fill OBSERVED_GUSTS and
   the HRRR prior. Settle the GUST_FACTOR question explicitly.
3. **Run the day-one experiment.** This is the first real result and tells you
   which way the whole residual-framing assumption falls.
4. **Wire File 1** by populating EventDiagnostics from HRRR/sounding/MRMS/GOES/RAWS
   for the events you have; confirm archetypes still classify.
5. **Wire File 3's features** from herbie; build the label set across events;
   run LOEO. Only then consider more features or capacity.

## Not yet built (the open thread)

The **timing-bust detector** (the "WHEN" axis). None of the three files touch it.
The approach: run the downscaling across a TIME SEQUENCE of synoptic states and
compare the modeled transition to when RAWS actually logged the shift; use a
cheap synoptic ensemble (e.g. HRRRCast's 9-member ensemble) for arrival-time
error bars. HRRRCast's role is UNCERTAINTY QUANTIFICATION of the forcing, NOT
resolution (it inherits HRRR's 3km terrain blindness). Build this after the
speed/direction loop is working end-to-end.
