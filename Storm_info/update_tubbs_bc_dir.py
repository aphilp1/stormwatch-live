#!/usr/bin/env python3
"""
update_tubbs_bc_dir.py
======================
Two steps:
  1. Replace bc_dir in hrrr_error_dataset.csv for all active Tubbs rows with
     time-aligned HRRR 850 hPa direction at each station's own peak hour.
     Unconditional — no per-row cherry-picking based on which value is closer
     to obs. The aligned value is the physically correct BC regardless of
     whether it widens or narrows dir_err.
  2. Write tubbs_direction_finding.md documenting the bc_dir ENE/NNE mismatch
     at inland stations as a solid, documented open issue.

Run: (PowerShell with hrrr311 DLLs in PATH)
  Add hrrr311 + Library/bin to PATH, then: python update_tubbs_bc_dir.py
"""
import csv, datetime, math, os, sys, shutil
import numpy as np
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE   = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DB     = os.path.join(BASE, 'hrrr_error_dataset.csv')
CACHE  = os.path.join(BASE, 'hrrr_bc_cache')
MS_MPH = 2.23694


def extract_hrrr_uv(peak_dt, level_hpa=850):
    search = f':(?:UGRD|VGRD):{level_hpa} mb:'
    H = Herbie(peak_dt, model='hrrr', product='prs', fxx=0,
               save_dir=CACHE, verbose=False)
    return H.xarray(search, remove_grib=False)


def uv_at_point(ds, lat, lon):
    vars_ = list(ds.data_vars)
    u_name = next((v for v in vars_ if 'u' in v.lower() and 'grd' in v.lower()), vars_[0])
    v_name = next((v for v in vars_ if 'v' in v.lower() and 'grd' in v.lower()), vars_[1])
    u_da, v_da = ds[u_name], ds[v_name]
    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    if grid_lon.min() > 0 and lon < 0:
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)
    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    _, idx = tree.query([lat, lon])
    u = float(u_da.values.ravel()[idx])
    v = float(v_da.values.ravel()[idx])
    spd = math.sqrt(u**2 + v**2) * MS_MPH
    drct = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return spd, drct


def ang_diff(a, b):
    """Signed angular difference (a - b) in [-180, 180]."""
    return (a - b + 180) % 360 - 180


# ── 1. Load all Tubbs rows from DB ───────────────────────────────────────────

