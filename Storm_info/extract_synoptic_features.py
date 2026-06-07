#!/usr/bin/env python3
"""
extract_synoptic_features.py
============================
Extract per-event synoptic features from HRRR for the outer BC trainer.

For each of the 12 analysis events, pulls two HRRR f00 products at the
event peak hour (floored to the nearest analysis hour):

  prs product : UGRD/VGRD at 700 mb
      → w700_speed_mph, w700_dir_deg, w700_dir_sin, w700_dir_cos
        (centroid nearest-neighbor; 700 hPa always, regardless of bc_level)

  sfc product : PRMSL (mean sea level pressure)
      → mslp_grad_pa100km  = mean |∇MSLP| over ±2.5° domain box

Also aggregates hrrr_coupling_frac_mean from the departure database
(event-mean of the per-station column written by add_coupling_frac.py).

Output: Storm_info/hrrr_synoptic_features.csv  (one row per event)
This is the event-level feature matrix for bc_outer_trainer.py.

Run:  conda run -n hrrr311 python extract_synoptic_features.py
"""

import csv, datetime, math, os, sys
import numpy as np
from collections import defaultdict
from herbie import Herbie
from scipy.spatial import KDTree

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE   = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
CACHE  = os.path.join(BASE, 'hrrr_bc_cache')
OUT    = os.path.join(BASE, 'hrrr_synoptic_features.csv')
MS_MPH = 2.23694

os.makedirs(CACHE, exist_ok=True)

REGIME_BC = {
    'diablo_offshore':       850,
    'diablo_offshore_NW':    850,
    'diablo_offshore_NE':    850,
    'santa_ana':             850,
    'chinook_frontrange':    700,
    'downslope_oregon':      700,
    'continental_downslope': 700,
    'frontal_passage':       700,
    'convective_outflow':    850,
}

FIELDS = [
    'event_id', 'synoptic_regime', 'bc_level', 'peak_dt_utc',
    'domain_lat', 'domain_lon', 'n_stations',
    'w700_speed_mph', 'w700_dir_deg', 'w700_dir_sin', 'w700_dir_cos',
    'mslp_grad_pa100km',
    'hrrr_coupling_frac_mean',
    'notes',
]


# ── load events from departure database ───────────────────────────────────────

