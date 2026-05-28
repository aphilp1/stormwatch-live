#!/usr/bin/env python3
"""
windninja_case1_wider.py

Case 1 — Missoula July 24 2024 Derecho
Wider WindNinja grid (12mi, center 46.9/-114.1) to cover all 4 stations.

Synoptic init: 234° SW / 30 mph
Source: OTX radiosonde 00z July 25, 700 hPa = 26 kt / 234° (identical at TFX)

Stations:
  KMSO       46.916°N  -114.090°W   3205 ft  (ASOS — 10-hr gap during event)
  MPOI/PtSix 46.876°N  -114.082°W   6300 ft  (assumed — coords UNVERIFIED)
  PNTM8      47.041°N  -113.986°W   7897 ft  (NIFC RAWS "Point 6" — may = MPOI)
  BLMM8      46.821°N  -114.101°W   3412 ft  (NIFC confirmed foothills SE)
  TS897/Lolo 46.749°N  -114.066°W   3200 ft  (Lolo Portable — outside old 8mi grid)
"""

import subprocess, sys, os, glob, math

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

# ── Grid parameters ──────────────────────────────────────────────────────────
CENTER_LAT = 46.9
CENTER_LON = -114.1
RADIUS_MI  = 12          # up from 8mi — covers Lolo (46.749°N) and PNTM8 (47.041°N)
WIND_SPEED = 30          # mph — from OTX 700hPa sounding 00z Jul 25
WIND_DIR   = 234         # degrees FROM — SW synoptic flow
VEGETATION = "trees"     # forested Missoula terrain

# ── Stations (all candidates including both MPOI coord hypotheses) ────────────
STATIONS = {
    "KMSO":        (46.916,    -114.090,   "KMSO        3205ft  ASOS"),
    "MPOI_assum":  (46.876,    -114.082,   "PtSix_assum 6300ft  (unverified)"),
    "PNTM8_NIFC":  (47.04136,  -113.98631, "PNTM8_NIFC  7897ft  (NIFC Point 6)"),
    "BLMM8":       (46.82073,  -114.10089, "BluMt_NIFC  3412ft  RAWS"),
    "TS897":       (46.749,    -114.066,   "Lolo        3200ft  RAWS"),
}

# ── DEM and output file paths ─────────────────────────────────────────────────
dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")


def run_windninja():
    """Run WindNinja CLI — fetches DEM if not cached."""
    args = [WINDNINJA_CLI, "--num_threads", "8"]

    if os.path.exists(dem_path):
        print(f"  DEM cached: {dem_stem}.tif — skipping fetch")
        args += ["--elevation_file", dem_path]
    else:
        print(f"  Fetching DEM: {dem_stem}.tif  (center {CENTER_LAT},{CENTER_LON}, {RADIUS_MI}mi)")
        args += [
            "--fetch_elevation",  dem_path,
            "--x_center",  str(CENTER_LON),
            "--y_center",  str(CENTER_LAT),
            "--x_buffer",  str(RADIUS_MI),
            "--y_buffer",  str(RADIUS_MI),
            "--buffer_units", "miles",
            "--elevation_source", "srtm",
        ]

    args += [
        "--initialization_method", "domainAverageInitialization",
        "--input_speed",        str(WIND_SPEED),
        "--input_speed_units",  "mph",
        "--input_direction",    str(WIND_DIR),
        "--input_wind_height",  "10",
        "--units_input_wind_height", "m",
        "--uni_air_temp",       "70",
        "--air_temp_units",     "F",
        "--uni_cloud_cover",    "0.5",
        "--cloud_cover_units",  "fraction",
        "--vegetation",         VEGETATION,
        "--mesh_choice",        "coarse",
        "--output_wind_height", "10",
        "--units_output_wind_height", "m",
        "--output_speed_units", "mph",
        "--output_path",        CACHE,
        "--write_ascii_output", "true",
        "--ascii_out_json",     "0",
        "--ascii_out_4326",     "1",
    ]

    print(f"\n  Running WindNinja: {WIND_DIR}° / {WIND_SPEED} mph, {RADIUS_MI}mi grid ...")
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print("  ERROR: WindNinja timed out after 10 minutes")
        return None, None

    if result.returncode != 0:
        print(f"  ERROR (exit {result.returncode}):\n{result.stderr[:800]}")
        return None, None

    print("  WindNinja complete.")

    # Find output files — WindNinja names them {dem_stem}_{dir}_{spd}_{res}m_vel-4326.asc
    vel_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_vel-4326.asc"))
    ang_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_ang-4326.asc"))

    if not vel_files:
        print(f"  ERROR: no vel output found in {CACHE}")
        print("  Available ASC files:")
        for f in glob.glob(os.path.join(CACHE, "*.asc")):
            print(f"    {os.path.basename(f)}")
        return None, None

    vel_path = vel_files[0]
    ang_path = ang_files[0] if ang_files else None
    print(f"  Output: {os.path.basename(vel_path)}")
    return vel_path, ang_path


def read_asc(path):
    """Read ESRI ASCII raster — returns (header dict, 2D list)."""
    with open(path) as f:
        lines = f.readlines()
    hdr, data = {}, []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) == 2 and not parts[0].replace('.', '').replace('-', '').replace('e', '').isdigit():
            hdr[parts[0].lower()] = float(parts[1])
        else:
            try:
                data.append([float(v) for v in parts])
            except ValueError:
                pass
    return hdr, data


