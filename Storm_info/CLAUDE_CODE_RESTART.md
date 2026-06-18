# CLAUDE CODE RESTART — Current Next Steps & Session Handoff

**Read order on restart:** THIS file → `STORMWATCH_MASTER_STATUS.md` (authoritative findings
ledger) → `stormwatch_test_protocol.md` (method). Update this file whenever work lands.

**Last updated:** 2026-06-17 (EXPTS tab live; latest commit db395da)

---

## ONE-LINE STATE

**EXPTS tab fully redesigned (2026-06-17): correct scientific framing, readable colors,
plain-English badges, diverging error chart, user-authored challenge text. Latest commit:
5ed97c2. Next: MCP bugs, then run WN on In Progress events.**

---

## HOW TO RESUME

When user types "resume," confirm current state and ask what to work on:

> **Where we are (2026-06-17):** EXPTS tab is live in StormWatch Live — 12 hindcast
> events displayed with regime filters, narrative panels, wind arrow markers, and WN
> result badges (WN NICHE, HRRR OK, PENDING, ARCH. PASS, FULL RECOV.).
> Database complete: 164 active station-events, all DEM+BC populated.
> 8 events still show PENDING (WN not yet run): Kincade Ignition, Kincade Run Day,
> Labor Day OR, Boulder Chinook, Boulder Downslope, Missoula Dec 2025, Missoula Jul 2024,
> Iowa Derecho.
> What would you like to work on?

---

## WHAT IS DONE — DO NOT REDO

### Database (all complete)
- `hrrr_error_dataset.csv`: 318 rows, 164 active (KEEP/CAUTION)
- All BC columns: bc_speed, bc_dir, bc_level populated; 850 hPa offshore, 700 hPa continental
- All DEM columns: slope, aspect, relief_1km, repr_error_flag, terrain_class
  - Distribution: exposed_ridge=63, canyon_gap=29, open=43, valley=29
  - CUUC1/woolsey synthesized from CUUC1/thomas (same coordinates)
- All 12 events in database; all obs and HRRR columns complete

### Phase B terrain gate (complete, FAILED)
- Run on full 164-station dataset: ratio=0.0134 (white noise threshold < 1.0)
- Rule #0 repr control: R²=0.000, ratio after=0.0135 — terrain collinearity ruled out
- VERDICT: terrain class does NOT predict HRRR bust magnitude. Filed in STORMWATCH_MASTER_STATUS.md.
- Report: `merge_gate_report.txt`

### Regime signal (SOLID)
- Offshore mean speed_err = −3.91 mph; Continental = +0.51 mph; Δ=4.41 mph
- This is the validated predictor used by the outer correction layer

### Two-level BC architecture (validated on 4 anchors)
- Outer: LOO Ridge on (w700, mslp_grad, hrrr_coupling_frac) → event delta
- Inner: UP if (relief>330m AND slope>10°) OR (coupling_ratio>1.08); else DOWN
- Do-no-harm gate: suppress if |wn_raw_spd - obs| ≤ 5 mph
  → fires at WMSC1/woolsey (saves 9.2 mph overcorrection)
- WMSC1/thomas: flat −32.1 → two-level +10.5 (architecture PASS)

### Camp Fire held-out test (FAILED, pre-registered)
- Fit on JBGC1/Jarbo Gap; tested on CBXC1+SLEC1 (both held-out)
- CBXC1: rawBC ratio 1.007, corrBC ratio 0.830 → correction DEGRADES
- SLEC1: rawBC ratio 1.128, corrBC ratio 0.717 → correction DEGRADES
- VERDICT: WN+rawBC IS the product. Learned correction adds risk without benefit.
- DO NOT re-run to chase a pass.

### Scripts written this session
- `donoharm_gate.py` — do-no-harm gate function + test harness; 3/4 OK
- `rrfs_extract.py` — Phase 3 RRFS GRIB2 harness; format-validated against HRRR cache
- `fetch_cuuc1_dem.py` — targeted DEM fetch for CUUC1 (not needed, superseded by merge script)
- `merge_all_remaining_dem.py` — merged all 68 remaining NEEDS_DEM rows in one pass

### EXPTS Tab (complete as of 2026-06-13, tweaks 2026-06-15)
- 12-event WindNinja Hindcast Series panel in StormWatch Live (weather-alerts.html)
- Left sidebar: event cards with HRRR err, anchor station, WN result badge, regime label
- Regime filter pills: ALL / DIABLO / SANTA ANA / CONTL
- Map markers: colored by wind regime (orange=Diablo, red=SantaAna, blue=Continental)
- Wind arrow divIcon markers: colored by HRRR error, arrow shows observed wind bearing
- Click station: dark popup with 3-bar comparison (Observed / HRRR / WN BC input)
- Click event card: story panel expands with full meteorological narrative
- Floating 'Hindcast Events' legend with regime + result key; close button; 'Fit all' zoom
- Alert/weather legend hidden while EXPTS tab active
- Badges: WN NICHE (Camp), HRRR OK (Tubbs), ARCH. PASS (Thomas), FULL RECOV. (Woolsey), PENDING (8 events not yet run)
- Key commits: 6da2bae → db395da (9 commits total)

### GitHub
- All commits pushed through db395da → origin/master
- Latest hash: db395da
- Repo: aphilp1/stormwatch-live (PUBLIC — do not commit credentials)

---

## NEXT ACTIONS — THREE PATHS

### Path A — Deploy validated niche (recommended first, deployable now)
WN+rawBC beats raw HRRR at isolated above-inversion ridges with direction-correct BC.
Niche: n=2, CBXC1 ratio 1.007, SLEC1 ratio 1.128 (both Camp Fire, DEM/CRS verified).

