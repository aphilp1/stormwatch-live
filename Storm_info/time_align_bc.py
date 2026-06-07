#!/usr/bin/env python3
"""
time_align_bc.py  —  Stage 1: time-align bc/obs for offshore+SA events
=======================================================================
Current state: bc_speed in hrrr_error_dataset.csv was pulled at the
EVENT-MEDIAN peak hour for all stations in an event (hrrr_bc_pull.py
uses the median of station peak_dt_utc values). This means stations that
peaked far from the event median get bc from the wrong HRRR hour.

Fix: re-pull HRRR 850 hPa at each station's OWN peak_dt_utc (floored to
the nearest analysis hour). Recompute bc/obs and hrrr_coupling_frac with
the time-aligned bc.

Scope: offshore+santa_ana regimes (bc_level=850) only.
       Continental events excluded (sign inverts; separate analysis if needed).

Output:
  time_aligned_bc.csv   — station-level, before/after comparison
  (does NOT modify hrrr_error_dataset.csv — read-only on the database)

Run:  conda run -n hrrr311 python time_align_bc.py
"""

import csv, datetime, math, os, sys
import numpy as np
from collections import defaultdict
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE   = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
CACHE  = os.path.join(BASE, 'hrrr_bc_cache')
OUT    = os.path.join(BASE, 'time_aligned_bc.csv')
MS_MPH = 2.23694

OFFSHORE_SA_REGIMES = {
    'diablo_offshore', 'diablo_offshore_NW', 'diablo_offshore_NE', 'santa_ana'
}

os.makedirs(CACHE, exist_ok=True)

# ── load departure database ───────────────────────────────────────────────────

