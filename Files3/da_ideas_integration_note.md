# DA Ideas — What Changes in the Build (integration note)

Companion to `Data Assimilation Ideas for HRRR–WindNinja Bust Diagnostics` (2026-06-01)
and the reframe doc (2026-05-31). This note records ONLY the concrete deltas to the
queued dataset build. The DA doc is the reasoning; this is the action.

## NET EFFECT: the next step is unchanged in scope. It gains 2 columns + 1 rule.

### ADD TO hrrr_error_dataset.csv schema (during construction — retrofitting is painful):
- `hrrr_era` — HRRR version / date-era tag per row. HRRR methodology changed across
  2017–2025; the bias "learned" is not the same model across eras. (DA doc §5)
- `synoptic_regime` — e.g. diablo_offshore / santa_ana / frontal_passage / chinook /
  derecho. A signal can look stationary only because one regime dominates. (DA doc §5)

### ADOPT AS THE DATASET'S IDENTITY (framing, §3):
- The file IS a DEPARTURE DATABASE: speed_err = hrrr − obs is the DA innovation/departure.
  DA assumes departures are zero-mean noise; our edge is that in complex terrain they are
  NOT zero-mean and the systematic part is the signal. Bin departures by terrain, regime,
  channel.

### ANALYSIS-ORDERING RULE (bake into the plan, §5 corollary):
- The effective held-out unit is ~12 EVENTS/REGIMES, not 172 stations. 172 is a comfort
  illusion for generalization. Honest test = leave-one-REGIME-out (or leave-one-HRRR-era-
  out) where N allows, not just leave-one-event-out.
- TEST TERRAIN-FEATURES-ALONE FIRST. Terrain is the stationary part (a canyon is a canyon
  in every era/regime). The WN-discrepancy predictor rides partly on HRRR's version-
  dependent behavior and is MORE fragile. Only credit the discrepancy signal AFTER
  checking whether terrain alone already carries it.

## PARKED (correctly — do NOT build yet):
- Terrain-similarity localization (§4): group cells by slope/aspect/relief not Euclidean
  radius. An ANALYSIS choice for the signal-hunt phase. Ensure the defining features are
  columns now; build the neighborhood logic later.
- Score-based DA / terrain-conditioned learned prior (§7): watch-and-prototype, AFTER the
  diagnostic signal is found and confirmed. GPU-rental territory. Does not gate current work.

## UNCHANGED NEXT MOVE:
Build hrrr_error_dataset.csv across all 172 usable RAWS files / 12 events. Report
complete-row count per channel (speed/direction/arrival). Fit nothing. Mark
NEEDS_HRRR_TS / NEEDS_DEM / NEEDS_WN. Now WITH hrrr_era + synoptic_regime columns.

---

## ADDENDUM (2026-06-01) — forward-design notes from JEDI/SABER slides

Post-signal design ideas only. Do NOT build now; capture so they're not lost.

- **Composable B-blocks (SABER "Block Chain").** Operational DA (JCSDA SABER) does not use
  one monolithic covariance — it COMPOSES B from separable, independently-calibrated blocks
  chained together. Maps onto the hybrid-B idea: build the bust error-model from separate
  blocks (terrain block + regime block + WN-discrepancy block), each trainable on its own,
  rather than one undifferentiated learned field. Cleaner architecture IF the engine is ever
  built. Still post-signal.
- **SABER's 4 B-flavors = parametric (static), ensemble, hybrid, and DIFFUSION.** Diffusion
  (generative/learned) covariance is now a first-class option in a deployed operational
  system — stronger version of the ML_BEC "permission slip": learned error structure is
  production-grade, not just research.
- JEDI component map (org vocabulary, not method): SABER→B, IODA→obs, UFO/CRTM→H operator,
  VADER→variable change, OOPS→minimization. Same J(x) cost function already reviewed and
  already set aside (no adjoint / no minimization in our pipeline). Nothing to implement.

These do not change the next step (build the dataset; report row counts; fit nothing).

- **Cross-channel correlation (balance-operator / ρ idea).** In multivariate 3D-Var a
  non-zero cross-covariance ρ means observing one variable constrains a correlated one
  (one obs updates both T and q). Analog: the three bust channels (speed/direction/arrival)
  are likely cross-correlated — a direction bust at a rotating summit may co-occur with a
  speed bust. SCHEMA IMPLICATION (minor, already mostly satisfied): keep speed_err,
  dir_err, arrival_err on the SAME row per station-event so the cross-channel correlation
  is recoverable later; don't analyze channels in total isolation. The off-diagonal
  (cross-channel) structure carries information, like ρ tilting the B ellipse.

