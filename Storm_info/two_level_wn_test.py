#!/usr/bin/env python3
"""
two_level_wn_test.py — Two-level BC correction WindNinja battery  2026-06-07
=============================================================================
Architecture under test:
  Outer layer: LOO Ridge event-level delta (w700, mslp_grad, hrrr_coupling_frac)
  Inner rule:  UP  if (relief_1km>330m AND slope>10%) OR (coupling_ratio>1.08)
               DOWN otherwise
  Two-level BC: bc_aligned + inner_sign × |outer_delta_speed|
  Direction:   raw aligned direction throughout (no direction correction)

Pass condition: WMSC1/thomas WN_err substantially better than flat WN_err.
  Flat gave WN_err = -31.9 mph (bc driven to 11.9 by event-mean DOWN correction).
  Two-level should correct sign for WMSC1 → bc ≈ bc_aligned + |outer_delta|.

NOTE — when inner direction agrees with outer direction, two-level = flat.
  Only changes outcome at stations where outer disagrees with inner.
  In this battery: WMSC1/thomas is the only such case.

Run: conda run -n hrrr311 python two_level_wn_test.py
"""

import csv, math, os, sys, subprocess, glob
import numpy as np
from collections import defaultdict
LOG = open(r'C:\temp\two_level_log.txt', 'w', encoding='utf-8')
sys.stdout = LOG

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bc_outer_trainer import load_samples, StandardizedRidge

BASE  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
WN_CLI = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE  = r'C:\temp\windninja_cache'

# ── Anchor definitions ────────────────────────────────────────────────────────
# bc_speed/bc_dir = time-ALIGNED values from time_aligned_bc.csv / wn_anchor_test.py
# relief/slope from flow_coupling_draft.csv; coupling_ratio from stage2_profile_features.csv
# PNTM8: continental event, not in stage2 profile; terrain arm only (slope=9.44 < 10 → fails)

ANCHORS = [
    {
        'label':          'CBXC1 / camp_2018   (coupled offshore)',
        'stid':           'CBXC1', 'event': 'camp_2018',
        'lat': 40.14564,  'lon': -121.5225,
        'dem': 'dem_40.0_-121.3_20mi.tif',
        'obs_sus': 28.99, 'obs_dir': 69.3,
        'hrrr_10m': 25.37, 'hrrr_err': -3.62,
        # aligned bc (offset_h=0 for camp, so aligned = raw)
        'bc_speed': 32.93, 'bc_dir': 85.8,
        # inner rule features
        'coupling_ratio': 0.7704,      # from stage2_profile_features.csv
        'relief_1km': 223.6,           # from flow_coupling_draft.csv
        'slope': 5.96,
        # Phase B flat result (reference only)
        'flat_phase_b_note': 'flat WN_err=-10.8  (bc=14.06@86°)',
    },
    {
        'label':          'WMSC1 / thomas_2017  (intermediate, ALIGNED bc=30.7@58°, KEY CASE)',
        'stid':           'WMSC1', 'event': 'thomas_2017',
        'lat': 34.59583,  'lon': -118.57861,
        'dem': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'obs_sus': 45.99, 'obs_dir': 62.3,
        'hrrr_10m': 10.34, 'hrrr_err': -35.65,
        'bc_speed': 30.67, 'bc_dir': 58.0,     # aligned Dec-07 02Z
        'coupling_ratio': 0.3371,
        'relief_1km': 505.9,
        'slope': 33.97,
        'flat_phase_b_note': 'flat WN_err=-31.9  (bc=11.91@58°)',
    },
    {
        'label':          'WMSC1 / woolsey_2018  (intermediate, ALIGNED bc=39.3@64°)',
        'stid':           'WMSC1', 'event': 'woolsey_2018',
        'lat': 34.59583,  'lon': -118.57861,
        'dem': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif',
        'obs_sus': 44.98, 'obs_dir': 68.0,
        'hrrr_10m': 17.94, 'hrrr_err': -27.04,
        'bc_speed': 39.32, 'bc_dir': 63.6,     # offset_h=0, same as raw
        'coupling_ratio': 0.4564,
        'relief_1km': 506.8,
        'slope': 47.63,
        'flat_phase_b_note': 'raw WN_err≈0 (full recovery); flat degraded (bc=47.1→overshoot)',
    },
    {
        'label':          'PNTM8 / missoula_dec2025  (continental downslope)',
        'stid':           'PNTM8', 'event': 'missoula_dec2025',
        'lat': 47.04136,  'lon': -113.98631,
        'dem': 'dem_47.0_-114.0_8mi.tif',
        'obs_sus': 46.06, 'obs_dir': 252.0,
        'hrrr_10m': 40.22, 'hrrr_err': -5.84,
        'bc_speed': 84.18, 'bc_dir': 275.4,    # 700 hPa event-median (no alignment for continental)
        'coupling_ratio': None,                  # continental event, not in stage2 profile
        'relief_1km': 500.4,
        'slope': 9.44,                           # JUST BELOW 10 threshold
        'flat_phase_b_note': 'flat WN_err=+35.3  (bc=53.4@275°)',
    },
]