def load_events(csv_path):
    by_event = defaultdict(lambda: {
        'dts': [], 'lats': [], 'lons': [], 'cfs': [], 'regime': ''
    })
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
                continue
            try:
                float(r['speed_err'])
            except Exception:
                continue
            eid = r['event_id']
            by_event[eid]['regime'] = r.get('synoptic_regime', '')
            try:
                dt = datetime.datetime.fromisoformat(
                    r['peak_dt_utc'].replace('Z', '+00:00'))
                # floor to hour — HRRR f00 is per whole hour
                dt_h = dt.replace(minute=0, second=0, microsecond=0, tzinfo=None)
                by_event[eid]['dts'].append(dt_h)
            except Exception:
                pass
            try:
                by_event[eid]['lats'].append(float(r['lat']))
                by_event[eid]['lons'].append(float(r['lon']))
            except Exception:
                pass
            try:
                by_event[eid]['cfs'].append(float(r['hrrr_coupling_frac']))
            except Exception:
                pass

    events = {}
    for eid, d in by_event.items():
        if not d['dts'] or not d['lats']:
            continue
        dts_sorted = sorted(d['dts'])
        peak_dt = dts_sorted[len(dts_sorted) // 2]
        events[eid] = {
            'regime':       d['regime'],
            'peak_dt':      peak_dt,
            'centroid_lat': float(np.mean(d['lats'])),
            'centroid_lon': float(np.mean(d['lons'])),
            'cf_mean':      float(np.mean(d['cfs'])) if d['cfs'] else None,
            'n_stations':   len(d['lats']),
        }
    return events


# ── herbie helpers ─────────────────────────────────────────────────────────────

def get_hrrr(peak_dt, product, search):
    H = Herbie(peak_dt, model='hrrr', product=product, fxx=0,
               save_dir=CACHE, verbose=False)
    return H.xarray(search, remove_grib=False)


def extract_uv_at_point(ds, lat, lon):
    """
    Nearest-neighbour U/V extraction from a herbie Dataset at (lat, lon).
    Returns (speed_mph, dir_deg) or (None, None).
    """
    if not hasattr(ds, 'data_vars'):
        raise ValueError(f'Expected Dataset, got {type(ds)}')
    vars_ = list(ds.data_vars)
    u_name = next((v for v in vars_
                   if 'u' in v.lower() and 'grd' in v.lower()), None)
    v_name = next((v for v in vars_
                   if 'v' in v.lower() and 'grd' in v.lower()), None)
    if u_name is None:
        u_name, v_name = vars_[0], vars_[1]
    u_da = ds[u_name]
    v_da = ds[v_name]

    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    if grid_lon.min() > 0 and lon < 0:
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    dist, idx = tree.query([lat, lon])
    if dist > 1.0:
        return None, None

    u = float(u_da.values.ravel()[idx])
    v = float(v_da.values.ravel()[idx])
    spd = math.sqrt(u ** 2 + v ** 2) * MS_MPH
    d = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return spd, d


def compute_mslp_grad(da, centroid_lat, centroid_lon, box_deg=2.5):
    """
    Mean |∇MSLP| over a ±box_deg domain centred on (centroid_lat, centroid_lon).
    Returns Pa/100km, or None on failure.

    Uses the actual lat/lon grid spacing to convert row/col differences to km,
    accounting for cos(lat) compression on the E-W axis.
    """
    lat2d = da.latitude.values.astype(float)
    lon2d = da.longitude.values.astype(float)
    P     = da.values.astype(float)          # Pa

    if lon2d.min() > 0 and centroid_lon < 0:
        lon2d = np.where(lon2d > 180, lon2d - 360, lon2d)

    mask     = ((lat2d >= centroid_lat - box_deg) &
                (lat2d <= centroid_lat + box_deg) &
                (lon2d >= centroid_lon - box_deg) &
                (lon2d <= centroid_lon + box_deg))
    row_idx  = np.where(mask.any(axis=1))[0]
    col_idx  = np.where(mask.any(axis=0))[0]
    if len(row_idx) < 5 or len(col_idx) < 5:
        return None

    r0, r1   = row_idx[0], row_idx[-1] + 1
    c0, c1   = col_idx[0], col_idx[-1] + 1
    P_box    = P[r0:r1, c0:c1]
    lat_box  = lat2d[r0:r1, c0:c1]
    lon_box  = lon2d[r0:r1, c0:c1]

    # km per row/col — using actual lat/lon gradients
    dlat_deg = np.gradient(lat_box, axis=0)           # deg / row (signed)
    dlon_deg = np.gradient(lon_box, axis=1)           # deg / col (signed)
    cos_lat  = np.cos(np.radians(lat_box))
    dkm_row  = np.abs(dlat_deg) * 111.11              # km / row
    dkm_col  = np.abs(dlon_deg) * 111.11 * cos_lat   # km / col

    dkm_row  = np.where(dkm_row > 0.1, dkm_row, np.nan)
    dkm_col  = np.where(dkm_col > 0.1, dkm_col, np.nan)

    dP_row   = np.gradient(P_box, axis=0)             # Pa / row
    dP_col   = np.gradient(P_box, axis=1)             # Pa / col
    dPdy     = dP_row / dkm_row                       # Pa / km (N-S)
    dPdx     = dP_col / dkm_col                       # Pa / km (E-W)

    grad_mag = np.sqrt(dPdy ** 2 + dPdx ** 2) * 100.0  # Pa / 100km
    return float(np.nanmean(grad_mag))


# ── main extraction loop ───────────────────────────────────────────────────────

events = load_events(os.path.join(BASE, 'hrrr_error_dataset.csv'))
print(f'Events to process: {len(events)}')
for eid in sorted(events):
    e = events[eid]
    print(f'  {eid:<28} {e["regime"]:<28} '
          f'peak={e["peak_dt"].strftime("%Y-%m-%d %HZ")}  '
          f'ctr=({e["centroid_lat"]:.2f},{e["centroid_lon"]:.2f})')
print()

rows_out = []

for eid in sorted(events):
    e        = events[eid]
    peak_dt  = e['peak_dt']
    clat     = e['centroid_lat']
    clon     = e['centroid_lon']
    regime   = e['regime']
    bc_level = REGIME_BC.get(regime, 850)

    print(f'=== {eid}  ({regime})  {peak_dt.strftime("%Y-%m-%d %HZ")} ===')

    row = {
        'event_id':      eid,
        'synoptic_regime': regime,
        'bc_level':      bc_level,
        'peak_dt_utc':   peak_dt.strftime('%Y-%m-%dT%H:00:00'),
        'domain_lat':    f'{clat:.4f}',
        'domain_lon':    f'{clon:.4f}',
        'n_stations':    e['n_stations'],
        'hrrr_coupling_frac_mean': (
            f'{e["cf_mean"]:.4f}' if e['cf_mean'] is not None else ''),
        'notes': '',
    }
    # initialise all extracted fields to FAIL so partial failures are obvious
    for k in ('w700_speed_mph', 'w700_dir_deg', 'w700_dir_sin', 'w700_dir_cos',
              'mslp_grad_pa100km'):
        row[k] = 'FAIL'

    # ── 700 hPa wind at centroid (prs product) ────────────────────────────────
    try:
        ds_prs = get_hrrr(peak_dt, 'prs', ':(?:UGRD|VGRD):700 mb:')
        w700_spd, w700_dir = extract_uv_at_point(ds_prs, clat, clon)
        if w700_spd is not None:
            row['w700_speed_mph'] = f'{w700_spd:.2f}'
            row['w700_dir_deg']   = f'{w700_dir:.1f}'
            row['w700_dir_sin']   = f'{math.sin(math.radians(w700_dir)):.5f}'
            row['w700_dir_cos']   = f'{math.cos(math.radians(w700_dir)):.5f}'
            print(f'  w700:      {w700_spd:.1f} mph @ {w700_dir:.0f}°')
        else:
            row['notes'] += 'w700_extract_fail '
            print(f'  w700:      EXTRACTION FAIL (nearest grid point > 1 deg away)')
    except Exception as ex:
        row['notes'] += 'w700_pull_fail '
        print(f'  w700:      PULL FAIL — {ex}')

    # ── MSLP gradient over ±2.5° box (sfc product) ───────────────────────────
    try:
        ds_sfc = get_hrrr(peak_dt, 'sfc', ':MSLMA:mean sea level:')
        # herbie returns DataArray or Dataset depending on cfgrib
        if hasattr(ds_sfc, 'data_vars'):
            mslp_da = ds_sfc[list(ds_sfc.data_vars)[0]]
        else:
            mslp_da = ds_sfc
        # ensure 2D lat/lon arrays are present
        if not hasattr(mslp_da, 'latitude'):
            raise ValueError('MSLP DataArray missing latitude coordinate')
        grad = compute_mslp_grad(mslp_da, clat, clon, box_deg=2.5)
        if grad is not None:
            row['mslp_grad_pa100km'] = f'{grad:.3f}'
            # centre-point MSLP for diagnostics
            lat2d = mslp_da.latitude.values.ravel()
            lon2d = mslp_da.longitude.values.ravel()
            if lon2d.min() > 0 and clon < 0:
                lon2d = np.where(lon2d > 180, lon2d - 360, lon2d)
            tree  = KDTree(np.column_stack([lat2d, lon2d]))
            _, ix = tree.query([clat, clon])
            mslp_hpa = float(mslp_da.values.ravel()[ix]) / 100.0
            print(f'  mslp_grad: {grad:.2f} Pa/100km  '
                  f'(centroid MSLP = {mslp_hpa:.1f} hPa)')
        else:
            row['notes'] += 'mslp_box_fail '
            print(f'  mslp_grad: BOX TOO SMALL or bad grid shape')
    except Exception as ex:
        row['notes'] += 'mslp_pull_fail '
        print(f'  mslp_grad: PULL FAIL — {ex}')

    row['notes'] = row['notes'].strip()
    rows_out.append(row)
    print()

# ── write output ──────────────────────────────────────────────────────────────
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows_out)

