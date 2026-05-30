#!/usr/bin/env python3
"""
hrrr_campfire_overnight.py
==========================
run via: conda run -n hrrr311 python hrrr_campfire_overnight.py

Camp Fire timing audit -- 00z Nov 8 2018 run, overnight through morning.
Resolves whether Camp Fire ignition was on the rising or declining limb
of the 700 hPa wind curve.

PRE-REGISTERED PREDICTION (set before data, 2026-05-30):
  Expected shape (from Mass 2021 description of "winds peaking around sunrise"):
  Winds rise overnight -> crest near/just before ignition (~14:33z = fxx=14) ->
  decline through morning.
  CONFIRMS timing pattern: peak at fxx<=14 (ignition on declining limb)
  BREAKS timing pattern:  peak at fxx>14  (ignition still on rising limb)

  Ignition: ~14:33z Nov 8 2018 = fxx=14-15 from 00z run

Run: 2018-11-08 00z, fxx=6-20
  fxx=6  = 06z = 10 PM PST Nov 7  (pre-event)
  fxx=12 = 12z = 04 AM PST Nov 8  (pre-dawn)
  fxx=14 = 14z = 06 AM PST Nov 8  (ignition ~06:33 PST = 14:33 UTC)
  fxx=18 = 18z = 10 AM PST Nov 8  (mid-morning)
  fxx=20 = 20z = 12 PM PST Nov 8  (midday)

Domain: same as hrrr_700hpa_campfire.py (terrain guard confirmed clean)
  Lat 39.5-40.5N, Lon 122.0-120.8W
"""
import warnings
warnings.filterwarnings("ignore")

import sys, math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

INIT_TIME = "2018-11-08 00:00"
FXX_LIST  = [6, 8, 10, 11, 12, 13, 14, 15, 16, 18, 20]
IGNITION_FXX = 14   # ~14:33z -> fxx=14 from 00z run

LAT_MIN, LAT_MAX = 39.5, 40.5
LON_MIN, LON_MAX = -122.0, -120.8

STATIONS = {
    "jarbo_gap":   (39.735944, -121.488944),   # NIFC authoritative
    "fire_origin": (39.896,    -121.432),
}


def get_mask(ds):
    lats = ds.latitude.values
    lons = ds.longitude.values
    return (
        (lats >= LAT_MIN) & (lats <= LAT_MAX) &
        (lons >= (LON_MIN + 360)) & (lons <= (LON_MAX + 360))
    )


def first_var(ds, candidates):
    for c in candidates:
        for v in ds.data_vars:
            if c.upper() in v.upper():
                return v
    raise KeyError(f"None of {candidates} found")


def domain_mean_wind(ds_u, ds_v, mask):
    u_var = first_var(ds_u, ["UGRD", "u"])
    v_var = first_var(ds_v, ["VGRD", "v"])
    u_mean = float(ds_u[u_var].values[mask].mean()) * 2.23694
    v_mean = float(ds_v[v_var].values[mask].mean()) * 2.23694
    spd = math.sqrt(u_mean**2 + v_mean**2)
    dirn = (270 - math.degrees(math.atan2(v_mean, u_mean))) % 360
    return dirn, spd


def point_wind(ds_u, ds_v, lat, lon_neg):
    lats = ds_u.latitude.values
    lons = ds_u.longitude.values
    dist2d = (lats - lat)**2 + (lons - (lon_neg + 360))**2
    iy, ix = np.unravel_index(dist2d.argmin(), dist2d.shape)
    u_var = first_var(ds_u, ["UGRD", "u"])
    v_var = first_var(ds_v, ["VGRD", "v"])
    u = float(ds_u[u_var].values[iy, ix]) * 2.23694
    v = float(ds_v[v_var].values[iy, ix]) * 2.23694
    spd = math.sqrt(u**2 + v**2)
    dirn = (270 - math.degrees(math.atan2(v, u))) % 360
    return dirn, spd


