#!/usr/bin/env python3
"""
add_coupling_frac.py
====================
Compute hrrr_coupling_frac = hrrr_10m_mph / bc_speed for every KEEP/CAUTION
station-event in the departure database and write it back as a new column.

Also computes the event-mean coupling fraction and verifies it predicts the
event-level bc/obs ratio (the signal identified from the Thomas/Woolsey analysis).

hrrr_coupling_frac interpretation:
  low  (< 0.5)  -> HRRR heavily decoupled; 850 hPa far above surface.
                   bc_speed >> obs likely; WN will overcorrect with raw BC.
  high (> 0.8)  -> HRRR near-coupled; 850 hPa close to surface.
                   bc_speed ≈ obs likely; WN performance tied to terrain accuracy.

The event-mean of this field is the feature for the outer BC regressor.
"""

import csv, os, shutil, sys
import numpy as np
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'

def process(fname):
    path = os.path.join(BASE, fname)
    bak  = path + '.pre_coupling_frac.bak'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
        fields = reader.fieldnames

    if 'hrrr_coupling_frac' not in fields:
        fields = list(fields) + ['hrrr_coupling_frac']

    n_set = n_skip = 0
    for row in rows:
        if row.get('qc_flag') not in ('KEEP', 'CAUTION'):
            row['hrrr_coupling_frac'] = ''
            n_skip += 1
            continue
        try:
            h10 = float(row['hrrr_10m_mph'])
            bc  = float(row['bc_speed'])
            if bc <= 0:
                raise ValueError
            row['hrrr_coupling_frac'] = f'{h10/bc:.4f}'
            n_set += 1
        except:
            row['hrrr_coupling_frac'] = ''
            n_skip += 1

    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f'  {fname}: set={n_set}  skipped={n_skip}')
    return rows, fields

# ── Write both CSVs ───────────────────────────────────────────────────────────
print('Writing coupling fraction to database...')
rows_src, _ = process('hrrr_error_dataset.csv')
rows_dem, _ = process('hrrr_error_dataset_dem.csv')
print()

# ── Verify the signal ─────────────────────────────────────────────────────────
# Compute event-mean coupling_frac and event-mean bc/obs.
# If the signal is real, these should correlate strongly.

print('SIGNAL CHECK: event-mean coupling_frac vs event-mean bc/obs')
print('(positive correlation expected: decoupled events have both high bc and low obs)')
print()

event_cf  = defaultdict(list)   # coupling frac values per event
event_bco = defaultdict(list)   # bc/obs values per event
event_se  = defaultdict(list)   # speed_err values per event

for row in rows_src:
    if row.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    cf  = row.get('hrrr_coupling_frac')
    bc  = row.get('bc_speed')
    obs = row.get('obs_sus_mph')
    se  = row.get('speed_err')
    eid = row.get('event_id')
    try:
        event_cf[eid].append(float(cf))
        event_bco[eid].append(float(bc) / float(obs))
        event_se[eid].append(float(se))
    except:
        pass

events = sorted(event_cf)
cf_means  = np.array([np.mean(event_cf[e])  for e in events])
bco_means = np.array([np.mean(event_bco[e]) for e in events])
se_means  = np.array([np.mean(event_se[e])  for e in events])

r_cf_bco = np.corrcoef(cf_means, bco_means)[0, 1]
r_cf_se  = np.corrcoef(cf_means, se_means)[0, 1]

print(f"{'event':<28} {'N':>3}  {'cf_mean':>8} {'bc/obs':>7} {'se_mean':>8}")
print('-' * 60)
for e, cf, bco, se in zip(events, cf_means, bco_means, se_means):
    n = len(event_cf[e])
    print(f"  {e:<26} {n:>3}  {cf:>8.3f} {bco:>7.3f} {se:>+8.2f}")

print()
print(f"Pearson r(cf_mean, bc/obs_mean):  {r_cf_bco:+.3f}")
print(f"Pearson r(cf_mean, se_mean):      {r_cf_se:+.3f}")
print()

if abs(r_cf_bco) >= 0.60:
    print('SIGNAL CONFIRMED: |r| >= 0.60 between event coupling fraction and bc/obs.')
    print('hrrr_coupling_frac is a valid predictor for the outer BC regressor.')
elif abs(r_cf_bco) >= 0.40:
    print('MODERATE SIGNAL: |r| in [0.40, 0.60). Worth including, but weak at event N.')
else:
    print('WEAK SIGNAL: |r| < 0.40. Re-examine feature or event groupings before adding.')
print()

# ── Regime breakdown ──────────────────────────────────────────────────────────
print('COUPLING FRACTION BY SYNOPTIC REGIME (all stations):')
regime_cf = defaultdict(list)
for row in rows_src:
    if row.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    cf = row.get('hrrr_coupling_frac')
    if not cf:
        continue
    regime = row.get('synoptic_regime', 'unknown')
    regime_cf[regime].append(float(cf))

for reg in sorted(regime_cf, key=lambda r: np.mean(regime_cf[r])):
    vals = regime_cf[reg]
    print(f"  {reg:<28} N={len(vals):>3}  mean={np.mean(vals):.3f}  "
          f"median={np.median(vals):.3f}  "
          f"p10={np.percentile(vals,10):.3f}  p90={np.percentile(vals,90):.3f}")
