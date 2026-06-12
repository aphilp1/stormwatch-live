#!/usr/bin/env python3
"""
rrfs_extract.py  —  Phase 3: RRFS hindcast wind extraction harness
===================================================================
Reads RRFS 3km and 1.5km GRIB2 output, extracts 10m u/v wind at each
anchor station's exact lat/lon and station-aligned peak hour, and writes
rrfs_hindcast.csv.

Conventions (must match departure-database pipeline):
  vec_avg:   mean u/v → atan2 (never average raw degrees)
  direction: meteorological FROM-direction (0=N, 90=E, 180=S, 270=W)
  speed:     mph = m/s × 2.23694
  output:    new file, do NOT touch hrrr_error_dataset.csv

RRFS file naming (expected):
  rrfs.YYYYMMDD/rrfs.tHHz.prslev.f000.conus_3km.grib2   (3km domain)
  rrfs.YYYYMMDD/rrfs.tHHz.prslev.f000.conus_15km.grib2  (1.5km domain)
  or any GRIB2 with UGRD/VGRD at "10 m above ground"

Usage:
  python rrfs_extract.py                  # dry-run against HRRR test files
  python rrfs_extract.py --run            # process RRFS files per RRFS_FILE_MAP

Testing:
  Without --run, uses HRRR_TEST_MAP (HRRR cache subsets, same GRIB2 format)
  to validate extraction logic before real RRFS data exists.

Run (PowerShell with hrrr311 DLLs in PATH):
  $CONDA_ENV = "C:/Users/aphil/miniforge3/envs/hrrr311"
  $env:PATH = "$CONDA_ENV;$CONDA_ENV/Library/bin;..." + $env:PATH
  & "$CONDA_ENV/python.exe" rrfs_extract.py
"""
import csv, math, os, sys, datetime, argparse
import numpy as np
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import cfgrib
    import xarray as xr
    CFGRIB_OK = True
except ImportError:
    CFGRIB_OK = False
    print('WARNING: cfgrib not available — using herbie fallback')
    try:
        from herbie import Herbie
    except ImportError:
        print('ERROR: neither cfgrib nor herbie available. Cannot read GRIB2.')
        sys.exit(1)

MS_MPH = 2.23694

BASE     = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
HRRR_CACHE = os.path.join(BASE, 'hrrr_bc_cache')
OUT_CSV  = os.path.join(BASE, 'rrfs_hindcast.csv')

# ── Anchor station definitions ────────────────────────────────────────────────
# Peak hours from hrrr_error_dataset.csv (station-aligned, each station's own peak)
# obs_sus_mph and hrrr_err from existing database for reference column.

ANCHORS = [
    {
        'stid':       'CBXC1',
        'event_id':   'camp_2018',
        'lat':        40.14564,
        'lon':       -121.52250,
        'peak_utc':  '2018-11-08T17:00Z',   # station-aligned
        'obs_sus':    28.99,
        'obs_dir':    69.3,
        'hrrr_spd':   25.37,
        'hrrr_err':   -3.62,
    },
    {
        'stid':       'WMSC1',
        'event_id':   'thomas_2017',
        'lat':        34.59583,
        'lon':       -118.57861,
        'peak_utc':  '2017-12-07T02:00Z',
        'obs_sus':    45.99,
        'obs_dir':    62.3,
        'hrrr_spd':   10.34,
        'hrrr_err':  -35.65,
    },
    {
        'stid':       'WMSC1',
        'event_id':   'woolsey_2018',
        'lat':        34.59583,
        'lon':       -118.57861,
        'peak_utc':  '2018-11-09T04:00Z',
        'obs_sus':    44.98,
        'obs_dir':    68.0,
        'hrrr_spd':   17.94,
        'hrrr_err':  -27.04,
    },
]

# ── RRFS file map (fill in once model output exists) ─────────────────────────
# Keys: (stid, event_id, resolution)
# Values: path to GRIB2 file for that station's peak hour
# resolution: '3km' or '15km' (1.5km abbreviated)

