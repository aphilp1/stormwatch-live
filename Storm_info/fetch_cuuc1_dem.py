#!/usr/bin/env python3
"""
fetch_cuuc1_dem.py — Targeted DEM fetch for CUUC1/woolsey_2018
==============================================================
CUUC1 (Chuchupate Ranger Station, 34.80637°N -119.01363°W, 1609.3 m) has no
entry in hrrr_error_dataset_dem.csv. This script fetches it via the same
py3dep/3DEP pipeline as build_dem_features.py and appends one row to
hrrr_error_dataset_dem.csv so that merge_woolsey_dem.py can pick it up.

Run in conda env `dem` (has py3dep, rasterio, rioxarray, pyproj):
  conda run -n dem python fetch_cuuc1_dem.py

After this script succeeds, run merge_woolsey_dem.py to push the DEM data into
hrrr_error_dataset.csv for the CUUC1/woolsey_2018 row.
"""
import csv, math, os, sys, time, warnings
import numpy as np
warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import py3dep
    import rasterio
    import rasterio.transform
    import pyproj
    from rasterio.windows import Window
except ImportError as e:
    print(f'ERROR: Missing dependency — {e}')
    print('Run in conda env `dem`:  conda run -n dem python fetch_cuuc1_dem.py')
    sys.exit(1)

BASE     = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DEM_CSV  = os.path.join(BASE, 'hrrr_error_dataset_dem.csv')
CACHE    = os.path.join(BASE, '_dem_cache')
os.makedirs(CACHE, exist_ok=True)

STID     = 'CUUC1'
EVENT_ID = 'woolsey_2018'
LAT      = 34.80637
LON      = -119.01363
ELEV_REG = 1609.3     # registry elevation (m)

# Fetch box: 0.3° buffer around station
BUF      = 0.3
BBOX     = (LON - BUF, LAT - BUF, LON + BUF, LAT + BUF)  # (west, south, east, north)
TILE_TIF = os.path.join(CACHE, f'{EVENT_ID}_cuuc1_dem.tif')

MAX_RETRIES   = 3
RETRY_DELAYS  = [5, 15, 45]


# ── Terrain metric helpers (identical to build_dem_features.py) ───────────────

def compute_slope_aspect(dem_arr, res_m):
    dz_dy, dz_dx = np.gradient(dem_arr, res_m, res_m)
    dz_dy_north = -dz_dy
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy_north**2))
    slope_deg = np.degrees(slope_rad)
    aspect_deg = (270.0 - np.degrees(np.arctan2(-dz_dy_north, -dz_dx))) % 360.0
    aspect_deg = np.where(slope_deg < 0.5, np.nan, aspect_deg)
    return slope_deg, aspect_deg


def disk_mask(radius_px):
    r = int(math.ceil(radius_px))
    y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x**2 + y**2) <= radius_px**2


def neighborhood_stats(arr, row, col, radius_px):
    mask = disk_mask(radius_px)
    r = int(math.ceil(radius_px))
    r0 = max(0, row - r);  r1 = min(arr.shape[0], row + r + 1)
    c0 = max(0, col - r);  c1 = min(arr.shape[1], col + r + 1)
    mr0 = r - (row - r0); mr1 = mr0 + (r1 - r0)
    mc0 = r - (col - c0); mc1 = mc0 + (c1 - c0)
    vals = arr[r0:r1, c0:c1][mask[mr0:mr1, mc0:mc1]]
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    return float(np.max(vals)), float(np.min(vals)), float(np.std(vals))


def classify_terrain(slope_pct, relief_m):
    """
    Classify terrain using the same heuristic as build_dem_features.py Phase A.
    slope_pct: slope in percent (not degrees)
    """
    if relief_m > 300 and slope_pct > 25:
        return 'exposed_ridge'
    if relief_m > 150 and slope_pct > 15:
        return 'canyon_gap'
    if slope_pct > 20:
        return 'exposed_ridge'
    if relief_m > 200 and slope_pct < 10:
        return 'valley'
    return 'open'


# ── DEM fetch ─────────────────────────────────────────────────────────────────

