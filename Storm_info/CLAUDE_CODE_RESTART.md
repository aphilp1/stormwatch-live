# CLAUDE CODE RESTART — Current Next Steps & Session Handoff

**Read order on restart:** THIS file (current state + next action) →
`STORMWATCH_MASTER_STATUS.md` (authoritative record) → `stormwatch_test_protocol.md`
(method). This is the rolling "where we are right now." When work lands, fold it into
the master status and update this file.

**Last updated:** 2026-05-31 (Kincade cross-event + terrain-rotation finding).

---

## ONE-LINE STATE
**Ridge niche n=2 (Camp CBXC1/SLEC1). Cross-event still OPEN after 5 candidates exhausted.**
New finding: Kincade summits deflect NNE→N (~45°); terrain rotation is the pattern blocking
cross-event confirmation. Sharpened hypothesis: niche holds where terrain doesn't rotate flow.
Next path: Tubbs non-Hawkeye ridge (likely flow-aligned) OR upstream BC sampling (new method).

---

## WHAT IS DONE THIS SESSION (do not redo)
- **ERA5 access via Copernicus CDS WORKS.** `cdsapi` installed in conda env
  `hrrr311`. Credentials in `~/.cdsapirc` (gitignored). The old ECMWF Web API key
  (`api.ecmwf.int/v1`) was the WRONG key; CDS needs a Personal Access Token — resolved.
- **`era5_event_pull.py`** pulls ERA5 over a CA box: levels 500/700/850/925/1000 hPa;
  vars u, v, geopotential, temperature, RH + single-level MSLP; all 24h; 3-day window
  per event. One CLI arg = one event.
- **Pulled clean (no errors/403):** camp_2018, tubbs_2017, thomas_2017, kincade_2019.
  Files: `era5/era5_pl_{event}.nc` + `era5/era5_sl_{event}.nc`.
- **Thomas was RE-PULLED** with the box extended south to **S=34.0N** (to cover
  Vandenberg). The other three use **S=35.0N**. Box = N42 / W-124 / S35(34) / E-117.
- **`era5_sounding_fidelity.py`** compares ERA5 700 hPa (and 850 for Camp) wind to
  Wyoming soundings at EXACT UTC launch times. Observed values are READ from
  `wyoming_soundings.json` — never hardcoded.
- **Fresh REV (Reno) sounding** pulled from Wyoming wsgi (src=FM35) for 2018-11-08
  00z+12z and appended to `wyoming_soundings.json`.
- Results written to master status and committed this session.
  **Verify the push landed:** `git log origin/master`.

---

## RESULTS THIS SESSION (SOLID — already in master status)
- **ERA5 = trusted synoptic BC source.** Tubbs/OAK (8 Oct) and Thomas/VBG (4 Dec):
  all four comparisons agree within ~12° direction and a few mph speed. Grid 3 km / 6 km
  from station. Direction (the high-leverage variable) is the strong match.
- **BC-LEVEL FINDING (Camp/REV).** 700 hPa (~3100 m) sits ABOVE the Reno inversion
  (2307 m at 00z / 1516 m at 12z) → samples free-atmosphere flow, NOT the NE gap flow.
  Rule (refines protocol §2.4): **sub-inversion gap-flow events need an 850 hPa /
  sub-lid BC, not 700 hPa.** 850 hPa agreement at REV is tight (12z: 1° direction).
- **WITHDRAWN (method catch).** Earlier "ERA5 reversed 202° at REV 12z" was a
  HAND-TRANSCRIBED IEM value, not ERA5. Real Wyoming sounding AGREES with ERA5 (~60–63°).
  Convention: never hand-enter obs; read from `wyoming_soundings.json`.
- **Noted, not a finding.** Camp 12z 700 hPa speed +6.7 mph (direction agrees within
  3°). Soft-threshold trip from a 28 km grid cell vs point sonde — not a divergence.

---

## NEXT ACTION — Cross-event niche confirmation (updated 2026-05-31 end-of-session)

Niche confirmed at n=2, both Camp (CBXC1 1.007, SLEC1 1.128), DEM/CRS-verified.
**Cross-event confirmation still OPEN.** All tonight's candidates exhausted cleanly
(HWKC1 HRRR-sufficient; WMSC1 elev error; CUUC1 overnight peak; WISC1 Δ36°; HGLC1 Δ46°).

**Sharpened working hypothesis (new):** WN-beats-HRRR niche holds where terrain does NOT
strongly rotate synoptic flow (Camp ridges: ~unrotated) and degrades where it does
(Kincade summits: NNE→N ~45° terrain rotation). This is more falsifiable — predicts
failure at rotation-dominated stations, success at flow-aligned ones. Test this next.

**Two principled next paths (pick when fresh):**

**(1) Tubbs non-Hawkeye ridge** — Hawkeye excluded (HRRR-sufficient). Find a station above
the Tubbs inversion (174m OAK) where HRRR undershoots AND flow isn't strongly rotated.
Diablo NNW flow at Tubbs should align well with NNW-facing ridges. Step 0 screening
first (registry elevation, DEM, direction R), then pre-register peak window + BC.

**(2) Upstream BC sampling — new method, pre-register before testing.** Sample 850 hPa at
a grid cell UPSTREAM (over terrain reflecting undeflected synoptic flow, east of the Coast
Ranges) rather than at the deflected station. If this closes the direction gates at WISC1
and HGLC1, it's a method improvement. But must be pre-registered fresh and applied to ALL
stations — NOT retrofitted to rescue existing failures.

**Parked permanently (do not revive):**
- Single-station BC correction — falsified
- Multi-station BC correction — falsified
- Do not re-run Camp to chase a pass

**Queued after point-prediction settles:**
- HRRRCast integration / BC_SENSITIVITY confidence field
- Resolve KNXC1 overshoot (WN=2.003, BC dir OK, cause unresolved)

**Queued after point-prediction settles:**
- HRRRCast integration / BC_SENSITIVITY confidence field

---

## CONVENTIONS — DO NOT DRIFT
- `vec_avg`: mean u and v THEN atan2. Never average raw degrees. Direction = met FROM.
  Speed mph = m/s × 2.23694.
- Observed values READ from `wyoming_soundings.json`. No hand-entered obs, EVER.
- Box S=35N default; **Thomas uses S=34N.** Coverage-flag per event.
- 700 hPa BC valid only ABOVE terrain AND ABOVE the inversion. Check inversion height
  per event before trusting the level.
- Domain-mean ≠ point. ERA5 = model INPUT, not surface truth. Domain-mean timing peaks
  = synoptic positioning, NOT fire-site timing. Timing thread stays PARKED.

---

## ENVIRONMENT / GOTCHAS
- Run from `C:\Users\aphil\Documents\Stormwatch\Storm_info`; ERA5 files in `./era5/`.
- New CDS netCDF: time coord is **`valid_time`** (not `time`). If `cdsapi` rejects
  `"data_format"`, use `"format"`.
- conda env `hrrr311`: cdsapi, xarray, numpy, netcdf4 installed.
- Credentials `~/.cdsapirc` (CDS token) and `~/.ecmwfapirc` — BOTH gitignored, never
  commit. Repo is PUBLIC.
- Confirm pushes with `git log origin/master`, not just local HEAD.

---

## STILL GATED (not today's work)
- Held-out RAWS validation (BC-corrected WindNinja beats raw HRRR at not-fitted terrain
  stations) = the bar for "workable." Still RAWS-gated.
- Kincade amplification work needs the run window (being pulled now) before use.
