#!/usr/bin/env python3
"""
build_dem_features.py — Phase A DEM step
Run in conda env dem (has py3dep, rasterio, rioxarray, scipy, pyproj).
Launcher: run_dem.ps1

Computes four terrain columns for the 164 active stations in hrrr_error_dataset.csv:

  slope        — degrees, downslope gradient at native 10 m DEM, projected CRS
  aspect       — degrees, downslope azimuth met convention (0=N, CW), at native 10 m
  relief_1km   — max − min elevation within 1 km RADIUS circle at native 10 m
  repr_error_flag — elevation std within 3 km RADIUS circle (HRRR cell proxy)

Convention record (do not change silently):
  DEM source:   USGS 3DEP 1/3 arc-second (~10 m), fetched per-event via py3dep
  Projection:   EPSG:5070 (CONUS Albers equal-area) for all metric computations
  slope:        degrees from horizontal (arctan of gradient magnitude at 10 m)
  aspect:       downslope-facing azimuth, 0=N, 90=E, 180=S, 270=W (met convention)
  relief_1km:   max − min within 1000 m radius disk
  repr_error_flag: elevation std within 3000 m radius disk (HRRR ~3km grid cell)
  QC threshold: DEM elevation vs elev_m_derived flagged if |residual| > 50 m

Output: dem_features.csv (keyed stid + event_id) — do NOT edit hrrr_error_dataset.csv
Report: DEM vs registry elevation residuals, nodata hits, column distributions by terrain_class

Source of truth: primary_goal_dataset_creation_spec.md
"""

import csv, math, os, sys, warnings
from collections import defaultdict
import numpy as np

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE      = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
DATASET   = os.path.join(BASE, "hrrr_error_dataset.csv")
OUT_CSV   = os.path.join(BASE, "dem_features.csv")
DEM_CACHE = os.path.join(BASE, "_dem_cache")

os.makedirs(DEM_CACHE, exist_ok=True)

# ── Load active stations from dataset ────────────────────────────────────────
def load_active_stations(path):
    stations = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("qc_flag", "") in ("KEEP", "CAUTION"):
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                except (ValueError, TypeError):
                    continue
                try:
                    elev_reg = float(row["elev_m"]) if row.get("elev_m", "").replace(".","").lstrip("-").isdigit() else None
                except:
                    elev_reg = None
                stations.append({
                    "stid":       row["stid"],
                    "event_id":   row["event_id"],
                    "station_name": row.get("station_name", row["stid"]),
                    "lat":        lat,
                    "lon":        lon,
                    "elev_m_reg": elev_reg,
                    "terrain_class": row.get("terrain_class", "open"),
                })
    return stations

# ── Haversine to meters ───────────────────────────────────────────────────────
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))

# ── Degrees/meters per degree of lat/lon at a given latitude ─────────────────
def meters_per_deg_lat(lat):
    return 111320.0  # roughly constant

def meters_per_deg_lon(lat):
    return 111320.0 * math.cos(math.radians(lat))

# ── Compute slope and aspect from DEM array ───────────────────────────────────
def compute_slope_aspect(dem_arr, res_m):
    """
    Compute slope (deg) and aspect (deg, met convention 0=N CW) from a 2D DEM array.
    res_m: pixel resolution in meters (same in x and y, EPSG:5070).
    Uses central difference (Zevenbergen & Thorne).
    Returns arrays of same shape as dem_arr; edges are NaN.
    """
    dz_dy, dz_dx = np.gradient(dem_arr, res_m, res_m)
    # dz_dx: east derivative (positive = uphill to east)
    # dz_dy: north derivative (positive = uphill to north) — np.gradient row=y,col=x
    # Note: np.gradient(..., res_m, res_m) gives row-derivative first, col-derivative second
    # rows increase downward (south) in raster convention, so dz_dy from np.gradient
    # is NEGATIVE of the north derivative. Flip:
    dz_dy_north = -dz_dy  # now positive = uphill going north

    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy_north**2))
    slope_deg = np.degrees(slope_rad)

    # Aspect: downslope-facing direction
    # Gradient points uphill; downslope = opposite = (-dz_dx, -dz_dy_north)
    # Met convention: 0=N, clockwise → (270 − atan2(v,u)) % 360
    # where u = downslope east component = -dz_dx, v = downslope north = -dz_dy_north
    aspect_deg = (270.0 - np.degrees(np.arctan2(-dz_dy_north, -dz_dx))) % 360.0

    # Flat areas: aspect is undefined → set to NaN where slope < 0.5°
    aspect_deg = np.where(slope_deg < 0.5, np.nan, aspect_deg)

    return slope_deg, aspect_deg

