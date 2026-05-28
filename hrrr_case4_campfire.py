#!/usr/bin/env python3
"""
hrrr_case4_campfire.py  --  run via: conda run -n hrrr311 python hrrr_case4_campfire.py

Case 4 -- Camp Fire  November 8, 2018
HRRR 3km winds at key stations near Feather River Canyon / Jarbo Gap.

Run: 12z Nov 8 2018, fxx=2-12 covers 14z-00z (ignition at ~14:30z)
"""
import warnings
warnings.filterwarnings("ignore")
from herbie import Herbie
import numpy as np, sys
sys.stdout.reconfigure(encoding='utf-8')

STATIONS = {
    "JARBO": (39.977, -121.422, "Jarbo Gap   ~2mi from ignition"),
    "FIRE":  (39.896, -121.432, "Camp Creek Rd  fire origin"),
    "PARA":  (39.760, -121.620, "Paradise    6mi W"),
    "RDD":   (40.509, -122.293, "KRDD Redding  valley floor"),
    "RBL":   (40.150, -122.252, "KRBL Red Bluff  valley"),
}

TARGET_HOURS = list(range(2, 13))   # fxx=2-12: 14z-00z

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
print("HRRR 10m Wind -- Camp Fire  November 8 2018  (AWS S3, 3km CONUS)")
print("Type 4: NE downslope / Feather River Canyon gap flow")
print("RNO 700hPa 12z: W 20mph (synoptic background, NOT the gap flow driver)")
print("ERA5 canyon: NE 19-25mph sust / 52-67mph gusts  |  PST = UTC-8")
print("Fire ignition: ~14:30z (6:30 AM PST)")
print("=" * 82)
print(f"  {'UTC':>8} {'PST':>4} | {'Jarbo Gap':^13} | {'Fire Origin':^13} | {'Paradise':^13} | {'KRDD':^13} | {'KRBL':^13}")
print(f"  {'':8} {'':4} | {'Dir  Spd':^13} | {'Dir  Spd':^13} | {'Dir  Spd':^13} | {'Dir  Spd':^13} | {'Dir  Spd':^13}")
print("  " + "-" * 88)

for fxx in TARGET_HOURS:
    utc_h = (12 + fxx) % 24
    pst   = utc_h - 8
    flag  = " <-- IGNITION ~14:30z" if fxx == 2 else ""

    try:
        H    = Herbie("2018-11-08 12:00", model="hrrr", product="sfc", fxx=fxx)
        ds_u = H.xarray("UGRD:10 m")
        ds_v = H.xarray("VGRD:10 m")
        row  = f"  {utc_h:02d}z Nov8 {pst:02d}M |"
        for stid, (lat, lon, label) in STATIONS.items():
            d, s = extract_wind(ds_u, ds_v, lat, lon)
            row += f" {d:3.0f}  {s:4.1f} |"
        print(row + flag)
    except Exception as e:
        print(f"  {utc_h:02d}z Nov8  ERROR: {e}")

print()
print("  Dir = FROM direction (met). All values 10m AGL.")
print("  Source: noaa-hrrr-bdp-pds S3 / Herbie + cfgrib")
print("  Copy fxx=2-6 rows into camp_fire_20181108.py HRRR dict.")
