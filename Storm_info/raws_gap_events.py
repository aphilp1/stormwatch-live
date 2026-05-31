"""
raws_gap_events.py
Pull obs for events where NIFC Hub returned 0 stations.
Uses Synoptic radius search + known station IDs.
"""
import requests, json, csv, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'
BASE  = 'https://api.synopticdata.com/v2/stations/timeseries'
META  = 'https://api.synopticdata.com/v2/stations/metadata'
HDR   = {
    'User-Agent': 'Mozilla/5.0',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=HWKC1',
    'Origin':     'https://www.weather.gov',
}

def synoptic_radius_search(lat, lon, radius_miles, start, end):
    """Use Synoptic's own radius search to find stations with data in a window."""
    r = requests.get(BASE, params={
        'radius': f'{lat},{lon},{radius_miles}',
        'start': start, 'end': end,
        'token': TOKEN, 'complete': '1',
        'units': 'temp|F,speed|mph,english',
        'limit': '50',
    }, headers=HDR, timeout=30)
    if r.status_code != 200:
        return []
    d = r.json()
    if d.get('SUMMARY', {}).get('RESPONSE_CODE') != 1:
        return []
    return d.get('STATION', [])

def pull_and_save(stid, start, end, site_key, name='', elev='', dist_km=''):
    site_dir = Path('raws_obs') / site_key
    site_dir.mkdir(exist_ok=True)
    fbase = site_dir / f'{stid}_{site_key}'
    if fbase.with_suffix('.csv').exists():
        print(f'    SKIP {stid} (exists)')
        return None

    r = requests.get(BASE, params={
        'STID': stid, 'start': start, 'end': end,
        'token': TOKEN, 'complete': '1',
        'units': 'temp|F,speed|mph,english', 'obtimezone': 'UTC',
    }, headers=HDR, timeout=30)
    if r.status_code != 200:
        return None
    d = r.json()
    stns = d.get('STATION', [])
    if not stns:
        return None
    s   = stns[0]
    obs = s.get('OBSERVATIONS', {})
    times     = obs.get('date_time', [])
    wspd_vals = obs.get('wind_speed_set_1') or obs.get('wind_speed_set_1d') or []
    wdir_vals = obs.get('wind_direction_set_1') or []
    wgst_vals = obs.get('wind_gust_set_1') or obs.get('wind_gust_set_1d') or []
    pkspd     = obs.get('peak_wind_speed_set_1', [])
    pkdir     = obs.get('peak_wind_direction_set_1', [])

    def safe(lst, i): return lst[i] if lst and i < len(lst) else ''

    fbase.with_suffix('.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
    with open(fbase.with_suffix('.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['datetime_utc','wind_speed_mph','wind_dir_deg',
                    'wind_gust_mph','peak_wind_speed_mph','peak_wind_dir_deg'])
        for i, t in enumerate(times):
            w.writerow([t, safe(wspd_vals,i), safe(wdir_vals,i),
                        safe(wgst_vals,i), safe(pkspd,i), safe(pkdir,i)])

    valid_gst = [x for x in wgst_vals if x is not None]
    peak_gust = max(valid_gst) if valid_gst else 0
    peak_spd  = max([x for x in wspd_vals if x is not None], default=0)
    return {'n': len(times), 'peak_gust': peak_gust, 'peak_spd': peak_spd}

OUT = Path('raws_obs')

# ── 1. Kincade ignition — reuse run-window stations, different time window ────
print('=== Kincade ignition phase (Oct 22-25 2019) ===')
# Known stations from kincade_run — same region
KINCADE_IGN_STIDS = ['HWKC1','KELC1','KNXC1','RSAC1','HPDC1','WISC1',
                     'COWC1','HGLC1','OAAC1','ATLC1']
for stid in KINCADE_IGN_STIDS:
    res = pull_and_save(stid, '201910220000', '201910252359', 'kincade_ign_2019')
    if res:
        print(f'  ✓ {stid:10s}  {res["n"]}obs  gust={res["peak_gust"]:.0f}mph')
    time.sleep(0.15)

# ── 2. Missoula derecho Jul 24 2024 ──────────────────────────────────────────
print('\n=== Missoula derecho Jul 24 2024 ===')
print('Synoptic radius search (46.87,-113.99, 75 miles)...')
stns = synoptic_radius_search(46.872, -113.994, 75, '202407230000', '202407252359')
print(f'  {len(stns)} stations found')
for s in stns:
    stid = s.get('STID','')
    nm   = s.get('NAME','?')
    obs  = s.get('OBSERVATIONS',{})
    n    = len(obs.get('date_time',[]))
    wgst = obs.get('wind_gust_set_1') or []
    pk   = max((x for x in wgst if x), default=0)
    # Save if not already done
    fbase = OUT / 'missoula_jul2024' / f'{stid}_missoula_jul2024'
    (OUT / 'missoula_jul2024').mkdir(exist_ok=True)
    if not fbase.with_suffix('.csv').exists():
        pull_and_save(stid, '202407230000', '202407252359', 'missoula_jul2024')
    print(f'  ✓ {stid:10s} {nm:28s} {n}obs  gust={pk:.0f}mph')
    time.sleep(0.1)

# ── 3. Boulder Chinook Jan 13-15 2021 ────────────────────────────────────────
print('\n=== Boulder Chinook Jan 13-15 2021 ===')
print('Synoptic radius search (39.94,-105.25, 60 miles)...')
stns = synoptic_radius_search(39.938, -105.250, 60, '202101130000', '202101152359')
print(f'  {len(stns)} stations found')
for s in stns:
    stid = s.get('STID','')
    nm   = s.get('NAME','?')
    obs  = s.get('OBSERVATIONS',{})
    n    = len(obs.get('date_time',[]))
    wgst = obs.get('wind_gust_set_1') or []
    pk   = max((x for x in wgst if x), default=0)
    fbase = OUT / 'boulder_chin2021' / f'{stid}_boulder_chin2021'
    (OUT / 'boulder_chin2021').mkdir(exist_ok=True)
    if not fbase.with_suffix('.csv').exists():
        pull_and_save(stid, '202101130000', '202101152359', 'boulder_chin2021')
    print(f'  ✓ {stid:10s} {nm:28s} {n}obs  gust={pk:.0f}mph')
    time.sleep(0.1)

# ── 4. Labor Day OR fires Sep 7-10 2020 ──────────────────────────────────────
print('\n=== Labor Day OR fires Sep 7-10 2020 ===')
# Three fire centers: Holiday Farm (44.27,-122.18), Beachie Creek (44.86,-122.41), Almeda (42.37,-122.93)
OR_SITES = [
    ('Holiday Farm / McKenzie River', 44.27, -122.18),
    ('Beachie Creek / Detroit', 44.86, -122.41),
    ('Almeda Drive / Medford',  42.37, -122.93),
]
seen = set()
for site_nm, lat, lon in OR_SITES:
    print(f'  {site_nm}: radius search 60mi ...')
    stns = synoptic_radius_search(lat, lon, 60, '202009070000', '202009102359')
    for s in stns:
        stid = s.get('STID','')
        if stid in seen: continue
        seen.add(stid)
        nm  = s.get('NAME','?')
        obs = s.get('OBSERVATIONS',{})
        n   = len(obs.get('date_time',[]))
        wgst= obs.get('wind_gust_set_1') or []
        pk  = max((x for x in wgst if x), default=0)
        fbase = OUT / 'labor_day_or2020' / f'{stid}_labor_day_or2020'
        (OUT / 'labor_day_or2020').mkdir(exist_ok=True)
        if not fbase.with_suffix('.csv').exists():
            pull_and_save(stid, '202009070000', '202009102359', 'labor_day_or2020')
        print(f'    ✓ {stid:10s} {nm:28s} {n}obs  gust={pk:.0f}mph')
        time.sleep(0.1)

print('\nDone.')
