#!/usr/bin/env python3
"""
build_dem_features.py — Phase A DEM step (tiled fetch, integrity-verified)
Run in conda env `dem` (has py3dep, rasterio, rioxarray, pyproj).
Launcher: run_dem.ps1

Computes four terrain columns for the 164 active stations in hrrr_error_dataset.csv:
  slope           — degrees, downslope gradient at native ~10 m DEM, EPSG:5070
  aspect          — degrees, downslope azimuth met convention (0=N, CW)
  relief_1km      — max − min elevation within 1 km radius disk
  repr_error_flag — elevation std within 3 km radius disk (HRRR ~3km grid cell proxy)

Fetch architecture (tiled, integrity-checked):
  Instead of one WCS request per event, the event bbox is split into TILE_DEG × TILE_DEG
  sub-tiles. Each tile is fetched individually, verified for completeness (actual shape ≥
  SHAPE_TOL × expected shape), and retried with exponential backoff (RETRY_DELAYS) before
  falling back to the 3DEP COG path. Tiles are only written to cache after passing the
  integrity check. Verified tiles are mosaicked into a single event-level GeoTIFF.

  Sub-tile cache: _dem_cache/{event}_t{row}_{col}.tif
  Event mosaic:   _dem_cache/{event}.tif  (same key as before — existing cache honored)

  Why this matters: a short read (fewer bytes than expected) silently poisons
  relief_1km and repr_error_flag for any station in the truncated region. The shape
  check refuses to accept a tile that isn't whole.

Convention record (do not change silently):
  DEM source:         USGS 3DEP 1/3 arc-second (~10 m), fetched via py3dep / COG fallback
  Projection:         EPSG:5070 (CONUS Albers equal-area) for all metric computations
  slope:              degrees from horizontal (arctan of gradient magnitude at 10 m)
  aspect:             downslope-facing azimuth, 0=N, 90=E, 180=S, 270=W (met convention)
  relief_1km:         max − min within 1000 m radius disk
  repr_error_flag:    elevation std within 3000 m radius disk (HRRR ~3km grid cell)
  QC threshold:       DEM elevation vs elev_m_derived flagged if |residual| > 50 m

Output: dem_features.csv (keyed stid + event_id) — do NOT edit hrrr_error_dataset.csv
Report: elevation residuals, tile success counts, column distributions by terrain_class
"""

import csv
import math
import os
import sys
import time
import warnings
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

# ── Fetch tuning ─────────────────────────────────────────────────────────────
TILE_DEG      = 0.25    # sub-tile edge in degrees (lat and lon)
MAX_RETRIES   = 3
RETRY_DELAYS  = [5, 15, 45]   # seconds between attempts
SHAPE_TOL     = 0.85    # accept tile if actual ≥ 85% of expected in each dimension
STATION_BUF   = 0.04    # skip tiles with no station within this many degrees (~4 km)
TILE_DELAY    = 3       # polite seconds between tile fetches


# ── Station loader ───────────────────────────────────────────────────────────

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
                    elev_reg = float(row["elev_m"]) if row.get("elev_m", "").replace(".", "").lstrip("-").isdigit() else None
                except Exception:
                    elev_reg = None
                stations.append({
                    "stid":          row["stid"],
                    "event_id":      row["event_id"],
                    "station_name":  row.get("station_name", row["stid"]),
                    "lat":           lat,
                    "lon":           lon,
                    "elev_m_reg":    elev_reg,
                    "terrain_class": row.get("terrain_class", "open"),
                })
    return stations


# ── Terrain metric helpers ────────────────────────────────────────────────────

def compute_slope_aspect(dem_arr, res_m):
    """
    slope (deg) and aspect (deg, met convention 0=N CW) from a 2D float array.
    Uses Zevenbergen & Thorne central-difference gradients.
    """
    dz_dy, dz_dx = np.gradient(dem_arr, res_m, res_m)
    dz_dy_north = -dz_dy  # np.gradient rows increase downward; flip for north-positive
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy_north ** 2))
    slope_deg = np.degrees(slope_rad)
    aspect_deg = (270.0 - np.degrees(np.arctan2(-dz_dy_north, -dz_dx))) % 360.0
    aspect_deg = np.where(slope_deg < 0.5, np.nan, aspect_deg)
    return slope_deg, aspect_deg


