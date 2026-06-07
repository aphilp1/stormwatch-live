#!/usr/bin/env python3
"""
wrcc_synoptic_pull.py
=====================
Pull ROVC1 (Rose Valley II) and CUUC1 (Chuchupate) time series from the
Synoptic API as a substitute for the WRCC manual download.

Validates the obs values in hrrr_error_dataset.csv for Thomas and Woolsey
by pulling the full hourly time series and finding the peak sustained wind.

Run: conda run -n hrrr311 python wrcc_synoptic_pull.py
"""

import requests, csv, os, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'   # NWS WRH public token
BASE  = 'https://api.synopticdata.com/v2/stations/timeseries'
HDR   = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=ROVC1',
    'Origin':     'https://www.weather.gov',
}

BASE_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DB_FILE  = os.path.join(BASE_DIR, 'hrrr_error_dataset.csv')
OUT_DIR  = Path(BASE_DIR) / 'raws_obs'
OUT_DIR.mkdir(exist_ok=True)

# ── Pulls: (STID, event_id, start_UTC, end_UTC, label) ───────────────────────
# Thomas Fire: Dec 4-8 2017.  Aligned bc uses Dec-07 02Z for WMSC1, so extend to Dec 8.
# Woolsey Fire: Nov 8-12 2018.
PULLS = [
    ('ROVC1', 'thomas_2017',  '201712040000', '201712082359', 'ROVC1_thomas_2017'),
    ('CUUC1', 'thomas_2017',  '201712040000', '201712082359', 'CUUC1_thomas_2017'),
    ('ROVC1', 'woolsey_2018', '201811080000', '201811122359', 'ROVC1_woolsey_2018'),
    ('CUUC1', 'woolsey_2018', '201811080000', '201811122359', 'CUUC1_woolsey_2018'),
]

# ── Load departure-database obs for comparison ────────────────────────────────
db_obs = {}
with open(DB_FILE, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            db_obs[(r['stid'], r['event_id'])] = float(r['obs_sus_mph'])
        except (ValueError, KeyError):
            pass

# ── Pull and report ────────────────────────────────────────────────────────────
print('Synoptic time-series pull — ROVC1/CUUC1, Thomas + Woolsey')
print('=' * 65)
print()

for stid, event_id, start, end, label in PULLS:
    print(f'{label}  ({start[:8]} – {end[:8]})')

    resp = requests.get(BASE, params={
        'STID': stid, 'showemptystations': '1',
        'units': 'temp|F,speed|mph,english',
        'start': start, 'end': end,
        'complete': '1', 'token': TOKEN, 'obtimezone': 'UTC',
    }, headers=HDR, timeout=30)

    if resp.status_code != 200:
        print(f'  HTTP {resp.status_code} — skipped')
        print()
        continue

    d = resp.json()
    summary = d.get('SUMMARY', {})
    if summary.get('RESPONSE_CODE') != 1:
        print(f'  API error: {summary.get("RESPONSE_MESSAGE")} — skipped')
        print()
        continue

    stns = d.get('STATION', [])
    if not stns:
        print(f'  No station data returned')
        print()
        continue

    st   = stns[0]
    obs  = st.get('OBSERVATIONS', {})
    times = obs.get('date_time', [])
    wspd  = obs.get('wind_speed_set_1',     [None]*len(times))
    wdir  = obs.get('wind_direction_set_1', [None]*len(times))
    wgst  = obs.get('wind_gust_set_1',      [None]*len(times))

    print(f'  Station: {st.get("NAME","?")}  ({st.get("LONGITUDE","?")}, {st.get("LATITUDE","?")})')
    print(f'  Elevation: {st.get("ELEVATION","?")} ft  |  {len(times)} hourly obs')

    valid_spd = [(wspd[i], times[i]) for i in range(len(times)) if wspd[i] is not None]
    valid_gst = [(wgst[i], times[i]) for i in range(len(times)) if wgst[i] is not None]

    if valid_spd:
        pk_spd, pk_spd_t = max(valid_spd, key=lambda x: x[0])
        print(f'  Peak sustained: {pk_spd:.1f} mph  @ {pk_spd_t} UTC')
    else:
        pk_spd = None
        print(f'  Peak sustained: no data')

    if valid_gst:
        pk_gst, pk_gst_t = max(valid_gst, key=lambda x: x[0])
        print(f'  Peak gust:      {pk_gst:.1f} mph  @ {pk_gst_t} UTC')

    # Compare to departure database
    db_val = db_obs.get((stid, event_id))
    if db_val is not None and pk_spd is not None:
        delta = abs(pk_spd - db_val)
        match = 'EXACT' if delta < 1.0 else (f'close (Δ{delta:+.1f})' if delta < 5 else f'MISMATCH (Δ{delta:+.1f})')
        print(f'  DB obs_sus_mph: {db_val:.1f}  →  {match}')
    elif db_val is None:
        print(f'  DB obs_sus_mph: not in database for this event')

    # Save CSV
    csvpath = OUT_DIR / f'{label}.csv'
    with open(csvpath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['datetime_utc', 'wind_speed_mph', 'wind_dir_deg', 'wind_gust_mph'])
        for i, t in enumerate(times):
            w.writerow([t,
                        wspd[i] if i < len(wspd) else '',
                        wdir[i] if i < len(wdir) else '',
                        wgst[i] if i < len(wgst) else ''])
    print(f'  Saved: {csvpath.name}')
    print()

print('Done.')
