# Post-mortem — SLEC1 = 57 provenance + table-framing errors (2026-06-22)

**Author:** Claude Code (the agent that made the errors)
**Reviewer who caught them:** Opus (separate review pass)
**Scope:** Fire Winds tab "Wind Speed Comparison" table for `camp_2018`, plus the
`station_results.json` value for SLEC1.
**Fix commit:** `b8680db` (pushed to `origin/master`). Verify against that tree.

The reviewer was correct on every substantive point. This documents *how* each
error was introduced, *why* it wasn't caught, and *what* the fix was, so it can be
independently verified.

---

## Error 1 — SLEC1 `WN_a` = 56.9 (should be 49.1): WindNinja cache contamination

### What the table showed
`camp_2018_station_results.json` had `SLEC1.wn_speed_a = 56.9` (ratio 1.63), and the
new dynamic loader surfaced that in the table. The decided/committed value was the
coarse-mesh **49.1**; the HTML still hardcoded 49.1, so the regression was masked
until the dynamic loader started reading the JSON.

### Root cause — a non-deterministic cache glob + an out-of-band experiment
1. Earlier in the session I ran a **one-off mesh-sensitivity experiment** on SLEC1's
   domain (`dem_39.6_-121.0_15mi`, BC `34 mph @ 81°`) at `fine` and `medium` mesh to
   test whether a finer mesh would reconcile toward the audited 39.5. It did not
   (fine = 57, medium = 54.9, coarse = 49.1). That experiment was a manual script,
   **not** part of `hindcast_wn_runner.py`.
2. That experiment wrote extra ASC outputs into the shared WN cache:
   ```
   dem_39.6_-121.0_15mi_81_34_341m_vel-4326.asc   ← fine    → 57.0
   dem_39.6_-121.0_15mi_81_34_482m_vel-4326.asc   ← medium  → 54.9
   dem_39.6_-121.0_15mi_81_34_762m_vel-4326.asc   ← coarse  → 49.1  (the runner's mesh)
   ```
3. `run_wn()` reuses cached output via
   `glob('{stem}_{dir}_{spd}_*_vel-4326.asc')` and returns `cached_vel[0]`. The `*`
   matches the **mesh-resolution** token, so after the experiment the glob matched
   **all three** files, and `glob()` order is filesystem-dependent → it returned the
   **341m (fine)** result.
4. Every subsequent `camp_2018` re-run (the merged-field run, commit `65fa89d`; the
   display-domain run, `1b18a3b`) therefore extracted SLEC1 from the *fine* ASC and
   wrote `56.9` into `station_results.json`.
5. The dynamic station loader added in `e61b32e`
   (`loadExptStationResults`) overrides the hardcoded `wn_stations` with the JSON, so
   the contaminated 56.9 became what the table displayed.

### Why I didn't catch it
- The runner itself only ever runs `--mesh_choice coarse`, so I assumed its output
  was coarse. I did not consider that a **manual** experiment had polluted the shared
  cache the runner reads from, nor that `run_wn`'s cache key is **mesh-agnostic**.
- I trusted the local `hindcast_grids` JSON as ground truth instead of cross-checking
  SLEC1 against the committed record (master status: WN/obs ≈ 1.128 → ~39.5).

### Fix (commit `b8680db`)
- Deleted the contaminating `*_341m_*` and `*_482m_*` ASCs for that domain/BC.
- Re-ran `camp_2018`; SLEC1 → **49.07** (`note: OK`, coarse 762m). Verified in the JSON.
- Scanned the whole cache for any other stem+dir+spd with >1 mesh resolution; only one
  unrelated stale leftover (`dem_39.9_-121.4_12mi`, not in any current domain config).

### Recommended hardening (not yet done)
`run_wn`'s cache glob should be made mesh-deterministic — match the specific mesh it
intends to run (e.g. encode `coarse` resolution in the key, or sort and select
explicitly) rather than `glob()[0]`. As-is, any future multi-mesh run on a domain
re-introduces this class of bug silently.

### Material consequence the reviewer correctly flagged
Even the *correct* coarse value (49.1) is a **+40% overshoot**, not the audited 39.5
near-win. So at the coarse mesh SLEC1 is **not** a clean ridge-niche win. The
exposed-ridge niche is presently solid at **CBXC1 only (n=1)** until the bespoke SLEC1
DEM (which produced 39.5) is found and reconciled. I had been carrying SLEC1 as a
near-win; that is unproven at the pipeline's current mesh.

