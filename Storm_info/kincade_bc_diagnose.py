"""
kincade_bc_diagnose.py  —  STAGE 1 ONLY
Diagnose the Kincade run (27 Oct 2019) BC direction problem.
No scoring, no WN runs, no amplification ratios.

Prints:
1. HRRR 700+850 hPa wind at KNXC1 grid cell at 00Z/06Z/12Z/18Z Oct 27
2. KNXC1 RAWS sustained wind + direction over Oct 27
3. ERA5 temperature profile at KNXC1 → inversion height estimate
4. Which (level, hour) best matches observed NE/NNE flow
"""

import sys, os, math, csv
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

os.environ['PATH'] = (
    r'C:\Users\aphil\miniforge3\envs\hrrr311' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\mingw-w64\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\usr\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Scripts' + os.pathsep +
    os.environ.get('PATH', '')
)
from herbie import Herbie

RAWS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\kincade_run_2019'

# KNXC1 Knoxville Creek: lat=38.862, lon=-122.417, elev=671m (2200 ft)
KNXC1_LAT, KNXC1_LON = 38.861940, -122.417200
KNXC1_ELEV_M = 671.0

# Also check Hawkeye (HWKC1) which IS on the RAWS for Oct 27
HWKC1_LAT, HWKC1_LON = 38.735090, -122.837060

def nearest_idx(ds, var, lat, lon):
    lats = ds['latitude'].values
    lons = ds['longitude'].values % 360
    dist = np.sqrt((lats - lat)**2 + (lons - lon % 360)**2)
    return np.unravel_index(dist.argmin(), dist.shape)

def nearest_val(ds, var, lat, lon):
    iy, ix = nearest_idx(ds, var, lat, lon)
    return float(ds[var].values[iy, ix])

def wind_from_uv(u, v):
    spd = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def ang_diff(a, b):
    """Signed angular difference a-b in (-180,180]."""
    d = (a - b + 180) % 360 - 180
    return d

# ─── 1. HRRR at KNXC1 and HWKC1: 700+850 hPa, 00/06/12/18Z Oct 27 ─────────
print('='*70)
print('HRRR f00 pressure-level winds at KNXC1 (38.862N, -122.417W) Oct 27 2019')
print('Also HWKC1 (38.735N, -122.837W) for comparison')
print('='*70)
print(f'{"Hour":6s}  {"Level":6s}  {"Site":8s}  {"Spd(mph)":>9s}  {"Dir(°)":>7s}  '
      f'{"U(m/s)":>7s}  {"V(m/s)":>7s}  {"HGT(m)":>7s}')
print('-'*70)

hrrr_results = {}   # (hour, level, site) -> {spd, dir, hgt}

LEVELS = [700, 850]
HOURS  = ['2019-10-27 00:00', '2019-10-27 06:00',
          '2019-10-27 12:00', '2019-10-27 18:00']
SITES  = {'KNXC1':(KNXC1_LAT, KNXC1_LON), 'HWKC1':(HWKC1_LAT, HWKC1_LON)}

for hrrr_time in HOURS:
    H = Herbie(hrrr_time, model='hrrr', product='prs', fxx=0)
    hz = hrrr_time[11:13]

    for level in LEVELS:
        ds_u  = H.xarray(f'UGRD:{level} mb')
        ds_v  = H.xarray(f'VGRD:{level} mb')
        ds_hgt= H.xarray(f'HGT:{level} mb')

        for site, (slat, slon) in SITES.items():
            u   = nearest_val(ds_u,   'u',   slat, slon)
            v   = nearest_val(ds_v,   'v',   slat, slon)
            hgt = nearest_val(ds_hgt, 'gh',  slat, slon)
            spd, dirn = wind_from_uv(u, v)
            hrrr_results[(hz, level, site)] = {'spd':spd, 'dir':dirn, 'hgt':round(hgt,0),
                                                'u':round(u,2), 'v':round(v,2)}
            print(f'{hz+"Z":6s}  {level:6d}  {site:8s}  {spd:>9.1f}  {dirn:>7.1f}  '
                  f'{u:>7.2f}  {v:>7.2f}  {hgt:>7.0f}')

# ─── 2. ERA5 temperature profile → inversion height ──────────────────────────
print()
print('='*70)
print('HRRR temperature profile at KNXC1 → inversion height (12Z Oct 27 2019)')
print('='*70)

H12 = Herbie('2019-10-27 12:00', model='hrrr', product='prs', fxx=0)
TEMP_LEVELS = [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 725, 700]

print(f'{"Level(hPa)":>12s}  {"HGT(m)":>8s}  {"Temp(°C)":>10s}  {"dT":>6s}')
print('-'*45)
prev_t, prev_h = None, None
inv_base_m = None

