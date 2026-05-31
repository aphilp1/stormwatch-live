# CLAUDE CODE RESTART — Current Next Steps & Session Handoff

**Read order on restart:** THIS file (current state + next action) →
`STORMWATCH_MASTER_STATUS.md` (authoritative record) → `stormwatch_test_protocol.md`
(method). This is the rolling "where we are right now." When work lands, fold it into
the master status and update this file.

**Last updated:** 2026-05-31 (RAWS data unlocked session).

---

## ONE-LINE STATE
**RAWS gate lifted.** Historical obs for all primary events now in `Storm_info/raws_obs/`
via `raws_pull_nws_token.py`. BC sweep is the next unblocked action.
Kincade ERA5 fidelity check (the previous NEXT ACTION) is still open but lower priority
now that RAWS has landed — do it in parallel, not as a blocker.

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

## NEXT ACTION (was in progress at crash) — KINCADE
Kincade is the LAST open fidelity check. Also: the existing `kincade_2019` file covers
only the 23–25 Oct ignition phase; the **27 Oct 102 mph Pine Flat run is NOT yet
pulled.** This step closes both.

**Step 1 — pull the run window.**
Add to `EVENTS` in `era5_event_pull.py` (do NOT alter existing `kincade_2019`):
```
"kincade_run_2019": {"year": "2019", "month": "10", "days": ["26", "27", "28"],
                     "ignition_utc": "27 Oct 2019 Pine Flat 102 mph Diablo run"},
```
Run (hrrr311 env, from Storm_info folder): `python era5_event_pull.py kincade_run_2019`
→ expect `era5_pl_kincade_run_2019.nc` + `era5_sl_kincade_run_2019.nc`. Uses S=35N box
(OAK well inside). Leave the four existing event files untouched.

**Step 2 — OAK 27 Oct sounding.**
Check `wyoming_soundings.json` for OAK (WMO 72493) 2019-10-27 at 00z + 12z. If missing,
pull from Wyoming wsgi (src=FM35) and append (same schema). If it returns CWMJ
(Canadian alias) instead of real OAK data, STOP.

**Step 3 — fidelity check.**
Add to `CHECKS` in `era5_sounding_fidelity.py`: event `kincade_run_2019`, station OAK,
date 2019-10-27, times 00z+12z, S=35N box. Run, paste full output, write nothing to
master status until reviewed.

**PRE-REGISTERED EXPECTATION (set before looking):** North Bay ridges (Hawkeye, Pine
Flat) sit ABOVE a low inversion — so unlike Camp, **700 hPa should be the RIGHT level
here**, and ERA5 should agree with OAK the way Tubbs did. If 700 hPa agrees → coherent
picture: inversion height decides BC level (850 sub-inversion / 700 above-inversion).
If it diverges → that's a finding, ESCALATE with both numbers.

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
