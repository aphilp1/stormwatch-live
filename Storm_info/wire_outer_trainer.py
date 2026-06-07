#!/usr/bin/env python3
"""
wire_outer_trainer.py
=====================
Wires bc_outer_trainer.py to the real 12-event departure database.

For each event, computes the event-level mean BC correction needed
over coupled+intermediate KEEP/CAUTION stations:
  delta_speed_mph = mean(obs_sus_mph − bc_speed)
  delta_dir       = circular mean of (obs_dir − bc_dir)
  hrrr_prior      = event-mean bc_speed (HRRR aloft wind)

Features from hrrr_synoptic_features.csv (one row per event):
  w700_speed_mph, mslp_grad (← mslp_grad_pa100km), hrrr_coupling_frac (← _mean)

N = 12 events, one sample per event → 12-fold LOO.
Baseline: delta=0  (use raw HRRR aloft wind directly as BC).

Run: conda run -n hrrr311 python wire_outer_trainer.py
"""

import csv, math, os, sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bc_outer_trainer import load_samples, loeo, print_loeo, BCResidualModel

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
FEAT = os.path.join(BASE, 'hrrr_synoptic_features.csv')
DB   = os.path.join(BASE, 'hrrr_error_dataset.csv')
FC   = os.path.join(BASE, 'flow_coupling_draft.csv')


# ── load event-level synoptic features ───────────────────────────────────────

