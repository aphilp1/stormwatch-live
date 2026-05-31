"""
camp_loso_loeo.py
Test 1: Within-Camp 4-of-5 leave-one-station-out (LOSO)
Test 2: Cross-event leave-one-event-out (LOEO)

No amplification ratios. Print result tables. Do not write to master status.
"""
import sys, os, math, csv, subprocess, glob, time, itertools
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

os.environ['PATH'] = (
    r'C:\Users\aphil\miniforge3\envs\hrrr311' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\mingw-w64\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\usr\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Library\bin' + os.pathsep +
    r'C:\Users\aphil\miniforge3\envs\hrrr311\Scripts' + os.pathsep +
    os.environ.get('PATH','')
)
from herbie import Herbie

WN    = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE = r'C:\temp\windninja_cache'
RAWS  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\raws_obs'

# ─── Station registry ────────────────────────────────────────────────────────
# gf = per-station median from raws_gust_factors.csv
STATIONS = {
    # Camp Fire (850 hPa BC — sub-inversion gap flow)
    'JBGC1':{'name':'Jarbo Gap',    'lat':39.735910,'lon':-121.488980,'elev_ft':2535,
              'event':'camp','bc_level':850,'gf':1.625,'dem':'dem_39.8_-121.5_12mi.tif'},
    'CBXC1':{'name':'Colby Mtn',    'lat':40.145640,'lon':-121.522500,'elev_ft':6004,
              'event':'camp','bc_level':850,'gf':2.004,'dem':'dem_40.0_-121.3_20mi.tif'},
    'SLEC1':{'name':'Saddleback',   'lat':39.636140,'lon':-120.863990,'elev_ft':6670,
              'event':'camp','bc_level':850,'gf':1.732,'dem':'dem_39.6_-120.9_12mi_utm.tif'},
    'HMRC1':{'name':'Humbug Summit','lat':40.109520,'lon':-121.382700,'elev_ft':6714,
              'event':'camp','bc_level':850,'gf':1.801,'dem':'dem_40.0_-121.3_20mi.tif'},
    'CICC1':{'name':'Openshaw',     'lat':39.589830,'lon':-121.635160,'elev_ft':268,
              'event':'camp','bc_level':850,'gf':1.760,'dem':'dem_39.6_-121.6_8mi_utm.tif',
              'note':'valley station'},
    # Tubbs 2017 (700 hPa BC — above-inversion Diablo)
    'HWKC1':{'name':'Hawkeye',      'lat':38.735090,'lon':-122.837060,'elev_ft':2024,
              'event':'tubbs','bc_level':700,'gf':2.149,'dem':'dem_38.7_-122.75_16mi.tif'},
    # Thomas 2017 (700 hPa BC — Santa Ana)
    'WTPC1':{'name':'Whitaker Peak','lat':34.569380,'lon':-118.740100,'elev_ft':4120,
              'event':'thomas','bc_level':700,'gf':1.957,'dem':'dem_34.58_-118.66_16mi_utm.tif'},
    'WMSC1':{'name':'Warm Springs', 'lat':34.595830,'lon':-118.578600,'elev_ft':4930,
              'event':'thomas','bc_level':700,'gf':2.060,'dem':'dem_34.58_-118.66_16mi_utm.tif'},
    # Kincade run Oct 27 2019 (700 hPa BC — above-inversion Diablo)
    'KNXC1':{'name':'Knoxville Ck', 'lat':38.861940,'lon':-122.417200,'elev_ft':2200,
              'event':'kincade','bc_level':700,'gf':2.443,'dem':'dem_38.9_-122.4_8mi_utm.tif'},
}
# Kincade HWKC1 is same station as Tubbs — different event window
STATIONS['HWKC1_k'] = {**STATIONS['HWKC1'], 'event':'kincade', 'gf':2.103,
                        'name':'Hawkeye(K)'}

# HRRR analysis hours per event (f00, UTC)
EVENT_HRRR = {
    'camp':   '2018-11-08 12:00',
    'tubbs':  '2017-10-09 06:00',
    'thomas': None,   # determined from RAWS peak hour below
    'kincade':'2019-10-27 12:00',
}

# BC grid to sweep (focused on NE–E quadrant, plausible range)
SPEED_GRID = [15, 20, 25, 30, 35, 40]
DIR_GRID   = [15, 30, 45, 60, 75]   # degrees, met convention (FROM)

