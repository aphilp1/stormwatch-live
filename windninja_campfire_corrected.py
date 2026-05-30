#!/usr/bin/env python3
"""
windninja_campfire_corrected.py
================================
Camp Fire -- corrected WindNinja run with NIFC-authoritative Jarbo Gap coordinates.

Previous runs used Jarbo Gap at (39.977, -121.422) -- wrong by ~27km.
NIFC-correct coords: (39.735944, -121.488944)  CAL FIRE RAWS 041214

Domain: centered at 39.8N, -121.5W, 12mi radius
  This covers BOTH stations in one grid:
    Jarbo Gap    39.736N  ~4.5mi from center  ✓
    Fire origin  39.896N  ~6.6mi from center  ✓

Two BC runs (comparing hand-tuned BC vs HRRR 700hPa prior):
  BC1: 35 mph @ 45 NE  (original hand-tuned BC)
  BC2: 25.2 mph @ 50   (HRRR 700 hPa domain mean, fxx=2 at ignition)

Validation targets from literature (Brewer & Clements 2020 / IBHS 2019):
  Jarbo Gap 8 Nov 2018: sustained ~32 mph, gust 52 mph
  Gust factor = 1.625 (physical, confirmed from paper)

Key question: does the corrected coordinate change the WN prediction at Jarbo?
  Old coords gave WN sustained = 49.7 mph (vs observed sustained 32 mph = 55% overshoot)
  New coords at correct ridge location may give a different result.

Run: python windninja_campfire_corrected.py
"""

import subprocess, sys, os, glob, math
sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

# Domain centered between Jarbo Gap and fire origin
CENTER_LAT = 39.8
CENTER_LON = -121.5
RADIUS_MI  = 12
VEGETATION = "brush"     # chaparral/brush for foothill terrain

# Boundary conditions to test
BCS = [
    (35,   45, "Hand-tuned BC (original)"),
    (25,   50, "HRRR 700hPa prior (rounded from 25.2 @ 50deg)"),
]

GUST_FACTOR = 1.625    # Jarbo Gap: sustained ~32 mph, gust 52 mph (Brewer & Clements 2020)

# Stations -- NIFC-authoritative coords
STATIONS = {
    "JARBO":    (39.735944, -121.488944, "Jarbo Gap RAWS  2535ft  CAL FIRE 041214"),
    "FIRE_ORI": (39.896,    -121.432,    "Fire origin     Pulga/Camp Creek Rd"),
    "PARADISE": (39.760,    -121.620,    "Paradise        foothills W"),
    "PULGA":    (39.896,    -121.432,    "Pulga area      canyon floor"),
}

