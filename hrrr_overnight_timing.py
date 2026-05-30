#!/usr/bin/env python3
"""
hrrr_overnight_timing.py
========================
run via: conda run -n hrrr311 python hrrr_overnight_timing.py

Overnight 700 hPa timing pulls for Tubbs (Case 9) and Thomas (Case 8).
Each case includes:
  - Fire-site point extraction
  - Control point (non-channeled, similar domain position)
  - Domain mean

Purpose: test whether fire-site 700 hPa leads domain mean due to
(a) translating-feature geometry or (b) terrain signal.
If fire-site and control lead domain mean equally -> geometry.
If fire-site leads control -> possible terrain signal (but still not
canyon flow, which isn't in the 700 hPa field; see timing_observations.md).

PRE-REGISTERED BEFORE PULLING (2026-05-30):
  Expected shape for both cases (if declining-limb holds under full overnight):
    Winds rise overnight, peak before ignition, declining at ignition.
  Confirms: peak fxx <= ignition fxx
  Breaks:   peak fxx >  ignition fxx  (same result as Camp Fire)

  Control point prediction: if translating-feature geometry, fire-site
  and control should lead domain mean by similar amounts. If terrain signal,
  fire-site should lead control by more than control leads domain mean.
"""
import warnings
warnings.filterwarnings("ignore")

import sys, math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

# ---------------------------------------------------------------------------
# EVENT CONFIGURATIONS
# ---------------------------------------------------------------------------

EVENTS = {
    "tubbs_2017": {
        "name":         "Tubbs Fire",
        "init_time":    "2017-10-08 00:00",  # 00z Oct 8 -- overnight before ignition
        "fxx_list":     [6, 8, 10, 12, 14, 16, 18, 20, 22],
        "ignition_fxx": 28,  # ~04:45z Oct 9 = fxx=28 from 00z Oct 8
        # Note: ignition Oct 9 04:45z = 28h 45m from 00z Oct 8 -> fxx=28-29
        "ignition_utc": "04:45z Oct 9",
        "lat_min": 38.0, "lat_max": 39.0,
        "lon_min": -123.2, "lon_max": -122.0,
        "fire_site":    (38.570, -122.580, "Tubbs ignition (Calistoga)"),
        "control":      (38.200, -121.800, "Control: Lodi/foothills (valley, not channeled)"),
    },
    "thomas_2017": {
        "name":         "Thomas Fire",
        "init_time":    "2017-12-03 00:00",  # 00z Dec 3 -- day before ignition
        "fxx_list":     [6, 9, 12, 15, 18, 21, 24, 27, 30, 33],
        "ignition_fxx": 33,  # ~09:45z Dec 4 = 33h 45m from 00z Dec 3
        # Note: ignition Dec 4 09:45z = fxx=33-34 from 00z Dec 3
        "ignition_utc": "09:45z Dec 4",
        "lat_min": 34.0, "lat_max": 35.0,
        "lon_min": -120.2, "lon_max": -118.0,
        "fire_site":    (34.441, -118.984, "Thomas ignition (Ventura/Santa Paula)"),
        "control":      (34.200, -118.200, "Control: San Gabriel Valley (flat, not channeled)"),
    },
}