PASS_LO, PASS_HI = 0.80, 1.20

# ─── Helpers ─────────────────────────────────────────────────────────────────
def hav(la1,lo1,la2,lo2):
    R,p=6371.0,math.pi/180
    a=math.sin((la2-la1)*p/2)**2+math.cos(la1*p)*math.cos(la2*p)*math.sin((lo2-lo1)*p/2)**2
    return 2*R*math.asin(math.sqrt(a))

def wind_from_uv(u,v):
    spd=math.sqrt(u**2+v**2)*2.23694
    dirn=(180+math.degrees(math.atan2(u,v)))%360
    return round(spd,2),round(dirn,1)

def nearest(ds,var,lat,lon):
    lats=ds['latitude'].values; lons=ds['longitude'].values%360
    dist=np.sqrt((lats-lat)**2+(lons-lon%360)**2)
    iy,ix=np.unravel_index(dist.argmin(),dist.shape)
    return float(ds[var].values[iy,ix])

def read_asc(path,lat,lon):
    with open(path) as f:
        hdr,data={},[]
        for line in f:
            p=line.strip().split()
            if not p: continue
            if len(p)==2 and not p[0][0].lstrip('-').replace('.','').isdigit():
                hdr[p[0].lower()]=float(p[1])
            else:
                try: data.append([float(v) for v in p])
                except: pass
    arr=np.array(data)
    nr=int(hdr['nrows']); nc=int(hdr['ncols'])
    xll=hdr['xllcorner']; yll=hdr['yllcorner']; cell=hdr['cellsize']
    nd=hdr.get('nodata_value',-9999)
    colf=(lon-xll)/cell; rowf=(nr-1)-(lat-yll)/cell
    ci,ri=int(colf),int(rowf); cr,rr=colf-ci,rowf-ri
    ci=max(0,min(ci,nc-2)); ri=max(0,min(ri,nr-2))
    v=(arr[ri,ci]*(1-rr)*(1-cr)+arr[ri,ci+1]*(1-rr)*cr+
       arr[ri+1,ci]*rr*(1-cr)+arr[ri+1,ci+1]*rr*cr)
    return round(float(v),2) if abs(v-nd)>1 else None

