#!/usr/bin/env python3
"""
windninja_case9.py
==================
Case 9 -- Tubbs Fire, October 8-9 2017
WindNinja terrain downscaling.

Run: python windninja_case9.py

BC from hrrr_700hpa_case9.py (fxx=4, ignition ~04:45z):
  HRRR 700 hPa domain mean: 23.6 mph @ 26 deg NNE
  (slightly more northerly than Camp Fire's 50 NE; Mayacamas orientation)

Domain: centered 38.7N / -122.75W, 16mi radius
  Covers both validation stations in one grid:
    Fire ignition  38.57N  -122.58W  ~8mi from center
    Hawkeye RAWS   38.80N  -122.90W  ~6mi from center
    Santa Rosa     38.44N  -122.71W  ~9mi from center

Validation targets (Mass & Ovens 2019 BAMS -- pre-registered):
  Hawkeye gust 79 mph; sustained TBD (est ~49 mph at gust factor ~1.625)
  Santa Rosa gust 68 mph; sustained TBD (est ~42 mph)
  Gust factor: TBD -- apply §2.2 cross-check, do not assume 1.625 from Jarbo

Notes on vegetation:
  Mayacamas / Sonoma coast range: mixed chaparral/oak woodland
  Using "trees" (closest WN approximation to coastal scrub)
"""

import subprocess, sys, os, glob, math
sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

CENTER_LAT = 38.7
CENTER_LON = -122.75
RADIUS_MI  = 16
WIND_SPEED = 24          # HRRR 700 hPa prior (23.6 rounded)
WIND_DIR   = 26          # HRRR 700 hPa prior direction (NNE)
VEGETATION = "trees"

STATIONS = {
    "ignition":   (38.570, -122.580, "Fire origin    Calistoga/Tubbs Lane"),
    "hawkeye":    (38.800, -122.900, "Hawkeye RAWS   ~45km NW Santa Rosa  (ID TBD)"),
    "santa_rosa": (38.440, -122.710, "Santa Rosa     city RAWS            (ID TBD)"),
    "fountgrove": (38.480, -122.680, "Fountaingrove  early fire spread area"),
}

# Pre-registered validation targets (Mass & Ovens 2019; sustained TBD)
OBSERVED_GUSTS = {
    "hawkeye":    79.0,   # mph gust -- record NE (Mass & Ovens 2019)
    "santa_rosa": 68.0,   # mph gust -- 2nd record NE
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")


def run_windninja(speed=WIND_SPEED, direction=WIND_DIR):
    existing = glob.glob(os.path.join(
        CACHE, f"{dem_stem}_{direction}_{speed}_*_vel-4326.asc"))
    if existing:
        ang = glob.glob(os.path.join(
            CACHE, f"{dem_stem}_{direction}_{speed}_*_ang-4326.asc"))
        print(f"  Cached: {os.path.basename(existing[0])}")
        return existing[0], ang[0] if ang else None

    args = [WINDNINJA_CLI, "--num_threads", "8"]
    if os.path.exists(dem_path):
        print(f"  DEM cached: {dem_stem}.tif")
        args += ["--elevation_file", dem_path]
    else:
        print(f"  Fetching DEM: {dem_stem}.tif  ({CENTER_LAT}N/{CENTER_LON}W, {RADIUS_MI}mi) ...")
        args += [
            "--fetch_elevation",  dem_path,
            "--x_center",         str(CENTER_LON),
            "--y_center",         str(CENTER_LAT),
            "--x_buffer",         str(RADIUS_MI),
            "--y_buffer",         str(RADIUS_MI),
            "--buffer_units",     "miles",
            "--elevation_source", "srtm",
        ]

    args += [
        "--initialization_method",    "domainAverageInitialization",
        "--input_speed",              str(speed),
        "--input_speed_units",        "mph",
        "--input_direction",          str(direction),
        "--input_wind_height",        "10",
        "--units_input_wind_height",  "m",
        "--uni_air_temp",             "65",     # warm October night
        "--air_temp_units",           "F",
        "--uni_cloud_cover",          "0.1",
        "--cloud_cover_units",        "fraction",
        "--vegetation",               VEGETATION,
        "--mesh_choice",              "coarse",
        "--output_wind_height",       "10",
        "--units_output_wind_height", "m",
        "--output_speed_units",       "mph",
        "--output_path",              CACHE,
        "--write_ascii_output",       "true",
        "--ascii_out_json",           "0",
        "--ascii_out_4326",           "1",
    ]

    print(f"  Running WindNinja: {direction}deg / {speed}mph ...")
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:400]}")
        return None, None

    print("  WindNinja complete.")
    vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{direction}_{speed}_*_vel-4326.asc"))
    ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{direction}_{speed}_*_ang-4326.asc"))
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
    xll   = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_idx = int((lon - xll) / cell)
    row_idx = nrows - 1 - int((lat - yll) / cell)
    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == nodata else val


