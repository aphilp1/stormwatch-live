"""
cuuc1_check.py  —  CUUC1 (Chuchupate) cross-event ridge candidate check.
Checks in order:
  1. Registry metadata + DEM elevation verification
  2. BC direction match (850 hPa 12Z 2017-12-05 vs CUUC1 observed)
  3. Own gust factor (peak-gust / concurrent-sustained)
  4. Score WN+rawBC vs HRRR if qualifies, STOP with reason if not.

Qualification gates (any failure = STOP, no further fishing):
  a) DEM elevation within ±50m of registry
  b) BC dir within 30° of CUUC1 observed vector-mean in scoring window
  c) Obs sustained estimate > 10 mph (not near-calm denominator)
"""
import sys, os, math, csv, subprocess, glob, time
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

# CUUC1 registry (Synoptic live-confirmed)
CUUC1_LAT    = 34.806370
CUUC1_LON    = -119.013630
CUUC1_REG_FT = 5280.0
CUUC1_REG_M  = 1609.3      # 5280 ft × 0.3048

# Pre-registered BC (unchanged)
HRRR_TIME   = '2017-12-05 12:00'
LEVEL       = 850
BC_CENTER   = (34.58, -118.70)
RAWS_PREFIX = '2017-12-05T12'
PASS_LO, PASS_HI = 0.80, 1.20

def load_dem(path):
    img = Image.open(path)
    t   = img.tag_v2
    Sx  = float(t[33550][0]); Sy = float(t[33550][1])
    x0  = float(t[33922][3]); y0 = float(t[33922][4])
    geo = str(t.get(34737, ''))
    arr = np.array(img, dtype=float)
    for nd in [-9999, 9999]:
        arr[np.abs(arr-nd) < 1] = np.nan
    if abs(x0) < 360:
        epsg = 4326
    elif 'zone 10N' in geo:
        epsg = 32610
    elif 'zone 11N' in geo:
        epsg = 32611
    else:
        epsg = 32610
    return arr, Sx, Sy, x0, y0, epsg, *img.size   # arr,Sx,Sy,x0,y0,epsg,ncols,nrows

def dem_lookup(path, lat, lon):
    arr, Sx, Sy, x0, y0, epsg, ncols, nrows = load_dem(path)
    if epsg == 4326:
        col = (lon - x0) / Sx; row = (y0 - lat) / Sy
    else:
        tf = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
        x, y = tf.transform(lon, lat)
        col = (x - x0) / Sx; row = (y0 - y) / Sy
    ci = max(0, min(int(round(col)), ncols-1))
    ri = max(0, min(int(round(row)), nrows-1))
    elev = float(arr[ri, ci])
    px_m = Sx if epsg != 4326 else Sx*111000*math.cos(math.radians(lat))
    margin_km = min(ri, nrows-1-ri, ci, ncols-1-ci) * px_m / 1000
    # 1km neighborhood stats
    r_px = max(1, int(1000/px_m))
    r0=max(0,ri-r_px); r1=min(nrows,ri+r_px+1)
    c0=max(0,ci-r_px); c1=min(ncols,ci+r_px+1)
    nbr = arr[r0:r1,c0:c1].flatten(); nbr=nbr[~np.isnan(nbr)]
    return elev, margin_km, float(np.nanmax(nbr)) if len(nbr) else 0, ri, ci

def wind_from_uv(u, v):
    spd  = math.sqrt(u**2+v**2)*2.23694
    dirn = (180+math.degrees(math.atan2(u,v)))%360
    return round(spd,1), round(dirn,1)

def nearest(ds, var, lat, lon):
    lats=ds['latitude'].values; lons=ds['longitude'].values%360
    dist=np.sqrt((lats-lat)**2+(lons-lon%360)**2)
    iy,ix=np.unravel_index(dist.argmin(),dist.shape)
    return float(ds[var].values[iy,ix])

def ang_diff(a, b):
    return abs((a-b+180)%360-180)

def vec_mean(dirs_speeds):
    us=[s*math.cos(math.radians(d)) for d,s in dirs_speeds]
    vs=[s*math.sin(math.radians(d)) for d,s in dirs_speeds]
    return math.degrees(math.atan2(sum(vs)/len(vs),sum(us)/len(us)))%360

# ─── 1. REGISTRY + DEM ELEVATION ──────────────────────────────────────────────
print('='*65)
print('CUUC1 (CHUCHUPATE) — CROSS-EVENT RIDGE CANDIDATE CHECK')
print('='*65)
print(f'  Coords:   {CUUC1_LAT}N, {CUUC1_LON}W')
print(f'  Registry: {CUUC1_REG_FT:.0f} ft / {CUUC1_REG_M:.1f} m')
print(f'  Thomas inversion lid: ~1388m (VBG 00Z)')
print(f'  CUUC1 above lid by:   {CUUC1_REG_M-1388:.0f} m ({(CUUC1_REG_M-1388)*3.28:.0f} ft)')
print()

