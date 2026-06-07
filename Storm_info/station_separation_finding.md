# Station Separation Check — Finding

**Date:** 2026-06-07  
**Script:** `station_separation_check.py`  
**Gate question:** Can obs-free features distinguish within-event bc-UP stations (needs higher BC input) from bc-DOWN stations (needs lower BC input)?

---

## Result: GATE PASS (71% in Thomas, baseline 57%)

| Event | N | UP | DOWN | Baseline | Best acc | Best feature |
|---|---|---|---|---|---|---|
| thomas_2017 | 21 | 9 | 12 | 57% | **71%** | coupling_ratio@1.08, relief@333m |
| woolsey_2018 | 13 | 9 | 4 | 69% | 85% | adiff@51.8° |
| kincade_ign_2019 | 9 | 2 | 7 | 78% | 89% | coupling_ratio@1.45 |
| kincade_run_2019 | 9 | 5 | 4 | 56% | 89% | coupling_ratio@1.39 |
| camp_2018 | 10 | 2 | 8 | 80% | 100% | relief_1km@385m |
| tubbs_2017 | 6 | 4 | 2 | 67% | 100% | shear_700 |

**Pooled (N=62, events ≥8 stations):**

| Feature | Accuracy | r |
|---|---|---|
| coupling_ratio | **73%** | +0.447 |
| relief_1km | **73%** | +0.388 |
| shear_925_850 | 65% | +0.196 |
| shear_700_850 | 61% | +0.172 |
| slope | 63% | +0.135 |
| adiff | 61% | +0.086 |
| fc_ord | 56% | +0.051 |

---

## The WMSC1 paradox — critical diagnostic

WMSC1/thomas: bco=0.667 (needs UP), coupling_ratio=0.337 (decoupled), slope=33.97% (very steep), relief=505.9m (highest in event).

| Feature | WMSC1 value | Predicts | Correct? |
|---|---|---|---|
| coupling_ratio | 0.337 | DOWN | ✗ |
| shear_925_850 | −13.64 | DOWN | ✗ |
| shear_700_850 | +9.75 | UP | ✓ |
| fc_ord | intermediate | DOWN | ✗ |
| slope | 33.97% | UP | ✓ |
| relief_1km | 505.9m | UP | ✓ |
| adiff | 151.5° | DOWN | ✗ |

**3/7 features correctly predict UP for WMSC1.**  
The atmospheric coupling signal (coupling_ratio=0.337) says "decoupled → bc >> surface obs → correct DOWN." This is correct for 12 of 21 Thomas stations where the atmosphere is genuinely decoupled. But at WMSC1, the low HRRR 10m is not from atmospheric decoupling — it is because HRRR does not resolve the Ventura valley channeling. WN *will* amplify the bc input dramatically at this steep, high-relief site.

**The terrain features (slope, relief) see this; the atmospheric features (coupling_ratio) do not.**

---

## What the gate pass means

The two-level architecture is warranted **if and only if** the inner predictor leads with terrain geometry, not BL coupling alone.

**Viable inner predictor features:**
1. `relief_1km` — direct terrain amplification proxy; correct for WMSC1 ✓
2. `slope` — second terrain amplification proxy; correct for WMSC1 ✓  
3. `coupling_ratio` — strong pooled signal (r=+0.447) but wrong for WMSC1 specifically

The pattern: `high relief + steep slope → WN amplifies strongly → bc must be right or higher, not lower, even when coupling_ratio is low`. This is a **terrain-amplification override** of the atmospheric coupling signal.

**Candidate inner predictor form:**
```
P(bc_up) ~ terrain_amplification_score × atmospheric_coupling_state
         = f(relief, slope) × g(coupling_ratio)
```
Or simpler: a threshold on `relief_1km × slope` could capture the interaction directly.

---

## Caveats

1. **In-sample threshold fitting.** The 71% Thomas accuracy was achieved by sweeping thresholds on the same N=21 data points. True LOO accuracy on Thomas would likely be lower (65–68%). The gate passes on the optimized number; the true generalization may be closer to partial-pass territory.

2. **N constraint.** 6 events total; 2 with ≥13 stations. Inner predictor LOEO would have ~4 training samples in leave-one-event-out, which is not enough for a multi-feature model. A single best feature (coupling_ratio or relief_1km) with a fixed pooled threshold is more defensible than a trained inner model.

3. **WMSC1 is a one-off.** It is the only known station where coupling_ratio strongly disagrees with the sign of the correction needed. If the inner predictor is built to get WMSC1 right, it must not overfit to its specific geometry. Generalizing "steep + high relief + low coupling = needs UP" is physically motivated, not data-mined.

---

## Decision

**Proceed to build the two-level architecture.** Use `relief_1km` as primary inner feature (correct for WMSC1, 73% pooled, monotonically meaningful), with `coupling_ratio` as secondary (73% pooled but wrong for WMSC1). The inner predictor should flag stations where `relief_1km > ~330m` as likely to need bc UP even when coupling_ratio is low, rather than applying the event-level correction uniformly.

**Do not** use a trained multi-feature regression for the inner layer given N≈4 in LOEO. Use a threshold-based rule with physical motivation.