RRFS_FILE_MAP = {
    # ('CBXC1', 'camp_2018',     '3km'):  r'path/to/rrfs_3km_camp.grib2',
    # ('CBXC1', 'camp_2018',     '15km'): r'path/to/rrfs_15km_camp.grib2',
    # ('WMSC1', 'thomas_2017',   '3km'):  r'path/to/rrfs_3km_thomas.grib2',
    # ('WMSC1', 'thomas_2017',   '15km'): r'path/to/rrfs_15km_thomas.grib2',
    # ('WMSC1', 'woolsey_2018',  '3km'):  r'path/to/rrfs_3km_woolsey.grib2',
    # ('WMSC1', 'woolsey_2018',  '15km'): r'path/to/rrfs_15km_woolsey.grib2',
}

# ── Test file map using HRRR cache (same GRIB2 format, validates logic) ──────
# Using Camp Fire date surface files (wrfsfcf00 has UGRD/VGRD at 10m AGL).
# These files validate the extraction pipeline before RRFS output exists.

def _find_hrrr_surface(date_str, hour):
    """Return path to HRRR surface subset grib2 in cache, or None."""
    day_dir = os.path.join(HRRR_CACHE, 'hrrr', date_str)
    if not os.path.exists(day_dir):
        return None
    for fname in os.listdir(day_dir):
        if f't{hour:02d}z.wrfsfcf00' in fname and fname.endswith('.grib2'):
            return os.path.join(day_dir, fname)
    return None

HRRR_TEST_MAP = {}
for anc in ANCHORS:
    dt = datetime.datetime.strptime(anc['peak_utc'].replace('Z',''), '%Y-%m-%dT%H:%M')
    date_str = dt.strftime('%Y%m%d')
    path = _find_hrrr_surface(date_str, dt.hour)
    if path is None:
        # try adjacent hours if exact hour not cached
        for dh in [1, -1, 2, -2]:
            dt2 = dt + datetime.timedelta(hours=dh)
            path = _find_hrrr_surface(dt2.strftime('%Y%m%d'), dt2.hour)
            if path: break
    if path:
        HRRR_TEST_MAP[(anc['stid'], anc['event_id'], '3km')]  = path
        HRRR_TEST_MAP[(anc['stid'], anc['event_id'], '15km')] = path


# ── GRIB2 extraction helpers ──────────────────────────────────────────────────

def _extract_uv_cfgrib(grib2_path, search_key='10 m above ground'):
    """Extract u/v wind from GRIB2 using cfgrib. Returns (u_da, v_da) xarray DataArrays."""
    filters = {'typeOfLevel': 'heightAboveGround', 'level': 10,
               'shortName': ['10u', '10v']}
    try:
        ds_list = cfgrib.open_datasets(grib2_path,
                                        filter_by_keys={'typeOfLevel': 'heightAboveGround',
                                                        'level': 10})
        for ds in ds_list:
            u = None; v = None
            for var in ds.data_vars:
                name = var.lower()
                if 'u10' in name or name == '10u' or ('u' in name and '10' in str(ds[var].attrs.get('GRIB_shortName',''))):
                    u = ds[var]
                if 'v10' in name or name == '10v' or ('v' in name and '10' in str(ds[var].attrs.get('GRIB_shortName',''))):
                    v = ds[var]
            if u is not None and v is not None:
                return u, v
    except Exception as ex:
        pass
    # Fallback: try all datasets, look for u10/v10 by GRIB_shortName
    try:
        ds_list = cfgrib.open_datasets(grib2_path)
        for ds in ds_list:
            for var in ds.data_vars:
                sname = str(ds[var].attrs.get('GRIB_shortName', ''))
                if sname == '10u':
                    u = ds[var]
                if sname == '10v':
                    v = ds[var]
            if 'u' in dir() and 'v' in dir():
                return u, v
    except Exception as ex2:
        raise RuntimeError(f'cfgrib could not extract 10m u/v from {grib2_path}: {ex2}')
    raise RuntimeError(f'No 10m u/v found in {grib2_path}')


def _extract_uv_herbie(grib2_date, grib2_hour):
    """Extract u/v 10m wind via Herbie (fallback if cfgrib unavailable)."""
    H = Herbie(datetime.datetime(grib2_date.year, grib2_date.month, grib2_date.day,
                                  grib2_hour), model='hrrr', product='sfc', fxx=0,
               save_dir=HRRR_CACHE, verbose=False)
    ds = H.xarray(':(?:UGRD|VGRD):10 m above ground:', remove_grib=False)
    return ds


