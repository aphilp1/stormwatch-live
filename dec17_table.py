#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, requests
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = 'ad101dda8834440795ff6f4e58f9ebf9'

LOCS = {
    'KMSO':    (46.916, -114.090),
    'PointSix':(46.876, -114.082),
    'BlueMtn': (46.832, -114.216),
    'Lolo':    (46.749, -114.066),
}

gfs = {}
for name, (lat, lon) in LOCS.items():
    r = requests.get('https://historical-forecast-api.open-meteo.com/v1/forecast', params={
        'latitude': lat, 'longitude': lon,
        'start_date': '2025-12-17', 'end_date': '2025-12-17',
        'hourly': 'wind_speed_10m,wind_direction_10m,wind_gusts_10m',
        'wind_speed_unit': 'mph', 'timezone': 'UTC',
        'models': 'gfs_global',
    }, timeout=20)
    h = r.json().get('hourly', {})
    gfs[name] = [h.get('wind_speed_10m',[]), h.get('wind_direction_10m',[]), h.get('wind_gusts_10m',[])]

r2 = requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py', params={
    'station':'MSO','data':'all','year1':'2025','month1':'12','day1':'17',
    'year2':'2025','month2':'12','day2':'17','tz':'UTC','format':'onlycomma',
    'latlon':'no','missing':'M','trace':'T','direct':'no','report_type':'1',
}, timeout=20)
kmso = {}
for line in r2.text.split('\n')[1:]:
    cols = line.strip().split(',')
    if len(cols)<12 or '2025-12-17' not in (cols[1] if len(cols)>1 else ''):
        continue
    try:
        dt = datetime.fromisoformat(cols[1]); h = dt.hour
        spd  = float(cols[6])*1.15078  if cols[6]  not in ('M','') else None
        gust = float(cols[11])*1.15078 if cols[11] not in ('M','') else None
        dirn = float(cols[5])          if cols[5]  not in ('M','') else None
        pri  = abs(dt.minute-53)
        if h not in kmso or pri < kmso[h]['p']:
            kmso[h] = {'s':spd,'g':gust,'d':dirn,'p':pri}
    except:
        pass

r3 = requests.get('https://api.synopticdata.com/v2/stations/timeseries', params={
    'stid':'BLMM8','start':'202512171000','end':'202512172200',
    'vars':'wind_speed,wind_gust,wind_direction','units':'english','token':TOKEN,
}, timeout=30)
blmm8 = {}
stn = r3.json().get('STATION',[{}])[0]
obs  = stn.get('OBSERVATIONS',{})
spds  = obs.get('wind_speed_set_1',[])
gusts = obs.get('wind_gust_set_1',[])
dirs  = obs.get('wind_direction_set_1',[])
for i, t in enumerate(obs.get('date_time',[])):
    dt = datetime.fromisoformat(t.replace('Z',''))
    blmm8[dt.hour] = {
        's': spds[i]  if i < len(spds)  else None,
        'g': gusts[i] if i < len(gusts) else None,
        'd': dirs[i]  if i < len(dirs)  else None,
    }

def fv(v): return f'{v:4.0f}' if v is not None else '   M'
def fd(v): return f'{v:3.0f}' if v is not None else '  M'
def gv(name, h, idx):
    lst = gfs[name][idx]
    return lst[h] if isinstance(lst, list) and h < len(lst) else None

print()
print('December 17, 2025 -- Hourly Winds 11-21z (04-14 MST)')
print('700 hPa 12z: 25 kt / 28.8 mph from 315 NW  (OTX = TFX)')
print()
print(f'  UTC  MST  | KMSO obs         | BLMM8 obs        | GFS-KMSO    | GFS-PtSix   | GFS-BluMtn  | GFS-Lolo')
print(f'            | Dir  Spd  Gust   | Dir  Spd  Gust   | Dir  Spd    | Dir  Spd    | Dir  Spd    | Dir  Spd')
print('  ' + '-'*98)
for uh in range(11, 22):
    mh = uh - 7
    k = kmso.get(uh, {})
    b = blmm8.get(uh, {})
    print(
        f'  {uh:02d}z {mh:02d}M |'
        f'{fd(k.get("d"))}{fv(k.get("s"))}{fv(k.get("g"))}  |'
        f'{fd(b.get("d"))}{fv(b.get("s"))}{fv(b.get("g"))}  |'
        f'{fd(gv("KMSO",uh,1))}{fv(gv("KMSO",uh,0))} |'
        f'{fd(gv("PointSix",uh,1))}{fv(gv("PointSix",uh,0))} |'
        f'{fd(gv("BlueMtn",uh,1))}{fv(gv("BlueMtn",uh,0))} |'
        f'{fd(gv("Lolo",uh,1))}{fv(gv("Lolo",uh,0))}'
    )

print()
print('  KMSO  = IEM ASOS real obs, valley floor 3205ft')
print('  BLMM8 = Synoptic real obs 3412ft (hourly on :01)')
print('  GFS   = Open-Meteo historical forecast archive ~13km')
print()
print('  MPOI (Point Six 6300ft) -- BLOCKED: WRCC >30 day; not in Synoptic')
print('  TS897 (Lolo Portable)   -- BLOCKED: WRCC >30 day; wrong station in Synoptic')
print('  HRRR (3km)              -- Files on AWS S3 but need wgrib2/ecCodes (blocked Python 3.14)')
