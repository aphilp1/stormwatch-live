"""
thomas_wmsc1_fix.py
====================
Step 1: Download a new DEM centered on WMSC1 (34.60N, -118.58W), 20mi extent.
Step 2: Verify DEM elevation at WMSC1 is within ±50m of registry 1503m.
        STOP if not — report the discrepancy and exit before scoring.
Step 3: Check DEM-edge integrity for all other scored stations:
        CBXC1, SLEC1, JBGC1, KNXC1 vs their own DEMs.
Step 4: Re-run Stage 2 for Thomas/WMSC1 with the corrected DEM.
        BC: 850 hPa 12Z 2017-12-05 (pre-registered).
        GF: report under all three — median 1.560, concurrent-hour 1.487, peak 1.619.
Step 5: Print updated cross-event table.

No master-status writes — show human first.
"""

import sys, os, math, csv, subprocess, glob, time, requests
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

os.environ['PATH'] = (
    r'C:\Users\aphil\miniforge3\envs\hrrr311' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\mingw-w64\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\usr\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Scripts' + os.pathsep +
    os.environ.get('PATH', '')
)
from PIL import Image
from pyproj import Transformer, CRS
from herbie import Herbie

WN    = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE = r'C:\temp\windninja_cache'
RAWS  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs'

# ─── Constants ────────────────────────────────────────────────────────────────
WMSC1_LAT     = 34.595830
WMSC1_LON     = -118.578610
WMSC1_REG_M   = 1502.7
ELEV_TOL_M    = 50.0          # pass/fail tolerance for DEM elevation check

NEW_DEM_NAME  = 'dem_34.60_-118.58_20mi_wmsc1.tif'
NEW_DEM_PATH  = os.path.join(CACHE, NEW_DEM_NAME)
CENTER_LAT    = 34.60
CENTER_LON    = -118.58
EXTENT_MI     = 20
EXTENT_KM     = EXTENT_MI * 1.60934

# Pre-registered BC
HRRR_TIME   = '2017-12-05 12:00'
LEVEL       = 850
BC_CENTER   = (34.58, -118.70)
RAWS_PREFIX = '2017-12-05T12'

# GFs to test
GF_MEDIAN   = 1.560   # pre-registered (median empirical)
GF_CONC     = 1.487   # concurrent-hour GF (55.01 gust / 37.0 sustained at 12Z)
GF_PEAK     = 1.619   # peak-moment GF (68.0 / 42.01 at 13Z)

PASS_LO, PASS_HI = 0.80, 1.20

# Other station DEMs for edge-integrity check
OTHER_STATIONS = {
    'CBXC1': {'lat': 40.145640, 'lon': -121.522500, 'reg_ft': 6004,
               'dem': 'dem_40.0_-121.3_20mi.tif'},
    'SLEC1': {'lat': 39.636140, 'lon': -120.863990, 'reg_ft': 6670,
               'dem': 'dem_39.6_-120.9_12mi_utm.tif'},
    'JBGC1': {'lat': 39.735910, 'lon': -121.488980, 'reg_ft': 1785,
               'dem': 'dem_39.8_-121.5_12mi.tif'},
    'KNXC1': {'lat': 38.861940, 'lon': -122.417200, 'reg_ft': 2198,
               'dem': 'dem_38.9_-122.4_8mi_utm.tif'},
}

def load_dem_geotiff(path):
    """Load DEM from GeoTIFF using PIL; return (arr, Sx, Sy, x0, y0, crs_epsg)."""
    img = Image.open(path)
    t   = img.tag_v2
    Sx  = float(t[33550][0]); Sy = float(t[33550][1])
    x0  = float(t[33922][3]); y0 = float(t[33922][4])
    geo_ascii = t.get(34737, '')
    arr = np.array(img, dtype=float)
    for nd in [-9999, 9999, 32767, -32768]:
        arr[np.abs(arr - nd) < 1] = np.nan
    # Detect CRS
    if x0 > 100000 and y0 > 1000000:
        epsg = 32611 if 300000 < x0 < 900000 else 32610
    else:
        epsg = 4326
    return arr, Sx, Sy, x0, y0, epsg, str(geo_ascii)

