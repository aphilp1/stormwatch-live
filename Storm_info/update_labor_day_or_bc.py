#!/usr/bin/env python3
"""
update_labor_day_or_bc.py
=========================
Apply time-aligned bc_speed AND bc_dir to all active labor_day_or2020 rows.

BC level: 700 hPa (downslope_oregon regime — Cascade ridge height ~3100m).
Both values extracted from HRRR 700 hPa at each station's own peak hour.
time_aligned_bc.csv has 0 rows for this event; alignment done fresh here.

23 unique pull hours across Sep 7-9 2020. Herbie fetches from AWS S3 archive
for any hours not yet cached.

Run (PowerShell with hrrr311 DLLs in PATH):
  & python update_labor_day_or_bc.py
"""
import csv, datetime, math, os, sys, shutil
import numpy as np
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE   = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DB     = os.path.join(BASE, 'hrrr_error_dataset.csv')
CACHE  = os.path.join(BASE, 'hrrr_bc_cache')
LEVEL  = 700   # downslope_oregon — 700 hPa throughout
MS_MPH = 2.23694


def extract_hrrr_uv(peak_dt, level_hpa=700):
    H = Herbie(peak_dt, model='hrrr', product='prs', fxx=0,
               save_dir=CACHE, verbose=False)
    search = f':(?:UGRD|VGRD):{level_hpa} mb:'
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
    spd  = math.sqrt(u**2 + v**2) * MS_MPH
    drct = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return spd, drct


def ang_diff(a, b):
    return (a - b + 180) % 360 - 180


# 1. Load DB
all_rows = []
with open(DB, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        all_rows.append(r)

active = [r for r in all_rows
          if r.get('event_id') == 'labor_day_or2020'
          and r.get('qc_flag') in ('KEEP', 'CAUTION')
          and r.get('peak_dt_utc', '') not in ('', 'N/A', 'nan')]
print(f'Active labor_day_or2020 rows: {len(active)}')

# 2. Group by peak hour
by_dt = {}
for r in active:
    dt = datetime.datetime.fromisoformat(r['peak_dt_utc'].replace('Z', '+00:00'))
    dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    by_dt.setdefault(dt_h, []).append(r)

print(f'Unique pull hours: {len(by_dt)}')
for dt_h in sorted(by_dt):
    print(f'  {dt_h}  n={len(by_dt[dt_h])}  '
          f'stids={[r["stid"] for r in by_dt[dt_h]]}')
print()

# 3. Fetch HRRR 700 hPa and extract speed + direction at each station
print(f'Fetching HRRR {LEVEL} hPa (fxx=0) for each peak hour...')
aligned = {}   # stid -> (bc_spd_new, bc_dir_new)
failed_hours = []
for dt_h, rows in sorted(by_dt.items()):
    try:
        ds = extract_hrrr_uv(dt_h, LEVEL)
        for r in rows:
            spd, drct = uv_at_point(ds, float(r['lat']), float(r['lon']))
            aligned[r['stid']] = (round(spd, 2), round(drct, 1))
        print(f'  OK: {dt_h}  {[r["stid"] for r in rows]}')
    except Exception as ex:
        print(f'  FAIL: {dt_h} -> {ex}')
        failed_hours.append(dt_h)

print(f'\nExtracted: {len(aligned)}/{len(active)} stations')
if failed_hours:
    print(f'Failed hours: {failed_hours}')
print()

# 4. Before/after table
print('=' * 105)
print(f'BEFORE / AFTER  bc_speed | bc_dir | hrrr_coupling_frac  ({LEVEL} hPa, time-aligned)')
print(f'  {"stid":<12} {"peak_h":>8} {"obs":>7} {"spd_OLD":>9} {"spd_NEW":>9} '
      f'{"dir_OLD":>8} {"dir_NEW":>8} {"bc_dir_err":>11}  {"cf_OLD":>7} {"cf_NEW":>7}  note')
print('  ' + '-' * 103)

for r in sorted(active, key=lambda x: x.get('peak_dt_utc', '')):
    stid    = r['stid']
    spd_old = float(r['bc_speed']) if r.get('bc_speed') not in ('', 'nan') else None
    dir_old = float(r['bc_dir'])   if r.get('bc_dir')   not in ('', 'nan') else None
    h10     = float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph') not in ('', 'nan') else None
    obs     = float(r['obs_sus_mph'])  if r.get('obs_sus_mph')  not in ('', 'nan', 'MISSING') else None
    obs_dir = float(r['obs_dir_deg'])  if r.get('obs_dir_deg')  not in ('', 'nan', 'MISSING') else None
    peak_h  = r.get('peak_dt_utc', '')[-14:-9] if r.get('peak_dt_utc') else '?'

    vals = aligned.get(stid)
    spd_new = vals[0] if vals else None
    dir_new = vals[1] if vals else None

    cf_old = h10 / spd_old if (h10 and spd_old) else None
    cf_new = h10 / spd_new if (h10 and spd_new) else None
    derr   = ang_diff(dir_new, obs_dir) if (dir_new is not None and obs_dir is not None) else None

    note = ''
    if spd_old is not None and spd_new is not None and abs(spd_new - spd_old) > 10:
        note = f'SPD_SHIFT({spd_new - spd_old:+.1f})'

    derr_s = f'{derr:+.1f}' if derr is not None else '---'
    print(f'  {stid:<12} {peak_h:>8} {obs or 0:>7.1f} {spd_old or 0:>9.2f} '
          f'{spd_new or 0:>9.2f} {dir_old or 0:>8.1f} {dir_new or 0:>8.1f} '
          f'{derr_s:>11}  {cf_old or 0:>7.4f} {cf_new or 0:>7.4f}  {note}')

print()

# 5. Backup and update
backup = DB.replace('.csv', '_pre_labor_day_or_bc.csv')
shutil.copy2(DB, backup)
print(f'Backup: {backup}')

n_spd = n_dir = n_cf = 0
for r in all_rows:
    if r.get('event_id') != 'labor_day_or2020':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    stid = r['stid']
    if stid not in aligned:
        continue

    spd_new, dir_new = aligned[stid]
    r['bc_speed'] = f'{spd_new:.2f}'
    n_spd += 1

    r['bc_dir'] = str(dir_new)
    n_dir += 1

    h10 = float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph') not in ('', 'nan') else None
    if h10 and spd_new:
        r['hrrr_coupling_frac'] = f'{h10 / spd_new:.4f}'
        n_cf += 1

with open(DB, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f'Updated: bc_speed={n_spd}, bc_dir={n_dir}, hrrr_coupling_frac={n_cf}')
print(f'Backup: {backup}')
