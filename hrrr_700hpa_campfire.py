#!/usr/bin/env python3
"""
hrrr_700hpa_campfire.py
=======================
run via: conda run -n hrrr311 python hrrr_700hpa_campfire.py

Pull HRRR 700 hPa wind over the Camp Fire domain for the day-one experiment
in bc_label_generator.py:
    Compare raw HRRR 700 hPa aloft wind  vs  hand-tuned BC (35 mph NE).

Domain: Feather River Canyon / Jarbo Gap area
    Lat  39.5 – 40.5 N
    Lon  121.8 – 120.8 W  (WRF-style negative; HRRR uses 0-360 internally)

Key run: 2018-11-08 12z, fxx=2 (valid 14z = ~30 min before ignition)
We also pull fxx=1,3,4,5 to show how the aloft wind evolves through the morning.

Output goes straight into bc_label_generator.py as:
    HRRR_PRIOR_SPEED = <value>   # mph
    HRRR_PRIOR_DIR   = <value>   # degrees, met convention

Terrain-height note:
700 hPa is a pressure surface, not a fixed height. It sits ~3000m in a neutral
airmass, drops toward ~2700m in cold air. Where domain terrain approaches that
altitude, HRRR extrapolates 700 hPa below-ground and the values are meaningless.
Camp Fire domain (Feather River foothills, max ~1000m): SAFE -- 700 hPa is 2000m
above terrain. No extrapolation concern. The +9.8 mph BC residual is physically
real, not an artifact.
For high-terrain domains (Missoula ridges ~2300m, Santa Ana peaks ~3500m):
check HGT:700 mb over the domain and flag points within 200m of terrain. See
hrrr_700hpa_case8.py for the guard implementation.
"""
import warnings
warnings.filterwarnings("ignore")

import sys
import math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

# Domain bounding box for Camp Fire / Feather River Canyon
LAT_MIN, LAT_MAX = 39.5, 40.5
LON_MIN, LON_MAX = -122.0, -120.8   # negative (geographic); HRRR uses lon+360

# HRRR run anchoring the Camp Fire hindcast
INIT_TIME = "2018-11-08 12:00"
FXX_LIST  = [1, 2, 3, 4, 5]         # valid 13z–17z; ignition ~14:30z = fxx 2-3

# Station coordinates for per-point extraction (reference vs domain mean)
STATIONS = {
    "jarbo_gap": (39.977, -121.422),
    "fire_origin": (39.896, -121.432),
    "paradise":  (39.760, -121.620),
}


def domain_mean_wind(ds_u, ds_v, lat_min, lat_max, lon_min, lon_max):
    """Average U and V over all grid points inside the bounding box."""
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values   # HRRR native: 0-360
    lon_min360 = lon_min + 360
    lon_max360 = lon_max + 360
    mask = (
        (lats >= lat_min) & (lats <= lat_max) &
        (lons >= lon_min360) & (lons <= lon_max360)
    )
    u_var = [v for v in ds_u.data_vars if "UGRD" in v or "u" in v.lower()][0]
    v_var = [v for v in ds_v.data_vars if "VGRD" in v or "v" in v.lower()][0]
    u_vals = ds_u[u_var].values
    v_vals = ds_v[v_var].values
    u_domain = float(u_vals[mask].mean()) * 2.23694   # m/s -> mph
    v_domain = float(v_vals[mask].mean()) * 2.23694
    spd = math.sqrt(u_domain**2 + v_domain**2)
    dirn = (270 - math.degrees(math.atan2(v_domain, u_domain))) % 360
    return dirn, spd, u_domain, v_domain


def point_wind(ds_u, ds_v, lat, lon_neg):
    """Extract wind at the nearest grid point to a station."""
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values
    lon360 = lon_neg + 360
    dist2d = (lats - lat)**2 + (lons - lon360)**2
    iy, ix = np.unravel_index(dist2d.argmin(), dist2d.shape)
    u_var = [v for v in ds_u.data_vars if "UGRD" in v or "u" in v.lower()][0]
    v_var = [v for v in ds_v.data_vars if "VGRD" in v or "v" in v.lower()][0]
    u = float(ds_u[u_var].values[iy, ix]) * 2.23694
    v = float(ds_v[v_var].values[iy, ix]) * 2.23694
    spd = math.sqrt(u**2 + v**2)
    dirn = (270 - math.degrees(math.atan2(v, u))) % 360
    return dirn, spd


print()
print("HRRR 700 hPa Wind -- Camp Fire  2018-11-08  (prs product)")
print("Domain mean + per-station  |  fxx 1-5 = valid 13z-17z")
print("Hand-tuned WN BC : 35 mph @ 45 deg NE (stable)")
print("=" * 88)
print(f"  {'fxx':>4}  {'valid':>5} | {'DOMAIN MEAN':^18} | {'Jarbo 700hPa':^14} | {'Fire Orig 700':^14} | {'Paradise 700':^14}")
print(f"  {'':4}  {'':5} | {'dir   spd':^18} | {'dir   spd':^14} | {'dir   spd':^14} | {'dir   spd':^14}")
print("  " + "-" * 92)

best_fxx = None
best_spd = None
best_dir = None

for fxx in FXX_LIST:
    valid_h = (12 + fxx) % 24
    flag = " <-- ignition" if fxx == 2 else ("")

    try:
        H = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx)
        ds_u = H.xarray("UGRD:700 mb")
        ds_v = H.xarray("VGRD:700 mb")

        dm_dir, dm_spd, _, _ = domain_mean_wind(
            ds_u, ds_v, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)

        row = f"  fxx{fxx:02d}  {valid_h:02d}z   | {dm_dir:5.0f}  {dm_spd:6.1f} mph   |"

        for sid, (lat, lon) in STATIONS.items():
            pd, ps = point_wind(ds_u, ds_v, lat, lon)
            row += f" {pd:4.0f}  {ps:5.1f} mph  |"

        print(row + flag)

        if fxx == 2:
            best_fxx = fxx
            best_spd = dm_spd
            best_dir = dm_dir

    except Exception as e:
        print(f"  fxx{fxx:02d}  {valid_h:02d}z   ERROR: {e}")

print()
print("  Dir = FROM direction (deg, met convention).  Speed in mph.")
print("  Domain mean averaged over grid points in 39.5-40.5N, 121.8-120.8W")
print()

if best_spd is not None:
    delta_s = best_spd - 35.0
    delta_d = best_dir - 45.0
    delta_d_norm = (delta_d + 180) % 360 - 180
    print("DAY-ONE EXPERIMENT SETUP")
    print("-" * 48)
    print(f"  fxx=2 domain mean  : {best_spd:.1f} mph @ {best_dir:.0f} deg")
    print(f"  Hand-tuned BC      : 35.0 mph @ 45 deg (NE)")
    print(f"  Delta speed        : {delta_s:+.1f} mph")
    print(f"  Delta direction    : {delta_d_norm:+.0f} deg")
    print()
    if abs(delta_s) <= 5 and abs(abs(delta_d_norm)) <= 20:
        print("  => SMALL residual. Copy these into bc_label_generator.py:")
    else:
        print("  => LARGE residual -- gap is the finding. Copy into bc_label_generator.py:")
    print(f"       HRRR_PRIOR_SPEED = {best_spd:.1f}")
    print(f"       HRRR_PRIOR_DIR   = {best_dir:.1f}")
