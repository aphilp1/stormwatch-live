#!/usr/bin/env python3
"""
hrrr_700hpa_case2.py
====================
run via: conda run -n hrrr311 python hrrr_700hpa_case2.py

Case 2 -- Missoula NW Flow, December 17 2025
HRRR 700 hPa wind over the Missoula domain for the BC audit.

Comparison:
  Sounding-derived WN BC  : 315 deg / 29 mph  (OTX + TFX radiosonde 12z, identical)
  HRRR 700 hPa domain mean: <- this script

Key run: 2025-12-17 00z, fxx=11-18 (valid 11-18z)
  fxx=12 = 12z valid: matches sounding time, WN initialization reference
  fxx=18 = 18z valid: start of coupled comparison window (cold pool mixed out)

Domain: Missoula valley + surrounding ridges
  Lat  46.5 – 47.5 N
  Lon  114.8 – 113.0 W  (negative geographic; HRRR uses 0-360 internally)

This is a PBL_TRANSIENT event (cold frontal wind shift). WindNinja applicability
is PARTIAL -- it can snapshot the pre-front NW regime and the post-front regime
but cannot model the transition itself.
"""
import warnings
warnings.filterwarnings("ignore")

import sys
import math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

LAT_MIN, LAT_MAX = 46.5, 47.5
LON_MIN, LON_MAX = -114.8, -113.0

INIT_TIME = "2025-12-17 00:00"
FXX_LIST  = [11, 12, 13, 14, 15, 16, 17, 18]

STATIONS = {
    "KMSO":  (46.916,   -114.090),
    "PNTM8": (47.04136, -113.98631),
    "BLMM8": (46.82073, -114.10089),
}

# Sounding-derived WN BC (the reference we're auditing against)
SOUNDING_BC_SPEED = 28.8   # mph (25 kt, OTX/TFX 12z identical)
SOUNDING_BC_DIR   = 315.0  # degrees NW


def domain_mean_wind(ds_u, ds_v):
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values
    lon_min360 = LON_MIN + 360
    lon_max360 = LON_MAX + 360
    mask = (
        (lats >= LAT_MIN) & (lats <= LAT_MAX) &
        (lons >= lon_min360) & (lons <= lon_max360)
    )
    u_var = [v for v in ds_u.data_vars if "UGRD" in v or "u" in v.lower()][0]
    v_var = [v for v in ds_v.data_vars if "VGRD" in v or "v" in v.lower()][0]
    u_vals = ds_u[u_var].values
    v_vals = ds_v[v_var].values
    u_domain = float(u_vals[mask].mean()) * 2.23694
    v_domain = float(v_vals[mask].mean()) * 2.23694
    spd = math.sqrt(u_domain**2 + v_domain**2)
    dirn = (270 - math.degrees(math.atan2(v_domain, u_domain))) % 360
    return dirn, spd


def point_wind(ds_u, ds_v, lat, lon_neg):
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
print("HRRR 700 hPa Wind -- Missoula NW Flow  2025-12-17  (prs product)")
print("Domain mean + per-station  |  fxx 11-18 = valid 11z-18z")
print(f"Sounding-derived WN BC  : {SOUNDING_BC_SPEED:.1f} mph @ {SOUNDING_BC_DIR:.0f} deg NW")
print("=" * 92)
print(f"  {'fxx':>4}  {'valid':>5} | {'DOMAIN MEAN':^18} | {'KMSO 700hPa':^14} | {'PNTM8 700hPa':^14} | {'BLMM8 700hPa':^14}")
print(f"  {'':4}  {'':5} | {'dir   spd':^18} | {'dir   spd':^14} | {'dir   spd':^14} | {'dir   spd':^14}")
print("  " + "-" * 96)

fxx12_dir, fxx12_spd = None, None

for fxx in FXX_LIST:
    valid_h = (0 + fxx) % 24
    flag = " <-- WN init reference" if fxx == 12 else ""
    flag = flag or (" <-- coupled window start" if fxx == 18 else "")

    try:
        H = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx)
        ds_u = H.xarray("UGRD:700 mb")
        ds_v = H.xarray("VGRD:700 mb")

        dm_dir, dm_spd = domain_mean_wind(ds_u, ds_v)
        row = f"  fxx{fxx:02d}  {valid_h:02d}z   | {dm_dir:5.0f}  {dm_spd:6.1f} mph   |"

        for sid, (lat, lon) in STATIONS.items():
            pd, ps = point_wind(ds_u, ds_v, lat, lon)
            row += f" {pd:4.0f}  {ps:5.1f} mph  |"

        print(row + flag)

        if fxx == 12:
            fxx12_dir, fxx12_spd = dm_dir, dm_spd

    except Exception as e:
        print(f"  fxx{fxx:02d}  {valid_h:02d}z   ERROR: {e}")

print()
print("  Dir = FROM direction (deg, met convention).  Speed in mph.")
print(f"  Domain mean: 46.5-47.5N, 114.8-113.0W")
print()

if fxx12_spd is not None:
    delta_s = fxx12_spd - SOUNDING_BC_SPEED
    delta_d = fxx12_dir - SOUNDING_BC_DIR
    delta_d_norm = (delta_d + 180) % 360 - 180
    print("BC AUDIT — Case 2  (PBL_TRANSIENT: WN applicability PARTIAL)")
    print("-" * 52)
    print(f"  HRRR 700 hPa fxx=12 domain mean : {fxx12_spd:.1f} mph @ {fxx12_dir:.0f} deg")
    print(f"  Sounding-derived WN BC          : {SOUNDING_BC_SPEED:.1f} mph @ {SOUNDING_BC_DIR:.0f} deg NW")
    print(f"  Delta speed                     : {delta_s:+.1f} mph")
    print(f"  Delta direction                 : {delta_d_norm:+.0f} deg")
    print()
    if abs(delta_s) <= 5 and abs(delta_d_norm) <= 20:
        print("  => SMALL residual: HRRR 700hPa closely matches sounding-derived BC.")
        print("     Copy into case2_reconstruction.py:")
    else:
        print("  => LARGE residual: HRRR 700hPa differs from sounding-derived BC.")
        print("     Sounding may be capturing mesoscale features HRRR misses (cold pool top,")
        print("     elevated wind max). Copy into case2_reconstruction.py:")
    print(f"       HRRR_700_SPEED = {fxx12_spd:.1f}")
    print(f"       HRRR_700_DIR   = {fxx12_dir:.1f}")
