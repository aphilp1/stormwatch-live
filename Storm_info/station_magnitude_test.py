#!/usr/bin/env python3
"""
station_magnitude_test.py — Phase B Steps 2+3
==============================================
Apply station_deficit = (1 - coupling_ratio) * bc_aligned as UP correction
magnitude (Step 2), then re-run four-anchor WN battery (Step 3).

Gate passed: station_deficit r=-0.665, LOEO RMSE 9.89 vs baseline 12.93.

Rules:
  Direction:  inner rule unchanged (0fabff7) — UP if (relief>330 AND slope>10) OR (cr>1.08)
  Magnitude:  UP anchors: bc = bc_raw + (1-cr)*bc_raw  [station-specific]
              DOWN anchors: bc = bc_raw + outer_LOO_delta  [event-level, unchanged]

New WN runs needed: WMSC1/thomas bc=51@58, WMSC1/woolsey bc=61@64.
All other anchors: station_mag = two_level (same bc → reuse cached WN outputs).

Pass condition (from handoff):
  WMSC1/thomas moves from +10.5 toward obs (needed +15.3 mph).
  WMSC1/woolsey protected — near-untouched.
  Net vs raw: ≥ 3 improved/neutral across four anchors.

Run:    conda run -n hrrr311 python station_magnitude_test.py
Output: C:\temp\station_mag_log.txt

NOTE: Flag: woolsey has cr=0.456 (not cr≈1 as assumed in handoff).
  station_deficit = 21.4 mph vs needed = 5.7 mph.
  Expected result: woolsey degraded; thomas slightly worse than event-mag.
  Running to confirm with actual WN numbers.
"""

import glob, math, os, subprocess, sys
import numpy as np

LOG = open(r'C:\temp\station_mag_log.txt', 'w', encoding='utf-8')
sys.stdout = LOG

WN_CLI = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE  = r'C:\temp\windninja_cache'

# ── Prior results from two_level_log.txt (hardcoded to avoid re-running all WN) ──
# WN_err = WN_output - obs; WN_output = obs + WN_err
# Format: (bc_speed_used, WN_output_mph)
PRIOR = {
    'CBXC1/camp_2018': {
        'obs': 28.99,
        'raw':  (32.93, 35.4),    # WN_err=+6.4
        'flat': (16.60, 18.2),    # WN_err=-10.8
        '2lev': (16.60, 18.2),    # =flat (inner sign agrees with outer DOWN)
    },
    'WMSC1/thomas_2017': {
        'obs': 45.99,
        'raw':  (30.67, 35.8),    # WN_err=-10.2
        'flat': (11.91, 13.9),    # WN_err=-32.1
        '2lev': (49.43, 56.5),    # WN_err=+10.5 ← the validated improvement
    },
    'WMSC1/woolsey_2018': {
        'obs': 44.98,
        'raw':  (39.32, 45.0),    # WN_err=-0.0
        'flat': (47.08, 54.2),    # WN_err=+9.2
        '2lev': (47.08, 54.2),    # =flat (outer=UP, inner=UP, same direction)
    },
    'PNTM8/missoula_dec2025': {
        'obs': 46.06,
        'raw':  (84.18, 126.3),   # WN_err=+80.2
        'flat': (53.36, 79.7),    # WN_err=+33.6
        '2lev': (53.36, 79.7),    # =flat (DOWN, inner agrees)
    },
}

# ── Anchor definitions (from two_level_wn_test.py exact values) ──────────────
ANCHORS = [
    {
        'key': 'CBXC1/camp_2018',
        'label': 'CBXC1 / camp_2018   (coupled offshore)',
        'lat': 40.14564, 'lon': -121.5225,
        'dem': 'dem_40.0_-121.3_20mi.tif',
        'bc_raw': 32.93, 'bc_dir': 85.8,
        'coupling_ratio': 0.7704,
        'relief_1km': 223.6, 'slope': 5.96,
        'outer_loo_delta': -16.33,
        'inner_sign': -1,   # DOWN: terrain=NO, coupling=NO
    },
    {
        'key': 'WMSC1/thomas_2017',
        'label': 'WMSC1 / thomas_2017  (UP, terrain arm, KEY CASE)',
        'lat': 34.59583, 'lon': -118.57861,
        'dem': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'bc_raw': 30.67, 'bc_dir': 58.0,
        'coupling_ratio': 0.3371,
        'relief_1km': 505.9, 'slope': 33.97,
        'outer_loo_delta': -18.76,
        'inner_sign': +1,   # UP: terrain=YES (relief>330 AND slope>10)
    },
    {
        'key': 'WMSC1/woolsey_2018',
        'label': 'WMSC1 / woolsey_2018  (UP, terrain arm)',
        'lat': 34.59583, 'lon': -118.57861,
        'dem': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'bc_raw': 39.32, 'bc_dir': 63.6,
        'coupling_ratio': 0.4564,
        'relief_1km': 506.8, 'slope': 47.63,
        'outer_loo_delta': +7.76,
        'inner_sign': +1,   # UP: terrain=YES
    },
    {
        'key': 'PNTM8/missoula_dec2025',
        'label': 'PNTM8 / missoula_dec2025  (continental downslope)',
        'lat': 47.04136, 'lon': -113.98631,
        'dem': 'dem_47.0_-114.0_8mi.tif',
        'bc_raw': 84.18, 'bc_dir': 275.4,
        'coupling_ratio': None,  # continental, not in profile
        'relief_1km': 500.4, 'slope': 9.44,
        'outer_loo_delta': -30.82,
        'inner_sign': -1,   # DOWN: terrain=NO (slope<10), coupling=N/A
    },
]


