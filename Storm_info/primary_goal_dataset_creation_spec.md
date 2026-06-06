# Stormwatch — Primary Goal & Dataset Creation Spec

> ## ⇒ NEXT ACTION FOR CLAUDE CODE (read first)
> **PHASE A — the observations task. Do this fully before anything else.**
> 1. Write the four current docs into `Storm_info` and commit (this file,
>    `da_ideas_integration_note.md`, `DART_AND_EXTERNAL_RESOURCES.md`, the reframe doc).
> 2. Build `hrrr_error_dataset.csv` per PART 2 below: **QC first**, one row per usable
>    station-event across **ALL 172 RAWS files / 12 events** (not the handful scored so far).
>    Include every column incl. the era/regime/QC/cluster/representativeness tags.
>    Mark `NEEDS_HRRR_TS` / `NEEDS_DEM` / `NEEDS_WN` where data is absent. **FIT NOTHING.**
> 3. **Report the complete-row count PER CHANNEL** (speed / direction / arrival) AND a
>    correlation-aware count (co-located stations on shared terrain counted once).
> 4. STOP and report. That row count is the decisive unknown — it determines whether a signal
>    is huntable yet or whether more extraction (esp. cell-level HRRR time series for the
>    arrival channel) is needed first. Do NOT start Phase B analysis until this is done.
>
> Everything below is the full spec. The DART/BNRH/HDW external resources and post-signal
> design ideas live in the two companion docs — do not act on them during Phase A.


**The single source for WHAT we are doing and the NEXT thing to build.**
Written 2026-06-01. This is the BUILD source of truth. Companion docs (distinct jobs, do NOT
supersede this one):
- `da_ideas_integration_note.md` — POST-SIGNAL DESIGN + sharpened-goal detail (forward-design
  ideas, the BNRH/mixed-distribution future capability, the three-lever better-starting-point
  detail). Consult at the design/output stage.
- `DART_AND_EXTERNAL_RESOURCES.md` — standalone tracking: DART/QCEFF/BNRH, people (Anderson,
  Grooms), the HDW baseline, fire-wind landscape. Consult when positioning the project or at
  the output stage.
Build from THIS file. Also read alongside `STORMWATCH_MASTER_STATUS.md` (full record) and
`CLAUDE_CODE_RESTART.md` (live next step). Earlier framing: reframe doc (2026-05-31), history.

---

## PHASE ORDER (do not skip ahead)
**PHASE A — OBSERVATIONS TASK (do this FULLY first).** Complete the systematic pass over
ALL observations: every one of the 172 usable RAWS files across all 12 events, QC'd and
built into `hrrr_error_dataset.csv` per Part 2. This is the foundation. Do NOT move to the
refined task working from only the handful of stations scored so far. Finish the whole
observations pass — including the row-count report per channel — before any analysis.

**PHASE B — REFINED TASK (only after Phase A is complete).** Diagnose WHY HRRR misses the
terrain-driven winds, and develop the better BC-sourcing rule for WindNinja (Part 1 mission).
The refined questions are exciting and will tempt early analysis — resist until the
observations task is done across all 172 files. The dataset is what makes Phase B honest.

---

## PART 1 — THE PRIMARY GOAL

### Mission (the plain-language version)
Forecast the **erratic, terrain-driven winds** that make wildfire behavior dangerous, by
answering two physical questions:
1. **WHY does HRRR miss these winds?** (diagnosis — terrain-resolution, inversion mislevel,
   terrain rotation are the candidate failure modes, all already evidenced in our results.)
2. **How do we give WindNinja a BETTER STARTING POINT (initialization)** so its downscaled
   wind avoids HRRR's terrain-blind failure modes? (constructive deliverable.) This has
   THREE LEVERS, cheapest → deepest, pursued as ONE research strand:
   - **(a) Selection** — best level / hour / location from HRRR (ERA5 work already supports).
   - **(b) Source substitution** — where HRRR is terrain-blind, feed a different/blended
     source: ERA5 at certain levels, multi-level blend, an upstream-undeflected sample, or
     RTMA / mesonet-anchored fields.
   - **(c) Initialization MODE** — *which* WindNinja init is used: domain-average wind vs.
     2D gridded field vs. point-observation-informed. This determines how much HRRR
     terrain-blindness is inherited BEFORE WindNinja runs; it has been treated as fixed and
     should be a variable.