def run_wn(dem_name,speed,direction,quiet=False):
    dem=os.path.join(CACHE,dem_name)
    stem=os.path.splitext(dem_name)[0]
    si,di=int(round(speed)),int(round(direction))
    # Check cache
    cached=glob.glob(os.path.join(CACHE,f'{stem}_{di}_{si}_*_vel-4326.asc'))
    if cached:
        ang=glob.glob(os.path.join(CACHE,f'{stem}_{di}_{si}_*_ang-4326.asc'))
        return cached[0],ang[0] if ang else None
    if not quiet: print(f'    WN {dem_name} {si}mph@{di}°...',end=' ',flush=True)
    args=[WN,'--num_threads','6','--elevation_file',dem,
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
    t0=time.time()
    res=subprocess.run(args,capture_output=True,text=True,timeout=300)
    if not quiet: print(f'[{time.time()-t0:.0f}s]')
    if res.returncode!=0:
        if not quiet: print(f'      ERROR: {res.stderr[-200:]}')
        return None,None
    vel=glob.glob(os.path.join(CACHE,f'{stem}_{di}_{si}_*_vel-4326.asc'))
    ang=glob.glob(os.path.join(CACHE,f'{stem}_{di}_{si}_*_ang-4326.asc'))
    return (vel[0] if vel else None),(ang[0] if ang else None)

def fetch_dem_wn(name,lat_c,lon_c,radius_mi):
    path=os.path.join(CACHE,name)
    if os.path.exists(path):
        print(f'  DEM exists: {name}'); return True
    print(f'  Fetching DEM {name} ({lat_c}N,{lon_c}W,{radius_mi}mi)...',end=' ',flush=True)
    args=[WN,'--fetch_elevation',path,
          '--x_center',str(lon_c),'--y_center',str(lat_c),
          '--x_buffer',str(radius_mi),'--y_buffer',str(radius_mi),
          '--buffer_units','miles','--elevation_source','srtm',
          '--initialization_method','domainAverageInitialization',
          '--input_speed','25','--input_speed_units','mph',
          '--input_direction','45',
          '--input_wind_height','10','--units_input_wind_height','m',
          '--output_wind_height','10','--units_output_wind_height','m',
          '--vegetation','trees','--mesh_choice','coarse',
          '--output_path',CACHE,
          '--write_ascii_output','true','--ascii_out_json','0','--ascii_out_4326','1']
    res=subprocess.run(args,capture_output=True,text=True,timeout=120)
    ok=res.returncode==0 and os.path.exists(path)
    print('OK' if ok else f'FAIL: {res.stderr[-100:]}')
    return ok

def read_peak_raws(stid,event,target_utc_prefix):
    """Return obs dict at the hour closest to target_utc_prefix."""
    event_key={'camp':'camp_2018','tubbs':'tubbs_2017',
               'thomas':'thomas_2017','kincade':'kincade_run_2019'}.get(event,event)
    fpath=os.path.join(RAWS,event_key,f'{stid}_{event_key}.csv')
    if not os.path.exists(fpath): return None
    rows=list(csv.DictReader(open(fpath,encoding='utf-8')))
    window=[r for r in rows if r['datetime_utc'].startswith(target_utc_prefix)]
    if not window: return None
    def gv(r):
        try: return float(r.get('wind_gust_mph') or 0)
        except: return 0
    best=max(window,key=gv)
    try:
        return {'time':best['datetime_utc'],
                'spd':float(best.get('wind_speed_mph') or 0),
                'gust':float(best.get('wind_gust_mph') or 0),
                'dir':float(best.get('wind_dir_deg') or 0)}
    except: return None

def find_thomas_peak_hour():
    """Find UTC hour of peak gust across WTPC1+WMSC1 in Thomas CSV."""
    best_t, best_g = None, 0
    for stid in ['WTPC1','WMSC1']:
        fpath=os.path.join(RAWS,'thomas_2017',f'{stid}_thomas_2017.csv')
        if not os.path.exists(fpath): continue
        for row in csv.DictReader(open(fpath,encoding='utf-8')):
            try:
                g=float(row.get('wind_gust_mph') or 0)
                t=row['datetime_utc']
                if g>best_g: best_g=g; best_t=t
            except: pass
    return best_t[:13] if best_t else '2017-12-05T06'  # fallback

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 0 — Fetch missing DEMs
# ═══════════════════════════════════════════════════════════════════════════════
print('='*60); print('STEP 0 — Fetch missing DEMs')
fetch_dem_wn('dem_39.6_-121.6_8mi_utm.tif', 39.6,-121.6, 8)   # CICC1
fetch_dem_wn('dem_34.58_-118.66_16mi_utm.tif',34.58,-118.66,16) # Thomas WTPC1+WMSC1
fetch_dem_wn('dem_38.9_-122.4_8mi_utm.tif',  38.9,-122.4, 8)   # KNXC1

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — HRRR raw BCs for all events
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*60); print('STEP 1 — HRRR raw BCs')

thomas_peak_prefix = find_thomas_peak_hour()
EVENT_HRRR['thomas'] = f"{thomas_peak_prefix[:10]} {thomas_peak_prefix[11:13]}:00"
print(f'Thomas peak hour: {thomas_peak_prefix}')

raw_bc = {}  # event → {spd, dir, level}
SCORE_UTC = {'camp':'2018-11-08T12','tubbs':'2017-10-09T06',
             'thomas':thomas_peak_prefix,'kincade':'2019-10-27T12'}

for event,hrrr_time in EVENT_HRRR.items():
    level=850 if event=='camp' else 700
    H_sfc=Herbie(hrrr_time,model='hrrr',product='sfc',fxx=0)
    H_prs=Herbie(hrrr_time,model='hrrr',product='prs',fxx=0)
    # Domain center per event
    centers={'camp':(39.75,-121.5),'tubbs':(38.7,-122.8),
              'thomas':(34.58,-118.7),'kincade':(38.8,-122.5)}
    clat,clon=centers[event]
    var='u' if level==700 else 'u'
    vvar='v'
    ds_u=H_prs.xarray(f'UGRD:{level} mb')
    ds_v=H_prs.xarray(f'VGRD:{level} mb')
    u=nearest(ds_u,'u',clat,clon); v=nearest(ds_v,'v',clat,clon)
    spd,dirn=wind_from_uv(u,v)
    # Also get HRRR 10m at each station in this event
    ds_u10=H_sfc.xarray('UGRD:10 m above ground')
    ds_v10=H_sfc.xarray('VGRD:10 m above ground')
    event_stids=[s for s,i in STATIONS.items() if i['event']==event]
    hrrr10 = {}
    for stid in event_stids:
        info=STATIONS[stid]
        u10=nearest(ds_u10,'u10',info['lat'],info['lon'])
        v10=nearest(ds_v10,'v10',info['lat'],info['lon'])
        s10,d10=wind_from_uv(u10,v10)
        hrrr10[stid]={'spd':s10,'dir':d10}
    raw_bc[event]={'spd':spd,'dir':dirn,'level':level,'hrrr10':hrrr10}
    print(f'  {event}: {level}hPa raw BC = {spd}mph @ {dirn:.0f}°  '
          f'(center {clat}N,{clon}W, t={hrrr_time})')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — RAWS observed at peak hour for all stations
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*60); print('STEP 2 — RAWS observed at peak hour')

