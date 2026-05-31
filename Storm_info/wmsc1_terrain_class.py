"""
wmsc1_terrain_class.py
Classify WMSC1 (Warm Springs) terrain: exposed ridge vs gap/wash/valley.

Three checks:
  1. Metadata: elevation from registry (already confirmed 4930 ft / 1502.7 m)
  2. DEM analysis: local relief, ridgeline vs drainage, aspect (from dem_34.58_-118.66_16mi_utm.tif)
  3. Direction consistency: is WMSC1 wind direction steady (ridge) or variable (terrain-deflected)?
"""

import sys, os, math, csv
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

# ─── 1. METADATA FROM REGISTRY ────────────────────────────────────────────────
print('='*65)
print('1. WMSC1 METADATA (raws_station_registry.csv)')
print('='*65)

WMSC1_LAT  = 34.595830
WMSC1_LON  = -118.578610
WMSC1_ELEV_FT = 4930.0
WMSC1_ELEV_M  = 1502.7

print(f'  Station: WMSC1  (WARM SPRINGS)')
print(f'  Lat/Lon: {WMSC1_LAT}N, {WMSC1_LON}W')
print(f'  Elevation: {WMSC1_ELEV_FT:.0f} ft  /  {WMSC1_ELEV_M:.1f} m  (Synoptic-reported)')
print()
print(f'  Context (Camp Fire ridges for comparison):')
print(f'    CBXC1 Colby:     6004 ft / 1830 m  → in-band WN ratio 1.007 ✓')
print(f'    SLEC1 Saddleback:6670 ft / 2033 m  → in-band WN ratio 1.128 ✓')
print(f'    WMSC1 Warm Sprgs:4930 ft / 1503 m  → this analysis')
print()
print(f'  VBG inversion lid: ~1388 m  → WMSC1 is {WMSC1_ELEV_M-1388:.0f} m ABOVE inversion')
print(f'  850 hPa height at bc_current 12Z: ~1514 m  → WMSC1 just below 850 hPa level')

# ─── 2. DEM ANALYSIS ──────────────────────────────────────────────────────────
print()
print('='*65)
print('2. DEM TERRAIN ANALYSIS')
print(f'   Source: dem_34.58_-118.66_16mi_utm.tif')
print(f'   Station: {WMSC1_LAT}N, {WMSC1_LON}W')
print('='*65)

DEM_PATH = r'C:\temp\windninja_cache\dem_34.58_-118.66_16mi_utm.tif'

