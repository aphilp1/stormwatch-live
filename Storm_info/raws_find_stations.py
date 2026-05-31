"""
raws_find_stations.py
Query NIFC ArcGIS Hub to find all RAWS stations within radius of each fire origin,
then verify each exists in Synoptic, then write a master station manifest.
"""
import requests, json, math, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'
HDR_SYNOPTIC = {
    'User-Agent': 'Mozilla/5.0',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=HWKC1',
    'Origin':     'https://www.weather.gov',
}
NIFC_DATASET = 'a6c5737d0c8b4e3cb1b3e9729a962269'

# All study sites — (name, lat, lon, radius_km, event_start, event_end, notes)
SITES = [
    # NorCal fire-wind events
    ('camp_2018',        39.806, -121.437, 60, '201811070000', '201811102359', 'Camp Fire origin Pulga'),
    ('tubbs_2017',       38.581, -122.693, 60, '201710080000', '201710102359', 'Tubbs Fire origin Calistoga'),
    ('kincade_ign_2019', 38.793, -122.769, 60, '201910220000', '201910252359', 'Kincade ignition phase'),
    ('kincade_run_2019', 38.793, -122.769, 60, '201910260000', '201910282359', 'Kincade 27 Oct destructive run'),
    # SoCal
    ('thomas_2017',      34.414, -119.003, 80, '201712030000', '201712082359', 'Thomas Fire Ventura'),
    ('woolsey_2018',     34.170, -118.940, 60, '201811080000', '201811122359', 'Woolsey Fire'),
    # MT
    ('missoula_dec2025', 47.041, -113.986, 60, '202512090000', '202512132359', 'Missoula cold-front Dec 2025'),
    ('missoula_jul2024', 46.872, -113.994, 60, '202407230000', '202407252359', 'Missoula derecho Jul 2024'),
    # CO
    ('marshall_2021',    39.938, -105.111, 60, '202112290000', '202201012359', 'Marshall Fire Boulder'),
    ('boulder_chin2021', 39.938, -105.250, 60, '202101130000', '202101152359', 'Boulder Chinook Jan 2021'),
    # IA / Midwest
    ('iowa_derecho2020', 42.010,  -95.860, 80, '202008090000', '202008112359', 'Iowa Derecho Aug 2020'),
    # OR
    ('labor_day_or2020', 44.500, -122.100, 80, '202009070000', '202009102359', 'Labor Day 2020 OR fires'),
]

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p = math.pi / 180
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = math.sin(dlat/2)**2 + math.cos(lat1*p)*math.cos(lat2*p)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def find_nifc_stations(lat, lon, radius_km):
    """Bounding-box query on NIFC ArcGIS Hub, then filter by haversine."""
    deg = radius_km / 111.0
    bbox_where = (f"Latitude >= {lat-deg} AND Latitude <= {lat+deg} AND "
                  f"Longitude >= {lon-deg} AND Longitude <= {lon+deg} AND Status = 'A'")
    r = requests.get(
        f'https://opendata.arcgis.com/datasets/{NIFC_DATASET}_1.geojson',
        params={'outSR': '4326', 'where': bbox_where, 'outFields': '*'},
        timeout=20
    )
    if r.status_code != 200:
        return []
    feats = r.json().get('features', [])
    result = []
    for f in feats:
        p = f.get('properties', {})
        slat = p.get('Latitude')
        slon = p.get('Longitude')
        if slat is None or slon is None:
            continue
        d = haversine_km(lat, lon, slat, slon)
        if d <= radius_km:
            result.append({
                'stid':        p.get('MesoWestStationID', ''),
                'name':        p.get('StationName', ''),
                'nwsid':       p.get('NWSID', ''),
                'elev_ft':     p.get('Elevation'),
                'lat':         slat,
                'lon':         slon,
                'agency':      p.get('Agency', ''),
                'dist_km':     round(d, 1),
                'site_desc':   p.get('SiteDescription', ''),
            })
    result.sort(key=lambda x: x['dist_km'])
    return result

def verify_synoptic(stid, start, end):
    """Check if station has actual obs in the event window."""
    if not stid:
        return False, 0
    r = requests.get('https://api.synopticdata.com/v2/stations/timeseries', params={
        'STID': stid, 'start': start, 'end': end,
        'token': TOKEN, 'complete': '1',
    }, headers=HDR_SYNOPTIC, timeout=15)
    if r.status_code != 200:
        return False, 0
    d = r.json()
    stns = d.get('STATION', [])
    if not stns:
        return False, 0
    obs = stns[0].get('OBSERVATIONS', {})
    n = len(obs.get('date_time', []))
    return n > 0, n

# Master manifest
manifest = {}
OUT = Path('raws_obs')
OUT.mkdir(exist_ok=True)

for site_key, lat, lon, radius_km, ev_start, ev_end, notes in SITES:
    print(f'\n{"="*60}')
    print(f'{site_key}  ({notes})')
    print(f'Center: {lat},{lon}  radius={radius_km}km')
    stations = find_nifc_stations(lat, lon, radius_km)
    print(f'NIFC stations found: {len(stations)}')

    confirmed = []
    for st in stations:
        stid = st['stid']
        if not stid:
            continue
        has_data, n_obs = verify_synoptic(stid, ev_start, ev_end)
        status = f'{n_obs} obs' if has_data else 'NO DATA'
        flag = '✓' if has_data else ' '
        print(f'  {flag} {stid:10s} {st["name"]:25s} {st["dist_km"]:5.1f}km  elev={st["elev_ft"]}ft  {status}')
        if has_data:
            confirmed.append({**st, 'n_obs': n_obs, 'start': ev_start, 'end': ev_end})

    manifest[site_key] = {
        'notes': notes, 'lat': lat, 'lon': lon,
        'start': ev_start, 'end': ev_end,
        'stations': confirmed,
    }

# Save manifest
mpath = OUT / 'station_manifest.json'
mpath.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'\n\nManifest saved → {mpath}')
print(f'Total confirmed station-event pairs: {sum(len(v["stations"]) for v in manifest.values())}')
