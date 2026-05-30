#!/usr/bin/env python3
"""
hrrr_700hpa_case8.py
====================
run via: conda run -n hrrr311 python hrrr_700hpa_case8.py

Case 8 -- Thomas Fire, December 4 2017
HRRR 700 hPa + 800 hPa wind pull with terrain-height guard.

This is the STANDARD TEMPLATE for Case 8+ high-terrain domains.
The guard flags 700 hPa cells where the pressure surface sits within
200m of local terrain (HRRR HGT:surface). Those cells are extrapolated
below-ground and must be excluded from the domain mean.

BC reference:
  Primary:     700 hPa wind (valid where HGT:700mb > terrain + 200m)
  Ridgetop proxy: 800 hPa (~2000m) sampled over the Topa Topa crest
                  (upwind barrier the NE flow crosses, ~1900m)
  NOT: San Gorgonio (3506m, 34.1N 116.8W) -- east of domain, off-axis

Domain: Ventura fire area + upwind Topa Topa/Santa Ynez terrain
  Lat  34.0 – 35.0 N
  Lon  120.2 – 118.0 W   (eastern bound stops well short of San Gorgonio)

Ignition: ~09:45z Dec 4 2017. Run: 00z, fxx=6-15 (valid 06z-15z).
"""
import warnings
warnings.filterwarnings("ignore")

import sys, math
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from herbie import Herbie

# Domain
LAT_MIN, LAT_MAX = 34.0, 35.0
LON_MIN, LON_MAX = -120.2, -118.0   # negative geographic

# HRRR run
INIT_TIME = "2017-12-04 00:00"
FXX_LIST  = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

# Terrain-height guard: exclude cells where 700 hPa surface is within this
# many meters of local terrain. HRRR extrapolates below-ground values there.
HGT_GUARD_MARGIN_M = 200.0

# Key stations (point extractions alongside domain mean)
STATIONS = {
    "fire_origin":   (34.441, -118.984, "Fire origin    ~1000ft"),
    "topa_topa":     (34.520, -119.080, "Topa Topa crest ~6230ft"),
    "wheeler_spr":   (34.522, -119.318, "Wheeler Springs ~2050ft"),
    "oxnard_asos":   (34.200, -119.207, "KOXR Oxnard     sea level"),
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_mask(ds):
    """Boolean mask for grid points inside the domain bounding box."""
    lats = ds.latitude.values
    lons = ds.longitude.values   # HRRR native 0-360
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


def domain_mean_wind(ds_u, ds_v, mask, label=""):
    """Vector-average U,V over masked domain cells. Returns (dir_deg, spd_mph)."""
    u_var = first_var(ds_u, ["UGRD", "u10", "u"])
    v_var = first_var(ds_v, ["VGRD", "v10", "v"])
    u_vals = ds_u[u_var].values
    v_vals = ds_v[v_var].values
    u_mean = float(u_vals[mask].mean()) * 2.23694
    v_mean = float(v_vals[mask].mean()) * 2.23694
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


# ---------------------------------------------------------------------------
# STEP 1 — TERRAIN-HEIGHT GUARD  (run once on first fxx)
# ---------------------------------------------------------------------------

def build_terrain_guard(fxx_ref=6):
    """
    Pull HRRR terrain elevation (HGT:surface, sfc product) and
    700 hPa geopotential height (HGT:700 mb, prs product) over the domain.
    Return a mask of VALID cells (700 hPa surface safely above terrain).
    """
    print(f"  Building terrain guard from fxx={fxx_ref:02d}...", end=" ", flush=True)
    try:
        H_sfc = Herbie(INIT_TIME, model="hrrr", product="sfc", fxx=fxx_ref)
        ds_terrain = H_sfc.xarray("HGT:surface")
        H_prs = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx_ref)
        ds_hgt700 = H_prs.xarray("HGT:700 mb")
    except Exception as e:
        print(f"ERROR: {e}")
        return None, None, None

    domain_mask = get_mask(ds_terrain)

    t_var = first_var(ds_terrain, ["HGT", "orog", "gh", "z"])
    h_var = first_var(ds_hgt700,  ["gh", "HGT", "z"])

    terrain_m = ds_terrain[t_var].values        # HRRR terrain elevation, meters
    hgt700_m  = ds_hgt700[h_var].values         # 700 hPa geopotential height, meters

    # Flag cells where 700 hPa surface is too close to (or below) terrain
    below_guard = (hgt700_m < terrain_m + HGT_GUARD_MARGIN_M)
    flagged_in_domain = domain_mask & below_guard
    valid_mask = domain_mask & ~below_guard

    n_domain   = int(domain_mask.sum())
    n_flagged  = int(flagged_in_domain.sum())
    frac_flag  = n_flagged / n_domain if n_domain > 0 else 0.0

    # Heights over valid domain cells
    valid_terrain = terrain_m[valid_mask]
    valid_hgt700  = hgt700_m[valid_mask]

    print("done.")
    print()
    print("  TERRAIN-HEIGHT GUARD RESULTS:")
    print(f"    Domain cells total       : {n_domain}")
    print(f"    Cells flagged (near-/below-ground 700 hPa): {n_flagged} ({frac_flag:.1%})")
    print(f"    Valid cells used for mean: {n_domain - n_flagged}")
    if valid_terrain.size > 0:
        print(f"    Valid domain terrain     : {valid_terrain.min():.0f} – {valid_terrain.max():.0f} m")
        print(f"    700 hPa height range     : {valid_hgt700.min():.0f} – {valid_hgt700.max():.0f} m")
        print(f"    Min margin (700hPa-terrain): {(valid_hgt700 - valid_terrain).min():.0f} m")
    if n_flagged > 0:
        flag_terrain = terrain_m[flagged_in_domain]
        print(f"    Flagged cell terrain     : {flag_terrain.min():.0f} – {flag_terrain.max():.0f} m")
        print(f"    --> These cells excluded from all domain-mean BC values.")
    else:
        print(f"    No cells flagged -- 700 hPa safely above all terrain in this domain.")

    return valid_mask, domain_mask, frac_flag


