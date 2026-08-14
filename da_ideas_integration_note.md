# Data Assimilation Ideas for HRRR–WindNinja Bust Diagnostics

**Written 2026-06-01; updated 2026-06-01 (covariance-estimation + EnVar); updated 2026-06-05
(CADRE-EPIC conference talks: MAP Lab hybrid-ensemble + Frolov/NOAA-MITRE-NVIDIA end-to-end DA).**
Companion to the reframe doc (`REFRAME: HRRR Forecast-Bust Detection`, 2026-05-31) and the
plan doc (`Primary Goal & Dataset Creation Spec`, 2026-06-01).
The plan/reframe docs are the **source of truth**; this is subordinate enrichment.

Source: data-assimilation (DA) lectures + an EnVar research talk + Van Leeuwen covariance-
estimation slides + two CADRE-EPIC conference talks. This doc extracts only what transfers
into the bust-prediction work — framing, vocabulary, concrete schema/validation choices, and
an instructions block for Claude Code. It does **not** change the next step.

> **What changed in the 2026-06-05 update (read this first):** the conference produced exactly
> **one new actionable item for Phase A** — the *structured-vs-white departure test* (see ★★
> below), a concrete addition to the Phase A report, not a new build task. Everything else from
> the talks (physics-anchored hybrid, pure-ML small-scale energy loss, score-based "limited
> success") **reinforces parking the learned path** — it does not add work. Do not let the
> volume of new framing expand scope: the build is still Phase A, unchanged.

---

## Orientation (read first)

Classical DA is built for **random, Gaussian** model error captured by a covariance, in a
**cycling** system with a model **adjoint**. HRRR–WN has none of those: WindNinja is a
diagnostic mass-conserving solver (no adjoint), and the ridgetop error is **systematic,
terrain-keyed, non-Gaussian**. So the DA *mechanisms* (Kalman gain, 4DVar trajectory
fitting, EnKF ensembles) do not port. What ports is the **conceptual architecture**:
hybrid static+flow-dependent error structure, scale-separation, learned-rather-than-
specified error, and — most importantly — **estimating error structure from departures and
model-vs-model differences without ground truth**. Steal the architecture; leave the
Gaussian/adjoint machinery behind.

---

## ★ THE TWO MOST IMPORTANT IDEAS (covariance estimation without truth) ★

These are not analogies. They are the established methods for doing exactly what this
project is trying to do — estimate error structure without truth at every point — and they
tell us both why the core bet is sound and what its precise limits are.

### A. Innovations / Hollingsworth–Lönnberg: the departure dataset IS a B-estimator

The innovation (departure) is `y − H(x_b)` = obs minus background-projected-to-obs-space =
exactly `speed_err = hrrr − obs`. The key identity:

    E[ (y − H x_b)(y − H x_b)^T ] = H B H^T + R

In words: **the covariance of the departures equals the (projected) background error plus
the observation error.** The left side is *observable* — accumulate departure statistics
over many cases. R is known-ish (instrument + representativeness). So you can **back out B
(the background-error structure) from departures you can actually measure**, never needing
the true state.

**Implication for the redesign:** `hrrr_error_dataset.csv` is a pile of departures. The
*covariance of those departures, binned by terrain class*, is an empirical estimate of how
HRRR's effective background-error B varies with terrain. That reframes the project from
"hunt for a bust predictor" to the more principled and more general "**empirically estimate
the terrain-dependence of HRRR's background-error covariance from departure statistics**" —
Hollingsworth–Lönnberg specialized to terrain.

**Critical caveat — R contains terrain-dependent representativeness error.** The departure
carries BOTH H B H^T (forecast error = signal) AND R (obs error = noise). For RAWS, R
includes *representativeness error*: a point sensor vs a 3 km grid cell, which is itself
worse in complex terrain. So part of the "departure" at a rugged site is point-vs-grid
mismatch, NOT HRRR being wrong. **This must be flagged/estimated** or it will masquerade as
terrain-driven forecast error — a direct confound for the speed and direction channels.

**Separating R from HBH^T — the Desroziers diagnostic (rigorous method + our proxy).**
There is an established way to split observation error R from forecast error HBH^T using only
departures, no truth: the Desroziers relations. Using the analysis departure
`y − H x_a = (I − HK)(y − H x_b)`, cross-covariances of prior and posterior departures give:
- prior×prior → `R + HBH^T`
- analysis×prior → `R` (observation error, isolated)
- analysis×(analysis−background) → `HBH^T` (forecast error, isolated)

So R and HBH^T are separately recoverable from departure statistics.
**BUT it requires an analysis x_a** — i.e. an actual assimilation step (a K, a posterior),
which the current pipeline does NOT have (we characterize raw HRRR departures, not a DA
cycle). So Desroziers is **not directly usable yet**. Two takeaways:
- *Current stand-in:* representativeness error is mostly a function of sub-grid terrain
  variability, so estimate it directly from the **DEM (terrain roughness / elevation variance
  within the 3 km cell)** — that is what `repr_error_flag` should encode. The DEM-roughness
  proxy replaces the Desroziers R-estimate during the dataset-construction phase.
- *Future option:* if the project ever grows a real analysis/correction step that produces
  x_a, Desroziers becomes available as a self-consistency check (does assumed R match the R
  the departures imply?). Validation tool for later, not now.

### B. NMC / forecast-differences: the WN−HRRR discrepancy, formalized

The NMC method estimates B with NO observations: take a 1-day and a 2-day forecast valid at
the SAME time, subtract them, repeat many times; the difference covariance ≈ 2B
(B^½ ≈ X^f/√2). It works because the shared (cancelled) truth drops out, and forecast
errors at different lead times are largely independent, so the difference reveals error
structure.

**This is the core Stormwatch bet, formalized.** The reframe says the HRRR↔WindNinja
disagreement is a free, obs-independent signal. NMC is the same principle — two model
estimates differenced, truth cancels, error structure remains — except:
- NMC differences **two lead times of one model**;
- Stormwatch differences **two models (HRRR, WindNinja) of one time**.

So **the WN−HRRR discrepancy is an NMC-style estimator**, which elevates the bet from
intuition to a recognized technique.

**The precise limit (and why it's actually good):** NMC works *because* the two members'
errors are largely independent. HRRR and WindNinja are **not** fully independent — WindNinja
runs ON HRRR's boundary condition, so it inherits HRRR's synoptic error and only adds
terrain structure on top. Therefore the discrepancy does NOT estimate HRRR's *total* error;
it estimates the **terrain-resolution error specifically** — the part WindNinja adds that
HRRR lacks. That partial dependence localizes the signal to exactly the terrain-gap you care
about. Useful precision: the discrepancy is a terrain-gap estimator, not a total-error
estimator.

---

## ★★ NEW (2026-06-05): the structured-vs-white departure test — a Phase A deliverable ★★

From Frolov's "well-behaved assimilation" slide: a *well-specified* analysis removes all
**structured** differences between obs and background (O−B), leaving an O−A residual that
looks like **white noise**. Structured residual = unexploited signal; white residual = nothing
left to extract.

**This hands Phase A its null hypothesis.** The whole bet is that HRRR's terrain departures are
**structured (terrain-keyed), not white**. So the Phase A report should not stop at row counts —
it should also answer: *are the departures structured by terrain, or are they white noise?*

**Concrete, no-fitting test to add to the Phase A report (per channel):**
- Bin the completed departures by `terrain_class` (and by `synoptic_regime`).
- Report the **between-bin spread vs within-bin spread** of the departure (e.g. variance of
  per-terrain-class mean departure ÷ pooled within-class variance). A ratio near 1 ⇒ departures
  are ~white w.r.t. terrain (no signal); a ratio meaningfully > 1 ⇒ structured by terrain.
- This is **descriptive statistics, not a model.** No fit, no learned correction, no claim of a
  predictor — just "do the means separate by terrain class, and by how much, at the current N?"

This is the single most important addition this week: it turns the row-count report from
"is N big enough?" into "is N big enough **and** is there terrain structure in the departures
at all?" — which is the actual go/no-go for Phase B. Still Phase A. Still fit nothing.

**Corollary — the working DA families are all incremental-Gaussian (departure-based).** Frolov's
catalog of systems that actually work (GraphDOP, Aardvark, HealDA, add-DA) are all the
incremental form ∇J = ∇‖x_a − x_b‖_{B⁻¹} + ∇‖y − H(...)‖_{R⁻¹} — i.e. **built on departures**,
exactly the object this dataset is. Score-based DA was labeled **"multiple attempts with limited
success"** by a NOAA/MITRE/NVIDIA collaboration with ECMWF tech. Net: the departure-database
direction is the one the field's working systems share; score-based stays parked (see §10),
now with stronger external warrant.

**Corollary — "what is the simplest problem one could try?"** The same collaboration, facing the
full end-to-end pipeline, explicitly asked for the *smallest tractable subproblem* first. That
is the Phase A instinct, validated by the largest players in the room: build the smallest huntable
thing, report, then decide. Do not build the end-to-end system.

---

## The other transferable ideas (architecture / framing)

### 1. HRRR ridgetop error is a form of FILTER DIVERGENCE
The model is overconfident in terrain it cannot resolve; its reported spread does not track
true error. `confidence_field.py` plays the role of **structured, learned, per-cell,
terrain-aware inflation** — restoring an honest spread/error relationship where HRRR is
overconfident.

### 2. Multiplicative inflation is the wrong fix — and that's diagnostic
Its stated limitations map onto the problem verbatim: "cannot correct missing dynamical
modes" = the unresolved canyon jet; "a single λ is rarely optimal in space, time, or across
variables" = the case for per-cell, per-channel treatment. Inflation cures *under-dispersion*
(spread too small but pointing the right way); the bust signal addresses *structural error*
(wrong direction / missing mode). Different diseases.

### 3. Hybrid B — the architectural template for the redesign
Operational DA does NOT choose between static climatological B and flow-dependent ensemble
B; it BLENDS them, weighted. Map onto HRRR–WN:
- **Static/stationary component = terrain** (a canyon is a canyon every event);
- **Flow-dependent component = WN−HRRR discrepancy** (event-specific);
- The open question is the **mixing weight**.
This is the clean statement of "check terrain alone before crediting the discrepancy":
terrain is the static B, discrepancy is the ensemble B, and the weight is what you learn.

### 4. Scale-dependent localization (Multiscale DA)
A single localization length is provably wrong when error lives at multiple scales. For the
bust field:
- **Speed/direction busts at canyons/summits are small-scale** → tight localization;
- **Synoptic-regime bias is large-scale** → broad spread.
A redesigned confidence field should be **scale-separated** (a broad synoptic-regime term +
a tight terrain term), not one undifferentiated per-cell field.

### 5. Learned B (ML_BEC) — the permission slip, with a hard constraint (updated 2026-06-05)
The establishment has replaced hand-built covariance with a *learned* one and beaten the
traditional version at lower cost. This validates "learn the error structure rather than
specify it" as a legitimate core for a redesign, not a bolt-on.

**But the MAP Lab hybrid-ensemble talk pins down HOW, and the constraint is strict:**
- **Pure-ML performs *worst* / diverges** (filter divergence, Slivinski et al. 2025). For a
  life-safety wind system this settles it: a learned terrain-wind emulator *alone* is off the table.
- **Pure-data-driven loses energy at wavelengths < 1000 km** — precisely the small-scale band
  where canyon jets and terrain channeling live. ML smooths away exactly what you need most.
- **The winning recipe is a hybrid *re-centered around the physics mean* (HV2), at equal
  compute** — physics provides the anchoring mean, the learned part contributes structure/spread
  around it. A **naive** hybrid (HV1, just pooling members) did **not** help — re-centering is
  the recipe, not concatenation or 50/50 averaging.

**Constraint for any eventual Stormwatch redesign:** WindNinja physics stays the anchoring mean;
any learned element is **re-centered onto it and bounded**, never replaces it, never pure-ML,
never a naive average. This is the same line the plan already draws ("better starting point =
physically-sourced, not a learned correction") — the conference result says that discipline is
not just safe but *optimal*. Parked architecture, not a build task.

### 6. Localization → TERRAIN-SIMILARITY neighborhoods
The LETKF localizes per-cell within a spatial radius (a circle) to kill spurious
correlations. Right structure, wrong metric for terrain. Replace the Euclidean radius with a
**terrain-similarity neighborhood** — group cells by slope/aspect/relief/exposure/regime,
not distance.

### 7. NONSTATIONARITY — the validation hazard inside the 172 files
Two distinct nonstationarities:
- **HRRR itself drifts** across the record (methodology updates change bias structure;
  Manshausen et al. trained 2018+ for exactly this). Events straddling version changes are
  not the same model.
- **Regimes drift** across events (Diablo/Santa Ana vs frontal, etc.); a signal can be
  regime-specific yet look stationary if one regime dominates.

Actions: **tag every row with HRRR version/date-era AND synoptic regime**; the honest test
is **leave-one-regime-out / leave-one-era-out**, not just leave-one-event-out (effective N
is ~12 events/regimes, not 172 stations). **Terrain features are the stationary part** —
check whether terrain ALONE carries the signal before crediting the WN-discrepancy.

### 8. Correlated observation errors (obs-processing pipeline)
Ignoring correlated errors causes overfitting and noisy increments. RAWS within an event are
NOT independent — stations on the same terrain feature share departures when HRRR busts the
synoptic flow. So **effective N < raw row count.** When reporting complete-row counts, also
report a **correlation-aware count** (independent station-events; co-located stations counted
once). This is also why leave-one-EVENT-out (not leave-one-row-out) is the honest test.

### 9. Arrival/timing channel = a 4DVar-style trajectory comparison
Timing is HRRR's wind time series at a cell vs RAWS onset/peak across the event window.
It inherently needs the **cell-level HRRR time series** (flag `NEEDS_HRRR_TS`) and
**peak-window scoring**, never a single 12Z snapshot (fixed-12Z misses overnight peaks —
HMRC1, CUUC1). Not running 4DVar (no adjoint); borrowing only the trajectory framing.

### 10. Score-based DA — the future "if the signal holds" path (now with stronger warrant to wait)
A terrain-conditioned learned prior over complex topography is unclaimed ground; the bust
dataset is its foundation. CPU-side groundwork first; GPU (rented) only later. Host has no
GPU. Watch-and-prototype-later, explicitly AFTER the diagnostic signal is found.
**2026-06-05:** a NOAA/MITRE/NVIDIA collaboration (ECMWF tech) labeled score-based DA "multiple
attempts with limited success." That is the strongest "stay parked" signal yet — the people
best resourced to make it work haven't. Keep parked; the incremental/departure form is the live one.

### 11. Learnable observation operator H — the tempting-but-falsified direction (new 2026-06-05)
Frolov's group is replacing the observation operator H with a *learned emulator*. WindNinja is
essentially a physics-based observation/downscaling operator (coarse HRRR → point, via terrain).
The analogous move would be replacing WindNinja with a learned H — i.e. turning it into a learned
correction. **That is exactly the falsified additive-correction direction.** Interesting framing,
but it lands on the wrong side of the plan's "physically-sourced, not learned" line. Do not build it.

---

## INSTRUCTIONS FOR CLAUDE CODE (when building)

**Primary objective:** build `hrrr_error_dataset.csv`. Construct the dataset only.
**Fit nothing. Claim no signal.** The reframe doc governs; this doc is subordinate.

**Step order (non-negotiable):**
1. Apply **quality control FIRST** — gross checks (stuck/flatlined anemometers, corrupt
   gusts) + a maintained bad-station-event **blacklist** — before any row is marked complete.
2. Build one row per usable station-event across **all 172 usable RAWS files / 12 events**.
3. Report the **complete-row count per channel** (speed / direction / arrival) AND a
   **correlation-aware count** (independent station-events; co-located stations on shared
   terrain counted once). Do not interpret the counts — just report them.
4. **(new 2026-06-05) Structured-vs-white check, per channel** — purely descriptive, no fit:
   bin completed departures by `terrain_class` (and by `synoptic_regime`) and report the
   between-bin vs within-bin spread ratio (variance of per-class mean departure ÷ pooled
   within-class variance). This answers "are departures terrain-structured or white?" — the
   actual go/no-go for Phase B. **No model, no predictor, no claim** — just the ratio and the
   per-class means. If N is too small in a channel to bin meaningfully, say so and stop there.
5. Stop. No fitting until a channel has enough N, shows terrain structure, and the reframe's
   leave-one-event-out (ideally leave-one-regime-out) plan is in place.

**Columns — ERROR (targets, truth from RAWS):**
- `speed_err = hrrr_10m_mph − obs_sus_mph` (own-station gust factor); also `speed_ratio`
- `dir_err = circular(hrrr_10m_dir − obs_vector_mean_dir)`
- `arrival_err = hrrr_peak/onset_hour − obs_peak/onset_hour`  (mark `NEEDS_HRRR_TS` where the
  cell-level HRRR time series is not pulled — the timing channel REQUIRES it)

**Columns — PREDICTORS (obs-independent, forecast-time):**
- terrain: `elev_m`, `slope`, `aspect`, `local_relief_1km`, `summit/canyon/valley`, `DEM_verified`
- inversion: station elev vs event inversion lid (above/below/near)
- synoptic: `BC_dir`, `BC_speed`, `BC_level`, `lapse/stability`, `MSLP_gradient`
- discrepancy: `wn_minus_hrrr_speed`, `wn_minus_hrrr_dir` at the cell  (the key signal)

**Columns — NONSTATIONARITY / VALIDATION TAGS (add NOW, during construction):**
- `hrrr_version` / `hrrr_era` — by event date (a lookup of which HRRR was operational; do
  NOT guess — flag `NEEDS_HRRR_VERSION` if unknown)
- `synoptic_regime` — per-event label (Diablo / Santa Ana / frontal / etc.), assigned from
  event metadata; flag `NEEDS_REGIME` if not yet labeled
- `event_id` and a `terrain_cluster_id` (which stations share a terrain feature within an
  event) — needed for the correlation-aware count and leave-one-event/regime-out

**Columns — REPRESENTATIVENESS (the R caveat):**
- `repr_error_flag` — estimate point-vs-3km-grid representativeness mismatch from the **DEM
  (terrain roughness / elevation variance within the cell)**; it is terrain-dependent. This
  is the proxy for the Desroziers R-term (the rigorous version needs an analysis we don't
  have yet). Part of the departure at rugged sites is R, not forecast error — do not let it
  masquerade as terrain-driven HRRR error.

**HARD RULES:**
- Compute only what is real. Mark `NEEDS_HRRR_TS` / `NEEDS_DEM` / `NEEDS_WN` /
  `NEEDS_HRRR_VERSION` / `NEEDS_REGIME`. **No guessing, no fabricated values.**
- Tags (era, regime) are **columns to populate from lookups/metadata**, not values to infer.
- Score at each event's **pre-registered peak window**, not fixed 12Z.
- Do NOT reach for inflation schemes, diffusion priors, hybrid weighting, or any correction
  model at this stage. Those are post-signal design ideas in this doc, not build tasks.
- If this doc and the reframe doc ever conflict, **the reframe doc wins.**

---

## What does NOT change

The next move is exactly as written in the plan/reframe docs: build the dataset, QC first, report
complete-row counts per channel (with a correlation-aware count and era/regime tags), fit
nothing. The 2026-06-05 update adds **one** thing to that report — the structured-vs-white
departure check — and it is still descriptive, still no-fit. The architecture ideas above shape
how the confidence/correction engine might EVENTUALLY be structured (hybrid re-centered on
physics, scale-separated, learned-but-bounded, departure/NMC-grounded, never pure-ML). They do
not change whether there is a signal to put in it — the row counts and the structure check
decide that.

**The three things most worth building in NOW (not just describing later):**
1. The **era/regime/terrain-cluster tags** (enable the honest leave-one-out tests).
2. The **representativeness-error flag** (the R term in `departures = HBH^T + R`; otherwise
   it confounds the very signal you are estimating).
3. The **structured-vs-white check** in the Phase A report (between-bin vs within-bin departure
   spread by terrain class) — the go/no-go for Phase B.

**The bright line for Claude Code:** schema columns + QC + counts + the structured-vs-white
ratio = IN SCOPE now. Inflation, hybrid weighting, learned H, score-based priors, any correction
model = OUT until Phase A reports a signal. If the plan/reframe docs conflict with this one, they win.
