"""
raws_pull_nws_token.py
Pull historical RAWS observations via the NWS WRH public Synoptic token.

Access method: NWS embeds a Synoptic token in /source/wrh/apiKey.js for their
timeseries viewer. Token is domain-restricted but passes with a weather.gov Referer
header. This is a read-only, public-data access; no credentials bypassed.

Usage:
    python raws_pull_nws_token.py
Outputs: raws_obs/{STID}_{event}.json  (raw Synoptic response)
         raws_obs/{STID}_{event}.csv   (cleaned wind obs)
"""

import requests, json, csv, sys, os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'  # NWS WRH public token
BASE  = 'https://api.synopticdata.com/v2/stations/timeseries'
HDR   = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=HWKC1',
    'Origin':     'https://www.weather.gov',
}

PULLS = [
    # (STID, start_YYYYMMDDHHMM, end_YYYYMMDDHHMM, label)
    ('HWKC1', '201710080000', '201710092359', 'tubbs_2017'),
    ('JBGC1', '201811070000', '201811092359', 'camp_2018'),
    ('HWKC1', '201910230000', '201910252359', 'kincade_ignition_2019'),
    ('HWKC1', '201910260000', '201910282359', 'kincade_run_2019'),   # 27 Oct destructive run
    ('PNTM8', '202512090000', '202512122359', 'missoula_2025'),
    # Thomas Fire stations
    ('ROVC1', '201712040000', '201712062359', 'thomas_rosevalley_2017'),
    ('CUUC1', '201712040000', '201712062359', 'thomas_chuchupate_2017'),
]

OUT = Path('raws_obs')
OUT.mkdir(exist_ok=True)

for stid, start, end, label in PULLS:
    print(f'Pulling {stid} / {label} ...', end=' ')
    r = requests.get(BASE, params={
        'STID': stid, 'showemptystations': '1',
        'units': 'temp|F,speed|mph,english',
        'start': start, 'end': end,
        'complete': '1', 'token': TOKEN, 'obtimezone': 'UTC',
    }, headers=HDR, timeout=30)

    fname = f'{stid}_{label}'
    if r.status_code != 200:
        print(f'HTTP {r.status_code} — skipping')
        continue

    d = r.json()
    summary = d.get('SUMMARY', {})
    if summary.get('RESPONSE_CODE') != 1:
        print(f'API error: {summary.get("RESPONSE_MESSAGE")} — skipping')
        continue

    # Save raw JSON
    (OUT / f'{fname}.json').write_text(json.dumps(d, indent=2), encoding='utf-8')

    stns = d.get('STATION', [])
    if not stns:
        print('0 stations returned')
        continue

    st   = stns[0]
    obs  = st.get('OBSERVATIONS', {})
    times = obs.get('date_time', [])
    wspd  = obs.get('wind_speed_set_1', [None]*len(times))
    wdir  = obs.get('wind_direction_set_1', [None]*len(times))
    wgst  = obs.get('wind_gust_set_1', [None]*len(times))
    pkspd = obs.get('peak_wind_speed_set_1', [None]*len(times))
    pkdir = obs.get('peak_wind_direction_set_1', [None]*len(times))

    # Write CSV
    csvpath = OUT / f'{fname}.csv'
    with open(csvpath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['datetime_utc', 'wind_speed_mph', 'wind_dir_deg',
                    'wind_gust_mph', 'peak_wind_speed_mph', 'peak_wind_dir_deg'])
        for i, t in enumerate(times):
            w.writerow([t,
                        wspd[i] if i < len(wspd) else '',
                        wdir[i] if i < len(wdir) else '',
                        wgst[i] if i < len(wgst) else '',
                        pkspd[i] if i < len(pkspd) else '',
                        pkdir[i] if i < len(pkdir) else ''])

    # Summary
    valid_spd = [s for s in wspd if s is not None]
    valid_gst = [g for g in wgst if g is not None]
    peak_gust = max(valid_gst) if valid_gst else 'N/A'
    peak_spd  = max(valid_spd) if valid_spd else 'N/A'
    peak_gust_t = times[wgst.index(max(valid_gst))] if valid_gst else '?'
    print(f'{len(times)} obs | peak spd={peak_spd} mph | peak gust={peak_gust} mph @ {peak_gust_t}')
    print(f'    -> {csvpath}')

print('\nDone.')
