import warnings
warnings.filterwarnings("ignore")
from herbie import Herbie
import numpy as np

STATIONS = {
    "KMSO":  (46.916, -114.090, "KMSO  3205ft"),
    "MPOI":  (46.876, -114.082, "PtSix 6300ft"),
    "BLMM8": (46.832, -114.216, "BluMt 3412ft"),
    "TS897": (46.749, -114.066, "Lolo  3200ft"),
}

TARGET_HOURS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]


def extract_wind(ds_u, ds_v, lat, lon_neg):
    """Extract u,v at nearest grid point. HRRR lon is 0-360."""
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values
    lon360 = lon_neg + 360          # convert -114 -> 246
    dist2d = (lats - lat)**2 + (lons - lon360)**2
    iy, ix = np.unravel_index(dist2d.argmin(), dist2d.shape)
    u = float(ds_u["u10"].values[iy, ix]) * 2.23694   # m/s -> mph
    v = float(ds_v["v10"].values[iy, ix]) * 2.23694
    spd  = (u**2 + v**2)**0.5
    dirn = (270 - np.degrees(np.arctan2(v, u))) % 360
    return dirn, spd


print()
print("HRRR 10m Wind — December 17, 2025  (AWS S3, 3km CONUS)")
print("700 hPa 12z: 25 kt / 28.8 mph from 315 NW  |  MST = UTC-7")
print("=" * 72)
print(f"  {'UTC':>5}  {'MST':>5} | {'KMSO 3205ft':^14} | {'PtSix 6300ft':^14} | {'BluMt 3412ft':^14} | {'Lolo 3200ft':^14}")
print(f"  {'':5}  {'':5} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14}")
print("  " + "-" * 72)

for fxx in TARGET_HOURS:
    mst = fxx - 7
    try:
        H    = Herbie("2025-12-17 00:00", model="hrrr", product="sfc", fxx=fxx)
        ds_u = H.xarray("UGRD:10 m")
        ds_v = H.xarray("VGRD:10 m")

        row = f"  {fxx:02d}z {mst:02d}M |"
        for stid, (lat, lon, label) in STATIONS.items():
            dirn, spd = extract_wind(ds_u, ds_v, lat, lon)
            row += f" {dirn:3.0f}  {spd:4.1f} |"
        print(row)
    except Exception as e:
        print(f"  {fxx:02d}z  ERROR: {e}")

print()
print("  Dir = FROM direction (met convention).  All values 10m AGL.")
print("  Source: noaa-hrrr-bdp-pds.s3.amazonaws.com  /  Herbie + cfgrib")
