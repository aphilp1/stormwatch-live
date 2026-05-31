"""
kincade_step0.py  —  STEP 0: rank Kincade run ridge candidates
For each usable station (not HWKC1/KNXC1/RSAC1 which are already resolved):
  - Registry elevation (ft, m)
  - DEM elevation + diff at coords (existing DEMs only; flag NEED_DEM if missing/edge)
  - Peak sustained wind + hour (full Oct 26-28 window)
  - Vector-mean direction + R (steadiness, all obs spd >= 10 mph, Oct 26-28)
  - Peak-hour obs: gust, sustained, direction (what scoring would see)

Pre-registered Kincade BC: 850 hPa, 12Z 2019-10-27
BC at bc_center (38.86, -122.42) = 44.7 mph @ 42 deg (pre-registered from stage2.py)
For a candidate to qualify at Step 0:
  - DEM elevation check within +-50m (or flag NEED_DEM)
  - Obs peak sustained >= 15 mph
  - Direction R >= 0.70 (mostly steady)
  - BC dir 42 deg within 30 deg of station peak-window observed direction
"""

import sys, os, math, csv, glob as _glob
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

os.environ['PATH'] = (
    r'C:\Users\aphil\miniforge3\envs\hrrr311' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\mingw-w64\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Scripts' + os.pathsep +
    os.environ.get('PATH', '')
)

from PIL import Image
from pyproj import Transformer, CRS

RAWS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\kincade_run_2019'
CACHE    = r'C:\temp\windninja_cache'
GF_CSV   = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\raws_gust_factors.csv'

# Pre-registered BC direction for direction-match check
BC_DIR = 42.0    # 850 hPa 12Z Oct 27 at KNXC1 bc_center

# Already-resolved stations — skip
SKIP = {'HWKC1', 'KNXC1', 'RSAC1'}

REGISTRY = {
    'ATLC1': (38.474850, -122.264800, 1934.0, 589.5,  'Atlas Peak'),
    'COWC1': (39.125830, -123.073330, 3355.0, 1022.6, 'Lyons Valley'),
    'HGLC1': (39.208900, -122.809990, 4807.0, 1465.2, 'High Glade Lookout'),
    'HPDC1': (39.030830, -123.080560, 2682.0, 817.5,  'Hopland UC'),
    'KELC1': (38.911890, -122.706310, 2163.0, 659.3,  'Konocti'),
    'OAAC1': (38.738060, -123.308390, 1890.0, 576.1,  'Oak Ridge'),
    'TR164': (39.124420, -122.771500, 3600.0, 1097.3, 'MNF02 Portable'),
    'TS379': (39.124420, -122.771500, 3600.0, 1097.3, 'MNF04 Portable'),
    'WISC1': (39.018830, -122.411690, 2085.0, 635.5,  'County Line'),
}

# Available DEMs (NorCal area) — assessed from cache
DEMS = [
    (r'C:\temp\windninja_cache\dem_38.7_-122.75_16mi.tif', 'EPSG:4326'),
    (r'C:\temp\windninja_cache\dem_38.9_-122.4_8mi_utm.tif', 'auto'),
]

def load_dem(path):
    img = Image.open(path)
    t   = img.tag_v2
    Sx  = float(t[33550][0]); Sy = float(t[33550][1])
    x0  = float(t[33922][3]); y0 = float(t[33922][4])
    geo = str(t.get(34737, ''))
    arr = np.array(img, dtype=float)
    for nd in [-9999, 9999]:
        arr[np.abs(arr - nd) < 1] = np.nan
    if abs(x0) < 360:
        epsg = 4326
    elif 'zone 10N' in geo:
        epsg = 32610
    elif 'zone 11N' in geo:
        epsg = 32611
    else:
        epsg = 32610
    return arr, Sx, Sy, x0, y0, epsg, *img.size

def dem_lookup(arr, Sx, Sy, x0, y0, epsg, ncols, nrows, lat, lon):
    if epsg == 4326:
        col = (lon - x0) / Sx; row = (y0 - lat) / Sy
    else:
        tf = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
        x, y = tf.transform(lon, lat)
        col = (x - x0) / Sx; row = (y0 - y) / Sy
    ci = int(round(col)); ri = int(round(row))
    in_bounds = 0 <= ci < ncols and 0 <= ri < nrows
    ci = max(0, min(ci, ncols-1)); ri = max(0, min(ri, nrows-1))
    elev = float(arr[ri, ci]) if not np.isnan(arr[ri, ci]) else None
    px_m = Sx if epsg != 4326 else Sx * 111000 * math.cos(math.radians(lat))
    margin_km = min(ri, nrows-1-ri, ci, ncols-1-ci) * px_m / 1000
    return elev, margin_km, in_bounds

