"""
wmsc1_dem_analysis.py
Read dem_34.58_-118.66_16mi_utm.tif with PIL + manual GeoTIFF tag parsing.
Compute local relief, ridgeline indicator, aspect at WMSC1 (34.59583N, -118.57861W).
"""

import sys, math
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

from PIL import Image
from PIL.TiffImagePlugin import IFDRational
from pyproj import Transformer, CRS

DEM_PATH  = r'C:\temp\windninja_cache\dem_34.58_-118.66_16mi_utm.tif'
WMSC1_LAT = 34.595830
WMSC1_LON = -118.578610

# ─── Read GeoTIFF via PIL ─────────────────────────────────────────────────────
img = Image.open(DEM_PATH)
tag_info = img.tag_v2   # raw IFD tags

# Key GeoTIFF tags
# 33550 = ModelPixelScaleTag   (Sx, Sy, Sz)  — pixel size in map units
# 33922 = ModelTiepointTag     (i,j,k, x,y,z) — tie-point
# 34737 = GeoAsciiParamsTag    — CRS string
# 34736 = GeoDoubleParamsTag   — CRS params

MODEL_PIXEL_SCALE_TAG = 33550
MODEL_TIEPOINT_TAG    = 33922
GEO_ASCII_TAG         = 34737
GEO_KEY_DIRECTORY_TAG = 34735
GEO_DOUBLE_PARAMS_TAG = 34736

scale = tag_info.get(MODEL_PIXEL_SCALE_TAG)
tiepoint = tag_info.get(MODEL_TIEPOINT_TAG)
geo_ascii = tag_info.get(GEO_ASCII_TAG, '')

print(f'DEM file: {DEM_PATH}')
print(f'Image size: {img.size[0]} x {img.size[1]} (ncols x nrows)')
print(f'Mode: {img.mode}')

# Parse scale and tiepoint into a geotransform
# ModelPixelScaleTag: (Sx, Sy, Sz) — Sy is always positive, but row increases downward
if scale:
    Sx = float(scale[0]); Sy = float(scale[1])
    print(f'Pixel scale: {Sx:.2f} x {Sy:.2f} m')
else:
    print('ERROR: no ModelPixelScaleTag'); sys.exit(1)

if tiepoint:
    # typically (0, 0, 0, x_origin, y_origin, 0)
    i0, j0, k0, x0, y0, z0 = [float(v) for v in tiepoint[:6]]
    print(f'Tiepoint: pixel({i0},{j0}) → map({x0:.1f}, {y0:.1f})')
else:
    print('ERROR: no ModelTiepointTag'); sys.exit(1)

# GeoTransform (GDAL convention):
# x = x0 + col * Sx
# y = y0 - row * Sy  (y decreases going down)
ncols, nrows = img.size
print(f'GeoTransform: x_origin={x0:.1f}, y_origin={y0:.1f}, px={Sx:.2f}m')
print(f'Extent: x=[{x0:.0f}, {x0+ncols*Sx:.0f}] y=[{y0-nrows*Sy:.0f}, {y0:.0f}]')

# ─── Determine CRS ────────────────────────────────────────────────────────────
# Try to infer from GeoAsciiParamsTag and bounding box
# The filename says _utm, and the bbox is ~UTM Zone 11N range
print(f'GeoAsciiParamsTag: {geo_ascii!r}')

# UTM Zone 11N (EPSG:32611) covers longitude 120W-114W at this latitude
# x range ~300k-800k m, y range ~3.8M-4.0M m
if x0 > 100000 and y0 > 1000000:
    # Likely UTM
    if 300000 < x0 < 800000 and 3700000 < y0 < 4200000:
        crs_dem = CRS.from_epsg(32611)   # UTM Zone 11N
        print('Inferred CRS: EPSG:32611 (UTM Zone 11N) from coordinate range')
    else:
        print(f'WARNING: coordinates out of expected UTM 11N range — check CRS')
        crs_dem = CRS.from_epsg(32611)
else:
    # Geographic?
    crs_dem = CRS.from_epsg(4326)
    print('CRS appears to be geographic (EPSG:4326)')

# ─── Transform WMSC1 coords to DEM CRS ───────────────────────────────────────
transformer = Transformer.from_crs(CRS.from_epsg(4326), crs_dem, always_xy=True)
x_sta, y_sta = transformer.transform(WMSC1_LON, WMSC1_LAT)
print(f'\nWMSC1 in DEM CRS: ({x_sta:.1f}, {y_sta:.1f})')