# Literature validation (from Brewer & Clements 2020 / IBHS 2019)
OBSERVED = {
    "JARBO": {"sustained_mph": 32.0, "gust_mph": 52.0,
              "source": "Brewer & Clements 2020 / IBHS 2019 Fig 1"},
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")


def run_windninja(speed, direction):
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
        "--uni_air_temp",             "45",
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
    ncols  = int(hdr['ncols']); nrows = int(hdr['nrows'])
    xll    = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_idx = int((lon - xll) / cell)
    row_idx = nrows - 1 - int((lat - yll) / cell)
    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == nodata else val


def print_run_results(vel_path, ang_path, bc_speed, bc_dir, label):
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)

    print(f"\n  {'-'*70}")
    print(f"  BC: {bc_speed} mph @ {bc_dir}deg  |  {label}")
    print(f"  {'-'*70}")
    print(f"  {'Station':^22} | {'WN sust':>8} | {'Pred gust':>10} | {'Ratio':>6} | {'Obs sust':>9} | {'Obs gust':>9} | Notes")
    print(f"  {'-'*22}-+-{'-'*8}-+-{'-'*10}-+-{'-'*6}-+-{'-'*9}-+-{'-'*9}-+-{'-'*20}")

    for stid, (lat, lon, desc) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None

        if spd is None:
            print(f"  {desc[:22]:^22} | {'outside':>8} | {'---':>10} | {'---':>6} | {'---':>9} | {'---':>9} |")
            continue

        pred_gust = spd * GUST_FACTOR
        ratio     = spd / bc_speed
        ang_s     = f"{ang:.0f}d" if ang else "---"

        obs = OBSERVED.get(stid, {})
        obs_sust = f"{obs['sustained_mph']:.0f} mph" if obs.get('sustained_mph') else "---"
        obs_gust = f"{obs['gust_mph']:.0f} mph"      if obs.get('gust_mph')      else "---"

        # Comparison flags
        note = ""
        if obs.get('sustained_mph'):
            pct_err = (spd - obs['sustained_mph']) / obs['sustained_mph'] * 100
            note = f"sust err {pct_err:+.0f}%"
        elif ratio > 1.20:
            note = "AMPLIFIED"
        elif ratio < 0.80:
            note = "sheltered"

        print(f"  {desc[:22]:^22} | {spd:>6.1f}mph | {pred_gust:>8.1f}mph | "
              f"{ratio:>6.2f}x | {obs_sust:>9} | {obs_gust:>9} | {note}")

    # Summary for Jarbo Gap
    jarbo_spd = extract_point(vel_hdr, vel_data,
                              STATIONS["JARBO"][0], STATIONS["JARBO"][1])
    if jarbo_spd and "JARBO" in OBSERVED:
        obs_s = OBSERVED["JARBO"]["sustained_mph"]
        obs_g = OBSERVED["JARBO"]["gust_mph"]
        print()
        print(f"  JARBO AUDIT vs literature (Brewer & Clements 2020):")
        print(f"    WN sustained:  {jarbo_spd:.1f} mph  vs  observed sustained {obs_s:.0f} mph")
        print(f"    WN pred gust:  {jarbo_spd*GUST_FACTOR:.1f} mph  vs  observed gust {obs_g:.0f} mph")
        print(f"    Gust factor:   {GUST_FACTOR:.3f}  (52/32, from literature)")
        print(f"    Sust ratio:    {jarbo_spd/bc_speed:.2f}x amplification")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CAMP FIRE WindNinja -- CORRECTED JARBO GAP COORDINATES")
    print("  NIFC coords: 39.735944, -121.488944  (was 39.977, -121.422)")
    print(f"  Domain: {CENTER_LAT}N / {CENTER_LON}W / {RADIUS_MI}mi")
    print(f"  Gust factor: {GUST_FACTOR} (Brewer & Clements 2020: sust 32 mph, gust 52 mph)")
    print("=" * 72)
    print()
    print("Coverage check:")
    for stid, (lat, lon, desc) in STATIONS.items():
        dlat_mi = abs(lat - CENTER_LAT) * 69.1
        dlon_mi = abs(lon - CENTER_LON) * 69.1 * math.cos(math.radians(CENTER_LAT))
        dist_mi = math.sqrt(dlat_mi**2 + dlon_mi**2)
        flag = "✓ in grid" if dist_mi <= RADIUS_MI else "✗ OUTSIDE"
        print(f"  {desc[:35]:35s}  {dist_mi:.1f}mi from center  {flag}")

    print()

    for bc_speed, bc_dir, bc_label in BCS:
        print(f"\nRunning BC: {bc_speed} mph @ {bc_dir}deg  ({bc_label})")
        vel_path, ang_path = run_windninja(bc_speed, bc_dir)
        if vel_path:
            print_run_results(vel_path, ang_path, bc_speed, bc_dir, bc_label)
        else:
            print(f"  FAILED for {bc_speed} @ {bc_dir}")

    print()
    print("=" * 72)
    print("  Copy Jarbo results into camp_fire_20181108.py WINDNINJA section.")
    print("  Key: sustained-to-sustained comparison (WN sust vs obs sust 32 mph).")
    print("  The 49.7 mph prediction from wrong coords is now superseded.")
    print("=" * 72)
