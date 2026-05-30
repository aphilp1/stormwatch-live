#!/usr/bin/env python3
"""
windninja_case8.py
==================
Case 8 -- Thomas Fire, December 4 2017
WindNinja terrain downscaling.

Run: python windninja_case8.py  (no conda env needed)

BC from hrrr_700hpa_case8.py (fxx=9, ignition ~09:45z):
  700 hPa domain mean: 28.8 mph @ 310 deg NW
  (domain-mean NW flow descending over Topa Topa / Santa Ynez into Ventura basin)

Stability: stable (Santa Ana = descending, adiabatically warmed, dry)

Domain center: 34.44N / 119.05W (Thomas Aquinas College / fire origin area)
Radius: 12 mi  (covers Topa Topa crest to Ventura coast)

Stations (validated against RAWS archive -- gusts TBD):
  Fire origin  34.441N  -118.984W  ~1000ft  (Thomas Aquinas College)
  Topa Topa    34.520N  -119.080W  ~6230ft  (upwind ridge crest)
  Wheeler Spr  34.522N  -119.318W  ~2050ft  (RAWS, W of fire)
  Oxnard ASOS  34.200N  -119.207W  ~10ft    (KOXR, coast reference)
  Santa Paula  34.354N  -119.056W  ~300ft   (city ASOS, near fire)

Notes on BC choice:
  700 hPa HRRR = 28.8 mph -- this is the HRRR prior for bc_label_generator.
  For the BC sweep, the optimal BC may be higher (same pattern as Camp Fire
  where HRRR 25.2 was corrected to optimal 35 mph, a +9.8 mph residual).
  Expect positive delta; run a few WN candidates bracketing 25-45 mph @ 310 deg.
"""

import subprocess, sys, os, glob
sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

CENTER_LAT = 34.44
CENTER_LON = -119.05
RADIUS_MI  = 12
WIND_SPEED = 29          # initial run: HRRR 700 hPa prior (28.8 mph, rounded)
WIND_DIR   = 310         # 700 hPa domain mean direction
VEGETATION = "trees"     # southern CA chaparral -- closest WN option

STATIONS = {
    "fire_origin":  (34.441,  -118.984, "Fire origin  ~1000ft"),
    "topa_topa":    (34.520,  -119.080, "Topa Topa   ~6230ft  (ridge crest)"),
    "wheeler_spr":  (34.522,  -119.318, "Wheeler Spr ~2050ft  (RAWS)"),
    "oxnard_asos":  (34.200,  -119.207, "KOXR Oxnard ~10ft    (ASOS coast)"),
    "santa_paula":  (34.354,  -119.056, "Santa Paula ~300ft   (near fire)"),
}