for lv in TEMP_LEVELS:
    try:
        ds_t = H12.xarray(f'TMP:{lv} mb')
        ds_h = H12.xarray(f'HGT:{lv} mb')
        t_k  = nearest_val(ds_t, 't',  KNXC1_LAT, KNXC1_LON)
        h_m  = nearest_val(ds_h, 'gh', KNXC1_LAT, KNXC1_LON)
        t_c  = round(t_k - 273.15, 1)
        dt_str = ''
        if prev_t is not None and prev_h is not None:
            dt = t_c - prev_t
            dh = h_m - prev_h   # positive = going up
            lapse = -dt / (dh / 1000) if dh != 0 else 0  # °C/km
            if dt > 0 and h_m > KNXC1_ELEV_M:  # temp increasing with height = inversion
                if inv_base_m is None:
                    inv_base_m = prev_h
                dt_str = f'  *** INVERSION ({lapse:+.1f}°C/km)'
            else:
                dt_str = f'  ({-lapse:+.1f}°C/km lapse)'
        print(f'{lv:>12d}  {h_m:>8.0f}  {t_c:>10.1f}  {dt_str}')
        prev_t, prev_h = t_c, h_m
    except Exception as e:
        print(f'{lv:>12d}  fetch failed: {e}')

print()
if inv_base_m:
    print(f'Inversion base estimate: ~{inv_base_m:.0f}m')
    print(f'  700 hPa at ~{hrrr_results.get(("12",700,"KNXC1"),{}).get("hgt","?"):.0f}m '
          f'→ {"ABOVE" if hrrr_results.get(("12",700,"KNXC1"),{}).get("hgt",0)>inv_base_m else "BELOW"} inversion')
    print(f'  850 hPa at ~{hrrr_results.get(("12",850,"KNXC1"),{}).get("hgt","?"):.0f}m '
          f'→ {"ABOVE" if hrrr_results.get(("12",850,"KNXC1"),{}).get("hgt",0)>inv_base_m else "BELOW"} inversion')
    print(f'  KNXC1 station at {KNXC1_ELEV_M:.0f}m '
          f'→ {"ABOVE" if KNXC1_ELEV_M>inv_base_m else "BELOW"} inversion')
else:
    print('No clear inversion layer detected in profile.')

# ─── 3. KNXC1 RAWS Oct 27 ─────────────────────────────────────────────────
print()
print('='*70)
print('KNXC1 RAWS observed — Oct 27 2019 (UTC)')
print('='*70)

fpath = f'{RAWS_DIR}/KNXC1_kincade_run_2019.csv'
if not os.path.exists(fpath):
    fpath = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\kincade_run_2019\KNXC1_kincade_run_2019.csv'

print(f'{"Time(UTC)":22s}  {"Spd(mph)":>9s}  {"Dir(°)":>7s}  {"Gust(mph)":>10s}')
print('-'*55)
obs_dirs = []
with open(fpath, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        t = row['datetime_utc']
        if '2019-10-27' not in t:
            continue
        try:
            spd  = float(row.get('wind_speed_mph') or 0)
            dirn = float(row.get('wind_dir_deg') or 0)
            gust = float(row.get('wind_gust_mph') or 0)
            print(f'{t:22s}  {spd:>9.1f}  {dirn:>7.0f}  {gust:>10.1f}')
            if spd > 5:
                obs_dirs.append(dirn)
        except:
            pass

if obs_dirs:
    # Vector-average direction
    us = [math.cos(math.radians(d)) for d in obs_dirs]
    vs = [math.sin(math.radians(d)) for d in obs_dirs]
    mean_dir = math.degrees(math.atan2(sum(vs)/len(vs), sum(us)/len(us))) % 360
    print(f'\nVector-mean obs direction (spd>5mph): {mean_dir:.0f}°')

# ─── 4. BC matching analysis ────────────────────────────────────────────────
print()
print('='*70)
print('BC DIRECTION MATCH — which (level, hour) aligns with observed NNE flow?')
print('Observed mean direction at KNXC1 (spd>5): '
      f'{mean_dir:.0f}° (target: within ±30° of ~20–40°)')
print('='*70)
print(f'{"Hour":6s}  {"Level":6s}  {"HRRR_dir":>9s}  {"OBS_dir":>8s}  '
      f'{"Delta":>7s}  {"Match?":>8s}  {"Spd(mph)"}')
print('-'*65)

TARGET_DIR = mean_dir  # use actual observed mean

best_match = None
best_delta = 999

for hz in ['00','06','12','18']:
    for level in LEVELS:
        r = hrrr_results.get((hz, level, 'KNXC1'), {})
        if not r:
            continue
        hdir = r['dir']
        delta = abs(ang_diff(hdir, TARGET_DIR))
        match = 'GOOD' if delta <= 30 else ('MARGINAL' if delta <= 60 else 'POOR')
        flag = ' ***' if delta <= 30 else ''
        print(f'{hz+"Z":6s}  {level:6d}  {hdir:>9.1f}  {TARGET_DIR:>8.1f}  '
              f'{delta:>7.1f}  {match:>8s}  {r["spd"]:.1f}{flag}')
        if delta < best_delta:
            best_delta = delta
            best_match = (hz, level, hdir, r['spd'])

print()
if best_match:
    hz, lv, hdir, spd = best_match
    print(f'Best match: {hz}Z / {lv} hPa — HRRR dir={hdir:.0f}° '
          f'vs obs {TARGET_DIR:.0f}° (Δ={best_delta:.0f}°)  spd={spd:.1f}mph')
print()
print('STAGE 1 COMPLETE — do not run Stage 2 until BC choice is confirmed.')