def dem_elev_at(arr, Sx, Sy, x0, y0, epsg, lat, lon):
    """Return DEM elevation in metres at given lat/lon."""
    nrows, ncols = arr.shape
    if epsg == 4326:
        col = (lon - x0) / Sx
        row = (y0 - lat) / Sy
    else:
        crs_dem = CRS.from_epsg(epsg)
        t_fwd   = Transformer.from_crs(CRS.from_epsg(4326), crs_dem, always_xy=True)
        x, y    = t_fwd.transform(lon, lat)
        col = (x - x0) / Sx
        row = (y0 - y) / Sy
    ci = int(round(col)); ri = int(round(row))
    ci = max(0, min(ci, ncols-1)); ri = max(0, min(ri, nrows-1))
    return float(arr[ri, ci]), ri, ci

def dem_margin_km(arr, Sx, Sy, epsg, ri, ci):
    """Distance from station pixel to nearest DEM edge, in km."""
    nrows, ncols = arr.shape
    px_m = Sx if epsg != 4326 else Sx * 111000 * math.cos(math.radians(34.6))
    margins = [ri, nrows-1-ri, ci, ncols-1-ci]
    return min(margins) * px_m / 1000

def wind_from_uv(u, v):
    spd  = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def nearest(ds, var, lat, lon):
    lats = ds['latitude'].values; lons = ds['longitude'].values % 360
    dist = np.sqrt((lats-lat)**2 + (lons-lon%360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

def run_wn(dem_name, speed, direction):
    dem  = os.path.join(CACHE, dem_name)
    stem = os.path.splitext(dem_name)[0]
    si, di = int(round(speed)), int(round(direction))
    cached_vel = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
        print(f'  [cached] WN {dem_name} {si}mph@{di}°')
        return cached_vel[0], (cached_ang[0] if cached_ang else None)
    if not os.path.exists(dem):
        print(f'  ERROR: DEM not found: {dem}'); return None, None
    print(f'  WN {dem_name} {si}mph@{di}°...', end=' ', flush=True)
    args = [WN, '--num_threads','6','--elevation_file',dem,
            '--initialization_method','domainAverageInitialization',
            '--input_speed',str(si),'--input_speed_units','mph',
            '--input_direction',str(di),
            '--input_wind_height','10','--units_input_wind_height','m',
            '--uni_air_temp','50','--air_temp_units','F',
            '--uni_cloud_cover','0.1','--cloud_cover_units','fraction',
            '--vegetation','trees','--mesh_choice','coarse',
            '--output_wind_height','10','--units_output_wind_height','m',
            '--output_speed_units','mph','--output_path',CACHE,
            '--write_ascii_output','true','--ascii_out_json','0','--ascii_out_4326','1']
    t0 = time.time()
    res = subprocess.run(args, capture_output=True, text=True, timeout=300)
    print(f'[{time.time()-t0:.0f}s]')
    if res.returncode != 0:
        print(f'  ERROR: {res.stderr[-300:]}'); return None, None
    vel = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    ang = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
    return (vel[0] if vel else None), (ang[0] if ang else None)

def read_asc(path, lat, lon):
    with open(path) as f:
        hdr, data = {}, []
        for line in f:
            p = line.strip().split()
            if not p: continue
            if len(p)==2 and not p[0][0].lstrip('-').replace('.','').isdigit():
                hdr[p[0].lower()] = float(p[1])
            else:
                try: data.append([float(v) for v in p])
                except: pass
    arr = np.array(data)
    nr=int(hdr['nrows']); nc=int(hdr['ncols'])
    xll=hdr['xllcorner']; yll=hdr['yllcorner']; cell=hdr['cellsize']
    nd=hdr.get('nodata_value',-9999)
    colf=(lon-xll)/cell; rowf=(nr-1)-(lat-yll)/cell
    ci,ri=int(colf),int(rowf); cr,rr=colf-ci,rowf-ri
    ci=max(0,min(ci,nc-2)); ri=max(0,min(ri,nr-2))
    v=(arr[ri,ci]*(1-rr)*(1-cr)+arr[ri,ci+1]*(1-rr)*cr+
       arr[ri+1,ci]*rr*(1-cr)+arr[ri+1,ci+1]*rr*cr)
    return round(float(v),2) if abs(v-nd)>1 else None

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: DOWNLOAD NEW WMSC1-CENTERED DEM
# ═══════════════════════════════════════════════════════════════════════════════
print('='*65)
print('STEP 1: DOWNLOAD NEW DEM CENTERED ON WMSC1')
print(f'  Center: {CENTER_LAT}N, {CENTER_LON}W  |  Extent: {EXTENT_MI}mi ({EXTENT_KM:.1f}km)')
print(f'  Target: {NEW_DEM_PATH}')
print('='*65)

if os.path.exists(NEW_DEM_PATH):
    print(f'  DEM already exists — skipping download')
else:
    buf_lat = (EXTENT_KM / 2) / 111.0
    buf_lon = (EXTENT_KM / 2) / (111.0 * math.cos(math.radians(CENTER_LAT)))
    xmin = CENTER_LON - buf_lon; xmax = CENTER_LON + buf_lon
    ymin = CENTER_LAT - buf_lat; ymax = CENTER_LAT + buf_lat
    bbox = f'{xmin:.4f},{ymin:.4f},{xmax:.4f},{ymax:.4f}'

    # WMSC1 margin check before downloading
    margin_lat_km = min(abs(WMSC1_LAT-ymin), abs(ymax-WMSC1_LAT)) * 111.0
    margin_lon_km = min(abs(WMSC1_LON-xmin), abs(xmax-WMSC1_LON)) * 111.0 * math.cos(math.radians(WMSC1_LAT))
    print(f'  Domain: {bbox}')
    print(f'  WMSC1 margin: {margin_lat_km:.1f}km (lat), {margin_lon_km:.1f}km (lon)')
    print(f'  Min margin: {min(margin_lat_km, margin_lon_km):.1f}km  '
          f'{"OK (>5km)" if min(margin_lat_km, margin_lon_km) > 5 else "*** TOO CLOSE TO EDGE"}')

    url = ('https://elevation.nationalmap.gov/arcgis/rest/services/'
           '3DEPElevation/ImageServer/exportImage')
    params = {
        'bbox': bbox, 'bboxSR': '4326', 'size': '1024,1024',
        'imageSR': '4326', 'format': 'tiff', 'pixelType': 'F32',
        'noDataInterpretation': 'esriNoDataMatchAny',
        'interpolation': '+RSP_BilinearInterpolation', 'f': 'image',
    }
    print(f'  Fetching 3DEP tile from USGS National Map...', flush=True)
    r = requests.get(url, params=params, timeout=120, stream=True)
    ct = r.headers.get('content-type', '?')
    size = len(r.content)
    print(f'  HTTP {r.status_code}  type={ct}  bytes={size:,}')
    if r.status_code == 200 and size > 10000 and 'tiff' in ct.lower():
        with open(NEW_DEM_PATH, 'wb') as f:
            f.write(r.content)
        print(f'  Saved -> {NEW_DEM_PATH}  ({size//1024}KB)')
    else:
        print(f'  DOWNLOAD FAILED. Body: {r.text[:200]}')
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: VERIFY DEM ELEVATION AT WMSC1
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*65)
print('STEP 2: VERIFY DEM ELEVATION AT WMSC1')
print(f'  Registry: {WMSC1_REG_M} m ({WMSC1_REG_M*3.28084:.0f} ft)')
print(f'  Tolerance: ±{ELEV_TOL_M} m')
print('='*65)

arr_new, Sx_new, Sy_new, x0_new, y0_new, epsg_new, crs_str_new = load_dem_geotiff(NEW_DEM_PATH)
dem_elev_new, ri_new, ci_new = dem_elev_at(arr_new, Sx_new, Sy_new, x0_new, y0_new, epsg_new,
                                             WMSC1_LAT, WMSC1_LON)
nrows_new, ncols_new = arr_new.shape
margin_new = dem_margin_km(arr_new, Sx_new, Sy_new, epsg_new, ri_new, ci_new)

print(f'  DEM CRS:           {crs_str_new.strip()[:60]}  (EPSG:{epsg_new})')
print(f'  DEM shape:         {nrows_new} x {ncols_new}  (pixel size ~{Sx_new:.0f}m)')
print(f'  WMSC1 pixel:       row={ri_new}, col={ci_new}')
print(f'  DEM elev at WMSC1: {dem_elev_new:.1f} m  ({dem_elev_new*3.28084:.0f} ft)')
print(f'  Registry elev:     {WMSC1_REG_M:.1f} m  ({WMSC1_REG_M*3.28084:.0f} ft)')
diff_new = dem_elev_new - WMSC1_REG_M
print(f'  Difference:        {diff_new:+.1f} m')
print(f'  Margin to edge:    {margin_new:.1f} km')

# Local neighborhood max (1km)
r_px = max(1, int(1000 / Sx_new))
r0 = max(0, ri_new-r_px); r1 = min(nrows_new, ri_new+r_px+1)
c0 = max(0, ci_new-r_px); c1 = min(ncols_new, ci_new+r_px+1)
nbr = arr_new[r0:r1, c0:c1].flatten()
nbr = nbr[~np.isnan(nbr)]
pct_below = (nbr < dem_elev_new).sum() / len(nbr) * 100 if len(nbr) > 0 else 0
print(f'  1km nbr: min={np.nanmin(nbr):.0f}m  max={np.nanmax(nbr):.0f}m  '
      f'pct_below={pct_below:.0f}%')

if abs(diff_new) <= ELEV_TOL_M:
    SCORING_OK = True
    print(f'\n  ✓ ELEVATION CHECK PASSED — proceeding to scoring')
else:
    SCORING_OK = False
    print(f'\n  ✗ ELEVATION CHECK FAILED (|{diff_new:+.0f}m| > ±{ELEV_TOL_M}m)')
    print(f'  SRTM/3DEP may genuinely underrepresent this spot.')
    print(f'  DEM max within 1km = {np.nanmax(nbr):.0f}m vs registry {WMSC1_REG_M:.0f}m')
    print(f'  STOPPING before scoring — showing result to human as instructed.')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: EDGE-INTEGRITY CHECK FOR ALL OTHER SCORED STATIONS
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*65)
print('STEP 3: DEM EDGE-INTEGRITY CHECK — ALL SCORED STATIONS')
print(f'  {"Station":8s}  {"RegFt":>6s}  {"RegM":>6s}  {"DEMm":>6s}  '
      f'{"DEMft":>6s}  {"Diff(m)":>8s}  {"Margin(km)":>11s}  {"Pct<Sta":>8s}  Status')
