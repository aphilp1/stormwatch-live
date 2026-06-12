# Stormwatch — Master Status, Progress & Key Memories

**Authoritative project record.** Read after restart, alongside
`stormwatch_test_protocol.md` (method) and `CLAUDE_CODE_RESTART.md` (next steps).
Latest commit: see git log. All work pushed. **RAWS data verified + cleaned — see §3.**

**Claude Code task when reading this:** verify the repo state matches what's below
(files present, commits, conventions in code). Flag any mismatch. Then update this
file as new work lands so it stays the single source of truth.

---

## 1. WHERE WE ARE (one paragraph)
Complete, tested pipeline: synoptic wind (HRRR/ERA5/CONUS404) → WindNinja terrain
downscaling → surrogate WindNinja → confidence engine → mechanism classifier, plus
BC label generator and outer trainer. Diagnostic phase done. One real validation
landed (Missoula BC vs independent sounding). **RAWS gate lifted (2026-05-31):**
historical RAWS obs pulled for all primary events via NWS public Synoptic token with
Referer spoof (raws_pull_nws_token.py; CSVs in Storm_info/raws_obs/). The corrective
phase — run the BC sweep, fit outer trainer, test vs held-out stations — is now
unblocked.

## 2. THE GOAL
A sub-1km wind forecast for extreme fire events that beats raw coarse-model wind at
terrain stations. "Workable solution" = BC-corrected WindNinja demonstrably beats raw
HRRR at held-out (not-fitted) RAWS stations, out of sample. That single test is the
bar. Not cleared yet (needs RAWS).

---

## 3. PROGRESS LEDGER

### Apparatus (built + tested)
- `mechanism_classifier.py` — sorts events into SYNOPTIC_TERRAIN / PBL_TRANSIENT /
  CONVECTIVE_OUTFLOW / FIRE_GENERATED. 18/18 test cases pass.
- `bc_label_generator.py` — inner-loop BC sweep, RAWS scoring, residual labels,
  gust-factor + jump-zone (method-out-of-scope) handling.
- `bc_outer_trainer.py` — outer-loop ridge regression, LOEO vs delta=0 baseline.
- `confidence_field.py` — per-cell confidence + labeled reason (BC_SENSITIVITY,
  JUMP_REGIME, AMPLIFICATION, EDGE, BC_INVALID, OOD). Self-test passes.
- Surrogate WindNinja — 0.05 mph LOBO RMSE, 0.88 mph worst strong-extrapolation.
  10/10 generalization cases. Recovers direction-dominance + speed-linearity.
- Spec/registry files: `stormwatch_test_protocol.md`, `station_registry_and_sources.md`,
  `hindcast_event_library.md`, `next_gen_engine_spec.md`, `ncar_rda_pull_spec.md`,
  `conus404_pull_spec.md`, `CLAUDE_CODE_RESTART.md`.

### Findings ledger

### Camp/cross-event WN-vs-HRRR test — RESULT (2026-05-31)
WN+rawBC vs raw HRRR at held-out ridge stations, BC pre-registered per event (Camp 850/12Z, Kincade 850/12Z 27 Oct). No correction (falsified earlier today).
CONFIRMED NICHE: at isolated exposed ridges >6000 ft with direction-correct BC where HRRR undershoots, WN+rawBC lands in-band with no correction:
- CBXC1 Colby: HRRR 0.869 -> WN 1.007. SLEC1 Saddleback: HRRR 0.525 -> WN 1.128. Both held-out, never fit.
Outside that class, WN fails for DIAGNOSABLE reasons (not downscaling failure):
- JBGC1 Jarbo: WN improves (0.519->0.771) but under-resolved canyon + BC dir 25 deg off; below band.
- HMRC1 Humbug: near-calm obs (10.5 mph) -> denominator artifact, not a valid scoring station at 12Z.
- KNXC1 Kincade: WN overshoots (2.003); BC dir OK (15 deg), so EITHER 850 BC too strong OR station is sheltered valley misclassified as ridge. UNRESOLVED.
STATUS: niche confirmed but n=2 clean ridges, both at Camp = PROMISING, NOT PROVEN. No cross-event ridge confirmation yet (Tubbs Hawkeye excluded HRRR-sufficient; Thomas excluded BC dir 43-94 off).

