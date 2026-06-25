#!/usr/bin/env python3
"""
trajectory_pull.py — Stage A of Trajectory Scoring  (run in the `dem` conda env)
================================================================================
Builds the per-station HOURLY curves for the three pulled sources —
  obs        : RAWS sustained wind (raws_obs/<event>/<STID>_<event>.csv, mph)
  hrrr_10m   : HRRR f00 10 m wind   (sfc product, :UGRD|VGRD:10 m above ground:)
  hrrr_bc    : HRRR f00 aloft BC    (prs product, bc_level mb; 850 offshore / 700 cont.)
over a window bracketing EACH STATION's own obs peak (±WINDOW_H hours, clipped to
the hours where obs exists). Writes <event>_hourly_hrrr.json, which
hindcast_wn_runner.py consumes to add the WindNinja curves (wn10m, wn850) and
compute the two trajectory metrics (curve RMSE + peak offset).

Provenance (unchanged from the peak-hour pipeline, only the hour advances):
  HRRR = f00 analysis at each window hour — NOT a forecast lead.
  Obs timestamps are reported off-the-hour (e.g. HH:27); each row is floored to
  its analysis hour so the obs grid aligns with HRRR f00 at HH:00.
  Obs files are already mph — used directly (no m/s conversion).

hrrr311 is broken at numpy (DLL 0xC0000139); run THIS in the `dem` env:
  conda run -n dem python trajectory_pull.py --event camp_2018
  conda run -n dem python trajectory_pull.py --all
  conda run -n dem python trajectory_pull.py --event camp_2018 --window-hours 3
"""

import argparse
import csv
import datetime as dt
import glob as glob_mod
import json
import os
import sys

import warnings
warnings.filterwarnings('ignore')  # xarray/cfgrib merge FutureWarnings — benign, noisy

import numpy as np
from scipy.spatial import KDTree
from herbie import Herbie
import xarray as xr

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE       = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
CSV_PATH   = os.path.join(BASE, "hrrr_error_dataset.csv")
RAWS_DIR   = os.path.join(BASE, "raws_obs")
OUTPUT_DIR = os.path.join(BASE, "hindcast_grids")
CACHE      = os.path.join(BASE, "hrrr_bc_cache")
MS_MPH     = 2.23694
DEFAULT_WINDOW_H = 6

# Same regime→level rule as hrrr_bc_pull.py (used only if a row lacks bc_level).
REGIME_BC = {
    "diablo_offshore": 850, "diablo_offshore_NW": 850, "diablo_offshore_NE": 850,
    "santa_ana": 850, "chinook_frontrange": 700, "downslope_oregon": 700,
    "frontal_passage": 700, "convective_outflow": 850,
}

# Run order mirrors hindcast_wn_runner.ALL_EVENTS.
ALL_EVENTS = [
    'camp_2018', 'kincade_run_2019', 'kincade_ign_2019', 'woolsey_2018',
    'thomas_2017', 'missoula_dec2025', 'labor_day_or2020', 'boulder_chin2021',
    'marshall_2021', 'iowa_derecho2020', 'missoula_jul2024', 'tubbs_2017',
]

os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── station selection (mirrors hindcast_wn_runner.load_event_stations) ──────────

def load_event_stations(event_id):
    """KEEP/usable stations with BC + obs for the event. Same filter as the
    runner so the trajectory station set matches the peak-hour station set."""
    rows, seen = [], set()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['event_id'] != event_id:
                continue
            if r.get('qc_flag', '') == 'DROP':
                continue
            key = (r['event_id'], r['stid'])
            if key in seen:
                continue
            if r.get('bc_speed', '') in ('', 'NEEDS_BC'):
                continue
            if r.get('obs_sus_mph', '') in ('', 'N/A'):
                continue
            try:
                lat = float(r['lat']); lon = float(r['lon'])
            except (ValueError, KeyError):
                continue
            seen.add(key)
            # bc_level from the CSV; fall back to regime rule if blank.
            lvl = r.get('bc_level', '')
            try:
                level = int(float(lvl))
            except (ValueError, TypeError):
                level = REGIME_BC.get(r.get('synoptic_regime', ''), 850)
            rows.append({'stid': r['stid'], 'lat': lat, 'lon': lon,
                         'bc_level': level,
                         'regime': r.get('synoptic_regime', '')})
    return rows


# ── obs curve ──────────────────────────────────────────────────────────────────

def floor_hour(ts):
    """Parse an ISO obs timestamp and floor to its analysis hour (UTC, naive)."""
    d = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return d.replace(minute=0, second=0, microsecond=0)