print('-'*90)

edge_results = {}
for stid, info in OTHER_STATIONS.items():
    dem_path = os.path.join(CACHE, info['dem'])
    if not os.path.exists(dem_path):
        print(f'  {stid:8s}  DEM NOT FOUND: {info["dem"]}')
        continue
    try:
        arr_s, Sx_s, Sy_s, x0_s, y0_s, epsg_s, _ = load_dem_geotiff(dem_path)
        dem_e, ri_s, ci_s = dem_elev_at(arr_s, Sx_s, Sy_s, x0_s, y0_s, epsg_s,
                                          info['lat'], info['lon'])
        nrows_s, ncols_s = arr_s.shape
        margin_s = dem_margin_km(arr_s, Sx_s, Sy_s, epsg_s, ri_s, ci_s)
        reg_m = info['reg_ft'] * 0.3048
        diff_s = dem_e - reg_m

        # 1km pct below
        r_px_s = max(1, int(1000 / Sx_s))
        r0s=max(0,ri_s-r_px_s); r1s=min(nrows_s,ri_s+r_px_s+1)
        c0s=max(0,ci_s-r_px_s); c1s=min(ncols_s,ci_s+r_px_s+1)
        nbr_s = arr_s[r0s:r1s,c0s:c1s].flatten()
        nbr_s = nbr_s[~np.isnan(nbr_s)]
        pct_s = (nbr_s < dem_e).sum()/len(nbr_s)*100 if len(nbr_s)>0 else 0

        ok = abs(diff_s) <= ELEV_TOL_M
        status = 'OK' if ok else f'MISMATCH {diff_s:+.0f}m'
        edge_flag = '  *** EDGE?' if margin_s < 3.0 else ''
        print(f'  {stid:8s}  {info["reg_ft"]:>6d}  {reg_m:>6.0f}  {dem_e:>6.0f}  '
              f'{dem_e*3.28084:>6.0f}  {diff_s:>+8.0f}  {margin_s:>11.1f}  '
              f'{pct_s:>7.0f}%  {status}{edge_flag}')
        edge_results[stid] = {'reg_m': reg_m, 'dem_m': dem_e, 'diff': diff_s,
                              'margin': margin_s, 'pct_below': pct_s, 'ok': ok}
    except Exception as e:
        print(f'  {stid:8s}  ERROR: {e}')

