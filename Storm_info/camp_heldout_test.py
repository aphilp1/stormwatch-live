"""
camp_heldout_test.py  —  Camp Fire BC-corrected WindNinja held-out test.
Pre-registered: camp_heldout_prereg.md, commit 4226e2c.

Three comparisons at held-out stations CBXC1 + SLEC1:
  (a) Raw HRRR 10m wind
  (b) WindNinja with raw HRRR 850 hPa BC
  (c) WindNinja with corrected BC (fit on JBGC1 only — CICC1 near-calm at 12Z)

Note on CICC1: Openshaw reported 1 mph sustained at 12:54Z — near-calm.
Gust/GF estimate = 7.4 mph. Station provides no meaningful BC constraint.
JBGC1 is the sole fit anchor (32 mph sustained, 38°, pre-registered).
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

WN_CLI   = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE    = r'C:\temp\windninja_cache'
RAWS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs\camp_2018'
SCORE_UTC = '2018-11-08T12'

STATIONS = {
    'JBGC1': {'name':'Jarbo Gap',  'lat':39.735910,'lon':-121.488980,
               'role':'fit',    'gf':1.625,
               'dem':'dem_39.7_-121.5_5mi.tif'},
    'CBXC1': {'name':'Colby Mtn', 'lat':40.145640,'lon':-121.522500,
               'role':'holdout','gf':2.004,
               'dem':'dem_40.0_-121.3_20mi.tif'},
    'SLEC1': {'name':'Saddleback','lat':39.636140,'lon':-120.863990,
               'role':'holdout','gf':1.732,
               'dem':'dem_39.6_-120.9_12mi_utm.tif'},
}

# ── WindNinja runner (correct flags from windninja_campfire_corrected.py) ────
def run_wn(dem_path, speed_mph, dir_deg, label=''):
    dem_stem = os.path.splitext(os.path.basename(dem_path))[0]
    spd_int  = int(round(speed_mph))
    dir_int  = int(round(dir_deg))
    # Check cache
    cached_vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
        print(f'  Cached: {os.path.basename(cached_vel[0])} ({label})')
        return cached_vel[0], cached_ang[0] if cached_ang else None

    args = [
        WN_CLI, '--num_threads', '6',
        '--elevation_file', dem_path,
        '--initialization_method', 'domainAverageInitialization',
        '--input_speed',           str(spd_int),
        '--input_speed_units',     'mph',
        '--input_direction',       str(dir_int),
        '--input_wind_height',     '10',
        '--units_input_wind_height','m',
        '--uni_air_temp',          '50',
        '--air_temp_units',        'F',
        '--uni_cloud_cover',       '0.1',
        '--cloud_cover_units',     'fraction',
        '--vegetation',            'trees',
        '--mesh_choice',           'coarse',
        '--output_wind_height',    '10',
        '--units_output_wind_height','m',
        '--output_speed_units',    'mph',
        '--output_path',           CACHE,
        '--write_ascii_output',    'true',
        '--ascii_out_json',        '0',
        '--ascii_out_4326',        '1',
    ]
    t0 = time.time()
    print(f'  Running WN: {spd_int}mph @ {dir_int}° ({label})...', end=' ', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=300)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f'ERROR\n  {res.stderr[-400:]}')
        return None, None
    print(f'done [{elapsed:.0f}s]')
    vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    ang = glob.glob(os.path.join(CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
    return (vel[0] if vel else None), (ang[0] if ang else None)

def read_asc_at(asc_path, lat, lon):
    with open(asc_path) as f:
        hdr, data = {}, []
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
            else:
                try: data.append([float(v) for v in parts])
                except: pass
    arr = np.array(data)
    nrows = int(hdr['nrows']); ncols = int(hdr['ncols'])
    xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)
    col_f = (lon - xll) / cell
    row_f = (nrows - 1) - (lat - yll) / cell
    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols-2)); ri = max(0, min(ri, nrows-2))
    v = (arr[ri,   ci  ]*(1-rr)*(1-cr) + arr[ri,   ci+1]*(1-rr)*cr +
         arr[ri+1, ci  ]*rr*(1-cr)     + arr[ri+1, ci+1]*rr*cr)
    return round(float(v), 2) if abs(v - nodata) > 1 else None

def hav(la1, lo1, la2, lo2):
    R, p = 6371.0, math.pi/180
    a = math.sin((la2-la1)*p/2)**2 + math.cos(la1*p)*math.cos(la2*p)*math.sin((lo2-lo1)*p/2)**2
    return 2*R*math.asin(math.sqrt(a))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 — fetch SLEC1 DEM via WindNinja (SRTM, UTM projected)
# ══════════════════════════════════════════════════════════════════════════════
print('='*60)
print('STEP 0 — Ensure SLEC1 UTM DEM')
slec1_dem = os.path.join(CACHE, 'dem_39.6_-120.9_12mi_utm.tif')
if not os.path.exists(slec1_dem):
    print('Fetching SLEC1 DEM via WindNinja SRTM...')
    args = [
        WN_CLI,
        '--fetch_elevation', slec1_dem,
        '--x_center', '-120.9',
        '--y_center', '39.6',
        '--x_buffer', '12',
        '--y_buffer', '12',
        '--buffer_units', 'miles',
        '--elevation_source', 'srtm',
        '--initialization_method', 'domainAverageInitialization',
        '--input_speed', '25', '--input_speed_units', 'mph',
        '--input_direction', '45',
        '--input_wind_height', '10', '--units_input_wind_height', 'm',
        '--output_wind_height', '10', '--units_output_wind_height', 'm',
        '--vegetation', 'trees', '--mesh_choice', 'coarse',
        '--output_path', CACHE,
        '--write_ascii_output', 'true',
        '--ascii_out_json', '0', '--ascii_out_4326', '1',
    ]
    res = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if res.returncode == 0 and os.path.exists(slec1_dem):
        print(f'  Fetched: {slec1_dem}  ({os.path.getsize(slec1_dem)//1024}KB)')
    else:
        print(f'  WN fetch failed (HTTP {res.stderr[-200:] if res.stderr else "?"})')
        print('  Falling back to dem_39.7_-121.5_5mi.tif as SLEC1 proxy (nearest UTM DEM)')
        # Use nearest existing UTM DEM — SLEC1 results will be marked as approximate
        STATIONS['SLEC1']['dem'] = 'dem_39.8_-121.5_12mi.tif'
        STATIONS['SLEC1']['note'] = 'DEM_PROXY: nearest UTM tile, not centered on SLEC1'
        slec1_dem = os.path.join(CACHE, STATIONS['SLEC1']['dem'])
else:
    print(f'  SLEC1 UTM DEM exists: {slec1_dem}')

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — HRRR f00 2018-11-08 12Z
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('STEP 1 — HRRR f00 2018-11-08 12Z')
H_sfc = Herbie('2018-11-08 12:00', model='hrrr', product='sfc', fxx=0)
H_prs = Herbie('2018-11-08 12:00', model='hrrr', product='prs', fxx=0)

def nearest(ds, var, lat, lon):
    lats = ds['latitude'].values; lons = ds['longitude'].values % 360
    lon360 = lon % 360
    dist = np.sqrt((lats-lat)**2 + (lons-lon360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

def wind_from_uv(u, v):
    spd = math.sqrt(u**2+v**2)*2.23694
    dirn = (180+math.degrees(math.atan2(u,v)))%360
    return round(spd,1), round(dirn,0)

print('Fetching HRRR 10m wind...')
ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
hrrr_10m = {}
for stid, info in STATIONS.items():
    u = nearest(ds_u10,'u10',info['lat'],info['lon'])
    v = nearest(ds_v10,'v10',info['lat'],info['lon'])
    spd, dirn = wind_from_uv(u,v)
    hrrr_10m[stid] = {'spd_mph':spd,'dir_deg':dirn}
    print(f'  HRRR 10m {stid}: {spd}mph @ {dirn:.0f}°')

print('Fetching HRRR 850 hPa...')
ds_u850 = H_prs.xarray('UGRD:850 mb')
ds_v850 = H_prs.xarray('VGRD:850 mb')
u850 = nearest(ds_u850,'u',39.75,-121.5)
v850 = nearest(ds_v850,'v',39.75,-121.5)
raw_bc_spd, raw_bc_dir = wind_from_uv(u850,v850)
print(f'  HRRR 850 hPa raw BC: {raw_bc_spd}mph @ {raw_bc_dir:.0f}°')

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Observed at ~12Z
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('STEP 2 — RAWS observed ~12Z Nov 8 2018')

def read_obs(stid):
    fpath = os.path.join(RAWS_DIR, f'{stid}_camp_2018.csv')
    rows = list(csv.DictReader(open(fpath,encoding='utf-8')))
    window = [r for r in rows if r['datetime_utc'].startswith(SCORE_UTC)]
    if not window: return None
    def gv(r):
        try: return float(r.get('wind_gust_mph') or 0)
        except: return 0
    best = max(window, key=gv)
    try:
        return {'time': best['datetime_utc'],
                'spd': float(best.get('wind_speed_mph') or 0),
                'gust': float(best.get('wind_gust_mph') or 0),
                'dir': float(best.get('wind_dir_deg') or 0)}
    except: return None

obs = {}
for stid, info in STATIONS.items():
    r = read_obs(stid)
    if r:
        gf = info['gf']
        sus_est = r['gust'] / gf
        obs[stid] = {**r, 'sus_est': round(sus_est,1), 'gf': gf}
        print(f'  {stid} @ {r["time"][:16]}: gust={r["gust"]:.1f}  '
              f'sus_raw={r["spd"]:.1f}  sus_est(÷{gf})={sus_est:.1f}  dir={r["dir"]:.0f}°')

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — WN with raw BC at all stations
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print(f'STEP 3 — WN raw BC: {raw_bc_spd}mph @ {raw_bc_dir:.0f}°')

wn_raw = {}
for stid, info in STATIONS.items():
    dem = os.path.join(CACHE, info['dem'])
    vel, ang = run_wn(dem, raw_bc_spd, raw_bc_dir, label=stid)
    if vel:
        spd = read_asc_at(vel, info['lat'], info['lon'])
        dirn = read_asc_at(ang, info['lat'], info['lon']) if ang else None
        wn_raw[stid] = {'spd_mph': spd, 'dir_deg': dirn}
        print(f'  {stid}: WN sustained={spd}mph  dir={dirn}°'
              + (f'  [{info.get("note","")}]' if info.get('note') else ''))
    else:
        wn_raw[stid] = {'spd_mph': None, 'dir_deg': None}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — BC correction from JBGC1 (sole fit anchor)
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('STEP 4 — BC correction (fit anchor: JBGC1 only)')
print('Note: CICC1 near-calm at 12Z (1 mph sustained) — excluded from fit')

obs_j   = obs['JBGC1']['sus_est']   # 32.0 mph
wn_j    = wn_raw['JBGC1']['spd_mph']
obs_dir_j = obs['JBGC1']['dir']
wn_dir_j  = wn_raw['JBGC1'].get('dir_deg')

if wn_j and wn_j > 0:
    speed_ratio = obs_j / wn_j
    dir_delta   = 0.0
    if wn_dir_j and obs_dir_j:
        dir_delta = obs_dir_j - wn_dir_j
        dir_delta = (dir_delta + 180) % 360 - 180
    corr_bc_spd = raw_bc_spd * speed_ratio
    corr_bc_dir = (raw_bc_dir + dir_delta) % 360
    print(f'  JBGC1: obs_sus_est={obs_j:.1f}  WN_pred={wn_j:.1f}  ratio={speed_ratio:.3f}')
    print(f'  JBGC1: obs_dir={obs_dir_j:.0f}°  WN_dir={wn_dir_j}°  delta={dir_delta:+.0f}°')
    print(f'  Raw BC:  {raw_bc_spd}mph @ {raw_bc_dir:.0f}°')
    print(f'  Corr BC: {corr_bc_spd:.1f}mph @ {corr_bc_dir:.0f}°')
else:
    print('  ERROR: JBGC1 WN prediction missing')
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — WN with corrected BC at held-out stations
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*60)
print(f'STEP 5 — WN corrected BC: {corr_bc_spd:.1f}mph @ {corr_bc_dir:.0f}°  (held-out only)')

wn_corr = {}
for stid in ['CBXC1', 'SLEC1']:
    info = STATIONS[stid]
    dem  = os.path.join(CACHE, info['dem'])
    vel, ang = run_wn(dem, corr_bc_spd, corr_bc_dir, label=stid)
    if vel:
        spd  = read_asc_at(vel, info['lat'], info['lon'])
        dirn = read_asc_at(ang, info['lat'], info['lon']) if ang else None
        wn_corr[stid] = {'spd_mph': spd, 'dir_deg': dirn}
        print(f'  {stid}: WN(corr) sustained={spd}mph  dir={dirn}°'
              + (f'  [{info.get("note","")}]' if info.get('note') else ''))
    else:
        wn_corr[stid] = {'spd_mph': None, 'dir_deg': None}

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*70)
print('HELD-OUT TEST RESULTS  —  Camp Fire 2018-11-08 12Z')
print('Pre-registered: commit 4226e2c  |  Fit: JBGC1 only (CICC1 near-calm)')
print('='*70)
print(f'Raw BC : {raw_bc_spd}mph @ {raw_bc_dir:.0f}°')
print(f'Corr BC: {corr_bc_spd:.1f}mph @ {corr_bc_dir:.0f}°  (factor {speed_ratio:.3f}, dir {dir_delta:+.0f}°)')
print()
print(f'{"":6s}  {"ObsGust":>8s}  {"ObsSus":>7s}  {"(a)HRRR10m":>12s}  {"(b)WN+rawBC":>13s}  {"(c)WN+corrBC":>14s}')
print(f'{"STID":6s}  {"mph":>8s}  {"est_mph":>7s}  {"sus/ratio":>12s}  {"sus/ratio":>13s}  {"sus/ratio":>14s}')
print('-'*75)

PASS_LO, PASS_HI = 0.80, 1.20
res_table = {}
for stid in ['CBXC1', 'SLEC1']:
    o   = obs.get(stid, {})
    og  = o.get('gust');   os_ = o.get('sus_est')
    h10 = hrrr_10m.get(stid,{}).get('spd_mph')
    wrb = wn_raw.get(stid,{}).get('spd_mph')
    wrc = wn_corr.get(stid,{}).get('spd_mph')

    def r(pred, obs_s):
        if pred is None or obs_s is None or obs_s == 0: return None
        return round(pred/obs_s, 3)
    ra = r(h10, os_); rb = r(wrb, os_); rc = r(wrc, os_)

    def fmt(val, ratio):
        if val is None: return '     —/—'
        flag = '✓' if ratio and PASS_LO<=ratio<=PASS_HI else '✗'
        return f'{val:5.1f}/{ratio:.3f}{flag}' if ratio else f'{val:5.1f}/—'

    note = f' [{STATIONS[stid].get("note","")[8:25]}]' if STATIONS[stid].get('note') else ''
    print(f'{stid:6s}  {og:>8.1f}  {os_:>7.1f}  {fmt(h10,ra):>12s}  {fmt(wrb,rb):>13s}  {fmt(wrc,rc):>14s}{note}')
    res_table[stid] = {'og':og,'os':os_,'h10':h10,'wrb':wrb,'wrc':wrc,'ra':ra,'rb':rb,'rc':rc}

print()
print('Ratio = predicted_sustained / obs_sustained_est  |  Pass band [0.80, 1.20]')
print()
print('FIT STATION (informational — not held-out):')
o_j = obs.get('JBGC1',{}); wr_j = wn_raw.get('JBGC1',{}).get('spd_mph')
rc_j = round(wr_j/o_j['sus_est'],3) if (wr_j and o_j.get('sus_est')) else None
print(f'  JBGC1  obs_sus_est={o_j.get("sus_est"):.1f}  WN_raw={wr_j}  ratio={rc_j}  '
      f'(corr BC applied only to held-out, not re-run at JBGC1)')
print()

# Verdict
def close(r): return r is not None and PASS_LO <= r <= PASS_HI
def better(rc_, rb_): return rc_ is not None and rb_ is not None and abs(rc_-1)<abs(rb_-1)
def better_a(rc_, ra_): return rc_ is not None and ra_ is not None and abs(rc_-1)<abs(ra_-1)

beats_a = all(better_a(res_table[s]['rc'],res_table[s]['ra']) for s in ['CBXC1','SLEC1'])
beats_b = all(better(res_table[s]['rc'],res_table[s]['rb'])   for s in ['CBXC1','SLEC1'])
in_band = all(close(res_table[s]['rc']) for s in ['CBXC1','SLEC1'])

print('VERDICT (pre-registered criteria):')
print(f'  (a) Beats raw HRRR 10m at both held-out:  {"YES" if beats_a else "NO"}')
print(f'  (b) Beats WN+rawBC at both held-out:      {"YES" if beats_b else "NO"}')
print(f'      Ratio within [0.80,1.20] at both:     {"YES" if in_band else "NO"}')
print()
if beats_a and beats_b and in_band:
    print('  RESULT: PASS')
elif beats_a and beats_b:
    print('  RESULT: PARTIAL — beats both baselines but outside 15-20% band')
else:
    print('  RESULT: FAIL')
print()
print('Do not write to master status — show human first.')