# ── WN runner (identical to two_level_wn_test.py) ──────────────────────────────

def run_wn(dem_stem, dem_path, spd_int, dir_int):
    cached_vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
        return cached_vel[0], (cached_ang[0] if cached_ang else None)
    args = [
        WN_CLI, '--num_threads', '6',
        '--elevation_file',           dem_path,
        '--initialization_method',    'domainAverageInitialization',
        '--input_speed',              str(spd_int),
        '--input_speed_units',        'mph',
        '--input_direction',          str(dir_int),
        '--input_wind_height',        '10',
        '--units_input_wind_height',  'm',
        '--uni_air_temp',             '50',
        '--air_temp_units',           'F',
        '--uni_cloud_cover',          '0.1',
        '--cloud_cover_units',        'fraction',
        '--vegetation',               'trees',
        '--mesh_choice',              'coarse',
        '--output_wind_height',       '10',
        '--units_output_wind_height', 'm',
        '--output_speed_units',       'mph',
        '--output_path',              CACHE,
        '--write_ascii_output',       'true',
        '--ascii_out_json',           '0',
        '--ascii_out_4326',           '1',
    ]
    print(f'    Running WN: {spd_int}mph @ {dir_int}°...', end=' ', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        print(f'ERROR\n  stderr: {res.stderr[-400:]}')
        return None, None
    print('done')
    vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
    return (vel[0] if vel else None), (ang[0] if ang else None)


def read_asc_at(path, lat, lon):
    if path is None: return None
    hdr, data = {}, []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
            else:
                try: data.append([float(v) for v in parts])
                except ValueError: pass
    arr = np.array(data)
    nrows = int(hdr['nrows']); ncols = int(hdr['ncols'])
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_f = (lon - xll) / cell; row_f = (nrows - 1) - (lat - yll) / cell
    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols - 2)); ri = max(0, min(ri, nrows - 2))
    val = (arr[ri, ci]*(1-rr)*(1-cr) + arr[ri, ci+1]*(1-rr)*cr +
           arr[ri+1, ci]*rr*(1-cr) + arr[ri+1, ci+1]*rr*cr)
    return float(val) if abs(val - nodata) > 1 else None


def wn_at(anchor, bc_speed, bc_dir):
    dem_path = os.path.join(CACHE, anchor['dem'])
    if not os.path.exists(dem_path):
        print(f'    DEM NOT FOUND: {dem_path}')
        return None
    spd_int  = int(round(bc_speed))
    dir_int  = int(round(bc_dir))
    dem_stem = os.path.splitext(anchor['dem'])[0]
    vel_path, _ = run_wn(dem_stem, dem_path, spd_int, dir_int)
    if vel_path is None: return None
    return read_asc_at(vel_path, anchor['lat'], anchor['lon'])


# ── Compute station-magnitude BC and run battery ──────────────────────────────

print('=' * 80)
print('STATION-MAGNITUDE WN BATTERY  —  2026-06-07')
print('Direction: inner rule unchanged (commit 0fabff7)')
print('Magnitude: UP → bc_raw + (1-cr)*bc_raw; DOWN → bc_raw + outer_LOO_delta (event-mag)')
print('=' * 80)
print()