# Also add WMSC1 old DEM for comparison
old_dem = os.path.join(CACHE, 'dem_34.58_-118.66_16mi_utm.tif')
if os.path.exists(old_dem):
    arr_o, Sx_o, Sy_o, x0_o, y0_o, epsg_o, _ = load_dem_geotiff(old_dem)
    dem_e_o, ri_o, ci_o = dem_elev_at(arr_o, Sx_o, Sy_o, x0_o, y0_o, epsg_o,
                                        WMSC1_LAT, WMSC1_LON)
    margin_o = dem_margin_km(arr_o, Sx_o, Sy_o, epsg_o, ri_o, ci_o)
    diff_o = dem_e_o - WMSC1_REG_M
    print(f'  {"WMSC1(old)":8s}  {4930:>6d}  {WMSC1_REG_M:>6.0f}  {dem_e_o:>6.0f}  '
          f'{dem_e_o*3.28084:>6.0f}  {diff_o:>+8.0f}  {margin_o:>11.1f}  '
          f'{"--":>7s}  INVALID (old DEM)')
    print(f'  {"WMSC1(new)":8s}  {4930:>6d}  {WMSC1_REG_M:>6.0f}  {dem_elev_new:>6.0f}  '
          f'{dem_elev_new*3.28084:>6.0f}  {diff_new:>+8.0f}  {margin_new:>11.1f}  '
          f'{pct_below:>7.0f}%  {"OK" if abs(diff_new)<=ELEV_TOL_M else "MISMATCH"}')

