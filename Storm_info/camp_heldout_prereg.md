# Camp Fire Held-Out Test — Pre-Registration

**Written and committed BEFORE any run. Do not modify after commit.**
**Date:** 2026-05-31

---

## Test definition

BC-corrected WindNinja vs raw HRRR 10m wind, scored at held-out terrain stations
CBXC1 (Colby Mountain) and SLEC1 (Saddleback). Neither station used in the fit.

**Fit set (training only):** JBGC1 (Jarbo Gap) + CICC1 (Openshaw). BC correction
derived from these two stations only. Held-out stations see no BC fit signal.

---

## BC input (pre-registered, single value — no sweep)

- **Model:** HRRR analysis, f00 (analysis run, not forecast)
- **Valid time:** 2018-11-08 12Z (single pre-registered hour)
- **Selection rationale:** Closest analysis hour to the observed Jarbo Gap peak
  window (~09–14Z Nov 8). Chosen blind — not selected to favor any result.
- **No hour sweep.** Running multiple hours and picking the best would be
  post-hoc; this hour is locked before execution.

---

## BC level (pre-registered)

**850 hPa.**

Rationale: The 700 hPa surface (~3100m) sits above the Reno inversion
(2307m at REV 00Z, 1516m at 12Z Nov 8 — confirmed from Wyoming soundings
2026-05-30). Camp Fire is a sub-inversion NE gap-flow event; 700 hPa samples
the free-atmosphere westerly above the gap, not the gap flow itself.
850 hPa (1° direction agreement at REV 12Z) is the correct level per
protocol §2.4 as updated this session.

---

## Convention (sustained-to-sustained)

Scoring is sustained-to-sustained throughout. Each station uses its OWN empirical
median gust factor from `raws_gust_factors.csv` (event window, camp_2018):

| Station | Role | Median GF | Source | n_pairs |
|---------|------|-----------|--------|---------|
| JBGC1 | Fit anchor | 1.625 | Pre-registered (52 gust / 32 sustained @ 12:13Z Nov 8) | — |
| CICC1 | Fit B | 1.760 | raws_gust_factors.csv median | 48 |
| CBXC1 | Held-out A | **2.004** | raws_gust_factors.csv median | 48 |
| SLEC1 | Held-out B | **1.732** | raws_gust_factors.csv median | 48 |

GF is used to convert observed gust to estimated sustained for apples-to-apples
comparison with WindNinja's sustained output: `obs_sustained_est = obs_gust / GF`.
The JBGC1 fit anchor uses the pre-registered event-peak value 1.625 (not the
median 1.750), because 1.625 was established before data inspection.

- **Clip JBGC1 after ~06:00 PST 9 Nov 2018** (~14:00Z Nov 9) — burnover/sensor
  artifact. The anomalous 72mph gust at 16:13Z Nov 9 (direction 88–90°) is
  excluded from scoring.
- **Drop Stirling City** (PG&E private station, not in RAWS network, excluded
  from fit and scoring).

---

## Success criterion (protocol §5)

Corrected WindNinja is declared to pass ("workable") if and only if it beats
**BOTH** of the following at the held-out stations, out of sample:

**(a)** Raw HRRR 10m wind at CBXC1 and SLEC1.
**(b)** WindNinja run with raw (uncorrected) HRRR BC at CBXC1 and SLEC1.

Metric: predicted/observed ratio within ~15–20% (i.e. ratio in [0.80, 1.20])
at both held-out stations. A station-by-station ratio table is the output.

**Threshold set before looking at numbers.** Pass or fail, the result is
escalated and recorded in `STORMWATCH_MASTER_STATUS.md` exactly as observed.
No goalpost moves after the number is seen.

---

## What is NOT tested here

- This test does not validate timing — timing thread remains parked.
- This test does not cover convective or PBL-transient events — mechanism
  scope is SYNOPTIC_TERRAIN only.
- Stations in hydraulic-jump zones are method-out-of-scope; none of the four
  Camp Fire stations (JBGC1, CICC1, CBXC1, SLEC1) have been identified as
  jump-zone stations.

---

## Files locked at commit time

| File | Role |
|------|------|
| `raws_obs/camp_2018/JBGC1_camp_2018.csv` | Fit station A |
| `raws_obs/camp_2018/CICC1_camp_2018.csv` | Fit station B |
| `raws_obs/camp_2018/CBXC1_camp_2018.csv` | Held-out target A |
| `raws_obs/camp_2018/SLEC1_camp_2018.csv` | Held-out target B |
| `raws_obs/raws_gust_factors.csv` | Gust factor source |
| `raws_obs/raws_station_registry.csv` | Coordinates + elevations |
| `C:\temp\windninja_cache\dem_40.0_-121.3_20mi.tif` | CBXC1 terrain |
| `C:\temp\windninja_cache\dem_39.6_-120.9_12mi.tif` | SLEC1 terrain (downloaded 2026-05-31) |

---

*Committed before run. Any result reported after this commit is the real result.*
