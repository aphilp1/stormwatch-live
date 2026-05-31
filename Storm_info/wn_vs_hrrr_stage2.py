"""
wn_vs_hrrr_stage2.py  —  STAGE 2
WN+rawBC vs raw HRRR at terrain stations across events. NO correction.

Pre-registered BCs:
  Camp:    850 hPa 12Z 2018-11-08  (25.6 mph @ 63°)
  Kincade: 850 hPa 12Z 2019-10-27  (44.7 mph @ 42°)
  Tubbs:   700 hPa 06Z 2017-10-09  (16.6 mph @ 7°)  — direction-check first
  Thomas:  700 hPa 13Z 2017-12-05  (39.8 mph @ 81°) — direction-check first

Inclusion: (i) BC dir within 30° of observed AND (ii) HRRR 10m doesn't already
score 0.90-1.10 ("HRRR sufficient"). Excluded stations logged separately.

Write nothing to master status — show human first.
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

PASS_LO, PASS_HI = 0.80, 1.20
HRRR_SUFF_LO, HRRR_SUFF_HI = 0.90, 1.10
DIR_THRESH = 30.0   # degrees

def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def wind_from_uv(u, v):
    spd = math.sqrt(u**2 + v**2) * 2.23694
    dirn = (180 + math.degrees(math.atan2(u, v))) % 360
    return round(spd, 1), round(dirn, 1)

def nearest(ds, var, lat, lon):
    lats = ds['latitude'].values; lons = ds['longitude'].values % 360
    dist = np.sqrt((lats-lat)**2 + (lons-lon%360)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)
    return float(ds[var].values[iy, ix])

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

def run_wn(dem_name, speed, direction):
    dem  = os.path.join(CACHE, dem_name)
    stem = os.path.splitext(dem_name)[0]
    si, di = int(round(speed)), int(round(direction))
    cached = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    if cached:
        ang = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
        return cached[0], ang[0] if ang else None
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
        print(f'  ERROR: {res.stderr[-200:]}'); return None, None
    vel = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_vel-4326.asc'))
    ang = glob.glob(os.path.join(CACHE, f'{stem}_{di}_{si}_*_ang-4326.asc'))
    return (vel[0] if vel else None), (ang[0] if ang else None)

def read_raws_at(stid, event_key, utc_prefix):
    fpath = os.path.join(RAWS, event_key, f'{stid}_{event_key}.csv')
    if not os.path.exists(fpath): return None
    rows = list(csv.DictReader(open(fpath, encoding='utf-8')))
    window = [r for r in rows if r['datetime_utc'].startswith(utc_prefix)]
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

# ═══════════════════════════════════════════════════════════════════════════════
# EVENT DEFINITIONS (pre-registered BCs)
# ═══════════════════════════════════════════════════════════════════════════════
EVENTS = {
    'camp': {
        'hrrr_time':'2018-11-08 12:00','level':850,'raws_prefix':'2018-11-08T12',
        'event_key':'camp_2018','bc_center':(39.75,-121.5),
        'stations':{
            'JBGC1':{'lat':39.735910,'lon':-121.488980,'gf':1.625,
                     'dem':'dem_39.8_-121.5_12mi.tif','name':'Jarbo Gap'},
            'CBXC1':{'lat':40.145640,'lon':-121.522500,'gf':2.004,
                     'dem':'dem_40.0_-121.3_20mi.tif','name':'Colby Mtn'},
            'SLEC1':{'lat':39.636140,'lon':-120.863990,'gf':1.732,
                     'dem':'dem_39.6_-120.9_12mi_utm.tif','name':'Saddleback'},
            'HMRC1':{'lat':40.109520,'lon':-121.382700,'gf':1.801,
                     'dem':'dem_40.0_-121.3_20mi.tif','name':'Humbug Summit'},
        }
    },
    'kincade': {
        'hrrr_time':'2019-10-27 12:00','level':850,'raws_prefix':'2019-10-27T12',
        'event_key':'kincade_run_2019','bc_center':(38.86,-122.42),
        'stations':{
            'KNXC1':{'lat':38.861940,'lon':-122.417200,'gf':2.443,
                     'dem':'dem_38.9_-122.4_8mi_utm.tif','name':'Knoxville Ck'},
        }
    },
    'tubbs': {
        'hrrr_time':'2017-10-09 06:00','level':700,'raws_prefix':'2017-10-09T06',
        'event_key':'tubbs_2017','bc_center':(38.7,-122.8),
        'stations':{
            'HWKC1':{'lat':38.735090,'lon':-122.837060,'gf':2.149,
                     'dem':'dem_38.7_-122.75_16mi.tif','name':'Hawkeye'},
        }
    },
    'thomas': {
        'hrrr_time':'2017-12-05 13:00','level':700,'raws_prefix':'2017-12-05T13',
        'event_key':'thomas_2017','bc_center':(34.58,-118.7),
        'stations':{
            'WTPC1':{'lat':34.569380,'lon':-118.740100,'gf':1.957,
                     'dem':'dem_34.58_-118.66_16mi_utm.tif','name':'Whitaker Peak'},
            'WMSC1':{'lat':34.595830,'lon':-118.578600,'gf':2.060,
                     'dem':'dem_34.58_-118.66_16mi_utm.tif','name':'Warm Springs'},
        }
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# FETCH HRRR BCs AND DIRECTION-CHECK
# ═══════════════════════════════════════════════════════════════════════════════
print('='*70)
print('DIRECTION CHECK — BC vs observed per event (before scoring)')
print('='*70)

event_bc    = {}  # event → {spd, dir, hrrr10: {stid: {spd,dir}}}
event_obs   = {}  # event → {stid: obs_dict}

for ev_name, ev in EVENTS.items():
    H_prs = Herbie(ev['hrrr_time'], model='hrrr', product='prs', fxx=0)
    H_sfc = Herbie(ev['hrrr_time'], model='hrrr', product='sfc', fxx=0)
    clat, clon = ev['bc_center']
    level = ev['level']

    ds_u = H_prs.xarray(f'UGRD:{level} mb')
    ds_v = H_prs.xarray(f'VGRD:{level} mb')
    u = nearest(ds_u, 'u', clat, clon)
    v = nearest(ds_v, 'v', clat, clon)
    bc_spd, bc_dir = wind_from_uv(u, v)

    ds_u10 = H_sfc.xarray('UGRD:10 m above ground')
    ds_v10 = H_sfc.xarray('VGRD:10 m above ground')
    hrrr10 = {}
    for stid, info in ev['stations'].items():
        u10 = nearest(ds_u10, 'u10', info['lat'], info['lon'])
        v10 = nearest(ds_v10, 'v10', info['lat'], info['lon'])
        s10, d10 = wind_from_uv(u10, v10)
        hrrr10[stid] = {'spd': s10, 'dir': d10}

    event_bc[ev_name] = {'spd': bc_spd, 'dir': bc_dir, 'hrrr10': hrrr10,
                         'level': level, 'time': ev['hrrr_time']}

    # Observed
    obs_ev = {}
    for stid, info in ev['stations'].items():
        r = read_raws_at(stid, ev['event_key'], ev['raws_prefix'])
        if r:
            sus_est = r['gust'] / info['gf']
            obs_ev[stid] = {**r, 'sus_est': round(sus_est, 1)}
    event_obs[ev_name] = obs_ev

    print(f'\n{ev_name.upper()} ({level}hPa {ev["hrrr_time"]}):')
    print(f'  BC: {bc_spd}mph @ {bc_dir:.0f}°')
    for stid, info in ev['stations'].items():
        o = obs_ev.get(stid)
        obs_dir = o['dir'] if o else None
        delta = ang_diff(bc_dir, obs_dir) if obs_dir is not None else None
        match = ('GOOD' if delta<=DIR_THRESH else
                 'MARGINAL' if delta<=60 else 'POOR') if delta is not None else '—'
        h10 = hrrr10.get(stid, {})
        h10_ratio = round(h10['spd']/o['sus_est'],3) if (o and h10.get('spd') and o.get('sus_est')) else None
        hrrr_suff = (HRRR_SUFF_LO <= h10_ratio <= HRRR_SUFF_HI) if h10_ratio else False
        print(f'  {stid} ({info["name"]}):  BC_dir={bc_dir:.0f}°  '
              f'obs_dir={obs_dir:.0f}° (Δ={delta:.0f}°, {match})  '
              f'HRRR10m={h10.get("spd",0):.1f}mph ratio={h10_ratio}  '
              f'{"HRRR_SUFFICIENT" if hrrr_suff else ""}')

# ═══════════════════════════════════════════════════════════════════════════════
# APPLY INCLUSION RULES
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*70)
print('INCLUSION DECISIONS')
print('='*70)

included  = []   # (ev, stid, obs, bc_spd, bc_dir, h10_spd, dem, gf)
excluded  = []   # (ev, stid, reason)

for ev_name, ev in EVENTS.items():
    bc = event_bc[ev_name]
    for stid, info in ev['stations'].items():
        o = event_obs[ev_name].get(stid)
        if not o:
            excluded.append((ev_name, stid, f'NO_OBS at {ev["raws_prefix"]}'))
            print(f'  EXCLUDE {ev_name}/{stid}: no obs at {ev["raws_prefix"]}')
            continue

        delta = ang_diff(bc['dir'], o['dir'])
        h10 = bc['hrrr10'].get(stid, {})
        h10_spd = h10.get('spd')
        h10_ratio = round(h10_spd / o['sus_est'], 3) if (h10_spd and o['sus_est']) else None

        reason = None
        if delta > DIR_THRESH:
            reason = f'BC_DIR_MISMATCH (Δ={delta:.0f}°, threshold {DIR_THRESH:.0f}°)'
        elif h10_ratio is not None and HRRR_SUFF_LO <= h10_ratio <= HRRR_SUFF_HI:
            reason = f'HRRR_SUFFICIENT (ratio={h10_ratio}, HRRR 10m already in [{HRRR_SUFF_LO},{HRRR_SUFF_HI}])'

        if reason:
            excluded.append((ev_name, stid, reason))
            print(f'  EXCLUDE {ev_name}/{stid} ({info["name"]}): {reason}')
        else:
            included.append((ev_name, stid, o, bc['spd'], bc['dir'],
                             h10_spd, h10_ratio, info['dem'], info['gf'],
                             info['lat'], info['lon'], info['name']))
            print(f'  INCLUDE {ev_name}/{stid} ({info["name"]}): '
                  f'BC Δ={delta:.0f}°<{DIR_THRESH:.0f}°, '
                  f'HRRR10m ratio={h10_ratio} not in HRRR-sufficient band')

# ═══════════════════════════════════════════════════════════════════════════════
# WN RUNS AT PRE-REGISTERED BC FOR INCLUDED STATIONS
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*70)
print('WN RUNS — pre-registered BC at included stations')
print('='*70)

wn_preds = {}  # (ev, stid) → predicted sustained mph
for (ev_name, stid, o, bc_spd, bc_dir, h10_spd, h10_ratio,
     dem, gf, lat, lon, name) in included:
    vel, ang = run_wn(dem, bc_spd, bc_dir)
    if vel:
        pred = read_asc(vel, lat, lon)
        wn_preds[(ev_name, stid)] = pred
        print(f'  {ev_name}/{stid}: WN+rawBC = {pred} mph  '
              f'(BC: {bc_spd:.0f}@{bc_dir:.0f}°, DEM: {dem})')
    else:
        wn_preds[(ev_name, stid)] = None
        print(f'  {ev_name}/{stid}: WN FAILED')

# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*70)
print('STAGE 2 RESULTS — WN+rawBC vs raw HRRR (NO correction)')
print('Ratio = predicted_sustained / obs_sustained_est  |  Pass [0.80, 1.20]')
print('='*70)

def rfmt(ratio):
    if ratio is None: return '    —'
    flag = '✓' if PASS_LO<=ratio<=PASS_HI else '✗'
    return f'{ratio:.3f}{flag}'

print(f'{"Event":8s}  {"STID":8s}  {"Name":16s}  {"ObsGust":>8s}  {"ObsSus":>7s}  '
      f'{"(a)HRRR10m":>12s}  {"(b)WN+rawBC":>12s}')
print('-'*85)

results = []
for (ev_name, stid, o, bc_spd, bc_dir, h10_spd, h10_ratio,
     dem, gf, lat, lon, name) in included:
    os_ = o['sus_est']
    ra  = h10_ratio
    wn  = wn_preds.get((ev_name, stid))
    rb  = round(wn/os_,3) if (wn and os_) else None
    results.append((ev_name, stid, name, o['gust'], os_, ra, rb))
    print(f'{ev_name:8s}  {stid:8s}  {name:16s}  {o["gust"]:>8.1f}  {os_:>7.1f}  '
          f'{rfmt(ra):>12s}  {rfmt(rb):>12s}')

print()
if results:
    wn_beats = [(ev,s,n,rb,ra) for ev,s,n,og,os_,ra,rb in results
                if ra and rb and abs(rb-1)<abs(ra-1)]
    in_band  = [(ev,s,n,rb) for ev,s,n,og,os_,ra,rb in results
                if rb and PASS_LO<=rb<=PASS_HI]
    print(f'WN+rawBC closer to 1.0 than raw HRRR: {len(wn_beats)}/{len(results)}')
    for ev,s,n,rb,ra in wn_beats:
        print(f'  {ev}/{s} ({n}): WN={rb:.3f} beats HRRR={ra:.3f}')
    print(f'WN+rawBC in-band [0.80,1.20]: {len(in_band)}/{len(results)}')
    for ev,s,n,rb in in_band:
        print(f'  {ev}/{s} ({n}): ratio={rb:.3f}')

print('\n--- EXCLUDED STATIONS ---')
print(f'{"Event":8s}  {"STID":8s}  Reason')
for ev_name, stid, reason in excluded:
    print(f'{ev_name:8s}  {stid:8s}  {reason}')

print()
print('Write nothing to master status — show human first.')