def extract_point(hdr, data, lat, lon):
    """Bilinear-ish: return value at nearest grid cell."""
    ncols = int(hdr['ncols'])
    nrows = int(hdr['nrows'])
    xll   = hdr['xllcorner']
    yll   = hdr['yllcorner']
    cell  = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)

    col_f = (lon - xll) / cell
    row_f = (lat - yll) / cell
    row_idx = nrows - 1 - int(row_f)
    col_idx = int(col_f)

    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == nodata else val


def grid_extent(hdr):
    xll  = hdr['xllcorner']
    yll  = hdr['yllcorner']
    cell = hdr['cellsize']
    xur  = xll + int(hdr['ncols']) * cell
    yur  = yll + int(hdr['nrows']) * cell
    return yll, yur, xll, xur


def print_results(vel_path, ang_path):
    """Extract and print WindNinja values at all stations."""
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)

    s_lat, n_lat, w_lon, e_lon = grid_extent(vel_hdr)
    ncols = int(vel_hdr['ncols'])
    nrows = int(vel_hdr['nrows'])
    cell  = vel_hdr['cellsize']
    res_m = cell * 111000

    print(f"\n{'='*70}")
    print(f"  WindNinja Output — Case 1 Missoula Derecho  July 24 2024")
    print(f"  Init: {WIND_DIR}° FROM / {WIND_SPEED} mph  (OTX 700hPa sounding 00z Jul 25)")
    print(f"  Grid: {ncols}×{nrows} cells  res≈{res_m:.0f}m")
    print(f"  Extent: {s_lat:.3f}°–{n_lat:.3f}°N  {w_lon:.3f}°–{e_lon:.3f}°E")
    print(f"{'='*70}")
    print(f"\n  {'Station':^22} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*22}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*20}")

    for stid, (lat, lon, label) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None

        if spd is None:
            in_lat = s_lat <= lat <= n_lat
            in_lon = w_lon <= lon <= e_lon
            note = "outside grid" if not (in_lat and in_lon) else "nodata"
            print(f"  {label:^22} |  {'---':>5} | {'---':>8} | {'---':>8} | {note}")
        else:
            ratio = spd / WIND_SPEED
            flag  = " ▲ amplified" if ratio > 1.20 else (" ▼ sheltered" if ratio < 0.80 else "")
            ang_s = f"{ang:.0f}°" if ang is not None else "---"
            print(f"  {label:^22} | {ang_s:>6} | {spd:>6.1f} mph | {ratio:>7.2f}x |{flag}")

    print(f"\n  Init speed for reference: {WIND_SPEED} mph from {WIND_DIR}°")
    print(f"  >1.20x = terrain amplification  <0.80x = terrain sheltering\n")


# ── NWS LSR observed gusts for comparison ────────────────────────────────────
def print_obs():
    print(f"\n{'='*70}")
    print("  OBSERVED — NWS Local Storm Reports  Jul 24 2024  (WFO TFX)")
    print(f"  Source: IEM GeoJSON LSR API  (convective downdraft gusts)")
    print(f"{'='*70}")
    lsrs = [
        ("20:35 MDT", 72,  "5 SW Lolo       46.720°N -114.160°W", "CWOP MOMM8"),
        ("20:55 MDT", 95,  "1 SSW Missoula  46.860°N -114.010°W", "NWS damage survey"),
        ("21:00 MDT", 90,  "1 SSW Missoula  46.850°N -114.010°W", "toppled 70-yr maple"),
        ("21:01 MDT", 81,  "6 NW Missoula   46.920°N -114.090°W", "personal WX station"),
        ("21:03 MDT", 66,  "2 ENE Stevensville 46.530°N -114.050°W", "CWOP AV610"),
        ("21:04 MDT", 65,  "1 ENE E.Missoula 46.880°N -113.920°W", "WU KMTMILLT2"),
        ("21:05 MDT", 109, "2 SSW E.Missoula 46.850°N -113.960°W", "WU Mt.Sentinel 5026ft"),
        ("21:05 MDT", 80,  "3 ESE Frenchtown 47.000°N -114.180°W", "power outage report"),
    ]
    print(f"\n  {'Time':^10} | {'Gust':>6} | {'Location':^38} | {'Source'}")
    print(f"  {'-'*10}-+-{'-'*6}-+-{'-'*38}-+-{'-'*25}")
    for t, g, loc, src in lsrs:
        print(f"  {t:^10} | {g:>4} mph | {loc:^38} | {src}")
    print(f"\n  HRRR captured: ~8-10 mph SW — missed convective downdraft entirely")
    print(f"  WindNinja models terrain effects on SYNOPTIC flow only")
    print(f"  Gap: 65-109 mph obs vs ~20-30 mph WN output = convective downdraft\n")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nCase 1 — Missoula Derecho  July 24 2024")
    print("WindNinja wider grid run (12mi, all stations)")
    print("=" * 70)

    # Check if output already exists
    existing_vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_vel-4326.asc"))
    if existing_vel:
        print(f"\n  Cached output found: {os.path.basename(existing_vel[0])}")
        vel_path = existing_vel[0]
        existing_ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WIND_DIR}_{WIND_SPEED}_*_ang-4326.asc"))
        ang_path = existing_ang[0] if existing_ang else None
    else:
        vel_path, ang_path = run_windninja()

    if vel_path:
        print_results(vel_path, ang_path)

    print_obs()