- **Wind speed is a bounded/skewed (near-"mixed") distribution near calm — analysis-phase
  caution.** Mixed distributions (Anderson, NCAR) have a discrete spike (e.g. P(zero rain))
  plus a continuous part; Gaussian methods break on them. Wind speed is non-negative and
  piles up near calm, so the speed_err = hrrr − obs distribution will be skewed/bounded near
  calm, NOT the symmetric Gaussian the error-ellipse picture assumes. CONSEQUENCE (metrics
  phase, not construction): symmetric error metrics (plain RMSE, symmetric intervals) can
  mislead near calm; this is part of why near-calm stations are QC-dropped (CUUC1) and why
  gust-factor denominators blow up near zero. Treat the speed channel as bounded/skewed when
  scoring. Direction is circular (already handled via vector mean). No build change.

---

## FUTURE CAPABILITY (parked, explicit) — mixed / bounded distributions for the speed channel

Promoting the wind-speed-distribution note from "analysis caution" to a tracked FUTURE
CAPABILITY, per request (2026-06-01).

**What:** Represent the speed channel (and any non-negative, calm-piled variable) with a
MIXED / bounded distribution — a discrete-ish mass near calm plus a continuous skewed part
above it — rather than forcing a symmetric Gaussian. Direction stays circular (vector-mean,
already handled). Reference: Anderson et al., MWR 152, 2111–2127 (NCAR/DART; mixed
distributions, "supports duplicate ensemble members"); wildfire-relevant per the slide.

**Why it matters for Stormwatch specifically:**
- speed_err = hrrr − obs is skewed and bounded near calm, not Gaussian — the error-ellipse
  / Gaussian-covariance picture misrepresents it exactly in the low-wind regime.
- The bust detector's CONFIDENCE intervals should be asymmetric near calm (you can't have
  negative wind; the upside tail is the dangerous one for fire). A mixed-distribution
  representation gives honest, asymmetric uncertainty instead of symmetric ± that spills
  below zero.
- Ties to existing pain: near-calm QC drops (CUUC1) and gust-factor denominator blow-ups are
  symptoms of treating a bounded variable as unbounded/Gaussian.

**When (gating — do NOT build now):**
- Only relevant at the CONFIDENCE/output-distribution stage, AFTER the bust signal is found
  and confirmed. The dataset build and signal hunt come first.
- Until then: keep the simple analysis caution (treat speed as bounded/skewed near calm;
  don't trust symmetric metrics in low-wind rows; near-calm QC flag stays).

**Where it would live:** the confidence engine — when it emits a per-cell speed
distribution/interval, use a bounded/mixed form so intervals are asymmetric and never go
below zero. Pairs naturally with the "calibrate offline, apply at runtime" deployment shape.

  **Concrete method to use when this is built (added 2026-06-01):** BNRH — Bounded Normal
  Rank Histogram with quantile regression (Anderson, QCEFF framework, implemented in NCAR
  DART). Demonstrated properties that are exactly what the speed channel needs: unbiased,
  CAN GO TO ALL ZEROS, produces NO NEGATIVE VALUES, and beats traditional Gaussian filters
  on RMSE especially in the low/near-zero regime (the analog of near-calm wind). So the
  parked capability is concrete, not vague: use a BNRH-style bounded representation for the
  speed-channel output distribution; reference Anderson / QCEFF / DART rather than
  reinventing. Still post-signal, output/confidence-stage only.

---

## PEOPLE / WORK TO TRACK

- **Jeff Anderson (NCAR / UCAR; DART, QCEFF framework).** Track his work — directly relevant
  to the bounded/mixed-distribution problem for the wind-speed channel. Key items:
  QCEFF filters, BNRH (Bounded Normal Rank Histogram) with quantile regression, mixed
  distributions for variables with a zero-spike + continuous part (precip, tracers, fire
  sources). Reference paper shown: Anderson et al., Mon. Wea. Rev. 152, 2111–2127. Code lives
  in NCAR DART. Relevant to: the future-capability (bounded speed-channel output
  distribution) and, more broadly, honest non-Gaussian uncertainty for fire-wind forecasts.
  - DART home: https://dart.ucar.edu  (docs, tutorials, source; QCEFF / BNRH implementations live here)
  - DART is downloadable + laptop-runnable (no-MPI build for conceptual models) — the
    QCEFF/BNRH reference implementation is real code with tutorials, not just papers.
    Get DART: https://dart.ucar.edu/software ; docs: https://docs.dart.ucar.edu ;
    tutorials: https://dart.ucar.edu/tutorials
  - MOST RELEVANT PAGE: non-Gaussian algorithm development —
    https://dart.ucar.edu/research/non-gaussian-algorithm-development (exactly the
    bounded/non-Gaussian problem domain). Track **Ian Grooms** too (novel non-Gaussian
    algorithms, featured there) alongside Anderson.
  - Context: Anderson is a 2022 AGU Fellow; see SIAM "Removing Kalman from Ensemble Kalman
    Filtering" — the QCEFF philosophy (past the Gaussian assumption) that mirrors why this
    project uses a feature-based predictor, not a covariance. DART is the OUTPUT-distribution
    methods source for us (bounded uncertainty), not a framework to run the pipeline inside.

