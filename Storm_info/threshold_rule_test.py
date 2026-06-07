#!/usr/bin/env python3
"""
threshold_rule_test.py
======================
Test the proposed inner-predictor threshold rule against the 68-station
complete-case dataset from the separation check.

Rule under test:
  predict UP if (relief_1km > 330m AND slope > 10%) OR (coupling_ratio > 1.08)

Also compares: coupling_ratio alone, relief alone, majority-class, and
several threshold variants to gauge sensitivity.

Run: conda run -n hrrr311 python threshold_rule_test.py
"""

import csv, math, os, sys
import numpy as np
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'

# ── load the same three CSVs as station_separation_check.py ──────────────────

aligned_idx = {}
with open(os.path.join(BASE, 'time_aligned_bc.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            aligned_idx[(r['stid'], r['event_id'])] = {
                'bco':  float(r['bc_over_obs_aligned']),
                'obs':  float(r['obs_sus_mph']),
                'bc':   float(r['bc_speed_aligned']),
            }
        except (ValueError, KeyError):
            pass

profile_idx = {}
with open(os.path.join(BASE, 'stage2_profile_features.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            profile_idx[(r['stid'], r['event_id'])] = {
                'coupling_ratio': float(r['coupling_ratio']),
                'shear_925_850':  float(r['shear_925_850']),
                'shear_700_850':  float(r['shear_700_850']),
            }
        except (ValueError, KeyError):
            pass

FC_ORD = {'sheltered': 0, 'intermediate': 1, 'coupled': 2}
terrain_idx = {}
with open(os.path.join(BASE, 'flow_coupling_draft.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            terrain_idx[(r['stid'], r['event_id'])] = {
                'flow_coupling': r['flow_coupling'],
                'fc_ord':        FC_ORD.get(r['flow_coupling'], 1),
                'slope':         float(r['slope']),
                'relief_1km':    float(r['relief']),
                'adiff':         float(r['adiff']) if r.get('adiff') else None,
            }
        except (ValueError, KeyError):
            pass

rows = []
for key, aln in aligned_idx.items():
    prof = profile_idx.get(key)
    terr = terrain_idx.get(key)
    if prof is None or terr is None or terr.get('adiff') is None:
        continue
    rows.append({
        'stid':         key[0],
        'event_id':     key[1],
        'bco':          aln['bco'],
        'bc_up':        1 if aln['bco'] < 1.0 else 0,
        'obs':          aln['obs'],
        'bc':           aln['bc'],
        'coupling_ratio': prof['coupling_ratio'],
        'shear_925_850':  prof['shear_925_850'],
        'shear_700_850':  prof['shear_700_850'],
        'flow_coupling': terr['flow_coupling'],
        'fc_ord':        terr['fc_ord'],
        'slope':         terr['slope'],
        'relief_1km':    terr['relief_1km'],
        'adiff':         terr['adiff'],
    })

N = len(rows)
print(f'Dataset: {N} complete-case rows, '
      f'{len(set(r["event_id"] for r in rows))} events')
print(f'bc_up distribution: {Counter(r["bc_up"] for r in rows)}  '
      f'(base rate UP={sum(r["bc_up"] for r in rows)/N:.1%})\n')


# ── helper ────────────────────────────────────────────────────────────────────

def evaluate(preds, targets, label):
    preds   = np.array(preds);  targets = np.array(targets)
    acc     = float(np.mean(preds == targets))
    tp = int(np.sum((preds==1) & (targets==1)))
    fp = int(np.sum((preds==1) & (targets==0)))
    fn = int(np.sum((preds==0) & (targets==1)))
    tn = int(np.sum((preds==0) & (targets==0)))
    prec  = tp/(tp+fp) if (tp+fp) else float('nan')
    rec   = tp/(tp+fn) if (tp+fn) else float('nan')
    f1    = 2*prec*rec/(prec+rec) if (prec+rec) else float('nan')
    print(f'  {label:<44} acc={acc:.1%}  prec={prec:.1%}  rec={rec:.1%}  f1={f1:.2f}  '
          f'TP={tp} FP={fp} FN={fn} TN={tn}')
    return acc


# ── baseline and single-feature rules ────────────────────────────────────────

targets = [r['bc_up'] for r in rows]

print('Classifier comparison (N=68):')
# majority class baseline
maj = Counter(targets).most_common(1)[0][0]
evaluate([maj]*N, targets, 'majority class (always DOWN)')

# single features with best in-sample threshold
for feat, thr, direction in [
    ('coupling_ratio', 1.08,  'high→UP'),
    ('coupling_ratio', 1.21,  'high→UP (pooled best)'),
    ('relief_1km',     330.0, 'high→UP'),
    ('relief_1km',     333.8, 'high→UP (pooled best)'),
    ('slope',          10.0,  'high→UP'),
    ('adiff',          78.7,  'low→UP'),
]:
    if direction == 'high→UP':
        preds = [1 if r[feat] >= thr else 0 for r in rows]
    else:
        preds = [1 if r[feat] < thr else 0 for r in rows]
    evaluate(preds, targets, f'{feat} {direction} @{thr}')

print()

# ── compound rule under test ──────────────────────────────────────────────────

def compound_rule(r, cr_thr, rel_thr, sl_thr):
    terrain_branch = (r['relief_1km'] > rel_thr) and (r['slope'] > sl_thr)
    coupling_branch = (r['coupling_ratio'] > cr_thr)
    return 1 if (terrain_branch or coupling_branch) else 0

print('Compound rule variants:')
variants = [
    ('(relief>330 & slope>10) OR (cr>1.08)',   1.08, 330.0, 10.0),
    ('(relief>333 & slope>10) OR (cr>1.21)',   1.21, 333.8, 10.0),
    ('(relief>330 & slope>15) OR (cr>1.08)',   1.08, 330.0, 15.0),
    ('(relief>400 & slope>10) OR (cr>1.08)',   1.08, 400.0, 10.0),
    ('(relief>330 & slope>10) OR (cr>0.90)',   0.90, 330.0, 10.0),
    ('(relief>330 & slope>10) OR (cr>1.30)',   1.30, 330.0, 10.0),
]
for label, cr_thr, rel_thr, sl_thr in variants:
    preds = [compound_rule(r, cr_thr, rel_thr, sl_thr) for r in rows]
    evaluate(preds, targets, label)

print()


# ── per-event breakdown for the primary rule ─────────────────────────────────

print('Per-event breakdown — primary rule (relief>330 & slope>10) OR (cr>1.08):')
print(f'  {"event_id":<28} N   up  down  acc     TP FP FN TN')
print('  ' + '-'*70)

for eid in sorted(set(r['event_id'] for r in rows)):
    sub = [r for r in rows if r['event_id'] == eid]
    preds   = [compound_rule(r, 1.08, 330.0, 10.0) for r in sub]
    targets_sub = [r['bc_up'] for r in sub]
    arr_p   = np.array(preds); arr_t = np.array(targets_sub)
    acc     = float(np.mean(arr_p == arr_t))
    tp = int(np.sum((arr_p==1) & (arr_t==1)))
    fp = int(np.sum((arr_p==1) & (arr_t==0)))
    fn = int(np.sum((arr_p==0) & (arr_t==1)))
    tn = int(np.sum((arr_p==0) & (arr_t==0)))
    n_up   = sum(targets_sub)
    n_down = len(targets_sub)-n_up
    print(f'  {eid:<28} {len(sub):2d}  {n_up:3d} {n_down:5d}  {acc:.0%}  {tp:3d}{fp:3d}{fn:3d}{tn:3d}')

print()


# ── WMSC1 spotlight ───────────────────────────────────────────────────────────

print('WMSC1 classification under primary rule:')
for eid in ['thomas_2017', 'woolsey_2018']:
    wmsc1 = next((r for r in rows if r['stid']=='WMSC1' and r['event_id']==eid), None)
    if not wmsc1:
        continue
    pred   = compound_rule(wmsc1, 1.08, 330.0, 10.0)
    actual = wmsc1['bc_up']
    terrain_arm = wmsc1['relief_1km'] > 330.0 and wmsc1['slope'] > 10.0
    coupling_arm = wmsc1['coupling_ratio'] > 1.08
    label = 'UP  ' if pred else 'DOWN'
    correct = '✓ CORRECT' if pred == actual else '✗ WRONG'
    print(f'  {eid:<20} bco={wmsc1["bco"]:.3f}  pred={label}  {correct}')
    print(f'    terrain arm: relief={wmsc1["relief_1km"]:.1f}>330 AND slope={wmsc1["slope"]:.1f}>10  → {terrain_arm}')
    print(f'    coupling arm: cr={wmsc1["coupling_ratio"]:.3f}>1.08  → {coupling_arm}')

print()


# ── false positives / false negatives ────────────────────────────────────────

preds_primary = [compound_rule(r, 1.08, 330.0, 10.0) for r in rows]
print('Misclassifications under primary rule:')
print(f'  {"type":<5} {"stid":<8} {"event":<28} bco   cr    relief  slope  fc')
for r, p in zip(rows, preds_primary):
    actual = r['bc_up']
    if p == actual:
        continue
    err_type = 'FP' if p==1 else 'FN'
    print(f'  {err_type:<5} {r["stid"]:<8} {r["event_id"]:<28} '
          f'{r["bco"]:.3f} {r["coupling_ratio"]:.3f} '
          f'{r["relief_1km"]:6.1f} {r["slope"]:6.2f}  {r["flow_coupling"]}')

print()


# ── threshold sensitivity sweep ───────────────────────────────────────────────

print('Coupling-ratio threshold sensitivity (relief>330 & slope>10 arm fixed):')
for cr_thr in [0.80, 0.90, 1.00, 1.08, 1.20, 1.30, 1.40, 1.50]:
    preds = [compound_rule(r, cr_thr, 330.0, 10.0) for r in rows]
    arr_p = np.array(preds); arr_t = np.array(targets)
    acc = float(np.mean(arr_p == arr_t))
    wmsc1_t = next((r for r in rows if r['stid']=='WMSC1' and r['event_id']=='thomas_2017'), None)
    wmsc1_pred = 'UP  ' if compound_rule(wmsc1_t, cr_thr, 330.0, 10.0) else 'DOWN'
    print(f'  cr>{cr_thr:.2f}  acc={acc:.1%}  WMSC1/thomas→{wmsc1_pred}')
