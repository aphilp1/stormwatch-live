#!/usr/bin/env python3
"""
hrrr_case5_iowa_derecho.py  --  conda run -n hrrr311 python hrrr_case5_iowa_derecho.py

Case 5 -- Iowa Derecho  August 10, 2020
HRRR 3km winds at Iowa stations during peak derecho passage.

Run: 12z Aug 10 2020, fxx=3-10 covers 15z-22z (10 AM - 5 PM CDT)
Peak event in eastern Iowa: ~17z (12 PM CDT)
Atkins IA (peak 126 mph): ~17:28z
"""
import warnings
warnings.filterwarnings("ignore")
from herbie import Herbie
import numpy as np, sys
sys.stdout.reconfigure(encoding='utf-8')

STATIONS = {
    "ATKINS": (41.790, -91.770, "Atkins IA     126mph gust site"),
    "CID":    (41.884, -91.711, "KCID          Cedar Rapids"),
    "ALO":    (42.557, -92.401, "KALO          Waterloo"),
    "AMW":    (41.990, -93.621, "KAMW          Ames"),
    "DSM":    (41.534, -93.663, "KDSM          Des Moines"),
}

TARGET_HOURS = list(range(3, 11))   # fxx=3-10: 15z-22z

def extract_wind(ds_u, ds_v, lat, lon_neg):
    lats = ds_u.latitude.values; lons = ds_u.longitude.values
    lon360 = lon_neg + 360
    dist2d = (lats - lat)**2 + (lons - lon360)**2
    iy, ix = np.unravel_index(dist2d.argmin(), dist2d.shape)
    u = float(ds_u["u10"].values[iy, ix]) * 2.23694
    v = float(ds_v["v10"].values[iy, ix]) * 2.23694
    spd  = (u**2 + v**2)**0.5
    dirn = (270 - np.degrees(np.arctan2(v, u))) % 360
    return dirn, spd

print()
print("HRRR 10m Wind -- Iowa Derecho  August 10 2020  (AWS S3, 3km CONUS)")
print("Type 1: Convective cold pool  |  CDT = UTC-5")
print("Peak event: ~17z (12 PM CDT)  |  Atkins IA 126mph at 17:28z")
print("OAX 12z env: 500hPa W 23mph / 700hPa WNW 21mph / 850hPa W 16mph")
print("=" * 80)
print(f"  {'UTC':>8} {'CDT':>4} | {'Atkins':^12} | {'KCID':^12} | {'KALO':^12} | {'KAMW':^12} | {'KDSM':^12}")
print(f"  {'':8} {'':4} | {'Dir Spd':^12} | {'Dir Spd':^12} | {'Dir Spd':^12} | {'Dir Spd':^12} | {'Dir Spd':^12}")
print("  " + "-" * 81)

for fxx in TARGET_HOURS:
    utc_h = (12 + fxx) % 24
    cdt   = utc_h - 5
    peak_flag = " <-- PEAK (~17:28z)" if utc_h == 17 else ""

    try:
        H    = Herbie("2020-08-10 12:00", model="hrrr", product="sfc", fxx=fxx)
        ds_u = H.xarray("UGRD:10 m")
        ds_v = H.xarray("VGRD:10 m")
        row  = f"  {utc_h:02d}z Aug10 {cdt:02d}M |"
        for stid, (lat, lon, label) in STATIONS.items():
            d, s = extract_wind(ds_u, ds_v, lat, lon)
            row += f" {d:3.0f} {s:4.1f} |"
        print(row + peak_flag)
    except Exception as e:
        print(f"  {utc_h:02d}z  ERROR: {e}")

print()
print("  Dir = FROM direction (met). All 10m AGL.")
print("  Obs: Atkins 126mph (17:28z), Cedar Rapids 130mph (17:28z)")
print("  Source: noaa-hrrr-bdp-pds S3 / Herbie + cfgrib")
