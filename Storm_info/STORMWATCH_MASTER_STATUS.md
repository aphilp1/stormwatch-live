# Stormwatch — Master Status, Progress & Key Memories

**Authoritative project record.** Read after restart, alongside
`stormwatch_test_protocol.md` (method) and `CLAUDE_CODE_RESTART.md` (next steps).
Latest commit: 83e6cf2. All work pushed.

**Claude Code task when reading this:** verify the repo state matches what's below
(files present, commits, conventions in code). Flag any mismatch. Then update this
file as new work lands so it stays the single source of truth.

---

## 1. WHERE WE ARE (one paragraph)
Complete, tested pipeline: synoptic wind (HRRR/ERA5/CONUS404) → WindNinja terrain
downscaling → surrogate WindNinja → confidence engine → mechanism classifier, plus
BC label generator and outer trainer. Diagnostic phase done. One real validation
landed (Missoula BC vs independent sounding). The corrective phase — learn the BC
correction and prove it beats raw HRRR at held-out terrain stations — is built but
RAWS-gated. RAWS data requests sent by Alex, awaiting reply. Current mode: finish
obs-independent work so validation runs immediately when data arrives.

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
**SOLID:**
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
  NE (Santa Ana standout); Kincade 18.9 mph NE (ignition phase only — 27 Oct
  destructive run needs separate 26-28 Oct pull). 700 hPa geo-height 3100-3181m >
  domain terrain in all cases. Input side of BC pipeline is now locked.
  See `era5_bc_characterization.md`.
- **ERA5 fidelity vs Wyoming soundings (2026-05-30).** ERA5 earns "trusted BC
  source" for NorCal Diablo + SoCal Santa Ana: Tubbs OAK Oct 8 (−2.8/3° at 00z,
  +3.0/12° at 12z); Thomas VBG Dec 4 (+1.1/5° at 00z, −3.5/11° at 12z). Direction
  within 12° in all four comparisons. Kincade not yet run (OAK 27 Oct sounding is
  outside the 23-25 Oct ERA5 window — pull 26-28 Oct to close).
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
  range, and OAK is still not a valid local denominator. Cannot close until: (a)
  Hawkeye sustained obs from RAWS, (b) local 700 hPa reference (not OAK distant).
  No circularity (BC sweep not yet run). Inversion + coordinate findings are solid.

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