try:
    import rasterio
    from rasterio.transform import rowcol
    from pyproj import Transformer

    with rasterio.open(DEM_PATH) as src:
        crs = src.crs
        transform = src.transform
        data = src.read(1).astype(float)
        nodata = src.nodata
        res = src.res   # (pixel_width, pixel_height) in CRS units

        print(f'  DEM CRS:        {crs}')
        print(f'  DEM resolution: {res[0]:.1f} x {res[1]:.1f} m')
        print(f'  DEM shape:      {data.shape}')

        if nodata is not None:
            data[data == nodata] = np.nan

        # Convert station lat/lon to DEM CRS
        transformer = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
        x_sta, y_sta = transformer.transform(WMSC1_LON, WMSC1_LAT)
        print(f'  Station in DEM CRS: ({x_sta:.1f}, {y_sta:.1f})')

        # Get row/col for station
        row_sta, col_sta = rowcol(transform, x_sta, y_sta)
        row_sta, col_sta = int(row_sta), int(col_sta)
        nrows, ncols = data.shape
        row_sta = max(0, min(row_sta, nrows-1))
        col_sta = max(0, min(col_sta, ncols-1))
        elev_dem = data[row_sta, col_sta]

        print(f'  Station row/col:    ({row_sta}, {col_sta})')
        print(f'  DEM elev at station:{elev_dem:.1f} m  '
              f'(registry: {WMSC1_ELEV_M} m, diff={elev_dem-WMSC1_ELEV_M:.1f} m)')

        px = abs(res[0])   # pixel size in meters

        # Local relief at multiple radii
        print()
        print(f'  LOCAL RELIEF (station elev vs neighborhood min/max):')
        for radius_m in [500, 1000, 2000, 3000]:
            r_px = max(1, int(radius_m / px))
            r0 = max(0, row_sta - r_px); r1 = min(nrows, row_sta + r_px + 1)
            c0 = max(0, col_sta - r_px); c1 = min(ncols, col_sta + r_px + 1)
            patch = data[r0:r1, c0:c1]

            # mask to actual radius
            rows_idx, cols_idx = np.mgrid[r0:r1, c0:c1]
            dist_m = np.sqrt(((rows_idx - row_sta)*px)**2 + ((cols_idx - col_sta)*px)**2)
            patch_masked = np.where(dist_m <= radius_m, patch, np.nan)
            valid = patch_masked[~np.isnan(patch_masked)]

            if len(valid) == 0: continue
            nbr_min = np.nanmin(valid)
            nbr_max = np.nanmax(valid)
            relief  = nbr_max - nbr_min
            pct_below = (valid < elev_dem).sum() / len(valid) * 100

            print(f'    r={radius_m:4d}m:  min={nbr_min:.0f}m  max={nbr_max:.0f}m  '
                  f'relief={relief:.0f}m  pct_cells_below_station={pct_below:.0f}%')

        # Ridgeline vs drainage: what fraction of surrounding cells are LOWER?
        r_px_1k = max(1, int(1000 / px))
        r0 = max(0, row_sta - r_px_1k); r1 = min(nrows, row_sta + r_px_1k + 1)
        c0 = max(0, col_sta - r_px_1k); c1 = min(ncols, col_sta + r_px_1k + 1)
        patch = data[r0:r1, c0:c1]
        rows_idx, cols_idx = np.mgrid[r0:r1, c0:c1]
        dist_m = np.sqrt(((rows_idx-row_sta)*px)**2 + ((cols_idx-col_sta)*px)**2)
        valid_mask = (dist_m > 0) & (dist_m <= 1000) & ~np.isnan(patch)
        neighbors = patch[valid_mask]
        pct_lower = (neighbors < elev_dem).sum() / len(neighbors) * 100 if len(neighbors) else 0

        print()
        print(f'  RIDGELINE INDICATOR (1km radius):')
        print(f'    {pct_lower:.0f}% of surrounding cells within 1km are LOWER than station')
        if pct_lower > 70:
            print(f'    → Station sits ABOVE most surroundings: RIDGE / SUMMIT character')
        elif pct_lower < 30:
            print(f'    → Station sits BELOW most surroundings: VALLEY / DRAINAGE character')
        else:
            print(f'    → Station sits at mid-slope or saddle: MIXED terrain')

        # Aspect: compute slope direction toward lowest neighbor
        # Use gradient of DEM at station cell ±5 pixels
        r_asp = 5
        r0a = max(0, row_sta-r_asp); r1a = min(nrows, row_sta+r_asp+1)
        c0a = max(0, col_sta-r_asp); c1a = min(ncols, col_sta+r_asp+1)
        patch_asp = data[r0a:r1a, c0a:c1a]
        patch_asp = np.where(np.isnan(patch_asp), np.nanmean(patch_asp), patch_asp)

        # dz/dy (south-positive in image coords = north in geographic)
        dz_dc = np.gradient(patch_asp, axis=1)   # east gradient
        dz_dr = np.gradient(patch_asp, axis=0)   # south gradient (image row increases south)
        mid_r = min(r_asp, patch_asp.shape[0]//2)
        mid_c = min(r_asp, patch_asp.shape[1]//2)
        dz_dx = dz_dc[mid_r, mid_c] / px   # dz per meter, east
        dz_dy = -dz_dr[mid_r, mid_c] / px  # dz per meter, north (negate row direction)

        slope_deg = math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2)))

        # Aspect: direction the slope faces (direction of uphill)
        # Uphill direction = gradient direction
        if dz_dx == 0 and dz_dy == 0:
            aspect = None
        else:
            # atan2(east_component, north_component) → clockwise from north
            aspect_uphill = math.degrees(math.atan2(dz_dx, dz_dy)) % 360
            aspect_facing = (aspect_uphill + 180) % 360  # downhill-facing aspect

        dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
                'S','SSW','SW','WSW','W','WNW','NW','NNW']
        def to_compass(deg):
            return dirs[int((deg + 11.25) / 22.5) % 16]

        print()
        print(f'  SLOPE AND ASPECT (at station cell ±{r_asp*px:.0f}m):')
        print(f'    Slope: {slope_deg:.1f}°')
        print(f'    Aspect (downhill-facing): {aspect_facing:.0f}° ({to_compass(aspect_facing)})')
        print(f'    Aspect (uphill direction): {aspect_uphill:.0f}° ({to_compass(aspect_uphill)})')
        print(f'    Interpretation: slope descends toward {to_compass(aspect_facing)}')

        # Check for ridgeline geometry: planform curvature
        # Simple: compare station elev to the 8 immediate neighbors
        neighbors_3x3 = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                rr = row_sta + dr; cc = col_sta + dc
                if 0 <= rr < nrows and 0 <= cc < ncols and not np.isnan(data[rr, cc]):
                    neighbors_3x3.append(data[rr, cc])
        if neighbors_3x3:
            n3_mean = np.mean(neighbors_3x3)
            n3_max  = np.max(neighbors_3x3)
            above_all = all(elev_dem >= h for h in neighbors_3x3)
            above_most = sum(elev_dem >= h for h in neighbors_3x3) / len(neighbors_3x3)
            print()
            print(f'  IMMEDIATE NEIGHBORS (3x3 grid, ~{px:.0f}m resolution):')
            print(f'    Station: {elev_dem:.0f}m  |  Neighbors mean: {n3_mean:.0f}m  '
                  f'max: {n3_max:.0f}m')
            print(f'    Station above {above_most*100:.0f}% of immediate neighbors')
            if above_most > 0.75:
                print(f'    → LOCAL HIGH POINT: ridge/summit at pixel scale')
            elif above_most < 0.25:
                print(f'    → LOCAL LOW POINT: drainage/valley at pixel scale')
            else:
                print(f'    → MID-SLOPE: saddle or hillside')

