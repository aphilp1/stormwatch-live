#!/usr/bin/env python3
"""
hrrr_700hpa_case9.py
====================
run via: conda run -n hrrr311 python hrrr_700hpa_case9.py

Case 9 -- Tubbs Fire, October 8-9 2017
HRRR 700 hPa wind with terrain guard. Standard Case 8+ template.

Ignition: ~04:45z Oct 9 2017 (21:45 PDT Oct 8), Tubbs Lane / Calistoga
HRRR run: 2017-10-09 00z, fxx=2-10 (valid 02z-10z covers ignition + first spread)

Domain: Mayacamas range + Sonoma/Napa fire area
  Lat  38.0 – 39.0 N
  Lon  123.2 – 122.0 W

Terrain guard: Mayacamas peak ~1324m (Mt. St. Helena). 700 hPa in warm
October airmass: ~3100m. Margin ~1776m -- expect 0 flagged cells.

Validation stations (Mass & Ovens 2019 BAMS):
  Hawkeye RAWS    ~38.80N  ~122.90W  (NW of Santa Rosa, ~45km from fire)
  Santa Rosa RAWS ~38.44N  ~122.71W  (city RAWS, near fire)
  IDs: TBD -- look up from MesoWest/Synoptic once research token active

BC comparison to Camp Fire:
  Camp Fire: HRRR 700 was 25.2 mph @ 50 NE; optimal BC ~28 mph; bias ~+3 mph
  Tubbs Fire: TBD from this run
"""
import warnings
warnings.filterwarnings("ignore")

import sys, math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

LAT_MIN, LAT_MAX = 38.0, 39.0
LON_MIN, LON_MAX = -123.2, -122.0

INIT_TIME = "2017-10-09 00:00"
FXX_LIST  = [2, 3, 4, 5, 6, 7, 8, 9, 10]

HGT_GUARD_MARGIN_M = 200.0

STATIONS = {
    "ignition":    (38.570, -122.580, "Tubbs Lane / Calistoga ignition"),
    "hawkeye":     (38.800, -122.900, "Hawkeye RAWS (approx) -- ID TBD"),
    "santa_rosa":  (38.440, -122.710, "Santa Rosa RAWS (approx) -- ID TBD"),
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
    raise KeyError(f"None of {candidates} found in {list(ds.data_vars)}")


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


def build_terrain_guard(fxx_ref=2):
    print(f"  Terrain guard (fxx={fxx_ref:02d})...", end=" ", flush=True)
    try:
        H_sfc = Herbie(INIT_TIME, model="hrrr", product="sfc", fxx=fxx_ref)
        ds_terrain = H_sfc.xarray("HGT:surface")
        H_prs = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx_ref)
        ds_hgt700 = H_prs.xarray("HGT:700 mb")
    except Exception as e:
        print(f"ERROR: {e}")
        return None, None

    domain_mask = get_mask(ds_terrain)
    t_var = first_var(ds_terrain, ["HGT", "orog", "gh", "z"])
    h_var = first_var(ds_hgt700,  ["gh", "HGT", "z"])

    terrain_m = ds_terrain[t_var].values
    hgt700_m  = ds_hgt700[h_var].values

    below_guard = hgt700_m < terrain_m + HGT_GUARD_MARGIN_M
    flagged     = domain_mask & below_guard
    valid_mask  = domain_mask & ~below_guard

    n_domain  = int(domain_mask.sum())
    n_flagged = int(flagged.sum())

    print("done.")
    print(f"  Domain cells: {n_domain} | Flagged: {n_flagged} ({n_flagged/n_domain:.1%})")
    if n_flagged == 0:
        print(f"  700 hPa safely above all terrain -- domain valid for BC reference")
    else:
        print(f"  WARNING: {n_flagged} cells near/below 700 hPa -- excluded from mean")
    if valid_mask.any():
        t_vals  = terrain_m[valid_mask]
        h_vals  = hgt700_m[valid_mask]
        print(f"  Valid terrain range:  {t_vals.min():.0f} – {t_vals.max():.0f} m")
        print(f"  700 hPa height range: {h_vals.min():.0f} – {h_vals.max():.0f} m")
        print(f"  Min margin:           {(h_vals - t_vals).min():.0f} m")
    return valid_mask, domain_mask


if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CASE 9 — TUBBS FIRE  October 8-9 2017")
    print("  HRRR 700 hPa pull with terrain guard")
    print(f"  Domain: {LAT_MIN}-{LAT_MAX}N, {abs(LON_MAX)}-{abs(LON_MIN)}W")
    print("=" * 72)
    print()

    valid_mask, domain_mask = build_terrain_guard(fxx_ref=2)
    if valid_mask is None:
        print("ERROR: terrain guard failed.")
        sys.exit(1)

    print()
    print("HRRR 700 hPa Wind -- Tubbs Fire  2017-10-09  (00z run)")
    print("=" * 96)
    print(f"  {'fxx':>4} {'valid':>5} | {'DOMAIN MEAN':^18} | {'Ignition':^14} "
          f"| {'Hawkeye':^14} | {'Santa Rosa':^14}")
    print(f"  {'':4} {'':5} | {'dir   spd':^18} | {'dir   spd':^14} "
          f"| {'dir   spd':^14} | {'dir   spd':^14}")
    print("  " + "-" * 100)

    fxx4_result = None

    for fxx in FXX_LIST:
        valid_h = fxx % 24
        flag = " <-- ignition ~04:45z" if fxx == 4 else (
               " <-- +6h" if fxx == 10 else "")
        try:
            H = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx)
            ds_u = H.xarray("UGRD:700 mb")
            ds_v = H.xarray("VGRD:700 mb")

            d700, s700 = domain_mean_wind(ds_u, ds_v, valid_mask)
            row = f"  fxx{fxx:02d} {valid_h:02d}z   | {d700:5.0f}  {s700:6.1f} mph   |"

            for sid, (lat, lon, _) in STATIONS.items():
                pd, ps = point_wind(ds_u, ds_v, lat, lon)
                row += f" {pd:4.0f}  {ps:5.1f} mph  |"

            print(row + flag)

            if fxx == 4:
                fxx4_result = (d700, s700)

        except Exception as e:
            print(f"  fxx{fxx:02d} {valid_h:02d}z   ERROR: {e}")

    print()
    if fxx4_result:
        d4, s4 = fxx4_result
        print("BC AUDIT — Case 9 Tubbs Fire  (SYNOPTIC_TERRAIN)")
        print("=" * 60)
        print(f"  HRRR 700 hPa domain mean at ignition (fxx=4, ~04:45z):")
        print(f"    {s4:.1f} mph @ {d4:.0f} deg")
        print()
        print("  Camp Fire reference:")
        print("    HRRR 700 was 25.2 mph @ 50 NE; optimal BC ~28 mph; bias ~+3 mph")
        print()
        print("  COPY INTO bc_label_generator.py (Tubbs event):")
        print(f"    HRRR_PRIOR_SPEED = {s4:.1f}")
        print(f"    HRRR_PRIOR_DIR   = {d4:.1f}")
        print()
        print("  Validation targets (Mass & Ovens 2019):")
        print("    Hawkeye sustained: TBD (gust 79 mph; sustained estimate ~49 mph)")
        print("    Santa Rosa sustained: TBD (gust 68 mph; sustained estimate ~42 mph)")
        print("    Gust factor for Tubbs: TBD -- apply same cross-check as Jarbo")
        print()
        print("  Next: python windninja_case9.py")