def fetch_dem():
    """Fetch DEM tile covering CUUC1, save to TILE_TIF. Returns True on success."""
    if os.path.exists(TILE_TIF):
        with rasterio.open(TILE_TIF) as ds:
            if ds.width >= 100 and ds.height >= 100:
                print(f'  Using cached DEM: {TILE_TIF}  ({ds.width}×{ds.height} px)')
                return True
        print('  Cached DEM failed integrity check — re-fetching')
        os.remove(TILE_TIF)

    print(f'  Fetching 3DEP DEM for CUUC1 bbox {BBOX}...')
    for attempt in range(MAX_RETRIES):
        try:
            dem = py3dep.get_map('DEM', BBOX, resolution=10, geo_crs='EPSG:4326',
                                  crs='EPSG:5070')
            # dem is an xarray DataArray in EPSG:5070
            dem.rio.to_raster(TILE_TIF)
            with rasterio.open(TILE_TIF) as ds:
                if ds.width >= 100 and ds.height >= 100:
                    print(f'  Fetch OK: {ds.width}×{ds.height} px, crs={ds.crs.to_epsg()}')
                    return True
                print(f'  Attempt {attempt+1}: tile too small ({ds.width}×{ds.height})')
        except Exception as ex:
            print(f'  Attempt {attempt+1} failed: {ex}')
        if attempt < MAX_RETRIES - 1:
            d = RETRY_DELAYS[attempt]
            print(f'  Waiting {d}s before retry...')
            time.sleep(d)

    print('  All fetch attempts failed.')
    return False


# ── Terrain metric extraction ─────────────────────────────────────────────────

def extract_terrain():
    """Open cached DEM, extract terrain metrics at CUUC1 lat/lon."""
    transformer = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:5070', always_xy=True)
    x5070, y5070 = transformer.transform(LON, LAT)

    with rasterio.open(TILE_TIF) as ds:
        res_m = abs(ds.transform.a)  # pixel size in meters (EPSG:5070)
        print(f'  DEM res: {res_m:.1f} m  crs: {ds.crs.to_epsg()}')

        try:
            row_ctr, col_ctr = ds.index(x5070, y5070)
        except Exception as ex:
            print(f'  ERROR: station not in DEM extent — {ex}')
            return None

        nrows, ncols = ds.height, ds.width
        if not (1 <= row_ctr < nrows-1 and 1 <= col_ctr < ncols-1):
            print(f'  ERROR: station at edge of DEM  (row={row_ctr}, col={col_ctr})')
            return None

        # Read window: 3 km repr disk + 5 px margin
        pad = int(math.ceil(3000.0 / res_m)) + 5
        r0 = max(0, row_ctr - pad);  r1 = min(nrows, row_ctr + pad + 1)
        c0 = max(0, col_ctr - pad);  c1 = min(ncols, col_ctr + pad + 1)
        win = Window(col_off=c0, row_off=r0, width=c1-c0, height=r1-r0)
        arr = ds.read(1, window=win).astype(float)
        nodata = ds.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan

        row_w = row_ctr - r0
        col_w = col_ctr - c0

        if not (1 <= row_w < arr.shape[0]-1 and 1 <= col_w < arr.shape[1]-1):
            print('  ERROR: station at edge of window after clipping')
            return None

    dem_elev = float(arr[row_w, col_w]) if np.isfinite(arr[row_w, col_w]) else None

    slope_arr, aspect_arr = compute_slope_aspect(arr, res_m)
    slope_deg  = float(slope_arr[row_w, col_w])  if np.isfinite(slope_arr[row_w, col_w])  else None
    aspect_deg = float(aspect_arr[row_w, col_w]) if np.isfinite(aspect_arr[row_w, col_w]) else None

    r1km_px = 1000.0 / res_m
    vmax, vmin, _ = neighborhood_stats(arr, row_w, col_w, r1km_px)
    relief_1km = round(vmax - vmin, 1) if (np.isfinite(vmax) and np.isfinite(vmin)) else None

    r3km_px = 3000.0 / res_m
    _, _, std_3km = neighborhood_stats(arr, row_w, col_w, r3km_px)
    repr_ef = round(std_3km, 2) if np.isfinite(std_3km) else None

    slope_pct = math.tan(math.radians(slope_deg)) * 100 if slope_deg is not None else None

    if slope_pct is not None and relief_1km is not None:
        tc = classify_terrain(slope_pct, relief_1km)
    else:
        tc = 'unknown'

    return {
        'dem_elev_m':      round(dem_elev, 1) if dem_elev is not None else None,
        'slope_deg':       round(slope_deg, 2) if slope_deg is not None else None,
        'slope_pct':       round(slope_pct, 2) if slope_pct is not None else None,
        'aspect_deg':      round(aspect_deg, 1) if aspect_deg is not None else None,
        'relief_1km':      relief_1km,
        'repr_error_flag': repr_ef,
        'terrain_class':   tc,
    }


