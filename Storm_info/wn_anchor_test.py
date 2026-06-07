#!/usr/bin/env python3
"""
wn_anchor_test.py  —  WindNinja anchor test (Phase B, 2026-06-07)

Tests whether WN+rawBC recovers the HRRR underbias at coupled ridge stations.
Benchmark from phase_a_finding.md: coupled offshore mean = -6.89 mph (N=20, 75% neg).

Anchors:
  CBXC1 / camp_2018    coupled   offshore   HRRR_err=-3.62  bc=32.93@85.8°
  WMSC1 / thomas_2017  intermediate  santa_ana  HRRR_err=-35.65  bc=51.30@64.6°  (lee/rotor contrast)
  WMSC1 / woolsey_2018 intermediate  santa_ana  HRRR_err=-27.04  bc=39.32@63.6°  (lee/rotor contrast)

Run in hrrr311 env (has numpy, scipy).
"""

import subprocess, sys, os, glob, math
import numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WN_CLI = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE  = r'C:\temp\windninja_cache'

# ── Anchor definitions ────────────────────────────────────────────────────────
# All bc_speed/bc_dir from hrrr_error_dataset.csv (HRRR 850hPa aloft wind)
ANCHORS = [
    {
        'label':    'CBXC1 / camp_2018 (COUPLED offshore, primary anchor)',
        'stid':     'CBXC1',
        'event':    'camp_2018',
        'coupling': 'coupled',
        'regime':   'diablo_offshore',
        'lat':      40.14564,
        'lon':     -121.5225,
        'dem':      'dem_40.0_-121.3_20mi.tif',
        'obs_sus':  28.99,
        'obs_dir':  69.3,
        'hrrr_10m': 25.37,
        'hrrr_err': -3.62,
        'bc_speed': 32.93,
        'bc_dir':   85.8,
    },
    {
        'label':    'WMSC1 / thomas_2017 (INTERMEDIATE lee/rotor, contrast)',
        'stid':     'WMSC1',
        'event':    'thomas_2017',
        'coupling': 'intermediate',
        'regime':   'santa_ana',
        'lat':      34.59583,
        'lon':     -118.57861,
        'dem':      'dem_34.60_-118.58_20mi_wmsc1.tif',
        'obs_sus':  45.99,
        'obs_dir':  62.3,
        'hrrr_10m': 10.34,
        'hrrr_err': -35.65,
        'bc_speed': 51.30,
        'bc_dir':   64.6,
    },
    {
        'label':    'WMSC1 / woolsey_2018 (INTERMEDIATE lee/rotor, contrast)',
        'stid':     'WMSC1',
        'event':    'woolsey_2018',
        'coupling': 'intermediate',
        'regime':   'santa_ana',
        'lat':      34.59583,
        'lon':     -118.57861,
        'dem':      'dem_34.60_-118.58_20mi_wmsc1.tif',
        'obs_sus':  44.98,
        'obs_dir':  68.0,
        'hrrr_10m': 17.94,
        'hrrr_err': -27.04,
        'bc_speed': 39.32,
        'bc_dir':   63.6,
    },
]


def run_wn(dem_stem, dem_path, spd_int, dir_int):
    cached_vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
        print(f'  Cached: {os.path.basename(cached_vel[0])}')
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
    print(f'  Running WN: {spd_int}mph @ {dir_int}°...', end=' ', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        print(f'ERROR\n  {res.stderr[-600:]}')
        return None, None
    print('done')
    vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
    return (vel[0] if vel else None), (ang[0] if ang else None)


def read_asc_at(path, lat, lon):
    if path is None:
        return None
    hdr, data = {}, []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
            else:
                try:
                    data.append([float(v) for v in parts])
                except ValueError:
                    pass
    arr  = np.array(data)
    nrows = int(hdr['nrows']); ncols = int(hdr['ncols'])
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_f = (lon - xll) / cell
    row_f = (nrows - 1) - (lat - yll) / cell
    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols-2)); ri = max(0, min(ri, nrows-2))
    val = (arr[ri,   ci  ]*(1-rr)*(1-cr) + arr[ri,   ci+1]*(1-rr)*cr +
           arr[ri+1, ci  ]*rr*(1-cr)     + arr[ri+1, ci+1]*rr*cr)
    return float(val) if abs(val - nodata) > 1 else None


def circ_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ── Run ───────────────────────────────────────────────────────────────────────
print('=' * 72)
print('WINDNINJA ANCHOR TEST  —  Phase B  2026-06-07')
print('Benchmark: coupled offshore mean HRRR_err = -6.89 mph (N=20, 75% neg)')
print('Success: WN_err closer to 0 than HRRR_err at primary anchor (CBXC1)')
print('=' * 72)

