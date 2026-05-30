#!/usr/bin/env python3
"""
windninja_confidence_engine.py
================================
Phase A confidence engine: quantify uncertainty in the terrain wind field
arising from BC uncertainty.

Run: python windninja_confidence_engine.py

The confidence engine answers:
  Given a range of plausible boundary conditions (HRRR prior ± uncertainty),
  what is the SPREAD of WindNinja terrain wind fields at key stations?

  Low spread  -> terrain response is ROBUST to BC uncertainty (high confidence)
  High spread -> terrain response SENSITIVE to BC uncertainty (low confidence)

This is the first real uncertainty quantification on the terrain fields.

BC Ensemble design (5x5 = 25 members):
  Speed:     [20, 24, 28, 32, 36] mph   (HRRR prior 25.2 ± ~8 mph)
  Direction: [30, 37, 45, 52, 60] deg   (HRRR prior 50 ± 15 deg)
  Stability: neutral (fixed for Phase A)

Domain: Camp Fire, 39.8N/-121.5W/12mi (corrected Jarbo coords)
  DEM already cached as dem_39.8_-121.5_12mi.tif

Stations (NIFC-authoritative):
  Jarbo Gap    39.735944  -121.488944   2536ft  CAL FIRE 041214
  Fire origin  39.896     -121.432       --
  Paradise     39.760     -121.620       --

Note: Colby Mountain (40.14, -121.52) and Saddleback (39.63, -120.86) are
outside this 12mi domain -- they need separate WN runs when obs arrive.

Observed validation targets (for speed context):
  Jarbo Gap: sustained ~32 mph, gust 52 mph (Brewer & Clements 2020)
  Gust factor: 1.625 (empirical from paper)
"""

import subprocess, sys, os, glob, math, json
from itertools import product
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"
CENTER_LAT    = 39.8
CENTER_LON    = -121.5
RADIUS_MI     = 12
VEGETATION    = "brush"

# BC ensemble grid
SPEED_MEMBERS = [20, 24, 28, 32, 36]       # mph
DIR_MEMBERS   = [30, 37, 45, 52, 60]       # degrees
STABILITY     = "neutral"

# HRRR prior for reference
HRRR_PRIOR_SPEED = 25.2
HRRR_PRIOR_DIR   = 50.0

# Observed targets for validation context
OBS = {
    "jarbo_gap": {"sustained": 32.0, "gust": 52.0, "gust_factor": 1.625},
}

# Stations to extract
STATIONS = {
    "jarbo_gap":   (39.735944, -121.488944, "Jarbo Gap  2536ft"),
    "fire_origin": (39.896,    -121.432,    "Fire origin Pulga"),
    "paradise":    (39.760,    -121.620,    "Paradise   foothills"),
}

dem_stem = f"dem_{CENTER_LAT}_{CENTER_LON}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")

TOTAL = len(SPEED_MEMBERS) * len(DIR_MEMBERS)


