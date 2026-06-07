#!/usr/bin/env python3
"""
phase_b_wn_test.py
==================
Phase B WindNinja test battery: raw BC vs outer-trainer corrected BC.

For each anchor station:
  1. LOO-predict the event-level BC correction (train on 10 events, test on 1).
  2. Apply: corrected_bc_speed = station_raw_bc + loo_delta_speed
             corrected_bc_dir  = station_raw_bc_dir + loo_delta_dir
  3. Run WindNinja with corrected BC over the station DEM.
  4. Extract WN output at station lat/lon.
  5. Compare: obs / HRRR_err / wn_err_raw / wn_err_corrected.

Anchors:
  CBXC1 / camp_2018         coupled offshore       bc=32.93@86°
  WMSC1 / thomas_2017       intermediate SA        bc=30.67@58° (aligned Stage 1)
  WMSC1 / woolsey_2018      intermediate SA        bc=39.32@64°
  PNTM8 / missoula_dec2025  coupled/decoupled 700  bc=84.18@275°  (fresh run, discard stale)

Sheltered variance check:
  HMRC1 / camp_2018         sheltered              obs=10.5 (near-calm denominator artifact)
  If HMRC1 DEM not available, sheltered check is deferred.

Run: conda run -n hrrr311 python phase_b_wn_test.py
"""

import csv, math, os, sys, glob, subprocess
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bc_outer_trainer import load_samples, StandardizedRidge

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
FEAT  = os.path.join(BASE, 'hrrr_synoptic_features.csv')
DB    = os.path.join(BASE, 'hrrr_error_dataset.csv')
FC    = os.path.join(BASE, 'flow_coupling_draft.csv')
CACHE = r'C:\temp\windninja_cache'
WN_CLI = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'


# ── rebuild event-level records (same as wire_outer_trainer.py) ───────────────

def circ_mean_deg(us, vs):
    return math.degrees(math.atan2(float(np.mean(us)), float(np.mean(vs)))) % 360.0

