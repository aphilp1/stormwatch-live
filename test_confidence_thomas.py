#!/usr/bin/env python3
"""
test_confidence_thomas.py
==========================
Run the confidence engine on the Thomas Fire domain.

Tests whether the direction-dominance pattern found at Camp Fire
(amplification ratio varies with direction, not speed) holds on different
terrain -- the Topa Topa / Ventura County coast range.

Pre-registered expectation (before running):
  Camp Fire finding: at Jarbo Gap, ratio is direction-only (1.03-1.19x),
  speed-invariant. If this is a general property of mass-conserving terrain
  solvers, it should hold at Thomas Fire stations too.
  If ratio varies with speed at Thomas, that's a terrain-specific finding.

BC grid: same as Camp Fire (5 speeds x 5 dirs = 25 members)
  Speeds: [20, 24, 28, 32, 36] mph
  Dirs:   [290, 300, 310, 320, 330] deg  (NNW-NW range for Thomas Fire)
  Note: Thomas Fire 700 hPa was ~310 deg at ignition; using NNW range.

Run: python test_confidence_thomas.py
"""

import subprocess, sys, os, glob, json, math
from itertools import product
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"
CENTER_LAT    = 34.44
CENTER_LON    = -119.05
RADIUS_MI     = 12
VEGETATION    = "trees"

STATIONS = {
    "fire_origin": (34.441, -118.984, "Fire origin  ~1000ft"),
    "topa_topa":   (34.520, -119.080, "Topa Topa   ~6230ft"),
    "santa_paula": (34.354, -119.056, "Santa Paula ~300ft"),
}

SPEED_MEMBERS = [20, 24, 28, 32, 36]
DIR_MEMBERS   = [290, 300, 310, 320, 330]   # NNW-NW range for Thomas

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")
TOTAL = len(SPEED_MEMBERS) * len(DIR_MEMBERS)


def run_wn(speed, direction):
    tag = f"{direction}_{speed}"
    existing = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_vel-4326.asc"))
    if existing:
        ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_ang-4326.asc"))
        return existing[0], ang[0] if ang else None

    args = [WINDNINJA_CLI, "--num_threads", "4"]
    if os.path.exists(dem_path):
        args += ["--elevation_file", dem_path]
    else:
        print(f"\n  Fetching DEM {dem_stem}.tif ...")
        args += ["--fetch_elevation", dem_path,
                 "--x_center", str(CENTER_LON), "--y_center", str(CENTER_LAT),
                 "--x_buffer", str(RADIUS_MI), "--y_buffer", str(RADIUS_MI),
                 "--buffer_units", "miles", "--elevation_source", "srtm"]

    args += ["--initialization_method", "domainAverageInitialization",
             "--input_speed", str(speed), "--input_speed_units", "mph",
             "--input_direction", str(direction),
             "--input_wind_height", "10", "--units_input_wind_height", "m",
             "--uni_air_temp", "85", "--air_temp_units", "F",
             "--uni_cloud_cover", "0.1", "--cloud_cover_units", "fraction",
             "--vegetation", VEGETATION, "--mesh_choice", "coarse",
             "--output_wind_height", "10", "--units_output_wind_height", "m",
             "--output_speed_units", "mph", "--output_path", CACHE,
             "--write_ascii_output", "true", "--ascii_out_json", "0",
             "--ascii_out_4326", "1"]

    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return None, None
    vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_vel-4326.asc"))
    ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_ang-4326.asc"))
    return (vel[0] if vel else None), (ang[0] if ang else None)


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