all_rows = []
with open(DB, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        all_rows.append(r)

tubbs_active = [r for r in all_rows
                if r.get('event_id') == 'tubbs_2017'
                and r.get('qc_flag') in ('KEEP', 'CAUTION')
                and r.get('obs_dir_deg') not in ('', 'nan', 'NaN')]

print(f"Active Tubbs rows with obs_dir: {len(tubbs_active)}")

# ── 2. Build pull groups by aligned peak hour ─────────────────────────────────

by_dt = {}
for r in tubbs_active:
    dt = datetime.datetime.fromisoformat(r['peak_dt_utc'].replace('Z', '+00:00'))
    dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    by_dt.setdefault(dt_h, []).append(r)

# ── 3. Extract aligned bc_dir from cached HRRR ───────────────────────────────

print("\nExtracting aligned bc_dir from cached HRRR 850 hPa:")
aligned = {}  # stid+event_id → (bc_dir_new, bc_spd_new)
for dt_h, rows in sorted(by_dt.items()):
    try:
        ds = extract_hrrr_uv(dt_h, 850)
        for r in rows:
            spd, drct = uv_at_point(ds, float(r['lat']), float(r['lon']))
            key = (r['stid'], r['event_id'])
            aligned[key] = (round(drct, 1), round(spd, 2))
        print(f"  OK: {dt_h}  stations={[r['stid'] for r in rows]}")
    except Exception as ex:
        print(f"  FAIL: {dt_h} → {ex}")

print()

# ── 4. Print before/after table ───────────────────────────────────────────────

print("=" * 85)
print("BEFORE / AFTER — bc_dir vs obs_dir (BC direction error, not HRRR vs obs)")
print("  (dir_err in DB = HRRR_10m_dir - obs_dir, unchanged by this update)")
print("=" * 85)
print(f"  {'stid':<8} {'obs_dir':>8} {'bc_dir_OLD':>10} {'Δ_OLD':>8}  "
      f"{'bc_dir_NEW':>10} {'Δ_NEW':>8}  {'|Δ|_OLD':>8} {'|Δ|_NEW':>8}  improved?")
print("  " + "-" * 83)

for r in sorted(tubbs_active, key=lambda x: x['peak_dt_utc']):
    key = (r['stid'], r['event_id'])
    obs_dir = float(r['obs_dir_deg'])
    bc_old = float(r['bc_dir']) if r.get('bc_dir') not in ('', 'nan', 'NaN') else None
    new_val = aligned.get(key)
    bc_new = new_val[0] if new_val else None

    d_old = ang_diff(bc_old, obs_dir) if bc_old is not None else None
    d_new = ang_diff(bc_new, obs_dir) if bc_new is not None else None

    old_s = f"{bc_old:.0f}°" if bc_old is not None else "---"
    new_s = f"{bc_new:.0f}°" if bc_new is not None else "FAIL"
    do_s  = f"{d_old:+.1f}°" if d_old is not None else "---"
    dn_s  = f"{d_new:+.1f}°" if d_new is not None else "FAIL"
    ao_s  = f"{abs(d_old):.1f}°" if d_old is not None else "---"
    an_s  = f"{abs(d_new):.1f}°" if d_new is not None else "---"
    impr  = ""
    if d_old is not None and d_new is not None:
        impr = "YES" if abs(d_new) < abs(d_old) else ("SAME" if abs(d_new) == abs(d_old) else "NO")

    print(f"  {r['stid']:<8} {obs_dir:>7.1f}° {old_s:>10} {do_s:>8}  "
          f"{new_s:>10} {dn_s:>8}  {ao_s:>8} {an_s:>8}  {impr}")

print()

# ── 5. Update DB unconditionally ──────────────────────────────────────────────

backup = DB.replace('.csv', '_pre_tubbs_bc_dir.csv')
shutil.copy2(DB, backup)
print(f"Backup: {backup}")

n_updated = 0
for r in all_rows:
    if r.get('event_id') != 'tubbs_2017':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    key = (r['stid'], r['event_id'])
    if key in aligned:
        bc_dir_new, _ = aligned[key]
        r['bc_dir'] = str(bc_dir_new)
        n_updated += 1

with open(DB, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f"Updated bc_dir for {n_updated} Tubbs rows in {DB}")
print()

# ── 6. Write finding doc ──────────────────────────────────────────────────────

FINDING_PATH = os.path.join(BASE, 'tubbs_direction_finding.md')

# Collect station data for the table
station_data = {}
for r in tubbs_active:
    key = (r['stid'], r['event_id'])
    obs_dir = float(r['obs_dir_deg'])
    bc_old = float(r['bc_dir']) if r.get('bc_dir') not in ('', 'nan', 'NaN') else None
    new_val = aligned.get(key)
    bc_new = new_val[0] if new_val else None
    station_data[r['stid']] = {
        'obs_dir': obs_dir,
        'bc_dir_old': bc_old,
        'bc_dir_new': bc_new,
        'd_old': ang_diff(bc_old, obs_dir) if bc_old is not None else None,
        'd_new': ang_diff(bc_new, obs_dir) if bc_new is not None else None,
        'peak_utc': r['peak_dt_utc'][:16],
        'elev_m': r.get('elev_m', ''),
        'terrain': r.get('terrain_class', ''),
        'lat': r.get('lat', ''),
        'obs_sus': r.get('obs_sus_mph', ''),
        'speed_err': r.get('speed_err', ''),
        'bc_speed_old': r.get('bc_speed', ''),
    }

with open(FINDING_PATH, 'w', encoding='utf-8') as f:
    f.write("""# Tubbs 2017 — Direction Finding: Coastal vs Inland BC/Obs Mismatch

**Event:** Tubbs Fire destructive run, Oct 9 2017
**Status:** SOLID WITH CAVEAT — speed underbias valid; bc direction at inland stations documented open issue
**Withheld conditions cleared:**
- (a) HWKC1 sustained obs from RAWS: peak 48.0 mph @ 35.7° NNE at 06:56Z Oct 9 ✅
- (b) OAK 700 hPa reference from Wyoming (not IEM): Oct 9 00Z/12Z retrieved ✅

---

## Finding

Time-aligned HRRR 850 hPa direction (each station at its own peak hour) shows a
**coastal vs inland split** in how well bc_dir represents the observed surface flow:

""")

    f.write("| Station | Peak UTC | Elev (m) | Obs dir | bc_dir OLD | Δ_old | bc_dir NEW | Δ_new | Terrain |\n")
    f.write("|---------|----------|----------|---------|------------|-------|------------|-------|----------|\n")
    order = ['HWKC1','WISC1','KNXC1','RSAC1','NVHC1','KELC1','ATLC1']
    for stid in order:
        if stid not in station_data:
            continue
        d = station_data[stid]
        bc_o = f"{d['bc_dir_old']:.0f}°" if d['bc_dir_old'] is not None else "—"
        bc_n = f"{d['bc_dir_new']:.0f}°" if d['bc_dir_new'] is not None else "—"
        do   = f"{d['d_old']:+.1f}°" if d['d_old'] is not None else "—"
        dn   = f"{d['d_new']:+.1f}°" if d['d_new'] is not None else "—"
        f.write(f"| {stid} | {d['peak_utc']} | {d['elev_m']} | {d['obs_dir']:.1f}° | "
                f"{bc_o} | {do} | {bc_n} | {dn} | {d['terrain']} |\n")

    f.write("""
Δ = bc_dir − obs_dir (positive = bc clockwise of obs).
Time alignment applied unconditionally; all bc_dir values updated in hrrr_error_dataset.csv.

---

## Interpretation

**HWKC1 (coastal, 38.73°N, −122.84°W):** bc_dir mismatch collapses from +20.6° to +6.3°
after alignment. This station is close to the coast and the 850 hPa Diablo flow
channels directly into the terrain gap. The aligned bc_dir (42°) closely matches the
observed NNE flow (35.7°). **HWKC1 is the clean coastal anchor.**

**WISC1 and KNXC1 (inland, 38.86–39.02°N, −122.41°W):** bc_dir remains ENE (59–60°)
after alignment — the temporal fix does nothing here because the mismatch isn't about
*when* the sample was taken. HRRR 850 hPa at these inland locations points ENE regardless
of hour, while observed surface winds are NNE (15–35°). The Wyoming OAK sounding for
Oct 9 shows 850 hPa N/NNE (0°–25°), consistent with obs — which means HRRR's 850 ENE at
the inland points is itself an error in the model's synoptic representation there, not just
a surface channeling effect.

**Physical story:** Diablo surface flow at inland Napa/Lake County stations channels more
northerly than the 850 hPa synoptic flow suggests. HRRR doesn't fully resolve this
directional shift. The result is that 850 hPa bc_dir overshoots ENE by ~25–44° at these
stations while being accurate (within 10°) at the coastal anchor.

---

## Connection to WMSC1 Speed Finding

This pattern mirrors the WMSC1 speed result documented in phase_a_finding.md. There, the
synoptic (850 hPa) speed and the surface speed diverge because valley terrain channeling
amplifies flow beyond what the synoptic flow implies. Here, the synoptic direction and the
surface direction diverge because inland terrain channeling rotates flow more northerly
than the 850 hPa synoptic vector. In both cases: **the synoptic BC and the actual surface
flow are related but not identical**, and the discrepancy is spatially structured by terrain
geometry that HRRR doesn't fully resolve.

This means that if direction correction is pursued downstream, the same two-level
architecture logic applies: a terrain-keyed direction adjustment is the candidate, not a
flat synoptic rotation. Coastal stations (HWKC1-type, low Δ after alignment) would not
need it; inland stations (WISC1/KNXC1-type, persistent ENE offset) would. This is not a
current deliverable — flag it so the pattern isn't lost.

---

## Wyoming OAK Sounding Cross-Check (Oct 9 2017)

Independent of ERA5 and HRRR — confirms 850 hPa level choice is correct:

| Time | 700 hPa | 850 hPa | Verdict |
|------|---------|---------|---------|
| 00Z Oct 9 | 24.2 mph @ 0° (N) | 27.7 mph @ 0° (N) | Both N; neither ENE |
| 12Z Oct 9 | 11.6 mph @ 345° (NNW) | 17.2 mph @ 25° (NNE) | 850 matches obs NNE; 700 wrong |

850 hPa remains the correct BC level for Tubbs above-inversion stations. The Wyoming
sounding confirms the synoptic flow is NNE, making the HRRR inland ENE bias a model
representation issue, not a BC-level error.

---

## Speed Signal (not affected by direction mismatch)

Speed underbias is valid and unaffected by this finding:
- HWKC1: obs 48.0 mph, HRRR 36.7 mph, speed_err −11.3 mph
- WISC1: obs 35.0 mph, HRRR 27.9 mph, speed_err −7.1 mph
- KNXC1: obs 36.0 mph, HRRR 36.7 mph, speed_err +0.7 mph (near zero)

HWKC1 and WISC1 show the offshore underbias pattern. KNXC1 is near-zero (canyon_gap
terrain, HRRR resolves this station reasonably). The speed analysis proceeds normally.

---

## Status

- Tubbs **un-withheld** as of this commit.
- bc_dir updated to time-aligned values (unconditional) in hrrr_error_dataset.csv.
- Direction mismatch at inland stations (WISC1, KNXC1) is a **documented open issue**,
  not a blocker for proceeding with the destructive-run rows.
- Do NOT use Tubbs dir_err at WISC1/KNXC1 as a validated direction result. Mark as
  DIR_MISMATCH in any per-station direction analysis.
""")

print(f"Written: {FINDING_PATH}")
