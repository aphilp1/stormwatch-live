# Stormwatch Test Protocol — Authoritative Reference for Claude Code

**Purpose:** define *what we are testing, how, and how we know a result is real* — so
work can proceed in long autonomous stretches without round-tripping. This is the
single source of truth for methodology, conventions, and experiment order. When a
result or decision is covered here, follow this document rather than asking. When a
result meets an **ESCALATE** condition (defined below), stop and surface it.

This document assumes familiarity with the codebase (`mechanism_classifier.py`,
`bc_label_generator.py`, `bc_outer_trainer.py`) and the companion files
(`hindcast_event_library.md`, `station_registry_and_sources.md`).

---

## 0. The one-paragraph mission

Wind is the weakest input to fire-spread models. Operational models already forecast
*synoptic-scale* winds skillfully (both BAMS papers say so). The gap — and our niche —
is the **3 km → sub-1 km terrain amplification** HRRR structurally cannot resolve, and
the **timing** of when dangerous flow arrives. We hindcast known extreme-wind fire
events to learn where each model layer fails and to build a correction that earns trust
on the past before deployment. Scope of the final solution is deliberately **open**;
this protocol is built to let the scope grow without rewriting the rules.

---

## 1. THE PRIME DIRECTIVE: artifact-first skepticism

**Every "finding" is presumed to be an artifact until it survives the artifact checks
in §3.** This is not pessimism; it is the lesson of the 1.42× collapse. The single
most expensive failure mode in this project is a coordinate/convention artifact
propagating into the algorithm dressed as physics.

Three permanent corollaries:

1. **No number is trustworthy without its provenance.** Every amplification ratio,
   bias, or BC value must travel with: the station coordinates used, the gust-factor
   convention, the data window, and whether the station participated in fitting.
2. **Coordinate verification is a precondition, not a cleanup step.** Terrain wind has
   huge spatial gradients — that's the whole premise — so any quantity tied to a
   station location is only as good as that location.
3. **"Consistent-with-zero" is a valid, publishable result.** "HRRR is near-unbiased
   for low-terrain downslope events" is a real finding. Do not manufacture a bias to
   have something to report.

---

## 2. CONVENTIONS & DATA HYGIENE (lock these; never let them drift between cases)

These are the things that must be *identical* across every event, or cross-case
comparison is meaningless.

### 2.1 Coordinates
- **Source of truth:** the live station registry (Synoptic/MesoWest metadata API or
  WRCC) — NOT papers, NOT memory, NOT summit GPS points. Papers tell you *which*
  stations and *what they observed*, not where the sensor sits. (Brewer & Clements
  Table 1 is fuel-moisture climatology, not coordinates — locations are only on the
  Fig 1B map.)
- **Mandatory elevation cross-check:** after pulling coordinates, verify the elevation
  matches the station's expected siting (a ridge RAWS reported gusting to ~58 mph must
  not resolve to a valley elevation). Mismatch = coordinate error; stop and re-resolve.
- **Record the coordinate + its source** in every event record. If coordinates change,
  every derived quantity for that station is invalidated and must be recomputed.

### 2.2 Gust factor (the single biggest lever on any BC magnitude)
- WindNinja outputs **sustained**; RAWS report **gust**. Never compare across types.
- **Default convention going forward: sustained-to-sustained.** Compute the BC and all
  amplification ratios in sustained terms. Convert obs gust → sustained (or vice versa)
  using a stated factor; for Camp Fire the empirical factor is 1.625 (Jarbo sustained
  32 / gust 52).
- **The gust factor may be per-event** (terrain/stability dependent). Record the factor
  used for each event explicitly. Do NOT carry one event's factor silently to another.
- The old "within 4%" Jarbo result used WN-sustained vs obs-gust — a wrong-convention
  comparison. Do not reuse it.

### 2.3 Data clipping & station QC
- **Clip burnover/contaminated windows.** Jarbo Gap: clip after ~06:00 PST 9 Nov 2018
  (soil temps >40 °C, station likely burned over).
- **Drop documented bad sites as validation targets.** Stirling City (rotor/siting),
  Atlas Peak (tree-sheltered, per the Tubbs paper). Use the literature's own rejections.
- **Honor the MesoWest "questionable data" flags** rather than ingesting through them.