results = []
for anc in ANCHORS:
    key  = anc['key']
    obs  = PRIOR[key]['obs']
    cr   = anc['coupling_ratio']
    isign = anc['inner_sign']

    # Compute station-magnitude BC
    if isign == +1 and cr is not None:
        station_deficit = (1.0 - cr) * anc['bc_raw']
        bc_stmag = anc['bc_raw'] + station_deficit
        magnitude_source = f'station_deficit={(1-cr):.3f}*{anc["bc_raw"]:.1f}={station_deficit:.1f}'
    else:
        # DOWN anchor or no coupling_ratio: keep event-level magnitude
        bc_stmag = anc['bc_raw'] + anc['outer_loo_delta']
        magnitude_source = f'event-LOO (unchanged, DOWN anchor)'

    print(f'{"─"*70}')
    print(f'{anc["label"]}')
    cr_str = f'{cr:.3f}' if cr is not None else 'N/A'
    print(f'  Direction:    {"UP" if isign>0 else "DOWN"}  |  cr={cr_str}')
    print(f'  BC raw:       {anc["bc_raw"]:.1f}')
    print(f'  BC 2lev:      {PRIOR[key]["2lev"][0]:.1f}  (event-mag)')
    print(f'  BC stmag:     {bc_stmag:.1f}  ({magnitude_source})')
    print(f'  Obs:          {obs:.1f} mph')
    print()

    # Get prior WN output for 2lev
    wn_2lev = PRIOR[key]['2lev'][1]

    # Run WN for station_mag if different from 2lev (>0.5 mph gap)
    if abs(bc_stmag - PRIOR[key]['2lev'][0]) < 0.5:
        print(f'  stmag ≈ 2lev (Δ<0.5), reusing cached WN_2lev output')
        wn_stmag = wn_2lev
    else:
        print(f'  Running stmag BC ({bc_stmag:.0f}@{anc["bc_dir"]:.0f}°):')
        wn_stmag = wn_at(anc, bc_stmag, anc['bc_dir'])
        if wn_stmag is not None:
            print(f'  WN_stmag = {wn_stmag:.1f} mph')

    print()
    results.append({
        'key':      key,
        'obs':      obs,
        'isign':    isign,
        'bc_raw':   PRIOR[key]['raw'][0],
        'wn_raw':   PRIOR[key]['raw'][1],
        'bc_flat':  PRIOR[key]['flat'][0],
        'wn_flat':  PRIOR[key]['flat'][1],
        'bc_2lev':  PRIOR[key]['2lev'][0],
        'wn_2lev':  wn_2lev,
        'bc_stmag': bc_stmag,
        'wn_stmag': wn_stmag,
        'cr':       cr,
    })


# ── Comparison table ──────────────────────────────────────────────────────────

print('=' * 100)
print('COMPARISON TABLE — Phase B Steps 2+3')
print('=' * 100)

def e(wn_spd, obs):
    if wn_spd is None: return '   N/A'
    return f'{wn_spd - obs:+.1f}'

print(f'{"anchor":<28} {"dir":<5} {"obs":>5} |'
      f' {"raw bc":>7} {"WN_err":>7} |'
      f' {"2lev bc":>7} {"WN_err":>7} |'
      f' {"stmag bc":>8} {"WN_err":>7}  vs_raw  vs_2lev')
print('-' * 100)

for r in results:
    obs = r['obs']
    err_raw   = r['wn_raw']   - obs if r['wn_raw']   is not None else None
    err_2lev  = r['wn_2lev']  - obs if r['wn_2lev']  is not None else None
    err_stmag = r['wn_stmag'] - obs if r['wn_stmag'] is not None else None

    direction = 'UP  ' if r['isign'] > 0 else 'DOWN'

    vs_raw   = ('↑' if (err_stmag is not None and err_raw  is not None and abs(err_stmag) < abs(err_raw))
                else ('↓' if (err_stmag is not None and err_raw  is not None) else '?'))
    vs_2lev  = ('↑' if (err_stmag is not None and err_2lev is not None and abs(err_stmag) < abs(err_2lev))
                else ('↓' if (err_stmag is not None and err_2lev is not None) else '?'))

    print(f'{r["key"]:<28} {direction:<5} {obs:>5.1f} |'
          f' {r["bc_raw"]:>7.1f} {e(r["wn_raw"],obs):>7} |'
          f' {r["bc_2lev"]:>7.1f} {e(r["wn_2lev"],obs):>7} |'
          f' {r["bc_stmag"]:>8.1f} {e(r["wn_stmag"],obs):>7}  {vs_raw}raw  {vs_2lev}2lev')

print()
print('raw  = aligned BC with no correction (baseline)')
print('2lev = event-LOO magnitude + inner terrain-arm sign override (commit 3f5b0af)')
print('stmag= station-deficit magnitude for UP; event-LOO magnitude for DOWN')
print()

# ── Pass condition assessment ─────────────────────────────────────────────────

print('=' * 70)
print('PASS CONDITION ASSESSMENT')
print('=' * 70)