# ── Disk mask for a radius in pixels ─────────────────────────────────────────
def disk_mask(radius_px):
    """Boolean 2D mask of a disk with given radius in pixels."""
    r = int(math.ceil(radius_px))
    y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x**2 + y**2) <= radius_px**2

# ── Extract neighborhood stats around a pixel ─────────────────────────────────
def neighborhood_stats(arr, row, col, radius_px):
    """Max, min, std of arr values within disk of radius_px centered at (row, col)."""
    mask = disk_mask(radius_px)
    r = int(math.ceil(radius_px))
    r0 = max(0, row - r)
    r1 = min(arr.shape[0], row + r + 1)
    c0 = max(0, col - r)
    c1 = min(arr.shape[1], col + r + 1)
    # Trim mask to match clipped region
    mr0 = r - (row - r0)
    mr1 = mr0 + (r1 - r0)
    mc0 = r - (col - c0)
    mc1 = mc0 + (c1 - c0)
    m_crop = mask[mr0:mr1, mc0:mc1]
    vals = arr[r0:r1, c0:c1][m_crop]
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    return float(np.max(vals)), float(np.min(vals)), float(np.std(vals))

# ── Fetch DEM for a bounding box via py3dep ───────────────────────────────────
def fetch_dem_for_bbox(minlon, minlat, maxlon, maxlat, event_tag, res=10):
    """
    Download USGS 3DEP DEM for the bounding box.
    Returns (dem_rioxarray_dataset, transform, crs) in EPSG:5070.
    Caches to disk by event_tag.
    """
    import py3dep
    import rioxarray  # noqa: F401  (registers .rio accessor on xarray)
    import pyproj

    import time
    import rasterio

    cache_path = os.path.join(DEM_CACHE, f"{event_tag}.tif")

    if os.path.exists(cache_path):
        print(f"  DEM cache hit: {event_tag}", flush=True)
        return rasterio.open(cache_path), True

    # Inter-fetch delay — avoid rate-limiting the 3DEP WCS service
    time.sleep(5)

    print(f"  Fetching 3DEP for {event_tag} ({minlat:.2f}-{maxlat:.2f}N, {minlon:.2f}-{maxlon:.2f}W) ...",
          end=" ", flush=True)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            dem = py3dep.get_dem((minlon, minlat, maxlon, maxlat), resolution=res, crs="EPSG:4326")
            dem_proj = dem.rio.reproject("EPSG:5070")
            dem_proj.rio.to_raster(cache_path)
            print(f"OK (attempt {attempt})", flush=True)
            return rasterio.open(cache_path), True
        except Exception as e:
            if attempt < max_retries:
                wait = 15 * attempt
                print(f"\n    attempt {attempt} failed ({e}); retrying in {wait}s ...",
                      end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"FAIL after {max_retries} attempts ({e})", flush=True)
                return None, False

