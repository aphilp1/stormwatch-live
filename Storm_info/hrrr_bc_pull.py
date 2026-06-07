#!/usr/bin/env python3
"""
hrrr_bc_pull.py  —  Populate bc_speed / bc_level / bc_dir in departure database

For each of the 12 analysis events, downloads HRRR pressure-level analysis
(f00) at the median peak hour, extracts U/V at the assigned bc_level for
every station in the event, and writes bc_speed (mph), bc_level (hPa int),
and bc_dir (degrees) back to:
  - hrrr_error_dataset.csv
  - hrrr_error_dataset_dem.csv

bc_level assignment (operational rule from hindcast framework):
  850 hPa:  sub-inversion gap/gradient flow  →  diablo, santa_ana
  700 hPa:  above-inversion ridgetop/downslope  →  chinook, downslope, frontal
  850 hPa:  convective outflow (nearest surface-driver; note uncertainty)

Run in hrrr311 env:  herbie, xarray, scipy all required.
"""

import csv
import datetime
import os
import shutil
import sys

import numpy as np
from scipy.spatial import KDTree

from herbie import Herbie

# ── paths ─────────────────────────────────────────────────────────────────────
BASE     = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
CSV_SRC  = os.path.join(BASE, "hrrr_error_dataset.csv")
CSV_DEM  = os.path.join(BASE, "hrrr_error_dataset_dem.csv")
CACHE    = os.path.join(BASE, "hrrr_bc_cache")
MS_MPH   = 2.23694  # m/s → mph

os.makedirs(CACHE, exist_ok=True)

# ── bc_level by regime ────────────────────────────────────────────────────────
REGIME_BC = {
    "diablo_offshore":    850,
    "diablo_offshore_NW": 850,
    "diablo_offshore_NE": 850,
    "santa_ana":          850,
    "chinook_frontrange": 700,
    "downslope_oregon":   700,
    "frontal_passage":    700,
    "convective_outflow": 850,  # outflow; closest surface driver
}

# ── load departure database ───────────────────────────────────────────────────

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f)), None

def fieldnames(path):
    with open(path, newline="", encoding="utf-8") as f:
        return csv.DictReader(f).fieldnames

all_rows_src, _ = load_csv(CSV_SRC)
all_rows_dem, _ = load_csv(CSV_DEM)
fields_src       = fieldnames(CSV_SRC)
fields_dem       = fieldnames(CSV_DEM)

# Build event map from active rows (KEEP/CAUTION with numeric speed_err)
from collections import defaultdict

active = {}
for r in all_rows_src:
    if r.get("qc_flag") not in ("KEEP", "CAUTION"):
        continue
    try:
        float(r["speed_err"])
    except Exception:
        continue
    eid = r["event_id"]
    if eid not in active:
        active[eid] = {"regime": r.get("synoptic_regime", ""), "stations": []}
    try:
        lat = float(r["lat"]); lon = float(r["lon"])
    except Exception:
        continue
    try:
        dt = datetime.datetime.fromisoformat(r["peak_dt_utc"].replace("Z", "+00:00"))
    except Exception:
        dt = None
    active[eid]["stations"].append({
        "stid": r["stid"],
        "lat":  lat,
        "lon":  lon,
        "dt":   dt,
    })