if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CONFIDENCE ENGINE -- Thomas Fire domain  (Topa Topa / Ventura)")
    print(f"  BC ensemble: {TOTAL} members ({len(SPEED_MEMBERS)} speeds x {len(DIR_MEMBERS)} dirs)")
    print(f"  Dirs: {DIR_MEMBERS} deg (NNW-NW, Thomas Fire 700hPa range)")
    print()
    print("  PRE-REGISTERED: expect direction-dominant amplification pattern")
    print("  (same as Camp Fire: ratio varies with dir, not speed)")
    print("=" * 72)

    ensemble = {}
    done = 0
    for speed, direction in product(SPEED_MEMBERS, DIR_MEMBERS):
        done += 1
        sys.stdout.write(f"\r  Running {done}/{TOTAL}: {speed}mph @ {direction}deg ...     ")
        sys.stdout.flush()
        vel_path, _ = run_wn(speed, direction)
        if not vel_path:
            continue
        vel_hdr, vel_data = read_asc(vel_path)
        member = {}
        for stid, (lat, lon, _) in STATIONS.items():
            spd = extract_point(vel_hdr, vel_data, lat, lon)
            member[stid] = spd
        ensemble[(speed, direction)] = member

    print(f"\r  Ensemble complete: {len(ensemble)}/{TOTAL} members.     ")

    # Amplification ratio table for Topa Topa (the key ridge station)
    print()
    print("AMPLIFICATION RATIO -- Topa Topa  [WN sust / BC speed]")
    print(f"  {'Dir\\Speed':>8}", end="")
    for s in SPEED_MEMBERS:
        print(f"  {s:5}", end="")
    print()
    print("  " + "-" * (10 + 7 * len(SPEED_MEMBERS)))

    dir_ratios = []
    for d in DIR_MEMBERS:
        print(f"  {d:8}°", end="")
        row_ratios = []
        for s in SPEED_MEMBERS:
            val = ensemble.get((s, d), {}).get("topa_topa")
            if val is not None:
                r = val / s
                print(f"  {r:5.2f}", end="")
                row_ratios.append(r)
            else:
                print(f"  {'---':>5}", end="")
        if row_ratios:
            dir_ratios.append((d, np.mean(row_ratios), np.std(row_ratios)))
        print()

    # Structural analysis
    print()
    print("STRUCTURAL ANALYSIS")
    print(f"  {'Dir':>6} | {'Mean ratio':>12} | {'Std across speeds':>18} | Verdict")
    print(f"  {'-'*6}-+-{'-'*12}-+-{'-'*18}-+-{'-'*20}")
    speed_invariant = True
    for d, mean_r, std_r in dir_ratios:
        verdict = "speed-invariant" if std_r < 0.01 else "speed-VARIANT"
        if std_r >= 0.01:
            speed_invariant = False
        print(f"  {d:6}° | {mean_r:12.3f} | {std_r:18.4f} | {verdict}")

    print()
    dir_ratio_range = max(r for _, r, _ in dir_ratios) - min(r for _, r, _ in dir_ratios)
    print(f"  Direction effect (ratio range): {dir_ratio_range:.3f}x")
    print(f"  Speed invariance: {'CONFIRMED' if speed_invariant else 'FAILS -- ratio varies with speed'}")
    print()

    if speed_invariant:
        print("  => CONFIRMS direction-dominance on Thomas Fire terrain.")
        print("     Same physics as Camp Fire: mass-conservation ratio is direction-only.")
        if dir_ratio_range > 0.1:
            print(f"     Direction range ({dir_ratio_range:.2f}x) larger than Camp Fire (0.16x) --")
            print("     Topa Topa terrain is more direction-sensitive.")
        else:
            print(f"     Direction range ({dir_ratio_range:.2f}x) similar to Camp Fire (0.16x).")
    else:
        print("  => BREAKS direction-dominance. Speed-variant ratio at Topa Topa.")
        print("     This terrain has different amplification physics from Camp Fire.")

    # Compare with Camp Fire finding
    print()
    print("CAMP FIRE vs THOMAS FIRE (Jarbo Gap vs Topa Topa at HRRR-prior speed ~28 mph):")
    cf_ratios = {30: 1.03, 37: 1.08, 45: 1.12, 52: 1.16, 60: 1.19}
    print(f"  Camp Fire  (dirs 30-60°):  ratio range {max(cf_ratios.values())-min(cf_ratios.values()):.2f}x")
    if dir_ratios:
        tf_mean_ratios = [(d, r) for d, r, _ in dir_ratios]
        tf_range = max(r for _, r in tf_mean_ratios) - min(r for _, r in tf_mean_ratios)
        print(f"  Thomas Fire (dirs 290-330°): ratio range {tf_range:.2f}x")
