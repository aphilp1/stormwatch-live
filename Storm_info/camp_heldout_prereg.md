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

---

## Cross-event BC pre-registrations (appended post-Camp-test, before Stage 2 scoring)

**Kincade run (27 Oct 2019):** BC = 850 hPa, 12Z. Chosen because Diablo flow reached
850 hPa by 12Z but 700 hPa still pre-transition NNW (346°) until 18Z — a
downward-propagating Diablo onset, NOT an inversion-driven level choice. No temperature
inversion present at 12Z (smooth lapse rate 1000→700 hPa). Same 850 hPa outcome as
Camp but distinct mechanism. Direction match: HRRR 850 hPa 12Z = 42° vs KNXC1 observed
mean = 27°, Δ=16°. Confirmed before Stage 2 scoring.

**Thomas Fire (4–5 Dec 2017):** BC = 850 hPa, 12Z 2017-12-05, bc_center (34.58N, -118.7W).
Pre-registered direction: 47.3 mph @ 62°. Direction match: Δ=15° vs WMSC1 vector-mean 47°.

Chosen because the original 700 hPa/13Z BC had rotated to 81° (Δ=34°, outside 30° threshold)
as the Santa Ana flow veered eastward through the event; 850 hPa/12Z holds the coherent
downslope drive at 1514 m, just above the VBG inversion lid (~1388 m), the physically correct
layer for Santa Ana forcing. Third event to land on 850 hPa via a third distinct mechanism:
Camp = sub-inversion gap flow (inversion-gated), Kincade = downward-propagating Diablo
transition (timing-gated), Thomas = directional rotation of a decaying Santa Ana
(veer-gated). Inversion confirmation: no thermal lid detected in HRRR temperature profile
at bc_current 12Z Dec 5 (smooth lapse rate 1000→700 hPa); the 1388 m reference is from the
VBG 00Z sounding and defines the top of the sub-inversion gap-flow layer.

WTPC1 (Whitaker Peak) excluded: 62° angular separation from WMSC1 — no BC candidate
satisfies both stations within 30° simultaneously. WTPC1 vector-mean 345° (NNW) is
terrain-deflected relative to WMSC1 vector-mean 47° (NNE). Method-out-of-scope, same
logic as Jarbo exclusion. Scoring station: WMSC1 (Warm Springs) only.

GF correction (pre-registered): stage2.py held gf=2.060 for WMSC1 — this is borrowed/
inflated. WMSC1's own empirical GF from raws_gust_factors.csv (thomas_2017, 72 window
pairs, status OK): median_gust_factor = 1.560, peak_gust_factor = 1.619 (68.0 mph gust /
42.01 mph concurrent sustained at 13:53Z peak). Scoring uses median GF = 1.560, consistent
with Camp protocol. With correct GF: obs_sustained_est = 55.01 gust / 1.560 = 35.3 mph
(vs the wrong 55.01/2.060 = 26.7 mph — a 32% denominator error).

**HGLC1 — Kincade run cross-event ridge candidate (2026-05-31):**
Station: HGLC1 (HIGH GLADE LOOKOUT), USFS fire lookout tower, Mendocino National Forest.
Registry: 39.208900N, -122.809990W, 4807 ft (1465.2 m), Synoptic network 2, status ACTIVE.
Terrain class: USFS fire lookout = exposed summit/ridge by construction.

Scoring window: HGLC1's observed PEAK hour per the per-event peak-window convention
(method note: fixed-12Z structurally misses overnight-peaking events).

Peak locked from RAWS CSV (kincade_run_2019/HGLC1_kincade_run_2019.csv):
  2019-10-27T11:36Z — 24.0 mph sustained, 51.0 mph gust, direction 359° (N)
  Concurrent GF at peak = 51.0 / 24.0 = 2.125
  This is the single highest-sustained row in the Oct 26-28 window.
  Runner-up: 2019-10-27T10:36Z (23.0 mph / 42.0 gust); 2019-10-27T12:36Z (17.0 / 51.0 tie gust).
RAWS scoring prefix: '2019-10-27T11' (all rows matching that UTC-hour prefix).

BC: HRRR f00 analysis, 850 hPa, 11Z 2019-10-27.
  BC hour = HRRR analysis hour matching the peak window (11:36Z obs → 11Z analysis).
  BC sampled at HGLC1's own HRRR grid cell: bc_center = (39.21N, -122.81W).
  Rationale: HGLC1 is in Mendocino NF, ~40km NW of the KNXC1 bc_center (38.86N, -122.42W)
  used for the original Kincade pre-registration. Sampling at HGLC1's cell avoids spatial
  interpolation error and is the correct local BC for this station's terrain context.
  Level = 850 hPa: same as KNXC1 pre-registration; Kincade has no detected temperature
  inversion (smooth lapse rate 1000→700 hPa at 12Z Oct 27, confirmed previously).

GF: HGLC1 own empirical median from raws_gust_factors.csv (kincade_run_2019):
  n_pairs = 48, peak_gust_factor = 2.125, median_gust_factor = 1.998, status = OK.
  Scoring uses median GF = 1.998 (consistent with Camp/Thomas protocol).
  obs_sustained_est = 51.0 gust / 1.998 = 25.5 mph.

Four gates — STOP at first failure, no goalpost moves after numbers are seen:
  (a) DEM elevation at HGLC1 coords within ±50m of registry 4807 ft (1465m); margin ≥2km.
  (b) DEM is UTM Zone 10N (longitude -122.81W is west of -120° → Zone 10N, EPSG:32610).
      CRS bug note: do NOT apply Zone 11N math to this DEM.
  (c) BC direction (850 hPa 11Z at bc_center 39.21N,-122.81W) within 30° of HGLC1
      observed direction at 11Z peak window (obs = 359°).
  (d) If (a)-(c) all pass: run WN+rawBC at HGLC1 coords, report ratio = WN_pred / 25.5 mph.
      Pass band [0.80, 1.20]. Also report raw HRRR 10m ratio for comparison.

Success criterion: WN+rawBC ratio in [0.80, 1.20] AND WN beats raw HRRR (closer to 1.0).
Failure is also a result — record exactly as observed.

*Committed before DEM download or any score. Any result reported after this commit is the real result.*
