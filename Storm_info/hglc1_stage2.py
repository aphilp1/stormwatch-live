"""
hglc1_stage2.py  —  HGLC1 Kincade run cross-event ridge test
Pre-registration: committed 316d1bc, 2026-05-31

Steps (STOP at first gate failure, no goalpost moves):
  Gate A: Download DEM centered on HGLC1 (39.209N,-122.810W), 16mi, geographic.
           Verify DEM elev at coords within +-50m of registry 4807ft (1465.2m).
           Confirm margin >=2km. STOP if fails.
  Gate B: Real circular R [0,1] for HGLC1 directions at the peak-window hour and
           the surrounding event period (Oct 27, spd>=10mph).
  Gate C: BC direction check — 850 hPa 11Z 2019-10-27 at HGLC1 grid cell
           (39.21N,-122.81W). Must be within 30deg of HGLC1 obs at 11Z window
           (pre-registered obs direction = 359deg). STOP if fails.
  Score:  WN+rawBC at HGLC1 coords. Report ratio under all three GFs.
          Also report raw HRRR 10m ratio.

Pre-registered parameters:
  Peak:         2019-10-27T11:36Z, 24.0 mph @ 359 deg, 51.0 mph gust
  RAWS prefix:  '2019-10-27T11'
  BC center:    (39.21N, -122.81W)
  BC level/hr:  850 hPa, 11Z 2019-10-27
  GF median:    1.998 (own empirical, status OK, 48 pairs)
  obs_sus_est:  51.0 / 1.998 = 25.5 mph
"""

import sys, os, math, csv, requests, subprocess, glob as _glob, time
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

