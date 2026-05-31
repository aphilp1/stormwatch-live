"""
thomas_bc_diagnose.py  —  STAGE 1 ONLY
Diagnose the correct BC for Thomas Fire (Dec 4-5, 2017).

Problem: current BC (700 hPa 13Z 2017-12-05 @ bc_center 34.58N -118.7W)
gives 81° (ESE) but WMSC1 observed 38° (NNE) — delta=43°, fails 30° threshold.
WTPC1 observed 347° (NNW) — delta=94°, terrain-deflected, likely out-of-scope.

Goal: find (level, hour, grid_point) with BC dir within 30° of WMSC1 ~38°.

Prints:
1. WMSC1 + WTPC1 observed directions on Dec 5 (hourly context)
2. HRRR 700/850/925 hPa winds at multiple grid points, multiple hours Dec 4-5
3. Best-match table with delta vs WMSC1 observed
4. Temperature profile at bc_center → inversion height (12Z Dec 5)

NO scoring, NO WN runs, NO writes to master status.
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

RAWS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\thomas_2017'

# Stations
WMSC1_LAT, WMSC1_LON = 34.595830, -118.578600   # Warm Springs
WTPC1_LAT, WTPC1_LON = 34.569380, -118.740100   # Whitaker Peak
CUUC1_LAT, CUUC1_LON = 34.568060, -119.013900   # Chuchupate (4900 ft, near lid)
ROVC1_LAT, ROVC1_LON = 34.498040, -118.882010   # Rose Valley II (3336 ft, sub-inv)

# Grid points to check for BC
GRID_POINTS = {
    'bc_current':  (34.58, -118.70),   # existing bc_center (problematic)
    'wmsc1_cell':  (34.60, -118.58),   # at WMSC1 directly
    'upstream_E':  (34.50, -118.00),   # upstream over San Gabriels/desert edge
    'high_desert': (34.50, -117.50),   # high desert, upstream source region
    'mojave_N':    (34.80, -117.80),   # north Mojave, source region
}

LEVELS = [700, 850, 925]
HOURS  = [
    '2017-12-04 00:00', '2017-12-04 06:00',
    '2017-12-04 12:00', '2017-12-04 18:00',
    '2017-12-05 00:00', '2017-12-05 06:00',
    '2017-12-05 12:00',
]

def wind_from_uv(u, v):
    spd  = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def nearest_val(ds, var, lat, lon):
    lats = ds['latitude'].values
    lons = ds['longitude'].values % 360
    dist = np.sqrt((lats - lat)**2 + (lons - lon % 360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def vec_mean_dir(dirs_and_speeds):
    """Vector-average direction; dirs_and_speeds = list of (dir_deg, speed)."""
    us = [s * math.cos(math.radians(d)) for d, s in dirs_and_speeds]
    vs = [s * math.sin(math.radians(d)) for d, s in dirs_and_speeds]
    return math.degrees(math.atan2(sum(vs)/len(vs), sum(us)/len(us))) % 360

# ─── 1. WMSC1 + WTPC1 observed context ────────────────────────────────────────
print('='*72)
print('OBSERVED CONTEXT — WMSC1 (Warm Springs) and WTPC1 (Whitaker Peak)')
print('Dec 5 2017 UTC — primary scoring window highlighted')
print('='*72)
print(f'{"Time(UTC)":22s}  {"WMSC1_spd":>9s}  {"WMSC1_dir":>9s}  {"WMSC1_gust":>10s}  '
      f'{"WTPC1_spd":>9s}  {"WTPC1_dir":>9s}  {"WTPC1_gust":>10s}')
print('-'*90)

wm_data, wt_data = {}, {}
for stid, fpath, store in [
    ('WMSC1', f'{RAWS_DIR}/WMSC1_thomas_2017.csv', wm_data),
    ('WTPC1', f'{RAWS_DIR}/WTPC1_thomas_2017.csv', wt_data),
]:
    with open(fpath, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t = row['datetime_utc']
            if '2017-12-05' not in t:
                continue
            try:
                store[t[:16]] = {
                    'spd':  float(row.get('wind_speed_mph') or 0),
                    'dir':  float(row.get('wind_dir_deg') or 0),
                    'gust': float(row.get('wind_gust_mph') or 0),
                }
            except: pass

all_times = sorted(set(list(wm_data.keys()) + list(wt_data.keys())))
for t in all_times:
    wm = wm_data.get(t, {})
    wt = wt_data.get(t, {})
    flag = ' <-- PEAK' if t >= '2017-12-05T10' and t <= '2017-12-05T14' else ''
    ws = wm.get('spd', 0); wd = wm.get('dir', 0); wg = wm.get('gust', 0)
    ts = wt.get('spd', 0); td = wt.get('dir', 0); tg = wt.get('gust', 0)
    print(f'{t:22s}  {ws:>9.1f}  {wd:>9.0f}  {wg:>10.1f}  '
          f'{ts:>9.1f}  {td:>9.0f}  {tg:>10.1f}{flag}')

# Vector-mean of WMSC1 obs in peak window (10-14Z Dec 5)
peak_wm = [(v['dir'], v['spd']) for t, v in wm_data.items()
           if '2017-12-05T10' <= t <= '2017-12-05T14' and v['spd'] > 5]
peak_wt = [(v['dir'], v['spd']) for t, v in wt_data.items()
           if '2017-12-05T10' <= t <= '2017-12-05T14' and v['spd'] > 5]
wmsc1_target = round(vec_mean_dir(peak_wm), 0) if peak_wm else None
wtpc1_target = round(vec_mean_dir(peak_wt), 0) if peak_wt else None
print(f'\nVector-mean 10-14Z Dec 5:  WMSC1={wmsc1_target:.0f}°  WTPC1={wtpc1_target:.0f}°')

# ─── 2. HRRR pressure-level wind sweep ─────────────────────────────────────────
print()
print('='*72)
print('HRRR PRESSURE-LEVEL WIND SWEEP')
print(f'Target: WMSC1 vector-mean = {wmsc1_target:.0f}° (need BC within ±30°)')
print(f'Checking levels={LEVELS}, hours={len(HOURS)}, grid_points={len(GRID_POINTS)}')
print('='*72)

results = []   # (delta, hour, level, gp_name, bc_spd, bc_dir, gp_lat, gp_lon)

for hrrr_time in HOURS:
    hz = hrrr_time[11:13]
    print(f'\n--- {hrrr_time} ---')
    try:
        H = Herbie(hrrr_time, model='hrrr', product='prs', fxx=0)
    except Exception as e:
        print(f'  Herbie fetch failed: {e}'); continue

    for level in LEVELS:
        try:
            ds_u = H.xarray(f'UGRD:{level} mb')
            ds_v = H.xarray(f'VGRD:{level} mb')
            try:
                ds_h = H.xarray(f'HGT:{level} mb')
                has_hgt = True
            except:
                has_hgt = False

            for gp_name, (gp_lat, gp_lon) in GRID_POINTS.items():
                u = nearest_val(ds_u, 'u', gp_lat, gp_lon)
                v = nearest_val(ds_v, 'v', gp_lat, gp_lon)
                spd, dirn = wind_from_uv(u, v)
                hgt = round(nearest_val(ds_h, 'gh', gp_lat, gp_lon), 0) if has_hgt else '?'
                delta = ang_diff(dirn, wmsc1_target)
                match = 'GOOD' if delta <= 30 else ('MARGINAL' if delta <= 60 else 'POOR')
                flag  = ' ***' if delta <= 30 else ''
                print(f'  {level}hPa {hz}Z  {gp_name:14s}  {spd:>6.1f}mph @ {dirn:>5.1f}°  '
                      f'hgt={hgt}m  Δ={delta:.0f}°  {match}{flag}')
                results.append((delta, hrrr_time, level, gp_name, spd, dirn, gp_lat, gp_lon))
        except Exception as e:
            print(f'  Level {level} failed: {e}')

# ─── 3. Best-match summary ─────────────────────────────────────────────────────
print()
print('='*72)
print('BEST MATCHES (sorted by Δ vs WMSC1)')
print(f'Target direction: WMSC1 = {wmsc1_target:.0f}°  |  Pass threshold: ≤30°')
print('='*72)
print(f'{"Δ°":>5s}  {"Hour":16s}  {"Level":>6s}  {"Grid point":14s}  '
      f'{"Spd(mph)":>9s}  {"Dir(°)":>7s}')
print('-'*65)
for delta, hrrr_time, level, gp_name, spd, dirn, gp_lat, gp_lon in sorted(results)[:20]:
    flag = ' ***' if delta <= 30 else ''
    print(f'{delta:>5.0f}  {hrrr_time:16s}  {level:>6d}  {gp_name:14s}  '
          f'{spd:>9.1f}  {dirn:>7.1f}{flag}')

# ─── 4. Temperature profile → inversion height (12Z Dec 5 at bc_current) ──────
print()
print('='*72)
print('TEMPERATURE PROFILE AT bc_current (34.58N, -118.7W) — 12Z Dec 5 2017')
print('Purpose: identify inversion height to verify level choice')
print('='*72)

lat_bc, lon_bc = GRID_POINTS['bc_current']
try:
    H12 = Herbie('2017-12-05 12:00', model='hrrr', product='prs', fxx=0)
    TEMP_LEVELS = [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 725, 700]
    print(f'{"Level(hPa)":>12s}  {"HGT(m)":>8s}  {"Temp(°C)":>10s}  Notes')
    print('-'*55)
    prev_t, prev_h = None, None
    inv_base_m = None

    for lv in TEMP_LEVELS:
        try:
            ds_t = H12.xarray(f'TMP:{lv} mb')
            ds_h = H12.xarray(f'HGT:{lv} mb')
            t_k  = nearest_val(ds_t, 't', lat_bc, lon_bc)
            h_m  = nearest_val(ds_h, 'gh', lat_bc, lon_bc)
            t_c  = round(t_k - 273.15, 1)
            note = ''
            if prev_t is not None and prev_h is not None:
                dt = t_c - prev_t
                dh = h_m - prev_h
                lapse = -dt / (dh / 1000) if dh != 0 else 0
                if dt > 0:
                    if inv_base_m is None:
                        inv_base_m = prev_h
                    note = f'INVERSION ({lapse:+.1f}°C/km)'
                else:
                    note = f'{-lapse:+.1f}°C/km'
            print(f'{lv:>12d}  {h_m:>8.0f}  {t_c:>10.1f}  {note}')
            prev_t, prev_h = t_c, h_m
        except Exception as e:
            print(f'{lv:>12d}  fetch failed: {e}')

    print()
    if inv_base_m:
        print(f'Inversion base: ~{inv_base_m:.0f}m')
        # check levels
        for lv in [700, 850, 925]:
            r = next(((delta, hrrr_time, level, gp_name, spd, dirn, gp_lat, gp_lon)
                      for delta, hrrr_time, level, gp_name, spd, dirn, gp_lat, gp_lon in results
                      if level == lv and hrrr_time == '2017-12-05 12:00'
                      and gp_name == 'bc_current'), None)
            if r:
                print(f'  {lv} hPa @ bc_current 12Z: dir={r[5]:.0f}°  Δ={r[0]:.0f}°')
    else:
        print('No inversion detected at bc_current 12Z.')
except Exception as e:
    print(f'Temperature profile failed: {e}')

# ─── 5. Also check WTPC1 vs best BC ───────────────────────────────────────────
print()
print('='*72)
print('WTPC1 DIRECTION CHECK (terrain-deflection assessment)')
print(f'WTPC1 observed vector-mean 10-14Z: {wtpc1_target:.0f}°')
print(f'WMSC1 observed vector-mean 10-14Z: {wmsc1_target:.0f}°')
print(f'Angular separation between stations: {ang_diff(wmsc1_target, wtpc1_target):.0f}°')
print()
print('Top 5 BC candidates vs WTPC1:')
results_vs_wt = [(ang_diff(dirn, wtpc1_target), hrrr_time, level, gp_name, spd, dirn)
                 for delta, hrrr_time, level, gp_name, spd, dirn, gp_lat, gp_lon in results]
for delta_wt, hrrr_time, level, gp_name, spd, dirn in sorted(results_vs_wt)[:5]:
    delta_wm = next(d for d, ht, lv, gp, s, di, glat, glon in results
                    if ht == hrrr_time and lv == level and gp == gp_name)
    print(f'  {level}hPa {hrrr_time[11:13]}Z {gp_name:14s}: dir={dirn:.0f}°  '
          f'Δ_WMSC1={delta_wm:.0f}°  Δ_WTPC1={delta_wt:.0f}°')
print()
print('If Δ_WMSC1 + Δ_WTPC1 >> 30° for ALL candidates, WTPC1 is terrain-deflected')
print('and should be excluded from scoring (same logic as Jarbo exclusion).')

print()
print('STAGE 1 COMPLETE — do not run Stage 2 until BC choice is confirmed.')
