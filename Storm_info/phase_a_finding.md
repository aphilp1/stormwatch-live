# Phase A Finding — HRRR Systematic Underbias at Terrain-Exposed Stations

**Date locked:** 2026-06-07  
**Dataset:** hrrr_error_dataset.csv — 165 station-events, 12 events, N=163 active (KEEP+CAUTION)  
**Events:** 10 offshore (diablo/santa_ana), 2 continental (downslope/chinook)

---

## Headline finding

HRRR systematically underestimates wind speed at terrain-exposed (coupled) stations in
offshore/diablo wind events. At coupled ridge stations the underbias is **~−7 mph**.

| Metric | Value |
|---|---|
| Event-level offshore mean (N=10 events) | −3.91 mph |
| Coupled-station mean, offshore regime (N=20) | **−6.89 mph** |
| Intermediate-station mean, offshore (N=48) | −4.62 mph |
| Sheltered-station mean, offshore (N=15) | +3.14 mph |
| Continental events (N=2) | near-zero / ambiguous |

The −3.91 event-level figure is **2.9× diluted** by composite averaging: offshore events
mix ridge and valley stations (sign-incoherent composites). The physically meaningful
benchmark is −6.89 at coupled stations.

---

## Terrain signal

Terrain representativeness error ruled out as primary driver.

- Elevation residual vs speed_err ratio: **0.0076 mph/m** (negligible)
- Representativeness R² ≈ 0 (no linear relationship)
- `flow_coupling` tag ∈ {coupled, intermediate, sheltered} shows monotonic separation
  (offshore: −6.89 / −4.62 / +3.14) — gradient confirms physical mechanism, not DEM artifact

---

## Anchor cases

| Station | Event | Coupling | HRRR err | Note |
|---|---|---|---|---|
| CBXC1 | camp_2018 | coupled | −3.6 mph | Offshore anchor; exposed_ridge, Camp Ridge, 224m relief |
| PNTM8 | missoula_dec2025 | coupled | −5.8 mph | Continental anchor; exposed_ridge, Point Six, 500m relief |

CBXC1 sits within the offshore event-level mean; the coupled-station mean of −6.89
is the correct Phase B benchmark for offshore events.
PNTM8 provides continental-regime confirmation; only 2 continental events so finding
is exploratory there.

---

## Key caveats

1. **Composite structure:** All 10 offshore events are composites (no event >80% sign-coherent).
   The −6.89 coupled mean is the within-event ridge stratum signal, not an event-level mean.
   Do not compare to the −3.91 event average when evaluating WindNinja performance.

2. **Within-regime only:** `flow_coupling` must be applied within-regime. In continental
   (chinook/frontrange) events, coupled stations show HRRR *overbias* (+19.1, +16.7 at
   Marshall Fire). Pooling regimes cancels the signal.

3. **WMSC1 exception:** thomas/woolsey exposed_ridge stations with adiff=151°/134° (lee-facing)
   show extreme underbias (−35.6, −27.0) classified as INTERMEDIATE under the geometry rule.
   These are lee/rotor candidates — not the same physical mechanism as windward enhancement.
   Do not average WMSC1 into the coupled group.

4. **Canyon_gap limitation:** High-relief canyon stations (e.g., PSTM8) may be overcoupled
   if canyon orientation blocks synoptic flow. A known rule limitation; future refinement
   requires canyon orientation geometry.

---

## Phase B implication

WindNinja benchmark: **−7 mph at coupled offshore stations.**

Test question: does WN-on-HRRR recover the −6.89 mph underbias at coupled ridge stations?
Anchor: CBXC1 (camp_2018, offshore) and PNTM8 (missoula_dec2025, continental).
Success criterion: WN error closer to 0 than HRRR error at both anchors.

---

*Derived frame: flow_coupling_draft.csv (read-only, do not overwrite hrrr_error_dataset.csv)*  
*Scripts: offshore_sign_check.py, drop_chac1.py, restore_wmsc1_fix_chac1.py, flow_coupling_draft.py*
