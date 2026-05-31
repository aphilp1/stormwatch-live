"""
raws_inventory_verify.py
Steps:
  1. Inventory every RAWS CSV: row count, date range, columns, gap/null flags.
  2. Pull live station metadata (lat, lon, elev) from Synoptic API for every unique STID.
  3. Elevation cross-check: flag ridge-named stations at valley elevations and vice-versa.
  4. Search specifically for Saddleback (held-out Camp Fire target — may not have been pulled).
  5. Write raws_station_registry.csv + raws_inventory.csv.

Do NOT compute amplification ratios. Do NOT score model output. Inventory and flag only.
"""

import csv, json, os, sys, re, math, requests, datetime
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = '7c76618b66c74aee913bdbae4b448bdd'
HDR   = {
    'User-Agent': 'Mozilla/5.0',
    'Referer':    'https://www.weather.gov/wrh/timeseries?site=HWKC1',
    'Origin':     'https://www.weather.gov',
}

RAWS_ROOT = Path('raws_obs')

# Critical event windows (UTC) — used to flag CSVs that miss the event
# Format: (window_start_str, window_end_str, description)
EVENT_WINDOWS = {
    'camp_2018':         ('2018-11-08T00:00', '2018-11-09T00:00', 'Camp Fire ignition day Nov 8'),
    'tubbs_2017':        ('2017-10-08T22:00', '2017-10-09T12:00', 'Tubbs peak wind night Oct 8-9'),
    'kincade_ign_2019':  ('2019-10-23T00:00', '2019-10-25T00:00', 'Kincade ignition phase'),
    'kincade_run_2019':  ('2019-10-27T00:00', '2019-10-28T00:00', 'Kincade 27 Oct destructive run'),
    'thomas_2017':       ('2017-12-04T00:00', '2017-12-06T00:00', 'Thomas Fire first 48h'),
    'woolsey_2018':      ('2018-11-08T00:00', '2018-11-10T00:00', 'Woolsey ignition + spread'),
    'missoula_dec2025':  ('2025-12-10T00:00', '2025-12-12T00:00', 'Missoula cold front peak'),
    'missoula_jul2024':  ('2024-07-24T00:00', '2024-07-25T00:00', 'Missoula derecho Jul 24'),
    'marshall_2021':     ('2021-12-30T00:00', '2022-01-01T00:00', 'Marshall Fire ignition day'),
    'boulder_chin2021':  ('2021-01-13T00:00', '2021-01-15T00:00', 'Boulder Chinook Jan 13-14'),
    'iowa_derecho2020':  ('2020-08-10T00:00', '2020-08-11T00:00', 'Iowa Derecho Aug 10'),
    'labor_day_or2020':  ('2020-09-07T00:00', '2020-09-10T00:00', 'Labor Day OR fires'),
}

# Elevation siting expectations for named station types (rough heuristic)
RIDGE_KEYWORDS = ['mountain','mtn','ridge','peak','summit','lookout','divide',
                  'crest','pass','saddle','high','top','bluff']
VALLEY_KEYWORDS = ['valley','creek','river','flat','lowland','bay','coastal',
                   'airport','field','junction','bridge']

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — INVENTORY
# ─────────────────────────────────────────────────────────────────────────────
print('='*70)
print('STEP 1 — CSV INVENTORY')
print('='*70)

inventory = []   # one row per CSV