if not SCORING_OK:
    print()
    print('ELEVATION CHECK FAILED on new DEM — stopping as instructed.')
    print('The DEM source (USGS 3DEP) does not reach registry elevation at these coords.')
    sys.exit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: RE-RUN STAGE 2 WITH CORRECTED DEM
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*65)
print('STEP 4: STAGE 2 RE-RUN — WMSC1 with corrected DEM')
print(f'  BC: {LEVEL} hPa {HRRR_TIME}  |  DEM: {NEW_DEM_NAME}')
print('='*65)

# Observations (same as before)
fpath = os.path.join(RAWS, 'thomas_2017', 'WMSC1_thomas_2017.csv')
rows  = list(csv.DictReader(open(fpath, encoding='utf-8')))
window = [r for r in rows if r['datetime_utc'].startswith(RAWS_PREFIX)]
best   = max(window, key=lambda r: float(r.get('wind_gust_mph') or 0))
obs_gust = float(best.get('wind_gust_mph') or 0)
obs_spd  = float(best.get('wind_speed_mph') or 0)
obs_dir  = float(best.get('wind_dir_deg') or 0)
obs_time = best['datetime_utc']
conc_gf  = round(obs_gust / obs_spd, 3) if obs_spd > 0 else None  # concurrent-hour GF

print(f'  Peak-gust row in {RAWS_PREFIX} window:')
print(f'    {obs_time}: gust={obs_gust}mph  sustained={obs_spd}mph  dir={obs_dir}°')
print(f'    Concurrent-hour GF = {obs_gust}/{obs_spd} = {conc_gf}')
print(f'    (Pre-registered GF_CONC={GF_CONC} — spot check: {conc_gf})')

# HRRR BC + 10m
H_prs = Herbie(HRRR_TIME, model='hrrr', product='prs', fxx=0)
H_sfc = Herbie(HRRR_TIME, model='hrrr', product='sfc', fxx=0)
clat, clon = BC_CENTER
ds_u = H_prs.xarray(f'UGRD:{LEVEL} mb'); ds_v = H_prs.xarray(f'VGRD:{LEVEL} mb')
bc_spd, bc_dir = wind_from_uv(nearest(ds_u,'u',clat,clon), nearest(ds_v,'v',clat,clon))
ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
h10_spd, h10_dir = wind_from_uv(nearest(ds_u10,'u10',WMSC1_LAT,WMSC1_LON),
                                  nearest(ds_v10,'v10',WMSC1_LAT,WMSC1_LON))

print(f'\n  BC ({LEVEL} hPa): {bc_spd} mph @ {bc_dir:.1f}°')
print(f'  HRRR 10m at WMSC1: {h10_spd} mph @ {h10_dir:.1f}°')

# WN run with new DEM
print()
vel_path, ang_path = run_wn(NEW_DEM_NAME, bc_spd, bc_dir)
if vel_path is None:
    print('WN FAILED — cannot score'); sys.exit(1)

wn_pred = read_asc(vel_path, WMSC1_LAT, WMSC1_LON)
if wn_pred is None:
    print('ERROR: could not interpolate WN at WMSC1'); sys.exit(1)

print(f'  WN output at WMSC1: {wn_pred} mph (sustained)')

