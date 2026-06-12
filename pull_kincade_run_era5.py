#!/usr/bin/env python3
"""
pull_kincade_run_era5.py
========================
Pull ERA5 pressure-level data for the Kincade run phase (Oct 26-28 2019).
All 12 active kincade_run_2019 stations peaked Oct 27 UTC (01:29-12:57 local PDT).
Covers Oct 26-28 for full context.

Output: era5/era5_pl_kincade_run_2019.nc (same domain and levels as kincade_ign file)
"""
import os, sys, numpy as np

try:
    import cdsapi
except ImportError:
    sys.exit("cdsapi not installed")

OUT_DIR = "./era5"
AREA    = [42.0, -124.0, 35.0, -117.0]   # same box as ignition file [N,W,S,E]
LEVELS  = ["500", "700", "850", "925", "1000"]
PL_VARS = [
    "u_component_of_wind",
    "v_component_of_wind",
    "geopotential",
    "temperature",
    "relative_humidity",
]
HOURS = [f"{h:02d}:00" for h in range(24)]

TARGET = os.path.join(OUT_DIR, "era5_pl_kincade_run_2019.nc")

os.makedirs(OUT_DIR, exist_ok=True)

if os.path.exists(TARGET):
    print(f"Already exists: {TARGET}")
    sys.exit(0)

print(f"Pulling ERA5 pressure levels for Kincade run (Oct 26-28 2019)")
print(f"Domain: {AREA}  Levels: {LEVELS}")
print(f"Output: {TARGET}")

c = cdsapi.Client()
c.retrieve(
    "reanalysis-era5-pressure-levels",
    {
        "product_type": ["reanalysis"],
        "variable": PL_VARS,
        "pressure_level": LEVELS,
        "year": ["2019"],
        "month": ["10"],
        "day": ["26", "27", "28"],
        "time": HOURS,
        "area": AREA,
        "data_format": "netcdf",
    },
    TARGET,
)

print(f"\nPull complete: {TARGET}")

# Quick summary
try:
    import xarray as xr
    G0 = 9.80665
    ds = xr.open_dataset(TARGET)
    tname = next(n for n in ["valid_time","time"] if n in ds)
    lev   = next(n for n in ["pressure_level","level"] if n in ds)
    u850 = ds["u"].sel(**{lev: 850}).mean(dim=["latitude","longitude"])
    v850 = ds["v"].sel(**{lev: 850}).mean(dim=["latitude","longitude"])
    spd850 = np.sqrt(u850**2 + v850**2).values * 2.23694
    drc850 = ((270 - np.degrees(np.arctan2(v850.values, u850.values))) % 360)
    peak_i = int(np.nanargmax(spd850))
    times = ds[tname].values
    print(f"850 hPa domain-mean: peak {spd850[peak_i]:.1f} mph @ {drc850[peak_i]:.0f}deg "
          f"at {np.datetime_as_string(times[peak_i], unit='h')}Z")

    u700 = ds["u"].sel(**{lev: 700}).mean(dim=["latitude","longitude"])
    v700 = ds["v"].sel(**{lev: 700}).mean(dim=["latitude","longitude"])
    spd700 = np.sqrt(u700**2 + v700**2).values * 2.23694
    drc700 = ((270 - np.degrees(np.arctan2(v700.values, u700.values))) % 360)
    peak_i7 = int(np.nanargmax(spd700))
    print(f"700 hPa domain-mean: peak {spd700[peak_i7]:.1f} mph @ {drc700[peak_i7]:.0f}deg "
          f"at {np.datetime_as_string(times[peak_i7], unit='h')}Z")

    # Spot-check Oct 27 12Z at both levels
    ts = ds[tname].values
    idx_12z = np.where(ts == np.datetime64("2019-10-27T12"))[0]
    if len(idx_12z):
        i = idx_12z[0]
        u8_12 = float(u850.values[i]); v8_12 = float(v850.values[i])
        spd8 = np.sqrt(u8_12**2 + v8_12**2) * 2.23694
        drc8 = (270 - np.degrees(np.arctan2(v8_12, u8_12))) % 360
        u7_12 = float(u700.values[i]); v7_12 = float(v700.values[i])
        spd7 = np.sqrt(u7_12**2 + v7_12**2) * 2.23694
        drc7 = (270 - np.degrees(np.arctan2(v7_12, u7_12))) % 360
        print(f"\nOct 27 12Z domain-mean:")
        print(f"  850 hPa: {spd8:.1f} mph @ {drc8:.0f}deg")
        print(f"  700 hPa: {spd7:.1f} mph @ {drc7:.0f}deg")
    ds.close()
except Exception as e:
    print(f"Summary failed: {e}")