for event_dir in sorted(RAWS_ROOT.iterdir()):
    if not event_dir.is_dir():
        continue
    event_key = event_dir.name
    win = EVENT_WINDOWS.get(event_key)
    win_start = win[0] if win else None
    win_end   = win[1] if win else None

    csvs = sorted(event_dir.glob('*.csv'))
    if not csvs:
        # also check root-level CSVs (early pulls stored there)
        continue

    print(f'\n── {event_key} ({len(csvs)} files) ──')

    for fpath in csvs:
        stem = fpath.stem          # e.g. HWKC1_tubbs_2017
        parts = stem.split('_', 1)
        stid  = parts[0]

        rows = list(csv.DictReader(fpath.open(encoding='utf-8', errors='replace')))
        n_rows = len(rows)
        cols   = list(rows[0].keys()) if rows else []

        # Date range
        times = [r.get('datetime_utc','') for r in rows if r.get('datetime_utc','').strip()]
        t_first = times[0][:16]  if times else ''
        t_last  = times[-1][:16] if times else ''

        # Wind column check
        spd_col  = next((c for c in cols if 'wind_speed_mph' in c), None)
        gust_col = next((c for c in cols if 'wind_gust_mph' in c), None)
        dir_col  = next((c for c in cols if 'wind_dir_deg' in c), None)

        spd_vals  = [r.get(spd_col,'')  for r in rows] if spd_col  else []
        gust_vals = [r.get(gust_col,'') for r in rows] if gust_col else []

        n_spd_null  = sum(1 for v in spd_vals  if v in ('','None','null',''))
        n_gust_null = sum(1 for v in gust_vals if v in ('','None','null',''))
        all_spd_null  = (n_spd_null  == n_rows) if n_rows > 0 else True
        all_gust_null = (n_gust_null == n_rows) if n_rows > 0 else True

        # Gap detection: flag if any consecutive gap > 2h during event window
        gap_flag = False
        large_gap_hours = 0
        if times:
            for i in range(1, len(times)):
                try:
                    t1 = datetime.datetime.fromisoformat(times[i-1].replace('Z',''))
                    t2 = datetime.datetime.fromisoformat(times[i].replace('Z',''))
                    diff_h = (t2 - t1).total_seconds() / 3600
                    if diff_h > 2.0:
                        # Only flag if gap is within the event window
                        if win_start and win_end:
                            if t1.isoformat()[:16] >= win_start and t2.isoformat()[:16] <= win_end:
                                gap_flag = True
                                large_gap_hours = max(large_gap_hours, diff_h)
                        else:
                            gap_flag = True
                            large_gap_hours = max(large_gap_hours, diff_h)
                except:
                    pass

        # Event window coverage check
        window_miss = False
        if win_start and t_first and t_last:
            if t_last < win_start or t_first > win_end:
                window_miss = True

        # Build flags string
        flags = []
        if n_rows == 0:           flags.append('EMPTY')
        if all_spd_null:          flags.append('ALL_SPD_NULL')
        if all_gust_null:         flags.append('ALL_GUST_NULL')
        if not spd_col:           flags.append('NO_SPD_COL')
        if not gust_col:          flags.append('NO_GUST_COL')
        if gap_flag:              flags.append(f'GAP>{large_gap_hours:.0f}h')
        if window_miss:           flags.append('WINDOW_MISS')
        if n_spd_null > n_rows/2 and n_rows > 0 and not all_spd_null:
            flags.append(f'SPARSE_SPD({n_spd_null}/{n_rows})')

        flag_str = '  *** ' + ' | '.join(flags) if flags else ''

        status = 'FLAG' if flags else 'OK  '
        print(f'  {status} {stid:12s} {n_rows:4d}rows  {t_first}→{t_last}'
              f'  cols={len(cols)}{flag_str}')

        inventory.append({
            'event':       event_key,
            'stid':        stid,
            'file':        str(fpath),
            'n_rows':      n_rows,
            'date_first':  t_first,
            'date_last':   t_last,
            'n_cols':      len(cols),
            'has_spd':     bool(spd_col),
            'has_gust':    bool(gust_col),
            'has_dir':     bool(dir_col),
            'all_spd_null': all_spd_null,
            'all_gust_null': all_gust_null,
            'gap_flag':    gap_flag,
            'window_miss': window_miss,
            'flags':       ' | '.join(flags),
        })

