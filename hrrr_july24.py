import warnings
warnings.filterwarnings("ignore")
from herbie import Herbie
import numpy as np

# NIFC RAWS-confirmed coordinates (queried 2026-05-09)
STATIONS = {
    "KMSO":  (46.916,   -114.090,  "KMSO  3205ft"),
    "MPOI":  (46.876,   -114.082,  "PtSix 6300ft"),
    "BLMM8": (46.82073, -114.10089,"BluMt 3412ft"),  # NIFC confirmed (not 46.832/-114.216)
    "TS897": (46.749,   -114.066,  "Lolo  3200ft"),
}

# July 24 2024 derecho: 21:00 MDT = 03z July 25
# Pull 00z July 24 run fxx=15-27 (15z Jul24=09MDT through 03z Jul25=21MDT)
TARGET_HOURS = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

def extract_wind(ds_u, ds_v, lat, lon_neg):
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values
    lon360 = lon_neg + 360
    dist2d = (lats - lat)**2 + (lons - lon360)**2
    iy, ix = np.unravel_index(dist2d.argmin(), dist2d.shape)
    u = float(ds_u["u10"].values[iy, ix]) * 2.23694
    v = float(ds_v["v10"].values[iy, ix]) * 2.23694
    spd  = (u**2 + v**2)**0.5
    dirn = (270 - np.degrees(np.arctan2(v, u))) % 360
    return dirn, spd

print()
print("HRRR 10m Wind — July 24, 2024  (AWS S3, 3km CONUS)")
print("700 hPa 00z July 25: 30 mph / 234 deg SW  (OTX sounding)")
print("Derecho struck 21:00 MDT = 03z July 25 = fxx=27")
print("=" * 72)
print(f"  {'UTC':>5}  {'MDT':>5} | {'KMSO 3205ft':^14} | {'PtSix 6300ft':^14} | {'BluMt 3412ft':^14} | {'Lolo 3200ft':^14}")
print(f"  {'':5}  {'':5} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14} | {'Dir  Spd':^14}")
print("  " + "-" * 72)

for fxx in TARGET_HOURS:
    # fxx=24 means 00z July 25; adjust display
    if fxx < 24:
        utc_label = f"{fxx:02d}z24"
        mdt = fxx - 6
        mdt_label = f"{mdt:02d}M24"
    else:
        utc_label = f"{fxx-24:02d}z25"
        mdt = fxx - 6 - 24 + 24
        mdt_label = f"{fxx-30:02d}M25" if fxx >= 30 else f"{fxx-24:02d}M25"
        mdt_label = f"{(fxx-24):02d}z25"

    mdt_hr = (fxx - 6) % 24
    day_label = "Jul24" if fxx < 24 else "Jul25"
    utc_hr = fxx % 24

    try:
        H    = Herbie("2024-07-24 00:00", model="hrrr", product="sfc", fxx=fxx)
        ds_u = H.xarray("UGRD:10 m")
        ds_v = H.xarray("VGRD:10 m")

        row = f"  {utc_hr:02d}z{day_label[3:]}  {mdt_hr:02d}M{day_label[3:]} |"
        for stid, (lat, lon, label) in STATIONS.items():
            dirn, spd = extract_wind(ds_u, ds_v, lat, lon)
            row += f" {dirn:3.0f}  {spd:4.1f} |"
        print(row)
    except Exception as e:
        print(f"  {utc_hr:02d}z{day_label[3:]}  ERROR: {e}")

print()
print("  Dir = FROM direction (met convention).  All values 10m AGL.")
print("  STORM HIT: 03z Jul25 (fxx=27) — obs are CONVECTIVE gusts, not terrain flow")
print("  Source: noaa-hrrr-bdp-pds.s3.amazonaws.com  /  Herbie + cfgrib")