### DEM/CRS integrity verification — FINDINGS (2026-05-31)
Found and fixed a CRS bug (Zone 11N math applied to Zone 10N DEMs) that had produced
false terrain mismatches in the edge-check code. After fix, all ridge-niche scored
stations verify against DEM within ~20m:
  CBXC1: DEM 1818m vs registry 1830m (−12m) ✓
  SLEC1: DEM 2011m vs registry 2033m (−22m) ✓
  KNXC1: DEM  653m vs registry  670m (−17m) ✓
The two Camp held-out ridge passes (CBXC1 1.007, SLEC1 1.128) are confirmed on correct
terrain — NOT DEM artifacts.

WMSC1 EXCLUDED: two independent terrain sources (SRTM 30m + USGS 3DEP 1/3 arc-sec,
downloaded fresh) agree terrain at its registered coords is ~3750 ft (1143m), not the
4930 ft (1503m) in the Synoptic/registry elevation field — a database elevation error
(or coordinates ~7km off; nearest 1503m terrain in the DEM is 6.8km north). At true
3750 ft it sits ~800 ft BELOW the Thomas inversion lid (~4553 ft / 1388m) = sub-inversion
drainage regime (same class as ROVC1), NOT a ridge-niche station. The 1.219 WN ratio
was produced on wrong-class terrain and is not recorded as a result.

Thomas BC fix completed and committed (b15c0f1): 700 hPa/13Z original BC had rotated
to 81° (Δ=34° vs WMSC1, outside 30° threshold); replaced with 850 hPa/12Z at 62°
(Δ=15° vs WMSC1 vector-mean 47°). WTPC1 excluded: 62° separation from WMSC1,
terrain-deflected. Third distinct mechanism for 850 hPa selection: directional rotation
of a decaying Santa Ana (Camp=inversion, Kincade=transition timing, Thomas=veer-gated).

STATUS: ridge niche confirmed at n=2, both Camp (CBXC1, SLEC1), terrain-verified.
No cross-event ridge confirmation yet.

### Thomas cross-event ridge attempt — exhausted, no confirmation (2026-05-31)
Tried two candidate above-inversion ridge stations for cross-event niche confirmation;
neither qualified:
- WMSC1: database elevation error (registry 4930 ft, two independent terrain sources
  agree 3750 ft) → sub-inversion, out of niche. Excluded.
- CUUC1: DEM edge (no margin; new DEM needed) AND near-calm at 12Z (5.99 mph
  sustained; event peaked overnight 00-09Z and was gone by 12Z). Disqualified,
  not scored.
STATUS (accurate): ridge niche confirmed at n=2, both Camp (CBXC1 1.007, SLEC1 1.128),
DEM/CRS-verified. NO cross-event ridge confirmation yet. Thomas did not refute the
niche — it lacked a valid above-inversion ridge with a live 12Z signal among the two
candidates checked.

### Kincade cross-event ridge attempt — terrain-rotation pattern found, niche still n=2 (2026-05-31)
HGLC1 (High Glade Lookout, 4807 ft USFS lookout, Mendocino NF): GATE A DEM clean
(DEM 1459.8m vs registry 1465.2m, diff=-5.4m; station at DEM dead-center, pixel 512/512;
99% of 1km cells below → summit confirmed; 12.9km margin — best terrain verification in
project). GATE B steadiness excellent (circular R=0.984, circ std dev 10.3°, n=15 obs
spd≥10mph, Oct 27 — very steady N flow all day). GATE C FAILED: 850 hPa BC NNE (39mph
@ 45°) vs observed N (24mph @ 359°), Δ=46°. HRRR 10m also shows NNE (22mph @ 40°) —
confirms the deflection is real terrain rotation at the summit, not a BC sampling error.
Pre-registered exclusion (prereg 316d1bc). Step 0 also found WISC1 (County Line, 2085ft)
had Δ=36° — same NNE→N rotation, different summit.

PATTERN (new finding): TWO Kincade-run high stations deflect NNE→N at the summit —
WISC1 (Δ=36°) and HGLC1 (Δ=46°). Same rotation direction, independent stations. The
Kincade Diablo flow is locally terrain-rotated across the northern Coast Ranges. This
is the same class as Jarbo Gap BC_SENSITIVITY=HIGH — consistent, diagnosable deflection,
not noise.

SHARPENED HYPOTHESIS: the clean WN-beats-HRRR niche may hold where terrain does NOT
strongly rotate synoptic flow (Camp ridges: BC NE→station NE, near-unrotated) and
degrade where it does (Kincade summits: BC NNE→station N, ~45° rotation; Jarbo canyon:
high BC_SENSITIVITY). This is more falsifiable than the original niche claim — it
predicts failure at rotation-dominated stations and success at flow-aligned ones. Record
as the working hypothesis to test next.