def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def vec_stats(dirs_speeds):
    if not dirs_speeds: return None, None, 0
    us = [s * math.cos(math.radians(d)) for d, s in dirs_speeds]
    vs = [s * math.sin(math.radians(d)) for d, s in dirs_speeds]
    mu = sum(us)/len(us); mv = sum(vs)/len(vs)
    R  = math.sqrt(mu**2 + mv**2)
    mean_dir = math.degrees(math.atan2(mv, mu)) % 360
    return round(mean_dir, 0), round(R, 3), len(dirs_speeds)

# Load all DEMs once
loaded_dems = []
for dem_path, _ in DEMS:
    if os.path.exists(dem_path):
        loaded_dems.append(load_dem(dem_path))

# Load gust factors
gf_lookup = {}
for row in csv.DictReader(open(GF_CSV, encoding='utf-8')):
    if row['event'] == 'kincade_run_2019':
        gf_lookup[row['stid']] = {
            'n': row['n_window_pairs'],
            'peak_gust': row['peak_gust_mph'],
            'peak_time': row['peak_gust_time'],
            'peak_sus':  row['peak_spd_concurrent'],
            'peak_gf':   row['peak_gust_factor'],
            'med_gf':    row['median_gust_factor'],
            'status':    row['status'],
            'flags':     row.get('flags',''),
        }

# ─── Per-station analysis ──────────────────────────────────────────────────────
results = []

for stid, (lat, lon, reg_ft, reg_m, name) in REGISTRY.items():
    if stid in SKIP:
        continue

    # DEM check
    dem_elev = dem_diff = dem_margin = None
    dem_status = 'NEED_DEM'
    for dem_data in loaded_dems:
        arr, Sx, Sy, x0, y0, epsg, ncols, nrows = dem_data
        elev, margin, in_b = dem_lookup(arr, Sx, Sy, x0, y0, epsg, ncols, nrows, lat, lon)
        if elev is None or not in_b:
            continue
        if margin < 2.0:
            dem_status = f'EDGE({margin:.1f}km)'
            dem_elev = elev; dem_diff = elev - reg_m; dem_margin = margin
        elif abs(elev - reg_m) <= 50:
            dem_status = f'OK({margin:.1f}km)'
            dem_elev = elev; dem_diff = elev - reg_m; dem_margin = margin
            break
        else:
            # Mismatch but in bounds — record it
            dem_status = f'MISMATCH({elev-reg_m:+.0f}m,{margin:.1f}km)'
            dem_elev = elev; dem_diff = elev - reg_m; dem_margin = margin

    # RAWS obs — Oct 26-28 2019
    fpath = os.path.join(RAWS_DIR, f'{stid}_kincade_run_2019.csv')
    if not os.path.exists(fpath):
        results.append({'stid':stid,'name':name,'reg_ft':reg_ft,'reg_m':reg_m,
                        'dem_status':dem_status,'dem_elev':dem_elev,'dem_diff':dem_diff,
                        'skip_reason':'NO_CSV'})
        continue

    rows_all = list(csv.DictReader(open(fpath, encoding='utf-8')))
    event_obs = []
    for r in rows_all:
        t = r['datetime_utc']
        if not ('2019-10-26' <= t[:10] <= '2019-10-28'):
            continue
        try:
            spd  = float(r.get('wind_speed_mph') or 0)
            dirn = float(r.get('wind_dir_deg') or 0)
            gust = float(r.get('wind_gust_mph') or 0)
            event_obs.append((t, spd, dirn, gust))
        except: pass

    if not event_obs:
        results.append({'stid':stid,'name':name,'reg_ft':reg_ft,'reg_m':reg_m,
                        'dem_status':dem_status,'dem_elev':dem_elev,'dem_diff':dem_diff,
                        'skip_reason':'NO_OBS'})
        continue

    # Peak sustained
    peak_row = max(event_obs, key=lambda x: x[1])
    peak_time, peak_spd, peak_dir, peak_gust = peak_row
    peak_gf_obs = round(peak_gust/peak_spd, 3) if peak_spd > 0 else None

    # Oct 27 window (the destructive run)
    oct27_obs = [(t,s,d,g) for t,s,d,g in event_obs if '2019-10-27' in t]
    peak_oct27 = max(oct27_obs, key=lambda x:x[1]) if oct27_obs else None

    # Direction stats — all spd >= 10 mph, Oct 26-28
    steady_obs = [(d, s) for _, s, d, _ in event_obs if s >= 10 and d > 0]
    vmean, R, n_steady = vec_stats(steady_obs)

    # Oct 27 12Z window specifically (matching pre-registered BC hour)
    oct27_12z = [(t,s,d,g) for t,s,d,g in event_obs
                 if t.startswith('2019-10-27T12')]
    best_12z = max(oct27_12z, key=lambda x:x[3]) if oct27_12z else None

    # Direction check vs pre-registered BC (42 deg)
    delta_bc = ang_diff(BC_DIR, vmean) if vmean is not None else None
    delta_bc_12z = ang_diff(BC_DIR, best_12z[2]) if best_12z and best_12z[2] > 0 else None

    # GF from registry
    gf = gf_lookup.get(stid, {})

    results.append({
        'stid': stid, 'name': name, 'reg_ft': reg_ft, 'reg_m': reg_m,
        'dem_status': dem_status, 'dem_elev': dem_elev, 'dem_diff': dem_diff,
        'peak_spd': peak_spd, 'peak_time': peak_time, 'peak_dir': peak_dir,
        'peak_gust': peak_gust, 'peak_gf_obs': peak_gf_obs,
        'peak_oct27': peak_oct27,
        'vmean': vmean, 'R': R, 'n_steady': n_steady,
        'delta_bc': delta_bc,
        'best_12z': best_12z, 'delta_bc_12z': delta_bc_12z,
        'gf': gf,
        'skip_reason': None,
    })