except ImportError:
    print('  rasterio not available — trying gdal fallback')
    try:
        from osgeo import gdal
        ds = gdal.Open(DEM_PATH)
        band = ds.GetRasterBand(1)
        gt = ds.GetGeoTransform()
        prj = ds.GetProjection()
        arr = band.ReadAsArray().astype(float)
        nodata_val = band.GetNoDataValue()
        if nodata_val is not None:
            arr[arr == nodata_val] = np.nan

        # Transform coords
        from pyproj import Transformer, CRS
        src_crs = CRS.from_wkt(prj)
        transformer = Transformer.from_crs('EPSG:4326', src_crs, always_xy=True)
        x_sta, y_sta = transformer.transform(WMSC1_LON, WMSC1_LAT)

        # gt = (x_origin, px_w, rot, y_origin, rot, px_h)
        px_size = abs(gt[1])
        col_sta = int((x_sta - gt[0]) / gt[1])
        row_sta = int((y_sta - gt[3]) / gt[5])
        nrows, ncols = arr.shape
        row_sta = max(0, min(row_sta, nrows-1))
        col_sta = max(0, min(col_sta, ncols-1))
        elev_dem = arr[row_sta, col_sta]
        print(f'  DEM elev at station: {elev_dem:.1f} m  (registry: {WMSC1_ELEV_M} m)')

        # 1km relief
        r_px = max(1, int(1000 / px_size))
        r0=max(0,row_sta-r_px); r1=min(nrows,row_sta+r_px+1)
        c0=max(0,col_sta-r_px); c1=min(ncols,col_sta+r_px+1)
        patch = arr[r0:r1, c0:c1]
        valid = patch[~np.isnan(patch)]
        pct_lower = (valid < elev_dem).sum() / len(valid) * 100 if len(valid) else 0
        print(f'  1km relief: min={np.nanmin(valid):.0f}m max={np.nanmax(valid):.0f}m '
              f'relief={np.nanmax(valid)-np.nanmin(valid):.0f}m')
        print(f'  {pct_lower:.0f}% of 1km cells are lower than station → '
              + ('RIDGE' if pct_lower>70 else 'VALLEY' if pct_lower<30 else 'MID-SLOPE'))
        ds = None
    except Exception as e2:
        print(f'  GDAL also failed: {e2}')
        print('  Cannot perform DEM analysis without rasterio or GDAL')

except Exception as e:
    print(f'  DEM analysis error: {e}')
    import traceback; traceback.print_exc()

# ─── 3. DIRECTION CONSISTENCY ─────────────────────────────────────────────────
print()
print('='*65)
print('3. WIND DIRECTION CONSISTENCY (WMSC1 vs WTPC1)')
print('   Steady = sees synoptic flow (ridge); variable = terrain-deflected')
print('='*65)