def disk_mask(radius_px):
    r = int(math.ceil(radius_px))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x ** 2 + y ** 2) <= radius_px ** 2


def neighborhood_stats(arr, row, col, radius_px):
    mask = disk_mask(radius_px)
    r = int(math.ceil(radius_px))
    r0 = max(0, row - r);      r1 = min(arr.shape[0], row + r + 1)
    c0 = max(0, col - r);      c1 = min(arr.shape[1], col + r + 1)
    mr0 = r - (row - r0);      mr1 = mr0 + (r1 - r0)
    mc0 = r - (col - c0);      mc1 = mc0 + (c1 - c0)
    vals = arr[r0:r1, c0:c1][mask[mr0:mr1, mc0:mc1]]
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    return float(np.max(vals)), float(np.min(vals)), float(np.std(vals))


def process_station(ds, lat, lon, res_m):
    """
    Extract terrain metrics at (lat, lon) using a windowed read.
    Reads only the ~700×700 px window needed for the 3 km repr disk —
    avoids loading the full event mosaic (which can be 900M+ pixels).
    Returns dict or None if station is outside the raster or in a nodata region.
    """
    import pyproj
    from rasterio.windows import Window

    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x5070, y5070 = transformer.transform(lon, lat)

    try:
        row_ctr, col_ctr = ds.index(x5070, y5070)
    except Exception:
        return None

    nrows, ncols = ds.height, ds.width
    if row_ctr < 1 or row_ctr >= nrows - 1 or col_ctr < 1 or col_ctr >= ncols - 1:
        return None

    # Window radius: 3 km repr disk + 5 px margin for gradient edge effects
    pad = int(math.ceil(3000.0 / res_m)) + 5

    r0 = max(0, row_ctr - pad)
    r1 = min(nrows, row_ctr + pad + 1)
    c0 = max(0, col_ctr - pad)
    c1 = min(ncols, col_ctr + pad + 1)

    win = Window(col_off=c0, row_off=r0, width=c1 - c0, height=r1 - r0)
    arr = ds.read(1, window=win).astype(float)
    nodata = ds.nodata
    if nodata is not None:
        arr[arr == nodata] = np.nan

    # Station's position within the windowed array
    row_w = row_ctr - r0
    col_w = col_ctr - c0

    if row_w < 1 or row_w >= arr.shape[0] - 1 or col_w < 1 or col_w >= arr.shape[1] - 1:
        return None

    dem_elev = float(arr[row_w, col_w]) if np.isfinite(arr[row_w, col_w]) else np.nan

    slope_arr, aspect_arr = compute_slope_aspect(arr, res_m)
    slope  = float(slope_arr[row_w, col_w])  if np.isfinite(slope_arr[row_w, col_w])  else np.nan
    aspect = float(aspect_arr[row_w, col_w]) if np.isfinite(aspect_arr[row_w, col_w]) else np.nan

    r1km_px = 1000.0 / res_m
    vmax, vmin, _ = neighborhood_stats(arr, row_w, col_w, r1km_px)
    relief_1km = round(vmax - vmin, 1) if (np.isfinite(vmax) and np.isfinite(vmin)) else np.nan

    r3km_px = 3000.0 / res_m
    _, _, std_3km = neighborhood_stats(arr, row_w, col_w, r3km_px)
    repr_ef = round(std_3km, 2) if np.isfinite(std_3km) else np.nan

    return {
        "dem_elev_m":      round(dem_elev, 1) if np.isfinite(dem_elev) else None,
        "slope":           round(slope, 2)    if np.isfinite(slope)    else None,
        "aspect":          round(aspect, 1)   if np.isfinite(aspect)   else None,
        "relief_1km":      relief_1km         if np.isfinite(relief_1km) else None,
        "repr_error_flag": repr_ef            if np.isfinite(repr_ef)  else None,
    }


# ── Tiled fetch layer ─────────────────────────────────────────────────────────

def expected_shape(minlat, maxlat, minlon, maxlon, res_m=10):
    """
    Approximate pixel dimensions after reprojection to EPSG:5070.
    Used only for integrity checking — not for exact size prediction.
    """
    lat_c  = (minlat + maxlat) / 2
    rows   = (maxlat - minlat) * 111320 / res_m
    cols   = (maxlon - minlon) * 111320 * math.cos(math.radians(lat_c)) / res_m
    return max(1, int(rows)), max(1, int(cols))


