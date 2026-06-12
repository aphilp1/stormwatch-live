#!/usr/bin/env python3
"""
update_kincade_run_bc.py
========================
Apply time-aligned bc_speed and bc_dir to all active kincade_run_2019 rows.
Same discipline as Tubbs: unconditional replacement with each station's own
peak-hour value from HRRR 850 hPa cache. Also recomputes hrrr_coupling_frac.

bc_speed source: time_aligned_bc.csv (already computed)
bc_dir source:   HRRR 850 hPa cache via Herbie at each station's peak hour

Run (PowerShell with hrrr311 DLLs in PATH):
  & python update_kincade_run_bc.py
"""
import csv, datetime, math, os, sys, shutil
import numpy as np
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DB    = os.path.join(BASE, 'hrrr_error_dataset.csv')
ALN   = os.path.join(BASE, 'time_aligned_bc.csv')
CACHE = os.path.join(BASE, 'hrrr_bc_cache')
MS_MPH = 2.23694


def extract_hrrr_uv(peak_dt, level_hpa=850):
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
    spd = math.sqrt(u**2 + v**2) * MS_MPH
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
          if r.get('event_id') == 'kincade_run_2019'
          and r.get('qc_flag') in ('KEEP', 'CAUTION')]
print(f'Active kincade_run_2019 rows: {len(active)}')

# 2. Load aligned bc_speed from time_aligned_bc.csv
spd_aligned = {}   # stid -> (bc_speed_aligned, offset_h)
with open(ALN, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('event_id') != 'kincade_run_2019':
            continue
        try:
            spd_aligned[r['stid']] = (float(r['bc_speed_aligned']), r.get('offset_h', ''))
        except Exception:
            pass
print(f'bc_speed aligned values loaded: {len(spd_aligned)} stations')

# 3. Extract aligned bc_dir from HRRR cache grouped by peak hour
by_dt = {}
for r in active:
    if r.get('peak_dt_utc', '') in ('N/A', '', 'nan'):
        continue
    dt = datetime.datetime.fromisoformat(r['peak_dt_utc'].replace('Z', '+00:00'))
    dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    by_dt.setdefault(dt_h, []).append(r)

print('\nExtracting aligned bc_dir from cached HRRR 850 hPa:')
dir_aligned = {}   # stid -> bc_dir_new
for dt_h, rows in sorted(by_dt.items()):
    try:
        ds = extract_hrrr_uv(dt_h, 850)
        for r in rows:
            spd, drct = uv_at_point(ds, float(r['lat']), float(r['lon']))
            dir_aligned[r['stid']] = round(drct, 1)
        print(f'  OK: {dt_h}  stations={[r["stid"] for r in rows]}')
    except Exception as ex:
        print(f'  FAIL: {dt_h} -> {ex}')

print()

# 4. Print before/after table
print('=' * 95)
print('BEFORE / AFTER  bc_speed | bc_dir | hrrr_coupling_frac')
print(f'  {"stid":<8} {"peak_h":>6} {"obs":>7} {"spd_OLD":>9} {"spd_NEW":>9} '
      f'{"dir_OLD":>8} {"dir_NEW":>8} {"dir_err_new":>11}  {"cf_OLD":>7} {"cf_NEW":>7}  note')
print('  ' + '-' * 93)

for r in sorted(active, key=lambda x: x.get('peak_dt_utc', '')):
    stid = r['stid']
    spd_old = float(r['bc_speed']) if r.get('bc_speed') not in ('', 'nan') else None
    dir_old = float(r['bc_dir']) if r.get('bc_dir') not in ('', 'nan') else None
    h10 = float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph') not in ('', 'nan') else None
    obs = float(r['obs_sus_mph']) if r.get('obs_sus_mph') not in ('', 'nan') else None
    obs_dir = float(r['obs_dir_deg']) if r.get('obs_dir_deg') not in ('', 'nan') else None
    peak_h = r.get('peak_dt_utc', '')[-14:-9] if r.get('peak_dt_utc') else '?'

    spd_new, off_h = spd_aligned.get(stid, (spd_old, ''))
    dir_new = dir_aligned.get(stid)

    cf_old = h10 / spd_old if (h10 and spd_old) else None
    cf_new = h10 / spd_new if (h10 and spd_new) else None

    derr = ang_diff(dir_new, obs_dir) if (dir_new is not None and obs_dir is not None) else None
    derr_s = f'{derr:+.1f}' if derr is not None else '---'

    note = ''
    if spd_old is not None and spd_new is not None and abs(spd_new - spd_old) > 10:
        note = f'SPD_SHIFT({spd_new - spd_old:+.1f})'

    print(f'  {stid:<8} {peak_h:>6} {obs or 0:>7.1f} {spd_old or 0:>9.2f} {spd_new or 0:>9.2f} '
          f'{dir_old or 0:>8.1f} {dir_new or 0:>8.1f} {derr_s:>11}  '
          f'{cf_old or 0:>7.4f} {cf_new or 0:>7.4f}  {note}')

print()

# 5. Backup and update
backup = DB.replace('.csv', '_pre_kincade_run_bc.csv')
shutil.copy2(DB, backup)
print(f'Backup: {backup}')

n_spd = n_dir = n_cf = 0
for r in all_rows:
    if r.get('event_id') != 'kincade_run_2019':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    stid = r['stid']

    if stid in spd_aligned:
        spd_new, _ = spd_aligned[stid]
        r['bc_speed'] = f'{spd_new:.2f}'
        n_spd += 1
        h10 = float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph') not in ('', 'nan') else None
        if h10 and spd_new:
            r['hrrr_coupling_frac'] = f'{h10/spd_new:.4f}'
            n_cf += 1

    if stid in dir_aligned:
        r['bc_dir'] = str(dir_aligned[stid])
        n_dir += 1

with open(DB, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f'Updated: bc_speed={n_spd} rows, bc_dir={n_dir} rows, hrrr_coupling_frac={n_cf} rows')
print(f'Backup: {backup}')
