# ERA5 Reanalysis Boundary-Condition Characterization — Four Extreme Fire-Wind Events

**Status:** obs-independent result, complete and checked.
**Date:** 2026-05-30.
**Companion files:** `ncar_rda_pull_spec.md` (spec), `stormwatch_test_protocol.md`
(methodology), `era5_event_pull.py` (the pull script).

---

## 1. What this establishes (and what it does not)

This work locks down the **synoptic input** side of the wind-coupling problem at
reanalysis quality. For all four primary events it provides a continuous,
**forecast-truncation-free** boundary condition (BC) — the upstream synoptic state
that drives WindNinja — pulled under a single fixed set of conventions over one
consistent domain.

It does **not** close the coupling test. ERA5 at 0.25° (~28 km) is, by design, blind
to canyon-scale terrain channeling. It anchors *what the synoptic flow and inversion
structure were doing upstream*; it does not resolve a Feather River Canyon jet, does
not validate terrain amplification, and its time series are domain-mean (synoptic
positioning), not fire-site timing. The held-out RAWS surface validation remains the
gated critical path. The value here is **sequencing**: the input half is now done, so
that when RAWS access lands, only the output half remains to plug in.

---

## 2. Data and method

**Source.** ERA5 via the Copernicus Climate Data Store (`cdsapi`), datasets
`reanalysis-era5-pressure-levels` and `reanalysis-era5-single-levels`.

**Domain.** One California box covering all four events: N 42°, W −124°, S 35°,
E −117° (CDS `area` order N/W/S/E).

**Levels.** 500, 700, 850, 925, 1000 hPa. 700 hPa is the BC reference level.

**Variables.** Pressure-level: u, v (wind → BC), geopotential (terrain-height guard),
temperature (inversion structure), relative humidity (dryness, secondary).
Single-level: mean sea-level pressure (inverted-trough / Diablo synoptic context).

**Temporal.** Hourly, full 24-hour coverage, three-day window bracketing each
ignition (UTC; local→UTC offset applied per event).

**Conventions (locked, identical across all events).**
- Direction via `vec_avg`: mean the u and v components, then `atan2` — never average
  raw degrees.
- Meteorological FROM-convention for direction.
- Speed in mph (m/s × 2.23694) to match the pipeline.
- Domain-mean is labeled as domain-mean throughout; never conflated with a point value.

---

## 3. Results

700 hPa domain-mean wind (vector-averaged over the box), peak over each window:

| Event | Window (UTC) | Peak speed | Peak dir | Window range | 700 hPa geo-height | Regime |
|---|---|---|---|---|---|---|
| Camp 2018    | 7–9 Nov  | 27.7 mph | 317° (NW) | 3.9–27.7 | 3123 m | NorCal Diablo |
| Tubbs 2017   | 8–10 Oct | 27.2 mph | 310° (NW) | 6.0–27.2 | 3100 m | NorCal Diablo |
| Thomas 2017  | 4–6 Dec  | 37.7 mph |  42° (NE) | 12.3–37.7 | 3117 m | SoCal Santa Ana |
| Kincade 2019 | 23–25 Oct| 18.9 mph |  45° (NE) | 3.5–18.9 | 3181 m | NE ignition-phase* |

\* See §6 — this window captures the ignition phase only, not the destructive 27 Oct run.

**Reading the numbers.** The four BCs are physically coherent and correctly
differentiated by regime. The two NorCal events (Camp, Tubbs) show NW offshore flow
at nearly identical magnitude (~27 mph) — the clean Diablo signature. Thomas is
correctly the standout: NE flow (42°) at the strongest magnitude (37.7 mph), matching
its character as the large wind-driven Southern California Santa Ana event. Kincade
returns NE flow at the weakest magnitude, consistent with having sampled the wind
ramp-up rather than the peak (§6).

---

## 4. The 700 hPa validity check

The 700 hPa geopotential surface sits at ~3100–3180 m domain-mean across all four
events — above the domain-mean terrain in every case. At the domain scale, the BC
reference level is therefore valid without invoking the terrain-height guard.

**Caveat retained:** this is a domain-mean check. Individual high ridge sites (Santa
Ana peaks approaching ~3500 m; Sierra ridges) can locally approach or exceed the
700 hPa height, where the HGT:700 guard must still flag the BC as possibly invalid and
a ridgetop-level wind substituted. The domain-scale clearance does not exempt
per-station validation.

---

## 5. Scope and limitations (explicit)

- **Model input, not surface truth.** Every value here is reanalysis output. Label as
  such everywhere; none of it is an observation.
- **No terrain resolution.** ERA5 cannot and is not meant to show canyon channeling.
  It characterizes the upstream synoptic condition only.
- **Timing is not fire-site timing.** The peak times in the table are domain-mean.
  A domain-mean (or a point) leading the mean is synoptic-scale positioning until a
  control point on the same propagation axis proves terrain — this is precisely the
  trap that produced the withdrawn Tubbs antisymmetry result. The timing thread stays
  **parked**; it requires a separate, pre-registered per-site run with the
  propagation-geometry control, not the domain-mean series produced here.
- **Amplification unvalidated.** Nothing here tests the 3 km → sub-1 km amplification.
  That needs held-out RAWS (Colby/Saddleback) or the CSU-MAPS lidar — still gated.

---

## 6. Kincade caveat (carry this forward)

The Kincade pull window (23–25 Oct) captures the **NW-ignition phase transitioning
into the early NE Diablo**, consistent with the event's documented two-regime
structure. The famous ~102 mph Pine Flat / 93 mph Healdsburg Hills run occurred on
**27 October — outside this window.** The Kincade BC above therefore represents the
ignition phase only and must not be used to characterize the destructive run.

**Action before any Kincade amplification work:** add a second pull window
(26–28 Oct) to capture the 27 Oct Diablo peak.

---

## 7. Provenance and reproducibility

- Retrieval: `era5_event_pull.py` (single argument selects the event;
  `python era5_event_pull.py camp_2018`).
- Credentials: CDS personal access token in `~/.cdsapirc` (kept out of the repo).
- Output: `./era5/era5_pl_{event}.nc` (pressure levels, ~3 MB each) and
  `./era5/era5_sl_{event}.nc` (MSLP, ~0.13 MB each); 8 files total.
- All four pulls completed with no errors and no licence (403) failures.
- Conventions recorded in §2 and enforced in the script.

---

## 8. Where this sits in the plan

This is Phase A/E **input work**: it hardens the BC (Phase A) at reanalysis quality
and provides the clean synoptic series the timing thread (Phase E) will eventually
need — without waiting on observations. It feeds the surrogate-WindNinja ensemble and
the confidence engine as the input distribution both require, all obs-independent.

It does not advance the output side. The held-out RAWS validation
(BC-corrected WindNinja vs raw HRRR at not-fitted terrain stations) remains the single
bar that defines a workable solution, and it is still RAWS-gated.

**Immediate next candidates (obs-independent, unblocked):**
1. ERA5-vs-sounding fidelity check at the verified soundings (Camp REV, Tubbs/Kincade
   OAK) — trust-or-flag ERA5 as a BC source before relying on it.
2. Per-event clean-BC characterization at ignition ±hours (700 hPa speed/direction,
   geopotential-height guard per station, crest-level inversion height/strength from T).
3. Stage the characterized BCs into the BC-sweep apparatus so the input side is locked
   for the moment RAWS lands.