### 2.4 BC level
- 700 hPa is the BC reference **only where it sits clearly above terrain.** Low domains
  (Camp Fire ~300–1000 m): clean. High domains (Missoula ridges ~2300 m, Santa Ana
  peaks ~3500 m): run the **HGT:700mb terrain-height guard** — flag any domain cell
  where 700 hPa geopotential height is within ~200 m of local terrain (below-ground
  extrapolation). For high-terrain domains the BC variable should be **ridgetop-level
  wind**, with 700 hPa carried only as a secondary feature flagged as possibly invalid.
- Distinguish, always, between **domain-mean raw HRRR 700 hPa** and a **sounding 700 hPa**
  value — they are different quantities and conflating them was a real error.

---

## 3. ARTIFACT CHECKS — run these on EVERY candidate finding before it's called real

A result graduates from "candidate" to "finding" only after passing all that apply.

### 3.1 The provenance audit (always)
State, for the result: coordinates + source, gust convention, data window, and
fit-participation. If any is unknown, the result is not yet a finding.

### 3.2 The circularity check (for any amplification ratio or BC-fit result)
**Was the validation station used to fit the BC?** If yes, the result is partially
circular and cannot stand alone. Keep two station partitions:
- *Fit set* → used to derive the BC.
- *Held-out set* → never seen by the BC; used to validate amplification.
Camp Fire example: fit on Jarbo (+Openshaw); validate amplification at Colby/Saddleback
(held-out, literature ~58 mph gust). Never let "sweep once against all stations"
collapse these.

### 3.3 The convention-consistency check (for any cross-case claim)
Two cases can only be compared if coordinates, gust factor, BC derivation method, and
data window were handled identically. A "constant across cases" claim requires all
legs re-derived under identical conventions. (The 1.42× "constant" failed exactly here:
one circular, two coordinate-sensitive, one unobserved.)