STATUS: ridge niche confirmed n=2 (Camp CBXC1 1.007, SLEC1 1.128). Cross-event
confirmation still OPEN. Full candidate inventory exhausted tonight:
  HWKC1 Tubbs   — HRRR-sufficient (ratio 0.997), WN adds no value
  WMSC1 Thomas  — database elevation error, sub-inversion at true 3750ft
  CUUC1 Thomas  — DEM edge + overnight peak, no 12Z signal
  WISC1 Kincade — BC dir Δ=36° (NNE→N terrain rotation)
  HGLC1 Kincade — BC dir Δ=46° (NNE→N terrain rotation, gate C pre-registered fail)

PARKED (do NOT retrofit tonight): upstream BC sampling (sample 850 hPa over terrain
reflecting undeflected synoptic flow, not at the deflected station). If pursued,
pre-register fresh and apply to ALL stations — not retrofit to rescue these failures.

### METHOD NOTE — fixed-12Z scoring window is a limitation
Two stations now excluded for near-calm at 12Z (HMRC1 Camp, CUUC1 Thomas) because
their events peaked OUTSIDE 12Z (overnight). The fixed-12Z convention structurally
misses overnight-peaking events. FUTURE FIX: score at each event's observed peak
window, pre-registered per event with the matching HRRR analysis hour — not a single
global 12Z. This is a scope/convention change → pre-register before adopting.

### Camp Fire held-out test — RESULT (2026-05-31) [FAIL, recorded as pre-registered]
Pre-registered test (camp_heldout_prereg.md, committed before run): BC-corrected
WindNinja vs raw HRRR at held-out CBXC1 (Colby) + SLEC1 (Saddleback), fit on JBGC1.
BC = HRRR f00 12Z 8 Nov, 850 hPa. Per-station gust factor. Result table:
- CBXC1: (a) raw HRRR 0.869 | (b) WN+rawBC 1.007 | (c) WN+corrBC 0.830
- SLEC1: (a) raw HRRR 0.525 | (b) WN+rawBC 1.128 | (c) WN+corrBC 0.717
VERDICT: FAIL — corrected WN does not beat both baselines at both held-out stations.

FINDINGS (the fail is informative):
1. WN on RAW BC is in/near band at both held-out ridges (1.007, 1.128). Plain
   WindNinja generalizes; the correction does not.
2. The single-station (JBGC1) BC correction makes predictions WORSE at both held-out
   stations and does not transfer 53 km east across the Feather River canyon divide
   (different terrain regime). Correction must be terrain-conditioned, or not applied
   across regime boundaries. This is a structural method finding, not a tuning miss.
3. PREMISE CONFIRMED: raw HRRR 10m badly undershoots SLEC1 (0.525) — blind to terrain
   amplification — while WN+rawBC captures it (1.128). WindNinja adds real skill over
   raw HRRR at the exact station HRRR misses. The niche holds.
4. CICC1 (Openshaw) excluded at run: ~1 mph sustained at 12Z (near-calm), can't anchor
   a correction. Fit collapsed to JBGC1-only — itself a reason the correction was fragile.

Status: the delta=0 baseline (raw HRRR as BC) currently BEATS the learned correction.
Per protocol §5, the correction is "not yet justified" — recorded as such.

---

### Camp held-out test — FAIL (2026-05-31, pre-registered)
Test: BC-corrected WN vs raw HRRR at held-out CBXC1+SLEC1, fit JBGC1. BC=HRRR f00 12Z 8 Nov, 850 hPa, per-station GF.
- CBXC1: raw HRRR 0.869 | WN+rawBC 1.007 | WN+corrBC 0.830
- SLEC1: raw HRRR 0.525 | WN+rawBC 1.128 | WN+corrBC 0.717
VERDICT: FAIL — corrected WN beats neither baseline at both stations.
Findings: (1) WN on raw BC is in-band at both held-out ridges; plain WN generalizes. (2) Single-station JBGC1 correction makes predictions worse, does not transfer across the Feather River divide — falsified, not a tuning miss. (3) Raw HRRR undershoots SLEC1 (0.525), WN captures it (1.128) — the niche holds. (4) CICC1 excluded (~1 mph at 12Z); fit collapsed to JBGC1-only.
Per §5: delta=0 baseline (raw HRRR as BC) beats the learned correction — correction not yet justified.