obs = {}
for stid,info in STATIONS.items():
    event=info['event']
    prefix=SCORE_UTC[event]
    r=read_peak_raws(stid,event,prefix)
    if r:
        gf=info['gf']
        sus_est=r['gust']/gf
        obs[stid]={**r,'sus_est':round(sus_est,1),'gf':gf}
        note=f' [{info.get("note","")}]' if info.get('note') else ''
        print(f'  {stid} {event:8s} @ {r["time"][:16]}: gust={r["gust"]:.0f} '
              f'sus_est={sus_est:.1f} dir={r["dir"]:.0f}°{note}')
    else:
        print(f'  {stid} {event}: NO OBS at {prefix}')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Build WN grid for all stations
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*60); print('STEP 3 — WN grid (all stations × all BCs)')
print(f'Grid: {len(SPEED_GRID)} speeds × {len(DIR_GRID)} dirs = '
      f'{len(SPEED_GRID)*len(DIR_GRID)} BCs per station')

# wn_grid[stid][(spd,dir)] = sustained mph at station
wn_grid = {stid:{} for stid in STATIONS}

for stid,info in STATIONS.items():
    dem=info['dem']
    print(f'  {stid} ({info["name"]}, {dem}):')
    for spd in SPEED_GRID:
        for dirn in DIR_GRID:
            vel,ang=run_wn(dem,spd,dirn,quiet=True)
            if vel:
                v=read_asc(vel,info['lat'],info['lon'])
                wn_grid[stid][(spd,dirn)]=v
            else:
                wn_grid[stid][(spd,dirn)]=None
    n_ok=sum(1 for v in wn_grid[stid].values() if v is not None)
    vals=[v for v in wn_grid[stid].values() if v]
    print(f'    {n_ok}/{len(SPEED_GRID)*len(DIR_GRID)} grid points, '
          f'range [{min(vals):.1f},{max(vals):.1f}] mph')

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER — optimal BC and ratio table
# ═══════════════════════════════════════════════════════════════════════════════
def find_optimal_bc(fit_stids, obs, wn_grid):
    """Find (spd, dir) that minimizes RMSE at fit_stids."""
    best_bc,best_rmse=None,float('inf')
    for spd in SPEED_GRID:
        for dirn in DIR_GRID:
            sq,n=0,0
            for stid in fit_stids:
                pred=wn_grid[stid].get((spd,dirn))
                o=obs.get(stid,{}).get('sus_est')
                if pred is None or o is None: continue
                sq+=(pred-o)**2; n+=1
            if n==0: continue
            rmse=math.sqrt(sq/n)
            if rmse<best_rmse: best_rmse=rmse; best_bc=(spd,dirn)
    return best_bc,best_rmse

def wn_at_bc(stid,bc,wn_grid):
    """Interpolate WN grid to non-grid BC if needed (nearest for now)."""
    if bc is None: return None
    spd,dirn=bc
    # Find nearest grid point
    best,best_dist=None,float('inf')
    for gs in SPEED_GRID:
        for gd in DIR_GRID:
            d=abs(gs-spd)+abs(gd-dirn)*0.5
            if d<best_dist:
                best_dist=d; best=(gs,gd)
    return wn_grid[stid].get(best)

