# Claude Code Kickoff — Stormwatch Phase A (read this first)

**Date:** 2026-06-05. **Status:** ready to build. **Scope:** Phase A only.

## Source-of-truth order (if anything conflicts, higher wins)
1. `Primary Goal & Dataset Creation Spec` (plan doc, 2026-06-01)
2. `REFRAME: HRRR Forecast-Bust Detection` (reframe doc, 2026-05-31)
3. `HRRR_WN_bust_DA_ideas.md` (DA ideas note — enrichment + full rationale)
4. This file (a one-page restatement; the docs above govern)

This kickoff exists because the 2026-06-05 conference emphasis post-dates the plan doc.
It carries **one new build-relevant item** (the structured-vs-white check). Everything else
new is parked architecture — do not build it.

## The job, in one sentence
Build `hrrr_error_dataset.csv` — a **departure database** (one row per usable station-event,
all **172 RAWS files / 12 events**), QC first, **fit nothing**, then report.

## Do, in order
1. **QC FIRST.** Gross checks (stuck/flatlined anemometers, corrupt gusts) + bad-station-event
   blacklist. Nothing is "complete" until it passes QC.
2. **Build rows** across all 172 files / 12 events. Compute only what is real; mark
   `NEEDS_HRRR_TS` / `NEEDS_DEM` / `NEEDS_WN` / `NEEDS_HRRR_VERSION` / `NEEDS_REGIME`.
   **No guessing, no fabricated values.**
3. **Report per channel** (speed / direction / arrival):
   - complete-row count, AND
   - correlation-aware count (co-located stations on shared terrain counted once).
4. **Structured-vs-white check** (NEW — descriptive only, no fit): bin departures by
   `terrain_class` (and `synoptic_regime`); report between-bin vs within-bin spread ratio
   (variance of per-class mean departure ÷ pooled within-class variance) + the per-class means.
   This is the go/no-go for Phase B: *are departures terrain-structured or white?*
   If N is too small to bin in a channel, say so and stop there.
5. **STOP and report.** No fitting, no correction model, no Phase B.

## Schema (columns)
- **Targets (truth from RAWS):** `speed_err = hrrr_10m_mph − obs_sus_mph`, `speed_ratio`;
  `dir_err = circular(hrrr_dir − obs_vector_mean_dir)`; `arrival_err` (+ `NEEDS_HRRR_TS`).
- **Predictors (obs-independent):** terrain (`elev_m`, `slope`, `aspect`, `local_relief_1km`,
  summit/canyon/valley class, `DEM_verified`); inversion (elev vs lid); synoptic (`BC_dir`,
  `BC_speed`, `BC_level`, `lapse/stability`, `MSLP_gradient`); discrepancy
  (`wn_minus_hrrr_speed`, `wn_minus_hrrr_dir`).
- **Nonstationarity/validation tags (populate from lookups/metadata, do NOT infer):**
  `hrrr_version`/`hrrr_era`, `synoptic_regime`, `event_id`, `terrain_cluster_id`.
- **Representativeness:** `repr_error_flag` from DEM roughness / elevation variance in the
  3 km cell (the R term; part of a rugged-site departure is point-vs-grid mismatch, not HRRR error).

## Scoring rule
Score at each event's **pre-registered peak window**, never fixed 12Z (overnight peaks exist).

## Bright line — IN vs OUT of scope right now
- **IN:** schema columns, QC, counts, the structured-vs-white ratio.
- **OUT (until Phase A reports a signal):** inflation schemes, hybrid weighting, learned
  observation operator (don't turn WindNinja into a learned H — that's the falsified correction),
  score-based / diffusion priors, any correction or confidence model.

## Why the new emphasis doesn't add work (one line each)
- Pure-ML is *worst* / diverges and loses energy < 1000 km (your fire-wind band) → learned path stays parked.
- Score-based DA = "limited success" per NOAA/MITRE/NVIDIA → stays parked.
- "Find the simplest subproblem first" (same group) → that's Phase A. You're already doing it.
- Any eventual learned element must be **re-centered on WindNinja physics, bounded, never pure-ML**
  → architecture note for later, not now.