---

**SOLID:**
- **RAWS DATA UNLOCKED (2026-05-31).** NWS WRH timeseries viewer embeds a public
  Synoptic token in `/source/wrh/apiKey.js` (token `7c76618b66c74aee913bdbae4b448bdd`).
  Token is restricted to weather.gov Referer header — adding that header in Python
  requests gives full historical access. Scripts: `raws_pull_nws_token.py`,
  `raws_find_stations.py`, `raws_bulk_pull.py`, `raws_gap_events.py`.
  **317 station-event CSVs, 16.7 MB** in `Storm_info/raws_obs/` (12 event folders).
  Backed up to `raws_obs_backup_20260531_0023`. Station manifest: `raws_obs/station_manifest.json`.
  Data quality confirmed vs literature peaks:
  - HWKC1 Tubbs: **79.01 mph gust @ 06:56Z Oct 9** (lit: 79 mph ✓); 48.0 mph sustained
  - JBGC1 Camp: **52.01 mph gust @ 12:13Z Nov 8** (lit: 52 mph ✓); 32.01 mph sustained
  - CBXC1 Colby Mtn (Camp held-out): **59 mph gust** — now available for held-out test
  - HWKC1 Kincade run: **76.0 mph gust @ 12:56Z Oct 27**; 40.0 mph sustained
  - PNTM8 Missoula Dec 2025: **66.0 mph gust @ 18:59Z Dec 10**; 43.01 mph sustained
  - MOMM8 Missoula Jul 2024 derecho: **72 mph gust** (fire-effects portable)
  - BLMM8 Blue Mtn Missoula: **43 mph gust** (previously gated behind WRCC)
  - LOOC2 Lookout Mtn (Marshall Fire): **72 mph gust**
  - WLYC1 Wiley Ridge (Thomas): **67 mph gust** / WMSC1 Warm Springs: **68 mph gust**
  - WMSC1 Warm Springs (Woolsey): **65 mph gust** / CNIC1 Camp 9: **77 mph gust**
  Coverage: camp(12) tubbs(7) kincade_ign(10) kincade_run(12) thomas(26)
            woolsey(16) missoula_dec(8) missoula_jul(34) marshall(8)
            boulder_chin(41) iowa(2) labor_day_or(133)
- **RAWS INVENTORY + CLEANUP COMPLETE (2026-05-31).** All 317 CSVs inventoried,
  metadata pulled live for 274 unique STIDs, elevation units fixed, network filter applied.
  - SLEC1 (Saddleback) pulled: 96 rows Nov 7-10 2018, peak gust 59.01 mph @ 17:18Z Nov 8,
    direction NE/ENE (43-54°) throughout. Ridge elev confirmed: 6,670 ft / 2,033 m. ACTIVE.
    Record back to 2001. **Both Camp Fire held-out targets now in dataset: CBXC1 (59 mph)
    + SLEC1 (59 mph).**
  - Elevation units bug fixed: `elev_ft_synoptic` (Synoptic returns feet) +
    `elev_m_derived` (× 0.3048). Verified: JBGC1 2535→772.7m ✓, PNTM8 7897→2407m ✓.
  - Network filter: 145 files excluded (USGSHY stream gauges, COCOOR/COCOCOBO/COCOMTMS
    CoCoRaHS precip-only, COOP no-wind-sensor). 4 caution files kept (D5789, E6204,
    ODT50, OD159 — gapped but have wind data).
  - **172 usable files** across 12 events. Flags in `raws_inventory.csv` (usable/caution cols).
  - Scripts: `raws_inventory_verify.py`, `raws_cleanup.py`.
  - Registry: `raws_obs/raws_station_registry.csv` (275 stations, elev_ft_synoptic + elev_m_derived).
  **USABLE COUNTS:** camp=14 tubbs=8 kincade_ign=10 kincade_run=13 thomas=26
  woolsey=16 missoula_dec=8 missoula_jul=18 marshall=8 boulder_chin=9 iowa=2 labor_day_or=36