# ─── Results under all three GFs ──────────────────────────────────────────────
print()
print('='*65)
print('STEP 4 RESULTS — WMSC1 under all three GFs')
print(f'  BC: {bc_spd}mph @ {bc_dir:.1f}°  |  WN output: {wn_pred}mph  |  HRRR 10m: {h10_spd}mph')
print('='*65)
print(f'  {"GF source":20s}  {"GF":>5s}  {"ObsSus":>7s}  {"HRRRrat":>8s}  {"WNrat":>7s}  '
      f'{"HRRR in-band":>13s}  {"WN in-band":>11s}  {"WN>HRRR":>8s}')
print('-'*85)

gf_results = {}
for label, gf in [('median (pre-reg)',GF_MEDIAN), ('concurrent-hr',GF_CONC), ('peak-moment',GF_PEAK)]:
    obs_sus = obs_gust / gf
    h_rat   = round(h10_spd / obs_sus, 3)
    wn_rat  = round(wn_pred  / obs_sus, 3)
    h_band  = 'in-band ✓' if PASS_LO<=h_rat<=PASS_HI else 'out ✗'
    wn_band = 'in-band ✓' if PASS_LO<=wn_rat<=PASS_HI else 'out ✗'
    wn_beats= abs(wn_rat-1) < abs(h_rat-1)
    print(f'  {label:20s}  {gf:>5.3f}  {obs_sus:>7.1f}  {h_rat:>8.3f}  {wn_rat:>7.3f}  '
          f'{h_band:>13s}  {wn_band:>11s}  {"YES" if wn_beats else "NO":>8s}')
    gf_results[label] = {'gf':gf,'obs_sus':obs_sus,'h_rat':h_rat,'wn_rat':wn_rat,
                         'wn_band':PASS_LO<=wn_rat<=PASS_HI,'wn_beats':wn_beats}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: UPDATED CROSS-EVENT TABLE
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*65)
print('STEP 5: CROSS-EVENT TABLE (corrected WMSC1 row)')
print('  Pass band [0.80, 1.20].  (*) = held-out.')
print('='*65)
print(f'{"Event":8s}  {"Sta":9s}  {"Elev":7s}  {"Terrain":16s}  '
      f'{"HRRRrat":>8s}  {"WNrat":>7s}  {"WN>HRRR":>8s}  {"InBand":>7s}  Note')
print('-'*95)

prior = [
    ('Camp',    'CBXC1(*)', '6004 ft', 'exposed ridge',   0.869, 1.007, 'held-out confirmed'),
    ('Camp',    'SLEC1(*)', '6670 ft', 'exposed ridge',   0.525, 1.128, 'held-out confirmed'),
    ('Camp',    'JBGC1',   '1850 ft', 'canyon/gap',       0.519, 0.771, 'excluded (canyon)'),
    ('Kincade', 'KNXC1',   '2200 ft', 'valley',           None,  2.003, 'unresolved overshoot'),
]
for ev, stid, elev, terr, hr, wr, note in prior:
    wn_b = ('YES' if (hr and wr and abs(wr-1)<abs(hr-1)) else
            'N/A' if hr is None else 'NO')
    inb  = ('✓' if wr and PASS_LO<=wr<=PASS_HI else '✗') if wr else '—'
    hr_s = f'{hr:.3f}' if hr is not None else '—'
    wr_s = f'{wr:.3f}' if wr is not None else '—'
    print(f'{ev:8s}  {stid:9s}  {elev:7s}  {terr:16s}  '
          f'{hr_s:>8s}  {wr_s:>7s}  {wn_b:>8s}  {inb:>7s}  {note}')

# Thomas WMSC1 — use median GF for table
res_med = gf_results['median (pre-reg)']
wn_b_t  = 'YES' if res_med['wn_beats'] else 'NO'
inb_t   = '✓' if res_med['wn_band'] else '✗'
print(f'{"Thomas":8s}  {"WMSC1":9s}  {"4930 ft":7s}  {"high slope/ridge":16s}  '
      f'{res_med["h_rat"]:>8.3f}  {res_med["wn_rat"]:>7.3f}  '
      f'{wn_b_t:>8s}  {inb_t:>7s}  DEM fixed; GF=1.560 median')

print()
print('GF sensitivity (WMSC1 only):')
for label, res in gf_results.items():
    print(f'  {label:20s}  GF={res["gf"]:.3f}  obs_sus={res["obs_sus"]:.1f}  '
          f'WN={res["wn_rat"]:.3f}  HRRR={res["h_rat"]:.3f}  '
          f'WN_in-band={"YES" if res["wn_band"] else "NO"}')

print()
print('Write nothing to master status — show human first.')
