#!/usr/bin/env python3
"""
station_separation_check.py
============================
Gate check: can obs-free features distinguish stations that need the BC
corrected UP (bc < obs) from those that need it DOWN (bc > obs)?

If yes → two-level architecture (outer event prior + inner station predictor) is viable.
If no  → station-level signal is in the obs, not in obs-free physics; stop.

Data sources (all read-only):
  time_aligned_bc.csv          → target: bc_over_obs_aligned (uses obs — label only)
  stage2_profile_features.csv  → HRRR profile features (coupling_ratio, shear_925/850/700)
  flow_coupling_draft.csv      → terrain geometry (flow_coupling, slope, relief, adiff)

Target: bc_up = 1 if bc_over_obs_aligned < 1 (obs > bc, need to increase BC)
        bc_up = 0 if bc_over_obs_aligned > 1 (obs < bc, need to decrease BC)

Features (obs-free):
  coupling_ratio    = hrrr_10m_aligned / hrrr_850_aligned  (BL coupling state)
  shear_925_850     = hrrr_925_aligned - hrrr_850_aligned
  shear_700_850     = hrrr_700_aligned - hrrr_850_aligned
  flow_coupling_ord = 0=sheltered, 1=intermediate, 2=coupled  (terrain geometry)
  slope             = terrain slope (%)
  relief_1km        = terrain relief within 1km (m)
  adiff             = angle between terrain aspect and event flow direction (°)

Baseline: majority-class classifier within each event (always predict DOWN for thomas).
Gate:  > 70% within-event sign accuracy from obs-free features = predictor exists
       < 60% sign accuracy = no predictor; stop.

Run: conda run -n hrrr311 python station_separation_check.py
"""

import csv, math, os, sys
import numpy as np
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'

# ── load and join ─────────────────────────────────────────────────────────────