---

## Error 2 — "WindNinja output ≈ its input" framing (false; contradicts locked finding)

### What I wrote
I headlined the table with "Run 1 (WN) carries the aloft HRRR wind down to the surface"
and described WN as essentially passing the BC through, modulated slightly by terrain.

### Why it's wrong
My own rows refute it: SLEC1 `34 → 49` (amplification), JBGC1 `38 → 35` (deceleration),
CBXC1 `33 → 35`. These are **terrain transforms**, not passthrough. The passthrough
description only coincidentally fits the open/canyon rows I happened to quote
(PSWC1, BNGC1, CDEC1). The **locked finding** is the correct one: *terrain geometry
governs the transform* — CBXC1 decelerates, SLEC1 amplifies (master status,
terrain-geometry section).

### Practical harm of the wrong framing
"WN ≈ BC" implies the remedy is "scale the BC down uniformly." That fails precisely at
terrain-amplifying ridges, where the *correctly sized* BC still gets amplified above
obs. This is exactly why the project plan calls for **per-station WN amplification
factors**, not a uniform BC scale. My framing would have pointed remediation the wrong
way.

### Fix (commit `b8680db`)
Header rewritten to "Run 1 applies a **terrain transfer** to the aloft HRRR wind —
amplifying at exposed ridges, decelerating at gentler terrain (geometry governs the
transform, not a uniform BC scale)." Run 1 is now colored by the **actual WN-vs-obs
result** (match / over / under), with a **Terrain** column as the explanatory variable.

---

## Error 3 — Near-calm denominator artifacts mislabeled as "decoupling"

### What I did
I colored the table by `bc/obs` and called high `bc/obs` "surface decoupled," holding
up **PSWC1 (bc/obs 9.2)** as the cleanest decoupling example.

### Why it's wrong
- PSWC1 obs = **4 mph**, QYRC1 = **2**, BNGC1 = **6** — these sit at/below the
  near-calm range the project already treats as denominator artifacts (e.g. HMRC1 was
  disqualified at ~10.5 mph). A `bc/obs` of 9.2 over a 4 mph obs is the **denominator
  blowing up**, not physical decoupling. `hrrr_coupling_frac` confirms it: PSWC1 cf =
  **0.57** (intermediate), not decoupled.
- PSWC1's time-aligned peak is **2018-11-09 10Z** (next-day, overnight) — a different
  hour than the 11-08 midday window the ridge stations sample. It isn't even the same
  event moment.
- `bc/obs` is the wrong axis generally: it disagrees with the cleaner model-internal
  coupling measure and is obs-denominator-sensitive. (And neither `bc/obs` nor
  `hrrr_coupling_frac` cleanly predicts the WN result — HMRC1 has cf = 0.98 yet WN
  overshoots — which is itself evidence that **terrain**, not a coupling scalar, is the
  governing variable.)

### Fix (commit `b8680db`)
Stations with **obs < 5 OR bc/obs > 3** are greyed and labeled **"near-calm · not
scored"** — an explicit exclusion (the project's own thresholds), not a "decoupled"
claim. This catches exactly PSWC1 / QYRC1 / BNGC1.

---

## Cross-cutting root cause

All three errors share one failure mode: **I built the presentation by reasoning
forward from convenient local artifacts (the `hindcast_grids` JSONs) and the
conversation, instead of validating against the authoritative record** — the committed
master-status findings, the project's near-calm/denominator thresholds, and the
determinism of the tools that produced the numbers. The reviewer's instruction —
"verify against the actual repo rather than reasoning from the transcript" — is the
correct guardrail and is what surfaced all three.

---

## Status after fixes (commit `b8680db`, pushed)
- SLEC1 = **49.1** restored and verified; contaminating ASCs removed.
- Table reframed to terrain-transfer; result-based coloring; near-calm excluded.
- **Still open:** (a) make `run_wn` cache mesh-deterministic; (b) find/reconcile the
  bespoke SLEC1 DEM that yielded 39.5 — until then treat the ridge niche as **n=1
  (CBXC1)**; (c) the runner's internal summary still prints "NICHE WIN" for SLEC1 at
  ratio 1.40, which is itself misleading and should be retired.