if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CAMP FIRE OVERNIGHT TIMING AUDIT")
    print("  HRRR 00z Nov 8 2018 -- 700 hPa domain mean, fxx=6-20")
    print()
    print("  PRE-REGISTERED: peak expected at fxx<=14 (confirms declining-limb)")
    print("  Ignition ~14:33z = fxx=14 from 00z run")
    print("=" * 72)
    print()

    # Build domain mask once from first fxx
    print("  Building domain mask...", end=" ", flush=True)
    try:
        H0 = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=FXX_LIST[0])
        ds0_u = H0.xarray("UGRD:700 mb")
        mask = get_mask(ds0_u)
        print(f"done ({mask.sum()} cells)")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print()
    print(f"  {'fxx':>4}  {'valid UTC':>9}  {'PST':>6} | "
          f"{'Domain mean':^16} | {'Jarbo Gap':^14} | {'Fire origin':^14} | Flag")
    print(f"  {'':4}  {'':9}  {'':6} | "
          f"{'dir   spd':^16} | {'dir   spd':^14} | {'dir   spd':^14} |")
    print("  " + "-" * 88)

    speeds = {}

    for fxx in FXX_LIST:
        utc_h  = fxx % 24
        utc_dd = "Nov8" if fxx <= 23 else "Nov9"
        pst_h  = (fxx - 8) % 24
        pst_s  = f"{pst_h:02d}:00"
        flag   = " <-- IGNITION" if fxx == IGNITION_FXX else ""
        flag   = flag or (" <-- +1h" if fxx == IGNITION_FXX + 1 else "")

        try:
            H = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx)
            ds_u = H.xarray("UGRD:700 mb")
            ds_v = H.xarray("VGRD:700 mb")

            dm_dir, dm_spd = domain_mean_wind(ds_u, ds_v, mask)
            speeds[fxx] = dm_spd

            row = (f"  fxx{fxx:02d}  {utc_h:02d}z {utc_dd}  {pst_s}PST | "
                   f"{dm_dir:4.0f}  {dm_spd:5.1f} mph   |")

            for sid, (lat, lon) in STATIONS.items():
                pd, ps = point_wind(ds_u, ds_v, lat, lon)
                row += f" {pd:3.0f}  {ps:4.1f}mph  |"

            print(row + flag)

        except Exception as e:
            print(f"  fxx{fxx:02d}  {utc_h:02d}z {utc_dd}  ERROR: {e}")

    # Evaluate against pre-registered prediction
    print()
    if speeds:
        peak_fxx = max(speeds, key=speeds.get)
        peak_spd = speeds[peak_fxx]
        ignition_spd = speeds.get(IGNITION_FXX)
        pre_peak_fxx = [f for f in sorted(speeds) if f <= IGNITION_FXX]
        post_peak_fxx = [f for f in sorted(speeds) if f > IGNITION_FXX]

        print("TIMING AUDIT RESULT")
        print("=" * 60)
        print(f"  Peak 700 hPa: {peak_spd:.1f} mph at fxx={peak_fxx} "
              f"({(peak_fxx)%24:02d}z = {(peak_fxx-8)%24:02d}:00 PST)")
        if ignition_spd:
            print(f"  At ignition (fxx={IGNITION_FXX}): {ignition_spd:.1f} mph")
            diff = ignition_spd - peak_spd
            print(f"  Delta (ignition - peak): {diff:+.1f} mph")
        print()
        if peak_fxx < IGNITION_FXX:
            lag = IGNITION_FXX - peak_fxx
            print(f"  RESULT: Peak BEFORE ignition by {lag} fxx-hours.")
            print(f"  => CONFIRMS declining-limb pattern.")
            print(f"     Ignition at {ignition_spd:.1f} mph, declining from peak {peak_spd:.1f} mph.")
        elif peak_fxx == IGNITION_FXX:
            print(f"  RESULT: Peak AT ignition (fxx={IGNITION_FXX}).")
            print(f"  => CONFIRMS declining-limb (at the crest).")
        else:
            print(f"  RESULT: Peak AFTER ignition by {peak_fxx - IGNITION_FXX} fxx-hours.")
            print(f"  => BREAKS declining-limb pattern for Camp Fire.")
            print(f"     Ignition was on the RISING limb -- fire started before peak.")
        print()
        print("  Update timing_observations.md with this result.")
