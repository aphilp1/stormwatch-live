#!/usr/bin/env python3
"""
stage2_profile_features.py
==========================
Stage 2: Test whether HRRR vertical profile features (obs-free) predict the
residual bc/obs spread among exposed stations after time alignment (Stage 1).

Target : bc_over_obs_aligned  (from time_aligned_bc.csv, Station-aligned 850 hPa)
Filter : coupled + intermediate stations (flow_coupling_draft.csv)
Features — NO obs used:
  coupling_ratio  = hrrr_10m_aligned / hrrr_850_aligned   (BL decoupling proxy)
  shear_925_850   = hrrr_925_mph_aligned - hrrr_850_mph_aligned
  shear_700_850   = hrrr_700_mph_aligned - hrrr_850_mph_aligned

Null model: predict bc_over_obs = 1.0 for every station (physical null = perfect coupling)
LOEO: leave-one-event-out, events as grouping unit (~6 events, ~40-65 exposed rows)

Run: conda run -n hrrr311 python stage2_profile_features.py
"""

import csv, datetime, math, os, sys
import numpy as np
from collections import defaultdict
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
CACHE = os.path.join(BASE, 'hrrr_bc_cache')
OUT   = os.path.join(BASE, 'stage2_profile_features.csv')

MS_MPH = 2.23694
os.makedirs(CACHE, exist_ok=True)


# ── load and join ─────────────────────────────────────────────────────────────

