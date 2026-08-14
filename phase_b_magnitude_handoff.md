# STORMWATCH — Phase B: Station-Level Magnitude Calibration

**Handoff to Claude Code**

---

## Where we are

The two-level architecture is **validated as a mechanism**: the inner terrain-override
rule correctly resolves the one sign disagreement (WMSC1/thomas: flat −32.1 → two-level
+10.5) and changes nothing else. Commit 3f5b0af.

But the four-anchor scorecard, **net of raw BC**, is not yet a product:

| anchor | dir | obs | raw WN_err | flat WN_err | 2lev WN_err | net vs raw |
|--------|-----|-----|-----------|-------------|-------------|------------|
| CBXC1/camp     | DOWN | 29.0 | +6.4  | −10.8 | −10.8 | **degraded** |
| WMSC1/thomas   | UP   | 46.0 | −10.2 | −32.1 | +10.5 | sign-rescue, magnitude wash |
| WMSC1/woolsey  | UP   | 45.0 | −0.0  | +9.2  | +9.2  | **degraded** |
| PNTM8/missoula | DOWN | 46.1 | +80.2 | +33.6 | +33.6 | improved (still +33.6) |

Net: 1 improved, 1 sign-rescue/wash, 2 degraded. **Direction is solved. Magnitude is not.**

## The diagnosis

The correction magnitude is **event-calibrated, not station-calibrated**. The outer LOO
delta (18.76 mph for Thomas) is sized for the event mean, so it overcorrects every
station that departs from that mean:
- WMSC1/thomas overshoots: needed +15.3, got +18.76
- CBXC1, woolsey degraded: event-magnitude correction applied to stations needing little/none

This is the **same lesson one level deeper**: event-level *direction* was wrong
granularity (fixed by the inner rule); event-level *magnitude* is wrong granularity (this step).

---

## Step 1 — GATE (cheap, do first): does the direction feature also predict magnitude?

Before building any magnitude model, check whether the features that nailed *direction*
also scale *magnitude*.

- For all active stations in events with ≥8 stations, compute the **needed correction
  magnitude** = `obs − bc_aligned` (this uses obs — it is the LABEL, not a feature).
- Test whether obs-free quantities predict that magnitude:
  - `(1 − coupling_ratio) × bc_aligned`  — the station-deficit estimator
  - `relief_1km × slope` (the terrain-amplification score)
  - `coupling_ratio` alone
- Report correlation (r) of each against the needed magnitude, and the leave-one-event-out
  error if a single-feature rule is used.

**Decision:**
- If `(1−coupling_ratio)×bc_aligned` or the terrain score predicts magnitude (meaningful r,
  LOEO error < event-mean baseline) → magnitude comes nearly free from features already
  validated. Proceed to Step 2.
- If nothing obs-free predicts magnitude → magnitude is a separate hard problem. STOP and
  report: "direction solved, magnitude event-calibrated, not station-predictable at this N."
  Document the overshoot as a known limitation and do not build a model that can't be fed
  at runtime.

---

## Step 2 — (only if gate passes) station-deficit magnitude scaling

Replace the event-mean correction magnitude with a **station-level** magnitude:

```
UP correction magnitude = (1 − coupling_ratio) × bc_aligned    [station-specific]
```

(or whichever Step 1 feature won). The inner rule still decides DIRECTION
(terrain-arm override + coupling arm, the validated 0fabff7 rule); this step sets the
per-station MAGNITUDE rather than inheriting the event mean.

- Keep the **direction rule exactly as committed** (relief>330 AND slope>10) OR (cr>1.08).
  Do not retune it.
- Apply station-level magnitude only to the UP corrections first (terrain arm is the
  zero-false-positive branch — safe to apply aggressively). Treat DOWN-correction
  magnitude separately if needed.

---

## Step 3 — re-run the four-anchor Phase B battery

Same anchors, same scoring (WindNinja output vs RAWS obs, NOT corrected-BC vs anything).

| anchor | obs | raw WN_err | 2lev (event-mag) | 2lev (station-mag) |
|--------|-----|-----------|------------------|--------------------|

**Pass condition:** station-magnitude two-level beats RAW BC at the UP stations
(WMSC1/thomas, woolsey) without degrading the DOWN stations further. WMSC1/thomas should
move from +10.5 toward obs (needed +15.3, not +18.76). Woolsey (bc≈obs, full recovery at
raw) should be left near-untouched — the station-deficit magnitude `(1−cr)` is small when
cr≈1, which should protect it.

---

## Discipline

- **Read-only** on the database; new output file.
- The needed-magnitude LABEL uses obs; every FEATURE must be obs-free. Flag any feature
  that sneaks obs in at runtime.
- Effective N is events (~6), not stations. Single-feature physically-motivated rule, not
  a trained multi-feature model. Same constraint that governed the direction rule.
- Score on WindNinja output vs obs. "Corrected BC looks closer to obs" is intermediate,
  not the deliverable.

---

## Stop and report

The four-anchor table with station-magnitude scaling. The headline numbers:
1. Does WMSC1/thomas land closer to obs than +10.5 (event-mag) — ideally within a few mph?
2. Is woolsey protected (still near obs, not degraded)?
3. Net vs raw across all four: is it now ≥ 3 improved/neutral, or still split?

If station-magnitude scaling gets the UP stations near obs and protects the bc≈obs
stations, the two-level corrected-BC → WindNinja path is a validated rung-2 product and
the next step is the full coupled-station battery benchmarked against HDW.
