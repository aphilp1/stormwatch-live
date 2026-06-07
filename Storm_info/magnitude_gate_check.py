#!/usr/bin/env python3
"""
magnitude_gate_check.py — Phase B Step 1
=========================================
Gate check: do obs-free features predict station-level needed correction magnitude?

needed_magnitude = obs - bc_aligned   (positive = UP needed, negative = DOWN)

Candidate features (all obs-free at runtime):
  station_deficit = (1 - coupling_ratio) * bc_aligned
  terrain_score   = relief_1km * slope
  coupling_ratio  alone
  relief_1km      alone

Gate pass condition: |r| > 0.3  AND  LOEO RMSE < baseline (training-mean predictor)
If gate fails: direction solved, magnitude event-calibrated, not station-predictable.

Run:    conda run -n hrrr311 python magnitude_gate_check.py
Output: C:\temp\magnitude_gate_log.txt
"""

import csv, math, os, sys
import numpy as np

LOG = open(r'C:\temp\magnitude_gate_log.txt', 'w', encoding='utf-8')
sys.stdout = LOG

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'

# ── load CSVs (same complete-case filter as threshold_rule_test.py → N=68) ────

aligned_idx = {}
with open(os.path.join(BASE, 'time_aligned_bc.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            aligned_idx[(r['stid'], r['event_id'])] = {
                'bco': float(r['bc_over_obs_aligned']),
                'obs': float(r['obs_sus_mph']),
                'bc':  float(r['bc_speed_aligned']),
            }
        except (ValueError, KeyError):
            pass

profile_idx = {}
with open(os.path.join(BASE, 'stage2_profile_features.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            profile_idx[(r['stid'], r['event_id'])] = {
                'coupling_ratio': float(r['coupling_ratio']),
            }
        except (ValueError, KeyError):
            pass

terrain_idx = {}
with open(os.path.join(BASE, 'flow_coupling_draft.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            terrain_idx[(r['stid'], r['event_id'])] = {
                'slope':      float(r['slope']),
                'relief_1km': float(r['relief']),
                'adiff':      float(r['adiff']) if r.get('adiff') else None,
            }
        except (ValueError, KeyError):
            pass

rows = []
for key, aln in aligned_idx.items():
    prof = profile_idx.get(key)
    terr = terrain_idx.get(key)
    if prof is None or terr is None or terr.get('adiff') is None:
        continue
    cr  = prof['coupling_ratio']
    bc  = aln['bc']
    obs = aln['obs']
    rows.append({
        'stid':            key[0],
        'event_id':        key[1],
        'bc':              bc,
        'obs':             obs,
        'bco':             aln['bco'],
        'bc_up':           1 if aln['bco'] < 1.0 else 0,
        'coupling_ratio':  cr,
        'slope':           terr['slope'],
        'relief_1km':      terr['relief_1km'],
        'station_deficit': (1.0 - cr) * bc,      # obs-free: decoupling-gap estimate
        'terrain_score':   terr['relief_1km'] * terr['slope'],  # obs-free
        'needed_mag':      obs - bc,              # LABEL: signed, positive=UP
    })

N = len(rows)
n_up = sum(r['bc_up'] for r in rows)
needed_all = [r['needed_mag'] for r in rows]

print(f'Dataset: N={N}, UP={n_up} ({n_up/N:.0%}), DOWN={N-n_up} ({(N-n_up)/N:.0%})')
print(f'needed_magnitude: mean={np.mean(needed_all):+.2f}  std={np.std(needed_all):.2f}  '
      f'range=[{min(needed_all):.1f}, {max(needed_all):.1f}]')
print()


# ── helpers ────────────────────────────────────────────────────────────────────

def pearson(a, b):
    a, b = np.array(a, float), np.array(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float('nan')
    return float(np.corrcoef(a, b)[0, 1])

def ols_predict(x_train, y_train, x_test):
    x_tr, y_tr = np.array(x_train, float), np.array(y_train, float)
    if len(x_tr) < 2 or np.std(x_tr) == 0:
        return [float(np.mean(y_tr))] * len(x_test)
    a = float(np.cov(x_tr, y_tr)[0, 1] / np.var(x_tr))
    b = float(np.mean(y_tr) - a * np.mean(x_tr))
    return [a * float(x) + b for x in x_test]


# ── feature registry ───────────────────────────────────────────────────────────

feat_defs = [
    ('station_deficit',  lambda r: r['station_deficit']),
    ('terrain_score',    lambda r: r['terrain_score']),
    ('coupling_ratio',   lambda r: r['coupling_ratio']),
    ('relief_1km',       lambda r: r['relief_1km']),
    ('slope',            lambda r: r['slope']),
    ('bc_aligned',       lambda r: r['bc']),
]


# ── pooled Pearson r (all 68 rows) ─────────────────────────────────────────────

print('Pearson r vs needed_magnitude (pooled, N=68):')
print(f'  {"feature":<40}  {"r (all)":<10}  {"r (UP only)"}')
print('  ' + '-'*65)

up_rows   = [r for r in rows if r['bc_up'] == 1]
down_rows = [r for r in rows if r['bc_up'] == 0]
needed_up   = [r['needed_mag'] for r in up_rows]
needed_down = [r['needed_mag'] for r in down_rows]

for fname, fget in feat_defs:
    r_all  = pearson(needed_all, [fget(r) for r in rows])
    r_up   = pearson(needed_up,  [fget(r) for r in up_rows])
    flag   = '  *** r>0.3' if abs(r_all) > 0.3 else ''
    print(f'  {fname:<40}  r={r_all:+.3f}    r_UP={r_up:+.3f}{flag}')
print()


# ── leave-one-event-out RMSE ───────────────────────────────────────────────────

events = sorted(set(r['event_id'] for r in rows))
all_sq = {fname: [] for fname, _ in feat_defs}
all_sq['baseline'] = []

print('LOEO RMSE (leave-one-event-out, OLS single-feature):')
col_names = [fn[:14] for fn, _ in feat_defs[:4]]
print(f'  {"event":<28}  N  baseline  ' + '  '.join(f'{c:<14}' for c in col_names))
print('  ' + '-'*105)

for held in events:
    train = [r for r in rows if r['event_id'] != held]
    test  = [r for r in rows if r['event_id'] == held]
    if not test:
        continue
    y_tr = [r['needed_mag'] for r in train]
    y_te = [r['needed_mag'] for r in test]

    train_mean = float(np.mean(y_tr))
    b_errs = [(train_mean - y)**2 for y in y_te]
    all_sq['baseline'].extend(b_errs)
    b_rmse = math.sqrt(np.mean(b_errs))

    rmses = {}
    for fname, fget in feat_defs:
        preds = ols_predict([fget(r) for r in train], y_tr, [fget(r) for r in test])
        errs  = [(p - y)**2 for p, y in zip(preds, y_te)]
        all_sq[fname].extend(errs)
        rmses[fname] = math.sqrt(np.mean(errs))

    line = f'  {held:<28}  {len(test):2d}  {b_rmse:8.2f}  '
    line += '  '.join(f'{rmses[fn]:14.2f}' for fn, _ in feat_defs[:4])
    print(line)

print('  ' + '-'*105)
b_ov = math.sqrt(np.mean(all_sq['baseline']))
line = f'  {"OVERALL":<28}  {N:2d}  {b_ov:8.2f}  '
line += '  '.join(f'{math.sqrt(np.mean(all_sq[fn])):14.2f}' for fn, _ in feat_defs[:4])
print(line)
print()


# ── per-station scatter for the two candidate features ─────────────────────────

print('Station-level detail — station_deficit vs needed_mag (sorted by needed_mag):')
print(f'  {"stid":<8} {"event":<28} bc_up  needed  deficit  terrain_sc  cr')
print('  ' + '-'*80)
for r in sorted(rows, key=lambda x: x['needed_mag']):
    print(f'  {r["stid"]:<8} {r["event_id"]:<28}  {"UP" if r["bc_up"] else "DN"}  '
          f'{r["needed_mag"]:+7.1f}  {r["station_deficit"]:7.1f}  '
          f'{r["terrain_score"]:10.0f}  {r["coupling_ratio"]:.3f}')
print()


# ── WMSC1 spotlight ────────────────────────────────────────────────────────────

print('WMSC1 spotlight — magnitude prediction comparison:')
loo_mags = {'thomas_2017': 18.76, 'woolsey_2018': 7.76}
for eid in ['thomas_2017', 'woolsey_2018']:
    w = next((r for r in rows if r['stid'] == 'WMSC1' and r['event_id'] == eid), None)
    if not w:
        continue
    loo_m = loo_mags.get(eid)
    isign = 1 if w['bc_up'] else -1
    bc_event_mag   = w['bc'] + isign * loo_m
    bc_station_def = w['bc'] + isign * w['station_deficit']
    print(f'  {eid}:')
    print(f'    bc={w["bc"]:.1f}  obs={w["obs"]:.1f}  needed_mag={w["needed_mag"]:+.1f} mph')
    print(f'    event-LOO magnitude ({loo_m:.2f} mph):  → bc_2lev={bc_event_mag:.1f}  '
          f'(overshoots by {abs(bc_event_mag - w["obs"]):.1f} mph)')
    print(f'    station_deficit ({w["station_deficit"]:.2f} mph):   → bc_2lev={bc_station_def:.1f}  '
          f'({"overshoots" if bc_station_def > w["obs"] else "undershoots"} by '
          f'{abs(bc_station_def - w["obs"]):.1f} mph)')
    print(f'    terrain_score={w["terrain_score"]:.0f} (m*%)  cr={w["coupling_ratio"]:.3f}')
    print()


# ── gate decision ──────────────────────────────────────────────────────────────

r_def  = pearson(needed_all, [r['station_deficit'] for r in rows])
r_ter  = pearson(needed_all, [r['terrain_score']   for r in rows])
loeo_def  = math.sqrt(np.mean(all_sq['station_deficit']))
loeo_ter  = math.sqrt(np.mean(all_sq['terrain_score']))
loeo_base = math.sqrt(np.mean(all_sq['baseline']))

print('=' * 60)
print('GATE DECISION')
print('=' * 60)
print(f'Pass criterion: |r| > 0.3  AND  LOEO_RMSE < baseline')
print(f'Baseline LOEO RMSE: {loeo_base:.2f} mph')
print()
print(f'station_deficit: r={r_def:+.3f}  LOEO={loeo_def:.2f}  '
      f'r_ok={abs(r_def)>0.3}  loeo_ok={loeo_def<loeo_base}  '
      f'PASS={abs(r_def)>0.3 and loeo_def<loeo_base}')
print(f'terrain_score:   r={r_ter:+.3f}  LOEO={loeo_ter:.2f}  '
      f'r_ok={abs(r_ter)>0.3}  loeo_ok={loeo_ter<loeo_base}  '
      f'PASS={abs(r_ter)>0.3 and loeo_ter<loeo_base}')
print()

pass_def = abs(r_def) > 0.3 and loeo_def < loeo_base
pass_ter = abs(r_ter) > 0.3 and loeo_ter < loeo_base

if pass_def or pass_ter:
    print('GATE: PASS')
    print('→ Proceed to Step 2: station-level magnitude scaling')
    if pass_def:
        print(f'  Primary feature: station_deficit=(1-cr)*bc  (r={r_def:+.3f})')
    if pass_ter:
        print(f'  Secondary feature: terrain_score=relief*slope  (r={r_ter:+.3f})')
else:
    print('GATE: FAIL — no obs-free feature predicts station magnitude reliably')
    print()
    print('Result: direction is solved end-to-end (commit 3f5b0af).')
    print('Magnitude: event-calibrated via outer LOO trainer is the ceiling at this N.')
    print('Known overshoot: WMSC1/thomas +10.5 instead of ~0 (event-mean too large).')
    print('Next step: full coupled-station benchmark vs HDW once more events available.')

LOG.flush()
LOG.close()