def validate_dem_file(path):
    """
    Return True if the file exists, opens without error, and has at least 100×100 px.
    This is the guard against caching a truncated file from a previous failed run.
    """
    if not os.path.exists(path):
        return False
    try:
        import rasterio
        with rasterio.open(path) as ds:
            return ds.width >= 100 and ds.height >= 100
    except Exception:
        return False


def frange(start, stop, step):
    """Float range: yields values from start up to (but not including) stop."""
    x = start
    while x < stop - 1e-9:
        yield x
        x = round(x + step, 10)


def tile_has_station(tminlat, tmaxlat, tminlon, tmaxlon, stations):
    """Return True if any station falls within this tile (plus STATION_BUF margin)."""
    for s in stations:
        if (tminlat - STATION_BUF <= s["lat"] <= tmaxlat + STATION_BUF and
                tminlon - STATION_BUF <= s["lon"] <= tmaxlon + STATION_BUF):
            return True
    return False


def fetch_tile_py3dep(tminlon, tminlat, tmaxlon, tmaxlat, out_path, res=10):
    """
    Fetch one sub-tile via py3dep WCS, verify shape, write to out_path only if OK.
    Returns (success, actual_rows, actual_cols).
    A failed or short tile is NOT written to disk.
    """
    import py3dep
    import rioxarray  # noqa: F401

    exp_r, exp_c = expected_shape(tminlat, tmaxlat, tminlon, tmaxlon, res)

    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            print(f"      backoff {wait}s ...", end=" ", flush=True)
            time.sleep(wait)
        try:
            dem = py3dep.get_dem(
                (tminlon, tminlat, tmaxlon, tmaxlat), resolution=res, crs="EPSG:4326"
            )
            dem_proj = dem.rio.reproject("EPSG:5070")
            act_r, act_c = dem_proj.shape[-2], dem_proj.shape[-1]

            if act_r < SHAPE_TOL * exp_r or act_c < SHAPE_TOL * exp_c:
                print(
                    f"short ({act_r}×{act_c} vs exp {exp_r}×{exp_c})",
                    end=" ", flush=True
                )
                continue  # retry — do NOT write to cache

            dem_proj.rio.to_raster(out_path)
            return True, act_r, act_c

        except Exception as e:
            print(f"err: {e}", end=" ", flush=True)

    return False, 0, 0


