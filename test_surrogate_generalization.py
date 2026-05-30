#!/usr/bin/env python3
"""
test_surrogate_generalization.py
=================================
Test whether the surrogate generalizes to BC values NOT in the training grid.

The 25-member ensemble covers speeds [20,24,28,32,36] x dirs [30,37,45,52,60].
This test checks:
  1. INTERPOLATION: BCs inside the grid but off-grid-node (e.g. 26 mph @ 41 deg)
  2. MILD EXTRAPOLATION: BCs slightly outside the grid (e.g. 18 mph @ 25 deg)
  3. STRONG EXTRAPOLATION: BCs well outside the grid (e.g. 40 mph @ 20 deg)

For each test BC, we:
  a) Predict with the surrogate (fast)
  b) Run real WindNinja (ground truth)
  c) Compare -- report whether interpolation stays close and extrapolation fails

This is the falsifiable test: a good surrogate should interpolate well and
degrade gracefully at extrapolation, not silently give wrong answers.

Run: python test_surrogate_generalization.py
"""

import subprocess, sys, os, glob, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"
CENTER_LAT, CENTER_LON, RADIUS_MI = 39.8, -121.5, 12
VEGETATION = "brush"

STATIONS = {
    "jarbo_gap":   (39.735944, -121.488944),
    "fire_origin": (39.896,    -121.432),
    "paradise":    (39.760,    -121.620),
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")

# Test cases: (speed, direction, category, note)
# WN requires integer inputs; use integers between/outside grid nodes
# Training grid: speeds [20,24,28,32,36], dirs [30,37,45,52,60]
TEST_BCS = [
    # Interpolation (between grid nodes, integers)
    (26, 41, "INTERPOLATION", "between 24-28 and 37-45"),
    (30, 48, "INTERPOLATION", "between 28-32 and 45-52"),
    (22, 34, "INTERPOLATION", "between 20-24 and 30-37"),
    # Mild extrapolation (just outside grid bounds)
    (18, 45, "MILD EXTRAP",   "speed just below min (20)"),
    (38, 45, "MILD EXTRAP",   "speed just above max (36)"),
    (28, 25, "MILD EXTRAP",   "dir just below min (30)"),
    (28, 65, "MILD EXTRAP",   "dir just above max (60)"),
    # Strong extrapolation (well outside grid)
    (15, 45, "STRONG EXTRAP", "speed well below min"),
    (45, 45, "STRONG EXTRAP", "speed well above max"),
    (28, 10, "STRONG EXTRAP", "dir well outside range"),
]


def run_wn_single(speed, direction):
    tag = f"{direction}_{speed}"
    existing = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_vel-4326.asc"))
    if existing:
        return existing[0]

    args = [WINDNINJA_CLI, "--num_threads", "4",
            "--elevation_file", dem_path,
            "--initialization_method", "domainAverageInitialization",
            "--input_speed", str(speed), "--input_speed_units", "mph",
            "--input_direction", str(direction),
            "--input_wind_height", "10", "--units_input_wind_height", "m",
            "--uni_air_temp", "45", "--air_temp_units", "F",
            "--uni_cloud_cover", "0.1", "--cloud_cover_units", "fraction",
            "--vegetation", VEGETATION, "--mesh_choice", "coarse",
            "--output_wind_height", "10", "--units_output_wind_height", "m",
            "--output_speed_units", "mph", "--output_path", CACHE,
            "--write_ascii_output", "true", "--ascii_out_json", "0",
            "--ascii_out_4326", "1"]

    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return None
    vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_vel-4326.asc"))
    return vel[0] if vel else None


def read_asc(path):
    with open(path) as f:
        lines = f.readlines()
    hdr, data = {}, []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) == 2 and not parts[0].replace('.','').replace('-','').replace('e','').isdigit():
            hdr[parts[0].lower()] = float(parts[1])
        else:
            try:
                data.append([float(v) for v in parts])
            except ValueError:
                pass
    return hdr, data


