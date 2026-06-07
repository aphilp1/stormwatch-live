# Stage 1 Finding: Time-Alignment of bc_speed Substantially Reduces Thomas Apparent Decoupling

**Date banked:** 2026-06-07  
**Scripts:** `time_align_bc.py` → `time_aligned_bc.csv`  
**Regime scope:** offshore + santa_ana (bc_level=850), 83 station-events, 6 events

---

## Summary

`hrrr_bc_pull.py` pulled bc_speed for each event at the **event-median peak_dt_utc**, not the individual station's own peak hour. For single-day events this is harmless. For multi-day events (Thomas, Woolsey) the median-time bc was compared against stations that peaked far from the median — producing large fictitious bc/obs ratios.

After re-pulling 850 hPa at each station's own aligned peak hour (floor to hour):

| metric | before (event-median) | after (station-aligned) | Δ |
|---|---|---|---|
| Thomas bc/obs median | 1.425 | 1.080 | −0.345 |
| Thomas stations > 1.0 | 81% | 58% | −23 pp |
| Woolsey bc/obs median | 0.876 | 0.848 | −0.028 |
| Woolsey stations > 1.0 | 29% | 29% | 0 pp |
| Thomas−Woolsey median gap | 0.549 | 0.232 | halved |

The Thomas "decoupling" story was substantially a timing artifact. The residual post-alignment gap (0.232) is real but modest and reflects genuine synoptic variability across the 4-day event window, not systematic HRRR 850 hPa failure.

---

## Most Extreme Corrections (Thomas)

| stid | bc/obs before | bc/obs after | offset_h | explanation |
|---|---|---|---|---|
| MOIC1 | 4.13 | 0.703 | −60h | peaked Dec 4 09Z (weak onset); bc pulled from Dec 5 14Z peak (37 mph) |
| OZNC1 | 2.20 | 0.398 | −30h | early onset; aloft wind much weaker at actual peak |
| GMTC1 | 1.654 | 0.826 | (large) | similar early-onset artifact |
| WMSC1 | 1.115 | 0.667 | +36h | peaked Dec 7 02Z (waning); bc pulled from Dec 5 peak (51.3 mph) |

---

## WMSC1/Thomas Anchor Correction

This is the critical case for the WN anchor test.

- **Stale (wrong):** bc=51.30 mph @ 64.6°, bc/obs = 1.115 → labeled "bc/obs > 1 (intermediate decoupled)"
- **Aligned (correct):** bc=30.67 mph @ 58.0° (850 hPa, 2017-12-07 02Z), bc/obs = 0.667 → **coupled**

WMSC1 is now coupled in **both** anchor events:  
- thomas_2017 bc/obs = 0.667 (aligned)  
- woolsey_2018 bc/obs = 0.874

WN anchor test re-run with aligned bc=30.67:

| event | bc_speed | bc/obs | WN_err | recovery | verdict |
|---|---|---|---|---|---|
| thomas_2017 | 30.67 | 0.667 | −10.2 | +25.4 | partial recovery |
| woolsey_2018 | 39.32 | 0.874 | −0.0 | +27.0 | FULL RECOVERY |

At woolsey (bc/obs=0.874), WN amplifies 1.144× → exact recovery.  
At thomas (bc/obs=0.667), WN amplifies 1.166× to 35.8 vs obs 46.0 — 10.2 mph gap remains.  
The gap tracks bc/obs input: WN cannot close a 33% input deficit via terrain alone.  
The stale bc=51.3 input would have produced WN_err ≈ +12 mph (severe overcorrection).

---

## Implications for the BC Learning Pipeline

1. **hrrr_coupling_frac in the database is also stale** — it was computed as `hrrr_10m / bc_speed` where bc_speed used event-median timing. MOIC1's cf=37/8.99=4.1 is a timing artifact (hrrr_10m from Dec 5 peak, obs from Dec 4). The cf column captures the artifact, not the physics.

2. **For the outer BC trainer**, event-mean `hrrr_coupling_frac` is more robust (timing artifacts partially average out across stations). The r=−0.775 correlation with event-mean bc/obs survives because most events are single-day. But for individual station predictions, alignment is required.

3. **For Stage 2 (vertical profile predictor)**: Work only with `time_aligned_bc.csv`. Features must be pulled at each station's own aligned peak hour. The target is `bc_over_obs_aligned`, not the stale `bc_over_obs_old`.

4. **For Phase B Phase A dataset rebuild**: Before outer trainer training on real data, re-pull hrrr_10m at station-aligned times for all 83 offshore+SA rows. This is deferred — the signal is in event-means which are less contaminated.

---

## Gate Result

**Stage 2 is authorized.** The Thomas-Woolsey difference survives in weakened form (0.232 vs 0.549). Coupled/intermediate stations are exposed for profile prediction. The null hypothesis (profile features explain 0, alignment closes the whole gap) is possible and would simplify the pipeline.

**Prior event-level decoupling story (Thomas bc/obs=1.425) is WITHDRAWN.**  
The correct post-alignment statement: Thomas bc/obs median = 1.080 (marginal, mostly coupled); Woolsey bc/obs median = 0.848 (coupled). Residual gap = 0.232 — within reach of synoptic variability across a 4-day event.