thomas  = next((r for r in results if 'thomas'  in r['key']), None)
woolsey = next((r for r in results if 'woolsey' in r['key']), None)

if thomas:
    e2   = thomas['wn_2lev']  - thomas['obs'] if thomas['wn_2lev']  is not None else None
    es   = thomas['wn_stmag'] - thomas['obs'] if thomas['wn_stmag'] is not None else None
    print(f'WMSC1/thomas:')
    print(f'  2lev WN_err = {e2:+.1f} mph  (bc={thomas["bc_2lev"]:.1f})')
    print(f'  stmag WN_err= {es:+.1f} mph  (bc={thomas["bc_stmag"]:.1f})')
    print(f'  needed = +15.3 mph  (obs=46.0, bc_raw=30.7)')
    if es is not None and e2 is not None:
        if abs(es) < abs(e2):
            print(f'  PASS: stmag ({abs(es):.1f}) < 2lev ({abs(e2):.1f}) — closer to obs')
        else:
            print(f'  FAIL: stmag ({abs(es):.1f}) >= 2lev ({abs(e2):.1f}) — further from obs or same')
    print()

if woolsey:
    e2   = woolsey['wn_2lev']  - woolsey['obs'] if woolsey['wn_2lev']  is not None else None
    es   = woolsey['wn_stmag'] - woolsey['obs'] if woolsey['wn_stmag'] is not None else None
    print(f'WMSC1/woolsey:')
    print(f'  2lev WN_err = {e2:+.1f} mph  (bc={woolsey["bc_2lev"]:.1f})')
    print(f'  stmag WN_err= {es:+.1f} mph  (bc={woolsey["bc_stmag"]:.1f})')
    print(f'  needed = +5.7 mph  (obs=45.0, bc_raw=39.3)')
    print(f'  NOTE: cr={woolsey["cr"]:.3f} (not cr≈1); station_deficit=21.4 >> needed=5.7')
    if es is not None and e2 is not None:
        protected = abs(es) <= abs(e2) + 3.0  # within 3 mph of 2lev
        print(f'  {"PROTECTED" if protected else "DEGRADED"}: stmag_err={es:+.1f} vs 2lev_err={e2:+.1f}')
    print()

# Net improvement count
improved = 0; neutral = 0; degraded = 0
for r in results:
    e_raw   = (r['wn_raw']   - r['obs']) if r['wn_raw']   is not None else None
    e_stmag = (r['wn_stmag'] - r['obs']) if r['wn_stmag'] is not None else None
    if e_raw is None or e_stmag is None: continue
    delta = abs(e_stmag) - abs(e_raw)
    if   delta < -2: improved += 1
    elif delta >  2: degraded += 1
    else:            neutral  += 1

print(f'Net vs RAW BC: improved={improved}  neutral={neutral}  degraded={degraded}')
print(f'Pass requires: ≥3 improved/neutral')
print(f'Result: {"PASS" if improved+neutral >= 3 else "FAIL"} ({improved}+{neutral}={improved+neutral} improved/neutral)')
print()

# ── Diagnosis ─────────────────────────────────────────────────────────────────

print('=' * 70)
print('DIAGNOSIS')
print('=' * 70)
print()
print('Gate passed on POOLED r=-0.665 (dominated by DOWN-correction signal):')
print('  Large station_deficit → large negative needed_mag (DOWN stations need large')
print('  reductions; their bc >> obs when deficit is large).')
print()
print('For UP corrections specifically:')
print('  r_UP = -0.335 (weak and negative-signed)')
print('  The UP stations needing LARGEST corrections (MBUC1, HPDC1: needed>20 mph)')
print('  have cr>1 (station_deficit<0), while WMSC1 stations have large positive')
print('  deficit but only moderate needed magnitude.')
print()
print('WMSC1/woolsey reveals the assumption failure:')
print('  Handoff assumed woolsey would have cr≈1 (small deficit, protected).')
print('  Actual cr=0.456 → station_deficit=21.4 >> needed=5.7.')
print('  The "bc≈obs" at raw is because WN amplifies bc=39.3 to obs=45,')
print('  NOT because the atmospheric deficit is small.')
print()
print('Conclusion:')
print('  station_deficit is a DOWN-correction magnitude predictor.')
print('  It is NOT a reliable UP-correction magnitude predictor at this N and station set.')
print('  Two-level event-magnitude (commit 3f5b0af) remains the validated architecture.')
print('  Magnitude calibration for UP corrections requires a separate signal')
print('  (e.g., WN amplification factor at station, per-station from full WN runs).')

LOG.flush()
LOG.close()