# ─── Sort by R desc, then elevation desc ──────────────────────────────────────
valid = [r for r in results if r.get('skip_reason') is None and r.get('R') is not None]
valid.sort(key=lambda r: (-(r['R'] or 0), -(r['reg_ft'] or 0)))
invalid = [r for r in results if r.get('skip_reason') or r.get('R') is None]

print('='*75)
print('KINCADE RUN 2019 — STEP 0: RIDGE CANDIDATE RANKING')
print(f'Pre-registered BC: 850 hPa 12Z 2019-10-27  BC_dir={BC_DIR:.0f}°')
print(f'Qualification: DEM OK, peak_sus≥15mph, R≥0.70, BC_dir delta≤30°')
print('='*75)

COLS = (f'{"STID":6s}  {"Name":22s}  {"RegFt":>6s}  {"RegM":>5s}  '
        f'{"DEM status":20s}  {"PeakSus":>7s}  {"PeakHr":>13s}  '
        f'{"PeakDir":>7s}  {"R":>5s}  {"n":>4s}  {"Δ_BC(all)":>9s}  {"12Z_gust":>8s}  {"Δ_BC(12Z)":>9s}')
print(COLS)
print('-'*len(COLS))

for r in valid + invalid:
    if r.get('skip_reason'):
        print(f'  {r["stid"]:6s}  {r["name"]:22s}  SKIP: {r["skip_reason"]}')
        continue

    dem_s  = r['dem_status'][:20]
    pk_spd = f'{r["peak_spd"]:.1f}' if r['peak_spd'] else '--'
    pk_hr  = r['peak_time'][11:16] if r['peak_time'] else '--'
    pk_day = r['peak_time'][8:10]  if r['peak_time'] else '--'
    pk_dir = f'{r["peak_dir"]:.0f}°' if r['peak_dir'] else '--'
    R_s    = f'{r["R"]:.3f}' if r['R'] else '--'
    n_s    = f'{r["n_steady"]}' if r['n_steady'] else '--'
    d_bc   = f'{r["delta_bc"]:.0f}°' if r['delta_bc'] is not None else '--'
    g12z   = f'{r["best_12z"][3]:.1f}' if r['best_12z'] else '--'
    d12z   = f'{r["delta_bc_12z"]:.0f}°' if r['delta_bc_12z'] is not None else '--'

    # Gate flags
    gates = []
    if 'NEED_DEM' in r['dem_status'] or 'EDGE' in r['dem_status']:
        gates.append('NEED_DEM')
    if (r['peak_spd'] or 0) < 15:
        gates.append('LOW_SPD')
    if (r['R'] or 0) < 0.70:
        gates.append('UNSTEADY')
    if r['delta_bc'] is not None and r['delta_bc'] > 30:
        gates.append(f'BC_DIR_ΔALL={r["delta_bc"]:.0f}°')
    gate_s = ' '.join(gates) if gates else 'PASS_ALL'

    print(f'  {r["stid"]:6s}  {r["name"]:22s}  {r["reg_ft"]:>6.0f}  {r["reg_m"]:>5.0f}  '
          f'{dem_s:20s}  {pk_spd:>7s}  {pk_day}T{pk_hr}Z  '
          f'{pk_dir:>7s}  {R_s:>5s}  {n_s:>4s}  {d_bc:>9s}  {g12z:>8s}  {d12z:>9s}  {gate_s}')

