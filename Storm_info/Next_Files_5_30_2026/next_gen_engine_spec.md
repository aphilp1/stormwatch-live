# Next-Generation Wind Engine — Design Specification

Companion to `confidence_field.py` (the buildable-now prototype) and
`stormwatch_test_protocol.md` (the methodology). This is the ambitious target:
an **uncertainty-aware wind engine for complex terrain and extreme fire events**
that doesn't just predict wind — it predicts wind *with a calibrated, spatially
varying, physically-labeled statement of how much to trust each value.*

The organizing thesis: **the leap from a model to a decision-grade tool is the
ability to know what it doesn't know.** This project earned that discipline by
hand (the 1.42× artifact, the +3 mph consistent-with-zero, the hydraulic-jump
method boundary). The engine encodes that same discipline so it scales.

---

## Layer 0 — what we have (the prototype)

`confidence_field.py` decomposes per-cell uncertainty into LABELED sources:
- **BC_SENSITIVITY** (reducible) — ensemble spread over the BC distribution
- **JUMP_REGIME** (irreducible by this method) — the hydraulic-jump method boundary
- **AMPLIFICATION** — extreme nonlinear regime, less validated
- **EDGE_ARTIFACT** — domain-boundary solver artifact
- **BC_INVALID** — terrain-height-guard / 700 hPa-underground
- **OUT_OF_DISTRIBUTION** — terrain unlike any validated station (hook, activates with data)

Each cell carries a confidence value AND a dominant reason, because the reason
determines the operational response (reducible → get better BC; irreducible →
widen margin, different tool). This is buildable now from WindNinja runs + terrain.

The four layers below turn this prototype into the next-generation engine.

---

## Layer 1 — CALIBRATED uncertainty (turn heuristic penalties into probabilities)

**Problem:** the prototype's penalties are physically-motivated heuristics with
tunable knobs. "Confidence 0.3" is meaningful as a ranking, not yet as a
probability. A decision-grade tool needs calibration: when it says "80%
confidence the gust is within ±X," that should be empirically true 80% of the time.

**Approach — conformal prediction against the hindcast library.**
- For each validated event, compute the engine's predicted wind + confidence at
  every station, and the actual error against obs.
- Use the hindcast set as a calibration set: conformal prediction converts the
  raw confidence into a **prediction interval with a guaranteed coverage rate**,
  with NO distributional assumptions — exactly suited to small N.
- Output becomes: "55 mph, 90% interval [48, 67] mph" per cell, where the 90%
  is empirically calibrated on held-out events.

**Why it fits this project:** conformal methods are distribution-free and work at
small N — the regime we're stuck in. And they validate per the protocol: coverage
is checked under leave-one-event-out, so a calibration claim is itself subject to
the same artifact discipline as everything else.

**Stretch:** make the calibration *conditional* on the dominant reason — jump-regime
cells get wider, asymmetric intervals than BC-sensitivity cells, because their
error distributions differ. This is "Mondrian" conformal prediction by reason class.

---

## Layer 2 — SURROGATE WindNinja (unlock ensembles + end-to-end training)

**Problem:** every uncertainty estimate above needs an ENSEMBLE of WindNinja runs
(vary the BC, see the spread). WindNinja is a black-box steady-state solve —
acceptable for a handful of runs, prohibitive for the 100–1000-member ensembles
that calibrated uncertainty wants, and impossible to backprop through.

**Approach — a fast neural surrogate that emulates WindNinja.**
- Train a network: (terrain patch, BC) → wind field, on a large library of
  WindNinja runs you generate yourself (no obs needed — WindNinja is the label).
- Architecture echoes the NeuralGCM lesson: the surrogate is the cheap stand-in
  for the *physics solver*, not a replacement for physics. Keep WindNinja as
  ground truth; the surrogate just makes it fast and differentiable.

**What it unlocks, in order of value:**
1. **Large BC ensembles in milliseconds** → properly sampled BC_SENSITIVITY fields
   and calibrated intervals, instead of a 12-member approximation.
2. **End-to-end BC learning** → because the surrogate is differentiable, the
   HRRR-state→BC map can finally be trained *through* the solver against held-out
   station error (the online-training idea), rather than only via offline labels.
3. **Real-time deployment** → sub-second terrain wind at forecast cadence.

**Validation discipline:** the surrogate must reproduce WindNinja to within a
stated tolerance on held-out terrain/BC combinations BEFORE it's trusted — and
it inherits WindNinja's method boundary (it cannot represent jumps either, by
construction, since its training labels can't). The confidence engine's
JUMP_REGIME flag therefore still applies on top of the surrogate.