SCOPE BOUNDARY: this is the **wind-driven** class of erratic fire behavior (strong ambient,
terrain-modulated winds). The **plume-driven** class (the fire generating its own winds via
heat feedback, up to ~10x ambient) is **OUT OF SCOPE** — it requires a coupled
fire-atmosphere model (CFBM/WRF-Fire), not WindNinja+HRRR.

IMPORTANT — "better starting point" means SELECTION / SOURCING / INIT-MODE, not CORRECTION.
All three levers (a/b/c above) are about WHAT YOU FEED WindNinja — a physically-sourced
input. None is the learned additive BC *correction*, which was already FALSIFIED (single- and
multi-station; do-not-revive). Source substitution (b) is the one that could drift back
toward "correction" — the line: choose a physically-sourced input, do NOT learn a fit to obs
and add it.

BASELINE TO BEAT: the Hot-Dry-Windy Index (HDW, USDA FS) is the incumbent fire-wind tool; it
uses raw model wind and ignores terrain-resolution error. "Does this add skill over HDW?" is
the benchmark question.

### The question (statistical form — how we operationalize the above)
**What observable signals predict that HRRR will BUST a wind forecast — in speed,
direction, or arrival time — and can that prediction be used to flag or bound the error?**

This is the measurable version of "why does HRRR miss these winds" — the dataset answers it.

This is forecast-ERROR prediction, not wind prediction. It only requires HRRR's errors
to be *predictable*, not for any model to be perfectly accurate — a weaker, more
achievable, and more useful claim than point accuracy.

### Why this framing
- A fire-weather forecaster does not need a perfect number. They need to know **when not
  to trust HRRR and how it will be wrong**. That is the product.
- Errors can be predictable even when neither HRRR nor WindNinja is individually accurate.
- Classical data assimilation assumes model error is random and Gaussian (captured by a
  covariance). This project exists because in complex terrain **HRRR's error is
  systematic, terrain-keyed, and structural** — so a learned, feature-based predictor is
  the right tool and a Kalman filter is not. This sentence is the justification for the
  whole approach.

### The core bet
The **HRRR↔WindNinja disagreement** is a free, observation-independent signal available
at forecast time. Where WN and HRRR diverge (and how) should predict where and how HRRR
busts. WindNinja is used as a **discrepancy detector**, not a truth source. Terrain and
synoptic state are the other predictors.

### The three bust channels
| Channel | Predictor (knowable at forecast time) | Truth (RAWS) | Signature seen so far |
|---|---|---|---|
| Speed | WN/HRRR speed ratio at the cell; terrain amplification | obs sustained vs HRRR | Saddleback: HRRR 0.525 (undershoot at exposed ridge) |
| Direction | WN−HRRR dir delta; terrain rotation | obs vector-mean dir | WISC1 Δ36°, HGLC1 Δ46°, Jarbo (summit/canyon rotation) |
| Arrival/Timing | WN-arrival vs HRRR-arrival across a time sequence | obs onset/peak hour | HMRC1, CUUC1 (events peaked overnight, missed at 12Z) |

### Two steps, order non-negotiable
1. **FIND THE SIGNAL.** Measure HRRR's actual error per channel against RAWS truth, then
   ask what *predicts* it (terrain, synoptic state, WN-discrepancy).