To deploy in StormWatch Live:
1. Identify integration point in `weather-alerts.html`
2. Run WN+rawBC for a current fire weather event at ridge stations
3. Display WN output alongside HRRR on the map

Claim to make: "WindNinja with unmodified HRRR boundary conditions improves over raw
HRRR specifically at above-inversion ridge stations during offshore flow events."

### Path B — More WN validation (the science path)
Thomas and Woolsey: full RAWS data, aligned BCs (850 hPa Santa Ana), DEMs in place.
Run WN+rawBC at held-out stations for those events. Confirms niche holds cross-event
OR confirms it consistently fails — either is publishable.

Scripts needed: WN run for Thomas (thomas_wn_run.cfg) and Woolsey. DEMs in Storm_info.
Compare held-out stations that have obs and aren't WMSC1 (the anchor).

### Path C — RRFS resolution ladder (HPC-blocked, human action required)
- `rrfs_extract.py` is written; populate RRFS_FILE_MAP and run with --run
- Blocked: need NOAA employee sponsor for RDHPCS access
- Action: email EPIC/NSSL/WPC — cannot self-apply as external researcher
- When unblocked: test whether 1.5km RRFS closes the offshore underbias before WN

---

## CONVENTIONS — DO NOT DRIFT

- `vec_avg`: mean u/v components THEN atan2. NEVER average raw degrees.
- Direction: meteorological FROM (0=N, 90=E, 180=S, 270=W)
- Speed: mph = m/s × 2.23694
- Slope: stored in DEGREES in hrrr_error_dataset.csv (NOT percent)
- BC level: 850 hPa offshore/Santa Ana; 700 hPa continental (see §2.4)
- Soundings: Wyoming wsgi (src=FM35) only. NEVER IEM (CWMJ alias bug — returns Canadian station)
- Synoptic token: NWS WRH public `7c76618b66c74aee913bdbae4b448bdd` + correct Referer header
- Security: `~/.cdsapirc` and `~/.ecmwfapirc` gitignored. Repo is PUBLIC. No credentials in code.

---

## ENVIRONMENT

```powershell
# hrrr311 env (primary — HRRR pulls, cfgrib, herbie, numpy, scipy, BC work):
$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\hrrr311"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"
& "$CONDA_ENV\python.exe" <script.py>

# dem env (py3dep, rasterio, rioxarray — DEM fetching only):
conda run -n dem python <script.py>

# WindNinja CLI:
C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe

# StormWatch Live dev server (run from Stormwatch folder, NOT Storm_info):
python -m http.server 8080
# then open: http://localhost:8080/weather-alerts.html
```

---

## KEY FILES

| File | Purpose |
|------|---------|
| `hrrr_error_dataset.csv` | Main DB — 164 active rows, all columns complete |
| `dem_features.csv` | Raw DEM metrics (pre-merge) |
| `time_aligned_bc.csv` | Per-station BC at each station's peak hour (offshore) |
| `two_level_wn_test.py` | WN battery — 4 anchors, inner/outer/2-level |
| `donoharm_gate.py` | Gate function + test harness |
| `rrfs_extract.py` | RRFS GRIB2 extraction harness |
| `bc_outer_trainer.py` | LOO Ridge outer correction |
| `merge_dem_and_gate.py` | Rebuilds dem CSV + runs Phase B gate |
| `merge_gate_report.txt` | Latest gate results (ratio=0.0134, INDETERMINATE) |
| `wyoming_soundings.json` | Canonical sounding values — READ only, never hand-enter |
| `STORMWATCH_MASTER_STATUS.md` | Full findings ledger (authoritative) |
| `stormwatch_test_protocol.md` | Method + pre-registration rules |
| `hindcast_event_library.md` | All 12 events, dates, anchor stations |
| `raws_obs/` | 317 station-event RAWS CSVs |
| `hrrr_bc_cache/` | Herbie GRIB2 cache |

---

## WITHHELD / PARKED (do not cite, do not revive)

- **Tubbs direction:** WISC1/KNXC1 carry 25–44° ENE structural offset. BC says ENE, obs says NNE.
- **WMSC1 Thomas elevation:** Registry 4930 ft, DEM ~3750 ft → sub-inversion; excluded from niche.
- **Timing thread:** Parked until fire-site RAWS propagation geometry is in place.
- **Amplification ratios:** All withdrawn except CBXC1/SLEC1 WN ratio (not amplification).
- **Single-station BC correction:** Falsified. Do not re-run.
- **Multi-station BC correction:** Falsified. Do not re-run.

---

## DISPLAY IDEAS FOR HINDCAST SERIES (brainstormed 2026-06-12)

**Option 1 — Findings map (recommended for StormWatch Live integration)**
Interactive map: 12 fire event markers on western US. Each shows event name, date, regime,
anchor HRRR vs WN error, terrain class. Color by regime (orange=Diablo, red=SantaAna,
blue=continental). Simple HTML/Leaflet, no server needed beyond python -m http.server.

**Option 2 — Experiment timeline table**
Static sortable HTML table: event, date, regime, anchor stations, HRRR err, WN+rawBC err,
WN+corrBC err, terrain gate result, status (PASS/FAIL/TBD). One row per anchor.
Shows full experimental progression. Good for a "Methods" or "Research" tab.

**Option 3 — Departure scatter plot**
speed_err vs event on x-axis, colored by regime, shape by terrain class.
Regression line showing offshore/continental split. Plotly or Chart.js, embeddable.
Most visually compelling way to show the regime signal.

---

*Authoritative findings: STORMWATCH_MASTER_STATUS.md*
*Method rules: stormwatch_test_protocol.md*
*Memory index: C:\Users\aphil\.claude\projects\C--Users-aphil\memory\MEMORY.md*