os.environ['PATH'] = (
    r'C:\Users\aphil\miniforge3\envs\hrrr311' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\mingw-w64\bin' + os.pathsep +
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

# ── Pre-registered constants (do not change after commit 316d1bc) ─────────────
HGLC1_LAT      = 39.208900
HGLC1_LON      = -122.809990
HGLC1_REG_FT   = 4807.0
HGLC1_REG_M    = 1465.2
PRE_PEAK_SPD   = 24.0      # locked from CSV
PRE_PEAK_GUST  = 51.0      # locked
PRE_PEAK_DIR   = 359.0     # locked
PRE_PEAK_TIME  = '2019-10-27T11:36Z'
RAWS_PREFIX    = '2019-10-27T11'
HRRR_TIME      = '2019-10-27 11:00'
LEVEL          = 850
BC_LAT, BC_LON = 39.21, -122.81
GF_MEDIAN      = 1.998
GF_PEAK_OWN    = 2.125     # 51.0/24.0 concurrent at peak
OBS_SUS_EST_M  = round(PRE_PEAK_GUST / GF_MEDIAN, 2)   # 25.5 mph

DEM_NAME = 'dem_39.21_-122.81_16mi_hglc1.tif'
DEM_PATH = os.path.join(CACHE, DEM_NAME)
EXTENT_MI = 16
EXTENT_KM = EXTENT_MI * 1.60934
ELEV_TOL  = 50.0
PASS_LO, PASS_HI = 0.80, 1.20

def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def wind_from_uv(u, v):
    spd  = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def nearest(ds, var, lat, lon):
    lats = ds['latitude'].values; lons = ds['longitude'].values % 360
    dist = np.sqrt((lats-lat)**2 + (lons-lon%360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

def load_dem(path):
    img = Image.open(path)
    t   = img.tag_v2
    Sx  = float(t[33550][0]); Sy = float(t[33550][1])
    x0  = float(t[33922][3]); y0 = float(t[33922][4])
    geo = str(t.get(34737, ''))
    arr = np.array(img, dtype=float)
    for nd in [-9999, 9999, 32767, -32768]:
        arr[np.abs(arr - nd) < 1] = np.nan
    if abs(x0) < 360:
        epsg = 4326
    elif 'zone 10N' in geo:
        epsg = 32610
    elif 'zone 11N' in geo:
        epsg = 32611
    else:
        epsg = 32610
    return arr, Sx, Sy, x0, y0, epsg, img.size[0], img.size[1], geo

def dem_at(arr, Sx, Sy, x0, y0, epsg, ncols, nrows, lat, lon):
    if epsg == 4326:
        col = (lon - x0) / Sx; row = (y0 - lat) / Sy
    else:
        tf = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
        x, y = tf.transform(lon, lat)
        col = (x - x0) / Sx; row = (y0 - y) / Sy
    ci = int(round(col)); ri = int(round(row))
    in_b = 0 <= ci < ncols and 0 <= ri < nrows
    ci = max(0, min(ci, ncols-1)); ri = max(0, min(ri, nrows-1))
    elev = float(arr[ri, ci]) if not np.isnan(arr[ri, ci]) else None
    px_m = Sx if epsg != 4326 else Sx*111000*math.cos(math.radians(lat))
    margin = min(ri, nrows-1-ri, ci, ncols-1-ci) * px_m / 1000
    return elev, margin, ri, ci, in_b, px_m

def run_wn(dem_name, speed, direction):
    dem  = os.path.join(CACHE, dem_name)
    stem = os.path.splitext(dem_name)[0]
    si, di = int(round(speed)), int(round(direction))
    cached = _glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    if cached:
        ang = _glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
        print(f'  [cached] {dem_name} {si}mph@{di}°')
        return cached[0], (ang[0] if ang else None)
    print(f'  WN {dem_name} {si}mph@{di}°...', end=' ', flush=True)
    args = [WN,'--num_threads','6','--elevation_file',dem,
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
        print(f'  WN ERROR: {res.stderr[-300:]}'); return None, None
    vel = _glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    ang = _glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
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
print('='*65)
print('HGLC1 — KINCADE RUN CROSS-EVENT RIDGE TEST')
print(f'Pre-registration: 316d1bc | Peak: {PRE_PEAK_TIME}')
print(f'24.0 mph @ 359° | 51.0 gust | GF_med={GF_MEDIAN} | obs_sus={OBS_SUS_EST_M} mph')
print('='*65)

# ═══ GATE A: DEM DOWNLOAD + ELEVATION VERIFY ══════════════════════════════════
print()
print('── GATE A: DEM ─────────────────────────────────────────────────────────')

if os.path.exists(DEM_PATH):
    print(f'  DEM exists: {DEM_NAME}')
else:
    buf_lat = (EXTENT_KM/2)/111.0
    buf_lon = (EXTENT_KM/2)/(111.0*math.cos(math.radians(HGLC1_LAT)))
    xmin = HGLC1_LON - buf_lon; xmax = HGLC1_LON + buf_lon
    ymin = HGLC1_LAT - buf_lat; ymax = HGLC1_LAT + buf_lat
    bbox = f'{xmin:.4f},{ymin:.4f},{xmax:.4f},{ymax:.4f}'
    margin_lat = (EXTENT_KM/2) - abs(HGLC1_LAT - (ymin+ymax)/2)*111
    margin_lon = (EXTENT_KM/2) - abs(HGLC1_LON - (xmin+xmax)/2)*111*math.cos(math.radians(HGLC1_LAT))
    print(f'  Downloading: {EXTENT_MI}mi centered {HGLC1_LAT}N,{HGLC1_LON}W')
    print(f'  Domain: {bbox}')
    print(f'  HGLC1 margins: lat={margin_lat:.1f}km lon={margin_lon:.1f}km (min should be >{EXTENT_KM/2-1:.0f}km)')
    url = ('https://elevation.nationalmap.gov/arcgis/rest/services/'
           '3DEPElevation/ImageServer/exportImage')
    r = requests.get(url, params={
        'bbox':bbox,'bboxSR':'4326','size':'1024,1024','imageSR':'4326',
        'format':'tiff','pixelType':'F32','noDataInterpretation':'esriNoDataMatchAny',
        'interpolation':'+RSP_BilinearInterpolation','f':'image'},
        timeout=120)
    ct = r.headers.get('content-type','?')
    print(f'  HTTP {r.status_code}  type={ct}  bytes={len(r.content):,}')
    if r.status_code==200 and len(r.content)>10000 and 'tiff' in ct.lower():
        with open(DEM_PATH,'wb') as f: f.write(r.content)
        print(f'  Saved → {DEM_PATH}  ({len(r.content)//1024}KB)')
    else:
        print(f'  DOWNLOAD FAILED — {r.text[:200]}'); sys.exit(1)

arr,Sx,Sy,x0,y0,epsg,ncols,nrows,geo_str = load_dem(DEM_PATH)
elev,margin,ri,ci,in_b,px_m = dem_at(arr,Sx,Sy,x0,y0,epsg,ncols,nrows,HGLC1_LAT,HGLC1_LON)
diff = (elev - HGLC1_REG_M) if elev is not None else None

# 1km neighborhood
r_px = max(1, int(1000/px_m))
r0=max(0,ri-r_px); r1=min(nrows,ri+r_px+1)
c0=max(0,ci-r_px); c1=min(ncols,ci+r_px+1)
nbr = arr[r0:r1,c0:c1].flatten(); nbr=nbr[~np.isnan(nbr)]
pct_below = (nbr < elev).sum()/len(nbr)*100 if len(nbr)>0 else 0

print(f'  CRS: {geo_str[:60]} (EPSG:{epsg})')
print(f'  DEM shape: {nrows}×{ncols}  pixel ~{px_m:.0f}m')
print(f'  HGLC1 pixel: ({ri},{ci})  in_bounds={in_b}')
print(f'  DEM elev: {elev:.1f}m ({elev*3.28084:.0f}ft)  registry: {HGLC1_REG_M}m ({HGLC1_REG_FT:.0f}ft)  diff={diff:+.1f}m')
print(f'  Margin to edge: {margin:.1f}km')
print(f'  1km neighborhood: max={np.nanmax(nbr):.0f}m  pct_below={pct_below:.0f}%')

gate_a_elev = abs(diff) <= ELEV_TOL if diff is not None else False
gate_a_margin = margin >= 2.0
gate_a = gate_a_elev and gate_a_margin

print(f'  Gate A elevation (±{ELEV_TOL}m): {"✓ PASS" if gate_a_elev else "✗ FAIL"}')
print(f'  Gate A margin (≥2km):            {"✓ PASS" if gate_a_margin else "✗ FAIL"}')

if not gate_a:
    print()
    if not gate_a_margin:
        print('GATE A FAIL — margin too small. New DEM needed.')
    else:
        print(f'GATE A FAIL — elev mismatch {diff:+.1f}m > ±{ELEV_TOL}m.')
        print(f'  DEM max in 1km = {np.nanmax(nbr):.0f}m vs registry {HGLC1_REG_M:.0f}m.')
        print('  STOPPING as instructed.')
    sys.exit(0)

# ═══ GATE B: CIRCULAR R (direction steadiness) ════════════════════════════════
print()
print('── GATE B: DIRECTION STEADINESS (real circular R) ──────────────────────')

fpath = os.path.join(RAWS,'kincade_run_2019','HGLC1_kincade_run_2019.csv')
rows  = list(csv.DictReader(open(fpath, encoding='utf-8')))

# Oct 27 event period, spd >= 10 mph
event_dirs = []
for r in rows:
    t = r['datetime_utc']
    if '2019-10-27' not in t: continue
    try:
        spd  = float(r.get('wind_speed_mph') or 0)
        dirn = float(r.get('wind_dir_deg') or 0)
        if spd >= 10 and dirn > 0:
            event_dirs.append((t[:16], spd, dirn))
    except: pass

# True circular R: use UNIT direction vectors (not speed-weighted)
sin_m = np.mean([math.sin(math.radians(d)) for _,_,d in event_dirs])
cos_m = np.mean([math.cos(math.radians(d)) for _,_,d in event_dirs])
circ_R = math.sqrt(sin_m**2 + cos_m**2)
mean_dir = math.degrees(math.atan2(sin_m, cos_m)) % 360

# Peak window obs
peak_window = [r for r in rows if r['datetime_utc'].startswith(RAWS_PREFIX)]
if peak_window:
    pr = peak_window[0]
    pw_spd  = float(pr.get('wind_speed_mph') or 0)
    pw_gust = float(pr.get('wind_gust_mph') or 0)
    pw_dir  = float(pr.get('wind_dir_deg') or 0)
    pw_time = pr['datetime_utc']
else:
    pw_spd = pw_gust = pw_dir = 0; pw_time = 'NOT FOUND'

print(f'  Oct 27 event obs (spd≥10mph, n={len(event_dirs)}):')
for t,s,d in event_dirs:
    flag = ' <-- PRE-REG PEAK WINDOW' if t.startswith('2019-10-27T11') else ''
    print(f'    {t}Z  {s:5.1f}mph  {d:5.0f}°{flag}')
print()
print(f'  True circular R = {circ_R:.4f}  (1.0=perfectly steady, 0=random)')
print(f'  Vector-mean direction = {mean_dir:.1f}°')
print(f'  Circular std dev ≈ {math.degrees(math.sqrt(-2*math.log(circ_R))):.1f}° '
      f'(approx, valid for R>0.5)')
print()
print(f'  Peak window obs ({RAWS_PREFIX}):')
print(f'    {pw_time}: {pw_spd} mph @ {pw_dir}° | gust {pw_gust} mph')
# Verify peak matches pre-registration
ok_peak = (abs(pw_spd - PRE_PEAK_SPD) < 0.1 and abs(pw_gust - PRE_PEAK_GUST) < 0.1
           and abs(pw_dir - PRE_PEAK_DIR) < 1)
print(f'  Pre-reg match (24.0/{PRE_PEAK_GUST}/{PRE_PEAK_DIR}°): {"✓" if ok_peak else "*** MISMATCH"}')
if not ok_peak:
    print(f'  WARNING: peak obs does not match pre-registration. Check CSV.')
# No hard gate on R here — just report. The direction Δ gate is Gate C.

# ═══ GATE C: BC DIRECTION CHECK ═══════════════════════════════════════════════
print()
print('── GATE C: BC DIRECTION CHECK ──────────────────────────────────────────')
print(f'  Fetching HRRR {LEVEL} hPa + 10m at {HRRR_TIME}...')

H_prs = Herbie(HRRR_TIME, model='hrrr', product='prs', fxx=0)
H_sfc = Herbie(HRRR_TIME, model='hrrr', product='sfc', fxx=0)

ds_u = H_prs.xarray(f'UGRD:{LEVEL} mb'); ds_v = H_prs.xarray(f'VGRD:{LEVEL} mb')
bc_spd, bc_dir = wind_from_uv(nearest(ds_u,'u',BC_LAT,BC_LON),
                               nearest(ds_v,'v',BC_LAT,BC_LON))
ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
h10_spd, h10_dir = wind_from_uv(nearest(ds_u10,'u10',HGLC1_LAT,HGLC1_LON),
                                  nearest(ds_v10,'v10',HGLC1_LAT,HGLC1_LON))

delta = ang_diff(bc_dir, pw_dir)
gate_c = delta <= 30.0

print(f'  BC  ({LEVEL} hPa at {BC_LAT}N,{BC_LON}W): {bc_spd} mph @ {bc_dir:.1f}°')
print(f'  HRRR 10m at HGLC1: {h10_spd} mph @ {h10_dir:.1f}°')
print(f'  HGLC1 obs at {RAWS_PREFIX}: {pw_spd} mph @ {pw_dir}°')
print(f'  BC dir vs obs dir: {bc_dir:.1f}° vs {pw_dir:.0f}° → Δ={delta:.1f}°')
print(f'  Gate C (Δ≤30°): {"✓ PASS" if gate_c else "✗ FAIL"}')

if not gate_c:
    print()
    print('GATE C FAIL — BC direction mismatch. STOPPING as instructed.')
    sys.exit(0)

# ═══ SCORE ════════════════════════════════════════════════════════════════════
print()
print('── ALL GATES PASSED — RUNNING WN ───────────────────────────────────────')
print(f'  BC: {bc_spd}mph @ {bc_dir:.0f}°  DEM: {DEM_NAME}')

vel_path, ang_path = run_wn(DEM_NAME, bc_spd, bc_dir)
if vel_path is None:
    print('WN FAILED — cannot score'); sys.exit(1)

wn_pred = read_asc(vel_path, HGLC1_LAT, HGLC1_LON)
if wn_pred is None:
    print('ERROR: WN output not interpolated at HGLC1 coords'); sys.exit(1)

print(f'  WN output at HGLC1: {wn_pred} mph (sustained)')

# ─── Results under all three GFs ──────────────────────────────────────────────
print()
print('='*65)
print('HGLC1 RESULTS — all three GF variants')
print(f'BC: {bc_spd}mph@{bc_dir:.0f}°  WN: {wn_pred}mph  HRRR10m: {h10_spd}mph')
print(f'Obs gust: {pw_gust}mph  Obs sustained: {pw_spd}mph  Dir: {pw_dir}°')
print('='*65)

# Concurrent GF (actual obs at peak)
gf_conc = round(pw_gust / pw_spd, 3) if pw_spd > 0 else None
print(f'  {"GF source":22s}  {"GF":>5s}  {"ObsSus":>7s}  '
      f'{"HRRRrat":>8s}  {"WNrat":>7s}  {"WN in-band":>11s}  {"WN>HRRR":>8s}')
print('-'*80)

gf_results = {}
for label, gf in [('median (pre-reg)', GF_MEDIAN),
                   ('concurrent-hr',   gf_conc),
                   ('peak-own (2.125)', GF_PEAK_OWN)]:
    if gf is None: continue
    obs_sus = pw_gust / gf
    h_rat   = round(h10_spd / obs_sus, 3)
    wn_rat  = round(wn_pred  / obs_sus, 3)
    h_band  = '✓' if PASS_LO<=h_rat<=PASS_HI else '✗'
    wn_band = '✓' if PASS_LO<=wn_rat<=PASS_HI else '✗'
    wn_b    = abs(wn_rat-1) < abs(h_rat-1)
    print(f'  {label:22s}  {gf:>5.3f}  {obs_sus:>7.1f}  '
          f'{h_rat:>8.3f}{h_band}  {wn_rat:>7.3f}{wn_band}  '
          f'{"in-band ✓" if PASS_LO<=wn_rat<=PASS_HI else "out ✗":>11s}  '
          f'{"YES" if wn_b else "NO":>8s}')
    gf_results[label] = {'gf':gf,'obs_sus':obs_sus,'h_rat':h_rat,'wn_rat':wn_rat,
                         'wn_band':PASS_LO<=wn_rat<=PASS_HI,'wn_beats':wn_b}

# ─── Cross-event table ─────────────────────────────────────────────────────────
print()
print('='*65)
print('CROSS-EVENT TABLE (updated with HGLC1)')
print('Pass band [0.80, 1.20]. (*) = held-out. (+) = peak-window scored.')
print('='*65)
print(f'{"Event":8s}  {"Sta":9s}  {"Elev":7s}  {"Terrain":16s}  '
      f'{"HRRRrat":>8s}  {"WNrat":>7s}  {"WN>HRRR":>8s}  {"InBand":>7s}  Note')
print('-'*92)

PRIOR = [
    ('Camp',    'CBXC1(*)', '6004ft', 'exposed ridge',   0.869, 1.007, 'held-out confirmed'),
    ('Camp',    'SLEC1(*)', '6670ft', 'exposed ridge',   0.525, 1.128, 'held-out confirmed'),
    ('Camp',    'JBGC1',   '1850ft', 'canyon/gap',       0.519, 0.771, 'excluded (canyon)'),
    ('Kincade', 'KNXC1',   '2200ft', 'valley',           None,  2.003, 'unresolved overshoot'),
]
for ev,stid,elev,terr,hr,wr,note in PRIOR:
    wn_b = ('YES' if hr and wr and abs(wr-1)<abs(hr-1) else
            'N/A' if hr is None else 'NO')
    inb  = ('✓' if wr and PASS_LO<=wr<=PASS_HI else '✗') if wr else '—'
    print(f'{ev:8s}  {stid:9s}  {elev:7s}  {terr:16s}  '
          f'{str(hr) if hr else "—":>8s}  {wr:.3f if wr else "—":>7}  '
          f'{wn_b:>8s}  {inb:>7s}  {note}')

# HGLC1 row using median GF
res = gf_results.get('median (pre-reg)', {})
h_r = res.get('h_rat'); wn_r = res.get('wn_rat')
wn_b_h = 'YES' if res.get('wn_beats') else 'NO'
inb_h  = '✓' if res.get('wn_band') else '✗'
print(f'{"Kincade":8s}  {"HGLC1(+)":9s}  {"4807ft":7s}  {"USFS lookout":16s}  '
      f'{h_r if h_r else "—":>8}  {wn_r if wn_r else "—":>7}  '
      f'{wn_b_h:>8s}  {inb_h:>7s}  peak-window (11Z); GF=1.998 median')

print()
print('GF sensitivity (HGLC1):')
for label, res in gf_results.items():
    print(f'  {label:22s}  GF={res["gf"]:.3f}  obs_sus={res["obs_sus"]:.1f}  '
          f'WN={res["wn_rat"]:.3f}  HRRR={res["h_rat"]:.3f}  '
          f'WN_in-band={"YES" if res["wn_band"] else "NO"}')

print()
print('DEM verification summary:')
print(f'  HGLC1: DEM {elev:.0f}m ({elev*3.28084:.0f}ft) vs registry {HGLC1_REG_M:.0f}m ({HGLC1_REG_FT:.0f}ft)  diff={diff:+.1f}m  margin={margin:.1f}km')
print(f'  CRS: {geo_str[:50]} (EPSG:{epsg}) — '
      f'{"Zone 10N correct for lon {:.0f}W".format(abs(HGLC1_LON)) if epsg in (4326,32610) else "*** CHECK CRS"}')
print()
print('Write nothing to master status — show human first.')