results = []
for a in ANCHORS:
    print(f'\n--- {a["label"]} ---')
    print(f'  BC input: {a["bc_speed"]:.1f} mph @ {a["bc_dir"]:.0f}°  '
          f'(HRRR 850hPa aloft wind)')
    print(f'  Obs:      {a["obs_sus"]:.1f} mph @ {a["obs_dir"]:.0f}°  (RAWS sustained)')
    print(f'  HRRR 10m: {a["hrrr_10m"]:.1f} mph  |  HRRR_err = {a["hrrr_err"]:+.1f} mph')

    dem_path = os.path.join(CACHE, a['dem'])
    if not os.path.exists(dem_path):
        print(f'  DEM NOT FOUND: {dem_path}')
        results.append({**a, 'wn_speed': None, 'wn_dir': None})
        continue

    spd_int = int(round(a['bc_speed']))
    dir_int = int(round(a['bc_dir']))
    dem_stem = os.path.splitext(a['dem'])[0]

    vel_path, ang_path = run_wn(dem_stem, dem_path, spd_int, dir_int)
    if vel_path is None:
        results.append({**a, 'wn_speed': None, 'wn_dir': None})
        continue

    wn_spd = read_asc_at(vel_path, a['lat'], a['lon'])
    wn_dir = read_asc_at(ang_path, a['lat'], a['lon']) if ang_path else None

    wn_err     = (wn_spd - a['obs_sus']) if wn_spd is not None else None
    recovery   = (a['hrrr_err'] - wn_err)          if wn_err is not None else None
    amp_ratio  = (wn_spd / a['bc_speed'])           if wn_spd else None
    hrrr_ratio = (a['hrrr_10m'] / a['obs_sus'])     if a['obs_sus'] else None
    wn_ratio   = (wn_spd / a['obs_sus'])             if (wn_spd and a['obs_sus']) else None
    dir_err_obs_bc = circ_diff(a['obs_dir'], a['bc_dir'])
    dir_err_obs_wn = circ_diff(a['obs_dir'], wn_dir) if wn_dir else None

    print(f'\n  RESULTS:')
    print(f'    WN output:      {wn_spd:.1f} mph @ {wn_dir:.0f}°' if wn_spd and wn_dir
          else f'    WN output:      {wn_spd}')
    print(f'    HRRR_err:       {a["hrrr_err"]:+.2f} mph  (HRRR/obs ratio = {hrrr_ratio:.3f})')
    if wn_err is not None:
        print(f'    WN_err:         {wn_err:+.2f} mph  (WN/obs ratio   = {wn_ratio:.3f})')
        print(f'    Recovery:       {recovery:+.2f} mph  (positive = WN moved toward obs)')
        print(f'    WN amplif:      {amp_ratio:.3f}x BC input speed')
    if dir_err_obs_wn is not None:
        print(f'    Dir_err (obs vs BC): {dir_err_obs_bc:.0f}°')
        print(f'    Dir_err (obs vs WN): {dir_err_obs_wn:.0f}°')

    results.append({**a, 'wn_speed': wn_spd, 'wn_dir': wn_dir,
                    'wn_err': wn_err, 'recovery': recovery,
                    'amp_ratio': amp_ratio, 'hrrr_ratio': hrrr_ratio, 'wn_ratio': wn_ratio})


# ── Summary table ─────────────────────────────────────────────────────────────
print('\n' + '=' * 72)
print('ANCHOR TEST SUMMARY')
print('=' * 72)
print(f'{"stid/event":<28} {"coupling":<14} {"obs":>6} {"HRRR":>7} {"WN":>7} '
      f'{"HRRR_err":>9} {"WN_err":>8} {"recovery":>9}  verdict')
print('-' * 72)

for r in results:
    wn_s   = f'{r["wn_speed"]:>7.1f}' if r.get('wn_speed') is not None else '      ?'
    we_s   = f'{r["wn_err"]:>+8.1f}' if r.get('wn_err') is not None else '       ?'
    rec_s  = f'{r["recovery"]:>+9.1f}' if r.get('recovery') is not None else '        ?'

    verdict = '?'
    if r.get('wn_err') is not None:
        wn_e   = r['wn_err']
        hrrr_e = r['hrrr_err']
        if abs(wn_e) <= 2.0:
            verdict = 'FULL RECOVERY'
        elif abs(wn_e) < abs(hrrr_e) and (wn_e * hrrr_e > 0 or abs(wn_e) < abs(hrrr_e)):
            verdict = 'partial recovery'
        elif wn_e * hrrr_e < 0 and abs(wn_e) > 2.0:
            verdict = 'OVERCORRECTION'
        else:
            verdict = 'no recovery'

    label = f'{r["stid"]}/{r["event"][:12]}'
    print(f'{label:<28} {r["coupling"]:<14} {r["obs_sus"]:>6.1f} {r["hrrr_10m"]:>7.1f} '
          f'{wn_s} {r["hrrr_err"]:>+9.2f} {we_s} {rec_s}  {verdict}')

print()
print('Benchmark: coupled offshore HRRR_err = -6.89 mph. WN_err target: |WN_err| < |HRRR_err|.')
print('WMSC1 contrast: intermediate/lee. If WN recovers WMSC1 but not CBXC1, that is surprising.')
print('If WN recovers CBXC1 but not WMSC1, that supports lee/rotor interpretation.')
