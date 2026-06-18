# CLAUDE CODE RESTART — Current Next Steps & Session Handoff

**Read order on restart:** THIS file → `STORMWATCH_MASTER_STATUS.md` (authoritative findings
ledger) → `stormwatch_test_protocol.md` (method). Update this file whenever work lands.

**Last updated:** 2026-06-17 · HindC tab v1.0 · latest commit: see git log

---

## ONE-LINE STATE

**HindC tab v1.0 shipped (2026-06-17): fully redesigned, logic-checked, four corrections
applied from external review. Next: MCP bugs, then WN runs on 8 In Progress events.**

---

## HOW TO RESUME

When user types "resume," confirm current state and ask what to work on:

> **Where we are (2026-06-17):** HindC tab (formerly EXPTS) is live in StormWatch Live
> at v1.0. 12 hindcast events, 4 regime-organized findings, correct anchor-vs-event-mean
> labeling, bc/obs as controlling variable for the niche claim, convective outflow as its
> own regime (Iowa + Missoula Jul), Kincade Ignition corrected to +4.13 mph.
> 8 events still show In Progress (WN not yet run).
> What would you like to work on?

---

## WHAT IS DONE — DO NOT REDO

### HindC Tab v1.0 (complete 2026-06-17)

**Commits this session (2026-06-17):** 439677c → 1909b35 + version/doc commit

- Tab renamed from EXPTS → HindC
- 4 finding chips (signal/causal/confirmed/arch) replacing 3
- Challenge text: user-authored, BC/obs pipeline framing, "diagnostic not prognostic"
- All WN-vs-HRRR language removed; replaced with HRRR-vs-station + WN-hindcast-vs-station
- Font sizes bumped (9px→11px body, 10px→12px titles); font-weight 800→700 everywhere;
  antialiasing on #tab-experiments container
- Blurry headlines fixed (fractional px → whole px)
- Legend section header: "WindNinja Result" → "WN Hindcast vs. Station Obs"

**Four logic fixes applied (from Claude Web external review):**
1. Chart relabeled "Anchor-station HRRR error" + note on divergence from event mean
2. Finding 3: bc/obs ≤ ~1 is the stated controlling variable; niche claim conditioned
3. Iowa + Missoula Jul: moved from 'continental' to 'convective' regime (purple pill)
4. Kincade Ignition: hrrr_err corrected from stale −2.1 to +4.13 (HWKC1, verified in DB)

**Review document for Claude Web:** `Storm_info/HINDC_REVIEW.md`
**GitHub raw URL:** https://raw.githubusercontent.com/aphilp1/stormwatch-live/master/Storm_info/HINDC_REVIEW.md

### Database (all complete)
- `hrrr_error_dataset.csv`: 318 rows, 164 active (KEEP/CAUTION)
- All BC columns: bc_speed, bc_dir, bc_level populated; 850 hPa offshore, 700 hPa continental
- All DEM columns: slope, aspect, relief_1km, repr_error_flag, terrain_class
- Phase B terrain gate: FAILED (ratio=0.013) — terrain class does NOT predict error
- Regime signal: offshore mean −3.9 mph, continental +0.5 mph, Δ=4.4 mph (SOLID)
- Two-level BC architecture: validated at 4 anchors; direction solved, magnitude bounded
- Camp Fire held-out test: WN+rawBC IS the product at exposed ridges with bc/obs ≤ ~1

### Scripts written
- `donoharm_gate.py`, `rrfs_extract.py`, `fetch_cuuc1_dem.py`, `merge_all_remaining_dem.py`
- `two_level_wn_test.py`, `bc_outer_trainer.py`, `merge_dem_and_gate.py`

---

## NEXT ACTIONS

### Priority 1 — MCP bug fixes (no data needed, pure code)
BUG-007 (briefing fires for non-US), BUG-012 (marine accepts inland),
BUG-013 (air quality accepts ocean), BUG-016 (alert formatting), BUG-021 (duplicate alerts)
Plus cosmetics: BUG-006, 014, 015, 018, 019, 020, 022–024

### Priority 2 — WN runs on 8 In Progress events
Kincade Ignition, Kincade Run Day, Labor Day OR, Marshall Fire, Boulder Chinook,
Missoula Dec 2025, Missoula Jul 2024
(Iowa Derecho = Control Case — flat terrain, no WN needed)

### Priority 3 — Tubbs direction mismatch (decision needed)
25–44° ENE structural offset at inland stations — withheld.
Decide: run WN with known caveat, or resolve direction first.

### Blocked
- RRFS resolution ladder: needs NOAA RDHPCS sponsor (rrfs_extract.py ready)
- ERA5 cross-check: needs Copernicus CDS registration (~/.cdsapirc)

---

## CONVENTIONS — DO NOT DRIFT

- `vec_avg`: mean u/v components THEN atan2. NEVER average raw degrees.
- Direction: meteorological FROM (0=N, 90=E, 180=S, 270=W)
- Speed: mph = m/s × 2.23694
- Slope: stored in DEGREES in hrrr_error_dataset.csv (NOT percent)
- BC level: 850 hPa offshore/Santa Ana; 700 hPa continental (see §2.4)
- Soundings: Wyoming wsgi (src=FM35) only. NEVER IEM (CWMJ alias bug)
- Synoptic token: NWS WRH public `7c76618b66c74aee913bdbae4b448bdd` + correct Referer header
- Security: `~/.cdsapirc` and `~/.ecmwfapirc` gitignored. Repo is PUBLIC. No credentials in code.
- WN framing: NEVER say "WN beats HRRR." Two comparisons only: HRRR vs. station obs,
  and WN hindcast vs. station obs.

---

## ENVIRONMENT

```powershell
# hrrr311 env (primary):
$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\hrrr311"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"
& "$CONDA_ENV\python.exe" <script.py>

# dem env (DEM fetching only):
conda run -n dem python <script.py>

# WindNinja CLI:
C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe

# StormWatch Live dev server (run from Stormwatch folder):
python -m http.server 8080
# then: http://localhost:8080/weather-alerts.html
```

---

## KEY FILES

| File | Purpose |
|------|---------|
| `hrrr_error_dataset.csv` | Main DB — 164 active rows, all columns complete |
| `HINDC_REVIEW.md` | Clean narrative extract for Claude Web review |
| `STORMWATCH_MASTER_STATUS.md` | Full findings ledger (authoritative) |
| `stormwatch_test_protocol.md` | Method + pre-registration rules |
| `hindcast_event_library.md` | All 12 events, dates, anchor stations |
| `two_level_wn_test.py` | WN battery — 4 anchors |
| `donoharm_gate.py` | Gate function + test harness |
| `rrfs_extract.py` | RRFS GRIB2 extraction (HPC-blocked) |
| `wyoming_soundings.json` | Canonical sounding values — READ only |

---

## WITHHELD / PARKED (do not cite, do not revive)

- **Tubbs direction:** WISC1/KNXC1 carry 25–44° ENE structural offset. Withheld.
- **WMSC1 Thomas elevation:** Registry 4930 ft, DEM ~3750 ft → sub-inversion; excluded from niche.
- **Single-station BC correction:** Falsified. Do not re-run.
- **Multi-station BC correction:** Falsified. Do not re-run.
- **Camp Fire corrBC:** CBXC1 ratio 0.830, SLEC1 ratio 0.717 — correction DEGRADES. Do not re-run.

---

*Authoritative findings: STORMWATCH_MASTER_STATUS.md*
*HindC review doc: HINDC_REVIEW.md*
*Memory index: C:\Users\aphil\.claude\projects\C--Users-aphil\memory\MEMORY.md*