# ---------------------------------------------------------------------------
# WindNinja runner (with DEM fetch/cache)
# ---------------------------------------------------------------------------

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
        print(f"  Fetching DEM {dem_stem}.tif ...")
        args += [
            "--fetch_elevation", dem_path,
            "--x_center", str(CENTER_LON), "--y_center", str(CENTER_LAT),
            "--x_buffer", str(RADIUS_MI),  "--y_buffer", str(RADIUS_MI),
            "--buffer_units", "miles", "--elevation_source", "srtm",
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

    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return None, None

    vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_vel-4326.asc"))
    ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{tag}_*_ang-4326.asc"))
    return (vel[0] if vel else None), (ang[0] if ang else None)


# ---------------------------------------------------------------------------
# ASC reader / point extractor
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  WINDNINJA CONFIDENCE ENGINE  --  Camp Fire domain")
    print(f"  BC ensemble: {len(SPEED_MEMBERS)} speeds × {len(DIR_MEMBERS)} dirs = {TOTAL} members")
    print(f"  Speeds: {SPEED_MEMBERS} mph")
    print(f"  Dirs:   {DIR_MEMBERS} deg")
    print(f"  HRRR prior: {HRRR_PRIOR_SPEED} mph @ {HRRR_PRIOR_DIR} deg")
    print("=" * 72)
    print()

    # Run all ensemble members
    ensemble = {}   # (speed, direction) -> {station_id: sustained_mph}
    done = 0

    for speed, direction in product(SPEED_MEMBERS, DIR_MEMBERS):
        done += 1
        sys.stdout.write(f"\r  Running {done}/{TOTAL}: {speed}mph @ {direction}deg ...     ")
        sys.stdout.flush()

        vel_path, ang_path = run_wn(speed, direction)
        if not vel_path:
            continue

        vel_hdr, vel_data = read_asc(vel_path)
        member = {}
        for stid, (lat, lon, _) in STATIONS.items():
            spd = extract_point(vel_hdr, vel_data, lat, lon)
            member[stid] = spd
        ensemble[(speed, direction)] = member

    print(f"\r  Ensemble complete: {len(ensemble)}/{TOTAL} members ran successfully.     ")

    # ---------------------------------------------------------------------------
    # Compute ensemble statistics per station
    # ---------------------------------------------------------------------------

    print()
    print("ENSEMBLE STATISTICS (sustained wind, mph)")
    print("=" * 72)

    station_stats = {}
    for stid, (lat, lon, label) in STATIONS.items():
        vals = [ensemble[bc][stid] for bc in ensemble
                if ensemble[bc].get(stid) is not None]
        if not vals:
            continue
        vals = np.array(vals)
        stats = {
            "mean":   float(np.mean(vals)),
            "median": float(np.median(vals)),
            "std":    float(np.std(vals)),
            "min":    float(np.min(vals)),
            "max":    float(np.max(vals)),
            "range":  float(np.max(vals) - np.min(vals)),
            "cv":     float(np.std(vals) / np.mean(vals)) if np.mean(vals) > 0 else 0,
            "n":      len(vals),
        }
        station_stats[stid] = stats

        obs = OBS.get(stid, {})
        obs_s = f"(obs sust ~{obs['sustained']:.0f} mph)" if obs.get('sustained') else ""
        print(f"\n  {label} {obs_s}")
        print(f"    Ensemble mean:   {stats['mean']:.1f} mph  (median {stats['median']:.1f})")
        print(f"    Std deviation:   {stats['std']:.1f} mph")
        print(f"    Range:           {stats['min']:.1f} – {stats['max']:.1f} mph  "
              f"(spread {stats['range']:.1f} mph)")
        print(f"    CV (spread/mean): {stats['cv']:.2f}  "
              f"({'HIGH sensitivity' if stats['cv'] > 0.15 else 'moderate' if stats['cv'] > 0.08 else 'LOW sensitivity'})")
        if obs.get('sustained'):
            pct_within = sum(1 for v in vals
                           if abs(v - obs['sustained']) <= 5) / len(vals) * 100
            print(f"    % members within 5 mph of obs sustained ({obs['sustained']:.0f} mph): "
                  f"{pct_within:.0f}%")

    # ---------------------------------------------------------------------------
    # Speed-direction sensitivity breakdown (Jarbo Gap)
    # ---------------------------------------------------------------------------

    print()
    print("SPEED vs DIRECTION SENSITIVITY  --  Jarbo Gap")
    print("=" * 72)
    print(f"\n  WN sustained (mph) at Jarbo Gap  [rows=direction, cols=speed]")
    print(f"  {'Dir\\Speed':>8}", end="")
    for s in SPEED_MEMBERS:
        print(f"  {s:5.0f}", end="")
    print()
    print("  " + "-" * (10 + 7 * len(SPEED_MEMBERS)))

    for d in DIR_MEMBERS:
        row_vals = []
        print(f"  {d:8.0f}°", end="")
        for s in SPEED_MEMBERS:
            val = ensemble.get((s, d), {}).get("jarbo_gap")
            if val is not None:
                print(f"  {val:5.1f}", end="")
                row_vals.append(val)
            else:
                print(f"  {'---':>5}", end="")
        print()

    # ---------------------------------------------------------------------------
    # Amplification ratio grid
    # ---------------------------------------------------------------------------

    print()
    print("AMPLIFICATION RATIO AT JARBO GAP  [WN sust / BC speed]")
    print(f"  {'Dir\\Speed':>8}", end="")
    for s in SPEED_MEMBERS:
        print(f"  {s:5.0f}", end="")
    print()
    print("  " + "-" * (10 + 7 * len(SPEED_MEMBERS)))

    for d in DIR_MEMBERS:
        print(f"  {d:8.0f}°", end="")
        for s in SPEED_MEMBERS:
            val = ensemble.get((s, d), {}).get("jarbo_gap")
            if val is not None:
                print(f"  {val/s:5.2f}", end="")
            else:
                print(f"  {'---':>5}", end="")
        print()

    # ---------------------------------------------------------------------------
    # Confidence summary
    # ---------------------------------------------------------------------------

    print()
    print("CONFIDENCE SUMMARY")
    print("=" * 72)
    print(f"  {'Station':^28} | {'Mean±Std':^14} | {'Range':^10} | {'CV':^6} | Verdict")
    print(f"  {'-'*28}-+-{'-'*14}-+-{'-'*10}-+-{'-'*6}-+-{'-'*20}")
    for stid, (lat, lon, label) in STATIONS.items():
        s = station_stats.get(stid)
        if not s:
            continue
        verdict = ("HIGH sensitivity" if s['cv'] > 0.15 else
                   "moderate" if s['cv'] > 0.08 else "LOW sensitivity")
        print(f"  {label:^28} | {s['mean']:5.1f}±{s['std']:4.1f} mph  | "
              f"{s['min']:4.1f}-{s['max']:4.1f}  | {s['cv']:.2f}  | {verdict}")

    print()
    print("  LOW sensitivity  -> BC uncertainty has little effect; forecast confident")
    print("  HIGH sensitivity -> terrain response depends strongly on BC; less confident")

    # Save ensemble data for surrogate WN training (Phase B)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ensemble_campfire.json")
    save_data = {
        "domain": {"center_lat": CENTER_LAT, "center_lon": CENTER_LON,
                   "radius_mi": RADIUS_MI},
        "ensemble": {f"{s}_{d}": ensemble.get((s, d), {})
                     for s, d in product(SPEED_MEMBERS, DIR_MEMBERS)},
        "station_stats": station_stats,
        "hrrr_prior": {"speed": HRRR_PRIOR_SPEED, "dir": HRRR_PRIOR_DIR},
        "obs": OBS,
    }
    with open(out_path, "w") as f:
        json.dump(save_data, f, indent=2)
    print(f"\n  Ensemble data saved to ensemble_campfire.json")
    print(f"  (This will be Phase B surrogate WindNinja training input)")
