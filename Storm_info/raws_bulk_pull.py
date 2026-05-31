"""
raws_bulk_pull.py
Download full obs CSVs for all station-event pairs in station_manifest.json.
Saves: raws_obs/{site_key}/{STID}_{site_key}.csv + .json
Skips files already downloaded.
"""
import requests, json, csv, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'
BASE  = 'https://api.synopticdata.com/v2/stations/timeseries'
HDR   = {
    'User-Agent': 'Mozilla/5.0',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=HWKC1',
    'Origin':     'https://www.weather.gov',
}

MANIFEST = Path('raws_obs/station_manifest.json')
manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

# Wind field names to try in order
WIND_FIELDS = ['wind_speed_set_1', 'wind_speed_set_1d']
GUST_FIELDS = ['wind_gust_set_1', 'wind_gust_set_1d']
DIR_FIELDS  = ['wind_direction_set_1', 'wind_direction_set_1d']

def pull_station(stid, start, end):
    r = requests.get(BASE, params={
        'STID': stid, 'showemptystations': '1',
        'units': 'temp|F,speed|mph,english',
        'start': start, 'end': end,
        'complete': '1', 'token': TOKEN, 'obtimezone': 'UTC',
    }, headers=HDR, timeout=30)
    return r

def first_valid(obs, field_list):
    for f in field_list:
        if f in obs and obs[f]:
            return obs[f], f
    return [], None

total_ok = 0
total_skip = 0
total_fail = 0
summary_rows = []

for site_key, site in manifest.items():
    site_dir = Path('raws_obs') / site_key
    site_dir.mkdir(exist_ok=True)
    stations = site.get('stations', [])
    print(f'\n{"─"*60}')
    print(f'{site_key}  ({site.get("notes","")})  {len(stations)} stations')

    for st in stations:
        stid  = st['stid']
        start = st['start']
        end   = st['end']
        fname = site_dir / f'{stid}_{site_key}'

        # Skip if already downloaded
        if (fname.with_suffix('.csv')).exists():
            print(f'  SKIP {stid:10s} (already downloaded)')
            total_skip += 1
            continue

        r = pull_station(stid, start, end)
        if r.status_code != 200:
            print(f'  FAIL {stid:10s} HTTP {r.status_code}')
            total_fail += 1
            continue

        d = r.json()
        if d.get('SUMMARY', {}).get('RESPONSE_CODE') != 1:
            print(f'  FAIL {stid:10s} {d.get("SUMMARY",{}).get("RESPONSE_MESSAGE","?")}')
            total_fail += 1
            continue

        stations_ret = d.get('STATION', [])
        if not stations_ret:
            print(f'  FAIL {stid:10s} no station in response')
            total_fail += 1
            continue

        s    = stations_ret[0]
        obs  = s.get('OBSERVATIONS', {})
        times = obs.get('date_time', [])

        wspd_vals, wspd_field = first_valid(obs, WIND_FIELDS)
        wdir_vals, _          = first_valid(obs, DIR_FIELDS)
        wgst_vals, _          = first_valid(obs, GUST_FIELDS)
        pkspd_vals = obs.get('peak_wind_speed_set_1', [])
        pkdir_vals = obs.get('peak_wind_direction_set_1', [])
        temp_vals  = obs.get('air_temp_set_1', [])
        rh_vals    = obs.get('relative_humidity_set_1', [])

        def safe(lst, i):
            return lst[i] if lst and i < len(lst) else ''

        # Write CSV
        with open(fname.with_suffix('.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['datetime_utc','wind_speed_mph','wind_dir_deg',
                        'wind_gust_mph','peak_wind_speed_mph','peak_wind_dir_deg',
                        'air_temp_f','relative_humidity_pct'])
            for i, t in enumerate(times):
                w.writerow([t,
                    safe(wspd_vals, i), safe(wdir_vals, i), safe(wgst_vals, i),
                    safe(pkspd_vals, i), safe(pkdir_vals, i),
                    safe(temp_vals, i), safe(rh_vals, i)])

        # Save raw JSON
        (fname.with_suffix('.json')).write_text(json.dumps(d, indent=2), encoding='utf-8')

        # Peak summary
        valid_spd  = [x for x in wspd_vals if x is not None]
        valid_gst  = [x for x in wgst_vals if x is not None]
        peak_gust  = max(valid_gst) if valid_gst else 0
        peak_spd   = max(valid_spd) if valid_spd else 0
        peak_t     = times[wgst_vals.index(peak_gust)] if valid_gst and peak_gust in wgst_vals else '?'

        row = {
            'site': site_key, 'stid': stid, 'name': st['name'],
            'elev_ft': st['elev_ft'], 'dist_km': st['dist_km'],
            'n_obs': len(times), 'peak_gust_mph': round(peak_gust, 1),
            'peak_spd_mph': round(peak_spd, 1), 'peak_gust_time': peak_t,
        }
        summary_rows.append(row)
        print(f'  ✓  {stid:10s} {st["name"]:25s} {len(times):3d}obs  '
              f'peak_gust={peak_gust:.0f}mph  spd={peak_spd:.0f}mph')
        total_ok += 1
        time.sleep(0.15)   # be polite

# Write summary CSV
sumpath = Path('raws_obs/pull_summary.csv')
if summary_rows:
    with open(sumpath, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        w.writeheader()
        w.writerows(summary_rows)

print(f'\n{"="*60}')
print(f'Done.  OK={total_ok}  SKIP={total_skip}  FAIL={total_fail}')
print(f'Summary → {sumpath}')