def ratio_str(pred,obs_s):
    if pred is None or obs_s is None or obs_s==0: return '   —'
    r=pred/obs_s
    flag='✓' if PASS_LO<=r<=PASS_HI else '✗'
    return f'{r:.3f}{flag}'

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Within-Camp LOSO
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*70)
print('TEST 1 — Within-Camp 4-of-5 Leave-One-Station-Out')
print('='*70)
camp_raw_bc=raw_bc['camp']
raw_bc_key=(min(SPEED_GRID,key=lambda s:abs(s-camp_raw_bc['spd'])),
            min(DIR_GRID,key=lambda d:abs(d-camp_raw_bc['dir'])))
print(f'Camp raw BC: {camp_raw_bc["spd"]}mph @ {camp_raw_bc["dir"]:.0f}°  '
      f'(nearest grid: {raw_bc_key[0]}mph@{raw_bc_key[1]}°)')
print()

camp_stids=['JBGC1','CBXC1','SLEC1','HMRC1','CICC1']

print(f'{"HeldOut":8s}  {"Obs_gust":>9s}  {"Obs_sus":>8s}  '
      f'{"(a)HRRR10m":>11s}  {"(b)WN+rawBC":>12s}  {"(c)WN+corrBC":>13s}  '
      f'{"Fit_RMSE":>9s}  {"Opt_BC":>12s}  Note')
print('-'*110)

loso_results={}
for holdout in camp_stids:
    fit=[s for s in camp_stids if s!=holdout]
    info=STATIONS[holdout]
    o=obs.get(holdout,{})
    og=o.get('gust'); os_=o.get('sus_est')

    # Flag near-calm
    note=''
    if og and og<10: note='NEAR-CALM — unreliable anchor'
    elif info.get('note'): note=info['note']

    # (a) raw HRRR 10m
    h10=camp_raw_bc['hrrr10'].get(holdout,{}).get('spd')
    ra=round(h10/os_,3) if (h10 and os_) else None

    # (b) WN + raw BC (nearest grid point)
    wrb=wn_grid[holdout].get(raw_bc_key)
    rb=round(wrb/os_,3) if (wrb and os_) else None

    # (c) Multi-station correction: optimal BC from 4 fit stations
    opt_bc,fit_rmse=find_optimal_bc(fit,obs,wn_grid)
    wrc=wn_grid[holdout].get(opt_bc) if opt_bc else None
    rc=round(wrc/os_,3) if (wrc and os_) else None

    opt_str=f'{opt_bc[0]}@{opt_bc[1]}°' if opt_bc else '—'
    print(f'{holdout:8s}  {og if og else "—":>9}  {os_ if os_ else "—":>8}  '
          f'{ratio_str(h10,os_):>11s}  {ratio_str(wrb,os_):>12s}  '
          f'{ratio_str(wrc,os_):>13s}  '
          f'{fit_rmse:>9.2f}  {opt_str:>12s}  {note}')
    loso_results[holdout]={'og':og,'os':os_,'ra':ra,'rb':rb,'rc':rc,
                           'opt_bc':opt_bc,'fit_rmse':fit_rmse,'note':note}

print()
# Summary: does corrBC beat rawBC at each held-out?
beats_raw = {s: (loso_results[s]['rc'] is not None and
                 loso_results[s]['rb'] is not None and
                 abs(loso_results[s]['rc']-1) < abs(loso_results[s]['rb']-1))
             for s in camp_stids if loso_results[s]['rc'] is not None}
print('Does multi-station corrBC beat WN+rawBC at held-out?')
for s,b in beats_raw.items():
    note=loso_results[s].get('note','')
    print(f'  {s}: {"YES" if b else "NO"}  {note}')
n_beats=sum(beats_raw.values()); n_tot=len(beats_raw)
print(f'  {n_beats}/{n_tot} held-out stations improved by multi-station correction')

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Cross-Event LOEO
# ═══════════════════════════════════════════════════════════════════════════════
print('\n'+'='*70)
print('TEST 2 — Cross-Event Leave-One-Event-Out')
print('='*70)

# Events and their stations
EVENT_STIDS = {
    'camp':    ['JBGC1','CBXC1','SLEC1','HMRC1'],  # exclude CICC1 (near-calm)
    'tubbs':   ['HWKC1'],
    'thomas':  ['WTPC1','WMSC1'],
    'kincade': ['KNXC1','HWKC1_k'],
}
ALL_EVENTS=['camp','tubbs','thomas','kincade']