def get_mask(ds, lat_min, lat_max, lon_min, lon_max):
    lats = ds.latitude.values
    lons = ds.longitude.values
    return (
        (lats >= lat_min) & (lats <= lat_max) &
        (lons >= (lon_min + 360)) & (lons <= (lon_max + 360))
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


def run_event(cfg):
    name         = cfg["name"]
    init_time    = cfg["init_time"]
    fxx_list     = cfg["fxx_list"]
    ign_fxx      = cfg["ignition_fxx"]
    fire_lat, fire_lon, fire_label = cfg["fire_site"]
    ctrl_lat, ctrl_lon, ctrl_label = cfg["control"]

    print()
    print("=" * 76)
    print(f"  {name}  --  {init_time} run")
    print(f"  Ignition: {cfg['ignition_utc']} = fxx={ign_fxx}")
    print(f"  Fire site: {fire_label}")
    print(f"  Control:   {ctrl_label}")
    print("=" * 76)

    # Build mask from first fxx
    print(f"  Building mask from fxx={fxx_list[0]:02d}...", end=" ", flush=True)
    try:
        H0 = Herbie(init_time, model="hrrr", product="prs", fxx=fxx_list[0])
        ds0_u = H0.xarray("UGRD:700 mb")
        mask = get_mask(ds0_u, cfg["lat_min"], cfg["lat_max"],
                        cfg["lon_min"], cfg["lon_max"])
        print(f"done ({mask.sum()} cells)")
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print()
    print(f"  {'fxx':>4}  {'valid':>7} | {'Domain mean':^12} | "
          f"{'Fire site':^12} | {'Control':^12} | "
          f"{'Site-Mean':>9} | {'Ctrl-Mean':>9}")
    print("  " + "-" * 78)

    mean_speeds = {}
    site_speeds = {}
    ctrl_speeds = {}

    for fxx in fxx_list:
        flag = " <-- IGNITION" if fxx == ign_fxx else (
               " <-- +1" if fxx == ign_fxx + 1 else "")
        try:
            H = Herbie(init_time, model="hrrr", product="prs", fxx=fxx)
            ds_u = H.xarray("UGRD:700 mb")
            ds_v = H.xarray("VGRD:700 mb")

            d_mean, s_mean = domain_mean_wind(ds_u, ds_v, mask)
            d_site, s_site = point_wind(ds_u, ds_v, fire_lat, fire_lon)
            d_ctrl, s_ctrl = point_wind(ds_u, ds_v, ctrl_lat, ctrl_lon)

            mean_speeds[fxx] = s_mean
            site_speeds[fxx] = s_site
            ctrl_speeds[fxx] = s_ctrl

            # Lead of site over mean; lead of ctrl over mean
            site_lead = s_site - s_mean
            ctrl_lead = s_ctrl - s_mean

            print(f"  fxx{fxx:02d}  {(fxx%24):02d}z      | "
                  f"{d_mean:3.0f}/{s_mean:5.1f}mph  | "
                  f"{d_site:3.0f}/{s_site:5.1f}mph  | "
                  f"{d_ctrl:3.0f}/{s_ctrl:5.1f}mph  | "
                  f"{site_lead:+6.1f}mph  | "
                  f"{ctrl_lead:+6.1f}mph {flag}")

        except Exception as e:
            print(f"  fxx{fxx:02d}  ERROR: {e}")

    # Verdict
    if mean_speeds:
        peak_mean_fxx = max(mean_speeds, key=mean_speeds.get)
        peak_site_fxx = max(site_speeds, key=site_speeds.get) if site_speeds else None
        peak_ctrl_fxx = max(ctrl_speeds, key=ctrl_speeds.get) if ctrl_speeds else None

        print()
        print("  TIMING VERDICT:")
        print(f"    Domain mean peak: fxx={peak_mean_fxx} "
              f"({peak_mean_fxx%24:02d}z, {mean_speeds[peak_mean_fxx]:.1f} mph)")
        if peak_site_fxx:
            print(f"    Fire site peak:   fxx={peak_site_fxx} "
                  f"({peak_site_fxx%24:02d}z, {site_speeds[peak_site_fxx]:.1f} mph)")
        if peak_ctrl_fxx:
            print(f"    Control peak:     fxx={peak_ctrl_fxx} "
                  f"({peak_ctrl_fxx%24:02d}z, {ctrl_speeds[peak_ctrl_fxx]:.1f} mph)")

        if peak_mean_fxx < ign_fxx:
            print(f"    Domain mean: CONFIRMS (peak {ign_fxx - peak_mean_fxx} fxx before ignition)")
        elif peak_mean_fxx == ign_fxx:
            print(f"    Domain mean: CONFIRMS (peak AT ignition)")
        else:
            print(f"    Domain mean: BREAKS (peak {peak_mean_fxx - ign_fxx} fxx AFTER ignition)")

        if peak_site_fxx and peak_ctrl_fxx:
            site_lead_over_mean = peak_mean_fxx - peak_site_fxx
            ctrl_lead_over_mean = peak_mean_fxx - peak_ctrl_fxx
            print()
            print(f"    Site leads mean by: {site_lead_over_mean} fxx-hours")
            print(f"    Ctrl leads mean by: {ctrl_lead_over_mean} fxx-hours")
            if abs(site_lead_over_mean - ctrl_lead_over_mean) <= 1:
                print(f"    => SIMILAR leads: likely translating-feature geometry, not terrain")
            else:
                diff = site_lead_over_mean - ctrl_lead_over_mean
                print(f"    => DIFFERENT leads (site leads ctrl by {diff} fxx-hours)")
                print(f"       Possible terrain signal -- but can't confirm at 700 hPa level")
                print(f"       (canyon flow not resolved in 700 hPa field)")


if __name__ == "__main__":
    print()
    print("OVERNIGHT 700 HPA TIMING AUDIT: Tubbs + Thomas")
    print("With control points to test translating-feature vs terrain geometry")
    print()
    print("PRE-REGISTERED: declining-limb CONFIRMS if domain mean peak <= ignition fxx")
    print("CONTROL TEST: similar site/ctrl leads -> geometry; different -> possible terrain")
    print()

    for event_key in ["tubbs_2017", "thomas_2017"]:
        run_event(EVENTS[event_key])

    print()
    print("Update timing_observations.md with results.")