def _wind_at_latlon(u_da, v_da, lat, lon):
    """
    Nearest-neighbour extraction of u/v at (lat,lon).
    Returns (speed_mph, direction_deg) using vec_avg convention.
    direction = meteorological FROM-direction: 0=N, 90=E, 180=S, 270=W.
    """
    # Build flat lat/lon arrays
    if 'latitude' in u_da.coords:
        grid_lat = u_da.latitude.values.ravel()
        grid_lon = u_da.longitude.values.ravel()
    elif 'lat' in u_da.coords:
        grid_lat = u_da.lat.values.ravel()
        grid_lon = u_da.lon.values.ravel()
    else:
        raise RuntimeError('Cannot find latitude coordinate in wind DataArray')

    # Normalize longitude to same sign as target
    if grid_lon.min() > 0 and lon < 0:
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    dist, idx = tree.query([lat, lon])
    if dist > 1.5:
        raise RuntimeError(f'Nearest grid point {dist:.2f}° away — too far (>1.5°)')

    u = float(u_da.values.ravel()[idx])  # m/s, + = eastward
    v = float(v_da.values.ravel()[idx])  # m/s, + = northward

    speed_ms  = math.sqrt(u**2 + v**2)
    speed_mph = speed_ms * MS_MPH

    # Met FROM-direction: wind FROM the direction (u,v) is blowing toward → FROM = opposite
    # atan2(u, v) gives direction toward which wind is blowing (met convention with FROM)
    # Standard: direction = (270 - math.degrees(atan2(v, u))) % 360  (FROM-direction)
    drct = (270.0 - math.degrees(math.atan2(v, u))) % 360.0

    return speed_mph, drct


def _ang_diff(a, b):
    return (a - b + 180) % 360 - 180


# ── Main extraction ───────────────────────────────────────────────────────────

def run_extraction(file_map, label='RRFS'):
    """
    Extract winds from GRIB2 files in file_map and return list of result dicts.
    file_map: {(stid, event_id, resolution): grib2_path}
    """
    results = []

    # Group by file (one cfgrib open per file, shared across stations)
    file_to_keys = {}
    for (stid, eid, res), path in file_map.items():
        file_to_keys.setdefault(path, []).append((stid, eid, res))

    for path, keys in sorted(file_to_keys.items()):
        print(f'\n  File: {os.path.basename(path)}')
        try:
            if CFGRIB_OK:
                u_da, v_da = _extract_uv_cfgrib(path)
            else:
                raise RuntimeError('cfgrib not available')
            print(f'    Loaded u/v 10m wind grid: shape={u_da.shape}')
        except Exception as ex:
            print(f'    ERROR loading {path}: {ex}')
            for (stid, eid, res) in keys:
                results.append(_make_row(stid, eid, res, None, None))
            continue

        for (stid, eid, res) in keys:
            anc = next(a for a in ANCHORS if a['stid']==stid and a['event_id']==eid)
            try:
                spd, drct = _wind_at_latlon(u_da, v_da, anc['lat'], anc['lon'])
                err = spd - anc['obs_sus']
                dir_err = _ang_diff(drct, anc['obs_dir'])
                print(f'    {stid}/{eid}/{res:>4}: spd={spd:.1f} mph @ {drct:.1f}°  '
                      f'obs={anc["obs_sus"]:.1f}  err={err:+.1f}  dir_err={dir_err:+.1f}°')
                results.append(_make_row(stid, eid, res, spd, drct, anc))
            except Exception as ex:
                print(f'    ERROR at {stid}/{eid}/{res}: {ex}')
                results.append(_make_row(stid, eid, res, None, None, anc))

    return results


def _make_row(stid, eid, res, spd, drct, anc=None):
    obs   = anc['obs_sus']  if anc else None
    hspd  = anc['hrrr_spd'] if anc else None
    herr  = anc['hrrr_err'] if anc else None
    err   = round(spd - obs, 2) if (spd is not None and obs is not None) else ''
    return {
        'stid':           stid,
        'event_id':       eid,
        'resolution':     res,
        'rrfs_speed_mph': round(spd, 2) if spd is not None else '',
        'rrfs_dir_deg':   round(drct, 1) if drct is not None else '',
        'speed_err_mph':  err,
        'obs_sus_mph':    obs if obs is not None else '',
        'hrrr_speed_mph': hspd if hspd is not None else '',
        'hrrr_err_mph':   herr if herr is not None else '',
    }