# For each training event, find the optimal BC (fit on all event stations)
print('Finding optimal BC per training event:')
event_opt_bc={}
for event in ALL_EVENTS:
    stids=EVENT_STIDS[event]
    # Filter to stids with obs and wn_grid data
    valid=[s for s in stids if s in obs and s in wn_grid and
           any(v for v in wn_grid[s].values())]
    if not valid:
        print(f'  {event}: no valid stations'); continue
    opt,rmse=find_optimal_bc(valid,obs,wn_grid)
    raw=raw_bc[event]
    ds=opt[0]-raw['spd'] if opt else 0
    dd=(opt[1]-raw['dir']+180)%360-180 if opt else 0
    event_opt_bc[event]={'opt_bc':opt,'rmse':rmse,
                         'delta_spd':ds,'delta_dir':dd,
                         'raw_spd':raw['spd'],'raw_dir':raw['dir']}
    print(f'  {event}: raw={raw["spd"]:.1f}@{raw["dir"]:.0f}  '
          f'opt={opt[0]}@{opt[1]}°  Δspd={ds:+.1f}  Δdir={dd:+.0f}  RMSE={rmse:.2f}')

print()
print(f'{"Event":8s}  {"Station":8s}  {"Obs_gust":>9s}  {"Obs_sus":>8s}  '
      f'{"(a)HRRR10m":>11s}  {"(b)WN+rawBC":>12s}  {"(c)WN+LOEO":>11s}  '
      f'{"LOEO_BC":>12s}')
print('-'*100)

loeo_results={}
for holdout_event in ALL_EVENTS:
    train_events=[e for e in ALL_EVENTS if e!=holdout_event]
    # Compute mean correction delta across training events
    ds_vals=[event_opt_bc[e]['delta_spd'] for e in train_events if e in event_opt_bc]
    dd_vals=[event_opt_bc[e]['delta_dir'] for e in train_events if e in event_opt_bc]
    if not ds_vals:
        print(f'{holdout_event}: no training events'); continue
    mean_ds=sum(ds_vals)/len(ds_vals)
    mean_dd=sum(dd_vals)/len(dd_vals)

    raw=raw_bc[holdout_event]
    corr_spd=raw['spd']+mean_ds
    corr_dir=(raw['dir']+mean_dd)%360
    # Snap to nearest grid
    corr_bc=(min(SPEED_GRID,key=lambda s:abs(s-corr_spd)),
             min(DIR_GRID,key=lambda d:abs(d-corr_dir)))
    raw_bc_key_ev=(min(SPEED_GRID,key=lambda s:abs(s-raw['spd'])),
                   min(DIR_GRID,key=lambda d:abs(d-raw['dir'])))

    loeo_results[holdout_event]=[]
    for stid in EVENT_STIDS[holdout_event]:
        if stid not in obs or stid not in wn_grid: continue
        o=obs[stid]; os_=o.get('sus_est'); og=o.get('gust')
        h10=raw['hrrr10'].get(stid,{}).get('spd')
        wrb=wn_grid[stid].get(raw_bc_key_ev)
        wrc=wn_grid[stid].get(corr_bc)
        ra=round(h10/os_,3) if (h10 and os_) else None
        rb=round(wrb/os_,3) if (wrb and os_) else None
        rc=round(wrc/os_,3) if (wrc and os_) else None
        loeo_results[holdout_event].append({'stid':stid,'ra':ra,'rb':rb,'rc':rc})
        loeo_bc_str=f'{corr_bc[0]}@{corr_bc[1]}° (Δ{mean_ds:+.0f}spd,Δ{mean_dd:+.0f}dir)'
        print(f'{holdout_event:8s}  {stid:8s}  {og if og else "—":>9}  '
              f'{os_ if os_ else "—":>8}  '
              f'{ratio_str(h10,os_):>11s}  {ratio_str(wrb,os_):>12s}  '
              f'{ratio_str(wrc,os_):>11s}  {loeo_bc_str}')

print()
print('Does LOEO-corrected BC beat WN+rawBC at held-out event?')
for event,rows in loeo_results.items():
    beats=[abs(r['rc']-1)<abs(r['rb']-1) for r in rows
           if r['rc'] is not None and r['rb'] is not None]
    n=sum(beats); tot=len(beats)
    print(f'  {event}: {n}/{tot} stations improved')

print()
print('Do not write to master status — show human first.')