def read_obs_curve(event_id, stid):
    """Return {floored_hour(datetime): wind_speed_mph} for a station, or {}.
    If several obs rows fall in the same analysis hour, keep the max (the
    sustained peak within that hour) — consistent with peak-hour scoring."""
    path = os.path.join(RAWS_DIR, event_id, f"{stid}_{event_id}.csv")
    if not os.path.exists(path):
        cand = glob_mod.glob(os.path.join(RAWS_DIR, event_id, f"{stid}_*.csv"))
        if not cand:
            return {}
        path = cand[0]
    curve = {}
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            v = r.get('wind_speed_mph', '')
            if v in ('', 'N/A', None):
                continue
            try:
                spd = float(v); hr = floor_hour(r['datetime_utc'])
            except (ValueError, KeyError):
                continue
            if hr not in curve or spd > curve[hr]:
                curve[hr] = spd
    return curve


def station_window(obs_curve, window_h):
    """Return (hours_list, obs_array, peak_hour) for a station.
    Window = obs-peak-hour ± window_h, clipped to the obs coverage range.
    obs_array has None for any hour inside the window with no obs row."""
    if not obs_curve:
        return None
    peak_hour = max(obs_curve, key=obs_curve.get)
    lo_cov, hi_cov = min(obs_curve), max(obs_curve)
    t0 = max(peak_hour - dt.timedelta(hours=window_h), lo_cov)
    t1 = min(peak_hour + dt.timedelta(hours=window_h), hi_cov)
    hours, obs = [], []
    h = t0
    while h <= t1:
        hours.append(h)
        obs.append(obs_curve.get(h))
        h += dt.timedelta(hours=1)
    return hours, obs, peak_hour


# ── HRRR pulls (f00 analysis at each window hour) ──────────────────────────────

# NO dataset caching: each hour is queried exactly once per event, so caching the
# full CONUS HRRR Datasets just leaks RAM across events (was a MemoryError on the
# --all run at event 8). Each ds is released after its hour's extraction.

def get_sfc(hour):
    try:
        H = Herbie(hour.strftime('%Y-%m-%d %H:00'), model='hrrr', product='sfc',
                   fxx=0, save_dir=CACHE, priority=['aws', 'google'], verbose=False)
        u = H.xarray(':UGRD:10 m above ground:')
        v = H.xarray(':VGRD:10 m above ground:')
        return xr.merge([u, v])
    except Exception as e:
        print(f"      sfc {hour:%Y-%m-%d %HZ} FAIL: {e}")
        return None


def get_prs(hour, level):
    try:
        H = Herbie(hour.strftime('%Y-%m-%d %H:00'), model='hrrr', product='prs',
                   fxx=0, save_dir=CACHE, priority=['aws', 'google'], verbose=False)
        ds = H.xarray(f':(?:UGRD|VGRD):{level} mb:')
        return ds if hasattr(ds, 'data_vars') else None
    except Exception as e:
        print(f"      prs {hour:%Y-%m-%d %HZ} {level}mb FAIL: {e}")
        return None


def _pick(ds, comp):
    """Pick the u or v DataArray name (comp='u'/'v'). sfc→u10/v10, prs→u/v."""
    cands = [v for v in ds.data_vars if v.lower().startswith(comp)]
    if not cands:  # fallback: anything containing the component letter+'grd'
        cands = [v for v in ds.data_vars if comp + 'grd' in v.lower()]
    return cands[0] if cands else None


# The HRRR native grid is identical for every hour and product (sfc/prs), so the
# KDTree only needs building ONCE — rebuilding ~1.9M points per hour was the bulk
# of the runtime. Cache by grid signature; holds one ~60MB tree, reused throughout.
_TREE_CACHE = {}


def _grid_tree(glat, glon):
    sig = (glat.shape[0], round(float(glat[0]), 3), round(float(glon[0]), 3),
           round(float(glat[-1]), 3), round(float(glon[-1]), 3))
    tree = _TREE_CACHE.get(sig)
    if tree is None:
        tree = KDTree(np.column_stack([glat, glon]))
        _TREE_CACHE[sig] = tree
    return tree


