#!/usr/bin/env python3
"""
conus404_pull.py
================
Pull CONUS404 4km WRF wind fields for the four fire events.

CONUS404: 4km WRF v3.9.1.1 dynamically downscaled from ERA5, hourly, 1979-2021.
Access: cloud Zarr via HyTEST intake catalog (S3/OSN, no login).
Why this over ERA5: ERA5 is 28km (won't resolve terrain). CONUS404 is terrain-resolving.

Per conus404_pull_spec.md:
  Priority: timing re-test on Camp Fire (no HRRR truncation artifacts).
  Pre-registered expectation: Camp Fire winds peak before/at ignition (Mass 2021).
  Apply domain-mean-vs-point + propagation-geometry checks (same as HRRR analysis).

GOTCHAS (from spec):
  - Curvilinear grid: use 2D lat/lon nearest-cell search, not .sel(lat=...)
  - U10/V10 in m/s: convert to mph
  - 700 hPa NOT a native coord: skip for first pass, use 10m winds
  - DST: Camp/Kincade span the Nov/Oct DST boundary -- verify UTC offset

Run: python conus404_pull.py
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import json

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# PRE-REGISTERED EXPECTATION
# ---------------------------------------------------------------------------
PRE_REG = """
PRE-REGISTERED (before data loaded):
  Camp Fire: 10m wind at Jarbo Gap peaks near/before ignition (~14:33z Nov 8 2018).
  Mass 2021 describes sunrise (~14z) peak in surface downslope winds.
  CONFIRMS timing: peak fxx <= ignition time at fire site.
  BREAKS timing:   peak clearly after ignition (same result as HRRR domain-mean).
  Apply: same domain-mean-vs-point and propagation-geometry checks that killed
  the Tubbs HRRR antisymmetry and quarantined the Oakland sounding timing.