def load_aligned(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def load_coupling(csv_path):
    idx = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            idx[(r['stid'], r['event_id'])] = r['flow_coupling']
    return idx


aligned_rows = load_aligned(os.path.join(BASE, 'time_aligned_bc.csv'))
coupling_idx = load_coupling(os.path.join(BASE, 'flow_coupling_draft.csv'))

# Attach flow_coupling; filter to exposed (coupled/intermediate)
exposed = []
missing_coupling = 0
for r in aligned_rows:
    fc = coupling_idx.get((r['stid'], r['event_id']))
    if fc is None:
        missing_coupling += 1
        continue
    if fc not in ('coupled', 'intermediate'):
        continue
    try:
        bco = float(r['bc_over_obs_aligned'])
        bc850 = float(r['bc_speed_aligned'])
        lat = float(r['lat'])
        lon = float(r['lon'])
    except (ValueError, KeyError):
        continue
    if bc850 <= 0:
        continue
    dt_str = r['peak_dt_utc']
    dt_h = datetime.datetime.fromisoformat(dt_str.replace('Z', '')).replace(
        minute=0, second=0, microsecond=0)
    exposed.append({
        'stid':       r['stid'],
        'event_id':   r['event_id'],
        'regime':     r['synoptic_regime'],
        'flow_coupling': fc,
        'peak_dt_h':  dt_h,
        'lat':        lat,
        'lon':        lon,
        'bc850':      bc850,
        'bco':        bco,
    })

print(f'Total time_aligned rows : {len(aligned_rows)}')
print(f'Missing from coupling   : {missing_coupling}')
print(f'Exposed (coupled+interm): {len(exposed)}')
from collections import Counter
print('Events:', Counter(r['event_id'] for r in exposed))
print('Flow coupling breakdown:', Counter(r['flow_coupling'] for r in exposed))
print()


# ── HRRR pull helpers ─────────────────────────────────────────────────────────

def pull_uv(peak_dt, product, search_re, cache_dir):
    H = Herbie(peak_dt, model='hrrr', product=product, fxx=0,
               save_dir=cache_dir, verbose=False)
    return H.xarray(search_re, remove_grib=False)


def extract_speed_at(ds, lat, lon):
    """Nearest-neighbour speed (mph) from U/V dataset at (lat, lon)."""
    if not hasattr(ds, 'data_vars'):
        raise ValueError(f'Expected Dataset, got {type(ds)}')
    vars_ = list(ds.data_vars)
    u_da = ds[vars_[0]]
    v_da = ds[vars_[1]]

    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    if grid_lon.min() > 0 and lon < 0:
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    dist, idx = tree.query([lat, lon])
    if dist > 1.0:
        return None
    u = float(u_da.values.ravel()[idx])
    v = float(v_da.values.ravel()[idx])
    return math.sqrt(u**2 + v**2) * MS_MPH


# ── group by unique hour and pull HRRR ───────────────────────────────────────

# unique hours per event (one HRRR file serves all stations with same peak hour)
unique_hours = sorted(set(r['peak_dt_h'] for r in exposed))
print(f'Unique aligned hours to pull: {len(unique_hours)}  '
      f'(vs {len(set(r["event_id"] for r in exposed))} event-medians)')
print()

# Cache pulled datasets keyed by (peak_dt_h, product, level)
# key: (dt, 'sfc_10m') or (dt, 'prs_925') or (dt, 'prs_700')
ds_cache = {}

def get_ds(peak_dt, key, product, search_re):
    if key not in ds_cache:
        try:
            ds_cache[key] = pull_uv(peak_dt, product, search_re, CACHE)
        except Exception as ex:
            ds_cache[key] = None
            print(f'  PULL FAIL {key}: {ex}')
    return ds_cache[key]


# ── extract profile for each station ─────────────────────────────────────────

OUT_FIELDS = [
    'event_id', 'stid', 'regime', 'flow_coupling', 'peak_dt_utc',
    'lat', 'lon', 'bc850', 'bco',
    'hrrr_10m_aligned', 'hrrr_925_aligned', 'hrrr_700_aligned',
    'coupling_ratio', 'shear_925_850', 'shear_700_850',
    'notes',
]

results = []
n_ok = 0
n_fail = 0

for i, r in enumerate(exposed):
    dt = r['peak_dt_h']
    lat, lon = r['lat'], r['lon']
    bc850 = r['bc850']

    k10  = (dt, 'sfc_10m')
    k925 = (dt, 'prs_925')
    k700 = (dt, 'prs_700')

    # Show progress for each unique hour on first encounter
    if k10 not in ds_cache:
        print(f'[{i+1}/{len(exposed)}] Pulling {dt.strftime("%Y-%m-%d %HZ")} '
              f'({r["event_id"]})...', end=' ', flush=True)

    ds10  = get_ds(dt, k10,  'sfc', r':(?:UGRD|VGRD):10 m above ground:')
    ds925 = get_ds(dt, k925, 'prs', r':(?:UGRD|VGRD):925 mb:')
    ds700 = get_ds(dt, k700, 'prs', r':(?:UGRD|VGRD):700 mb:')

    if k10 not in [k for k, _ in [('placeholder', 'done')]]:
        pass  # progress already printed above when we set ds_cache

    notes = []
    spd10, spd925, spd700 = None, None, None

    if ds10 is not None:
        try:
            spd10 = extract_speed_at(ds10, lat, lon)
        except Exception as ex:
            notes.append(f'10m_ex:{ex}')
    else:
        notes.append('10m_pull_fail')

    if ds925 is not None:
        try:
            spd925 = extract_speed_at(ds925, lat, lon)
        except Exception as ex:
            notes.append(f'925_ex:{ex}')
    else:
        notes.append('925_pull_fail')

    if ds700 is not None:
        try:
            spd700 = extract_speed_at(ds700, lat, lon)
        except Exception as ex:
            notes.append(f'700_ex:{ex}')
    else:
        notes.append('700_pull_fail')

    # features
    cr     = (spd10  / bc850) if (spd10  is not None and bc850 > 0) else None
    sh925  = (spd925 - bc850) if  spd925 is not None               else None
    sh700  = (spd700 - bc850) if  spd700 is not None               else None

    row_out = {
        'event_id':         r['event_id'],
        'stid':             r['stid'],
        'regime':           r['regime'],
        'flow_coupling':    r['flow_coupling'],
        'peak_dt_utc':      dt.strftime('%Y-%m-%dT%H:00:00'),
        'lat':              f'{lat:.5f}',
        'lon':              f'{lon:.5f}',
        'bc850':            f'{bc850:.3f}',
        'bco':              f'{r["bco"]:.4f}',
        'hrrr_10m_aligned': f'{spd10:.3f}'  if spd10  is not None else 'FAIL',
        'hrrr_925_aligned': f'{spd925:.3f}' if spd925 is not None else 'FAIL',
        'hrrr_700_aligned': f'{spd700:.3f}' if spd700 is not None else 'FAIL',
        'coupling_ratio':   f'{cr:.4f}'  if cr    is not None else 'FAIL',
        'shear_925_850':    f'{sh925:.3f}' if sh925 is not None else 'FAIL',
        'shear_700_850':    f'{sh700:.3f}' if sh700 is not None else 'FAIL',
        'notes':            ' '.join(notes),
    }
    results.append(row_out)

    if all(x is not None for x in [spd10, spd925, spd700]):
        n_ok += 1
    else:
        n_fail += 1

# Flush a newline after the progress dots
print()

# Print a per-event summary of pulls
print('\nPull summary:')
for evt in sorted(set(r['event_id'] for r in results)):
    sub = [r for r in results if r['event_id'] == evt]
    ok_10  = sum(1 for r in sub if r['hrrr_10m_aligned']  != 'FAIL')
    ok_925 = sum(1 for r in sub if r['hrrr_925_aligned']  != 'FAIL')
    ok_700 = sum(1 for r in sub if r['hrrr_700_aligned']  != 'FAIL')
    print(f'  {evt:<28} N={len(sub):2d}  '
          f'10m:{ok_10:2d}/{len(sub)}  925:{ok_925:2d}/{len(sub)}  700:{ok_700:2d}/{len(sub)}')

# Write CSV
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)
print(f'\nWritten: {OUT}  ({n_ok} fully OK, {n_fail} partial/fail)')