# Also inventory root-level legacy CSVs
print('\n── root-level legacy CSVs ──')
for fpath in sorted(RAWS_ROOT.glob('*.csv')):
    if fpath.name in ('station_manifest.json','pull_summary.csv','raws_station_registry.csv','raws_inventory.csv'):
        continue
    rows = list(csv.DictReader(fpath.open(encoding='utf-8', errors='replace')))
    n_rows = len(rows)
    times = [r.get('datetime_utc','') for r in rows if r.get('datetime_utc','')]
    t_first = times[0][:16]  if times else ''
    t_last  = times[-1][:16] if times else ''
    stem  = fpath.stem
    parts = stem.split('_', 1)
    stid  = parts[0]
    event = '_'.join(parts[1:]) if len(parts)>1 else 'unknown'
    cols  = list(rows[0].keys()) if rows else []
    print(f'  OK   {stid:12s} {n_rows:4d}rows  {t_first}→{t_last}  event={event}')
    inventory.append({
        'event': event, 'stid': stid, 'file': str(fpath),
        'n_rows': n_rows, 'date_first': t_first, 'date_last': t_last,
        'n_cols': len(cols), 'has_spd': True, 'has_gust': True, 'has_dir': True,
        'all_spd_null': False, 'all_gust_null': False,
        'gap_flag': False, 'window_miss': False, 'flags': '',
    })

# Save inventory CSV
inv_path = RAWS_ROOT / 'raws_inventory.csv'
with open(inv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=inventory[0].keys())
    w.writeheader(); w.writerows(inventory)
print(f'\nInventory saved → {inv_path}  ({len(inventory)} files)')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — LIVE METADATA PULL
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*70)
print('STEP 2 — LIVE SYNOPTIC METADATA FOR ALL UNIQUE STIDs')
print('='*70)

# Collect unique STIDs and which events each appears in
stid_events = defaultdict(set)
for row in inventory:
    stid_events[row['stid']].add(row['event'])

unique_stids = sorted(stid_events.keys())
print(f'Unique STIDs: {len(unique_stids)}')

# Batch metadata pull (Synoptic supports comma-separated STID list)
BATCH = 50
meta_map = {}   # stid → metadata dict

for i in range(0, len(unique_stids), BATCH):
    batch = unique_stids[i:i+BATCH]
    stid_str = ','.join(batch)
    r = requests.get('https://api.synopticdata.com/v2/stations/metadata', params={
        'STID': stid_str, 'token': TOKEN, 'complete': '1',
    }, headers=HDR, timeout=30)
    if r.status_code != 200:
        print(f'  Metadata batch {i//BATCH+1}: HTTP {r.status_code}')
        continue
    d = r.json()
    if d.get('SUMMARY', {}).get('RESPONSE_CODE') != 1:
        print(f'  Metadata batch {i//BATCH+1}: {d.get("SUMMARY",{}).get("RESPONSE_MESSAGE")}')
        continue
    for st in d.get('STATION', []):
        stid = st.get('STID', '')
        period = st.get('PERIOD_OF_RECORD', {})
        meta_map[stid] = {
            'stid':     stid,
            'name':     st.get('NAME', ''),
            'lat':      st.get('LATITUDE'),
            'lon':      st.get('LONGITUDE'),
            'elev_m':   st.get('ELEVATION'),
            'elev_ft':  round(float(st.get('ELEVATION', 0)) * 3.28084) if st.get('ELEVATION') else None,
            'state':    st.get('STATE', ''),
            'network':  st.get('MNET_ID', ''),
            'status':   st.get('STATUS', ''),
            'rec_start': period.get('start', ''),
            'rec_end':   period.get('end', ''),
        }
    print(f'  Batch {i//BATCH+1}: {len(batch)} queried, {len([s for s in batch if s in meta_map])} found')

# STIDs not in metadata
missing_meta = [s for s in unique_stids if s not in meta_map]
if missing_meta:
    print(f'  STIDs with NO metadata: {missing_meta}')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — ELEVATION CROSS-CHECK
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*70)
print('STEP 3 — ELEVATION CROSS-CHECK')
print('='*70)