"""

MS_TO_MPH = 2.23694

# Fire sites (NIFC-verified coords carry full weight; approx flagged)
SITES = {
    "camp":    {
        "jarbo_gap":   (39.735944, -121.488944, "JBGC1 Jarbo Gap  NIFC-verified"),
        "fire_origin": (39.896,    -121.432,    "Camp Creek Rd   approx"),
        "control_pt":  (39.700,    -121.200,    "Control: Sierra foothills non-channeled"),
    },
    "tubbs":   {
        "fire_origin": (38.570, -122.580, "Tubbs / Calistoga   approx"),
        "control_pt":  (38.200, -121.800, "Control: Lodi valley floor"),
    },
    "thomas":  {
        "fire_origin": (34.441, -118.984, "Thomas / Ventura    approx"),
        "topa_topa":   (34.520, -119.080, "Topa Topa ~6230ft   UNVERIFIED coords"),
        "control_pt":  (34.200, -118.200, "Control: San Gabriel Valley"),
    },
    "kincade": {
        "fire_origin": (38.680, -122.750, "Kincade / Geysers   approx"),
        "control_pt":  (38.200, -121.800, "Control: valley floor"),
    },
}

# Ignition times (UTC)
IGNITIONS = {
    "camp":    ("2018-11-08T14:33", "14:33z Nov 8 2018  (06:33 PST, PST=UTC-8)"),
    "tubbs":   ("2017-10-09T04:45", "04:45z Oct 9 2017  (21:45 PDT, PDT=UTC-7)"),
    "thomas":  ("2017-12-04T09:45", "09:45z Dec 4 2017  (01:45 PST, PST=UTC-8)"),
    "kincade": ("2019-10-24T04:27", "04:27z Oct 24 2019 (21:27 PDT, PDT=UTC-7)"),
}

# Event windows (UTC)
EVENTS = {
    "camp":    ("2018-11-07T00:00", "2018-11-09T23:00"),
    "tubbs":   ("2017-10-08T00:00", "2017-10-10T23:00"),
    "thomas":  ("2017-12-04T00:00", "2017-12-06T23:00"),
    "kincade": ("2019-10-23T00:00", "2019-10-25T23:00"),
}

DOMAIN = {"lat_min": 35.0, "lat_max": 42.0,
           "lon_min": -124.0, "lon_max": -117.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def speed_dir_mph(u, v):
    """Convert WRF U/V (m/s) to speed (mph) and FROM direction (deg)."""
    spd = float(np.sqrt(u**2 + v**2)) * MS_TO_MPH
    drc = float((270.0 - np.degrees(np.arctan2(float(v), float(u)))) % 360.0)
    return spd, drc


def nearest_cell(lat2d, lon2d, lat0, lon0):
    """Find nearest grid cell to a point on a curvilinear grid."""
    d2 = (lat2d - lat0)**2 + (lon2d - lon0)**2
    j, i = np.unravel_index(np.argmin(d2), d2.shape)
    return int(j), int(i)


# ---------------------------------------------------------------------------
# Main pull
# ---------------------------------------------------------------------------

def run_pull():
    print(PRE_REG)
    print("=" * 70)
    print("  CONUS404 PULL -- 4km WRF terrain-resolving winds")
    print("=" * 70)

    # Step 1: Open catalog
    print("\nStep 1: Opening HyTEST intake catalog ...")
    try:
        import intake
        CAT_URL = ("https://raw.githubusercontent.com/hytest-org/hytest/"
                   "main/dataset_catalog/hytest_intake_catalog.yml")
        cat = intake.open_catalog(CAT_URL)
        print(f"  Catalog entries: {list(cat)[:8]}...")
    except Exception as e:
        print(f"  ERROR opening catalog: {e}")
        return None

    # Step 2: Find and open CONUS404 dataset
    print("\nStep 2: Opening CONUS404 dataset ...")
    try:
        # Try common catalog paths
        ds = None
        for cat_key in list(cat):
            if "conus404" in cat_key.lower() or "404" in cat_key:
                print(f"  Found CONUS404 entry: {cat_key}")
                sub_cat = cat[cat_key]
                print(f"  Sub-catalog entries: {list(sub_cat)[:8]}")
                # look for hourly cloud source
                for src_key in list(sub_cat):
                    if "hourly" in src_key.lower():
                        print(f"  Trying source: {src_key}")
                        try:
                            ds = sub_cat[src_key].to_dask()
                            print(f"  Dataset opened: {dict(ds.dims)}")
                            print(f"  Wind vars: {[v for v in ds.data_vars if 'U' in v.upper() or 'V' in v.upper() or 'W' in v.upper()][:10]}")
                            break
                        except Exception as e2:
                            print(f"  Source {src_key} failed: {e2}")
                if ds is not None:
                    break
        if ds is None:
            print("  No CONUS404 hourly dataset found in catalog.")
            print("  Available top-level keys:")
            for k in list(cat):
                print(f"    {k}")
            return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    # Confirm variable and coordinate names
    lat_var = "lat" if "lat" in ds.coords else ("XLAT" if "XLAT" in ds.coords else None)
    lon_var = "lon" if "lon" in ds.coords else ("XLONG" if "XLONG" in ds.coords else None)
    u_var   = "U10" if "U10" in ds.data_vars else None
    v_var   = "V10" if "V10" in ds.data_vars else None

    print(f"\n  Coord names: lat={lat_var}, lon={lon_var}")
    print(f"  Wind vars:   U={u_var}, V={v_var}")
    if not all([lat_var, lon_var, u_var, v_var]):
        print("  ESCALATE: expected variables not found. Inspect ds manually.")
        print(f"  Coords: {list(ds.coords)[:20]}")
        print(f"  Data vars: {list(ds.data_vars)[:20]}")
        return ds

    # Step 3: California subset
    print("\nStep 3: California bounding-box subset ...")
    lat2d = ds[lat_var].values
    lon2d = ds[lon_var].values
    inside = ((lat2d >= DOMAIN["lat_min"]) & (lat2d <= DOMAIN["lat_max"]) &
              (lon2d >= DOMAIN["lon_min"]) & (lon2d <= DOMAIN["lon_max"]))
    jj, ii = np.where(inside)
    if len(jj) == 0:
        print("  ERROR: No cells inside CA bounding box.")
        return None
    j0, j1 = int(jj.min()), int(jj.max()) + 1
    i0, i1 = int(ii.min()), int(ii.max()) + 1
    ds_ca = ds.isel(y=slice(j0, j1), x=slice(i0, i1))
    print(f"  CA subset: {dict(ds_ca.dims)}")

    # Step 4: Per-event pulls
    results = {}
    for event, (t0, t1) in EVENTS.items():
        ign_str, ign_label = IGNITIONS[event]
        print(f"\nEvent: {event}  (ignition {ign_label})")
        try:
            sub = ds_ca[[u_var, v_var]].sel(time=slice(t0, t1)).load()
            print(f"  Loaded: {dict(sub.dims)}, {len(sub.time)} hours")

            lat2d_ca = ds_ca[lat_var].values
            lon2d_ca = ds_ca[lon_var].values

            # Domain mean
            u_mean = float(sub[u_var].mean(dim=("y", "x")).sel(
                time=ign_str, method="nearest"))
            v_mean = float(sub[v_var].mean(dim=("y", "x")).sel(
                time=ign_str, method="nearest"))
            dm_spd, dm_dir = speed_dir_mph(u_mean, v_mean)
            print(f"  Domain mean at ignition: {dm_spd:.1f} mph @ {dm_dir:.0f} deg")

            # Domain mean time series -- find peak
            u_ts = sub[u_var].mean(dim=("y", "x"))
            v_ts = sub[v_var].mean(dim=("y", "x"))
            spd_ts = np.sqrt(u_ts**2 + v_ts**2) * MS_TO_MPH
            peak_t = spd_ts.idxmax().values
            peak_v = float(spd_ts.max())
            print(f"  Domain mean peak: {peak_v:.1f} mph at {peak_t}")

            # Per-site extraction
            site_results = {}
            for site_id, (lat0, lon0, desc) in SITES.get(event, {}).items():
                j, i = nearest_cell(lat2d_ca, lon2d_ca, lat0, lon0)
                u_pt = sub[u_var].isel(y=j, x=i)
                v_pt = sub[v_var].isel(y=j, x=i)
                spd_pt = np.sqrt(u_pt**2 + v_pt**2) * MS_TO_MPH
                peak_pt = float(spd_pt.max())
                peak_t_pt = spd_pt.idxmax().values
                # value at ignition
                spd_ign = float(spd_pt.sel(time=ign_str, method="nearest"))
                u_ign = float(u_pt.sel(time=ign_str, method="nearest"))
                v_ign = float(v_pt.sel(time=ign_str, method="nearest"))
                _, dir_ign = speed_dir_mph(u_ign, v_ign)
                site_results[site_id] = {
                    "peak_mph": peak_pt, "peak_time": str(peak_t_pt),
                    "at_ignition_mph": spd_ign, "at_ignition_dir": dir_ign,
                }
                print(f"  {site_id}: peak {peak_pt:.1f}mph @ {peak_t_pt}  |  at ignition {spd_ign:.1f}mph @ {dir_ign:.0f}deg")

            results[event] = {
                "domain_mean_at_ignition": {"spd": dm_spd, "dir": dm_dir},
                "domain_mean_peak": {"mph": peak_v, "time": str(peak_t)},
                "sites": site_results,
                "ignition_utc": ign_str,
            }

        except Exception as e:
            print(f"  ERROR for {event}: {e}")
            import traceback; traceback.print_exc()

    # ---------------------------------------------------------------------------
    # Timing verdict
    # ---------------------------------------------------------------------------
    if results:
        print()
        print("=" * 70)
        print("  TIMING VERDICT (domain mean 10m wind, pre-registered)")
        print("=" * 70)
        for event, r in results.items():
            ign = r.get("ignition_utc", "")
            peak = r.get("domain_mean_peak", {})
            dm_ign = r.get("domain_mean_at_ignition", {})
            print(f"\n  {event}  (ignition {ign})")
            print(f"    Domain mean at ignition: {dm_ign.get('spd', 'N/A'):.1f} mph @ {dm_ign.get('dir', 'N/A'):.0f}deg")
            print(f"    Domain mean peak:        {peak.get('mph', 'N/A'):.1f} mph at {peak.get('time', 'N/A')}")
            # simple verdict based on whether peak is before or after ignition
            try:
                import pandas as pd
                ign_pd = pd.Timestamp(ign)
                peak_pd = pd.Timestamp(peak["time"])
                diff_h = (peak_pd - ign_pd).total_seconds() / 3600
                if diff_h < -1:
                    verdict = f"CONFIRMS declining limb (peak {abs(diff_h):.1f}h BEFORE ignition)"
                elif diff_h > 1:
                    verdict = f"BREAKS -- peak {diff_h:.1f}h AFTER ignition (rising limb)"
                else:
                    verdict = f"AT peak (~{diff_h:.1f}h from ignition)"
                print(f"    Verdict: {verdict}")
                print(f"    Apply domain-mean-vs-point + geometry checks before trusting.")
            except Exception:
                pass

        # Save
        with open("conus404_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("\n  Results saved to conus404_results.json")

    return results


if __name__ == "__main__":
    run_pull()