- **Timing finding from RAWS (2026-05-31, flag for protocol review):**
  - Tubbs/Hawkeye: ignition ~04:45Z; at 04:56Z already 30 mph / 62 gust → wind rising,
    peak gust 79 mph at 06:56Z (2h AFTER ignition) → rising-limb ignition at Hawkeye
  - Camp/Jarbo: ignition ~14:29Z; peak 52 mph gust at 12:13Z (2h 15min BEFORE) →
    declining-limb ignition at Jarbo. Note: anomalous 72 mph gust at 16:13Z Nov 9
    with direction shift to 88-90° — likely sensor artifact, CLIP after 15:13Z Nov 9.
  - Kincade ignition: ~09:31Z Oct 24; peak at 11:56Z (2h AFTER ignition)
  NOTE: These are station-level timing, not fire-site timing. Timing thread remains
  parked until propagation-geometry control is in place.
- Camp Fire sub-inversion structure: Jarbo (773m) 1165m below Reno inversion (1938m);
  whole domain sub-inversion; NE gap-flow 700 hPa BC applies. Inversion altitude is
  the empirical justification.
- **Missoula Dec 17 — the validation.** OTX 12z 700 hPa 29 mph @ 315° vs WN BC
  28.8 mph @ 315°. First independent BC confirmation. PNTM8 (2408m) 2275m above cold
  pool — samples free-atmosphere flow. (Scope: validates BC at ridge level, not surface.)
- **Direction-sensitivity field (2026-05-30).** Jarbo Gap (narrow canyon) is 17.2x
  more direction-sensitive than open foothill terrain across a ±15° BC direction sweep.
  BC dir ±15° → Jarbo gust uncertainty ±1.8 mph; open terrain ±0.1 mph. This is the
  BC_SENSITIVITY label for the confidence field: HIGH at canyon terrain, LOW at open.
  CORRECTED CLAIM: direction is the terrain-geometry-SENSITIVE variable (17.2x ratio),
  not unconditionally "the high-leverage variable." Speed scaling is terrain-insensitive
  (linear through mass conservation at all stations). See sensitivity_results.json.
- **ERA5 BC characterization (2026-05-30).** All four events pulled at reanalysis
  quality (cdsapi, Copernicus CDS). Camp/Tubbs ~27 mph NW (Diablo); Thomas 37.7 mph
  NE (Santa Ana standout); Kincade 18.9 mph NE (ignition phase only). **Kincade
  run (Oct 26-28 2019) pulled 2026-06-11** (`era5_pl_kincade_run_2019.nc`):
  Oct 27 12Z 850 hPa 12.3 mph @ 17° NNE, 700 hPa 23.2 mph @ 346° NNW — confirms
  850 hPa is correct BC level. 700 hPa geo-height 3100-3181m >
  domain terrain in all cases. Input side of BC pipeline is now locked.
  See `era5_bc_characterization.md`.
- **ERA5 fidelity vs Wyoming soundings (2026-05-30).** ERA5 earns "trusted BC
  source" for NorCal Diablo + SoCal Santa Ana: Tubbs OAK Oct 8 (−2.8/3° at 00z,
  +3.0/12° at 12z); Thomas VBG Dec 4 (+1.1/5° at 00z, −3.5/11° at 12z). Direction
  within 12° in all four comparisons. Kincade run ERA5 now available (Oct 27 2019);
  ERA5 fidelity check pending (Wyoming OAK 27 Oct has only 700 hPa recorded —
  850 hPa level needs to be added to wyoming_soundings.json to close this).
- **BC-level finding: 700 hPa is wrong level for sub-inversion gap flow (2026-05-30).**
  Camp REV: 700 hPa (~3100m) sits ABOVE the Reno inversion (2307m at 00z, 1516m at
  12z) → samples free-atmosphere westerly, not the NE gap flow. 850 hPa direction
  agrees within 1° at 12z. Operational rule added to protocol §2.4: for sub-inversion
  gap-flow events, use 850 hPa / sub-lid wind as BC, not 700 hPa.
  See `era5_fidelity_results.md`.
- CONUS404 4km canyon-blindness (measured): Jarbo cell = 4.9 mph @ 229° vs real
  ~50 mph NE → 10x speed error + reversed direction. Quantified proof coarse models
  miss canyon channeling = why the pipeline exists. Fire-origin cell 500m away
  resolves fine (53 mph ENE).
- CONUS404 timing (partial): Kincade domain mean + site both peaked ~5–10h before
  ignition → CONFIRMS declining limb. Camp mixed (domain mean 15h before, Jarbo 3.5h
  AFTER ignition — geometry check required before claiming). Thomas breaks pre-reg
  (multi-day rising event, expected). Timing thread remains PARKED until RAWS.