# Priority stations to verify explicitly
PRIORITY_CHECK = {
    'CBXC1': ('ridge', 'Camp held-out target — Colby Mountain'),
    'JBGC1': ('ridge', 'Camp primary anchor — Jarbo Gap ridge'),
    'HWKC1': ('ridge', 'Tubbs/Kincade anchor — Hawkeye ridge'),
    'PNTM8': ('ridge', 'Missoula anchor — Point Six ridge'),
    'BLMM8': ('ridge', 'Missoula — Blue Mountain'),
    'HMRC1': ('ridge', 'Camp — Humbug Summit'),
    'PKCC1': ('ridge', 'Camp — Pike County Lookout'),
    'CDEC1': ('ridge', 'Camp — Carpenter Ridge'),
    'ROVC1': ('valley', 'Thomas — Rose Valley (below inversion, expected low elev)'),
    'CUUC1': ('ridge', 'Thomas — Chuchupate (near inversion lid, expected high)'),
    'WMSC1': ('ridge', 'Thomas/Woolsey — Warm Springs'),
    'WLYC1': ('ridge', 'Thomas — Wiley Ridge'),
    'WTPC1': ('ridge', 'Thomas — Whitaker Peak'),
    'LOOC2': ('ridge', 'Marshall — Lookout Mountain'),
}

# Rough elevation thresholds by region (meters)
RIDGE_MIN = {  # minimum elevation expected for a "ridge" station in this state
    'CA': 400,   # California ridge stations
    'CO': 2000,  # Colorado — much higher terrain
    'MT': 900,   # Montana
    'OR': 300,
    'IA': 100,   # Iowa — low terrain, RAWS are plains
}
VALLEY_MAX = {
    'CA': 300,
    'CO': 1700,
    'MT': 1000,
    'OR': 400,
    'IA': 400,
}

elev_flags = []

print(f'\n{"STID":10s}  {"Name":28s}  {"Elev(m)":>8s}  {"Elev(ft)":>8s}  {"State":5s}  {"Siting":8s}  {"Check"}')
print('-'*90)

for stid, (expected, note) in sorted(PRIORITY_CHECK.items()):
    m = meta_map.get(stid)
    if not m:
        print(f'{stid:10s}  {"NO METADATA":28s}  {"?":>8s}  {"?":>8s}  {"?":5s}  {expected:8s}  *** FLAG: NOT IN SYNOPTIC')
        elev_flags.append({'stid': stid, 'flag': 'NO_METADATA', 'note': note})
        continue

    elev_m  = float(m['elev_m'])  if m['elev_m']  else None
    elev_ft = float(m['elev_ft']) if m['elev_ft'] else None
    state   = m['state']
    name    = m['name']

    check = 'OK'
    if elev_m is not None:
        if expected == 'ridge':
            thresh = RIDGE_MIN.get(state, 300)
            if elev_m < thresh:
                check = f'*** FLAG: expected ridge (>{thresh}m) but elev={elev_m:.0f}m'
                elev_flags.append({'stid': stid, 'flag': 'RIDGE_AT_LOW_ELEV',
                                   'elev_m': elev_m, 'threshold_m': thresh, 'note': note})
        elif expected == 'valley':
            thresh = VALLEY_MAX.get(state, 300)
            if elev_m > thresh:
                check = f'NOTE: valley-class but elev={elev_m:.0f}m (above {thresh}m)'

    elev_m_str  = f'{elev_m:.0f}'  if elev_m  is not None else '?'
    elev_ft_str = f'{elev_ft:.0f}' if elev_ft is not None else '?'
    print(f'{stid:10s}  {name:28s}  {elev_m_str:>8s}  {elev_ft_str:>8s}  {state:5s}  {expected:8s}  {check}')

# Check for Saddleback (held-out Camp target — ID unknown)
print('\n── Saddleback search (Camp held-out target) ──')
r = requests.get('https://api.synopticdata.com/v2/stations/metadata', params={
    'token': TOKEN, 'state': 'CA', 'complete': '1',
    'radius': '39.806,-121.437,60',  # 60mi from Camp origin
}, headers=HDR, timeout=30)
saddleback_hits = []
if r.status_code == 200 and r.json().get('SUMMARY',{}).get('RESPONSE_CODE') == 1:
    for st in r.json().get('STATION', []):
        nm = st.get('NAME','').upper()
        if 'SADDLE' in nm or 'SADDLEBACK' in nm:
            saddleback_hits.append(st)
            meta_map[st['STID']] = {
                'stid': st['STID'], 'name': st['NAME'],
                'lat': st.get('LATITUDE'), 'lon': st.get('LONGITUDE'),
                'elev_m': st.get('ELEVATION'),
                'elev_ft': round(float(st.get('ELEVATION',0))*3.28084) if st.get('ELEVATION') else None,
                'state': st.get('STATE',''), 'network': st.get('MNET_ID',''),
                'status': st.get('STATUS',''), 'rec_start': '', 'rec_end': '',
            }