# time_aligned_bc: target values
aligned_idx = {}
with open(os.path.join(BASE, 'time_aligned_bc.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            aligned_idx[(r['stid'], r['event_id'])] = {
                'bco':       float(r['bc_over_obs_aligned']),
                'obs':       float(r['obs_sus_mph']),
                'bc':        float(r['bc_speed_aligned']),
                'regime':    r['synoptic_regime'],
                'offset_h':  float(r['offset_h']),
            }
        except (ValueError, KeyError):
            pass

# stage2_profile: HRRR profile features
profile_idx = {}
with open(os.path.join(BASE, 'stage2_profile_features.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            profile_idx[(r['stid'], r['event_id'])] = {
                'coupling_ratio': float(r['coupling_ratio']),
                'shear_925_850':  float(r['shear_925_850']),
                'shear_700_850':  float(r['shear_700_850']),
                'hrrr_10m_aligned': float(r['hrrr_10m_aligned']),
                'hrrr_925_aligned': float(r['hrrr_925_aligned']),
                'hrrr_700_aligned': float(r['hrrr_700_aligned']),
            }
        except (ValueError, KeyError):
            pass

# flow_coupling: terrain geometry
FC_ORD = {'sheltered': 0, 'intermediate': 1, 'coupled': 2}
terrain_idx = {}
with open(os.path.join(BASE, 'flow_coupling_draft.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            terrain_idx[(r['stid'], r['event_id'])] = {
                'flow_coupling':     r['flow_coupling'],
                'fc_ord':            FC_ORD.get(r['flow_coupling'], 1),
                'slope':             float(r['slope']),
                'relief_1km':        float(r['relief']),
                'adiff':             float(r['adiff']) if r.get('adiff') else None,
                'tc':                r.get('tc', ''),
            }
        except (ValueError, KeyError):
            pass

# ── build complete-case rows ──────────────────────────────────────────────────

FEAT_NAMES = ['coupling_ratio', 'shear_925_850', 'shear_700_850',
              'fc_ord', 'slope', 'relief_1km', 'adiff']

rows = []
for key, aln in aligned_idx.items():
    prof = profile_idx.get(key)
    terr = terrain_idx.get(key)
    if prof is None or terr is None:
        continue
    if terr.get('adiff') is None:
        continue
    feats = {
        'coupling_ratio': prof['coupling_ratio'],
        'shear_925_850':  prof['shear_925_850'],
        'shear_700_850':  prof['shear_700_850'],
        'fc_ord':         terr['fc_ord'],
        'slope':          terr['slope'],
        'relief_1km':     terr['relief_1km'],
        'adiff':          terr['adiff'],
    }
    rows.append({
        'stid':          key[0],
        'event_id':      key[1],
        'regime':        aln['regime'],
        'flow_coupling': terr['flow_coupling'],
        'tc':            terr['tc'],
        'bco':           aln['bco'],
        'bc_up':         1 if aln['bco'] < 1.0 else 0,   # TARGET
        'obs':           aln['obs'],
        'bc':            aln['bc'],
        'offset_h':      aln['offset_h'],
        **feats,
    })

print(f'Complete-case rows: {len(rows)} across '
      f'{len(set(r["event_id"] for r in rows))} events')
from collections import Counter
print('Events:', Counter(r['event_id'] for r in rows))
print('bc_up distribution:', Counter(r['bc_up'] for r in rows))
print()


# ── helper: sign accuracy for a single feature threshold within an event ──────

def threshold_accuracy(feat_vals, targets, direction='higher_means_up'):
    """
    For a single feature: sweep thresholds to find best within-group accuracy.
    direction='higher_means_up': feature high → bc_up=1.
    Returns (best_accuracy, best_threshold).
    """
    vals = np.array(feat_vals, dtype=float)
    y    = np.array(targets)
    thresholds = np.unique(vals)
    best_acc = 0.5
    best_thr = np.median(vals)
    for thr in thresholds:
        if direction == 'higher_means_up':
            pred = (vals >= thr).astype(int)
        else:
            pred = (vals < thr).astype(int)
        acc = float(np.mean(pred == y))
        if acc > best_acc:
            best_acc = acc
            best_thr = thr
    # also try opposite
    for thr in thresholds:
        if direction == 'higher_means_up':
            pred = (vals < thr).astype(int)
        else:
            pred = (vals >= thr).astype(int)
        acc = float(np.mean(pred == y))
        if acc > best_acc:
            best_acc = acc
            best_thr = thr
    return best_acc, best_thr


def pearson(a, b):
    a = np.array(a) - np.mean(a); b = np.array(b) - np.mean(b)
    d = math.sqrt(float(np.dot(a,a)) * float(np.dot(b,b)))
    return float(np.dot(a,b)/d) if d > 0 else 0.0


# ── overall feature–target correlations ──────────────────────────────────────

print('Feature–target correlations (r with bc_up, N=' + str(len(rows)) + '):')
targets_all = [r['bc_up']   for r in rows]
for feat in FEAT_NAMES:
    vals = [r[feat] for r in rows]
    r_val = pearson(vals, targets_all)
    acc, thr = threshold_accuracy(vals, targets_all)
    print(f'  {feat:<20} r={r_val:+.3f}   best threshold acc={acc:.2%}  thr≈{thr:.2f}')
print()


# ── per-event within-event analysis ──────────────────────────────────────────

print('Per-event within-event sign accuracy (majority-class baseline in parens):')
print()
events_with_enough = []
for eid in sorted(set(r['event_id'] for r in rows)):
    sub = [r for r in rows if r['event_id'] == eid]
    n_up   = sum(r['bc_up'] for r in sub)
    n_down = len(sub) - n_up
    baseline = max(n_up, n_down) / len(sub)

    feat_accs = {}
    for feat in FEAT_NAMES:
        vals = [r[feat] for r in sub]
        tgt  = [r['bc_up'] for r in sub]
        acc, thr = threshold_accuracy(vals, tgt)
        feat_accs[feat] = (acc, thr)

    best_feat = max(feat_accs, key=lambda f: feat_accs[f][0])
    best_acc, best_thr = feat_accs[best_feat]

    print(f'  {eid:<28} N={len(sub):2d}  up={n_up:2d}  down={n_down:2d}  '
          f'baseline={baseline:.0%}  best={best_acc:.0%} ({best_feat}@{best_thr:.2f})')

    if len(sub) >= 8:
        events_with_enough.append(eid)
        for feat in FEAT_NAMES:
            acc, thr = feat_accs[feat]
            print(f'    {feat:<20} acc={acc:.0%}  r={pearson([r[feat] for r in sub], [r["bc_up"] for r in sub]):+.3f}')
    print()


# ── WMSC1 spotlight ───────────────────────────────────────────────────────────

print('=' * 68)
print('WMSC1 SPOTLIGHT — can obs-free features predict "needs bc UP"?')
print('=' * 68)

for eid in ['thomas_2017', 'woolsey_2018']:
    sub = [r for r in rows if r['event_id'] == eid]
    wmsc1 = next((r for r in sub if r['stid'] == 'WMSC1'), None)
    if wmsc1 is None:
        print(f'{eid}: WMSC1 not found in complete-case rows')
        continue

    print(f'\n{eid}  (N={len(sub)}, WMSC1 bco={wmsc1["bco"]:.3f}, target={"UP" if wmsc1["bc_up"] else "DOWN"}):')

    for feat in FEAT_NAMES:
        vals   = np.array([r[feat] for r in sub])
        targets = np.array([r['bc_up'] for r in sub])
        acc, thr = threshold_accuracy(vals.tolist(), targets.tolist())

        wmsc1_val   = wmsc1[feat]
        up_vals     = vals[targets == 1]
        down_vals   = vals[targets == 0]
        up_mean     = float(up_vals.mean()) if len(up_vals) > 0 else float('nan')
        down_mean   = float(down_vals.mean()) if len(down_vals) > 0 else float('nan')

        # What does this feature predict for WMSC1?
        if acc >= 0.5:
            # use the best threshold direction
            thr2_vals = vals
            if float(np.mean((thr2_vals >= thr).astype(int) == targets)) >= \
               float(np.mean((thr2_vals <  thr).astype(int) == targets)):
                pred_wmsc1 = 'UP  ' if wmsc1_val >= thr else 'DOWN'
            else:
                pred_wmsc1 = 'DOWN' if wmsc1_val >= thr else 'UP  '
        else:
            pred_wmsc1 = '?   '

        correct = '✓' if (pred_wmsc1.strip()=='UP' and wmsc1['bc_up']==1) or \
                         (pred_wmsc1.strip()=='DOWN' and wmsc1['bc_up']==0) else '✗'
        print(f'  {feat:<20} val={wmsc1_val:7.2f}  up_mean={up_mean:7.2f}  '
              f'down_mean={down_mean:7.2f}  acc={acc:.0%}  '
              f'→predicts {pred_wmsc1} {correct}')


# ── Decision ──────────────────────────────────────────────────────────────────

print()
print('=' * 68)
print('SEPARATION CHECK SUMMARY')
print('=' * 68)

# Pooled accuracy across large events
pooled_rows  = [r for r in rows if r['event_id'] in events_with_enough]
print(f'\nPooled analysis (events with N>=8): {len(pooled_rows)} rows')
for feat in FEAT_NAMES:
    vals = [r[feat] for r in pooled_rows]
    tgt  = [r['bc_up'] for r in pooled_rows]
    acc, thr = threshold_accuracy(vals, tgt)
    r_val = pearson(vals, tgt)
    print(f'  {feat:<20} acc={acc:.0%}  r={r_val:+.3f}')

print()
print('WMSC1/thomas feature check:')
wmsc1_t = next((r for r in rows if r['stid']=='WMSC1' and r['event_id']=='thomas_2017'), None)
if wmsc1_t:
    print(f'  bco={wmsc1_t["bco"]:.3f} (needs UP={wmsc1_t["bc_up"]})')
    print(f'  coupling_ratio={wmsc1_t["coupling_ratio"]:.3f}  '
          f'(up-group mean={np.mean([r["coupling_ratio"] for r in rows if r["event_id"]=="thomas_2017" and r["bc_up"]==1]):.3f}, '
          f'down-group mean={np.mean([r["coupling_ratio"] for r in rows if r["event_id"]=="thomas_2017" and r["bc_up"]==0]):.3f})')
    print(f'  slope={wmsc1_t["slope"]:.2f}  adiff={wmsc1_t["adiff"]:.1f}  fc={wmsc1_t["flow_coupling"]}')

# Overall gate decision
print()
thomas_sub  = [r for r in rows if r['event_id'] == 'thomas_2017']
if thomas_sub:
    thomas_tgt  = [r['bc_up'] for r in thomas_sub]
    thomas_base = max(sum(thomas_tgt), len(thomas_tgt)-sum(thomas_tgt)) / len(thomas_tgt)
    best_accs   = []
    for feat in FEAT_NAMES:
        acc, _ = threshold_accuracy([r[feat] for r in thomas_sub], thomas_tgt)
        best_accs.append(acc)
    thomas_best = max(best_accs)
    print(f'Thomas within-event: baseline={thomas_base:.0%}  best_feature_acc={thomas_best:.0%}')
    print()
    if thomas_best >= 0.70:
        print('GATE PASS: obs-free features achieve ≥70% sign accuracy in Thomas.')
        print('WMSC1-as-UP is distinguishable. Two-level architecture is warranted.')
    elif thomas_best >= 0.60:
        print('PARTIAL: 60–70% accuracy. Weak signal. Proceed with caution.')
        print('Two-level model may help at the margin. Feature set needs improvement.')
    else:
        print('GATE FAIL: best obs-free feature < 60% sign accuracy in Thomas.')
        print('Station-level signal is in the obs. The two-level model is circular.')
        print('Ceiling reached. Worth reporting; do not build the inner sweep predictor.')