def make_extractor(ds):
    """Return f(lat,lon)->(speed_mph,dir_deg) via nearest grid point, or None."""
    if ds is None:
        return None
    un, vn = _pick(ds, 'u'), _pick(ds, 'v')
    if un is None or vn is None:
        return None
    glat = ds['latitude'].values.ravel()
    glon = ds['longitude'].values.ravel()
    glon = np.where(glon > 180, glon - 360, glon)
    tree = _grid_tree(glat, glon)
    uf = ds[un].values.ravel()
    vf = ds[vn].values.ravel()

    def extract(lat, lon):
        d, idx = tree.query([lat, lon])
        if d > 1.0:           # >1° = suspect, treat as no-data
            return None, None
        u = float(uf[idx]); v = float(vf[idx])
        spd = float(np.hypot(u, v)) * MS_MPH
        ang = float((270.0 - np.degrees(np.arctan2(v, u))) % 360.0)
        return round(spd, 2), round(ang, 1)
    return extract


# ── main per-event build ────────────────────────────────────────────────────────

def build_event(event_id, window_h):
    stations = load_event_stations(event_id)
    if not stations:
        print(f"  {event_id}: no stations with BC+obs — SKIP")
        return None

    print(f"\n{'='*70}\nTRAJECTORY PULL  {event_id}  "
          f"({len(stations)} stations)  ±{window_h}h window\n{'='*70}")

    # 1) per-station window + obs curve
    built, skipped = {}, []
    for s in stations:
        obs_curve = read_obs_curve(event_id, s['stid'])
        win = station_window(obs_curve, window_h)
        if win is None:
            skipped.append(s['stid'])
            continue
        hours, obs, peak = win
        built[s['stid']] = {
            'lat': s['lat'], 'lon': s['lon'], 'bc_level': s['bc_level'],
            'window_utc': [hours[0].strftime('%Y-%m-%dT%H:00Z'),
                           hours[-1].strftime('%Y-%m-%dT%H:00Z')],
            'obs_peak_hour_utc': peak.strftime('%Y-%m-%dT%H:00Z'),
            'hours': [h.strftime('%Y-%m-%dT%H:00Z') for h in hours],
            '_hour_objs': hours,
            'obs': obs,
            'hrrr_10m': [None] * len(hours),
            'hrrr_10m_dir': [None] * len(hours),
            'hrrr_bc': [None] * len(hours),
            'hrrr_bc_dir': [None] * len(hours),
        }
    if skipped:
        print(f"  no-obs (skipped): {', '.join(skipped)}")
    if not built:
        print(f"  {event_id}: no station had usable obs — SKIP")
        return None

    # 2) global hour set + level set (pull each once, extract all stations)
    all_hours = sorted({h for b in built.values() for h in b['_hour_objs']})
    levels = sorted({b['bc_level'] for b in built.values()})
    print(f"  hours to pull: {len(all_hours)}  "
          f"({all_hours[0]:%Y-%m-%d %HZ} → {all_hours[-1]:%Y-%m-%d %HZ})  "
          f"levels={levels}")

    # 3) pull + extract hour by hour
    for hi, hour in enumerate(all_hours, 1):
        print(f"  [{hi}/{len(all_hours)}] {hour:%Y-%m-%d %HZ}", flush=True)
        sfc_ex = make_extractor(get_sfc(hour))
        prs_ex = {lv: make_extractor(get_prs(hour, lv)) for lv in levels}
        for stid, b in built.items():
            objs = b['_hour_objs']
            if hour not in objs:
                continue
            i = objs.index(hour)
            if sfc_ex:
                spd, ang = sfc_ex(b['lat'], b['lon'])
                b['hrrr_10m'][i] = spd
                b['hrrr_10m_dir'][i] = ang
            ex = prs_ex.get(b['bc_level'])
            if ex:
                spd, ang = ex(b['lat'], b['lon'])
                b['hrrr_bc'][i] = spd
                b['hrrr_bc_dir'][i] = ang

    # 4) write
    for b in built.values():
        b.pop('_hour_objs', None)
    out = {
        'event_id': event_id,
        'window_hours': window_h,
        'levels': levels,
        'n_stations': len(built),
        'stations': built,
    }
    out_path = os.path.join(OUTPUT_DIR, f"{event_id}_hourly_hrrr.json")
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"  Saved: {out_path}  ({len(built)} stations, {len(all_hours)} hours)")
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Trajectory Scoring — Stage A (HRRR+obs hourly pull)')
    ap.add_argument('--event', default='camp_2018')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--window-hours', type=int, default=DEFAULT_WINDOW_H,
                    help='Half-width in hours (±N). Default 6 → 13-hour window.')
    args = ap.parse_args()

    events = ALL_EVENTS if args.all else [args.event]
    for ev in events:
        build_event(ev, args.window_hours)
