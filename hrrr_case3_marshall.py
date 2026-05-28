#!/usr/bin/env python3
"""
hrrr_case3_marshall.py  --  run via: conda run -n hrrr311 python hrrr_case3_marshall.py

Case 3 -- Marshall Fire  December 30, 2021
HRRR 3km winds at key stations: BOU, BJC, EIK, DEN, and fire origin.

Run: 12z Dec 30 2021, fxx=3-18 covers 15z-06z (8 AM - 11 PM MST)
Fire ignition: ~18z Dec 30 (11 AM MST)
"""
import warnings
warnings.filterwarnings("ignore")
from herbie import Herbie
import numpy as np, sys
sys.stdout.reconfigure(encoding='utf-8')

STATIONS = {
    "BOU":  (40.0376,  -105.2264, "KBOU  5278ft Boulder"),
    "BJC":  (39.9088,  -105.1166, "KBJC  5673ft Broomfield"),
    "EIK":  (40.0105,  -105.0505, "KEIK  5130ft Erie"),
    "DEN":  (39.8561,  -104.6737, "KDEN  5431ft Denver"),
    "FIRE": (39.954,   -105.168,  "Marshall Rd 5420ft fire origin"),
}

TARGET_HOURS = list(range(3, 19))   # fxx=3-18: 15z-06z

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
print("HRRR 10m Wind -- Marshall Fire  December 30 2021  (AWS S3, 3km CONUS)")
print("700 hPa GJT 00z Dec 31: 31 mph WSW (250deg)  |  MST = UTC-7")
print("Fire ignition: ~18z (11 AM MST)")
print("=" * 80)
print(f"  {'UTC':>8} {'MST':>4} | {'KBOU':^14} | {'KBJC':^14} | {'KEIK':^14} | {'KDEN':^14} | {'Fire':^14}")
print(f"  {'':8} {'':4} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14}")
print("  " + "-" * 87)

for fxx in TARGET_HOURS:
    utc_h = (12 + fxx) % 24
    day   = "Dec30" if (12 + fxx) < 24 else "Dec31"
    mst   = (utc_h - 7) % 24
    flag  = " <-- IGNITION" if fxx == 6 else ""   # fxx=6 = 18z = fire ignition

    try:
        H    = Herbie("2021-12-30 12:00", model="hrrr", product="sfc", fxx=fxx)
        ds_u = H.xarray("UGRD:10 m")
        ds_v = H.xarray("VGRD:10 m")
        row  = f"  {utc_h:02d}z {day} {mst:02d}M |"
        for stid, (lat, lon, label) in STATIONS.items():
            d, s = extract_wind(ds_u, ds_v, lat, lon)
            row += f" {d:3.0f}  {s:4.1f} |"
        print(row + flag)
    except Exception as e:
        print(f"  {utc_h:02d}z {day}  ERROR: {e}")

print()
print("  Dir = FROM direction (met convention). All values 10m AGL.")
print("  Source: noaa-hrrr-bdp-pds.s3.amazonaws.com / Herbie + cfgrib")
print()
print("  Copy output into marshall_fire_20211230.py HRRR dict.")