def write_csv(rows, path):
    fields = ['stid','event_id','resolution','rrfs_speed_mph','rrfs_dir_deg',
              'speed_err_mph','obs_sus_mph','hrrr_speed_mph','hrrr_err_mph']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f'\nWritten: {path}')


# ── Integration summary table ─────────────────────────────────────────────────

def print_summary(rows):
    print()
    print('=' * 90)
    print('INTEGRATION TABLE: HRRR err → RRFS 3km err → RRFS 1.5km err')
    print(f'  {"anchor":<30} {"obs":>5} | {"HRRR_err":>9} | {"3km_err":>9} | {"15km_err":>9} | {"WN_err*":>9}')
    print('-' * 90)
    wn_err = {'CBXC1/camp_2018': '+6.4', 'WMSC1/thomas_2017': '-10.2', 'WMSC1/woolsey_2018': '≈0.0'}
    for anc in ANCHORS:
        key = f'{anc["stid"]}/{anc["event_id"]}'
        obs = anc['obs_sus']
        herr = anc['hrrr_err']
        r3  = next((r for r in rows if r['stid']==anc['stid'] and r['event_id']==anc['event_id'] and r['resolution']=='3km'), None)
        r15 = next((r for r in rows if r['stid']==anc['stid'] and r['event_id']==anc['event_id'] and r['resolution']=='15km'), None)
        e3   = f'{r3["speed_err_mph"]:+.1f}'  if r3 and r3['speed_err_mph'] != '' else 'PENDING'
        e15  = f'{r15["speed_err_mph"]:+.1f}' if r15 and r15['speed_err_mph'] != '' else 'PENDING'
        wn   = wn_err.get(key, '?')
        print(f'  {key:<30} {obs:>5.1f} | {herr:>+9.1f} | {e3:>9} | {e15:>9} | {wn:>9}')
    print()
    print('* WN_err = raw WN+rawBC result from phase_b_wn_test.py (existing validated result)')
    print('  Interpretation: 3km RRFS ≈ HRRR expected (FV3 physics, same resolution)')
    print('  Key rung: 1.5km nest — if error shrinks there, resolution drives the underbias')
    print('=' * 90)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RRFS hindcast extraction harness')
    parser.add_argument('--run', action='store_true',
                        help='Process real RRFS files (RRFS_FILE_MAP). Default: test mode (HRRR)')
    args = parser.parse_args()

    if args.run:
        if not RRFS_FILE_MAP:
            print('ERROR: RRFS_FILE_MAP is empty. Fill in file paths before running with --run.')
            sys.exit(1)
        print('MODE: RRFS run (real model output)')
        file_map = RRFS_FILE_MAP
    else:
        print('MODE: TEST (HRRR cache files — validates extraction logic)')
        if not HRRR_TEST_MAP:
            print('  WARNING: No HRRR test files found in cache. Check HRRR_CACHE path.')
        else:
            print(f'  Test files found: {len(HRRR_TEST_MAP)} entries')
            for k, v in sorted(HRRR_TEST_MAP.items()):
                print(f'    {k[0]}/{k[1]}/{k[2]}: {os.path.basename(v)}')
        file_map = HRRR_TEST_MAP

    print(f'\ncfgrib available: {CFGRIB_OK}')
    print(f'Anchors: {len(ANCHORS)} stations × 2 resolutions = {len(ANCHORS)*2} extractions\n')

    rows = run_extraction(file_map, label='TEST' if not args.run else 'RRFS')
    print_summary(rows)

    out = OUT_CSV if args.run else OUT_CSV.replace('.csv', '_test.csv')
    write_csv(rows, out)

    if not args.run:
        print()
        print('Test complete. Review extraction results above.')
        print('If speeds/directions look physically plausible, harness is format-validated.')
        print('Populate RRFS_FILE_MAP and run with --run once real model output is available.')