### 3.4 Leave-One-Event-Out (for any learned/generalizing claim)
A bias or correction "generalizes" only if it survives LOEO: train on all events but
one, predict the held-out event, compare to the **delta = 0 baseline** ("just use raw
HRRR aloft wind as the BC"). Must beat baseline **by a margin** (see §5), not by a
hair. Random splits leak (hourly slices within an event are correlated) — hold out
whole events.

### 3.5 The mundane-cause check (for any systematic bias)
Before attributing a same-signed bias to physics, rule out: comparison-convention
mismatch, time-matching offset (HRRR fxx vs valid time), and terrain-height
extrapolation. A systematic bias is *also* the signature of a methodological artifact;
the two are indistinguishable from the residual alone. The literature warns the
model-obs bias is **speed-dependent** (high bias at low speeds) — so a single offset
is suspect by default.

---

## 4. ESCALATE conditions — when to stop and surface to the human/Opus

Run autonomously *except* when one of these triggers. These are the genuinely
load-bearing loops worth keeping.

- **A finding survives all applicable §3 checks** → surface it (this is the good case —
  a real result deserves review before it becomes load-bearing).
- **A coordinate/convention error invalidates prior committed results** → surface
  immediately (like the 1.42× collapse); do not silently overwrite the record.
- **An artifact check cannot be run** because required data is missing (e.g. no
  held-out station exists for an amplification claim) → surface the limitation rather
  than reporting the un-checkable number.
- **A result contradicts the peer-reviewed record** → surface with both numbers.
- **A scope decision is implied** (e.g. "should we add the timing axis now?") → surface;
  scope is deliberately open and is a human call.
- **A data-access dead-end** (e.g. WRCC >30-day block) that blocks an experiment →
  surface with the specific station/date/route attempted.

Everything else — running sweeps, fitting, classifying, fetching obs, computing ratios
under fixed conventions — proceed without asking.

---

## 5. SUCCESS CRITERIA (principles + adaptable example thresholds)

Thresholds are **starting values to calibrate against the data**, not law. The
*principle* is fixed; the number is tunable and must be recorded when changed.

- **Amplification ratio is real** if it reproduces at a **held-out** station under fixed
  conventions and the elevation cross-check passes. *Example margin:* held-out predicted
  vs observed ratio within ~15–20% before claiming the physics is captured.
- **A speed/direction bias generalizes** if it beats the delta=0 baseline under LOEO by
  a meaningful margin. *Example:* >0.5 mph (speed) / >2° (direction) beyond baseline —
  tune to the label-RMSE floor; sub-margin = "consistent with zero."
- **The BC-correction adds value** if WindNinja-with-corrected-BC beats both (a) raw
  HRRR 10 m wind and (b) WindNinja-with-raw-HRRR-BC, at held-out terrain stations,
  out-of-sample. If it can't beat raw-HRRR-as-BC, the correction is not yet justified —
  and that itself is a finding.
- **A mechanism classification is trustworthy** only at adequate `evidence_fraction`;
  low-evidence or MIXED labels are surfaced, not asserted.
- **Negative results count.** "No reliable speed bias over low terrain" and "HRRR is
  near-unbiased here" are successes, not failures — they tell us where the correction
  *isn't* needed, which bounds the solution.

---

## 6. EXPERIMENT ROADMAP (order chosen for fastest, cleanest signal)

Scope is open, so this is a priority queue, not a fixed plan. Re-order as data access
dictates; the *dependencies* are what matter.

### Phase A — Close the Camp Fire audit (in progress)
1. Pull verified coordinates for the 5-RAWS network from the live registry; elevation
   cross-check each. (Jarbo, Openshaw, Colby Mtn, Saddleback, Humbug; PG&E Stirling
   City + Red Hill with caution.)
2. Fetch Nov 7–9 2018 obs (sustained **and** gust) for all; clip Jarbo post-burnover.
3. **Two-partition sweep:** (A) fit BC on Jarbo+Openshaw → BC label; (B) validate
   amplification at held-out Colby + Saddleback (literature ~58 mph gust).
4. Report under §3 checks: corrected Jarbo ratio, held-out ratios, speed bias vs raw
   HRRR — each with provenance. **ESCALATE the surviving findings.**

### Phase B — Re-derive Missoula & Thomas under fixed conventions
- The 1.4× "constant" is withdrawn. Re-derive each independently at verified
  coordinates, consistent gust factor, identical BC method. Missoula PNTM8 moved to true
  ridgetop (7897 ft) — its ratio could move either way; don't assume it shrinks.
- Apply the terrain-height guard to both (high-terrain domains).

### Phase C — Build the BC-correction map only if Phase A/B show learnable signal
- Populate the outer-trainer feature set from HRRR for all clean events; run LOEO.
- If LOEO says NO SIGNAL: that localizes the value to direction and/or high-terrain
  regimes — a finding, not a failure. Do not force a model.

### Phase D — Grow N (cheapest path to trustworthy generalization)
- Ingest the Tier-1/2 in-scope library events (Marshall, Labor Day 2020, the Mayacamas
  cluster, Woolsey, North Complex). Non-fire strong-wind events also count.
- Every new event: full §2 conventions + §3 checks. No shortcuts for "easy" cases.

### Phase E — The timing axis (the deferred WHEN problem)
- Formalize the Missoula "coupled window" hand-analysis into a detector: run downscaling
  across a *time sequence* of synoptic states; compare modeled transition to when RAWS
  logged the shift. Use a cheap synoptic ensemble (e.g. HRRRCast's members) for
  arrival-time error bars. (HRRRCast = uncertainty, NOT resolution — it inherits HRRR's
  3 km terrain blindness.)
- This is a **scope-expansion** step → ESCALATE before committing to it.

### Phase F — Uncertainty & deployment (open scope)
- Only after the speed/direction/timing pieces validate out-of-sample. Defer specifics.

---

## 7. STANDING REMINDERS (cheap to state, expensive to forget)

- Rotate any credential that has touched a public repo (the Synoptic token in
  `dec17_final.py` was public — rotate + move to env var + scrub history).
- `git log` shows local HEAD; confirm `git log origin/master` to know what's actually
  pushed before declaring the repo current.
- Reuse `vec_avg` (u/v decomposition) for all direction averaging; never average raw
  degrees. Regress direction as sin/cos, reconstruct with atan2.
- Two BC quantities are NOT interchangeable: domain-mean raw HRRR 700 hPa vs sounding
  700 hPa. Label which is which everywhere.
- Validate on the past to earn trust in the future. The hindcast loop is the product,
  not a detour from it.
```
