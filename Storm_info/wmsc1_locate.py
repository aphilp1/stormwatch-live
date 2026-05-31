"""
wmsc1_locate.py — Find nearest DEM pixels at ~1503m to WMSC1 coords;
query live Synoptic metadata to confirm station location.
"""
import sys, numpy as np, math, requests
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
from pyproj import Transformer, CRS

DEM_PATH  = r'C:\temp\windninja_cache\dem_34.58_-118.66_16mi_utm.tif'
WMSC1_LAT = 34.595830
WMSC1_LON = -118.578610
TARGET_M  = 1502.7

img = Image.open(DEM_PATH)
t = img.tag_v2
Sx, Sy = float(t[33550][0]), float(t[33550][1])
x0, y0 = float(t[33922][3]), float(t[33922][4])
ncols, nrows = img.size
arr = np.array(img, dtype=float)
arr[arr < -1000] = np.nan

crs_dem = CRS.from_epsg(32611)
t_fwd = Transformer.from_crs(CRS.from_epsg(4326), crs_dem, always_xy=True)
t_inv = Transformer.from_crs(crs_dem, CRS.from_epsg(4326), always_xy=True)

x_sta, y_sta = t_fwd.transform(WMSC1_LON, WMSC1_LAT)
col_sta = int(round((x_sta - x0) / Sx))
row_sta = int(round((y0 - y_sta) / Sy))

# Find pixels within 20km of station with elevation within 75m of target
print(f'Searching for DEM pixels within 20km of WMSC1 at elev {TARGET_M-75:.0f}-{TARGET_M+75:.0f} m...')
r_max = int(20000 / Sx)
r0 = max(0, row_sta - r_max); r1 = min(nrows, row_sta + r_max + 1)
c0 = max(0, col_sta - r_max); c1 = min(ncols, col_sta + r_max + 1)

candidates = []
step = 3
for r in range(r0, r1, step):
    for c in range(c0, c1, step):
        e = arr[r, c]
        if np.isnan(e):
            continue
        if abs(e - TARGET_M) < 75:
            x = x0 + c * Sx
            y = y0 - r * Sy
            dist_km = math.sqrt((x - x_sta)**2 + (y - y_sta)**2) / 1000
            lon2, lat2 = t_inv.transform(x, y)
            candidates.append((dist_km, r, c, e, lat2, lon2))

candidates.sort()
print(f'Found {len(candidates)} candidates. Nearest 10:')
for dist, r, c, e, lat, lon in candidates[:10]:
    print(f'  dist={dist:.1f}km  elev={e:.0f}m  lat={lat:.4f}  lon={lon:.4f}  pixel({r},{c})')

if candidates:
    nearest_dist, _, _, nearest_elev, nearest_lat, nearest_lon = candidates[0]
    print()
    print(f'Nearest DEM pixel at target elevation:')
    print(f'  {nearest_dist:.1f} km from registry coords')
    print(f'  lat={nearest_lat:.4f}, lon={nearest_lon:.4f}')
    print(f'  elev={nearest_elev:.0f}m')
    bearing = math.degrees(math.atan2(nearest_lon - WMSC1_LON, nearest_lat - WMSC1_LAT)) % 360
    print(f'  Direction from registry: {bearing:.0f}° ({["N","NE","E","SE","S","SW","W","NW"][int((bearing+22.5)//45)%8]})')

# ─── Live Synoptic metadata query ────────────────────────────────────────────
print()
print('='*55)
print('LIVE SYNOPTIC METADATA — WMSC1')
print('='*55)
TOKEN = '7c76618b66c74aee913bdbae4b448bdd'
HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer': 'https://www.weather.gov/wrh/timeseries?site=WMSC1',
    'Origin': 'https://www.weather.gov',
}
resp = requests.get('https://api.synopticdata.com/v2/stations/metadata',
    params={'stid': 'WMSC1', 'token': TOKEN, 'complete': '1'},
    headers=HDR, timeout=15)
print(f'HTTP status: {resp.status_code}')
if resp.status_code == 200:
    d = resp.json()
    summary = d.get('SUMMARY', {})
    print(f'API response code: {summary.get("RESPONSE_CODE")} — {summary.get("RESPONSE_MESSAGE")}')
    stns = d.get('STATION', [])
    if stns:
        s = stns[0]
        print(f'  STID:      {s.get("STID")}')
        print(f'  Name:      {s.get("NAME")}')
        print(f'  Latitude:  {s.get("LATITUDE")}')
        print(f'  Longitude: {s.get("LONGITUDE")}')
        print(f'  Elevation: {s.get("ELEVATION")} ft')
        print(f'  State:     {s.get("STATE")}')
        print(f'  Network:   {s.get("MNET_ID")}')
        print(f'  Status:    {s.get("STATUS")}')
        # Check coords vs registry
        live_lat = float(s.get('LATITUDE', 0))
        live_lon = float(s.get('LONGITUDE', 0))
        live_elev = float(s.get('ELEVATION', 0))
        lat_diff = abs(live_lat - WMSC1_LAT)
        lon_diff = abs(live_lon - WMSC1_LON)
        elev_diff = abs(live_elev * 0.3048 - TARGET_M)
        print()
        print(f'  Registry vs live comparison:')
        print(f'    Lat diff:  {lat_diff:.6f}° ({lat_diff*111000:.0f} m)')
        print(f'    Lon diff:  {lon_diff:.6f}° ({lon_diff*94000:.0f} m)')
        print(f'    Elev diff: live={live_elev}ft={live_elev*0.3048:.0f}m vs registry={TARGET_M}m → Δ={elev_diff:.0f}m')
    else:
        print('  No stations returned')
        print(f'  Raw: {d}')
else:
    print(f'  Body: {resp.text[:300]}')
