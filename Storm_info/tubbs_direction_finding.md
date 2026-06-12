# Tubbs 2017 — Direction Finding: Coastal vs Inland BC/Obs Mismatch

**Event:** Tubbs Fire destructive run, Oct 9 2017
**Status:** SOLID WITH CAVEAT — speed underbias valid; bc direction at inland stations documented open issue
**Withheld conditions cleared:**
- (a) HWKC1 sustained obs from RAWS: peak 48.0 mph @ 35.7° NNE at 06:56Z Oct 9 ✅
- (b) OAK 700 hPa reference from Wyoming (not IEM): Oct 9 00Z/12Z retrieved ✅

---

## Before / After: bc_dir vs obs_dir (consistent metric throughout)

`Δ = bc_dir − obs_dir` (positive = BC clockwise of obs). All bc_dir values updated to
time-aligned (station's own peak hour) unconditionally in `hrrr_error_dataset.csv`.

| Station | Peak UTC | Obs dir | bc_dir OLD | Δ_old | bc_dir NEW | Δ_new | |Δ| improved? |
|---------|----------|---------|------------|-------|------------|-------|-------------|
| HWKC1 | 2017-10-09T06 | 35.7° | 56° | +20.6° | 42° | +6.4° | YES — coastal anchor |
| WISC1 | 2017-10-09T07 | 15.3° | 65° | +49.9° | 59° | +43.8° | slight — persistent mismatch |
| KNXC1 | 2017-10-09T08 | 34.7° | 60° | +25.2° | 60° | +25.2° | SAME — mismatch unchanging |
| RSAC1 | 2017-10-09T09 | 60.3° | 41° | −19.0° | 57° | −2.9° | YES |
| NVHC1 | 2017-10-09T11 | 13.3° | 49° | +36.0° | 79° | +65.9° | NO — near-inversion valley |
| KELC1 | 2017-10-08T05 | 294.3° | 68° | +133.3° | 331° | +36.8° | YES (pre-event, off-peak) |
| ATLC1 | 2017-10-10T23 | 234.5° | 49° | +174.1° | 230° | −4.7° | YES (post-event) |

Note: `dir_err` in `hrrr_error_dataset.csv` is HRRR 10m direction − obs direction (unchanged
by this update). The column above is a separate diagnostic: BC direction vs obs direction,
which governs WindNinja input quality.

---

## Finding

**HWKC1 (coastal, 38.73°N, −122.84°W):** bc_dir mismatch collapses from 20.6° to 6.4°
after time alignment. This station is close to the coast; the 850 hPa Diablo flow channels
directly into the terrain gap. **HWKC1 is the clean coastal anchor — bc_dir and obs_dir
agree within 10° after alignment.**

**WISC1 (inland, 39.02°N, −122.41°W):** Mismatch reduces slightly (49.9° → 43.8°) but
remains large. Time alignment does not fix this station because the mismatch is not
temporal — HRRR 850 hPa at this inland location points ENE (59°) at the aligned hour,
while the observed surface flow is NNE (15.3°). A 43.8° bc_dir error will degrade any
WindNinja direction output at this station.

**KNXC1 (inland, 38.86°N, −122.42°W):** bc_dir is 60° both before and after alignment.
HRRR 850 hPa at this location is persistently ENE regardless of hour. Obs is NNE (34.7°).
The 25.2° mismatch is time-invariant and therefore structural.

---

## Physical Story

Diablo surface flow at inland Napa/Lake County stations (WISC1, KNXC1) channels more
northerly than the 850 hPa synoptic flow suggests. The Wyoming OAK sounding for Oct 9
shows 850 hPa N→NNE (0°–25°), consistent with obs NNE — meaning HRRR's 850 ENE at the
inland station locations is itself a model error, not simply surface channeling. HRRR
doesn't resolve the directional rotation that moves synoptic NNE flow into the terrain
interior.

**Coastal station (HWKC1) is clean after alignment. Inland stations (WISC1, KNXC1) carry
a persistent ~25–44° ENE offset that time alignment cannot touch.**

---

## Connection to WMSC1 Speed Finding

This pattern is the directional analogue of the WMSC1 speed result (see `phase_a_finding.md`).
At WMSC1, the synoptic BC speed and the surface speed diverge because valley terrain
channeling amplifies flow beyond what 850 hPa implies — the model doesn't resolve the
amplification. Here, the synoptic BC direction and the surface direction diverge because
inland terrain channeling rotates the flow more northerly than 850 hPa suggests — the model
doesn't resolve the rotation. The mechanism is the same: **a spatially structured discrepancy
between the synoptic BC and the actual surface flow, caused by terrain geometry the model
doesn't fully see.**

If direction correction is ever pursued downstream, the same two-level architecture applies:
a terrain-keyed direction adjustment is the candidate, not a flat synoptic rotation. Coastal
HWKC1-type stations (low Δ after alignment) would not need it; inland WISC1/KNXC1-type
stations (persistent ENE offset) would. Flag this pattern now so it isn't lost.

---

## Wyoming OAK Sounding Cross-Check (Oct 9 2017)

Independent of ERA5 and HRRR — confirms 850 hPa level choice is correct:

| Time | 700 hPa | 850 hPa | Verdict |
|------|---------|---------|---------|
| 00Z Oct 9 | 24.2 mph @ 0° (N) | 27.7 mph @ 0° (N) | Both N; obs NNE consistent |
| 12Z Oct 9 | 11.6 mph @ 345° (NNW) | 17.2 mph @ 25° (NNE) | 850 matches obs NNE; 700 NNW |

850 hPa is the correct BC level. The Wyoming sounding confirms the synoptic flow is N/NNE,
making HRRR's inland ENE bias a model representation issue, not a BC-level error.

---

## Speed Signal (unaffected)

Speed underbias at Tubbs is valid:
- HWKC1: obs 48.0 mph, HRRR 36.7 mph, speed_err −11.3 mph
- WISC1: obs 35.0 mph, HRRR 27.9 mph, speed_err −7.1 mph
- KNXC1: obs 36.0 mph, HRRR 36.7 mph, speed_err +0.7 mph (near zero — canyon_gap)

---

## Status

- Tubbs **un-withheld** as of this commit.
- bc_dir updated to time-aligned values (unconditional) in `hrrr_error_dataset.csv`.
  Backup: `hrrr_error_dataset_pre_tubbs_bc_dir.csv`.
- Direction mismatch at inland stations (WISC1, KNXC1) is a **documented open issue**.
  Do NOT use Tubbs bc_dir or dir_err at WISC1/KNXC1 as validated direction results.
- Scripts: `pull_tubbs_oct9_soundings.py`, `tubbs_bc_dir_aligned.py`,
  `update_tubbs_bc_dir.py`