---

## Layer 3 — BEYOND STEADY-STATE (the jump/rotor frontier)

**Problem — and it's the deepest one:** the hydraulic-jump finding says the most
dangerous, most erratic winds live precisely in the regime WindNinja (and any
surrogate of it) structurally CANNOT represent. A mass-conserving diagnostic
solver has no non-hydrostatic physics — no jumps, no rotors, no transient
pulsing. Today the engine's correct response is to flag those cells
method-out-of-scope. A next-generation engine for *extreme* events must
eventually do better than flag them.

**Three escalating options, least-to-most ambitious:**

1. **Diagnose, don't simulate (near-term).** Predict *where* and *when* jump/rotor
   conditions occur (Froude, lee geometry, inversion strength, deceleration) and
   attach an empirical "erratic-wind hazard" — a probabilistic gust-envelope and
   variability estimate derived from how observed winds behaved in past jump
   zones — without claiming to resolve the structure. This is a hazard layer, not
   a wind field, and it's honest about being statistical.

2. **Learn the transient correction from obs (medium-term).** Where high-rate obs
   exist in jump zones (the CSU-MAPS lidar in the Camp Fire paper is exactly this),
   learn the residual between steady-state output and observed unsteady behavior,
   conditioned on the jump diagnostics. A data-driven transient correction layer.

3. **Couple to a non-hydrostatic core (long-term).** For the highest-stakes
   forecasts, nest a true non-hydrostatic LES/WRF-LES solve in the flagged jump
   zones only — expensive, but applied surgically where the steady-state method
   has declared itself out of scope. The confidence engine becomes the *trigger*
   for when to invoke the expensive model.

**The unifying idea:** the method boundary isn't a wall, it's a *router*. The
confidence engine says "steady-state is invalid here" → that routes the cell to a
hazard estimate, a learned correction, or an expensive solve, depending on stakes.

---

## Layer 4 — THE INTEGRATION (one product, four questions)

The full engine answers four questions per location, each with calibrated
uncertainty and a labeled basis:

| Question | Layer that answers it | Uncertainty source |
|---|---|---|
| **How strong?** | BC→WindNinja(/surrogate) + amplification | BC_SENSITIVITY, AMPLIFICATION |
| **From where?** | same, direction channel | directional ensemble spread |
| **When does it arrive/shift?** | timing detector (synoptic sequence + ensemble) | arrival-time spread |
| **Can this method even be trusted here?** | mechanism classifier + jump diagnostics | JUMP_REGIME, BC_INVALID, OOD |

The integration product is a **per-cell, per-time wind field with a calibrated
interval and a dominant-reason label** — the thing a fire-weather forecaster reads
as "65 mph from the NE arriving 0400–0600 ±90 min, high confidence; but this
drainage is a jump zone, treat the peak as a floor not a ceiling."

That last clause — the engine volunteering its own limitation — is the
next-generation feature. Everything else is in service of earning the right to
say it.

---

## Build order (respecting dependencies + the protocol)

1. **NOW:** `confidence_field.py` on real WindNinja ensembles (vary BC, ≥12
   members) for Camp Fire once obs/coordinates land. Validate that low-confidence
   cells co-locate with the stations the BC-fit struggles on (the testable
   hydraulic-jump prediction).
2. **Next:** conformal calibration (Layer 1) against the hindcast library as it
   grows — needs ≥ a handful of validated events.
3. **Then:** surrogate WindNinja (Layer 2) — buildable in parallel now from
   WindNinja runs; unlocks large ensembles that make Layer 1 sharp.
4. **Frontier:** jump-zone hazard layer (Layer 3, option 1) — diagnostic only,
   honest about being statistical.
5. **Long-term, scope-decision-gated:** transient correction / non-hydrostatic
   coupling (Layer 3, options 2–3) and full integration (Layer 4).

Each step is subject to the protocol's artifact checks and ESCALATE conditions.
No layer is trusted until it survives leave-one-event-out. Negative results
(a layer that doesn't beat its baseline) are findings that redirect effort, not
failures.

---

## The one-sentence north star

A wind engine that earns a forecaster's trust not by always being right, but by
being **calibrated about when it is right and honest about where it cannot be** —
because in extreme fire weather, a confident wrong number costs lives and a
well-bounded uncertain one saves them.