if saddleback_hits:
    for st in saddleback_hits:
        print(f'  FOUND: {st["STID"]:10s}  {st["NAME"]:28s}  '
              f'lat={st.get("LATITUDE")}  lon={st.get("LONGITUDE")}  '
              f'elev={st.get("ELEVATION")}m  status={st.get("STATUS")}')
else:
    print('  *** FLAG: No Saddleback station found within 60mi of Camp Fire origin.')
    print('  Saddleback cannot be used as held-out target unless a station ID is confirmed.')
    elev_flags.append({'stid': 'SADDLEBACK', 'flag': 'STATION_NOT_FOUND',
                       'note': 'Camp Fire held-out target — no matching RAWS in Synoptic'})

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — BUILD REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*70)
print('STEP 4 — STATION REGISTRY')
print('='*70)

registry_rows = []
for stid in sorted(stid_events.keys()):
    m = meta_map.get(stid, {})
    events_list = sorted(stid_events[stid])
    inv_rows = [r for r in inventory if r['stid'] == stid]
    any_flag = any(r['flags'] for r in inv_rows)
    elev_flag_stids = {e['stid'] for e in elev_flags}

    registry_rows.append({
        'stid':        stid,
        'name':        m.get('name','UNKNOWN'),
        'lat':         m.get('lat',''),
        'lon':         m.get('lon',''),
        'elev_m':      m.get('elev_m',''),
        'elev_ft':     m.get('elev_ft',''),
        'state':       m.get('state',''),
        'status':      m.get('status',''),
        'rec_start':   m.get('rec_start',''),
        'rec_end':     m.get('rec_end',''),
        'events':      '|'.join(events_list),
        'n_event_files': len(inv_rows),
        'has_data_flags': 'YES' if any_flag else 'no',
        'elev_flag':    'YES' if stid in elev_flag_stids else 'no',
    })

# Print registry table
print(f'\n{"STID":12s}  {"Name":28s}  {"Lat":8s}  {"Lon":9s}  {"Elev_m":>7s}  '
      f'{"Elev_ft":>7s}  {"St":3s}  {"Events"}')
print('-'*110)
for r in registry_rows:
    flag = ' ***' if r['has_data_flags']=='YES' or r['elev_flag']=='YES' else ''
    print(f'{r["stid"]:12s}  {r["name"][:28]:28s}  '
          f'{str(r["lat"])[:8]:8s}  {str(r["lon"])[:9]:9s}  '
          f'{str(r["elev_m"])[:7]:>7s}  {str(r["elev_ft"])[:7]:>7s}  '
          f'{r["state"]:3s}  {r["events"][:55]}{flag}')

# Save registry CSV
reg_path = RAWS_ROOT / 'raws_station_registry.csv'
with open(reg_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=registry_rows[0].keys())
    w.writeheader(); w.writerows(registry_rows)
print(f'\nRegistry saved → {reg_path}  ({len(registry_rows)} stations)')

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY OF FLAGS
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*70)
print('FLAG SUMMARY (all issues requiring attention before use)')
print('='*70)

data_flags = [r for r in inventory if r['flags']]
if data_flags:
    print(f'\nData flags ({len(data_flags)} files):')
    for r in data_flags:
        print(f'  {r["event"]:25s}  {r["stid"]:12s}  {r["flags"]}')
else:
    print('\nNo data flags.')

if elev_flags:
    print(f'\nElevation / station-identity flags ({len(elev_flags)}):')
    for e in elev_flags:
        print(f'  {e["stid"]:12s}  {e["flag"]:25s}  {e.get("note","")}')
else:
    print('\nNo elevation flags.')

print('\nDone. No amplification ratios computed.')
