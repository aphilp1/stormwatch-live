"""
thomas_stage2.py  —  STAGE 2 (Thomas Fire only)
Pre-registered BC: 850 hPa, 12Z 2017-12-05, bc_center (34.58N, -118.7W)
Scoring station: WMSC1 (Warm Springs) only. WTPC1 excluded (terrain-deflected).

Steps:
  1. Flag the GF correction (stage2.py held 2.060; confirmed 1.560)
  2. Fetch HRRR 850 hPa 12Z for BC, fetch HRRR 10m at WMSC1 for comparison
  3. Run WN with pre-registered BC at WMSC1 DEM
  4. Print: obs sustained (confirmed GF), raw HRRR ratio, WN+rawBC ratio
  5. Print cross-event table (Camp CBXC1/SLEC1 + Kincade KNXC1 + Thomas WMSC1)

No correction applied. Write nothing to master status — show human first.
"""

import sys, os, math, csv, subprocess, glob, time
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
from herbie import Herbie

WN    = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE = r'C:\temp\windninja_cache'
RAWS  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs'

# ─── Pre-registered parameters ────────────────────────────────────────────────
HRRR_TIME   = '2017-12-05 12:00'
LEVEL       = 850
BC_CENTER   = (34.58, -118.70)
RAWS_PREFIX = '2017-12-05T12'

# WMSC1 confirmed parameters
WMSC1_LAT = 34.595830
WMSC1_LON = -118.578600
WMSC1_DEM = 'dem_34.58_-118.66_16mi_utm.tif'
GF_WRONG  = 2.060    # what stage2.py had — borrowed/inflated
GF_MEDIAN = 1.560    # WMSC1 own empirical median (thomas_2017, 72 pairs, OK)
GF_PEAK   = 1.619    # peak-moment GF (68.0/42.01 at 13:53Z) — shown for reference

# Pass band
PASS_LO, PASS_HI = 0.80, 1.20