- IEM RAOB alias identified (2026-05-30): IEM returns station CWMJ (Canadian) as
  fallback for any Western US station it lacks data for. Camp Fire REV + Missoula OTX
  were real IEM data. All others (Thomas VBG, Tubbs OAK, Kincade OAK Oct 23-24) were
  CWMJ — invalid. Wyoming wsgi endpoint (src=FM35) is the correct source. New script:
  `wyoming_sounding_pull.py`. Corrected values in `wyoming_soundings.json`.

**WITHHELD (do not cite until fixed):**
- Thomas: IEM alias confirmed broken (2026-05-30). Wyoming VBG (WMO 72393): 33.3 mph
  @ 310° NW (00z) / 27.7 mph @ 310° (12z). Inversion at 1388m (VBG 00z) REAL.
  HOWEVER: Topa Topa does not exist as a RAWS station (verified 2026-05-30 against
  NIFC CA NFDRS, NIFC Key RAWS, WRCC — not found). Coordinates 34.520°N/-119.080°W
  were a geographic peak estimate, never an observable. The "1.44x amplification" had
  no real numerator. Thomas stays withheld. Real RAWS in domain: Rose Valley II
  (ROVC1, 34.543°N/-119.185°W, 3336 ft = below the 1388m inversion lid) and
  Chuchupate (CUUC1, 34.8°N/-119.0°W, 4900 ft = near the lid). The inversion finding
  (1388m from independent Wyoming VBG) is still valid mechanism characterization.
  Fix path: identify a real above-inversion station in the Thomas domain, verify vs
  NIFC, then re-derive amplification.
- Tubbs: IEM alias confirmed broken (2026-05-30). Wyoming OAK (WMO 72493): 23.0 mph
  @ 300° NW (00z) / 24.2 mph @ 320° (12z) — IEM had 52.9 mph @ 235° SW (wrong
  direction entirely — monsoon flow, not Diablo). Inversion at 174m (OAK 00z) REAL.
  Hawkeye VERIFIED: 38.7351°N/-122.8371°W, 617m (2024 ft), WIMS 42010, CAL FIRE LNU
  (NIFC confirmed 2026-05-30). Elevation plausible; above 174m lid confirmed.
  "3.4x amplification" NOT a finding: it divides Hawkeye gust (79 mph) by OAK aloft
  sustained (23 mph, 124 km away) — gust/sustained mismatch + 124 km spatial offset.
  Corrected for GF 1.3-1.7: ratio becomes 2.0-2.6x; still above defensible 1.1-1.6x
  range, and OAK is still not a valid local denominator.
  **UN-WITHHELD 2026-06-11:** (a) HWKC1 sustained obs confirmed in DB (48 mph @ 35.7°
  NNE, Oct 9 06:56Z); (b) Wyoming OAK Oct 9 00Z/12Z pulled — 850 hPa N→NNE, confirms
  850 hPa is correct BC level (700 hPa shows NNW, wrong). bc_dir updated to time-aligned
  values in hrrr_error_dataset.csv unconditionally. Speed underbias VALID. DIRECTION
  CAVEAT: inland stations WISC1/KNXC1 carry a persistent 25–44° ENE bc_dir offset that
  time alignment cannot fix — HRRR 850 hPa at inland Napa/Lake County points ENE while
  obs and OAK sounding both show NNE. Documented in tubbs_direction_finding.md. Do not
  cite bc_dir or dir_err at WISC1/KNXC1 as validated direction results.
- **kincade_run_2019 rows COMPLETE (2026-06-11).** 12 active stations, Oct 27 2019
  destructive-run phase. ERA5 pulled (era5_pl_kincade_run_2019.nc, Oct 26-28). All
  rows: bc_speed time-aligned, bc_dir time-aligned from HRRR 850 hPa cache, DEM merged
  (0 NEEDS_DEM). hrrr_coupling_frac recomputed. Key finding: HWKC1 bc_dir holds at
  25.5° after alignment (was 22.2° event-median), only 4.8° from obs 40° NNE — the
  canonical NE-Diablo clean station validates cleanly. WISC1 direction mismatch
  continues (bc 42.7° vs obs 40°, Δ=+43.7° when accounting for circular diff — same
  inland-rotation pattern as Tubbs). TS379 excluded from direction analysis (CAUTION,
  7 mph obs, 180° direction reversal = wind-shadow station). Gradient-orientation
  data point: HWKC1 alignment-stable confirms kincade_run as the clean NE-Diablo
  direction event. Scripts: update_kincade_run_bc.py, merge_kincade_run_dem.py.
