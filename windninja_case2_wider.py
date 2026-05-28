#!/usr/bin/env python3
"""
windninja_case2_wider.py

Case 2 — Missoula NW Flow, December 17 2025
Wider WindNinja grid (12mi, center 46.9/-114.1) — DEM reused from Case 1.

Init: 315° NW / 29 mph
Source: OTX + TFX radiosonde 12z Dec 17 2025, 700 hPa = 25 kt / 315° (both identical)

Valid comparison window: 18-21z (11-14 MST) — cold pool fully mixed out, surface coupled

Stations:
  KMSO       46.916°N  -114.090°W   3205 ft  (ASOS — full day, 272 records)
  MPOI assum 46.876°N  -114.082°W   6300 ft  (assumed — coords RETIRED, see PNTM8)
  PNTM8      47.041°N  -113.986°W   7897 ft  (NIFC RAWS "Point 6" — correct coords)
  BLMM8      46.821°N  -114.101°W   3412 ft  (NIFC confirmed foothills SE — corrected)
  TS897/Lolo 46.749°N  -114.066°W   3200 ft  (Lolo Portable — outside old 8mi grid)
"""

import subprocess, sys, os, glob

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

CENTER_LAT = 46.9
CENTER_LON = -114.1
RADIUS_MI  = 12
WIND_SPEED = 29
WIND_DIR   = 315
VEGETATION = "trees"

STATIONS = {
    "KMSO":        (46.916,    -114.090,   "KMSO        3205ft  ASOS"),
    "MPOI_assum":  (46.876,    -114.082,   "PtSix_assum 6300ft  (retired)"),
    "PNTM8_NIFC":  (47.04136,  -113.98631, "PNTM8_NIFC  7897ft  (NIFC Point 6)"),
    "BLMM8":       (46.82073,  -114.10089, "BluMt_NIFC  3412ft  RAWS"),
    "TS897":       (46.749,    -114.066,   "Lolo        3200ft  RAWS"),
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")


def run_windninja():
    if not os.path.exists(dem_path):
        print(f"  ERROR: DEM not found at {dem_path}")
        print("  Run windninja_case1_wider.py first to fetch the 12mi DEM.")
        return None, None

    print(f"  DEM cached: {dem_stem}.tif")

    # Check if output already exists
    existing_vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_vel-4326.asc"))
    if existing_vel:
        print(f"  Cached output: {os.path.basename(existing_vel[0])}")
        ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_ang-4326.asc"))
        return existing_vel[0], ang[0] if ang else None

    args = [
        WINDNINJA_CLI,
        "--num_threads",             "8",
        "--elevation_file",          dem_path,
        "--initialization_method",   "domainAverageInitialization",
        "--input_speed",             str(WIND_SPEED),
        "--input_speed_units",       "mph",
        "--input_direction",         str(WIND_DIR),
        "--input_wind_height",       "10",
        "--units_input_wind_height", "m",
        "--uni_air_temp",            "35",
        "--air_temp_units",          "F",
        "--uni_cloud_cover",         "0.5",
        "--cloud_cover_units",       "fraction",
        "--vegetation",              VEGETATION,
        "--mesh_choice",             "coarse",
        "--output_wind_height",      "10",
        "--units_output_wind_height","m",
        "--output_speed_units",      "mph",
        "--output_path",             CACHE,
        "--write_ascii_output",      "true",
        "--ascii_out_json",          "0",
        "--ascii_out_4326",          "1",
    ]

    print(f"\n  Running WindNinja: {WIND_DIR}° / {WIND_SPEED} mph, {RADIUS_MI}mi grid ...")
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print("  ERROR: timed out")
        return None, None

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:800]}")
        return None, None

    print("  WindNinja complete.")
    vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_vel-4326.asc"))
    ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_ang-4326.asc"))
    if not vel:
        print("  ERROR: no output files found")
        return None, None
    print(f"  Output: {os.path.basename(vel[0])}")
    return vel[0], ang[0] if ang else None


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
    ncols  = int(hdr['ncols']); nrows = int(hdr['nrows'])
    xll    = hdr['xllcorner']; yll   = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_idx = int((lon - xll) / cell)
    row_idx = nrows - 1 - int((lat - yll) / cell)
    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == nodata else val


def grid_extent(hdr):
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    return yll, yll + int(hdr['nrows'])*cell, xll, xll + int(hdr['ncols'])*cell


def print_results(vel_path, ang_path):
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)

    s_lat, n_lat, w_lon, e_lon = grid_extent(vel_hdr)
    ncols = int(vel_hdr['ncols']); nrows = int(vel_hdr['nrows'])
    res_m = vel_hdr['cellsize'] * 111000

    print(f"\n{'='*72}")
    print(f"  WindNinja — Case 2 Missoula NW Flow  December 17 2025")
    print(f"  Init: {WIND_DIR}° FROM / {WIND_SPEED} mph  (OTX/TFX 700hPa 12z)")
    print(f"  Valid comparison window: 18-21z (coupled period, cold pool mixed out)")
    print(f"  Grid: {ncols}×{nrows}  res≈{res_m:.0f}m  Extent: {s_lat:.3f}–{n_lat:.3f}°N")
    print(f"{'='*72}")
    print(f"\n  {'Station':^24} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*24}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*22}")

    results = {}
    for stid, (lat, lon, label) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        results[stid] = (ang, spd)

        if spd is None:
            print(f"  {label:^24} |  {'---':>5} | {'---':>8} | {'---':>8} | outside grid")
        else:
            ratio = spd / WIND_SPEED
            flag  = " ▲ amplified" if ratio > 1.20 else (" ▼ sheltered" if ratio < 0.80 else "")
            ang_s = f"{ang:.0f}°" if ang is not None else "---"
            print(f"  {label:^24} | {ang_s:>6} | {spd:>6.1f} mph | {ratio:>7.2f}x |{flag}")

    print(f"\n  Init: {WIND_SPEED} mph from {WIND_DIR}°  |  >1.20x=amplified  <0.80x=sheltered")

    # Print values in dec17_final.py WINDNINJA dict format for easy copy-paste
    print(f"\n  ── Copy these into dec17_final.py WINDNINJA dict ──")
    for stid, key in [("KMSO","KMSO"), ("PNTM8_NIFC","MPOI"), ("BLMM8","BLMM8"), ("TS897","TS897")]:
        ang, spd = results.get(stid, (None, None))
        if ang is not None and spd is not None:
            print(f'    "{key}":  ({ang:.0f}, {spd:.1f}),')
        else:
            print(f'    "{key}":  None,  # outside grid')

    return results


if __name__ == "__main__":
    print("\nCase 2 — Missoula NW Flow  December 17 2025")
    print("WindNinja wider grid (12mi, DEM reused from Case 1)")
    print("=" * 72)

    vel_path, ang_path = run_windninja()
    if vel_path:
        print_results(vel_path, ang_path)