feat_by_event = {}
with open(FEAT, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            feat_by_event[r['event_id']] = {
                'w700_speed_mph':     float(r['w700_speed_mph']),
                'mslp_grad':          float(r['mslp_grad_pa100km']),   # rename for trainer
                'hrrr_coupling_frac': float(r['hrrr_coupling_frac_mean']),  # rename
                'w700_dir_sin':       float(r['w700_dir_sin']),
                'w700_dir_cos':       float(r['w700_dir_cos']),
                'synoptic_regime':    r['synoptic_regime'],
                'bc_level':           r['bc_level'],
            }
        except (ValueError, KeyError):
            pass

print(f'Synoptic features loaded: {len(feat_by_event)} events')


# ── load flow-coupling classification ────────────────────────────────────────

fc_idx = {}
with open(FC, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        fc_idx[(r['stid'], r['event_id'])] = r['flow_coupling']


# ── aggregate event-level targets from departure database ────────────────────

acc = defaultdict(lambda: {
    'delta_speed': [], 'bc_speed': [], 'obs_speed': [],
    'obs_dir_u': [], 'obs_dir_v': [],
    'bc_dir_u':  [], 'bc_dir_v':  [],
})
n_included = n_skip_fc = n_skip_missing = 0

with open(DB, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
            continue
        fc = fc_idx.get((r['stid'], r['event_id']))
        if fc not in ('coupled', 'intermediate'):
            n_skip_fc += 1
            continue
        try:
            obs = float(r['obs_sus_mph'])
            bc  = float(r['bc_speed'])
            if bc <= 0:
                raise ValueError
        except (ValueError, KeyError):
            n_skip_missing += 1
            continue

        eid = r['event_id']
        acc[eid]['delta_speed'].append(obs - bc)
        acc[eid]['bc_speed'].append(bc)
        acc[eid]['obs_speed'].append(obs)

        try:
            od = float(r['obs_dir_deg'])
            bd = float(r['bc_dir'])
            acc[eid]['obs_dir_u'].append(math.sin(math.radians(od)))
            acc[eid]['obs_dir_v'].append(math.cos(math.radians(od)))
            acc[eid]['bc_dir_u'].append(math.sin(math.radians(bd)))
            acc[eid]['bc_dir_v'].append(math.cos(math.radians(bd)))
        except (ValueError, KeyError):
            pass

        n_included += 1

print(f'Stations included (coupled+intermediate KEEP/CAUTION): {n_included}')
print(f'Skipped (sheltered/unclassified/no coupling tag)     : {n_skip_fc}')
print(f'Skipped (missing bc or obs)                          : {n_skip_missing}')
print()


def circ_mean_deg(us, vs):
    return math.degrees(math.atan2(float(np.mean(us)), float(np.mean(vs)))) % 360.0


# ── build event-level records and display summary table ──────────────────────

records = []
print(f'{"event_id":<28} {"regime":<22} {"bcL":>3} {"N":>3}  '
      f'{"bc_spd":>7} {"obs_spd":>7} {"Δspd":>7}  bc_dir  obs_dir  Δdir')
print('-' * 108)

for eid in sorted(feat_by_event):
    d = acc.get(eid)
    if d is None or len(d['delta_speed']) < 2:
        n = len(d['delta_speed']) if d else 0
        print(f'  {eid:<26} — {n} exposed station(s), skip')
        continue

    feats   = feat_by_event[eid]
    n       = len(d['delta_speed'])
    d_spd   = float(np.mean(d['delta_speed']))
    bc_spd  = float(np.mean(d['bc_speed']))
    obs_spd = float(np.mean(d['obs_speed']))

    d_dir_deg  = 0.0
    bc_dir_str = obs_dir_str = d_dir_str = 'N/A'
    if len(d['bc_dir_u']) >= 2:
        bc_dir    = circ_mean_deg(d['bc_dir_u'],  d['bc_dir_v'])
        obs_dir   = circ_mean_deg(d['obs_dir_u'], d['obs_dir_v'])
        d_dir_deg = ((obs_dir - bc_dir + 180) % 360) - 180
        bc_dir_str  = f'{bc_dir:.0f}°'
        obs_dir_str = f'{obs_dir:.0f}°'
        d_dir_str   = f'{d_dir_deg:+.0f}°'

    print(f'  {eid:<26} {feats["synoptic_regime"]:<22} '
          f'{feats["bc_level"]:>3}  {n:>3}  '
          f'{bc_spd:7.2f} {obs_spd:7.2f} {d_spd:+7.2f}  '
          f'{bc_dir_str:>6} {obs_dir_str:>7}  {d_dir_str}')

    records.append({
        'event': eid,
        'features': {
            'w700_speed_mph':     feats['w700_speed_mph'],
            'mslp_grad':          feats['mslp_grad'],
            'hrrr_coupling_frac': feats['hrrr_coupling_frac'],
        },
        'delta_speed_mph': d_spd,
        'delta_dir_sin':   math.sin(math.radians(d_dir_deg)),
        'delta_dir_cos':   math.cos(math.radians(d_dir_deg)),
        'hrrr_prior_speed_mph': bc_spd,
        'hrrr_prior_dir_deg':   (
            circ_mean_deg(d['bc_dir_u'], d['bc_dir_v'])
            if len(d['bc_dir_u']) >= 2 else 0.0),
    })

print()
print(f'Records built: {len(records)} events (one sample per event)')
print()

if len(records) < 3:
    print('Too few events for LOEO — exit.')
    sys.exit(1)


# ── feature–target correlations (raw, before LOEO) ───────────────────────────

def pearson(a, b):
    a = np.array(a) - np.mean(a); b = np.array(b) - np.mean(b)
    d = math.sqrt(float(np.dot(a,a)) * float(np.dot(b,b)))
    return float(np.dot(a,b)) / d if d > 0 else 0.0

w700s = [r['features']['w700_speed_mph']     for r in records]
mslps = [r['features']['mslp_grad']          for r in records]
cfs   = [r['features']['hrrr_coupling_frac'] for r in records]
dspds = [r['delta_speed_mph']                for r in records]

print('Feature–target Pearson r  (event level, N=' + str(len(records)) + '):')
print(f'  r(w700_speed_mph,    Δspeed) = {pearson(w700s, dspds):+.3f}')
print(f'  r(mslp_grad,         Δspeed) = {pearson(mslps, dspds):+.3f}')
print(f'  r(hrrr_coupling_frac,Δspeed) = {pearson(cfs,   dspds):+.3f}')
print()
print('  Note: with N=12, |r| > 0.58 is p<0.05 (two-tailed); treat correlations cautiously.')
print()


# ── LOEO ──────────────────────────────────────────────────────────────────────

samples = load_samples(records)
result  = loeo(samples, features=['w700_speed_mph', 'mslp_grad', 'hrrr_coupling_frac'], alpha=1.0)
print_loeo(result)


# ── full-data ridge coefficients (descriptive only) ──────────────────────────

print('\nFull-data ridge coefficients (all 12 events, descriptive only):')
model = BCResidualModel(
    features=['w700_speed_mph', 'mslp_grad', 'hrrr_coupling_frac'], alpha=1.0)
model.fit(samples)
for ridge_m, tname in [(model._speed, 'delta_speed'), (model._sin, 'delta_dir_sin')]:
    coefs = dict(zip(['w700', 'mslp', 'cf'], ridge_m.coef_.tolist()))
    print(f'  {tname:<16} intercept={ridge_m.intercept_:+7.3f}  '
          f'w700={coefs["w700"]:+.4f}  mslp={coefs["mslp"]:+.4f}  cf={coefs["cf"]:+.4f}')


# ── feature table sorted by coupling fraction ────────────────────────────────

print('\nEvent features sorted by hrrr_coupling_frac (low=decoupled → large neg delta expected):')
print(f'  {"event_id":<28} {"regime":<22} {"w700":>7} {"mslp_grad":>10}  {"cf":>6}  Δspd')
print('  ' + '-' * 85)
for rec in sorted(records, key=lambda r: r['features']['hrrr_coupling_frac']):
    f  = rec['features']
    rg = feat_by_event[rec['event']]['synoptic_regime']
    print(f'  {rec["event"]:<28} {rg:<22} '
          f'{f["w700_speed_mph"]:7.1f} {f["mslp_grad"]:10.0f}  '
          f'{f["hrrr_coupling_frac"]:6.3f}  {rec["delta_speed_mph"]:+.2f}')
