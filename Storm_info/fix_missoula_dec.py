#!/usr/bin/env python3
"""
fix_missoula_dec.py  —  Replace missoula_dec2025 rows with correct Dec 17 2025 data

The departure database captured Dec 9-11 2025 frontal events instead of
Dec 17 2025. Case 2 hindcast confirmed Dec 17: 700 hPa 29 mph @ 315° NW (OTX).

Steps:
  1. Pull Synoptic obs for 8 stations, Dec 17 2025 00Z-23Z
  2. Find peak sustained wind per station (nearest HRRR analysis hour)
  3. Pull HRRR f00 at peak hour: 10m wind + 700 hPa wind (bc_level)
  4. Update rows in hrrr_error_dataset.csv and hrrr_error_dataset_dem.csv

Run in hrrr311 env (herbie + scipy).
"""

import csv
import datetime
import json
import os
import shutil
import sys

import numpy as np
import requests
from scipy.spatial import KDTree
from herbie import Herbie

BASE   = r"C:\Users\aphil\Documents\Stormwatch"
SINFO  = os.path.join(BASE, "Storm_info")
CSV_SRC = os.path.join(SINFO, "hrrr_error_dataset.csv")
CSV_DEM = os.path.join(SINFO, "hrrr_error_dataset_dem.csv")
CACHE   = os.path.join(SINFO, "hrrr_bc_cache")
os.makedirs(CACHE, exist_ok=True)

# Synoptic config
sys.path.insert(0, BASE)
import synoptic_config as sc
TOKEN   = sc.SYNOPTIC_TOKEN
SYN_BASE = "https://api.synopticdata.com/v2/stations/timeseries"
MS_MPH   = 2.23694

EVENT_ID = "missoula_dec2025"
STIDS    = ["BLMM8", "CONM8", "FINM8", "NINM8", "PNTM8", "PSTM8", "RONM8", "STVM8"]
BC_LEVEL = 700  # frontal_passage uses 700 hPa

# Dec 17 2025: use 00Z-23Z window
WIN_START = "20251217000000"
WIN_END   = "20251217230000"
WIN_START_DT = datetime.datetime(2025, 12, 17, 0,  0, tzinfo=datetime.timezone.utc)
WIN_END_DT   = datetime.datetime(2025, 12, 17, 23, 0, tzinfo=datetime.timezone.utc)

# ── Step 1: Pull Synoptic obs for Dec 17 ─────────────────────────────────────

print("Step 1: Pulling Synoptic obs for Dec 17 2025...")
print(f"  Stations: {', '.join(STIDS)}")

params = {
    "token":   TOKEN,
    "stid":    ",".join(STIDS),
    "start":   WIN_START,
    "end":     WIN_END,
    "vars":    "wind_speed,wind_gust,wind_direction",
    "units":   "english",
    "obtimezone": "utc",
    "output":  "json",
}
r = requests.get(SYN_BASE, params=params, timeout=60)
if r.status_code != 200:
    sys.exit(f"Synoptic HTTP {r.status_code}: {r.text[:200]}")

data = r.json()
summary = data.get("SUMMARY", {})
if summary.get("RESPONSE_CODE") != 1:
    sys.exit(f"Synoptic error: {summary.get('RESPONSE_MESSAGE', 'unknown')}")

stations_data = data.get("STATION", [])
print(f"  Got data for {len(stations_data)} stations")

# ── Step 2: Find peak sustained wind per station ──────────────────────────────

print()
print("Step 2: Finding peak sustained wind on Dec 17...")
print(f"  {'stid':<8} {'obs_sus':>8} {'obs_gust':>9} {'obs_dir':>8} {'peak_dt_utc':<24} {'lat':>7} {'lon':>8}")