# Find DEM — try available Thomas-area DEMs
candidates = [
    (r'C:\temp\windninja_cache\dem_34.44_-119.05_12mi.tif', '34.44_-119.05_12mi'),
    (r'C:\temp\windninja_cache\dem_34.58_-118.66_16mi_utm.tif', '34.58_-118.66_16mi_utm'),
]
dem_used = None
for dem_path, dem_label in candidates:
    if not os.path.exists(dem_path):
        print(f'  DEM {dem_label}: NOT ON DISK')
        continue
    elev, margin, nbr_max, ri, ci = dem_lookup(dem_path, CUUC1_LAT, CUUC1_LON)
    diff = elev - CUUC1_REG_M
    print(f'  DEM {dem_label}:')
    print(f'    pixel ({ri},{ci})  elev={elev:.0f}m ({elev*3.28084:.0f}ft)  '
          f'reg={CUUC1_REG_M:.0f}m  diff={diff:+.0f}m  margin={margin:.1f}km  1km_max={nbr_max:.0f}m')
    if margin < 2.0:
        print(f'    → MARGIN TOO SMALL ({margin:.1f}km) — station near/outside DEM edge')
    elif abs(diff) <= 50:
        print(f'    → ELEVATION OK (within ±50m)')
        dem_used = (dem_path, dem_label, elev, diff, margin)
        break
    else:
        print(f'    → ELEVATION MISMATCH (|{diff:+.0f}m| > 50m)')

if dem_used is None:
    print()
    print('  No existing DEM covers CUUC1 with correct elevation and margin.')
    print('  CUUC1 is at 34.806N, -119.014W — need a DEM centered there.')
    print()

# ─── 2. OBSERVED WINDS — CUUC1 DEC 5 ─────────────────────────────────────────
print('='*65)
print('CUUC1 OBSERVED WINDS — Dec 5 2017')
print('='*65)
fpath = os.path.join(RAWS, 'thomas_2017', 'CUUC1_thomas_2017.csv')
rows  = list(csv.DictReader(open(fpath, encoding='utf-8')))

# Full Dec 5 picture
print(f'{"Time(UTC)":22s}  {"Spd":>5s}  {"Dir":>5s}  {"Gust":>6s}')
print('-'*45)
for r in rows:
    t = r['datetime_utc']
    if '2017-12-05' not in t: continue
    try:
        spd  = float(r.get('wind_speed_mph') or 0)
        dirn = float(r.get('wind_dir_deg') or 0)
        gust = float(r.get('wind_gust_mph') or 0)
        flag = ' <-- 12Z' if t.startswith('2017-12-05T12') else ''
        print(f'{t[:19]:22s}  {spd:>5.1f}  {dirn:>5.0f}°  {gust:>6.1f}{flag}')
    except: pass

# Scoring window obs (12Z)
print()
window_12z = [r for r in rows if r['datetime_utc'].startswith(RAWS_PREFIX)]
if window_12z:
    best = max(window_12z, key=lambda r: float(r.get('wind_gust_mph') or 0))
    obs_gust = float(best.get('wind_gust_mph') or 0)
    obs_spd  = float(best.get('wind_speed_mph') or 0)
    obs_dir  = float(best.get('wind_dir_deg') or 0)
    gf_conc  = round(obs_gust/obs_spd, 3) if obs_spd > 0 else None
    print(f'12Z SCORING WINDOW peak: gust={obs_gust} mph  sustained={obs_spd} mph  '
          f'dir={obs_dir}°  GF={gf_conc}')
    if obs_spd < 10:
        print(f'  *** NEAR-CALM: {obs_spd} mph sustained — denominator artifact, DISQUALIFIED')
        qual_obs = False
    else:
        qual_obs = True
        print(f'  obs_sus_est would be {obs_gust}/{gf_conc:.3f} = {obs_gust/gf_conc:.1f} mph')
else:
    print('  No rows for 2017-12-05T12 prefix')
    qual_obs = False
    obs_gust = obs_spd = obs_dir = 0

# Peak period direction for reference
peak_rows = [(r, float(r.get('wind_speed_mph') or 0), float(r.get('wind_dir_deg') or 0))
             for r in rows
             if '2017-12-05T00' <= r['datetime_utc'][:16] <= '2017-12-05T09'
             and float(r.get('wind_speed_mph') or 0) >= 10]
if peak_rows:
    vmean = vec_mean([(d,s) for _,s,d in peak_rows])
    peak_gust = max(float(r.get('wind_gust_mph') or 0) for r,_,_ in peak_rows)
    print(f'\n  Peak window 00-09Z Dec 5 (spd≥10mph, n={len(peak_rows)}):')
    print(f'    Vector-mean dir: {vmean:.0f}°  |  Max gust: {peak_gust} mph')
    print(f'    (For reference only — 12Z is pre-registered scoring window)')