feat_by_event = {}
with open(FEAT, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            feat_by_event[r['event_id']] = {
                'w700_speed_mph':     float(r['w700_speed_mph']),
                'mslp_grad':          float(r['mslp_grad_pa100km']),
                'hrrr_coupling_frac': float(r['hrrr_coupling_frac_mean']),
            }
        except (ValueError, KeyError):
            pass

fc_idx = {}
with open(FC, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        fc_idx[(r['stid'], r['event_id'])] = r['flow_coupling']

acc = defaultdict(lambda: {
    'delta_speed': [], 'bc_speed': [], 'obs_speed': [],
    'obs_dir_u': [], 'obs_dir_v': [], 'bc_dir_u': [], 'bc_dir_v': [],
})
with open(DB, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
            continue
        if fc_idx.get((r['stid'], r['event_id'])) not in ('coupled', 'intermediate'):
            continue
        try:
            obs = float(r['obs_sus_mph']); bc = float(r['bc_speed'])
            if bc <= 0: raise ValueError
        except (ValueError, KeyError):
            continue
        eid = r['event_id']
        acc[eid]['delta_speed'].append(obs - bc)
        acc[eid]['bc_speed'].append(bc)
        acc[eid]['obs_speed'].append(obs)
        try:
            od = float(r['obs_dir_deg']); bd = float(r['bc_dir'])
            acc[eid]['obs_dir_u'].append(math.sin(math.radians(od)))
            acc[eid]['obs_dir_v'].append(math.cos(math.radians(od)))
            acc[eid]['bc_dir_u'].append(math.sin(math.radians(bd)))
            acc[eid]['bc_dir_v'].append(math.cos(math.radians(bd)))
        except (ValueError, KeyError):
            pass

FEAT_COLS = ['w700_speed_mph', 'mslp_grad', 'hrrr_coupling_frac']

records = []
for eid in sorted(feat_by_event):
    d = acc.get(eid)
    if d is None or len(d['delta_speed']) < 2:
        continue
    feats = feat_by_event[eid]
    d_spd = float(np.mean(d['delta_speed']))
    d_dir = 0.0
    if len(d['bc_dir_u']) >= 2:
        bc_dir  = circ_mean_deg(d['bc_dir_u'],  d['bc_dir_v'])
        obs_dir = circ_mean_deg(d['obs_dir_u'], d['obs_dir_v'])
        d_dir   = ((obs_dir - bc_dir + 180) % 360) - 180
    records.append({
        'event': eid,
        'features': {k: feats[k] for k in FEAT_COLS},
        'delta_speed_mph': d_spd,
        'delta_dir_sin':   math.sin(math.radians(d_dir)),
        'delta_dir_cos':   math.cos(math.radians(d_dir)),
    })

samples = load_samples(records)
print(f'Training set: {len(samples)} events')


# ── LOO correction for each anchor event ─────────────────────────────────────

def loo_predict(held_event, samples, feat_cols=FEAT_COLS, alpha=1.0):
    """Train on all events except held_event; return predicted (delta_spd, delta_dir_deg)."""
    train = [s for s in samples if s.event != held_event]
    test  = [s for s in samples if s.event == held_event]
    if not train or not test:
        return None, None

    X_tr = np.array([[s.features[f] for f in feat_cols] for s in train])
    X_te = np.array([[s.features[f] for f in feat_cols] for s in test])
    y_spd = np.array([s.delta_speed_mph for s in train])
    y_sin = np.array([s.delta_dir_sin   for s in train])
    y_cos = np.array([s.delta_dir_cos   for s in train])

    m_spd = StandardizedRidge(alpha).fit(X_tr, y_spd)
    m_sin = StandardizedRidge(alpha).fit(X_tr, y_sin)
    m_cos = StandardizedRidge(alpha).fit(X_tr, y_cos)

    pred_spd = float(m_spd.predict(X_te)[0])
    pred_sin = float(m_sin.predict(X_te)[0])
    pred_cos = float(m_cos.predict(X_te)[0])
    pred_dir = math.degrees(math.atan2(pred_sin, pred_cos))  # correction in degrees
    return pred_spd, pred_dir


# ── WN helpers ────────────────────────────────────────────────────────────────

def run_wn(dem_stem, dem_path, spd_int, dir_int, force_fresh=False):
    """Run WindNinja; returns (vel_path, ang_path). Caches by (dem_stem, dir, spd)."""
    pattern = os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc')
    cached_vel = glob.glob(pattern)
    if cached_vel and not force_fresh:
        cached_ang = glob.glob(
            os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
        print(f'    [cached] {os.path.basename(cached_vel[0])}')
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
    print(f'    [running WN] {spd_int}mph @ {dir_int}°... ', end='', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        print(f'ERROR\n      {res.stderr[-400:]}')
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
    xll  = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_f = (lon - xll) / cell
    row_f = (nrows - 1) - (lat - yll) / cell
    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols-2)); ri = max(0, min(ri, nrows-2))
    val = (arr[ri,  ci  ]*(1-rr)*(1-cr) + arr[ri,  ci+1]*(1-rr)*cr +
           arr[ri+1,ci  ]*rr*(1-cr)     + arr[ri+1,ci+1]*rr*cr)
    return float(val) if abs(val - nodata) > 1 else None

def circ_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ── Phase B anchors ───────────────────────────────────────────────────────────

ANCHORS = [
    # (label, stid, event_id, coupling, lat, lon, dem, obs, obs_dir,
    #  hrrr_10m, hrrr_err, raw_bc, raw_bc_dir, note)
    {
        'label':   'CBXC1 / camp_2018  (coupled offshore)',
        'stid':    'CBXC1',
        'event':   'camp_2018',
        'coupling':'coupled',
        'lat':     40.14564, 'lon': -121.5225,
        'dem':     'dem_40.0_-121.3_20mi.tif',
        'obs':     28.99,    'obs_dir': 69.3,
        'hrrr_10m':25.37,    'hrrr_err': -3.62,
        'raw_bc':  32.93,    'raw_bc_dir': 85.8,
        'force_fresh': False,
        'note':    'raw BC: wn_err=+6.36 (overcorrection)',
    },
    {
        'label':   'WMSC1 / thomas_2017 (intermediate SA, aligned bc=30.67)',
        'stid':    'WMSC1',
        'event':   'thomas_2017',
        'coupling':'intermediate',
        'lat':     34.59583, 'lon': -118.57861,
        'dem':     'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'obs':     45.99,    'obs_dir': 62.3,
        'hrrr_10m':10.34,    'hrrr_err': -35.65,
        'raw_bc':  30.67,    'raw_bc_dir': 58.0,  # aligned Stage 1
        'force_fresh': False,
        'note':    'aligned bc (Stage 1): wn_err=-10.2 (partial recovery)',
    },
    {
        'label':   'WMSC1 / woolsey_2018 (intermediate SA)',
        'stid':    'WMSC1',
        'event':   'woolsey_2018',
        'coupling':'intermediate',
        'lat':     34.59583, 'lon': -118.57861,
        'dem':     'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'obs':     44.98,    'obs_dir': 68.0,
        'hrrr_10m':17.94,    'hrrr_err': -27.04,
        'raw_bc':  39.32,    'raw_bc_dir': 63.6,
        'force_fresh': False,
        'note':    'raw BC: wn_err=-0.0 (FULL RECOVERY)',
    },
    {
        'label':   'PNTM8 / missoula_dec2025 (continental/700hPa)',
        'stid':    'PNTM8',
        'event':   'missoula_dec2025',
        'coupling':'intermediate',
        'lat':     47.04136, 'lon': -113.98631,
        'dem':     'dem_47.0_-114.0_8mi.tif',
        'obs':     46.06,    'obs_dir': 255.0,
        'hrrr_10m':40.22,    'hrrr_err': -5.84,
        'raw_bc':  84.18,    'raw_bc_dir': 275.4,
        'force_fresh': True,   # discard stale per master status
        'note':    'bc=84.18 anomaly flag; running fresh; 700hPa bc; HRRR already close',
    },
]

# Also define previously-known raw-BC WN results (from wn_anchor_test.py)
# For PNTM8, raw-BC WN result is NOT in cache — run it here for the first time.
RAW_WN_KNOWN = {
    'CBXC1/camp_2018':       {'wn_speed': 35.3, 'wn_dir': 95},
    'WMSC1/thomas_2017':     {'wn_speed': 35.8, 'wn_dir': 58},
    'WMSC1/woolsey_2018':    {'wn_speed': 45.0, 'wn_dir': 64},
    'PNTM8/missoula_dec2025': None,   # needs fresh run
}


# ── Main loop ─────────────────────────────────────────────────────────────────

print()
print('=' * 72)
print('PHASE B  WindNinja — raw BC vs corrected BC')
print('=' * 72)

results = []

for a in ANCHORS:
    print(f'\n--- {a["label"]} ---')

    # 1. LOO prediction for this event
    d_spd_pred, d_dir_pred = loo_predict(a['event'], samples)
    corr_bc_spd = a['raw_bc'] + d_spd_pred
    corr_bc_dir = (a['raw_bc_dir'] + d_dir_pred) % 360.0
    corr_bc_spd = max(1.0, corr_bc_spd)   # floor at 1 mph

    print(f'  Raw BC       : {a["raw_bc"]:.1f} mph @ {a["raw_bc_dir"]:.0f}°')
    print(f'  LOO Δspd     : {d_spd_pred:+.2f} mph  |  Δdir : {d_dir_pred:+.1f}°')
    print(f'  Corrected BC : {corr_bc_spd:.1f} mph @ {corr_bc_dir:.0f}°')
    print(f'  Obs          : {a["obs"]:.1f} mph @ {a["obs_dir"]:.0f}°')

    dem_path = os.path.join(CACHE, a['dem'])
    if not os.path.exists(dem_path):
        print(f'  DEM NOT FOUND: {dem_path}')
        results.append({**a, 'corr_bc_spd': corr_bc_spd, 'corr_bc_dir': corr_bc_dir,
                        'wn_raw_spd': None, 'wn_corr_spd': None})
        continue

    dem_stem = os.path.splitext(a['dem'])[0]

    # 2. WN with raw BC (use cached if available; run if PNTM8)
    key = f'{a["stid"]}/{a["event"]}'
    raw_known = RAW_WN_KNOWN.get(key)
    if raw_known is not None:
        wn_raw_spd = raw_known['wn_speed']
        wn_raw_dir = raw_known['wn_dir']
        print(f'  WN(raw BC)   : {wn_raw_spd:.1f} mph @ {wn_raw_dir}°  [from prior anchor test]')
    else:
        print(f'  Running WN with raw BC ({int(round(a["raw_bc"]))}@{int(round(a["raw_bc_dir"]))})...')
        raw_dir_int = int(round(a['raw_bc_dir']))
        raw_spd_int = int(round(a['raw_bc']))
        v, ang = run_wn(dem_stem, dem_path, raw_spd_int, raw_dir_int,
                        force_fresh=a['force_fresh'])
        wn_raw_spd = read_asc_at(v, a['lat'], a['lon']) if v else None
        wn_raw_dir = read_asc_at(ang, a['lat'], a['lon']) if ang else None
        if wn_raw_spd:
            print(f'  WN(raw BC)   : {wn_raw_spd:.1f} mph @ {wn_raw_dir:.0f}°')

    # 3. WN with corrected BC
    corr_dir_int = int(round(corr_bc_dir))
    corr_spd_int = int(round(corr_bc_spd))
    print(f'  Running WN with corrected BC ({corr_spd_int}@{corr_dir_int})...')
    v_c, ang_c = run_wn(dem_stem, dem_path, corr_spd_int, corr_dir_int,
                        force_fresh=False)
    wn_corr_spd = read_asc_at(v_c, a['lat'], a['lon']) if v_c else None
    wn_corr_dir = read_asc_at(ang_c, a['lat'], a['lon']) if ang_c else None
    if wn_corr_spd:
        print(f'  WN(corr BC)  : {wn_corr_spd:.1f} mph @ {wn_corr_dir:.0f}°')

    # Errors
    hrrr_err    = a['hrrr_err']
    wn_raw_err  = (wn_raw_spd  - a['obs']) if wn_raw_spd  is not None else None
    wn_corr_err = (wn_corr_spd - a['obs']) if wn_corr_spd is not None else None

    results.append({
        **a,
        'corr_bc_spd': corr_bc_spd, 'corr_bc_dir': corr_bc_dir,
        'd_spd_pred': d_spd_pred,  'd_dir_pred': d_dir_pred,
        'wn_raw_spd':  wn_raw_spd,  'wn_raw_dir':  wn_raw_dir,
        'wn_corr_spd': wn_corr_spd, 'wn_corr_dir': wn_corr_dir,
        'wn_raw_err':  wn_raw_err,
        'wn_corr_err': wn_corr_err,
    })


# ── Comparison table ──────────────────────────────────────────────────────────

print()
print('=' * 92)
print('PHASE B COMPARISON TABLE')
print('=' * 92)
print(f'{"anchor":<38} {"obs":>6} {"HRRR_err":>9} {"raw_bc":>7} {"WN(raw)_err":>12} {"corr_bc":>8} {"WN(cor)_err":>12}  Δ  verdict')
print('-' * 92)

for r in results:
    obs        = r['obs']
    hrrr_err   = r['hrrr_err']
    raw_bc     = r['raw_bc']
    corr_bc    = r.get('corr_bc_spd')
    wn_raw_err  = r.get('wn_raw_err')
    wn_corr_err = r.get('wn_corr_err')

    raw_err_s  = f'{wn_raw_err:+.2f}'  if wn_raw_err  is not None else '    ?'
    corr_err_s = f'{wn_corr_err:+.2f}' if wn_corr_err is not None else '    ?'
    corr_bc_s  = f'{corr_bc:.1f}'      if corr_bc     is not None else '  ?'
    delta_s = '  ?'
    verdict = '?'
    if wn_raw_err is not None and wn_corr_err is not None:
        imp = abs(wn_raw_err) - abs(wn_corr_err)
        delta_s = f'{imp:+.2f}'
        if abs(wn_corr_err) <= 2.0:
            verdict = 'FULL RECOVERY'
        elif imp > 0:
            verdict = f'improved ({imp:+.1f})'
        elif imp < -1.0:
            verdict = f'degraded  ({imp:+.1f})'
        else:
            verdict = 'neutral'

    label = f'{r["stid"]}/{r["event"][:14]}'
    print(f'  {label:<36} {obs:>6.1f} {hrrr_err:>+9.2f} {raw_bc:>7.1f} '
          f'{raw_err_s:>12} {corr_bc_s:>8} {corr_err_s:>12}  {delta_s}  {verdict}')

print()
print('Columns: obs=RAWS (mph); HRRR_err=obs−hrrr10m; WN(raw)_err=wn_raw−obs; WN(cor)_err=wn_corr−obs')
print('Δ = |wn_raw_err| − |wn_corr_err|  (positive = corrected WN moves toward obs)')

# ── Direction summary ─────────────────────────────────────────────────────────
print()
print('Direction summary (obs_dir vs raw_bc_dir vs corr_bc_dir vs wn_corr_dir):')
for r in results:
    print(f'  {r["stid"]}/{r["event"][:12]:<20} '
          f'obs={r["obs_dir"]:.0f}°  raw_bc={r["raw_bc_dir"]:.0f}°  '
          f'corr_bc={r.get("corr_bc_dir",0):.0f}°  '
          f'wn_corr={r["wn_corr_dir"]:.0f}°'
          if r.get('wn_corr_dir') is not None
          else f'  {r["stid"]}/{r["event"][:12]:<20} obs={r["obs_dir"]:.0f}°  raw_bc={r["raw_bc_dir"]:.0f}°  '
               f'corr_bc={r.get("corr_bc_dir",0):.0f}°  wn_corr=N/A')

# ── per-event LOO correction summary ─────────────────────────────────────────
print()
print('LOO correction applied per event:')
for r in results:
    d_s = r.get("d_spd_pred")
    d_d = r.get("d_dir_pred")
    if d_s is not None:
        print(f'  {r["event"]:<28}  LOO Δspd={d_s:+.2f}  Δdir={d_d:+.1f}°  '
              f'raw={r["raw_bc"]:.1f} → corr={r.get("corr_bc_spd",0):.1f}')

# ── decision tree ─────────────────────────────────────────────────────────────
print()
print('=' * 72)
print('DECISION TREE:')
n_improved = sum(1 for r in results
                 if r.get('wn_raw_err') is not None and r.get('wn_corr_err') is not None
                 and abs(r['wn_corr_err']) < abs(r['wn_raw_err']))
n_total    = sum(1 for r in results
                 if r.get('wn_raw_err') is not None and r.get('wn_corr_err') is not None)
if n_total > 0:
    print(f'  {n_improved}/{n_total} anchors improved by corrected BC.')
    pntm8 = next((r for r in results if r['stid'] == 'PNTM8'), None)
    if pntm8 and pntm8.get('wn_corr_err') is not None:
        imp = abs(pntm8['wn_raw_err'] or 0) - abs(pntm8['wn_corr_err'])
        print(f'  PNTM8 (strongest test): Δ={imp:+.2f} (positive = improved)')
    print()
    if n_improved >= 3:
        print('  GO: Corrected BC improves WN at large-correction anchors.')
        print('  Scale to full coupled-station battery and benchmark vs HDW.')
    elif n_improved >= 2:
        print('  PARTIAL: Corrected BC helps at large-correction anchors.')
        print('  Degrade at bc≈obs stations consistent with under-determined regime.')
        print('  Document caveat; proceed to full battery with near-zero events excluded.')
    else:
        print('  STOP: Corrected BC does not improve WN output.')
        print('  The correction sizes the BC but WN terrain step is not the recovery mechanism.')
        print('  Revisit feature set or correction application strategy.')
print('=' * 72)