def fetch_tile_cog(tminlon, tminlat, tmaxlon, tmaxlat, out_path):
    """
    Fallback: windowed read from USGS 3DEP 1/3 arc-second COGs on AWS S3.
    Uses /vsicurl to stream only the needed window — avoids downloading full 1° tiles.

    Tile naming: USGS_13_n{N:02d}w{W:03d}.tif where N = floor(lat)+1, W = abs(floor(lon))
    e.g. lat=42.5, lon=-122.3 → tile n43w123.tif (NW corner 43°N, 123°W)
    """
    import rasterio
    from rasterio.merge import merge as rio_merge
    import rioxarray as rxr

    # GDAL config for remote COG access
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff,.ovr")

    BASE_URL = (
        "https://prd-tnm.s3.amazonaws.com"
        "/StagedProducts/Elevation/13/TIFF/current"
    )

    # Determine which 1° tiles span this sub-tile bbox
    lat_tiles = range(int(math.floor(tminlat)), int(math.ceil(tmaxlat)))
    lon_tiles = range(int(math.floor(tminlon)), int(math.ceil(tmaxlon)))

    sources = []
    for tlat in lat_tiles:
        for tlon in lon_tiles:
            N = tlat + 1
            W = abs(tlon)
            tile_name = f"USGS_13_n{N:02d}w{W:03d}.tif"
            url = f"/vsicurl/{BASE_URL}/{tile_name}"
            try:
                ds = rasterio.open(url)
                sources.append(ds)
                print(f"COG:{tile_name} ", end="", flush=True)
            except Exception as e:
                print(f"COG:{tile_name} FAIL({e}) ", end="", flush=True)

    if not sources:
        return False

    tmp_path = out_path + ".cog_tmp.tif"
    try:
        merged, transform = rio_merge(
            sources, bounds=(tminlon, tminlat, tmaxlon, tmaxlat)
        )
        for ds in sources:
            ds.close()

        profile = {
            "driver": "GTiff", "dtype": merged.dtype,
            "width": merged.shape[-1], "height": merged.shape[-2],
            "count": 1, "crs": "EPSG:4326", "transform": transform,
        }
        with rasterio.open(tmp_path, "w", **profile) as dst:
            dst.write(merged)

        dem = rxr.open_rasterio(tmp_path)
        dem_proj = dem.rio.reproject("EPSG:5070")

        # Integrity check on COG result too
        exp_r, exp_c = expected_shape(tminlat, tmaxlat, tminlon, tmaxlon)
        act_r, act_c = dem_proj.shape[-2], dem_proj.shape[-1]
        if act_r < SHAPE_TOL * exp_r or act_c < SHAPE_TOL * exp_c:
            print(f"COG short ({act_r}×{act_c} vs {exp_r}×{exp_c})", end=" ", flush=True)
            return False

        dem_proj.rio.to_raster(out_path)
        return True

    except Exception as e:
        print(f"COG merge/reproject err: {e}", end=" ", flush=True)
        return False
    finally:
        for ds in sources:
            try:
                ds.close()
            except Exception:
                pass
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def fetch_dem_tiled(minlon, minlat, maxlon, maxlat, event_tag, ev_stations, res=10):
    """
    Fetch the DEM for an event bbox using TILE_DEG × TILE_DEG sub-tiles.

    Strategy:
      1. If event mosaic cache exists and validates → return it (no re-fetch).
      2. Otherwise: tile bbox, skip tiles with no nearby station, fetch each tile
         with py3dep, verify shape, retry with backoff, fall back to COG on failure.
         A tile is only written to cache after passing the integrity check.
      3. Mosaic all verified tiles into the event cache file.

    Returns (rasterio.DatasetReader, partial_flag) where partial_flag=True means
    some tiles failed (stations in those regions will report NODATA, not wrong values).
    """
    import rasterio
    from rasterio.merge import merge as rio_merge

    mosaic_path = os.path.join(DEM_CACHE, f"{event_tag}.tif")

    # Honor existing event-level cache (backward-compatible with prior single-tile fetches)
    if validate_dem_file(mosaic_path):
        print(f"  cache hit: {event_tag}", flush=True)
        return rasterio.open(mosaic_path), False

    # Build sub-tile grid
    lat_edges = list(frange(minlat, maxlat, TILE_DEG)) + [maxlat]
    lon_edges = list(frange(minlon, maxlon, TILE_DEG)) + [maxlon]

    all_tiles = [
        (ri, ci,
         lat_edges[ri], lat_edges[ri + 1],
         lon_edges[ci], lon_edges[ci + 1])
        for ri in range(len(lat_edges) - 1)
        for ci in range(len(lon_edges) - 1)
    ]
    # Keep only tiles that contain at least one station (+ buffer)
    needed_tiles = [t for t in all_tiles if tile_has_station(t[2], t[3], t[4], t[5], ev_stations)]
    skipped = len(all_tiles) - len(needed_tiles)

    n_tiles = len(needed_tiles)
    print(
        f"  Tiling: {len(all_tiles)} sub-tiles → {n_tiles} needed "
        f"({skipped} skipped, no station nearby)", flush=True
    )
    if n_tiles == 0:
        print(f"  FAIL: no tiles needed for {event_tag} (station list empty?)", flush=True)
        return None, True

    tile_paths   = []
    failed_tiles = []
    tile_stats   = []

    for ri, ci, tminlat, tmaxlat, tminlon, tmaxlon in needed_tiles:
        tile_key  = f"{event_tag}_t{ri}_{ci}"
        tile_path = os.path.join(DEM_CACHE, f"{tile_key}.tif")

        if validate_dem_file(tile_path):
            print(f"    ({ri},{ci}) cache hit", flush=True)
            tile_paths.append(tile_path)
            tile_stats.append((ri, ci, "cache"))
            continue

        exp_r, exp_c = expected_shape(tminlat, tmaxlat, tminlon, tmaxlon, res)
        print(
            f"    ({ri},{ci}) {tminlat:.2f}-{tmaxlat:.2f}N {tminlon:.2f}-{tmaxlon:.2f}W "
            f"~{exp_r}×{exp_c}px ... ",
            end="", flush=True
        )
        time.sleep(TILE_DELAY)

        ok, act_r, act_c = fetch_tile_py3dep(tminlon, tminlat, tmaxlon, tmaxlat, tile_path, res)

        if not ok:
            print(f"py3dep failed → COG ... ", end="", flush=True)
            ok = fetch_tile_cog(tminlon, tminlat, tmaxlon, tmaxlat, tile_path)

        if ok and validate_dem_file(tile_path):
            print(f"OK", flush=True)
            tile_paths.append(tile_path)
            tile_stats.append((ri, ci, "ok"))
        else:
            print(f"FAIL", flush=True)
            failed_tiles.append((ri, ci, tminlat, tmaxlat, tminlon, tmaxlon))
            tile_stats.append((ri, ci, "fail"))
            # Remove any partial/corrupt file so it is not cached
            if os.path.exists(tile_path):
                try:
                    os.remove(tile_path)
                except Exception:
                    pass

    if failed_tiles:
        print(
            f"  WARNING: {len(failed_tiles)}/{n_tiles} tiles failed: "
            f"{[(r,c) for r,c,*_ in failed_tiles]}"
        )

    if not tile_paths:
        print(f"  FAIL: all tiles failed for {event_tag}", flush=True)
        return None, True

    # Mosaic verified tiles
    partial = len(failed_tiles) > 0
    print(
        f"  Mosaicking {len(tile_paths)}/{n_tiles} tiles ... ",
        end="", flush=True
    )
    try:
        src_files = [rasterio.open(p) for p in tile_paths]
        mosaic, transform = rio_merge(src_files)
        meta = src_files[0].meta.copy()
        meta.update({
            "height":    mosaic.shape[-2],
            "width":     mosaic.shape[-1],
            "transform": transform,
            "compress":  "lzw",
        })
        for src in src_files:
            src.close()

        with rasterio.open(mosaic_path, "w", **meta) as dst:
            dst.write(mosaic)

        print(f"OK ({mosaic.shape[-2]}×{mosaic.shape[-1]} px)", flush=True)
        return rasterio.open(mosaic_path), partial

    except Exception as e:
        print(f"mosaic FAIL: {e}", flush=True)
        for src in src_files:
            try:
                src.close()
            except Exception:
                pass
        return None, True


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("DEM Features — build_dem_features.py (tiled, integrity-verified)")
    print("CRS: EPSG:5070 | Source: USGS 3DEP 10 m | Tile size: {:.2f}°".format(TILE_DEG))
    print("Conventions: slope deg @ 10m | aspect 0=N CW | relief_1km 1000m radius")
    print("             repr_error_flag = elev std within 3000m radius (HRRR cell)")
    print("=" * 70)
    print()

    stations = load_active_stations(DATASET)
    print(f"Loaded {len(stations)} active station-events.")

    by_event = defaultdict(list)
    for s in stations:
        by_event[s["event_id"]].append(s)

    PAD = 0.15  # bounding-box padding around the event's station cluster
    results = []
    event_tile_summary = {}

    for event, ev_stations in sorted(by_event.items()):
        lats = [s["lat"] for s in ev_stations]
        lons = [s["lon"] for s in ev_stations]
        minlat = min(lats) - PAD;  maxlat = max(lats) + PAD
        minlon = min(lons) - PAD;  maxlon = max(lons) + PAD

        print(
            f"\n[{event}] {len(ev_stations)} stations  "
            f"bbox=({minlat:.2f},{minlon:.2f})-({maxlat:.2f},{maxlon:.2f})"
        )

        ds, partial = fetch_dem_tiled(
            minlon, minlat, maxlon, maxlat, event, ev_stations
        )

        event_tile_summary[event] = {
            "n_stations": len(ev_stations),
            "ok":         ds is not None,
            "partial":    partial,
        }

        if ds is None:
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

        res_m = abs(ds.transform.a)
        print(f"  DEM loaded: {ds.width}×{ds.height} px @ {res_m:.1f} m/px", flush=True)

        for i, s in enumerate(ev_stations):
            print(f"  station {i+1}/{len(ev_stations)} {s['stid']} ...", end=" ", flush=True)
            metrics = process_station(ds, s["lat"], s["lon"], res_m)
            print("ok" if metrics else "NODATA", flush=True)

            if metrics is None:
                row_out = {
                    "stid": s["stid"], "event_id": s["event_id"],
                    "dem_elev_m": None, "elev_m_reg": s["elev_m_reg"],
                    "elev_residual_m": None, "elev_qc": "NODATA_OR_EDGE",
                    "slope": None, "aspect": None,
                    "relief_1km": None, "repr_error_flag": None,
                    "terrain_class": s["terrain_class"],
                }
            else:
                dem_e  = metrics["dem_elev_m"]
                reg_e  = s["elev_m_reg"]
                if dem_e is not None and reg_e is not None:
                    resid  = round(dem_e - reg_e, 1)
                    elev_qc = "FLAG_LARGE_RESIDUAL" if abs(resid) > 50 else "OK"
                else:
                    resid   = None
                    elev_qc = "MISSING_REG_ELEV" if dem_e is not None else "NODATA"
                row_out = {
                    "stid":            s["stid"],
                    "event_id":        s["event_id"],
                    "dem_elev_m":      dem_e,
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
    cols = [
        "stid", "event_id", "dem_elev_m", "elev_m_reg", "elev_residual_m", "elev_qc",
        "slope", "aspect", "relief_1km", "repr_error_flag", "terrain_class",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)
    print(f"\nWrote {len(results)} rows → {OUT_CSV}")

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DEM FEATURE REPORT")
    print("=" * 70)

    print("\nTile fetch summary per event:")
    print(f"  {'event':<25} {'n_sta':>5}  {'status'}")
    for ev, s in sorted(event_tile_summary.items()):
        status = "FAIL" if not s["ok"] else ("PARTIAL" if s["partial"] else "OK")
        print(f"  {ev:<25} {s['n_stations']:>5}  {status}")

    ok_rows   = [r for r in results if r["elev_qc"] in ("OK", "MISSING_REG_ELEV")]
    flag_rows = [r for r in results if r["elev_qc"] == "FLAG_LARGE_RESIDUAL"]
    fail_rows = [r for r in results if r["elev_qc"] in ("NODATA_OR_EDGE", "DEM_FETCH_FAIL")]

    print(f"\nElevation QC (DEM vs registry elev_m, flag threshold = 50 m):")
    print(f"  OK:                 {len(ok_rows)}")
    print(f"  FLAG >50m residual: {len(flag_rows)}")
    print(f"  Nodata / FAIL:      {len(fail_rows)}")

    resids = [r["elev_residual_m"] for r in results if r.get("elev_residual_m") is not None]
    if resids:
        print(
            f"\n  Residual stats (DEM − registry, m): "
            f"min={min(resids):.1f}  median={sorted(resids)[len(resids)//2]:.1f}  max={max(resids):.1f}"
        )
    if flag_rows:
        print(f"\n  Flagged (|residual| > 50 m):")
        for r in flag_rows:
            print(
                f"    {r['event_id']}/{r['stid']}: "
                f"dem={r['dem_elev_m']}m  reg={r['elev_m_reg']}m  Δ={r['elev_residual_m']}m"
            )

    print(f"\nColumn distributions by terrain_class:")
    for col_name, unit in [
        ("slope", "°"), ("aspect", "°"), ("relief_1km", "m"), ("repr_error_flag", "m std")
    ]:
        print(f"\n  {col_name} ({unit}):")
        by_class = defaultdict(list)
        for r in results:
            v = r.get(col_name)
            tc = r.get("terrain_class", "open")
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
                print(
                    f"    {tc:<20} n={len(vals):4d}  "
                    f"mean={np.mean(vals):7.1f}  std={np.std(vals):6.1f}  "
                    f"min={min(vals):7.1f}  max={max(vals):7.1f}"
                )

    n_complete = sum(1 for r in results if r.get("slope") is not None)
    n_fail     = sum(1 for r in results if r.get("slope") is None)
    print(f"\nStations with complete DEM metrics: {n_complete} / {len(results)}")
    if n_fail > 0:
        print(f"Stations still lacking DEM data:    {n_fail}")
        still_fail = [r for r in results if r.get("slope") is None]
        for r in still_fail[:10]:
            print(f"  {r['event_id']}/{r['stid']}  elev_qc={r['elev_qc']}")
        if len(still_fail) > 10:
            print(f"  ... and {len(still_fail)-10} more")
        print("\n  Re-run this script to retry failed tiles (cached tiles are skipped).")
        print("  If py3dep tiles keep failing, the COG fallback will activate automatically.")
    else:
        print("\nAll stations complete. Run merge_dem_and_gate.py for full gate check.")

    print("\nEND OF DEM FEATURE REPORT")


if __name__ == "__main__":
    main()