station_peaks = {}
for stn in stations_data:
    stid = stn["STID"]
    lat  = float(stn["LATITUDE"])
    lon  = float(stn["LONGITUDE"])

    obs  = stn.get("OBSERVATIONS", {})
    times = obs.get("date_time", [])
    spds  = obs.get("wind_speed_set_1",      [None] * len(times))
    gusts = obs.get("wind_gust_set_1",       [None] * len(times))
    dirs  = obs.get("wind_direction_set_1",  [None] * len(times))

    # Find peak sustained wind within window
    best = {"sus": None, "gust": None, "dir": None, "dt": None}
    for t, s, g, d in zip(times, spds, gusts, dirs):
        if s is None:
            continue
        try:
            dt = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            continue
        if not (WIN_START_DT <= dt <= WIN_END_DT):
            continue
        if best["sus"] is None or float(s) > best["sus"]:
            best = {"sus": float(s), "gust": float(g) if g is not None else None,
                    "dir": float(d) if d is not None else None, "dt": dt}

    if best["dt"] is None:
        print(f"  {stid:<8}  NO DATA in window")
        continue

    # Round to nearest HRRR analysis hour
    peak_dt = best["dt"].replace(minute=0, second=0, microsecond=0)
    if best["dt"].minute >= 30:
        peak_dt += datetime.timedelta(hours=1)

    station_peaks[stid] = {
        "lat":      lat, "lon": lon,
        "obs_sus":  best["sus"],
        "obs_gust": best["gust"],
        "obs_dir":  best["dir"],
        "peak_dt":  peak_dt,
        "peak_dt_utc_str": best["dt"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hrrr_dt":  peak_dt.replace(tzinfo=None),
    }

    print(f"  {stid:<8} {best['sus']:>8.1f} {str(best['gust'] or 'N/A'):>9} "
          f"{str(best['dir'] or 'N/A'):>8} {best['dt'].strftime('%Y-%m-%dT%HZ'):<24} "
          f"{lat:>7.3f} {lon:>8.3f}")

if not station_peaks:
    sys.exit("No stations had data in the Dec 17 window. Check Synoptic API.")

# ── Step 3: Pull HRRR 10m + 700 hPa at each station's peak hour ──────────────

print()
print("Step 3: Pulling HRRR 10m + 700 hPa for each peak hour...")

# Group stations by HRRR valid hour (avoid duplicate downloads)
by_hour = {}
for stid, d in station_peaks.items():
    h = d["hrrr_dt"]
    if h not in by_hour:
        by_hour[h] = []
    by_hour[h].append(stid)

def get_uv(H, search, stids_hr):
    ds = H.xarray(search, remove_grib=False)
    if hasattr(ds, "data_vars"):
        vars_ = list(ds.data_vars)
        u_name = next((v for v in vars_ if "u" in v.lower()), None)
        v_name = next((v for v in vars_ if "v" in v.lower()), None)
        if u_name is None:
            u_name, v_name = vars_[0], vars_[1]
        u_da, v_da = ds[u_name], ds[v_name]
    else:
        raise ValueError("Expected Dataset")

    grid_lat = u_da.latitude.values.ravel()
    grid_lon = u_da.longitude.values.ravel()
    if grid_lon.min() > 0:
        grid_lon = np.where(grid_lon > 180, grid_lon - 360, grid_lon)

    tree = KDTree(np.column_stack([grid_lat, grid_lon]))
    results = {}
    for stid in stids_hr:
        lat = station_peaks[stid]["lat"]
        lon = station_peaks[stid]["lon"]
        dist, idx = tree.query([[lat, lon]])
        u = float(u_da.values.ravel()[idx[0]])
        v = float(v_da.values.ravel()[idx[0]])
        spd = np.sqrt(u**2 + v**2) * MS_MPH
        d   = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
        results[stid] = (float(spd), float(d))
    return results

for hrrr_dt, stids_hr in sorted(by_hour.items()):
    print(f"  {hrrr_dt.strftime('%Y-%m-%d %HZ')}: {stids_hr}")
    try:
        H_sfc = Herbie(hrrr_dt, model="hrrr", product="sfc", fxx=0,
                       save_dir=CACHE, verbose=False)
        H_prs = Herbie(hrrr_dt, model="hrrr", product="prs", fxx=0,
                       save_dir=CACHE, verbose=False)

        # 10m wind
        uv_10m = get_uv(H_sfc, ":(?:UGRD|VGRD):10 m above ground:", stids_hr)
        # 700 hPa wind
        uv_700 = get_uv(H_prs, f":(?:UGRD|VGRD):{BC_LEVEL} mb:", stids_hr)

        for stid in stids_hr:
            spd10, dir10 = uv_10m[stid]
            spd700, dir700 = uv_700[stid]
            station_peaks[stid]["hrrr_10m_mph"] = spd10
            station_peaks[stid]["hrrr_10m_dir"] = dir10
            station_peaks[stid]["bc_speed"]     = spd700
            station_peaks[stid]["bc_dir"]       = dir700
            station_peaks[stid]["bc_level"]     = str(BC_LEVEL)
            se = spd10 - station_peaks[stid]["obs_sus"]
            station_peaks[stid]["speed_err"]    = se
            print(f"    {stid}: obs={station_peaks[stid]['obs_sus']:.1f}  "
                  f"hrrr_10m={spd10:.1f}  err={se:+.1f}  bc700={spd700:.1f}")

    except Exception as e:
        print(f"    FAIL for {stids_hr}: {e}")
        for stid in stids_hr:
            station_peaks[stid]["hrrr_10m_mph"] = None
            station_peaks[stid]["hrrr_10m_dir"] = None
            station_peaks[stid]["bc_speed"]     = None
            station_peaks[stid]["bc_dir"]       = None
            station_peaks[stid]["bc_level"]     = str(BC_LEVEL)
            station_peaks[stid]["speed_err"]    = None

# ── Step 4: Update CSVs ───────────────────────────────────────────────────────

print()
print("Step 4: Updating CSVs...")

def _s(v, fmt=None):
    if v is None:
        return ""
    return (fmt % v) if fmt else str(v)

def update_csv(path, all_rows, fields):
    bak = path + ".pre_missoula_fix.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  Backup: {bak}")

    updated = 0
    for row in all_rows:
        if row["event_id"] != EVENT_ID:
            continue
        stid = row["stid"]
        if stid not in station_peaks:
            print(f"  {stid}: no new data — leaving unchanged")
            continue
        d = station_peaks[stid]

        row["peak_dt_utc"]     = d["peak_dt_utc_str"]
        row["peak_hour_utc"]   = str(d["peak_dt"].hour)
        row["obs_sus_mph"]     = _s(d["obs_sus"],  "%.2f")
        row["obs_gust_mph"]    = _s(d["obs_gust"], "%.2f")
        row["obs_dir_deg"]     = _s(d["obs_dir"],  "%.1f")
        row["hrrr_10m_mph"]    = _s(d.get("hrrr_10m_mph"), "%.2f")
        row["hrrr_10m_dir"]    = _s(d.get("hrrr_10m_dir"), "%.1f")
        row["speed_err"]       = _s(d.get("speed_err"),    "%.2f")
        row["bc_speed"]        = _s(d.get("bc_speed"),     "%.2f")
        row["bc_dir"]          = _s(d.get("bc_dir"),       "%.1f")
        row["bc_level"]        = d.get("bc_level", str(BC_LEVEL))
        updated += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"  Wrote {path}  (updated={updated} missoula_dec2025 rows)")

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames

all_src, fields_src = load_csv(CSV_SRC)
all_dem, fields_dem = load_csv(CSV_DEM)

# fields_src is None after iteration — re-read
with open(CSV_SRC, newline="", encoding="utf-8") as f:
    fields_src = csv.DictReader(f).fieldnames
with open(CSV_DEM, newline="", encoding="utf-8") as f:
    fields_dem = csv.DictReader(f).fieldnames

update_csv(CSV_SRC, all_src, fields_src)
update_csv(CSV_DEM, all_dem, fields_dem)

print()
print("Summary of updated missoula_dec2025 rows:")
print(f"  {'stid':<8} {'peak_dt_utc':<22} {'obs_sus':>8} {'hrrr_10m':>9} {'speed_err':>10} {'bc_speed700':>12}")
for stid in STIDS:
    if stid not in station_peaks:
        print(f"  {stid:<8}  NO DATA")
        continue
    d = station_peaks[stid]
    print(f"  {stid:<8} {d['peak_dt_utc_str']:<22} {d['obs_sus']:>8.1f} "
          f"{str(d.get('hrrr_10m_mph') or 'N/A'):>9} "
          f"{str(d.get('speed_err') or 'N/A'):>10} "
          f"{str(d.get('bc_speed') or 'N/A'):>12}")