col_sta = (x_sta - x0) / Sx
row_sta = (y0 - y_sta) / Sy   # y decreases going down
print(f'WMSC1 pixel: row={row_sta:.1f}, col={col_sta:.1f}')

col_i = int(round(col_sta)); row_i = int(round(row_sta))
col_i = max(0, min(col_i, ncols-1))
row_i = max(0, min(row_i, nrows-1))
print(f'WMSC1 pixel (rounded): row={row_i}, col={col_i}')

# ─── Load DEM as numpy array ──────────────────────────────────────────────────
arr = np.array(img, dtype=float)
nodata_candidates = [-9999, -9999.0, 9999, 32767, -32768, -32767]
for nd in nodata_candidates:
    mask = np.abs(arr - nd) < 1
    if mask.sum() > 0:
        arr[mask] = np.nan
        print(f'Masked {mask.sum()} nodata cells (value {nd})')
        break

elev_at_sta = arr[row_i, col_i]
print(f'\nDEM elevation at WMSC1 pixel: {elev_at_sta:.1f} m')
print(f'Registry elevation:            1502.7 m  (diff={elev_at_sta-1502.7:.1f}m)')

# ─── Local relief at multiple radii ──────────────────────────────────────────
print()
print('LOCAL RELIEF ANALYSIS')
print(f'{"Radius":>8s}  {"Min(m)":>8s}  {"Max(m)":>8s}  {"Relief(m)":>10s}  {"PctBelow":>9s}  {"Character"}')
print('-'*70)

classifications = []
for radius_m in [250, 500, 1000, 2000, 3000]:
    r_px = max(1, int(radius_m / Sx))
    r0 = max(0, row_i - r_px); r1 = min(nrows, row_i + r_px + 1)
    c0 = max(0, col_i - r_px); c1 = min(ncols, col_i + r_px + 1)
    patch = arr[r0:r1, c0:c1].copy()

    # Mask to circular radius
    rows_g, cols_g = np.mgrid[r0:r1, c0:c1]
    dist_m = np.sqrt(((rows_g - row_i)*Sy)**2 + ((cols_g - col_i)*Sx)**2)
    patch_circ = np.where((dist_m > 0) & (dist_m <= radius_m), patch, np.nan)
    valid = patch_circ[~np.isnan(patch_circ)]

    if len(valid) == 0:
        print(f'{radius_m:>7}m  (no data)'); continue

    nbr_min   = np.nanmin(valid)
    nbr_max   = np.nanmax(valid)
    relief    = nbr_max - nbr_min
    pct_below = (valid < elev_at_sta).sum() / len(valid) * 100

    if pct_below > 75: char = 'RIDGE/SUMMIT'
    elif pct_below > 55: char = 'upper slope'
    elif pct_below > 35: char = 'mid-slope'
    elif pct_below > 15: char = 'lower slope'
    else: char = 'VALLEY/DRAINAGE'

    print(f'{radius_m:>7}m  {nbr_min:>8.0f}  {nbr_max:>8.0f}  {relief:>10.0f}  '
          f'{pct_below:>8.0f}%  {char}')
    classifications.append((radius_m, pct_below, char))

# ─── Immediate 3×3 neighbors ─────────────────────────────────────────────────
print()
print('IMMEDIATE NEIGHBORS (3×3 grid, one-pixel offsets)')
neighbors = []
for dr in [-1, 0, 1]:
    for dc in [-1, 0, 1]:
        if dr == 0 and dc == 0: continue
        rr = row_i + dr; cc = col_i + dc
        if 0 <= rr < nrows and 0 <= cc < ncols and not np.isnan(arr[rr, cc]):
            neighbors.append(arr[rr, cc])
if neighbors:
    above_pct = sum(elev_at_sta >= h for h in neighbors) / len(neighbors) * 100
    print(f'  Station: {elev_at_sta:.0f}m  |  Neighbors: '
          f'min={min(neighbors):.0f}m  max={max(neighbors):.0f}m  mean={np.mean(neighbors):.0f}m')
    print(f'  Station above {above_pct:.0f}% of immediate neighbors '
          f'({sum(elev_at_sta>=h for h in neighbors)}/{len(neighbors)})')
    if above_pct > 75:
        local_char = 'LOCAL HIGH POINT → ridge/summit pixel'
    elif above_pct < 25:
        local_char = 'LOCAL LOW POINT → drainage/valley pixel'
    else:
        local_char = 'MID-SLOPE → saddle or hillside'
    print(f'  → {local_char}')

