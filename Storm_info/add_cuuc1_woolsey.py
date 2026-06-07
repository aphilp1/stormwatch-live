#!/usr/bin/env python3
"""
add_cuuc1_woolsey.py
====================
Add CUUC1 (Chuchupate, 5280 ft) / woolsey_2018 to hrrr_error_dataset.csv
and time_aligned_bc.csv.

Obs from wrcc_synoptic_pull.py / raws_obs/CUUC1_woolsey_2018.csv:
  peak_dt_utc = 2018-11-09T02:22:00Z → aligned peak_hour = 2018-11-09T02:00Z
  obs_sus_mph = 15.99 (≈16.0)  obs_gust_mph = 28.01  obs_dir_deg = 41.0°
  lat = 34.80637   lon = -119.01363   elev_m = 1609.3 ft

Pulls:
  (a) HRRR 850 hPa at event-median hour  → bc_speed (DB convention)
  (b) HRRR 850 hPa at aligned peak hour  → bc_speed_aligned (time_aligned_bc.csv)
  (c) HRRR 10m at aligned peak hour      → hrrr_10m_mph / dir (aligned coupling)

Run: conda run -n hrrr311 python add_cuuc1_woolsey.py
"""

import csv, datetime, math, os, sys
import numpy as np
from scipy.spatial import KDTree
from herbie import Herbie

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE    = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
CACHE   = os.path.join(BASE, 'hrrr_bc_cache')
DB_FILE = os.path.join(BASE, 'hrrr_error_dataset.csv')
TAB     = os.path.join(BASE, 'time_aligned_bc.csv')   # time_aligned_bc.csv
MS_MPH  = 2.23694

os.makedirs(CACHE, exist_ok=True)

# ── Station / obs constants ───────────────────────────────────────────────────
STID      = 'CUUC1'
EVENT_ID  = 'woolsey_2018'
LAT       = 34.80637
LON       = -119.01363
ELEV_M    = 1609.3
OBS_SUS   = 15.99
OBS_GUST  = 28.01
OBS_DIR   = 41.0
PEAK_DT   = datetime.datetime(2018, 11, 9, 2, 22, 0)
PEAK_H    = datetime.datetime(2018, 11, 9, 2, 0, 0)   # aligned peak hour
BC_LEVEL  = 850