INNER_RULE_THR = dict(relief=330.0, slope=10.0, cr=1.08)


def inner_sign(anchor):
    """
    Returns +1 (predict UP, keep/increase bc) or -1 (predict DOWN, reduce bc).
    Rule: UP if (relief>330 AND slope>10) OR (coupling_ratio>1.08).
    For continental events (no coupling_ratio), terrain arm only.
    """
    terrain = (anchor['relief_1km'] > INNER_RULE_THR['relief'] and
               anchor['slope']      > INNER_RULE_THR['slope'])
    cr = anchor['coupling_ratio']
    coupling = (cr is not None and cr > INNER_RULE_THR['cr'])
    return +1 if (terrain or coupling) else -1


# ── Load event records (same as wire_outer_trainer.py) ───────────────────────

feat_by_event = {}
with open(os.path.join(BASE, 'hrrr_synoptic_features.csv'), newline='', encoding='utf-8') as f:
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
with open(os.path.join(BASE, 'flow_coupling_draft.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        fc_idx[(r['stid'], r['event_id'])] = r['flow_coupling']

def circ_mean_deg(us, vs):
    return math.degrees(math.atan2(float(np.mean(us)), float(np.mean(vs)))) % 360.0

event_acc = defaultdict(lambda: {
    'delta_speed': [], 'bc_speed': [], 'obs_speed': [],
    'obs_dir_u': [], 'obs_dir_v': [], 'bc_dir_u': [], 'bc_dir_v': [],
})
with open(os.path.join(BASE, 'hrrr_error_dataset.csv'), newline='', encoding='utf-8') as f:
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
        event_acc[eid]['delta_speed'].append(obs - bc)
        event_acc[eid]['bc_speed'].append(bc)
        event_acc[eid]['obs_speed'].append(obs)
        try:
            od = float(r['obs_dir_deg']); bd = float(r['bc_dir'])
            event_acc[eid]['obs_dir_u'].append(math.sin(math.radians(od)))
            event_acc[eid]['obs_dir_v'].append(math.cos(math.radians(od)))
            event_acc[eid]['bc_dir_u'].append(math.sin(math.radians(bd)))
            event_acc[eid]['bc_dir_v'].append(math.cos(math.radians(bd)))
        except (ValueError, KeyError):
            pass

records = []
for eid, feats in sorted(feat_by_event.items()):
    d = event_acc.get(eid)
    if d is None or len(d['delta_speed']) < 2:
        continue
    d_spd   = float(np.mean(d['delta_speed']))
    d_dir_deg = 0.0
    if len(d['bc_dir_u']) >= 2:
        bc_dir  = circ_mean_deg(d['bc_dir_u'],  d['bc_dir_v'])
        obs_dir = circ_mean_deg(d['obs_dir_u'], d['obs_dir_v'])
        d_dir_deg = ((obs_dir - bc_dir + 180) % 360) - 180
    records.append({
        'event':      eid,
        'features':   feats,
        'delta_speed_mph': d_spd,
        'delta_dir_sin':   math.sin(math.radians(d_dir_deg)),
        'delta_dir_cos':   math.cos(math.radians(d_dir_deg)),
        'hrrr_prior_speed_mph': float(np.mean(d['bc_speed'])),
        'hrrr_prior_dir_deg':   (
            circ_mean_deg(d['bc_dir_u'], d['bc_dir_v'])
            if len(d['bc_dir_u']) >= 2 else 0.0),
    })

print(f'Event records built: {len(records)} events')

FEATURES = ['w700_speed_mph', 'mslp_grad', 'hrrr_coupling_frac']
ALPHA = 1.0

def loo_predict_event(held_event, all_records):
    """Hold out held_event, train Ridge on rest, return predicted delta_speed."""
    train = [r for r in all_records if r['event'] != held_event]
    test  = [r for r in all_records if r['event'] == held_event]
    if not train or not test:
        return float('nan'), float('nan')

    def to_xy(recs):
        X = np.array([[r['features'][f] for f in FEATURES] for r in recs])
        y_spd = np.array([r['delta_speed_mph'] for r in recs])
        return X, y_spd

    X_tr, y_tr = to_xy(train)
    X_te, _    = to_xy(test)

    # Standardize features (fit on train only)
    mu  = X_tr.mean(axis=0)
    std = X_tr.std(axis=0); std[std < 1e-9] = 1.0
    X_tr_s = (X_tr - mu) / std
    X_te_s = (X_te - mu) / std

    # Ridge regression (closed-form)
    n_f = X_tr_s.shape[1]
    A = X_tr_s.T @ X_tr_s + ALPHA * np.eye(n_f)
    b_spd = X_tr_s.T @ y_tr
    coef_spd = np.linalg.solve(A, b_spd)
    intercept_spd = y_tr.mean() - (X_tr_s.mean(axis=0) @ coef_spd)
    pred_arr = X_te_s @ coef_spd + intercept_spd
    pred_spd = float(pred_arr.flat[0])
    return pred_spd, test[0]['delta_speed_mph']


# Compute LOO predictions for all events
samples = load_samples(records)  # needed only for event list

loo_delta_speed = {}
loo_actual_speed = {}
print('LOO predictions:')
for rec in records:
    eid = rec['event']
    pred, actual = loo_predict_event(eid, records)
    loo_delta_speed[eid]  = pred
    loo_actual_speed[eid] = actual
    print(f'  {eid:<28} actual={actual:+.2f}  LOO_pred={pred:+.2f}')
print()


# ── WN runner (from wn_anchor_test.py) ───────────────────────────────────────

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
    print(f'    Running WN fresh: {spd_int}mph @ {dir_int}°...', end=' ', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        print(f'ERROR\n  stderr: {res.stderr[-500:]}')
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
            if len(parts)==2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
            else:
                try: data.append([float(v) for v in parts])
                except ValueError: pass
    arr = np.array(data)
    nrows=int(hdr['nrows']); ncols=int(hdr['ncols'])
    xll=hdr['xllcorner']; yll=hdr['yllcorner']; cell=hdr['cellsize']
    nodata=hdr.get('nodata_value',-9999)
    col_f=(lon-xll)/cell; row_f=(nrows-1)-(lat-yll)/cell
    ci,ri=int(col_f),int(row_f)
    cr,rr=col_f-ci,row_f-ri
    ci=max(0,min(ci,ncols-2)); ri=max(0,min(ri,nrows-2))
    val=(arr[ri,ci]*(1-rr)*(1-cr)+arr[ri,ci+1]*(1-rr)*cr+
         arr[ri+1,ci]*rr*(1-cr)+arr[ri+1,ci+1]*rr*cr)
    return float(val) if abs(val-nodata)>1 else None


def wn_at(anchor, bc_speed, bc_dir):
    dem_path = os.path.join(CACHE, anchor['dem'])
    if not os.path.exists(dem_path):
        print(f'    DEM NOT FOUND: {dem_path}')
        return None, None
    spd_int = int(round(bc_speed))
    dir_int = int(round(bc_dir))
    dem_stem = os.path.splitext(anchor['dem'])[0]
    vel_path, ang_path = run_wn(dem_stem, dem_path, spd_int, dir_int)
    if vel_path is None: return None, None
    wn_spd = read_asc_at(vel_path, anchor['lat'], anchor['lon'])
    wn_dir = read_asc_at(ang_path, anchor['lat'], anchor['lon']) if ang_path else None
    return wn_spd, wn_dir


# ── Main battery ──────────────────────────────────────────────────────────────

print('=' * 76)
print('TWO-LEVEL WN BATTERY  —  2026-06-07')
print('Rule: UP if (relief>330 AND slope>10) OR (cr>1.08); else DOWN')
print('bc_2level = bc_aligned + inner_sign × |outer_LOO_delta|')
print('=' * 76)

rows = []
for anchor in ANCHORS:
    eid   = anchor['event']
    isign = inner_sign(anchor)

    # Outer LOO delta
    outer_delta = loo_delta_speed.get(eid, 0.0)

    # Inner rule info
    terrain_fires = (anchor['relief_1km'] > INNER_RULE_THR['relief'] and
                     anchor['slope'] > INNER_RULE_THR['slope'])
    cr = anchor['coupling_ratio']
    cr_fires = (cr is not None and cr > INNER_RULE_THR['cr'])
    direction = 'UP  ' if isign > 0 else 'DOWN'

    # Two-level and flat corrected bc speeds
    bc_raw   = anchor['bc_speed']
    bc_flat  = bc_raw + outer_delta                      # flat event-level
    bc_2lev  = bc_raw + isign * abs(outer_delta)         # two-level

    print(f'\n{"─"*68}')
    print(f'{anchor["label"]}')
    cr_str = f'{cr:.3f}' if cr is not None else 'N/A'
    cr_label = 'YES' if cr_fires else ('NO' if cr is not None else 'N/A(continental)')
    print(f'  Inner rule:  terrain={"YES" if terrain_fires else "NO"} (relief={anchor["relief_1km"]:.0f}m/{INNER_RULE_THR["relief"]:.0f} slope={anchor["slope"]:.1f}%/{INNER_RULE_THR["slope"]:.0f})'
          f'  coupling={cr_label} (cr={cr_str}/{INNER_RULE_THR["cr"]:.2f})')
    print(f'  Direction:   {direction}  |  outer_LOO_delta={outer_delta:+.2f} mph')
    print(f'  BC values:   raw={bc_raw:.1f}  flat={bc_flat:.1f}  two-level={bc_2lev:.1f} mph  @ {anchor["bc_dir"]:.0f}°')
    print(f'  Obs:         {anchor["obs_sus"]:.1f} mph  HRRR_err={anchor["hrrr_err"]:+.1f}')
    print(f'  Prior note:  {anchor.get("flat_phase_b_note","")}')

    # Run WN for: raw, flat (if different from raw or 2lev), two-level
    print()
    print(f'  Running raw BC ({bc_raw:.0f}@{anchor["bc_dir"]:.0f}°):')
    wn_raw_spd, wn_raw_dir   = wn_at(anchor, bc_raw,  anchor['bc_dir'])
    print(f'  Running flat BC ({bc_flat:.0f}@{anchor["bc_dir"]:.0f}°):')
    wn_flat_spd, wn_flat_dir = wn_at(anchor, bc_flat, anchor['bc_dir'])
    if abs(bc_2lev - bc_flat) < 0.5:
        print(f'  Two-level = flat (inner sign agrees with outer, no new WN run needed)')
        wn_2lev_spd, wn_2lev_dir = wn_flat_spd, wn_flat_dir
    else:
        print(f'  Running two-level BC ({bc_2lev:.0f}@{anchor["bc_dir"]:.0f}°):')
        wn_2lev_spd, wn_2lev_dir = wn_at(anchor, bc_2lev, anchor['bc_dir'])

    def fmt_err(wn_spd, obs):
        if wn_spd is None: return '   N/A'
        return f'{wn_spd-obs:+.1f}'
    def fmt_spd(wn_spd):
        if wn_spd is None: return '  N/A'
        return f'{wn_spd:.1f}'

    rows.append({
        'anchor': f'{anchor["stid"]}/{eid[:12]}',
        'direction': direction.strip(),
        'bc_raw':   bc_raw,   'wn_raw':  wn_raw_spd,  'err_raw':  (wn_raw_spd  - anchor['obs_sus']) if wn_raw_spd  else None,
        'bc_flat':  bc_flat,  'wn_flat': wn_flat_spd, 'err_flat': (wn_flat_spd - anchor['obs_sus']) if wn_flat_spd else None,
        'bc_2lev':  bc_2lev,  'wn_2lev': wn_2lev_spd,'err_2lev': (wn_2lev_spd - anchor['obs_sus']) if wn_2lev_spd else None,
        'obs':      anchor['obs_sus'],
        'hrrr_err': anchor['hrrr_err'],
        'changed':  abs(bc_2lev - bc_flat) >= 0.5,
    })


# ── Comparison table ──────────────────────────────────────────────────────────

print()
print('=' * 88)
print('COMPARISON TABLE')
print('=' * 88)
print(f'{"anchor":<28} {"dir":<5} {"obs":>5} |'
      f' {"raw bc":>7} {"WN_err":>7} |'
      f' {"flat bc":>7} {"WN_err":>7} |'
      f' {"2lev bc":>7} {"WN_err":>7}  changed?')
print('-' * 88)

for r in rows:
    def e(v):
        return f'{v:+.1f}' if v is not None else '  N/A'
    def s(v):
        return f'{v:.1f}' if v is not None else ' N/A'
    changed = '← NEW' if r['changed'] else '=flat'
    print(f'{r["anchor"]:<28} {r["direction"]:<5} {r["obs"]:>5.1f} |'
          f' {r["bc_raw"]:>7.1f} {e(r["err_raw"]):>7} |'
          f' {r["bc_flat"]:>7.1f} {e(r["err_flat"]):>7} |'
          f' {r["bc_2lev"]:>7.1f} {e(r["err_2lev"]):>7}  {changed}')

print()
print('Flat = event-level LOO correction applied uniformly (Phase B architecture).')
print('2lev = inner sign rule applied: UP stations get +|delta|, DOWN get -|delta|.')
print()

# Pass condition
thomas = next((r for r in rows if 'WMSC1' in r['anchor'] and 'thomas' in r['anchor']), None)
if thomas:
    print('PASS CONDITION: WMSC1/thomas two-level WN_err substantially better than flat.')
    flat_err = thomas['err_flat']
    lev_err  = thomas['err_2lev']
    raw_err  = thomas['err_raw']
    print(f'  raw    WN_err = {e(raw_err):>7}  (bc={thomas["bc_raw"]:.1f})')
    print(f'  flat   WN_err = {e(flat_err):>7}  (bc={thomas["bc_flat"]:.1f})')
    print(f'  2-level WN_err = {e(lev_err):>7}  (bc={thomas["bc_2lev"]:.1f})')
    if lev_err is not None and flat_err is not None:
        if abs(lev_err) < abs(flat_err):
            print(f'  RESULT: PASS — |two-level err| {abs(lev_err):.1f} < |flat err| {abs(flat_err):.1f}')
            print(f'          Improvement over flat: {abs(flat_err)-abs(lev_err):.1f} mph')
        else:
            print(f'  RESULT: FAIL — |two-level err| {abs(lev_err):.1f} >= |flat err| {abs(flat_err):.1f}')
    if lev_err is not None:
        if abs(lev_err) <= 3.0:
            print(f'  BONUS: near-full recovery (|WN_err|={abs(lev_err):.1f} ≤ 3 mph)')
        elif abs(lev_err) <= 10.0:
            print(f'  NOTE: partial recovery, sign may be reversed from flat (overshoot)')
        else:
            print(f'  NOTE: overcorrection (|WN_err|={abs(lev_err):.1f} > 10 mph)')
print()
print('NOTE: Inner rule only changes outcome when outer event-direction != inner station-direction.')
print('In this battery, the only case where they disagree is WMSC1/thomas (outer=DOWN, inner=UP).')
print('All other anchors: two-level result = flat result.')
LOG.flush()
LOG.close()
sys.stdout = sys.__stdout__
print('Output written to C:\\temp\\two_level_log.txt')
