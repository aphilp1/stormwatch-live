#!/usr/bin/env python3
"""
tubbs_bc_dir_aligned.py
=======================
Extract time-aligned HRRR 850 hPa bc_dir for Tubbs 2017 stations.

The existing time_aligned_bc.csv has bc_speed_aligned but not bc_dir_aligned.
This script re-extracts direction at the same aligned peak hours, using cached
HRRR files, and reports dir_err_old vs dir_err_aligned for each station.

Goal: confirm whether time alignment resolves the Tubbs "direction mismatch"
(bc_dir was from event-median Oct 8 12Z ENE; aligned bc_dir should be NNE).

Run: conda run -n hrrr311 python tubbs_bc_dir_aligned.py
"""
import csv, datetime, math, os, sys
import numpy as np
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
CACHE = os.path.join(BASE, 'hrrr_bc_cache')
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
    u_da = ds[u_name]
    v_da = ds[v_name]
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


def dir_diff(a, b):
    """Signed angular difference a-b in [-180,180]."""
    d = (a - b + 180) % 360 - 180
    return d


# Load Tubbs rows from departure database
tubbs_rows = []
with open(os.path.join(BASE, 'hrrr_error_dataset.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('event_id') != 'tubbs_2017':
            continue
        if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
            continue
        if not r.get('obs_dir_deg') or r['obs_dir_deg'] in ('', 'nan', 'NaN'):
            continue
        tubbs_rows.append(r)

print(f"Tubbs active rows with obs_dir: {len(tubbs_rows)}")
print()

# Build pull groups: (aligned_peak_dt_h, bc_level) → rows
# Use the same flooring logic as time_align_bc.py
by_dt = {}
for r in tubbs_rows:
    dt = datetime.datetime.fromisoformat(r['peak_dt_utc'].replace('Z', '+00:00'))
    dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    key = dt_h
    if key not in by_dt:
        by_dt[key] = []
    by_dt[key].append(r)

print("Pull times and stations:")
for dt_h, rows in sorted(by_dt.items()):
    stids = [r['stid'] for r in rows]
    print(f"  {dt_h}  →  {stids}")
print()

# Extract bc_dir at each aligned time
results = []
for dt_h, rows in sorted(by_dt.items()):
    try:
        ds = extract_hrrr_uv(dt_h, 850)
        print(f"OK: {dt_h}")
        for r in rows:
            lat, lon = float(r['lat']), float(r['lon'])
            spd, drct = uv_at_point(ds, lat, lon)
            r['_bc_dir_aligned'] = drct
            r['_bc_speed_aligned'] = spd
    except Exception as ex:
        print(f"FAIL: {dt_h} → {ex}")
        for r in rows:
            r['_bc_dir_aligned'] = None
            r['_bc_speed_aligned'] = None

print()

# Report
print("=" * 80)
print("TUBBS bc_dir ALIGNMENT — before vs after")
print(f"  Wyoming OAK soundings (Oct 9):")
print(f"    00Z: 700 hPa=24.2@0°  850 hPa=27.7@0°")
print(f"    12Z: 700 hPa=11.6@345° 850 hPa=17.2@25°")
print(f"  Observed NNE winds: HWKC1 @35.7°, WISC1 @15.3°, KNXC1 @34.7°")
print("=" * 80)
print(f"  {'stid':<8} {'peak_utc':>18}  {'obs_dir':>7} {'bc_dir_OLD':>10} {'dir_err_OLD':>11}  "
      f"{'bc_dir_NEW':>10} {'dir_err_NEW':>11}  {'improved?'}")
print("  " + "-" * 90)

for r in sorted(tubbs_rows, key=lambda x: x['peak_dt_utc']):
    obs_dir = float(r['obs_dir_deg'])
    bc_dir_old = float(r['bc_dir']) if r.get('bc_dir') not in ('', 'nan', 'NaN', None) else None
    dir_err_old = float(r['dir_err']) if r.get('dir_err') not in ('', 'nan', 'NaN', None) else None
    bc_dir_new = r.get('_bc_dir_aligned')
    dir_err_new = dir_diff(obs_dir, bc_dir_new) if bc_dir_new is not None else None

    old_s = f"{bc_dir_old:.0f}°" if bc_dir_old is not None else "---"
    err_old_s = f"{dir_err_old:+.1f}°" if dir_err_old is not None else "---"
    new_s = f"{bc_dir_new:.0f}°" if bc_dir_new is not None else "FAIL"
    err_new_s = f"{dir_err_new:+.1f}°" if dir_err_new is not None else "FAIL"
    improved = ""
    if dir_err_old is not None and dir_err_new is not None:
        improved = "YES" if abs(dir_err_new) < abs(dir_err_old) else "NO"

    peak_short = r['peak_dt_utc'][:16]
    print(f"  {r['stid']:<8} {peak_short:>18}  {obs_dir:>7.1f}° {old_s:>10} {err_old_s:>11}  "
          f"{new_s:>10} {err_new_s:>11}  {improved}")

print()
print("VERDICT: The direction mismatch is cleared if most stations show |dir_err_NEW| < 30°")
print("         and are improved vs OLD.")
