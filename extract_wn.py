#!/usr/bin/env python3
"""Extract WindNinja ASC grid values at station coordinates."""
import sys, os, math
sys.stdout.reconfigure(encoding='utf-8')

CACHE = r"C:\temp\windninja_cache"

STATIONS = {
    "KMSO":  (46.916,   -114.090,  "KMSO  3205ft"),
    "MPOI":  (46.876,   -114.082,  "PtSix 6300ft"),
    "BLMM8": (46.82073, -114.10089,"BluMt 3412ft"),  # NIFC RAWS authoritative
    "TS897": (46.749,   -114.066,  "Lolo  3200ft"),
}

def read_asc(path):
    with open(path) as f:
        lines = f.readlines()
    hdr, data = {}, []
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
            hdr[parts[0].lower()] = float(parts[1])
        else:
            if parts:
                data.append([float(v) for v in parts])
    return hdr, data

def extract_point(hdr, data, lat, lon):
    ncols = int(hdr['ncols']); nrows = int(hdr['nrows'])
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    col = (lon - xll) / cell
    row_from_bottom = (lat - yll) / cell
    row_idx = nrows - 1 - int(row_from_bottom)
    col_idx = int(col)
    if row_idx < 0 or row_idx >= nrows or col_idx < 0 or col_idx >= ncols:
        return None
    val = data[row_idx][col_idx]
    return None if val == hdr.get('nodata_value', -9999) else val

def analyze_case(label, vel_file, ang_file):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  vel: {os.path.basename(vel_file)}")
    print(f"  ang: {os.path.basename(ang_file)}")
    print(f"{'='*60}")

    if not os.path.exists(vel_file):
        print("  ERROR: vel file not found")
        return
    if not os.path.exists(ang_file):
        print("  ERROR: ang file not found")
        return

    vel_hdr, vel_data = read_asc(vel_file)
    ang_hdr, ang_data = read_asc(ang_file)

    print(f"  Grid: {int(vel_hdr['ncols'])}x{int(vel_hdr['nrows'])} cells  "
          f"cellsize={vel_hdr['cellsize']:.4f}deg  "
          f"SW corner ({vel_hdr['yllcorner']:.4f}N, {vel_hdr['xllcorner']:.4f}E)")
    print(f"  {'Station':^14} | {'Dir':>5} | {'Spd (mph)':>9} | {'Status'}")
    print(f"  {'-'*14}-+-{'-'*5}-+-{'-'*9}-+-{'-'*20}")

    for stid, (lat, lon, label_s) in STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon)
        if spd is None:
            print(f"  {label_s:^14} | {'---':>5} | {'---':>9} | outside grid extent")
        else:
            print(f"  {label_s:^14} | {ang:5.1f} | {spd:9.1f} | ok")

# ── Dec 17 2025: 315° NW / 29 mph ────────────────────────────────────────────
# Two runs with slightly different centers — try both, use best coverage
analyze_case(
    "Dec 17 2025 — 315° NW / 29 mph  (center 46.9, -114.1)",
    os.path.join(CACHE, "dem_46.9_-114.1_8mi_315_29_406m_vel-4326.asc"),
    os.path.join(CACHE, "dem_46.9_-114.1_8mi_315_29_406m_ang-4326.asc"),
)
analyze_case(
    "Dec 17 2025 — 315° NW / 29 mph  (center 47.0, -114.0)",
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_315_29_406m_vel-4326.asc"),
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_315_29_406m_ang-4326.asc"),
)

# ── July 24 2024: 234° SW / 30 mph ───────────────────────────────────────────
analyze_case(
    "July 24 2024 — 234° SW / 30 mph  (center 47.0, -114.0)",
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_234_30_406m_vel-4326.asc"),
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_234_30_406m_ang-4326.asc"),
)

# ── Most recent run ───────────────────────────────────────────────────────────
analyze_case(
    "Most recent — 284° / 25 mph  (center 47.0, -114.0)",
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_284_25_406m_vel-4326.asc"),
    os.path.join(CACHE, "dem_47.0_-114.0_8mi_284_25_406m_ang-4326.asc"),
)

print()
