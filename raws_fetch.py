#!/usr/bin/env python3
"""
raws_fetch.py — Synoptic Data API: RAWS wind obs for Missoula derecho July 24, 2024
Target: 21:00-22:00 MDT = 03:00-04:00 UTC July 25, 2024
Stations: MPOI (Point Six), BLMM8 (Blue Mountain), TS897 (Lolo Portable)
"""
import requests

API_KEY = 'Kun2M9j4GiyoIKzzLfqyRZa7smE8sdiC3cJA3ZR6ef'
TOKEN   = 'ad101dda8834440795ff6f4e58f9ebf9'   # generated from API key via /v2/auth

STATIONS = {
    'MPOI':  'Point Six',
    'BLMM8': 'Blue Mountain',
    'TS897': 'Lolo Portable',
}

# 21:00-22:00 MDT = 03:00-04:00 UTC July 25
# Pull 02:00-05:00 UTC to get full hour window with margin
params = {
    'stid':  ','.join(STATIONS.keys()),
    'start': '202407250200',
    'end':   '202407250500',
    'vars':  'wind_speed,wind_gust,wind_direction',
    'units': 'english',
    'token': TOKEN,
}

print()
print('Fetching Synoptic Data API — RAWS wind obs July 25 02:00-05:00 UTC')
print('(= July 24 20:00-23:00 MDT)')
print('=' * 60)

r = requests.get('https://api.synopticdata.com/v2/stations/timeseries', params=params, timeout=30)
print(f'Status: {r.status_code}')

if r.status_code != 200:
    print(f'FAILED: {r.text[:400]}')
    raise SystemExit(1)

data = r.json()

summary = data.get('SUMMARY', {})
if summary.get('RESPONSE_CODE') != 1:
    print(f'API error: {summary}')
    raise SystemExit(1)

stations_data = data.get('STATION', [])
print(f'Stations returned: {len(stations_data)}')

# Target: 03:00 UTC July 25 = 21:00 MDT July 24
TARGET_UTC_HOUR = 3

for stn in stations_data:
    stid = stn.get('STID', '?')
    name = STATIONS.get(stid, stid)
    elev = stn.get('ELEVATION', '?')
    lat  = stn.get('LATITUDE', '?')
    lon  = stn.get('LONGITUDE', '?')

    print()
    print(f'--- {name} ({stid})  {lat}N {lon}W  elev={elev} ft ---')

    obs = stn.get('OBSERVATIONS', {})
    times     = obs.get('date_time', [])
    speeds    = obs.get('wind_speed_set_1', [])
    gusts     = obs.get('wind_gust_set_1', [])
    dirs      = obs.get('wind_direction_set_1', [])

    if not times:
        print('  No observations returned')
        continue

    # Print all obs in window, highlight target hour
    for i, t in enumerate(times):
        spd  = speeds[i] if speeds and i < len(speeds) else None
        gust = gusts[i]  if gusts  and i < len(gusts)  else None
        dirn = dirs[i]   if dirs   and i < len(dirs)   else None

        # Parse UTC hour from ISO string (e.g. "2024-07-25T03:00:00Z")
        try:
            utc_hour = int(t[11:13])
        except Exception:
            utc_hour = -1

        mdt_hour = (utc_hour - 6) % 24
        marker = ' <== 21:00 MDT TARGET' if utc_hour == TARGET_UTC_HOUR else ''

        spd_s  = f'{spd:.1f} mph'   if spd  is not None else 'N/A'
        gust_s = f'{gust:.1f} mph'  if gust is not None else 'N/A'
        dir_s  = f'{dirn:.0f}°'     if dirn is not None else 'N/A'

        print(f'  {t}  ({mdt_hour:02d}:00 MDT)  spd={spd_s:>9}  gust={gust_s:>9}  dir={dir_s:>5}{marker}')

print()
print('=' * 60)
print('SUMMARY — 21:00 MDT (03:00 UTC) observations:')
print(f"{'Station':<20} {'Speed (mph)':>12} {'Gust (mph)':>12} {'Dir (°)':>9}")
print('-' * 56)

for stn in stations_data:
    stid = stn.get('STID', '?')
    name = STATIONS.get(stid, stid)
    obs  = stn.get('OBSERVATIONS', {})
    times  = obs.get('date_time', [])
    speeds = obs.get('wind_speed_set_1', [])
    gusts  = obs.get('wind_gust_set_1', [])
    dirs   = obs.get('wind_direction_set_1', [])

    target_row = None
    for i, t in enumerate(times):
        try:
            utc_hour = int(t[11:13])
        except Exception:
            continue
        if utc_hour == TARGET_UTC_HOUR:
            target_row = i
            break

    if target_row is None:
        print(f'  {name:<18}  no 03:00 UTC obs')
        continue

    spd  = speeds[target_row] if speeds and target_row < len(speeds) else None
    gust = gusts[target_row]  if gusts  and target_row < len(gusts)  else None
    dirn = dirs[target_row]   if dirs   and target_row < len(dirs)   else None

    spd_s  = f'{spd:.1f}'  if spd  is not None else 'N/A'
    gust_s = f'{gust:.1f}' if gust is not None else 'N/A'
    dir_s  = f'{dirn:.0f}' if dirn is not None else 'N/A'
    print(f'{name:<20} {spd_s:>12} {gust_s:>12} {dir_s:>9}')