print(f'Written: {OUT}')
print()

# ── summary table ─────────────────────────────────────────────────────────────
ok_w700  = sum(1 for r in rows_out if r['w700_speed_mph']  not in ('FAIL',''))
ok_mslp  = sum(1 for r in rows_out if r['mslp_grad_pa100km'] not in ('FAIL',''))
print(f'w700 OK:     {ok_w700}/{len(rows_out)}')
print(f'mslp_grad OK: {ok_mslp}/{len(rows_out)}')
print()
print(f"{'event_id':<28} {'regime':<24} {'w700':>7} {'dir':>5} {'mslp_grad':>11} "
      f"{'cf_mean':>8}  notes")
print('-' * 95)
for row in rows_out:
    w700  = row.get('w700_speed_mph',  'FAIL')
    wdir  = row.get('w700_dir_deg',    'FAIL')
    grad  = row.get('mslp_grad_pa100km','FAIL')
    cf    = row.get('hrrr_coupling_frac_mean','')
    notes = row.get('notes','')
    try: w700 = f'{float(w700):7.1f}'
    except: w700 = f'{w700:>7}'
    try: wdir = f'{float(wdir):5.0f}'
    except: wdir = f'{wdir:>5}'
    try: grad = f'{float(grad):11.2f}'
    except: grad = f'{grad:>11}'
    try: cf = f'{float(cf):8.3f}'
    except: cf = f'{cf:>8}'
    print(f"  {row['event_id']:<26} {row['synoptic_regime']:<24} "
          f"{w700} {wdir} {grad} {cf}  {notes}")