# Observed gusts -- fill from RAWS archive (WPNC1, KOXR, etc.)
# LSRs document 40-60+ mph gusts in Ventura County Dec 4 2017.
# TODO: pull from IEM ASOS (KOXR, KSBP) and Synoptic (WPNC1, local RAWS)
OBSERVED_GUSTS = {
    "fire_origin": None,   # TODO
    "topa_topa":   None,   # TODO
    "wheeler_spr": None,   # TODO
    "oxnard_asos": None,   # TODO -- KOXR IEM ASOS
    "santa_paula": None,   # TODO
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")


def run_windninja(speed=WIND_SPEED, direction=WIND_DIR, stability="stable"):
    existing_vel = glob.glob(os.path.join(
        CACHE, f"{dem_stem}_{direction}_{speed}_*_vel-4326.asc"))
    if existing_vel:
        print(f"  Cached: {os.path.basename(existing_vel[0])}")
        ang = glob.glob(os.path.join(
            CACHE, f"{dem_stem}_{direction}_{speed}_*_ang-4326.asc"))
        return existing_vel[0], ang[0] if ang else None

    args = [WINDNINJA_CLI, "--num_threads", "8"]

    if os.path.exists(dem_path):
        print(f"  DEM cached: {dem_stem}.tif")
        args += ["--elevation_file", dem_path]
    else:
        print(f"  Fetching DEM: {dem_stem}.tif  (center {CENTER_LAT},{CENTER_LON}, {RADIUS_MI}mi)")
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
        "--initialization_method",   "domainAverageInitialization",
        "--input_speed",             str(speed),
        "--input_speed_units",       "mph",
        "--input_direction",         str(direction),
        "--input_wind_height",       "10",
        "--units_input_wind_height", "m",
        "--uni_air_temp",            "85",     # warm Santa Ana descent ~85F
        "--air_temp_units",          "F",
        "--uni_cloud_cover",         "0.1",    # clear skies
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

    print(f"\n  Running WindNinja: {direction}deg / {speed}mph ({stability}) ...")
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print("  ERROR: timed out")
        return None, None

    if result.returncode != 0:
        print(f"  ERROR:\n{result.stderr[:800]}")
        return None, None

    print("  WindNinja complete.")
    vel = glob.glob(os.path.join(
        CACHE, f"{dem_stem}_{direction}_{speed}_*_vel-4326.asc"))
    ang = glob.glob(os.path.join(
        CACHE, f"{dem_stem}_{direction}_{speed}_*_ang-4326.asc"))
    return (vel[0] if vel else None), (ang[0] if ang else None)


def read_asc(path):
    with open(path) as f:
        lines = f.readlines()
    hdr, data = {}, []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        if (len(parts) == 2
                and not parts[0].replace('.','').replace('-','').replace('e','').isdigit()):
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
    print(f"  WindNinja — Case 8 Thomas Fire  December 4 2017")
    print(f"  Init: {direction}deg FROM / {speed} mph  (HRRR 700 hPa prior)")
    print(f"  Grid: {ncols}x{nrows}  res~{res_m:.0f}m  center {CENTER_LAT}N/{CENTER_LON}W")
    print(f"{'='*72}")
    print(f"\n  {'Station':^22} | {'WN Dir':>6} | {'WN Spd':>8} | {'Ratio':>6} | {'Obs gust':>8} | Notes")
    print(f"  {'-'*22}-+-{'-'*6}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*22}")

    results = {}
    for stid, (lat, lon, label) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        results[stid] = (ang, spd)

        if spd is None:
            print(f"  {label:^22} | {'---':>6} | {'---':>8} | {'---':>6} | {'---':>8} | outside grid")
        else:
            ratio = spd / speed
            obs = OBSERVED_GUSTS.get(stid)
            obs_s = f"{obs:.0f} mph" if obs else "TODO"
            flag = " AMPLIFIED" if ratio > 1.20 else (" sheltered" if ratio < 0.80 else "")
            ang_s = f"{ang:.0f}deg" if ang else "---"
            print(f"  {label:^22} | {ang_s:>6} | {spd:>6.1f} mph | {ratio:>6.2f}x | {obs_s:>8} |{flag}")

    print(f"\n  BC: {speed} mph @ {direction}deg  |  >1.20x amplified  <0.80x sheltered")
    print(f"\n  Copy into case8_reconstruction.py WINDNINJA dict:")
    for stid, (ang, spd) in results.items():
        if ang is not None:
            print(f'    "{stid}": ({ang:.0f}, {spd:.1f}),')
        else:
            print(f'    "{stid}": None,  # outside grid')

    return results


if __name__ == "__main__":
    print(f"\nCase 8 — Thomas Fire  December 4 2017")
    print(f"WindNinja {RADIUS_MI}mi grid, center {CENTER_LAT}N/{CENTER_LON}W")
    print(f"BC: {WIND_DIR}deg / {WIND_SPEED} mph  (HRRR 700 hPa prior, stable)")
    print("=" * 72)

    vel_path, ang_path = run_windninja()
    if vel_path:
        print_results(vel_path, ang_path)
    else:
        print("\nWindNinja run failed or DEM not available.")
        print("If DEM is missing, WindNinja will auto-fetch it on first run.")