# ── LOEO ─────────────────────────────────────────────────────────────────────

print('\n' + '=' * 68)
print('LEAVE-ONE-EVENT-OUT (LOEO) — bc_over_obs_aligned ~ profile features')
print('Null model: predict 1.0 (physical null = perfect coupling)')
print('Circularity guard: NO obs used in features')
print('=' * 68)

# Build complete-case dataset (all 3 features present)
cc = []
for r in results:
    try:
        bco = float(r['bco'])
        cr  = float(r['coupling_ratio'])
        s92 = float(r['shear_925_850'])
        s70 = float(r['shear_700_850'])
        cc.append({
            'event_id': r['event_id'],
            'stid':     r['stid'],
            'regime':   r['regime'],
            'bco':      bco,
            'cr':       cr,
            's92':      s92,
            's70':      s70,
        })
    except (ValueError, KeyError):
        continue

events_cc = sorted(set(r['event_id'] for r in cc))
print(f'\nComplete-case rows: {len(cc)} across {len(events_cc)} events')
for e in events_cc:
    sub = [r for r in cc if r['event_id'] == e]
    bcos = [r['bco'] for r in sub]
    print(f'  {e:<28} N={len(sub):2d}  '
          f'bco=[{min(bcos):.2f},{max(bcos):.2f}]  mean={sum(bcos)/len(bcos):.3f}')

if len(events_cc) < 3:
    print('\nToo few events for LOEO — exit')
    sys.exit(0)

# LOEO
null_sq_errors  = []
loeo_sq_errors  = []
loeo_predictions = []

print('\n--- LOEO folds ---')
for held_out in events_cc:
    train = [r for r in cc if r['event_id'] != held_out]
    test  = [r for r in cc if r['event_id'] == held_out]

    # Build design matrix (intercept + 3 features)
    def build_X(rows_):
        return np.column_stack([
            np.ones(len(rows_)),
            [r['cr']  for r in rows_],
            [r['s92'] for r in rows_],
            [r['s70'] for r in rows_],
        ])

    y_train = np.array([r['bco'] for r in train])
    y_test  = np.array([r['bco'] for r in test])
    X_train = build_X(train)
    X_test  = build_X(test)

    # Least-squares fit on training fold
    coef, res, rank, sv = np.linalg.lstsq(X_train, y_train, rcond=None)
    pred = X_test @ coef

    fold_loeo_mse  = float(np.mean((pred   - y_test) ** 2))
    fold_null_mse  = float(np.mean((np.ones_like(y_test) - y_test) ** 2))
    fold_rmse_l    = math.sqrt(fold_loeo_mse)
    fold_rmse_n    = math.sqrt(fold_null_mse)

    print(f'  held={held_out:<28} N_test={len(test):2d}  '
          f'null_RMSE={fold_rmse_n:.3f}  loeo_RMSE={fold_rmse_l:.3f}  '
          f'{"BEAT" if fold_rmse_l < fold_rmse_n else "null wins"}')

    null_sq_errors.extend((np.ones_like(y_test) - y_test).tolist())
    loeo_sq_errors.extend((pred - y_test).tolist())
    loeo_predictions += [
        {'event_id': r['event_id'], 'stid': r['stid'],
         'bco_actual': r['bco'], 'bco_pred': float(p),
         'null_err': 1.0 - r['bco'], 'loeo_err': float(p) - r['bco']}
        for r, p in zip(test, pred)
    ]

