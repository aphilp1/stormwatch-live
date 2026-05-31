#!/usr/bin/env python
"""
era5_event_pull.py — ERA5 pressure-level + single-level pull for the four
extreme fire-wind events, via the Copernicus CDS API.
Conventions from stormwatch_test_protocol.md: vec_avg on u/v (never raw degrees),
met FROM-direction, mph = m/s x 2.23694, 700 hPa BC with geo-height readout.
Requires cdsapi (>=0.7.7), xarray, numpy, netcdf4. Reads ~/.cdsapirc.
Accept the licence once on both dataset pages or you get a 403:
reanalysis-era5-pressure-levels and reanalysis-era5-single-levels.
"""

import os
import sys
import numpy as np

try:
    import cdsapi
except ImportError:
    sys.exit("cdsapi not installed. conda install -n hrrr311 -c conda-forge 'cdsapi>=0.7.7'")

OUT_DIR = "./era5"
MS_TO_MPH = 2.23694
G0 = 9.80665
AREA = [42.0, -124.0, 35.0, -117.0]
LEVELS = ["500", "700", "850", "925", "1000"]
PL_VARS = [
    "u_component_of_wind",
    "v_component_of_wind",
    "geopotential",
    "temperature",
    "relative_humidity",
]
SL_VARS = ["mean_sea_level_pressure"]
ALL_HOURS = [f"{h:02d}:00" for h in range(24)]

EVENTS = {
    "camp_2018": {"year": "2018", "month": "11", "days": ["07", "08", "09"],
                  "ignition_utc": "2018-11-08 ~14:33Z (06:33 PST)"},
    "tubbs_2017": {"year": "2017", "month": "10", "days": ["08", "09", "10"],
                   "ignition_utc": "2017-10-09 night"},
    "thomas_2017": {"year": "2017", "month": "12", "days": ["04", "05", "06"],
                    "ignition_utc": "2017-12-05 ~03Z"},
    "kincade_2019": {"year": "2019", "month": "10", "days": ["23", "24", "25"],
                     "ignition_utc": "2019-10-24 ~04:27Z (21:27 PDT 23 Oct)"},
}

def speed_dir_from_uv(u, v):
    spd = np.sqrt(u**2 + v**2) * MS_TO_MPH
    drc = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
    return spd, drc

def vec_avg(u, v):
    return speed_dir_from_uv(np.asarray(u), np.asarray(v))

def _client():
    return cdsapi.Client()

def pull_pressure_levels(client, name, ev):
    target = os.path.join(OUT_DIR, f"era5_pl_{name}.nc")
    if os.path.exists(target):
        print(f"  [skip] {target} exists")
        return target
    req = {
        "product_type": ["reanalysis"],
        "variable": PL_VARS,
        "pressure_level": LEVELS,
        "year": [ev["year"]], "month": [ev["month"]], "day": ev["days"],
        "time": ALL_HOURS,
        "area": AREA,
        "data_format": "netcdf",
    }
    print(f"  pulling pressure levels -> {target}")
    client.retrieve("reanalysis-era5-pressure-levels", req, target)
    return target

def pull_single_levels(client, name, ev):
    target = os.path.join(OUT_DIR, f"era5_sl_{name}.nc")
    if os.path.exists(target):
        print(f"  [skip] {target} exists")
        return target
    req = {
        "product_type": ["reanalysis"],
        "variable": SL_VARS,
        "year": [ev["year"]], "month": [ev["month"]], "day": ev["days"],
        "time": ALL_HOURS,
        "area": AREA,
        "data_format": "netcdf",
    }
    print(f"  pulling single levels -> {target}")
    client.retrieve("reanalysis-era5-single-levels", req, target)
    return target

def _find(ds, names):
    for n in names:
        if n in ds.variables or n in ds.coords or n in ds.dims:
            return n
    return None

def summarize(name, pl_path):
    try:
        import xarray as xr
    except ImportError:
        print("  (xarray not installed; skipping summary)")
        return
    ds = xr.open_dataset(pl_path)
    tname = _find(ds, ["valid_time", "time"])
    lev = _find(ds, ["pressure_level", "level", "isobaricInhPa"])
    lat = _find(ds, ["latitude", "lat"])
    lon = _find(ds, ["longitude", "lon"])
    uvar = _find(ds, ["u", "u_component_of_wind"])
    vvar = _find(ds, ["v", "v_component_of_wind"])
    zvar = _find(ds, ["z", "geopotential"])
    if not all([tname, lev, lat, lon, uvar, vvar]):
        print(f"  [warn] couldn't map all coords in {pl_path}; vars present:")
        print("   ", list(ds.variables))
        return
    sel700 = {lev: 700}
    u700 = ds[uvar].sel(**sel700).mean(dim=[lat, lon])
    v700 = ds[vvar].sel(**sel700).mean(dim=[lat, lon])
    spd, drc = vec_avg(u700.values, v700.values)
    peak_i = int(np.nanargmax(spd))
    times = ds[tname].values
    print(f"  700 hPa domain-mean: peak {spd[peak_i]:.1f} mph @ {drc[peak_i]:.0f}deg "
          f"at {np.datetime_as_string(times[peak_i], unit='h')}Z")
    print(f"  700 hPa domain-mean window range: {np.nanmin(spd):.1f}-{np.nanmax(spd):.1f} mph")
    if zvar:
        ght = (ds[zvar].sel(**sel700).mean(dim=[lat, lon]) / G0)
        print(f"  700 hPa geo height (domain-mean): {float(ght.mean()):.0f} m")
    ds.close()

def main(only=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    client = _client()
    names = [only] if only else list(EVENTS)
    for name in names:
        ev = EVENTS[name]
        print(f"\n=== {name} ({ev['year']}-{ev['month']}-{ev['days'][0]}..{ev['days'][-1]} UTC) ===")
        print(f"    ignition: {ev['ignition_utc']}  |  box N,W,S,E = {AREA}")
        try:
            pl = pull_pressure_levels(client, name, ev)
            pull_single_levels(client, name, ev)
            summarize(name, pl)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            print("  If 403: accept the dataset licence on the CDS dataset page.")

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(only=arg)