---

## EXTERNAL LANDSCAPE — fire-wind forecasting (where this project sits)

- **HDW (Hot-Dry-Windy Index), USDA Forest Service (Srock, Charney, Potter, Goodrick).**
  The incumbent operational tool for anticipating erratic/dangerous fire-weather days from
  temperature, moisture, wind. Works with standard NWP, any terrain/fuel. USES RAW MODEL
  WIND — does nothing about terrain-resolution error. => HDW is our BASELINE-TO-BEAT: when a
  signal exists, the first question a fire-weather audience asks is "does it add skill over
  HDW?" Track it as the comparison benchmark.
- **Coupled fire-atmosphere models (WRF-Fire; Community Fire Behavior Model CFBM in NOAA UFS
  SRW v3.0.0, 2025; NSF NCAR 3km->100m downscaling).** These resolve winds in complex
  terrain AND the fire's own feedback. Their 3km->100m downscaling is the same terrain-gap
  WindNinja targets. NOTE: these are the plume-driven / coupled path — explicitly OUT OF
  SCOPE for us (see scope boundary below).
- **NOAA UFS fire-weather (subseasonal fire metrics; SRW dynamic downscaling improves wind
  variability).** Same terrain-downscaling theme at a different timescale. Context, not a
  dependency.
- Predictability caveat (extreme-fire synthesis lit): coupled-model skill drops with lead
  time, severely at fine scales — the wall that motivates focusing on WIND, and on knowing
  where the forecast is unreliable, rather than chasing perfect fine-scale prediction.

## SCOPE BOUNDARY (explicit) — wind-driven, not plume-driven

Fire-wind erratic behavior splits into two classes (extreme-fire synthesis lit):
- **WIND-DRIVEN:** strong ambient, terrain-modulated winds drive the fire. <- THIS PROJECT.
  WindNinja + HRRR speak to exactly this: ambient flow shaped by terrain. In scope.
- **PLUME-DRIVEN:** weak ambient wind; the FIRE generates its own winds (up to ~10x ambient)
  via heat-release feedback. Needs a coupled fire-atmosphere model (CFBM/WRF-Fire).
  EXPLICITLY OUT OF SCOPE. We do not model the fire's own winds.
State this boundary in any writeup: "we improve the forecast of the ambient terrain-driven
wind that drives wind-driven erratic fire behavior; plume-driven winds require coupled
fire-atmosphere modeling and are out of scope."

## SHARPENED GOAL (2026-06-01) — two questions that refocus the project

The reframe stands, but the user sharpened it to two physical questions:

1. **WHY is HRRR missing the erratic (terrain-driven) winds?** A DIAGNOSIS question, not just
   a statistical-bust question. Named physical failure modes already evidenced in our work:
   (a) terrain-resolution — 3km cell can't see the ridge/canyon that channels/accelerates
   flow (Saddleback undershoot); (b) inversion mislevel — BC sampled at the wrong level
   relative to the inversion lid (Camp 700 vs 850); (c) terrain rotation — HRRR 10m shows the
   undeflected synoptic direction because it can't resolve the summit/canyon that rotates the
   flow (Kincade WISC1/HGLC1, both NNE->N). The dataset's terrain + discrepancy columns are
   how we test which mode dominates where.