# ---------------------------------------------------------------------------
# STEP 2 — WIND PULL  (700 hPa + 800 hPa ridgetop proxy)
# ---------------------------------------------------------------------------

def run_pull(valid_mask):
    print()
    print("HRRR 700 hPa + 800 hPa Wind -- Thomas Fire  2017-12-04")
    print("(domain mean uses terrain-guard valid cells only)")
    print(f"Domain: {LAT_MIN}-{LAT_MAX}N, {abs(LON_MAX)}-{abs(LON_MIN)}W")
    print(f"        (eastern bound {abs(LON_MIN)}W excludes San Gorgonio at 116.8W)")
    print("=" * 96)
    print(f"  {'fxx':>4} {'valid':>5} | {'700hPa MEAN':^18} | {'800hPa MEAN':^18}"
          f" | {'Fire orig':^12} | {'Topa Topa':^12} |")
    print(f"  {'':4} {'':5} | {'dir   spd':^18} | {'dir   spd':^18}"
          f" | {'dir   spd':^12} | {'dir   spd':^12} |")
    print("  " + "-" * 100)

    fxx9_700 = None   # capture at ignition time for BC audit

    for fxx in FXX_LIST:
        valid_h = fxx % 24
        flag = " <-- ignition ~09:45z" if fxx == 9 else (
               " <-- +3h" if fxx == 12 else "")
        try:
            H = Herbie(INIT_TIME, model="hrrr", product="prs", fxx=fxx)
            ds_u700 = H.xarray("UGRD:700 mb")
            ds_v700 = H.xarray("VGRD:700 mb")
            ds_u800 = H.xarray("UGRD:800 mb")
            ds_v800 = H.xarray("VGRD:800 mb")

            d700, s700 = domain_mean_wind(ds_u700, ds_v700, valid_mask)
            d800, s800 = domain_mean_wind(ds_u800, ds_v800, valid_mask)

            # Point extractions at fire origin and Topa Topa crest
            d_fo, s_fo = point_wind(ds_u700, ds_v700,
                                    STATIONS["fire_origin"][0],
                                    STATIONS["fire_origin"][1])
            d_tt, s_tt = point_wind(ds_u700, ds_v700,
                                    STATIONS["topa_topa"][0],
                                    STATIONS["topa_topa"][1])

            row = (f"  fxx{fxx:02d} {valid_h:02d}z   "
                   f"| {d700:5.0f}  {s700:6.1f} mph   "
                   f"| {d800:5.0f}  {s800:6.1f} mph   "
                   f"| {d_fo:4.0f} {s_fo:5.1f}m   "
                   f"| {d_tt:4.0f} {s_tt:5.1f}m   |")
            print(row + flag)

            if fxx == 9:
                fxx9_700 = (d700, s700, d800, s800)

        except Exception as e:
            print(f"  fxx{fxx:02d} {valid_h:02d}z   ERROR: {e}")

    print()
    print("  700 hPa: free-atmosphere BC reference (guard-filtered domain mean)")
    print("  800 hPa: ridgetop-level proxy for Topa Topa crest (~1900m / ~2000m)")
    print()
    return fxx9_700


# ---------------------------------------------------------------------------
# STEP 3 — BC AUDIT  (compare to Camp Fire + document residual)
# ---------------------------------------------------------------------------

def bc_audit(fxx9_700):
    if fxx9_700 is None:
        print("  BC audit skipped -- no fxx=9 data.")
        return

    d700, s700, d800, s800 = fxx9_700
    print("BC AUDIT — Case 8 Thomas Fire  (SYNOPTIC_TERRAIN)")
    print("=" * 70)
    print(f"  HRRR 700 hPa domain mean at ignition (fxx=9, ~09:45z):")
    print(f"    {s700:.1f} mph @ {d700:.0f} deg")
    print()
    print(f"  HRRR 800 hPa ridgetop proxy (Topa Topa level):")
    print(f"    {s800:.1f} mph @ {d800:.0f} deg")
    print()
    print("  Hand-tuned BC (not yet established for this case -- TBD from WN sweep).")
    print("  Camp Fire reference: HRRR 700 was 25.2 mph @ 50 NE;")
    print("    hand-tuned BC was 35 mph @ 45 NE; delta = +9.8 mph.")
    print()
    print("  COPY INTO bc_label_generator.py for this event:")
    print(f"    HRRR_PRIOR_SPEED = {s700:.1f}   # 700 hPa domain mean fxx=9")
    print(f"    HRRR_PRIOR_DIR   = {d700:.1f}   # degrees")
    print()
    print("  NOTE: 800 hPa ridgetop proxy gives:")
    print(f"    {s800:.1f} mph @ {d800:.0f} deg")
    print("  Compare to 700 hPa: if ridgetop speed > 700hPa speed, the flow")
    print("  is accelerating at crest level -- important for WN BC selection.")
    print()
    print("  NEXT STEP: run WindNinja with this BC and sweep around it.")
    print("  See windninja_case8.py (to be built).")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  CASE 8 — THOMAS FIRE  December 4 2017")
    print("  HRRR 700/800 hPa pull with terrain-height guard")
    print("=" * 70)
    print()

    valid_mask, domain_mask, frac_flag = build_terrain_guard(fxx_ref=6)

    if valid_mask is None:
        print("ERROR: Could not build terrain guard. Exiting.")
        sys.exit(1)

    fxx9_700 = run_pull(valid_mask)
    bc_audit(fxx9_700)