overall_null_rmse = math.sqrt(np.mean(np.array(null_sq_errors)**2))
overall_loeo_rmse = math.sqrt(np.mean(np.array(loeo_sq_errors)**2))

# Full-data fit for coefficient reporting
X_all = build_X(cc)
y_all = np.array([r['bco'] for r in cc])
coef_full, _, _, _ = np.linalg.lstsq(X_all, y_all, rcond=None)

print(f'\n--- Overall ---')
print(f'  Null RMSE  (predict 1.0) : {overall_null_rmse:.4f}')
print(f'  LOEO RMSE               : {overall_loeo_rmse:.4f}')
skill = 1.0 - (overall_loeo_rmse / overall_null_rmse)
print(f'  Skill vs null           : {skill:+.3f}  '
      f'(positive = profile helps, negative = profile hurts)')

print(f'\n--- Full-data OLS coefficients (not for prediction — LOEO is the test) ---')
print(f'  intercept      : {coef_full[0]:+.4f}')
print(f'  coupling_ratio : {coef_full[1]:+.4f}  (hrrr_10m/hrrr_850)')
print(f'  shear_925_850  : {coef_full[2]:+.4f}  mph')
print(f'  shear_700_850  : {coef_full[3]:+.4f}  mph')

# Feature correlation with target
cr_vals  = np.array([r['cr']  for r in cc])
s92_vals = np.array([r['s92'] for r in cc])
s70_vals = np.array([r['s70'] for r in cc])
bco_vals = np.array([r['bco'] for r in cc])

def pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    denom = np.sqrt((a**2).sum() * (b**2).sum())
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0

print(f'\n--- Feature–target correlations (r, station level) ---')
print(f'  r(coupling_ratio, bco)  = {pearson(cr_vals,  bco_vals):+.3f}')
print(f'  r(shear_925_850,  bco)  = {pearson(s92_vals, bco_vals):+.3f}')
print(f'  r(shear_700_850,  bco)  = {pearson(s70_vals, bco_vals):+.3f}')

# Distribution of bco in exposed stations
print(f'\n--- Aligned bc/obs distribution (exposed stations, complete cases) ---')
print(f'  N={len(bco_vals)}  mean={bco_vals.mean():.3f}  '
      f'median={float(np.median(bco_vals)):.3f}  '
      f'std={bco_vals.std():.3f}  '
      f'min={bco_vals.min():.3f}  max={bco_vals.max():.3f}')
print(f'  Fraction > 1.0 : {(bco_vals > 1.0).sum()/len(bco_vals):.2%}')
print(f'  Fraction < 0.8 : {(bco_vals < 0.8).sum()/len(bco_vals):.2%}')

print('\n' + '=' * 68)
print('VERDICT:')
if skill > 0.10:
    print('  SIGNAL — profile features predict > 10% RMSE reduction vs null.')
    print('  Stage 2 pipeline warranted. Check coefficient signs for physics.')
elif skill > 0.0:
    print('  WEAK SIGNAL — LOEO beats null by < 10%. Marginal.')
else:
    print('  NULL — profile features do not predict bc/obs after time-alignment.')
    print('  Interpretation: at exposed stations, HRRR 850 hPa couples correctly')
    print('  on average. No vertical-profile BC correction needed for this regime.')
print('=' * 68)