def print_results(vel_path, ang_path, speed=WIND_SPEED, direction=WIND_DIR):
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)
    ncols = int(vel_hdr['ncols']); nrows = int(vel_hdr['nrows'])
    res_m = vel_hdr['cellsize'] * 111000

    print(f"\n{'='*72}")
    print(f"  WindNinja — Case 9 Tubbs Fire  October 8-9 2017")
    print(f"  BC: {direction}deg / {speed} mph  (HRRR 700 hPa prior)")
    print(f"  Grid: {ncols}x{nrows}  res~{res_m:.0f}m  center {CENTER_LAT}N/{CENTER_LON}W  {RADIUS_MI}mi")
    print(f"{'='*72}")
    print(f"\n  {'Station':^28} | {'WN dir':>6} | {'WN sust':>8} | {'Ratio':>6} | "
          f"{'Obs gust':>9} | Notes")
    print(f"  {'-'*28}-+-{'-'*6}-+-{'-'*8}-+-{'-'*6}-+-{'-'*9}-+-{'-'*20}")

    results = {}
    for stid, (lat, lon, label) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        results[stid] = (ang, spd)

        if spd is None:
            print(f"  {label[:28]:^28} | {'---':>6} | {'---':>8} | {'---':>6} | "
                  f"{'---':>9} | outside grid")
            continue

        ratio = spd / speed
        ang_s = f"{ang:.0f}d" if ang else "---"
        obs_g = OBSERVED_GUSTS.get(stid)
        obs_s = f"{obs_g:.0f} mph" if obs_g else "TBD"
        flag  = " AMPLIFIED" if ratio > 1.20 else (" sheltered" if ratio < 0.80 else "")
        print(f"  {label[:28]:^28} | {ang_s:>6} | {spd:>6.1f}mph | {ratio:>6.2f}x | "
              f"{obs_s:>9} | WN={ratio:.2f}x{flag}")

    print(f"\n  BC: {speed} mph @ {direction}deg  |  >1.20x amplified  <0.80x sheltered")
    print(f"\n  Copy into case9_reconstruction.py WINDNINJA dict:")
    for stid, (ang, spd) in results.items():
        if ang is not None:
            print(f'    "{stid}": ({ang:.0f}, {spd:.1f}),')
        else:
            print(f'    "{stid}": None,  # outside grid')
    return results


if __name__ == "__main__":
    print(f"\nCase 9 — Tubbs Fire  October 8-9 2017")
    print(f"WindNinja {RADIUS_MI}mi grid, center {CENTER_LAT}N/{CENTER_LON}W")
    print(f"BC: {WIND_DIR}deg / {WIND_SPEED} mph  (HRRR 700 hPa prior)")
    print()

    # Coverage check
    for stid, (lat, lon, desc) in STATIONS.items():
        dlat_mi = abs(lat - CENTER_LAT) * 69.1
        dlon_mi = abs(lon - CENTER_LON) * 69.1 * math.cos(math.radians(CENTER_LAT))
        dist_mi = math.sqrt(dlat_mi**2 + dlon_mi**2)
        flag = "in grid" if dist_mi <= RADIUS_MI else "OUTSIDE"
        print(f"  {desc[:40]:40s}  {dist_mi:.1f}mi  {flag}")
    print()

    vel_path, ang_path = run_windninja()
    if vel_path:
        print_results(vel_path, ang_path)
    else:
        print("WindNinja run failed or DEM fetch failed.")