# Per-event: median peak datetime and bc_level
event_bc = {}
for eid, d in active.items():
    regime   = d["regime"]
    bc_level = REGIME_BC.get(regime, 850)
    dts = sorted([s["dt"] for s in d["stations"] if s["dt"] is not None])
    if not dts:
        print(f"  {eid}: no valid timestamps — SKIP")
        continue
    peak_dt = dts[len(dts) // 2].replace(tzinfo=None)  # herbie wants naive UTC
    event_bc[eid] = {"peak_dt": peak_dt, "bc_level": bc_level, "regime": regime}

print(f"Events to process: {len(event_bc)}")
for eid, d in sorted(event_bc.items()):
    print(f"  {eid:<25} regime={d['regime']:<25} bc_level={d['bc_level']} hPa  "
          f"peak={d['peak_dt'].strftime('%Y-%m-%d %HZ')}")
print()


# ── herbie pull + extraction ──────────────────────────────────────────────────

def get_hrrr_prs_uv(peak_dt, level_hpa):
    """
    Download HRRR f00 pressure-level U/V at `level_hpa` hPa.
    Returns (ds, u_da, v_da) — xarray DataArrays with lat/lon coords.
    """
    search = f":(?:UGRD|VGRD):{level_hpa} mb:"
    H = Herbie(
        peak_dt,
        model="hrrr",
        product="prs",
        fxx=0,
        save_dir=CACHE,
        verbose=False,
    )
    ds = H.xarray(search, remove_grib=False)
    # ds may be Dataset or DataArray
    if hasattr(ds, "data_vars"):
        vars_ = list(ds.data_vars)
        # look for u/v by name
        u_name = next((v for v in vars_ if "u" in v.lower() and "grd" in v.lower()), None)
        v_name = next((v for v in vars_ if "v" in v.lower() and "grd" in v.lower()), None)
        if u_name is None:
            # fallback: first/second by shortName
            u_name, v_name = vars_[0], vars_[1]
        u_da = ds[u_name]
        v_da = ds[v_name]
    else:
        # It's a DataArray — shouldn't happen for two variables
        raise ValueError(f"Expected Dataset, got DataArray: {ds}")
    return ds, u_da, v_da


def extract_speeds_at_stations(u_da, v_da, lats, lons):
    """
    Nearest-neighbor extraction of U/V at station (lat, lon) pairs.
    Returns arrays: speeds_mph, dirs_deg.
    """
    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    # HRRR longitude can be -180..180 or 0..360; normalize to match station lons
    if grid_lon.min() > 0 and np.any(np.array(lons) < 0):
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    query_pts = np.column_stack([lats, lons])
    dists, idxs = tree.query(query_pts)

    u_flat = u_da.values.ravel()
    v_flat = v_da.values.ravel()

    speeds = []
    dirs   = []
    for i, (dist, idx) in enumerate(zip(dists, idxs)):
        if dist > 1.0:  # >1 degree = suspect extraction
            speeds.append(None); dirs.append(None)
            continue
        u = float(u_flat[idx])
        v = float(v_flat[idx])
        spd = float(np.sqrt(u**2 + v**2)) * MS_MPH
        d   = float((270.0 - np.degrees(np.arctan2(v, u))) % 360.0)
        speeds.append(spd)
        dirs.append(d)
    return speeds, dirs


# Run extraction for each event
results = {}  # {(event_id, stid): (bc_speed, bc_dir, bc_level)}

for eid, einfo in sorted(event_bc.items()):
    peak_dt  = einfo["peak_dt"]
    bc_level = einfo["bc_level"]
    stations = active[eid]["stations"]
    lats = [s["lat"] for s in stations]
    lons = [s["lon"] for s in stations]
    stids = [s["stid"] for s in stations]

    print(f"  {eid}  ({einfo['regime']})  {peak_dt.strftime('%Y-%m-%d %HZ')}  "
          f"bc_level={bc_level} hPa  n_stations={len(stations)}")

    try:
        ds, u_da, v_da = get_hrrr_prs_uv(peak_dt, bc_level)
        speeds, dirs = extract_speeds_at_stations(u_da, v_da, lats, lons)

        ok_count = sum(1 for s in speeds if s is not None)
        mean_spd = np.nanmean([s for s in speeds if s is not None]) if ok_count > 0 else None
        print(f"    → extracted {ok_count}/{len(stids)} stations  "
              f"mean_bc_speed={mean_spd:.1f} mph" if mean_spd else "    → NO DATA")

        for stid, spd, d in zip(stids, speeds, dirs):
            results[(eid, stid)] = (spd, d, bc_level)

    except Exception as e:
        print(f"    FAIL: {e}")
        for stid in stids:
            results[(eid, stid)] = (None, None, bc_level)

print()
print(f"Extraction complete. Populated {sum(1 for v in results.values() if v[0] is not None)} / "
      f"{len(results)} station-events.")
print()


# ── write back to CSVs ────────────────────────────────────────────────────────

def update_csv(all_rows, fields, path, results):
    """Update bc_speed/bc_level/bc_dir columns in-place; write to path."""
    bak = path + ".pre_bc_pull.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  Backup: {bak}")

    updated = skipped = 0
    for row in all_rows:
        key = (row["event_id"], row["stid"])
        if key in results:
            spd, d, lev = results[key]
            row["bc_speed"] = f"{spd:.2f}" if spd is not None else "PULL_FAIL"
            row["bc_level"] = str(lev)
            row["bc_dir"]   = f"{d:.1f}" if d is not None else "PULL_FAIL"
            updated += 1
        else:
            skipped += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"  Wrote {path}  (updated={updated}, skipped={skipped})")


print("Writing CSVs...")
update_csv(all_rows_src, fields_src, CSV_SRC, results)
update_csv(all_rows_dem, fields_dem, CSV_DEM, results)
print()

# ── quick sanity check ────────────────────────────────────────────────────────

print("Sanity check — event-mean bc_speed vs hrrr_10m_mph:")
print(f"  {'event_id':<25} {'bc_level':>8}  {'bc_speed_mean':>14}  {'hrrr_10m_mean':>14}  "
      f"{'ratio (10m/bc)':>15}")

from collections import defaultdict
by_event_check = defaultdict(list)
with open(CSV_DEM, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        try:
            bc_s = float(row["bc_speed"])
            h10  = float(row["hrrr_10m_mph"])
        except Exception:
            continue
        by_event_check[row["event_id"]].append((bc_s, h10))

for eid in sorted(by_event_check):
    vals   = by_event_check[eid]
    bc_s   = np.mean([v[0] for v in vals])
    h10    = np.mean([v[1] for v in vals])
    ratio  = h10 / bc_s if bc_s > 0 else float("nan")
    lev    = event_bc.get(eid, {}).get("bc_level", "?")
    print(f"  {eid:<25} {str(lev):>8}  {bc_s:>14.2f}  {h10:>14.2f}  {ratio:>15.3f}")