# ── Process one station from an open rasterio dataset ─────────────────────────
def process_station(ds, lat, lon, res_m):
    """
    Given a rasterio Dataset in EPSG:5070, compute terrain metrics at (lat, lon).
    Returns dict with slope, aspect, relief_1km, repr_error_flag, dem_elev_m, nodata.
    """
    import rasterio
    from rasterio.transform import rowcol as rc
    import pyproj

    # Project station coords to EPSG:5070
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x5070, y5070 = transformer.transform(lon, lat)

    # Get row, col in raster
    try:
        row, col = ds.index(x5070, y5070)
    except Exception:
        return None

    arr = ds.read(1).astype(float)
    nodata = ds.nodata
    if nodata is not None:
        arr[arr == nodata] = np.nan

    nrows, ncols = arr.shape
    if row < 1 or row >= nrows-1 or col < 1 or col >= ncols-1:
        return None  # too close to edge for gradient

    # DEM elevation at station
    dem_elev = float(arr[row, col]) if np.isfinite(arr[row, col]) else np.nan

    # Slope and aspect from the full array
    slope_arr, aspect_arr = compute_slope_aspect(arr, res_m)
    slope = float(slope_arr[row, col]) if np.isfinite(slope_arr[row, col]) else np.nan
    aspect = float(aspect_arr[row, col]) if np.isfinite(aspect_arr[row, col]) else np.nan

    # relief_1km: max−min within 1000 m radius disk
    radius_1km_px = 1000.0 / res_m
    vmax, vmin, _ = neighborhood_stats(arr, row, col, radius_1km_px)
    relief_1km = round(vmax - vmin, 1) if np.isfinite(vmax) and np.isfinite(vmin) else np.nan

    # repr_error_flag: elev std within 3000 m radius disk (HRRR ~3km cell)
    radius_3km_px = 3000.0 / res_m
    _, _, std_3km = neighborhood_stats(arr, row, col, radius_3km_px)
    repr_error_flag = round(std_3km, 2) if np.isfinite(std_3km) else np.nan

    return {
        "dem_elev_m":      round(dem_elev, 1)        if np.isfinite(dem_elev) else None,
        "slope":           round(slope, 2)            if np.isfinite(slope)    else None,
        "aspect":          round(aspect, 1)           if np.isfinite(aspect)   else None,
        "relief_1km":      relief_1km                 if np.isfinite(relief_1km) else None,
        "repr_error_flag": repr_error_flag            if np.isfinite(repr_error_flag) else None,
    }

# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("DEM Features — build_dem_features.py")
    print("CRS: EPSG:5070 (CONUS Albers) | Source: USGS 3DEP 10 m")
    print("Conventions: slope deg @ 10m | aspect 0=N CW | relief_1km 1000m radius")
    print("             repr_error_flag = elev std within 3000m radius (HRRR cell)")
    print("=" * 70)
    print()

    stations = load_active_stations(DATASET)
    print(f"Loaded {len(stations)} active station-events.")

    # Group stations by event for per-event DEM fetch
    by_event = defaultdict(list)
    for s in stations:
        by_event[s["event_id"]].append(s)

    # Per-event: compute bounding box with 0.15° padding
    PAD = 0.15

    results = []
    nodata_count = 0
    failed_events = []

    for event, ev_stations in sorted(by_event.items()):
        lats = [s["lat"] for s in ev_stations]
        lons = [s["lon"] for s in ev_stations]
        minlat = min(lats) - PAD
        maxlat = max(lats) + PAD
        minlon = min(lons) - PAD
        maxlon = max(lons) + PAD

        print(f"\n[{event}] {len(ev_stations)} stations, bbox=({minlat:.2f},{minlon:.2f})-({maxlat:.2f},{maxlon:.2f})")

        ds, ok = fetch_dem_for_bbox(minlon, minlat, maxlon, maxlat, event)
        if not ok or ds is None:
            failed_events.append(event)
            for s in ev_stations:
                results.append({
                    "stid": s["stid"], "event_id": s["event_id"],
                    "dem_elev_m": None, "elev_m_reg": s["elev_m_reg"],
                    "elev_residual_m": None, "elev_qc": "DEM_FETCH_FAIL",
                    "slope": None, "aspect": None,
                    "relief_1km": None, "repr_error_flag": None,
                    "terrain_class": s["terrain_class"],
                })
            continue

        # Get native resolution from rasterio transform
        import math as _math
        res_m = abs(ds.transform.a)  # pixel width in EPSG:5070 meters
        print(f"  DEM loaded: {ds.width}x{ds.height} px @ {res_m:.1f} m/px", flush=True)

        for s in ev_stations:
            metrics = process_station(ds, s["lat"], s["lon"], res_m)

            if metrics is None:
                nodata_count += 1
                row_out = {
                    "stid": s["stid"], "event_id": s["event_id"],
                    "dem_elev_m": None, "elev_m_reg": s["elev_m_reg"],
                    "elev_residual_m": None, "elev_qc": "NODATA_OR_EDGE",
                    "slope": None, "aspect": None,
                    "relief_1km": None, "repr_error_flag": None,
                    "terrain_class": s["terrain_class"],
                }
            else:
                dem_e = metrics["dem_elev_m"]
                reg_e = s["elev_m_reg"]
                if dem_e is not None and reg_e is not None:
                    resid = round(dem_e - reg_e, 1)
                    elev_qc = "FLAG_LARGE_RESIDUAL" if abs(resid) > 50 else "OK"
                else:
                    resid = None
                    elev_qc = "MISSING_REG_ELEV" if dem_e is not None else "NODATA"

                row_out = {
                    "stid":            s["stid"],
                    "event_id":        s["event_id"],
                    "dem_elev_m":      metrics["dem_elev_m"],
                    "elev_m_reg":      reg_e,
                    "elev_residual_m": resid,
                    "elev_qc":         elev_qc,
                    "slope":           metrics["slope"],
                    "aspect":          metrics["aspect"],
                    "relief_1km":      metrics["relief_1km"],
                    "repr_error_flag": metrics["repr_error_flag"],
                    "terrain_class":   s["terrain_class"],
                }

            results.append(row_out)

        ds.close()

    # ── Write CSV ─────────────────────────────────────────────────────────────
    cols = ["stid","event_id","dem_elev_m","elev_m_reg","elev_residual_m","elev_qc",
            "slope","aspect","relief_1km","repr_error_flag","terrain_class"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)
    print(f"\nWrote {len(results)} rows -> {OUT_CSV}")

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DEM FEATURE REPORT")
    print("=" * 70)

    ok_rows = [r for r in results if r["elev_qc"] in ("OK", "MISSING_REG_ELEV")]
    flag_rows = [r for r in results if r["elev_qc"] == "FLAG_LARGE_RESIDUAL"]
    fail_rows = [r for r in results if r["elev_qc"] in ("NODATA_OR_EDGE","DEM_FETCH_FAIL")]

    print(f"\nElevation QC (DEM vs registry elev_m_derived, flag threshold = 50 m):")
    print(f"  OK:                 {len(ok_rows)}")
    print(f"  FLAG >50m residual: {len(flag_rows)}")
    print(f"  Nodata / edge:      {nodata_count}")
    print(f"  DEM fetch failed:   {len([r for r in results if r['elev_qc']=='DEM_FETCH_FAIL'])}")
    if failed_events:
        print(f"  Failed events:      {failed_events}")

    resids = [r["elev_residual_m"] for r in results if r.get("elev_residual_m") is not None]
    if resids:
        print(f"\n  Residual stats (DEM - registry, m):  "
              f"min={min(resids):.1f}  median={sorted(resids)[len(resids)//2]:.1f}  max={max(resids):.1f}")

    if flag_rows:
        print(f"\n  Flagged stations (|residual| > 50 m):")
        for r in flag_rows:
            print(f"    {r['event_id']}/{r['stid']}: dem={r['dem_elev_m']} reg={r['elev_m_reg']} Δ={r['elev_residual_m']}")

    # Column distributions by terrain_class
    print(f"\nColumn distributions by terrain_class:")
    for col_name, unit in [("slope","°"), ("aspect","°"), ("relief_1km","m"), ("repr_error_flag","m std")]:
        print(f"\n  {col_name} ({unit}):")
        by_class = defaultdict(list)
        for r in results:
            v = r.get(col_name)
            tc = r.get("terrain_class","open")
            if v is not None:
                try:
                    by_class[tc].append(float(v))
                except (TypeError, ValueError):
                    pass
        if not by_class:
            print("    (no data)")
            continue
        for tc in sorted(by_class.keys()):
            vals = by_class[tc]
            if vals:
                print(f"    {tc:<20} n={len(vals):4d}  "
                      f"mean={np.mean(vals):7.1f}  std={np.std(vals):6.1f}  "
                      f"min={min(vals):7.1f}  max={max(vals):7.1f}")

    print("\nNOTE: Next step is to join dem_features.csv to hrrr_error_dataset.csv on")
    print("(stid, event_id), re-run structured-vs-white check with DEM terrain class,")
    print("then run separability pre-condition (rule #0) before claiming any terrain signal.")
    print("\nDO NOT start Phase B analysis until both checks are reviewed.")
    print("\nEND OF DEM FEATURE REPORT")


if __name__ == "__main__":
    main()