# ── Compute event-median peak hour from existing woolsey DB rows ──────────────
peak_hours = []
with open(DB_FILE, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['event_id'] != EVENT_ID:
            continue
        if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
            continue
        if r.get('synoptic_regime', '') != 'santa_ana':
            continue
        try:
            dt = datetime.datetime.fromisoformat(
                r['peak_dt_utc'].replace('Z', '+00:00'))
            ph = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
            peak_hours.append(ph)
        except Exception:
            pass

peak_hours_sorted = sorted(peak_hours)
event_median_h = peak_hours_sorted[len(peak_hours_sorted) // 2]
print(f'Woolsey event-median peak hour (from {len(peak_hours)} stations): {event_median_h}')

# ── HRRR extraction helper ────────────────────────────────────────────────────
def pull_prs_uv(dt_naive, level_hpa):
    search = f':(?:UGRD|VGRD):{level_hpa} mb:'
    H = Herbie(dt_naive, model='hrrr', product='prs', fxx=0,
               save_dir=CACHE, verbose=False)
    return H.xarray(search, remove_grib=False)

def pull_sfc_10m_uv(dt_naive):
    search = r':(?:UGRD|VGRD):10 m above ground:'
    H = Herbie(dt_naive, model='hrrr', product='sfc', fxx=0,
               save_dir=CACHE, verbose=False)
    return H.xarray(search, remove_grib=False)

def extract_uv(ds, lat, lon):
    if not hasattr(ds, 'data_vars'):
        raise ValueError(f'Expected Dataset, got {type(ds)}')
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
    dist, idx = tree.query([lat, lon])
    if dist > 1.0:
        raise RuntimeError(f'Nearest grid point too far: {dist:.3f} deg')

    u = float(u_da.values.ravel()[idx])
    v = float(v_da.values.ravel()[idx])
    spd = math.sqrt(u**2 + v**2) * MS_MPH
    d   = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return spd, d


# ── Pull A: bc at event-median hour (matches other woolsey DB entries) ─────────
print(f'\nPulling 850 hPa at event-median {event_median_h}...')
try:
    ds_med = pull_prs_uv(event_median_h, BC_LEVEL)
    bc_speed_med, bc_dir_med = extract_uv(ds_med, LAT, LON)
    print(f'  bc_speed (event-median) = {bc_speed_med:.2f} mph @ {bc_dir_med:.1f}°')
except Exception as ex:
    print(f'  FAIL: {ex}')
    bc_speed_med = bc_dir_med = None

# ── Pull B: bc at aligned peak hour ──────────────────────────────────────────
print(f'\nPulling 850 hPa at aligned peak {PEAK_H}...')
try:
    ds_pk = pull_prs_uv(PEAK_H, BC_LEVEL)
    bc_speed_aligned, bc_dir_aligned = extract_uv(ds_pk, LAT, LON)
    print(f'  bc_speed (aligned)      = {bc_speed_aligned:.2f} mph @ {bc_dir_aligned:.1f}°')
except Exception as ex:
    print(f'  FAIL: {ex}')
    bc_speed_aligned = bc_dir_aligned = None

# ── Pull C: HRRR 10m at aligned peak hour ─────────────────────────────────────
print(f'\nPulling HRRR 10m at aligned peak {PEAK_H}...')
try:
    ds_10m = pull_sfc_10m_uv(PEAK_H)
    hrrr_10m_mph, hrrr_10m_dir = extract_uv(ds_10m, LAT, LON)
    print(f'  hrrr_10m                = {hrrr_10m_mph:.2f} mph @ {hrrr_10m_dir:.1f}°')
except Exception as ex:
    print(f'  FAIL: {ex}')
    hrrr_10m_mph = hrrr_10m_dir = None

# ── Compute derived fields ─────────────────────────────────────────────────────
print()
bc_speed_db = bc_speed_med if bc_speed_med is not None else bc_speed_aligned

if bc_speed_db is not None and hrrr_10m_mph is not None:
    speed_err   = round(hrrr_10m_mph - OBS_SUS, 4)
    speed_ratio = round(hrrr_10m_mph / OBS_SUS, 3) if OBS_SUS > 0 else None
    dir_err     = round(hrrr_10m_dir - OBS_DIR, 1) if hrrr_10m_dir is not None else None
    coupling_frac = round(hrrr_10m_mph / bc_speed_db, 4) if bc_speed_db > 0 else None

    print('Computed fields:')
    print(f'  speed_err         = {speed_err:+.2f} mph  (HRRR 10m - obs)')
    print(f'  speed_ratio       = {speed_ratio:.3f}  (HRRR/obs)')
    print(f'  dir_err           = {dir_err:+.1f}°')
    print(f'  hrrr_coupling_frac= {coupling_frac:.4f}')
else:
    speed_err = speed_ratio = dir_err = coupling_frac = None

# ── Check for existing CUUC1/woolsey row in DB ─────────────────────────────────
existing_keys = set()
db_rows = []
db_fieldnames = None
with open(DB_FILE, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    db_fieldnames = reader.fieldnames
    for r in reader:
        existing_keys.add((r['stid'], r['event_id']))
        db_rows.append(r)

already_in_db = (STID, EVENT_ID) in existing_keys
print(f'\n{"[ALREADY IN DB]" if already_in_db else "[NOT IN DB — will add]"}  ({STID}, {EVENT_ID})')

if not already_in_db and bc_speed_db is not None and hrrr_10m_mph is not None:
    new_row = {f: '' for f in db_fieldnames}
    new_row.update({
        'event_id':        EVENT_ID,
        'stid':            STID,
        'station_name':    'CHUCHUPATE',
        'lat':             str(LAT),
        'lon':             str(LON),
        'state':           'CA',
        'qc_flag':         'KEEP',
        'qc_reason':       'Synoptic obs confirmed vs WRCC (EXACT match 2026-06-07); 5280 ft, Ventura County, near Santa Ana inversion lid',
        'obs_sus_mph':     f'{OBS_SUS:.2f}',
        'obs_gust_mph':    f'{OBS_GUST:.2f}',
        'obs_dir_deg':     f'{OBS_DIR:.1f}',
        'peak_dt_utc':     PEAK_DT.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'peak_hour_utc':   PEAK_H.strftime('%Y-%m-%dT%H:%MZ'),
        'hrrr_10m_mph':    f'{hrrr_10m_mph:.2f}' if hrrr_10m_mph is not None else 'NEEDS_HRRR',
        'hrrr_10m_dir':    f'{hrrr_10m_dir:.1f}' if hrrr_10m_dir is not None else 'NEEDS_HRRR',
        'speed_err':       f'{speed_err:.4f}' if speed_err is not None else 'NEEDS_HRRR',
        'speed_ratio':     f'{speed_ratio:.3f}' if speed_ratio is not None else 'NEEDS_HRRR',
        'dir_err':         f'{dir_err:.1f}' if dir_err is not None else 'NEEDS_HRRR',
        'arrival_err':     'NEEDS_HRRR_TS',
        'elev_m':          f'{ELEV_M}',
        'slope':           'NEEDS_DEM',
        'aspect':          'NEEDS_DEM',
        'relief_1km':      'NEEDS_DEM',
        'terrain_class':   'exposed_ridge',
        'terrain_class_source': 'elev_heuristic',
        'dem_verified':    'no',
        'elev_vs_inversion': 'NEEDS_INVERSION',
        'bc_dir':          f'{bc_dir_med:.1f}' if bc_dir_med is not None else (
                            f'{bc_dir_aligned:.1f}' if bc_dir_aligned is not None else 'NEEDS_BC'),
        'bc_speed':        f'{bc_speed_db:.2f}',
        'bc_level':        str(BC_LEVEL),
        'lapse_stability': 'NEEDS_BC',
        'mslp_grad':       'NEEDS_BC',
        'wn_minus_hrrr_speed': 'NEEDS_WN',
        'wn_minus_hrrr_dir':   'NEEDS_WN',
        'hrrr_version':    'v3',
        'hrrr_era':        'v3_era',
        'synoptic_regime': 'santa_ana',
        'spatial_cluster_id': 'wool-CUUC1',
        'repr_error_flag': 'NEEDS_DEM',
        'hrrr_coupling_frac': f'{coupling_frac:.4f}' if coupling_frac is not None else '',
    })

    db_rows.append(new_row)
    with open(DB_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=db_fieldnames)
        w.writeheader()
        w.writerows(db_rows)
    print(f'  → Added to hrrr_error_dataset.csv')

# ── Update time_aligned_bc.csv ────────────────────────────────────────────────
tab_rows = []
tab_fieldnames = None
already_in_tab = False
with open(TAB, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    tab_fieldnames = reader.fieldnames
    for r in reader:
        tab_rows.append(r)
        if r['stid'] == STID and r['event_id'] == EVENT_ID:
            already_in_tab = True

print(f'\n{"[ALREADY IN TAB]" if already_in_tab else "[NOT IN TAB — will add]"}  ({STID}, {EVENT_ID})')

if not already_in_tab and bc_speed_aligned is not None and hrrr_10m_mph is not None:
    offset_h = round((PEAK_H - event_median_h).total_seconds() / 3600)
    bco_aligned  = bc_speed_aligned / OBS_SUS
    bco_old      = (bc_speed_med / OBS_SUS) if bc_speed_med else bco_aligned
    cf_aligned   = hrrr_10m_mph / bc_speed_aligned if bc_speed_aligned > 0 else None
    cf_old       = hrrr_10m_mph / bc_speed_med if (bc_speed_med and bc_speed_med > 0) else cf_aligned

    tab_row = {
        'event_id':             EVENT_ID,
        'stid':                 STID,
        'synoptic_regime':      'santa_ana',
        'peak_dt_utc':          PEAK_DT.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'offset_h':             str(offset_h),
        'obs_sus_mph':          f'{OBS_SUS:.2f}',
        'hrrr_10m_mph':         f'{hrrr_10m_mph:.2f}',
        'speed_err':            f'{speed_err:.4f}' if speed_err is not None else '',
        'bc_speed_old':         f'{bc_speed_med:.2f}' if bc_speed_med else f'{bc_speed_aligned:.2f}',
        'bc_speed_aligned':     f'{bc_speed_aligned:.2f}',
        'bc_delta':             f'{bc_speed_aligned - (bc_speed_med or bc_speed_aligned):+.2f}',
        'bc_over_obs_old':      f'{bco_old:.3f}',
        'bc_over_obs_aligned':  f'{bco_aligned:.3f}',
        'bco_delta':            f'{bco_aligned - bco_old:+.3f}',
        'cf_old':               f'{cf_old:.4f}' if cf_old else '',
        'cf_aligned':           f'{cf_aligned:.4f}' if cf_aligned else '',
        'bc_level':             str(BC_LEVEL),
        'lat':                  str(LAT),
        'lon':                  str(LON),
    }
    tab_rows.append(tab_row)
    with open(TAB, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=tab_fieldnames)
        w.writeheader()
        w.writerows(tab_rows)
    print(f'  → Added to time_aligned_bc.csv')
    print(f'    offset_h={offset_h}h  bc_aligned={bc_speed_aligned:.2f}  bco={bco_aligned:.3f}  cf_aligned={cf_aligned:.4f}')

print('\nDone.')