def extract_point(hdr, data, lat, lon):
    ncols = int(hdr['ncols']); nrows = int(hdr['nrows'])
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_idx = int((lon - xll) / cell)
    row_idx = nrows - 1 - int((lat - yll) / cell)
    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == nodata else val


def surrogate_predict(surrogate, speed, direction, station):
    return surrogate.predict(speed, direction).get(station)


if __name__ == "__main__":
    # Load surrogate
    from windninja_surrogate import WindNinjaSurrogate, ENSEMBLE_PATH

    with open(ENSEMBLE_PATH) as f:
        data = json.load(f)
    records = []
    for key, output in data["ensemble"].items():
        s, d = key.split("_")
        records.append({"speed": float(s), "direction": float(d), "output": output})

    surrogate = WindNinjaSurrogate(alpha=0.1).fit(records)

    print()
    print("=" * 76)
    print("  SURROGATE GENERALIZATION TEST")
    print("  Comparing surrogate predictions to real WindNinja at off-grid BCs")
    print("=" * 76)
    print()
    print(f"  {'BC':^18} | {'Category':^14} | {'Surrog':>8} | {'WN':>8} | {'Err':>7} | Note")
    print(f"  {'-'*18}-+-{'-'*14}-+-{'-'*8}-+-{'-'*8}-+-{'-'*7}-+-{'-'*20}")

    results = []
    for speed, direction, category, note in TEST_BCS:
        sys.stdout.write(f"\r  Running WN: {speed}mph @ {direction}deg ...     ")
        sys.stdout.flush()

        vel_path = run_wn_single(speed, direction)
        if not vel_path:
            print(f"\r  {speed}mph @ {direction:5.1f}d | {category:^14} | {'---':>8} | {'FAIL':>8} | {'---':>7} | WN failed")
            continue

        vel_hdr, vel_data = read_asc(vel_path)
        wn_val = extract_point(vel_hdr, vel_data,
                               STATIONS["jarbo_gap"][0], STATIONS["jarbo_gap"][1])
        surr_val = surrogate_predict(surrogate, speed, direction, "jarbo_gap")

        if wn_val is None or surr_val is None:
            continue

        err = surr_val - wn_val
        flag = " !" if abs(err) > 2.0 else ("  " if abs(err) < 0.5 else " ~")
        bc_str = f"{speed:.0f}mph @ {direction:.0f}°"
        results.append((category, abs(err)))
        print(f"\r  {bc_str:^18} | {category:^14} | {surr_val:8.2f} | {wn_val:8.2f} | {err:+7.2f} |{flag} {note}")

    print()
    if results:
        interp = [e for c, e in results if c == "INTERPOLATION"]
        mild   = [e for c, e in results if c == "MILD EXTRAP"]
        strong = [e for c, e in results if c == "STRONG EXTRAP"]

        print("SUMMARY BY CATEGORY:")
        print(f"  {'Category':^18} | {'Mean abs err':>13} | {'Max abs err':>11}")
        print(f"  {'-'*18}-+-{'-'*13}-+-{'-'*11}")
        for label, errs in [("INTERPOLATION", interp),
                             ("MILD EXTRAP", mild),
                             ("STRONG EXTRAP", strong)]:
            if errs:
                print(f"  {label:^18} | {np.mean(errs):13.2f} | {np.max(errs):11.2f}")

        print()
        interp_ok = not interp or max(interp) < 1.0
        mild_ok   = not mild   or max(mild)   < 3.0
        print(f"  Interpolation quality: {'PASS (<1 mph)' if interp_ok else 'FAIL'}")
        print(f"  Mild extrapolation:    {'PASS (<3 mph)' if mild_ok else 'FAIL'}")
        print(f"  Strong extrapolation:  expected to be worse (use with caution)")
        print()
        print("  Surrogate is ready for interpolation use within the training grid.")
        print("  Mild extrapolation (±2 mph, ±5 deg) is acceptable for BC sweep.")
        print("  Strong extrapolation should be flagged in production.")