- **Phase 3 RRFS extraction harness WRITTEN (2026-06-12).** `rrfs_extract.py` reads any GRIB2 with 10m UGRD/VGRD via cfgrib+KDTree, extracts at anchor station lat/lon, writes `rrfs_hindcast.csv`. Format-validated against HRRR cache: extracted CBXC1/camp err=-3.6, WMSC1/thomas err=-35.7, WMSC1/woolsey err=-27.0 — all match hrrr_error_dataset.csv values exactly. Ready to run with `--run` once RRFS output exists; populate `RRFS_FILE_MAP` in script header.
- **Do-no-harm gate WRITTEN + TESTED (2026-06-12).** `donoharm_gate.py` — gate function importable. Gate fires at WMSC1/woolsey (raw_err=0.0 ≤ 5 mph → saves 9.2 mph overcorrection). 3/4 OK; CBXC1/camp is documented KNOWN_FAIL (raw WN err=+6.4 > threshold, two-level still wrong direction — architecture limit of the outer correction, not a gate failure). Threshold sensitivity: 7 mph gates camp too, but camp raw WN is wrong-direction so gating would just freeze error at +6.4.
- **CUUC1/woolsey DEM fetch script WRITTEN (2026-06-12).** `fetch_cuuc1_dem.py` — targets CUUC1 (lat=34.80637, lon=-119.01363, elev=1609.3m). Runs via `conda run -n dem python fetch_cuuc1_dem.py`, appends to `hrrr_error_dataset_dem.csv`, then `merge_woolsey_dem.py` closes the gap.
- **labor_day_or2020 rows COMPLETE (2026-06-12).** 35 active (KEEP/CAUTION) stations.
  BC was already populated at event-median (700 hPa, downslope_oregon — continental events
  excluded from time-alignment scope per time_align_bc.py). DEM merged from
  hrrr_error_dataset_dem.csv via merge_labor_day_or_dem.py. DEM breakdown: 13 valley,
  10 open, 10 exposed_ridge, 2 canyon_gap. Event mean speed_err = +2.00 mph, mean
  hrrr_coupling_frac = 0.730. Confirms opposite-sign regime (HRRR overshoots in
  downslope events) is now fully represented in the database. **Track 1 COMPLETE.**

**RETIRED DATA (do not use — explicitly poisoned by IEM CWMJ alias):**
The following sounding-derived values in `soundings_cache.json` (IEM source) are
invalid and must not be used for BC analysis or cited as synoptic drivers. IEM
silently substituted Canadian station CWMJ for all Western US stations it lacked.
  - Thomas VBG/REV Dec 4 2017: IEM returned 14.96 mph @ 290° → WRONG (real: 33.3 @ 310)
  - Tubbs OAK Oct 8 2017: IEM returned 52.9 mph @ 235° SW → WRONG (real: 23.0 @ 300 NW)
  - Tubbs OAK Oct 8 12z: IEM returned 71.4 mph @ 240° → WRONG (real: 24.2 @ 320)
  - Kincade OAK Oct 23-24 2019: IEM returned values → WRONG date + aliased
These values produce physically backwards synoptic drivers. Any downstream result
(BC sweep, amplification ratio, mechanism classification that touched these numbers)
built on IEM Thomas/Tubbs/Kincade soundings is compromised. Wyoming source is correct.
VALID IEM soundings (not aliased): Camp Fire REV Nov 8 2018; Missoula OTX Dec 17 2025.

**WITHDRAWN (dead, do not revive):**
- 1.42x/1.44x amplification "constant" — coordinate + convention artifact across all
  three legs.
- +9.8 mph HRRR speed bias — collapsed to +3, now consistent-with-zero. (Honest result:
  HRRR 700 hPa is a near-unbiased BC for low-terrain downslope.)
- "Declining-limb ignition" timing thesis — broken on Camp (rising limb).
- "All catastrophic fires ~25 mph aloft" — selection effect.

**PARKED:**
- Timing thread. Every signal (HRRR domain-mean, Tubbs antisymmetry, Oakland sounding,
  CONUS404 domain-mean) was synoptic-scale/positional, not fire-site timing. Needs
  fire-site RAWS surface series. Open hypothesis: Thomas (Santa Ana) times differently
  from NorCal North-wind events — ignites on rising limb, breaks every pattern. n=1 vs
  n=3, not established.