def wind_from_uv(u, v):
    spd  = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def nearest(ds, var, lat, lon):
    lats = ds['latitude'].values
    lons = ds['longitude'].values % 360
    dist = np.sqrt((lats - lat)**2 + (lons - lon % 360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def run_wn(dem_name, speed, direction):
    dem  = os.path.join(CACHE, dem_name)
    stem = os.path.splitext(dem_name)[0]
    si, di = int(round(speed)), int(round(direction))
    cached_vel = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
        print(f'  [cached] WN {dem_name} {si}mph@{di}°')
        return cached_vel[0], (cached_ang[0] if cached_ang else None)
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

# ─── 0. GF CORRECTION NOTICE ──────────────────────────────────────────────────
print('='*70)
print('GF CORRECTION (pre-registered, committed b15c0f1)')
print('='*70)
print(f'  stage2.py held gf = {GF_WRONG}  ← BORROWED / INFLATED (not WMSC1\'s own)')
print(f'  WMSC1 own (thomas_2017, 72 pairs, status OK):')
print(f'    median_gust_factor = {GF_MEDIAN}   ← USE THIS')
print(f'    peak_gust_factor   = {GF_PEAK}   (68.0 gust / 42.01 sustained at 13:53Z)')
print()
print(f'  Impact on obs_sustained_est at 12Z observation (peak gust in window = 55.01 mph):')
print(f'    Wrong  (gf={GF_WRONG}): 55.01 / {GF_WRONG} = {55.01/GF_WRONG:.1f} mph')
print(f'    Correct(gf={GF_MEDIAN}): 55.01 / {GF_MEDIAN} = {55.01/GF_MEDIAN:.1f} mph')
print(f'  Denominator error was {(55.01/GF_WRONG - 55.01/GF_MEDIAN)/(55.01/GF_MEDIAN)*100:.0f}% low → HRRR/WN ratios were inflated')

# ─── 1. OBSERVED WMSC1 at 12Z ─────────────────────────────────────────────────
print()
print('='*70)
print('WMSC1 OBSERVATIONS — 12Z window (2017-12-05T12)')
print('='*70)
fpath = os.path.join(RAWS, 'thomas_2017', 'WMSC1_thomas_2017.csv')
rows  = list(csv.DictReader(open(fpath, encoding='utf-8')))
window = [r for r in rows if r['datetime_utc'].startswith(RAWS_PREFIX)]
if not window:
    print('ERROR: no rows found for prefix', RAWS_PREFIX); sys.exit(1)

def gv(r):
    try: return float(r.get('wind_gust_mph') or 0)
    except: return 0

best = max(window, key=gv)
obs_gust = float(best.get('wind_gust_mph') or 0)
obs_spd  = float(best.get('wind_speed_mph') or 0)
obs_dir  = float(best.get('wind_dir_deg') or 0)
obs_time = best['datetime_utc']

obs_sus_est = round(obs_gust / GF_MEDIAN, 2)

print(f'  Peak-gust row in 12Z window:')
print(f'    Time:            {obs_time}')
print(f'    Gust:            {obs_gust} mph')
print(f'    Sustained (obs): {obs_spd} mph')
print(f'    Direction:       {obs_dir}°')
print(f'    GF (median):     {GF_MEDIAN}')
print(f'    Obs sustained est = gust / GF = {obs_gust} / {GF_MEDIAN} = {obs_sus_est} mph')

# ─── 2. HRRR BC + HRRR 10m ────────────────────────────────────────────────────
print()
print('='*70)
print(f'HRRR FETCH — {LEVEL} hPa and 10m  @ {HRRR_TIME}')
print('='*70)

H_prs = Herbie(HRRR_TIME, model='hrrr', product='prs', fxx=0)
H_sfc = Herbie(HRRR_TIME, model='hrrr', product='sfc', fxx=0)

clat, clon = BC_CENTER
ds_u = H_prs.xarray(f'UGRD:{LEVEL} mb')
ds_v = H_prs.xarray(f'VGRD:{LEVEL} mb')
u = nearest(ds_u, 'u', clat, clon)
v = nearest(ds_v, 'v', clat, clon)
bc_spd, bc_dir = wind_from_uv(u, v)

ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
u10 = nearest(ds_u10, 'u10', WMSC1_LAT, WMSC1_LON)
v10 = nearest(ds_v10, 'v10', WMSC1_LAT, WMSC1_LON)
h10_spd, h10_dir = wind_from_uv(u10, v10)

delta_bc_obs = ang_diff(bc_dir, obs_dir)

print(f'  BC ({LEVEL} hPa at bc_center):   {bc_spd} mph @ {bc_dir:.1f}°')
print(f'  HRRR 10m at WMSC1:           {h10_spd} mph @ {h10_dir:.1f}°')
print(f'  BC dir vs WMSC1 obs dir:     {bc_dir:.1f}° vs {obs_dir:.1f}° → Δ={delta_bc_obs:.0f}°  '
      f'{"GOOD (≤30°)" if delta_bc_obs<=30 else "FAIL (>30°)"}')

h10_ratio = round(h10_spd / obs_sus_est, 3) if obs_sus_est else None
print(f'  HRRR 10m ratio = {h10_spd} / {obs_sus_est} = {h10_ratio}  '
      f'{"✓" if h10_ratio and PASS_LO<=h10_ratio<=PASS_HI else "✗"}')

# ─── 3. WN RUN ────────────────────────────────────────────────────────────────
print()
print('='*70)
print(f'WN RUN — pre-registered BC: {bc_spd:.0f} mph @ {bc_dir:.0f}°  DEM: {WMSC1_DEM}')
print('='*70)
vel_path, ang_path = run_wn(WMSC1_DEM, bc_spd, bc_dir)
if vel_path is None:
    print('WN FAILED — cannot score'); sys.exit(1)

wn_pred = read_asc(vel_path, WMSC1_LAT, WMSC1_LON)
if wn_pred is None:
    print('ERROR: could not interpolate WN output at WMSC1 coords'); sys.exit(1)

wn_ratio = round(wn_pred / obs_sus_est, 3) if obs_sus_est else None
print(f'  WN output at WMSC1:    {wn_pred} mph (sustained)')
print(f'  WN+rawBC ratio = {wn_pred} / {obs_sus_est} = {wn_ratio}  '
      f'{"✓" if wn_ratio and PASS_LO<=wn_ratio<=PASS_HI else "✗"}')

wn_beats = (wn_ratio is not None and h10_ratio is not None and
            abs(wn_ratio-1) < abs(h10_ratio-1))

# ─── 4. THOMAS RESULT SUMMARY ────────────────────────────────────────────────
print()
print('='*70)
print('THOMAS / WMSC1 — STAGE 2 RESULT')
print(f'BC: {LEVEL} hPa {HRRR_TIME[11:13]}Z  GF: {GF_MEDIAN} (median, own empirical)')
print('='*70)
print(f'  Obs gust:         {obs_gust} mph  @ {obs_time}')
print(f'  Obs sus est:      {obs_sus_est} mph  (= {obs_gust}/{GF_MEDIAN})')
print(f'  HRRR 10m:         {h10_spd} mph  ratio={h10_ratio}  '
      f'{"✓ in-band" if h10_ratio and PASS_LO<=h10_ratio<=PASS_HI else "✗ out-of-band"}')
print(f'  WN+rawBC:         {wn_pred} mph  ratio={wn_ratio}  '
      f'{"✓ in-band" if wn_ratio and PASS_LO<=wn_ratio<=PASS_HI else "✗ out-of-band"}')
print(f'  WN beats HRRR:    {"YES" if wn_beats else "NO"}  '
      f'(|WN-1|={abs(wn_ratio-1):.3f} vs |HRRR-1|={abs(h10_ratio-1):.3f})')
print(f'  BC dir check:     Δ={delta_bc_obs:.0f}°  '
      f'{"PASS" if delta_bc_obs<=30 else "FAIL — excluded from scoring"}')

# ─── 5. CROSS-EVENT TABLE ─────────────────────────────────────────────────────
print()
print('='*70)
print('CROSS-EVENT TABLE — WN+rawBC vs raw HRRR at terrain stations')
print('Pass band [0.80, 1.20].  (*) = held-out (never fit).')
print('='*70)
print(f'{"Event":8s}  {"Sta":7s}  {"Elev":6s}  {"Terrain":16s}  {"ObsSus":>7s}  '
      f'{"HRRRrat":>8s}  {"WNrat":>7s}  {"WN>HRRR":>8s}  {"InBand":>7s}')
print('-'*80)

prior = [
    # event, stid, elev_ft, terrain, obs_sus, hrrr_ratio, wn_ratio
    ('Camp',    'CBXC1(*)', '6004 ft', 'exposed ridge',   None, 0.869, 1.007),
    ('Camp',    'SLEC1(*)', '6670 ft', 'exposed ridge',   None, 0.525, 1.128),
    ('Camp',    'JBGC1',   '1850 ft', 'canyon/gap',       None, 0.519, 0.771),  # not in-band
    ('Kincade', 'KNXC1',   '2200 ft', 'valley',           None, None,  2.003),  # WN overshoots
]

for ev, stid, elev, terr, obs_sus_pr, hr, wr in prior:
    wn_b  = ('YES' if (hr and wr and abs(wr-1)<abs(hr-1)) else
             'N/A' if hr is None else 'NO')
    inb   = ('✓' if wr and PASS_LO<=wr<=PASS_HI else '✗') if wr else '—'
    hr_s  = f'{hr:.3f}' if hr is not None else '—'
    wr_s  = f'{wr:.3f}' if wr is not None else '—'
    note  = '(unresolved)' if stid=='KNXC1' else ''
    print(f'{ev:8s}  {stid:7s}  {elev:6s}  {terr:16s}  {"—":>7s}  '
          f'{hr_s:>8s}  {wr_s:>7s}  {wn_b:>8s}  {inb:>7s}  {note}')

# Thomas current result
wn_b_t = 'YES' if wn_beats else 'NO'
inb_t  = '✓' if wn_ratio and PASS_LO<=wn_ratio<=PASS_HI else '✗'
hr_s_t = f'{h10_ratio:.3f}' if h10_ratio else '—'
wr_s_t = f'{wn_ratio:.3f}' if wn_ratio else '—'
print(f'{"Thomas":8s}  {"WMSC1":7s}  {"~4200ft":6s}  {"exposed ridge?":16s}  '
      f'{obs_sus_est:>7.1f}  {hr_s_t:>8s}  {wr_s_t:>7s}  {wn_b_t:>8s}  {inb_t:>7s}')

print()
print('Notes:')
print('  Camp CBXC1+SLEC1: held-out niche confirmed (2026-05-31)')
print('  Camp JBGC1: canyon under-resolved, BC dir 25° off — not counted')
print('  Kincade KNXC1: WN overshoots, cause unresolved — not counted')
print('  Thomas WMSC1: THIS RUN (GF corrected from 2.060 → 1.560)')
print()
print('Write nothing to master status — show human first.')
