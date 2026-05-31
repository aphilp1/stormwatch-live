"""Check CRS detection for all scored-station DEMs."""
import sys, numpy as np, math
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
from pyproj import Transformer, CRS

STATIONS = {
    'CBXC1': (40.145640, -121.522500, 6004,
              r'C:\temp\windninja_cache\dem_40.0_-121.3_20mi.tif'),
    'SLEC1': (39.636140, -120.863990, 6670,
              r'C:\temp\windninja_cache\dem_39.6_-120.9_12mi_utm.tif'),
    'KNXC1': (38.861940, -122.417200, 2198,
              r'C:\temp\windninja_cache\dem_38.9_-122.4_8mi_utm.tif'),
    'WMSC1_old': (34.595830, -118.578610, 4930,
                  r'C:\temp\windninja_cache\dem_34.58_-118.66_16mi_utm.tif'),
    'WMSC1_new': (34.595830, -118.578610, 4930,
                  r'C:\temp\windninja_cache\dem_34.60_-118.58_20mi_wmsc1.tif'),
}

for stid, (lat, lon, reg_ft, path) in STATIONS.items():
    img = Image.open(path)
    t = img.tag_v2
    Sx = float(t[33550][0]); Sy = float(t[33550][1])
    x0 = float(t[33922][3]); y0 = float(t[33922][4])
    geo_ascii = str(t.get(34737, ''))
    ncols, nrows = img.size

    # CRS detection using GeoAscii string
    if abs(x0) < 360:
        epsg = 4326
    elif 'zone 10N' in geo_ascii or 'Zone_10N' in geo_ascii:
        epsg = 32610
    elif 'zone 11N' in geo_ascii or 'Zone_11N' in geo_ascii:
        epsg = 32611
    else:
        epsg = 32610   # default

    arr = np.array(img, dtype=float)
    for nd in [-9999, 9999]:
        arr[np.abs(arr - nd) < 1] = np.nan

    if epsg == 4326:
        col = (lon - x0) / Sx
        row = (y0 - lat) / Sy
    else:
        t_fwd = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
        x, y = t_fwd.transform(lon, lat)
        col = (x - x0) / Sx
        row = (y0 - y) / Sy

    ci = max(0, min(int(round(col)), ncols-1))
    ri = max(0, min(int(round(row)), nrows-1))
    elev = arr[ri, ci]
    reg_m = reg_ft * 0.3048
    diff  = elev - reg_m

    px_m = (Sx if epsg != 4326
            else Sx * 111000 * math.cos(math.radians(lat)))
    margins = [ri, nrows-1-ri, ci, ncols-1-ci]
    margin_km = min(margins) * px_m / 1000

    # 1km max elevation
    r_px = max(1, int(1000 / px_m))
    r0=max(0,ri-r_px); r1=min(nrows,ri+r_px+1)
    c0=max(0,ci-r_px); c1=min(ncols,ci+r_px+1)
    nbr = arr[r0:r1,c0:c1].flatten(); nbr = nbr[~np.isnan(nbr)]
    nbr_max = np.nanmax(nbr) if len(nbr) > 0 else 0
    pct_below = (nbr < elev).sum()/len(nbr)*100 if len(nbr) > 0 else 0

    ok = abs(diff) <= 100
    print(f'{stid:12s}  EPSG:{epsg}  Sx={Sx:.2f}  '
          f'x0={x0:.1f} y0={y0:.1f}')
    print(f'  pixel: ({ri},{ci})  elev_dem={elev:.0f}m ({elev*3.28084:.0f}ft)  '
          f'reg={reg_m:.0f}m ({reg_ft}ft)  diff={diff:+.0f}m')
    print(f'  margin={margin_km:.1f}km  1km_max={nbr_max:.0f}m  pct_below={pct_below:.0f}%  '
          f'{"OK" if ok else "MISMATCH"}')
    print(f'  GeoAscii: {geo_ascii[:70]!r}')
    print()