# ── Append to hrrr_error_dataset_dem.csv ─────────────────────────────────────

def check_existing_entry():
    """Return True if CUUC1/woolsey_2018 already exists in DEM CSV."""
    if not os.path.exists(DEM_CSV):
        return False
    with open(DEM_CSV, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('stid') == STID and r.get('event_id') == EVENT_ID:
                return True
    return False


def append_to_dem_csv(metrics):
    """
    Append one row to hrrr_error_dataset_dem.csv with format compatible
    with merge_woolsey_dem.py (reads slope/aspect/relief_1km/repr_error_flag/
    terrain_class/terrain_class_source/dem_verified).
    """
    row = {
        'stid':                STID,
        'event_id':            EVENT_ID,
        'lat':                 LAT,
        'lon':                 LON,
        'elev_m_reg':          ELEV_REG,
        'dem_elev_m':          metrics['dem_elev_m'] or '',
        'elev_resid_m':        round(metrics['dem_elev_m'] - ELEV_REG, 1)
                                if metrics['dem_elev_m'] is not None else '',
        'slope':               metrics['slope_pct'] or '',    # stored as % in DB
        'aspect':              metrics['aspect_deg'] or '',
        'relief_1km':          metrics['relief_1km'] or '',
        'repr_error_flag':     metrics['repr_error_flag'] or '',
        'terrain_class':       metrics['terrain_class'],
        'terrain_class_source':'dem_computed',
        'dem_verified':        'YES',
    }

    file_exists = os.path.exists(DEM_CSV)
    if file_exists:
        with open(DEM_CSV, newline='', encoding='utf-8') as f:
            existing_fields = csv.DictReader(f).fieldnames or list(row.keys())
    else:
        existing_fields = list(row.keys())

    with open(DEM_CSV, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=existing_fields, extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerow(row)

    print(f'\nAppended to {DEM_CSV}')
    print(f'  stid={STID}  event_id={EVENT_ID}')
    print(f'  slope={row["slope"]}%  aspect={row["aspect"]}°  '
          f'relief_1km={row["relief_1km"]}m')
    print(f'  repr_error_flag={row["repr_error_flag"]}  terrain_class={row["terrain_class"]}')
    print(f'  dem_elev={row["dem_elev_m"]}m  registry_elev={ELEV_REG}m  '
          f'resid={row["elev_resid_m"]}m')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f'CUUC1 DEM fetch  —  {STID}/{EVENT_ID}')
    print(f'  lat={LAT}  lon={LON}  registry_elev={ELEV_REG} m')
    print()

    if check_existing_entry():
        print(f'  CUUC1/woolsey_2018 already in {DEM_CSV} — nothing to do.')
        print('  To re-fetch: delete the row from hrrr_error_dataset_dem.csv and re-run.')
        return

    print('Step 1: fetch DEM')
    if not fetch_dem():
        print('\nFetch failed — check network or py3dep installation.')
        sys.exit(1)

    print('\nStep 2: extract terrain metrics')
    metrics = extract_terrain()
    if metrics is None:
        print('Terrain extraction failed.')
        sys.exit(1)

    print(f'  dem_elev   = {metrics["dem_elev_m"]} m  (registry={ELEV_REG} m)')
    print(f'  slope      = {metrics["slope_deg"]}° = {metrics["slope_pct"]}%')
    print(f'  aspect     = {metrics["aspect_deg"]}°')
    print(f'  relief_1km = {metrics["relief_1km"]} m')
    print(f'  repr_ef    = {metrics["repr_error_flag"]}')
    print(f'  terrain    = {metrics["terrain_class"]}')

    # Elevation QC
    if metrics['dem_elev_m'] is not None:
        resid = metrics['dem_elev_m'] - ELEV_REG
        flag = ' ← LARGE RESIDUAL (>50m), verify coordinates' if abs(resid) > 50 else ' ✓'
        print(f'  elev_resid = {resid:+.1f} m{flag}')

    print('\nStep 3: append to hrrr_error_dataset_dem.csv')
    append_to_dem_csv(metrics)

    print('\nDone. Next step:')
    print('  python merge_woolsey_dem.py   ← merges CUUC1 DEM into hrrr_error_dataset.csv')


if __name__ == '__main__':
    main()