2. **USE IT** (only if step 1 finds a real, out-of-sample signal). The use is to flag
   untrustworthy cells and bound the error ("HRRR says 25 mph NNE, but this is a rotating
   summit — expect N, possibly higher, low confidence"), feeding `confidence_field.py`, AND
   to inform the better-WindNinja-starting-point work (Part 1 Q2). NOTE: this does NOT mean
   reviving the learned additive BC *correction* — that was FALSIFIED (see Current State and
   the IMPORTANT note above). "Use it" = flag/bound + better input sourcing, not correct.

### The hard constraint
You cannot find a signal in ~10 station-events × 3 channels — anything found is noise.
The first real move is building the error dataset large enough to hunt in, across all
**172 usable RAWS files / 12 events**. The effective held-out unit for generalization is
~12 events/regimes, NOT 172 stations — the 172 is a comfort illusion.

### Current state (carry-over)
- Old point-accuracy "ridge niche": confirmed n=2 (Camp CBXC1 1.007, SLEC1 1.128),
  DEM/CRS-verified. Becomes the speed-channel/exposed-ridge/unrotated-flow special case
  of this frame. Cross-event confirmation still open.
- BOTH BC corrections (single-station, multi-station) FALSIFIED — do not revive.
- Terrain rotation that broke the point test (Kincade summits, Jarbo) is, in this frame,
  a DIRECTION-bust predictor — the same physics is now a signal.
- ERA5 validated as a trusted BC source. 850 hPa is the working BC level across 3 events
  via 3 mechanisms (inversion / transition-timing / rotation); rule = pick level+hour
  where BC direction matches observed flow.
- Fixed-12Z scoring is a known limitation; measure at each event's pre-registered peak
  window (overnight peaks are missed otherwise).
- HRRCast → queued for BC_SENSITIVITY (uncertainty, not accuracy) and arrival-time
  spread, AFTER the signal work.

---

## PART 2 — DATASET CREATION SPEC (PHASE A — the next thing to build)

> This dataset is the FOUNDATION, not the final deliverable. It's what makes the Phase B
> mission (diagnosis + better WindNinja starting point) honest. Build it, report row counts,
> stop.

### Identity: this is a DEPARTURE DATABASE
`speed_err = hrrr − obs` is the data-assimilation innovation/departure. DA assumes
departures are zero-mean noise; our entire edge is that in complex terrain they are NOT
zero-mean, and the systematic part is the signal. Bin departures by terrain, regime,
channel.

### File: `hrrr_error_dataset.csv`
One row per usable station-event across ALL 12 events (the 172-file usable set from
`raws_inventory.csv`, not just the handful scored so far).

### Columns

**ERROR — the target (truth from RAWS):**
- `speed_err` = hrrr_10m_mph − obs_sus_mph (own-station gust factor), plus `speed_ratio`
- `dir_err` = circular(hrrr_10m_dir − obs_vector_mean_dir)
- `arrival_err` = hrrr peak/onset hour − obs peak/onset hour
  (mark `NEEDS_HRRR_TS` where the cell-level HRRR time series isn't pulled yet)

**CANDIDATE PREDICTORS — obs-independent, forecast-time:**
- terrain: `elev_m`, `slope`, `aspect`, `relief_1km`, `terrain_class`
  (exposed_ridge / canyon_gap / valley / summit_rotating / sub_inversion), `dem_verified`
- inversion: `elev_vs_inversion` (above / below / near the event lid)
- synoptic: `bc_dir`, `bc_speed`, `bc_level`, `lapse_stability`, `mslp_grad`
- **discrepancy (the key signal):** `wn_minus_hrrr_speed`, `wn_minus_hrrr_dir` at the cell

**NONSTATIONARITY TAGS — add NOW, retrofitting is painful:**
- `hrrr_era` — HRRR version / date-era. The bias being learned is not the same model
  across eras; a generalization failure could be pure version mismatch.
- `synoptic_regime` — diablo_offshore / santa_ana / frontal_passage / chinook / derecho /
  etc. A signal can look stationary only because one regime dominates the sample.

**QC + THINNING TAGS — from the operational obs-processing pipeline (Feng & Pu; the
standard Ingest→TimeWindow→QC→BiasCorrection→Thinning/Superobs→Departures chain).
Our dataset IS the "Departures" (O−B) endpoint of that pipeline; these two columns
formalize the QC and Thinning stages we were doing ad hoc:**
- `qc_flag` + `qc_reason` — named, RECORDED exclusion status, not silent filtering.
  Values e.g. KEEP / DROP_NETWORK_TYPE (USGS/CoCoRaHS/COOP) / DROP_NEAR_CALM
  (denominator artifact, peak sustained < ~8 mph) / DROP_BAD_SITING /
  DROP_DEM_UNVERIFIED / CAUTION_GAPPED. Every excluded row keeps its reason so the
  blacklist is auditable (operational "gross checks + blacklists").
- `spatial_cluster_id` — within each event, group stations that are spatially close
  (same drainage / within ~a few km) into a cluster id. Stations in one cluster see
  CORRELATED flow and are NOT independent observations — this is the operational
  "thinning / superobs: reduce correlation + cost" step. In the signal-hunt, down-weight
  or thin within-cluster duplicates so a single drainage doesn't masquerade as many
  independent points. Reinforces that effective N << 172.

**REPRESENTATIVENESS TAG — the confound that could fake the whole result:**
- `repr_error_flag` — an estimate of point-sensor-vs-3km-grid mismatch, computed from the
  DEM (terrain roughness / elevation variance within the station's grid cell). This is the
  R term in `departures = HBH^T + R`: part of every departure at a rugged site is the
  point-vs-grid representativeness error, NOT HRRR being wrong. It is TERRAIN-DEPENDENT and
  worse exactly where the terrain signal lives, so it is COLLINEAR with the signal we're
  hunting. (DEM-roughness is a proxy for the rigorous Desroziers R-estimate, which needs an
  analysis step / x_a the pipeline doesn't have yet — Desroziers is parked as a later
  self-consistency check.)

### Construction rules
- Compute only what is real. Mark `NEEDS_HRRR_TS` / `NEEDS_DEM` / `NEEDS_WN`. No guessing.
- This is dataset construction ONLY — fit nothing, claim no signal.
- **Report the complete-row count PER CHANNEL** (speed / direction / arrival). This
  reality check decides whether a signal is huntable yet or whether more extraction is
  needed first.

### Analysis-ordering rules (for AFTER the dataset exists — bake into the plan now)
0. **SEPARABILITY PRE-CONDITION (run before crediting ANY terrain signal).** The terrain
   signal and the representativeness error (`repr_error_flag`) both rise with terrain
   ruggedness — they are collinear. Before claiming "terrain predicts the bust," show the
   terrain–departure relationship is LARGER THAN and SEPARABLE FROM the
   terrain–representativeness relationship (e.g. does the departure exceed what
   point-vs-grid mismatch alone would produce? does the signal survive controlling for
   `repr_error_flag`?). If the bust signal is really just representativeness mismatch, there
   is no forecast-error finding. This is the deepest threat to the whole approach — gate on
   it first.
1. Held-out unit is the **regime/event (~12)**, not the station (~172). Honest
   generalization test = leave-one-REGIME-out (or leave-one-HRRR-era-out) where N allows,
   not just leave-one-event-out.
2. **Test terrain-features-alone FIRST.** Terrain is the stationary part (a canyon is a
   canyon in every era/regime). The WN-discrepancy predictor rides partly on HRRR's
   version-dependent behavior and is more fragile — only credit it AFTER checking whether
   terrain alone already carries the signal.
3. **Correlated predictors → overfitting (operational lesson: "ignoring correlated
   errors leads to overfitting and noisy increments").** Terrain features (slope, relief,
   elevation) move together, and the WN-discrepancy is correlated with the terrain that
   produces it. Throwing all predictors in as if independent will manufacture a "signal"
   that is a correlation-structure artifact. Start with FEW, terrain-only predictors;
   add capacity only as N (in regimes/events) supports it. Thin spatially-clustered
   stations (`spatial_cluster_id`) before fitting so a single drainage isn't counted as
   many independent observations.
4. State any clustering as a HYPOTHESIS; confirm out-of-sample before calling it a
   finding; feed confirmed signals to `confidence_field.py` as the bust-flag/interval term.

### Parked (do NOT build yet)
- Terrain-similarity localization (group cells by slope/aspect/relief, not Euclidean
  radius): an analysis-phase choice. Ensure the defining features are columns now; build
  the neighborhood logic later.
- Score-based / terrain-conditioned learned prior: watch-and-prototype AFTER the
  diagnostic signal is found and confirmed. GPU-rental territory; does not gate current work.

---

## ONE-LINE SUMMARY
Goal: forecast erratic terrain-driven fire winds by (1) diagnosing WHY HRRR misses them and
(2) giving WindNinja a better STARTING POINT (selection / source-substitution / init-mode —
NOT a learned correction). PHASE A FIRST: build the departure database across ALL 172 RAWS
files / 12 events — QC'd, tagged by era/regime/cluster/representativeness — and report row
counts per channel; fit nothing. PHASE B (after A): hunt the signal only where N supports it,
gate on the separability pre-condition (rule #0), test terrain-alone first, confirm
leave-one-regime-out, then use confirmed signals to flag/bound errors and inform the better
WindNinja starting point. Baseline to beat: HDW. Scope: wind-driven only, not plume-driven.