# ─── Slope and aspect ─────────────────────────────────────────────────────────
print()
print('SLOPE AND ASPECT')
r_asp = 10
r0a = max(0, row_i-r_asp); r1a = min(nrows, row_i+r_asp+1)
c0a = max(0, col_i-r_asp); c1a = min(ncols, col_i+r_asp+1)
patch_asp = arr[r0a:r1a, c0a:c1a].copy()
patch_asp = np.where(np.isnan(patch_asp), np.nanmedian(patch_asp), patch_asp)

# Gradient: dz/dc = east, dz/dr = south (image row increases southward)
grad_r, grad_c = np.gradient(patch_asp, Sy, Sx)
mid_r = min(r_asp, patch_asp.shape[0]//2)
mid_c = min(r_asp, patch_asp.shape[1]//2)
dz_east  =  grad_c[mid_r, mid_c]   # dz per meter going east
dz_north = -grad_r[mid_r, mid_c]   # dz per meter going north (negate row direction)

slope_deg = math.degrees(math.atan(math.sqrt(dz_east**2 + dz_north**2)))

if abs(dz_east) > 1e-9 or abs(dz_north) > 1e-9:
    # Uphill direction (direction gradient points)
    uphill_deg = math.degrees(math.atan2(dz_east, dz_north)) % 360
    # Aspect = direction the FACE looks = downhill direction
    aspect_deg = (uphill_deg + 180) % 360
else:
    aspect_deg = None; uphill_deg = None

dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
        'S','SSW','SW','WSW','W','WNW','NW','NNW']
def compass(d): return dirs[int((d + 11.25) / 22.5) % 16]

print(f'  Slope angle: {slope_deg:.1f}°')
if aspect_deg is not None:
    print(f'  Aspect (face direction / downhill): {aspect_deg:.0f}° ({compass(aspect_deg)})')
    print(f'  Uphill direction:                   {uphill_deg:.0f}° ({compass(uphill_deg)})')
    # For Santa Ana flow (NNE/ENE, ~40-60°): does slope face INTO the wind?
    wind_dir = 52   # WMSC1 vector-mean wind direction
    wind_source = (wind_dir + 180) % 360   # direction wind comes FROM
    aspect_alignment = abs((aspect_deg - wind_source + 180) % 360 - 180)
    print(f'  Wind comes from: {wind_source:.0f}° ({compass(wind_source)})')
    print(f'  Slope face vs wind-source alignment: {aspect_alignment:.0f}°  '
          f'(0°=fully exposed, 90°=crosswind, 180°=lee)')
    if aspect_alignment < 45:
        print(f'  → WINDWARD: slope faces into the synoptic flow — exposed')
    elif aspect_alignment < 135:
        print(f'  → CROSSWIND: moderate exposure')
    else:
        print(f'  → LEEWARD: slope faces away from flow — sheltered')

# ─── Final summary ────────────────────────────────────────────────────────────
print()
print('='*65)
print('DEM TERRAIN CLASSIFICATION SUMMARY FOR WMSC1')
print('='*65)
print(f'  Elevation:    4930 ft / {elev_at_sta:.0f} m (DEM), 1502.7 m (registry)')
print(f'  Pixel size:   {Sx:.0f} m')
if classifications:
    # Majority vote
    ridge_count = sum(1 for _, pct, _ in classifications if pct > 65)
    valley_count = sum(1 for _, pct, _ in classifications if pct < 35)
    if ridge_count >= len(classifications)//2:
        verdict = 'EXPOSED RIDGE / HIGH TERRAIN'
    elif valley_count >= len(classifications)//2:
        verdict = 'VALLEY / DRAINAGE'
    else:
        verdict = 'MID-SLOPE (ambiguous)'
    pcts = [pct for _, pct, _ in classifications]
    print(f'  PctBelow at radii: {[f"{p:.0f}%" for _,p,_ in classifications]}')
    print(f'  Overall verdict:  {verdict}')
    print(f'  Mean pct-below:   {np.mean(pcts):.0f}%')
