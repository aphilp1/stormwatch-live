"""Download a 12mi DEM tile centered at 39.6N, -120.9W for SLEC1 coverage."""
import requests, sys, math
sys.stdout.reconfigure(encoding='utf-8')

lat_c, lon_c = 39.6, -120.9
buf_km = 19.3   # 12 miles
buf_lat = buf_km / 111.0
buf_lon = buf_km / (111.0 * math.cos(math.radians(lat_c)))
xmin = lon_c - buf_lon
xmax = lon_c + buf_lon
ymin = lat_c - buf_lat
ymax = lat_c + buf_lat
bbox = f'{xmin:.4f},{ymin:.4f},{xmax:.4f},{ymax:.4f}'

# SLEC1 coverage check
slec1_lat, slec1_lon = 39.636140, -120.863990
in_lat = ymin < slec1_lat < ymax
in_lon = xmin < slec1_lon < xmax
margin_lat_km = min(abs(slec1_lat - ymin), abs(ymax - slec1_lat)) * 111.0
margin_lon_km = min(abs(slec1_lon - xmin), abs(xmax - slec1_lon)) * 111.0 * math.cos(math.radians(slec1_lat))

print(f'Domain: {bbox}')
print(f'SLEC1 ({slec1_lat},{slec1_lon}): lat_in={in_lat}  lon_in={in_lon}')
print(f'Margin to edge: {margin_lat_km:.1f}km (lat) / {margin_lon_km:.1f}km (lon)')
print()

OUT = r'C:\temp\windninja_cache\dem_39.6_-120.9_12mi.tif'

# USGS 3DEP 1/3 arc-second elevation service
url = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'
params = {
    'bbox': bbox,
    'bboxSR': '4326',
    'size': '1024,1024',
    'imageSR': '4326',
    'format': 'tiff',
    'pixelType': 'F32',
    'noDataInterpretation': 'esriNoDataMatchAny',
    'interpolation': '+RSP_BilinearInterpolation',
    'f': 'image',
}

print(f'Fetching 3DEP tile from USGS National Map...')
r = requests.get(url, params=params, timeout=90, stream=True)
ct = r.headers.get('content-type', '?')
size = len(r.content)
print(f'HTTP {r.status_code}  type={ct}  bytes={size}')

if r.status_code == 200 and size > 10000 and 'tiff' in ct.lower():
    with open(OUT, 'wb') as f:
        f.write(r.content)
    print(f'Saved -> {OUT}  ({size//1024}KB)')

    # Verify SLEC1 is covered with margin check
    print()
    print('Coverage confirmation:')
    print(f'  DEM extent: {xmin:.4f}W to {xmax:.4f}W,  {ymin:.4f}N to {ymax:.4f}N')
    print(f'  SLEC1:      {slec1_lon}W,  {slec1_lat}N')
    print(f'  Margin:     {margin_lat_km:.1f}km from N/S edge,  {margin_lon_km:.1f}km from E/W edge')
    print(f'  Covered:    {"YES" if in_lat and in_lon else "NO"}')
    print()
    print('WindNinja domain context:')
    print('  A WindNinja run at SLEC1 needs ~3-5km of terrain context on each side.')
    print(f'  Minimum margin to any edge: {min(margin_lat_km, margin_lon_km):.1f}km — '
          f'{"SUFFICIENT (>5km)" if min(margin_lat_km, margin_lon_km) > 5 else "*** CHECK"}')
else:
    print(f'FAIL. Body: {r.text[:300]}')