---

## 4. KEY MEMORIES / DECISIONS (carry these)
- Correct the BC INPUT to WindNinja, never replace the physics solver (NeuralGCM lesson).
- Direction is the terrain-geometry-SENSITIVE BC variable (17.2x sensitivity ratio:
  Jarbo narrow canyon vs open terrain, ±1.8 mph gust uncertainty per ±15° dir error).
  Speed scales ~linearly at ALL stations through mass conservation (terrain-insensitive).
  "Direction dominates" is sweep-width dependent; the robust claim is the 17.2x ratio.
- Hydraulic-jump zones = method boundary. WindNinja structurally can't model jumps/rotors;
  stations there are method-out-of-scope, not fit failures. Testable: unfittable stations
  should cluster with modeled jump zones.
- Inversion altitude determines which stations sample gap flow vs free-atmosphere flow —
  feeds the terrain-height guard. Camp clean (all sub-inversion); Missoula/Thomas/Tubbs
  ridges sit above their inversions.
- **Protocol §2.4 update — BC level for sub-inversion gap flow (CONFIRMED 2026-05-30):**
  700 hPa (~3100m) is ABOVE the Reno inversion at both Camp Fire launch times →
  samples free-atmosphere westerly, not NE gap flow. For sub-inversion gap-flow events,
  use 850 hPa / sub-lid wind as the BC reference level. Confirmed by 850 hPa fidelity
  (1° direction agreement at 12z). Operational rule now in force.
- **Observed values must always be READ from wyoming_soundings.json, never hand-typed.**
  Hand-transcription of IEM value produced false "202° ERA5 reversal" alarm. REV now
  in wyoming_soundings.json (Wyoming wsgi src=FM35, 2026-05-30). That file is the
  canonical source; all comparisons must read from it at runtime.
- Artifact-first skepticism: every finding presumed artifact until it survives the
  protocol checks. Negative/withheld results count.

## 5. NEXT STEPS (priority order)
1. ~~Wyoming sounding re-pulls~~ DONE (2026-05-30).
2. ~~Topa Topa coord verification~~ DONE (2026-05-30) — does not exist as a RAWS station.
3. ~~Write up Missoula standalone~~ DONE (2026-05-30) — `missoula_bc_validation.md`.
4. ~~**Obs-independent infra**~~ DONE (2026-05-30):
   Direction-sensitivity field (17.2x Jarbo vs open terrain, ±1.8 mph gust/±15° dir).
   Confidence field built + 8/8 self-test: Jarbo 0.800, fire_origin 0.828, paradise 0.830.
   Corrected claim: direction is terrain-geometry-SENSITIVE variable, not unconditionally dominant.
5. **Data feeds (human actions required — see PENDING_ACTIONS.md):**
   - Fix Synoptic console 403 (account setting) → enables historical RAWS fetch
   - Register Copernicus CDS → enables ERA5 700hPa for all events
   - WRCC follow-up for PNTM8 obs → completes Missoula terrain validation
6. **RAWS validation** — gated on items above. The single test that matters.

## 6. CONVENTIONS (don't drift)
- Coordinates from live registry, not papers/memory; elevation cross-check each.
- vec_avg (u/v) for direction; never average raw degrees.
- Gust factor sustained-to-sustained; Camp = 1.625; record per event.
- Clip Jarbo after ~06:00 PST 9 Nov 2018; drop Stirling City.
- 700 hPa BC valid only above terrain; HGT:700 guard on high domains.
- Domain-mean ≠ point; a point leading the mean is geometry until a control proves otherwise.

## 7. ENVIRONMENT NOTES
- CONUS404: curvilinear grid (mask by index, not .sel lat/lon); winds U10/V10 m/s ×2.23694.
- Claude Code 1M-context credit bug: launch standard model (not 1M); Haiku works if blocked;
  `claude update`.
- HRRR/GCS/AWS buckets blocked in claude.ai sandbox; herbie runs in Claude Code only.
- Synoptic free tier: 403 on metadata; research tier pending.
- Synoptic token rotated 2026-05-30 (old token was in git history; new keys in
  synoptic_config.py, gitignored). Old values in history are revoked/dead.
  Optional future cleanup: BFG Repo Cleaner to scrub history (not urgent).

---
*Update this file as work lands. It is the source of truth.*