# ─── Detailed view of top 3 candidates ────────────────────────────────────────
print()
print('='*75)
print('TOP CANDIDATES — Oct 27 hourly detail (peak event day)')
print('='*75)
for r in valid[:4]:
    stid = r['stid']
    fpath = os.path.join(RAWS_DIR, f'{stid}_kincade_run_2019.csv')
    rows_all = list(csv.DictReader(open(fpath, encoding='utf-8')))
    print(f'\n{stid} ({r["name"]}, {r["reg_ft"]:.0f}ft, R={r["R"]:.3f}):')
    print(f'  {"Time(UTC)":16s}  {"Spd":>5s}  {"Dir":>5s}  {"Gust":>6s}')
    print('  ' + '-'*36)
    for row in rows_all:
        t = row['datetime_utc']
        if '2019-10-27' not in t: continue
        try:
            spd  = float(row.get('wind_speed_mph') or 0)
            dirn = float(row.get('wind_dir_deg') or 0)
            gust = float(row.get('wind_gust_mph') or 0)
            flag = ' <--12Z' if t.startswith('2019-10-27T12') else ''
            print(f'  {t[:16]:16s}  {spd:>5.1f}  {dirn:>5.0f}°  {gust:>6.1f}{flag}')
        except: pass

# ─── GF summary for valid candidates ──────────────────────────────────────────
print()
print('='*75)
print('GUST FACTORS (kincade_run_2019, own empirical)')
print('='*75)
print(f'  {"STID":6s}  {"n":>4s}  {"PeakGust":>9s}  {"PeakSus":>8s}  '
      f'{"PeakGF":>7s}  {"MedGF":>7s}  {"Status":8s}  Flags')
print('-'*70)
for r in valid[:6]:
    gf = r['gf']
    if gf:
        print(f'  {r["stid"]:6s}  {gf["n"]:>4s}  {gf["peak_gust"]:>9s}  '
              f'{gf["peak_sus"]:>8s}  {gf["peak_gf"]:>7s}  {gf["med_gf"]:>7s}  '
              f'{gf["status"]:8s}  {gf["flags"][:40]}')
    else:
        print(f'  {r["stid"]:6s}  NOT IN raws_gust_factors.csv')

print()
print('─'*75)
print('RECOMMENDATION:')
if valid:
    top = valid[0]
    gates_top = []
    if 'NEED_DEM' in top['dem_status'] or 'EDGE' in top['dem_status']:
        gates_top.append('needs new DEM')
    if (top['peak_spd'] or 0) < 15: gates_top.append('low speed')
    if (top['R'] or 0) < 0.70: gates_top.append('unsteady')
    if top['delta_bc'] is not None and top['delta_bc'] > 30:
        gates_top.append(f'BC dir Δ={top["delta_bc"]:.0f}°')
    gate_note = f' — BLOCKERS: {", ".join(gates_top)}' if gates_top else ' — all gates PASS'
    print(f'  Top candidate: {top["stid"]} ({top["name"]}, {top["reg_ft"]:.0f}ft, R={top["R"]:.3f}){gate_note}')
    for r in valid[1:3]:
        print(f'  Runner-up:     {r["stid"]} ({r["name"]}, {r["reg_ft"]:.0f}ft, R={r["R"]:.3f})')