2. **How to give WindNinja a BETTER STARTING POINT (initialization)?**
   The constructive deliverable. WindNinja is only as good as what you feed it. THREE LEVERS,
   pursued as ONE strand (cheapest → deepest):
   (a) SELECTION — best level/hour/location from HRRR (ERA5 work supports this).
   (b) SOURCE SUBSTITUTION — where HRRR is terrain-blind, feed a different/blended source:
       ERA5 at certain levels, multi-level blend, upstream-undeflected sample, RTMA/mesonet.
   (c) INITIALIZATION MODE — which WindNinja init: domain-average vs 2D gridded vs
       point-obs-informed. Treated as fixed so far; make it a variable. Determines how much
       HRRR terrain-blindness is inherited before WindNinja runs.
   GUARDRAIL: all three are about the INPUT you feed — NOT a learned additive BC *correction*,
   which we FALSIFIED (single- and multi-station, do-not-revive). Substitution (b) is the one
   that could drift toward "correction": the line is choose a physically-sourced input, do not
   learn a fit to obs and add it. ERA5 work showed selection matters and is defensible.

Net: the bust dataset still comes first (it's how we answer Q1 — which failure mode, where).
Q2 (better BC sourcing) is the product that follows once Q1 says where/why HRRR fails.

---

## PHASE B EVALUATION PLAN — how to score the bust detector (forecast verification)

Source: forecast-verification lecture (CAWCR framework, https://www.cawcr.gov.au/projects/verification/).
This fills a real gap — the docs specified how to BUILD the dataset but not how to SCORE a
bust detector once one exists. Use these in Phase B, not Phase A.

**The bust flag is a BINARY-EVENT forecast ("will HRRR bust here? y/n") → score with the
contingency-table family:**
- **POD** (probability of detection) = hits/(hits+misses): of real busts, how many flagged.
  Missing a bust is the dangerous error for fire — weight this.
- **POFD** (prob. false detection) = false_alarms/(false_alarms+correct_nulls): of non-busts,
  how many wrongly flagged. Too many → forecasters stop trusting the flag.
- **ROC curve** = POD vs POFD swept over the flag threshold. THE way to show skill above the
  no-skill diagonal; threshold-independent, so it sidesteps "what cutoff = a bust."
- **ETS** (equitable threat score) = credits hits above chance. Use because busts are RARE;
  rare-event scoring needs the chance correction.

**TRAP — do NOT headline plain ACCURACY.** Accuracy = (hits+correct_nulls)/total looks great
for rare busts (predict "no bust" everywhere → ~95% accurate, zero busts caught). Accuracy is
the wrong metric here; POD / POFD / ROC / ETS are the honest ones. Also note FAR (false alarm
RATIO = false_alarms/(hits+false_alarms)) differs from POFD (false alarm RATE) — don't conflate.

**Output-distribution scoring (the BNRH/bounded speed channel, post-signal):**
- **CRPS** (continuous ranked probability score) scores a full predictive DISTRIBUTION vs the
  observed value — the natural scoring rule for the asymmetric/bounded speed interval. Use CRPS
  to evaluate whether the bounded speed distribution is honest, not RMSE.
- **Brier score** (+ its reliability/resolution/uncertainty decomposition) for any probabilistic
  yes/no bust output.

**Neighborhood / fuzzy verification (note for our spatially-localized busts):**
- Grid-point-exact scoring double-penalizes a bust predicted one cell off (counts as miss AND
  false alarm). Since busts are terrain-keyed and local, use NEIGHBORHOOD verification — credit
  a hit if the bust is predicted NEAR the observed one. Ties to spatial_cluster_id.
- CONCRETE METHOD: **FSS — Fractions Skill Score** (Roberts & Lean 2008). Compute the FRACTION
  of points exceeding the bust threshold within a neighborhood (NP) for forecast vs obs; FBS =
  mean-squared difference of those fractions; FSS = 1 - FBS/WFBS (1=perfect, 0=no skill). The
  neighborhood RADIUS is a tunable knob — report the standard "FSS vs neighborhood size" curve
  to show at what spatial scale the bust detector has skill.

**Framing reference:** Murphy 1993, "What is a Good Forecast?" (MWR) — three goodnesses:
consistency, QUALITY (does the flag match reality), and VALUE (does it help a fire manager
decide). Quality is necessary; VALUE vs HDW is the real bar. Good for positioning the project.