rows_db = []
with open(os.path.join(BASE, 'hrrr_error_dataset.csv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
            continue
        if r.get('synoptic_regime', '') not in OFFSHORE_SA_REGIMES:
            continue
        try:
            float(r['speed_err'])
            float(r['bc_speed'])
            float(r['obs_sus_mph'])
        except Exception:
            continue
        rows_db.append(r)

print(f'Offshore+SA rows loaded: {len(rows_db)}')

# ── compute event-median times (reproduces hrrr_bc_pull.py logic) ────────────
# This is what bc_speed was pulled at — we'll compare against it.

by_event_dts = defaultdict(list)
for r in rows_db:
    try:
        dt = datetime.datetime.fromisoformat(
            r['peak_dt_utc'].replace('Z', '+00:00'))
        by_event_dts[r['event_id']].append(
            dt.replace(minute=0, second=0, microsecond=0, tzinfo=None))
    except Exception:
        pass

event_medians = {}
for eid, dts in by_event_dts.items():
    dts_s = sorted(dts)
    event_medians[eid] = dts_s[len(dts_s) // 2]

print('Event-median times (what the current bc_speed was pulled at):')
for eid in sorted(event_medians):
    print(f'  {eid:<30} {event_medians[eid]}')
print()

# Annotate each row with its offset from event-median
for r in rows_db:
    med = event_medians.get(r['event_id'])
    try:
        dt = datetime.datetime.fromisoformat(
            r['peak_dt_utc'].replace('Z', '+00:00'))
        dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
        r['_peak_dt_h'] = dt_h
        r['_offset_h'] = round((dt_h - med).total_seconds() / 3600) if med else None
    except Exception:
        r['_peak_dt_h'] = None
        r['_offset_h'] = None

# ── identify unique (peak_dt_floored, bc_level) pairs to pull ────────────────

pull_groups = defaultdict(list)   # (peak_dt_h, bc_level) → [row, ...]
for r in rows_db:
    if r['_peak_dt_h'] is None:
        continue
    bc_level = int(r.get('bc_level', 850))
    key = (r['_peak_dt_h'], bc_level)
    pull_groups[key].append(r)

print(f'Unique HRRR pulls required: {len(pull_groups)}  '
      f'(vs {len(event_medians)} with event-median approach)')
print()


# ── herbie pull + extraction ──────────────────────────────────────────────────

def pull_850_uv(peak_dt, level_hpa, cache_dir):
    search = f':(?:UGRD|VGRD):{level_hpa} mb:'
    H = Herbie(peak_dt, model='hrrr', product='prs', fxx=0,
               save_dir=cache_dir, verbose=False)
    return H.xarray(search, remove_grib=False)


def extract_at_stations(ds, lats, lons):
    if not hasattr(ds, 'data_vars'):
        raise ValueError(f'Expected Dataset, got {type(ds)}')
    vars_ = list(ds.data_vars)
    u_name = next((v for v in vars_ if 'u' in v.lower() and 'grd' in v.lower()), vars_[0])
    v_name = next((v for v in vars_ if 'v' in v.lower() and 'grd' in v.lower()), vars_[1])
    u_da = ds[u_name]
    v_da = ds[v_name]

    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    if grid_lon.min() > 0 and any(ln < 0 for ln in lons):
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    u_flat = u_da.values.ravel()
    v_flat = v_da.values.ravel()

    results = []
    for lat, lon in zip(lats, lons):
        dist, idx = tree.query([lat, lon])
        if dist > 1.0:
            results.append((None, None))
            continue
        u = float(u_flat[idx])
        v = float(v_flat[idx])
        spd = math.sqrt(u ** 2 + v ** 2) * MS_MPH
        d = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
        results.append((spd, d))
    return results


# Pull and extract
n_ok = n_fail = 0
for (peak_dt_h, bc_level), group_rows in sorted(pull_groups.items()):
    lats  = [float(r['lat'])  for r in group_rows]
    lons  = [float(r['lon'])  for r in group_rows]
    try:
        ds = pull_850_uv(peak_dt_h, bc_level, CACHE)
        spd_dir = extract_at_stations(ds, lats, lons)
        for row, (spd, d) in zip(group_rows, spd_dir):
            row['_bc_aligned']      = spd
            row['_bc_dir_aligned']  = d
        n_ok += 1
    except Exception as ex:
        for row in group_rows:
            row['_bc_aligned']     = None
            row['_bc_dir_aligned'] = None
        print(f'  PULL FAIL  {peak_dt_h}  {bc_level}hPa  → {ex}')
        n_fail += 1

print(f'Pulls: {n_ok} OK  /  {n_fail} FAIL')
print()


# ── compute before/after ratios ───────────────────────────────────────────────

for r in rows_db:
    try:
        obs   = float(r['obs_sus_mph'])
        bc_old = float(r['bc_speed'])
        h10   = float(r['hrrr_10m_mph'])
        r['_bco_old'] = bc_old / obs if obs > 0 else None
        r['_cf_old']  = h10 / bc_old  if bc_old > 0 else None
    except Exception:
        r['_bco_old'] = r['_cf_old'] = None

    bc_new = r.get('_bc_aligned')
    try:
        obs = float(r['obs_sus_mph'])
        r['_bco_new'] = bc_new / obs if (bc_new is not None and obs > 0) else None
        h10 = float(r['hrrr_10m_mph'])
        r['_cf_new']  = h10 / bc_new if (bc_new is not None and bc_new > 0) else None
    except Exception:
        r['_bco_new'] = r['_cf_new'] = None


# ── write output CSV ──────────────────────────────────────────────────────────

OUT_FIELDS = [
    'event_id','stid','synoptic_regime','peak_dt_utc','offset_h',
    'obs_sus_mph','hrrr_10m_mph','speed_err',
    'bc_speed_old','bc_speed_aligned','bc_delta',
    'bc_over_obs_old','bc_over_obs_aligned','bco_delta',
    'cf_old','cf_aligned',
    'bc_level','lat','lon',
]

with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction='ignore')
    w.writeheader()
    for r in rows_db:
        bc_old  = float(r['bc_speed'])
        bc_new  = r.get('_bc_aligned')
        bco_old = r.get('_bco_old')
        bco_new = r.get('_bco_new')
        w.writerow({
            'event_id':         r['event_id'],
            'stid':             r['stid'],
            'synoptic_regime':  r['synoptic_regime'],
            'peak_dt_utc':      r['peak_dt_utc'],
            'offset_h':         r.get('_offset_h', ''),
            'obs_sus_mph':      r['obs_sus_mph'],
            'hrrr_10m_mph':     r['hrrr_10m_mph'],
            'speed_err':        r['speed_err'],
            'bc_speed_old':     f'{bc_old:.2f}',
            'bc_speed_aligned': f'{bc_new:.2f}' if bc_new is not None else 'FAIL',
            'bc_delta':         f'{bc_new - bc_old:+.2f}' if bc_new is not None else '',
            'bc_over_obs_old':  f'{bco_old:.3f}' if bco_old is not None else '',
            'bc_over_obs_aligned': f'{bco_new:.3f}' if bco_new is not None else 'FAIL',
            'bco_delta':        f'{bco_new - bco_old:+.3f}' if (bco_new and bco_old) else '',
            'cf_old':           f'{r["_cf_old"]:.4f}' if r.get("_cf_old") else '',
            'cf_aligned':       f'{r["_cf_new"]:.4f}' if r.get("_cf_new") else '',
            'bc_level':         r.get('bc_level',''),
            'lat':              r.get('lat',''),
            'lon':              r.get('lon',''),
        })

print(f'Written: {OUT}')
print()


# ── Stage 1 report ────────────────────────────────────────────────────────────

def report_event(eid, rows):
    erows = [r for r in rows if r['event_id'] == eid]
    med   = event_medians.get(eid)
    print(f'=== {eid} (event-median bc was at {med}) ===')
    print(f"  {'stid':<8} {'off':>5}h  {'obs':>6} {'bc_old':>7} {'bc_new':>7} "
          f"{'Δbc':>6}  {'bco_old':>7} {'bco_new':>7}  {'Δbco':>7}  note")
    print('  ' + '-' * 90)

    for r in sorted(erows, key=lambda x: abs(x.get('_offset_h') or 0), reverse=True):
        bc_old  = float(r['bc_speed'])
        bc_new  = r.get('_bc_aligned')
        bco_old = r.get('_bco_old')
        bco_new = r.get('_bco_new')
        off     = r.get('_offset_h', '?')
        obs_v   = float(r['obs_sus_mph'])

        bc_new_s  = f'{bc_new:.1f}'  if bc_new  is not None else 'FAIL'
        dbc_s     = f'{bc_new-bc_old:+.1f}' if bc_new is not None else ''
        bco_new_s = f'{bco_new:.3f}' if bco_new is not None else 'FAIL'
        dbco_s    = f'{bco_new-bco_old:+.3f}' if (bco_new and bco_old) else ''

        note = ''
        if isinstance(off, int) and abs(off) >= 24:
            note += f'LARGE_OFFSET({off:+d}h)'
        if bco_old is not None and bco_old > 3.0:
            note += ' HIGH_BCO'

        stid = r['stid']
        flag = ' <--' if stid in ('TCLC1','MOIC1','WMSC1','GMTC1') else ''
        print(f"  {stid:<8} {str(off):>5}h  {obs_v:>6.1f} {bc_old:>7.1f} {bc_new_s:>7}  "
              f"{dbc_s:>6}  {bco_old:>7.3f} {bco_new_s:>7}  {dbco_s:>7}  {note}{flag}")

    print()

    # Distribution summary
    bco_old_vals = [r['_bco_old'] for r in erows if r.get('_bco_old') is not None]
    bco_new_vals = [r['_bco_new'] for r in erows if r.get('_bco_new') is not None]
    n = len(bco_new_vals)
    if bco_old_vals and bco_new_vals:
        print(f'  bc/obs DISTRIBUTION (N={n}):')
        print(f'  {"metric":<12}  {"BEFORE (event-median bc)":>26}  {"AFTER (station-aligned bc)":>26}')
        print(f'  {"":<12}  {"mean":>6} {"median":>7} {"p75":>5} {"above1":>7}  '
              f'{"mean":>6} {"median":>7} {"p75":>5} {"above1":>7}')
        print('  ' + '-' * 70)
        for lbl, vals_o, vals_n in [('all', bco_old_vals, bco_new_vals)]:
            m_o = np.mean(vals_o);    med_o = np.median(vals_o)
            p75_o = np.percentile(vals_o, 75)
            ab1_o = sum(1 for x in vals_o if x > 1) / len(vals_o) * 100
            m_n = np.mean(vals_n);    med_n = np.median(vals_n)
            p75_n = np.percentile(vals_n, 75)
            ab1_n = sum(1 for x in vals_n if x > 1) / len(vals_n) * 100
            print(f'  {lbl:<12}  {m_o:>6.3f} {med_o:>7.3f} {p75_o:>5.2f} {ab1_o:>6.0f}%  '
                  f'{m_n:>6.3f} {med_n:>7.3f} {p75_n:>5.2f} {ab1_n:>6.0f}%')
    print()


report_event('thomas_2017', rows_db)
report_event('woolsey_2018', rows_db)


# ── Cross-event summary: does the Thomas-decoupled / Woolsey-mixed split survive? ──

print('=' * 72)
print('STAGE 1 SUMMARY: does the Thomas-decoupled / Woolsey-mixed split survive?')
print('=' * 72)
print()
print(f"{'event':<18}  {'N':>3}  {'BEFORE':>22}  {'AFTER':>22}  {'verdict'}")
print(f"{'':18}  {'':3}  {'mean':>6} {'med':>6} {'%>1':>6}  {'mean':>6} {'med':>6} {'%>1':>6}")
print('-' * 80)

for eid in ('thomas_2017', 'woolsey_2018'):
    erows = [r for r in rows_db if r['event_id'] == eid]
    bco_o = [r['_bco_old'] for r in erows if r.get('_bco_old') is not None]
    bco_n = [r['_bco_new'] for r in erows if r.get('_bco_new') is not None]
    if not bco_n:
        continue
    m_o  = np.mean(bco_o);   med_o = np.median(bco_o)
    ab1_o = sum(1 for x in bco_o if x > 1) / len(bco_o) * 100
    m_n  = np.mean(bco_n);   med_n = np.median(bco_n)
    ab1_n = sum(1 for x in bco_n if x > 1) / len(bco_n) * 100

    delta_med = med_n - med_o
    # Survival criterion: Thomas should stay > Woolsey median after alignment
    print(f'  {eid:<16}  {len(bco_n):>3}  {m_o:>6.3f} {med_o:>6.3f} {ab1_o:>5.0f}%  '
          f'{m_n:>6.3f} {med_n:>6.3f} {ab1_n:>5.0f}%  Δmedian={delta_med:+.3f}')

print()

# Check if Thomas bc/obs median still exceeds Woolsey after alignment
thomas_new = [r['_bco_new'] for r in rows_db
              if r['event_id'] == 'thomas_2017' and r.get('_bco_new') is not None]
woolsey_new = [r['_bco_new'] for r in rows_db
               if r['event_id'] == 'woolsey_2018' and r.get('_bco_new') is not None]

if thomas_new and woolsey_new:
    t_med = np.median(thomas_new)
    w_med = np.median(woolsey_new)
    gap   = t_med - w_med
    if gap > 0.3:
        verdict = (f'SIGNAL SURVIVES: Thomas median ({t_med:.3f}) still exceeds '
                   f'Woolsey ({w_med:.3f}) by {gap:.3f}. Proceed to Stage 2.')
    elif gap > 0:
        verdict = (f'WEAK SURVIVAL: gap = {gap:.3f}. '
                   f'Thomas ({t_med:.3f}) > Woolsey ({w_med:.3f}) but marginal.')
    else:
        verdict = (f'SIGNAL COLLAPSES: after alignment Thomas ({t_med:.3f}) no longer '
                   f'exceeds Woolsey ({w_med:.3f}). Stop; timing was the artifact.')
    print(verdict)