RAWS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\thomas_2017'

for stid, fname in [('WMSC1','WMSC1_thomas_2017.csv'), ('WTPC1','WTPC1_thomas_2017.csv')]:
    fpath = os.path.join(RAWS_DIR, fname)
    if not os.path.exists(fpath):
        print(f'  {stid}: file not found'); continue

    rows = list(csv.DictReader(open(fpath, encoding='utf-8')))

    # Gather Dec 4-5 observations with speed > 15 mph
    event_obs = []
    for r in rows:
        t = r['datetime_utc']
        if '2017-12-04' not in t and '2017-12-05' not in t:
            continue
        try:
            spd  = float(r.get('wind_speed_mph') or 0)
            dirn = float(r.get('wind_dir_deg') or 0)
            gust = float(r.get('wind_gust_mph') or 0)
            if spd >= 15:
                event_obs.append((t, spd, dirn, gust))
        except: pass

    if not event_obs:
        print(f'  {stid}: no obs >= 15 mph in Dec 4-5'); continue

    dirs = [d for _, _, d, _ in event_obs]
    speeds = [s for _, s, _, _ in event_obs]

    # Direction statistics
    # Circular std dev
    sin_m = np.mean([math.sin(math.radians(d)) for d in dirs])
    cos_m = np.mean([math.cos(math.radians(d)) for d in dirs])
    R = math.sqrt(sin_m**2 + cos_m**2)       # mean resultant length (0=random, 1=perfectly consistent)
    circ_std = math.degrees(math.sqrt(-2 * math.log(R))) if R > 0 else 999
    mean_dir = math.degrees(math.atan2(sin_m, cos_m)) % 360
    dir_range = max(dirs) - min(dirs)

    # Simple direction spread (percentiles)
    dirs_arr = np.array(dirs)
    p10 = np.percentile(dirs_arr, 10)
    p90 = np.percentile(dirs_arr, 90)

    print()
    print(f'  {stid} (n={len(event_obs)} obs ≥15 mph, Dec 4-5):')
    print(f'    Vector-mean direction: {mean_dir:.0f}°')
    print(f'    Dir range (raw):       {min(dirs):.0f}° – {max(dirs):.0f}°  (span={dir_range:.0f}°)')
    print(f'    Dir 10th–90th pct:     {p10:.0f}° – {p90:.0f}°')
    print(f'    Circular std dev:      {circ_std:.0f}°  (lower = more consistent)')
    print(f'    Mean resultant R:      {R:.3f}  (1.0 = perfectly steady, 0 = random)')

    if R >= 0.90:
        steadiness = 'VERY STEADY (R≥0.90) → ridge/synoptic character'
    elif R >= 0.75:
        steadiness = 'MOSTLY STEADY (R≥0.75) → probable ridge'
    elif R >= 0.50:
        steadiness = 'MODERATE CONSISTENCY → ambiguous'
    else:
        steadiness = 'VARIABLE (R<0.50) → terrain-deflected or transitional'
    print(f'    → {steadiness}')

    # Hourly detail for Dec 5 peak window
    print(f'    Dec 5 10–14Z detail (peak window):')
    for t, spd, dirn, gust in event_obs:
        if '2017-12-05T10' <= t[:16] <= '2017-12-05T14':
            print(f'      {t[:16]}Z  spd={spd:.0f}  dir={dirn:.0f}°  gust={gust:.0f}')

# ─── 4. CLASSIFICATION SUMMARY ────────────────────────────────────────────────
print()
print('='*65)
print('4. TERRAIN CLASSIFICATION SUMMARY')
print('='*65)
print(f'  WMSC1 (WARM SPRINGS):')
print(f'    Elevation:    4930 ft / 1502.7 m')
print(f'    Above inversion lid (1388m VBG): YES  (+115 m)')
print(f'    CBXC1 comp:   1830m (6004ft) — WMSC1 is 327m lower')
print(f'    SLEC1 comp:   2033m (6670ft) — WMSC1 is 530m lower')
print(f'    CUUC1 comp:   1494m (4900ft) — nearly identical elevation')
print()
print('  See DEM analysis above for ridge/valley determination.')
print('  See direction consistency above for synoptic vs deflected flow.')