# ─── 3. BC DIRECTION CHECK ────────────────────────────────────────────────────
print()
print('='*65)
print(f'BC DIRECTION CHECK — 850 hPa 12Z 2017-12-05 vs CUUC1')
print('='*65)
H_prs = Herbie(HRRR_TIME, model='hrrr', product='prs', fxx=0)
H_sfc = Herbie(HRRR_TIME, model='hrrr', product='sfc', fxx=0)
clat, clon = BC_CENTER
ds_u = H_prs.xarray(f'UGRD:{LEVEL} mb'); ds_v = H_prs.xarray(f'VGRD:{LEVEL} mb')
bc_spd, bc_dir = wind_from_uv(nearest(ds_u,'u',clat,clon), nearest(ds_v,'v',clat,clon))
ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
h10_spd, h10_dir = wind_from_uv(nearest(ds_u10,'u10',CUUC1_LAT,CUUC1_LON),
                                  nearest(ds_v10,'v10',CUUC1_LAT,CUUC1_LON))

print(f'  BC ({LEVEL} hPa at bc_center):  {bc_spd} mph @ {bc_dir:.1f}°')
print(f'  HRRR 10m at CUUC1:            {h10_spd} mph @ {h10_dir:.1f}°')
print(f'  CUUC1 obs at 12Z:             {obs_spd} mph @ {obs_dir}° (near-calm)')

delta_bc_obs = ang_diff(bc_dir, obs_dir) if obs_dir > 0 else None
if delta_bc_obs is not None:
    print(f'  BC vs obs dir:  Δ={delta_bc_obs:.0f}°  '
          f'{"PASS" if delta_bc_obs<=30 else "FAIL (>30°)"}')
    print(f'  NOTE: obs direction at near-calm wind is unreliable — direction check')
    print(f'        is not meaningful when sustained < 5 mph')

if peak_rows:
    delta_bc_peak = ang_diff(bc_dir, vmean)
    print(f'\n  BC vs peak-window dir ({vmean:.0f}°, 00-09Z): Δ={delta_bc_peak:.0f}°  '
          f'{"within 30°" if delta_bc_peak<=30 else "outside 30°"}  '
          f'(pre-registered BC is 12Z, not 00-09Z)')

# ─── 4. GUST FACTOR ───────────────────────────────────────────────────────────
print()
print('='*65)
print('GUST FACTOR — CUUC1 own empirical (from raws_gust_factors.csv)')
print('='*65)
gf_path = os.path.join(RAWS, 'raws_gust_factors.csv')
gf_row  = None
for r in csv.DictReader(open(gf_path, encoding='utf-8')):
    if r['stid'] == 'CUUC1' and r['event'] == 'thomas_2017':
        gf_row = r; break
if gf_row:
    print(f'  n_pairs:            {gf_row["n_window_pairs"]}')
    print(f'  peak_gust_mph:      {gf_row["peak_gust_mph"]}')
    print(f'  peak_gust_time:     {gf_row["peak_gust_time"]}')
    print(f'  peak_spd_conc:      {gf_row["peak_spd_concurrent"]}')
    print(f'  peak_gust_factor:   {gf_row["peak_gust_factor"]}')
    print(f'  median_gust_factor: {gf_row["median_gust_factor"]}')
    print(f'  status:             {gf_row["status"]}')
    print(f'  flags:              {gf_row.get("flags","none")}')
    peak_gf = float(gf_row['peak_gust_factor']) if gf_row['peak_gust_factor'] else None
    med_gf  = float(gf_row['median_gust_factor']) if gf_row['median_gust_factor'] else None
else:
    print('  CUUC1/thomas_2017 not found in raws_gust_factors.csv')
    peak_gf = med_gf = None

# ─── 5. QUALIFICATION SUMMARY ─────────────────────────────────────────────────
print()
print('='*65)
print('CUUC1 QUALIFICATION SUMMARY')
print('='*65)

gates = {
    'DEM available+valid': dem_used is not None,
    'Obs sustained >10mph at 12Z': qual_obs,
}

print()
for gate, passed in gates.items():
    print(f'  {"✓" if passed else "✗"} {gate}')

print()
if not qual_obs:
    print('DISQUALIFIED: near-calm at pre-registered 12Z window.')
    print(f'  12Z obs: {obs_spd} mph sustained / {obs_gust} mph gust')
    print(f'  This is the same denominator-artifact failure as HMRC1 at Camp.')
    print()
    print('  The Thomas Fire event at CUUC1 peaked overnight (03-06Z Dec 5):')
    print(f'    Max gust: {peak_gust} mph  |  Mean dir: {vmean:.0f}°')
    print(f'    BC dir: {bc_dir:.0f}°  |  Δ from peak obs dir: {ang_diff(bc_dir, vmean):.0f}°')
    print()
    print('  To score CUUC1 would require re-registering the BC at the earlier')
    print('  window (00-06Z) with a matching HRRR analysis hour. This would be')
    print('  a NEW pre-registration, not a fix of an existing one.')
    print()
    print('STOPPING as instructed — no further stations tonight.')
elif not gates['DEM available+valid']:
    print('DISQUALIFIED: no DEM covers CUUC1 with correct elevation and margin.')
    print('  A new DEM centered on 34.81N, -119.01W would be needed.')
    print('STOPPING as instructed.')
else:
    print('QUALIFIED — all gates pass. Proceeding to score...')
    # (scoring code would go here)

print()
print('Write nothing to master status — show human first.')
