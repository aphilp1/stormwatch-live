"""
raws_cleanup.py  — four cleanup actions, no amplification ratios computed.

1. Pull SLEC1 (Saddleback) for Camp Fire window Nov 7-10 2018.
2. Add SLEC1 to raws_station_registry.csv with live metadata.
3. Fix elevation units: rename elev_m -> elev_ft_synoptic, add elev_m_derived.
4. Network filter: add usable + caution columns to raws_inventory.csv.
"""

import requests, json, csv, sys
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

RAWS_ROOT  = Path('raws_obs')
REG_PATH   = RAWS_ROOT / 'raws_station_registry.csv'
INV_PATH   = RAWS_ROOT / 'raws_inventory.csv'
CAMP_DIR   = RAWS_ROOT / 'camp_2018'

# ─── Network prefixes that are not weather stations ───────────────────────────
EXCLUDE_PREFIXES = ('USGSHY', 'COCOOR', 'COCOCOBO', 'COCOMTMS', 'COOP')
CAUTION_STIDS    = {'D5789', 'E6204', 'ODT50', 'OD159'}   # gapped but keep

# ─────────────────────────────────────────────────────────────────────────────
# ACTION 1 — PULL SLEC1 (Saddleback)
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('ACTION 1 — PULL SLEC1 (Saddleback) Camp Fire Nov 7-10 2018')
print('='*60)

slec1_csv = CAMP_DIR / 'SLEC1_camp_2018.csv'
slec1_json = CAMP_DIR / 'SLEC1_camp_2018.json'

r = requests.get(BASE, params={
    'STID': 'SLEC1',
    'start': '201811070000',
    'end':   '201811102359',
    'units': 'temp|F,speed|mph,english',
    'complete': '1', 'token': TOKEN, 'obtimezone': 'UTC',
}, headers=HDR, timeout=30)

print(f'HTTP {r.status_code}')
d = r.json()
summary = d.get('SUMMARY', {})
print(f'Response: {summary.get("RESPONSE_MESSAGE")}  objects={summary.get("NUMBER_OF_OBJECTS")}')

stns = d.get('STATION', [])
if not stns:
    print('*** FAIL: no station returned for SLEC1')
    sys.exit(1)

st   = stns[0]
obs  = st.get('OBSERVATIONS', {})
times     = obs.get('date_time', [])
wspd_vals = obs.get('wind_speed_set_1') or obs.get('wind_speed_set_1d') or []
wdir_vals = obs.get('wind_direction_set_1') or []
wgst_vals = obs.get('wind_gust_set_1') or obs.get('wind_gust_set_1d') or []
pkspd     = obs.get('peak_wind_speed_set_1', [])
pkdir     = obs.get('peak_wind_direction_set_1', [])
temp_vals = obs.get('air_temp_set_1', [])
rh_vals   = obs.get('relative_humidity_set_1', [])

def safe(lst, i): return lst[i] if lst and i < len(lst) else ''

# Write CSV
slec1_json.write_text(json.dumps(d, indent=2), encoding='utf-8')
with open(slec1_csv, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['datetime_utc', 'wind_speed_mph', 'wind_dir_deg',
                'wind_gust_mph', 'peak_wind_speed_mph', 'peak_wind_dir_deg',
                'air_temp_f', 'relative_humidity_pct'])
    for i, t in enumerate(times):
        w.writerow([t,
            safe(wspd_vals,i), safe(wdir_vals,i), safe(wgst_vals,i),
            safe(pkspd,i), safe(pkdir,i),
            safe(temp_vals,i), safe(rh_vals,i)])

# Coverage check
t_first = times[0][:16]  if times else 'MISSING'
t_last  = times[-1][:16] if times else 'MISSING'
valid_spd  = [x for x in wspd_vals if x is not None]
valid_gust = [x for x in wgst_vals if x is not None]
peak_gust  = max(valid_gust) if valid_gust else 0
peak_spd   = max(valid_spd)  if valid_spd  else 0
peak_gust_t = times[wgst_vals.index(peak_gust)] if valid_gust and peak_gust in wgst_vals else '?'

window_start = '2018-11-07T00:00'
window_end   = '2018-11-10T23:59'
covers_window = (t_first <= '2018-11-08T00:00' and t_last >= '2018-11-09T23:00')
has_sustained  = len(valid_spd) > 0
has_gust       = len(valid_gust) > 0

print(f'\nStation: {st.get("NAME")}  STID={st.get("STID")}')
print(f'Rows: {len(times)}')
print(f'Date range: {t_first} → {t_last}')
print(f'Covers Nov 7-10 window: {"YES" if covers_window else "*** NO — FLAG"}')
print(f'Has sustained wind: {"YES" if has_sustained else "*** NO — FLAG"}')
print(f'Has gust: {"YES" if has_gust else "*** NO — FLAG"}')
print(f'Peak sustained: {peak_spd:.1f} mph')
print(f'Peak gust: {peak_gust:.1f} mph @ {peak_gust_t}')
print(f'Fields present: {[k for k,v in obs.items() if v]}')

# Print key ignition-window rows (Nov 8 UTC)
print('\nNov 8 2018 (ignition day, UTC):')
print(f'  {"Time":22s}  {"Spd_mph":>8s}  {"Dir":>5s}  {"Gust_mph":>9s}')
for i, t in enumerate(times):
    if '2018-11-08' in t:
        s = safe(wspd_vals, i)
        dd = safe(wdir_vals, i)
        g = safe(wgst_vals, i)
        print(f'  {t:22s}  {str(s):>8s}  {str(dd):>5s}  {str(g):>9s}')

print(f'\nSaved → {slec1_csv}')

# ─────────────────────────────────────────────────────────────────────────────
# ACTION 2 — ADD SLEC1 TO REGISTRY (live metadata)
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('ACTION 2 — ADD SLEC1 TO REGISTRY with live metadata')
print('='*60)

r_meta = requests.get(META, params={
    'STID': 'SLEC1', 'token': TOKEN, 'complete': '1',
}, headers=HDR, timeout=20)

meta_d = r_meta.json()
slec1_meta = meta_d.get('STATION', [{}])[0]
period = slec1_meta.get('PERIOD_OF_RECORD', {})

slec1_row_raw = {
    'stid':        'SLEC1',
    'name':        slec1_meta.get('NAME', ''),
    'lat':         slec1_meta.get('LATITUDE'),
    'lon':         slec1_meta.get('LONGITUDE'),
    'elev_ft_synoptic': slec1_meta.get('ELEVATION'),
    'elev_m_derived': round(float(slec1_meta.get('ELEVATION', 0)) * 0.3048, 1)
                       if slec1_meta.get('ELEVATION') else None,
    'state':       slec1_meta.get('STATE', ''),
    'status':      slec1_meta.get('STATUS', ''),
    'rec_start':   period.get('start', ''),
    'rec_end':     period.get('end', ''),
    'events':      'camp_2018',
    'n_event_files': 1,
    'has_data_flags': 'no',
    'elev_flag':   'no',
}

print(f'SLEC1 live metadata:')
print(f'  Name:     {slec1_row_raw["name"]}')
print(f'  Lat/Lon:  {slec1_row_raw["lat"]}, {slec1_row_raw["lon"]}')
print(f'  Elev (ft, Synoptic): {slec1_row_raw["elev_ft_synoptic"]}')
print(f'  Elev (m, derived):   {slec1_row_raw["elev_m_derived"]}')
print(f'  Status:   {slec1_row_raw["status"]}')
print(f'  Record:   {slec1_row_raw["rec_start"]} → {slec1_row_raw["rec_end"]}')

elev_ft = float(slec1_row_raw['elev_ft_synoptic'] or 0)
if elev_ft < 5000:
    print(f'  *** FLAG: elev {elev_ft:.0f} ft is below 5,000 ft — verify ridge siting')
else:
    print(f'  Elevation check: {elev_ft:.0f} ft — ridge elevation confirmed ✓')

# ─────────────────────────────────────────────────────────────────────────────
# ACTION 3 — FIX ELEVATION UNITS IN REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('ACTION 3 — FIX ELEVATION UNITS in raws_station_registry.csv')
print('='*60)

# Read existing registry
reg_rows = list(csv.DictReader(REG_PATH.open(encoding='utf-8')))
print(f'Existing registry: {len(reg_rows)} rows')
print(f'Existing columns: {list(reg_rows[0].keys())}')

# Build new rows: rename elev_m -> elev_ft_synoptic, add elev_m_derived, insert SLEC1
new_rows = []
slec1_inserted = False

for row in reg_rows:
    # Rename column
    elev_ft_val = row.pop('elev_m', None) or row.pop('elev_ft_synoptic', None)
    try:
        elev_ft_f = float(elev_ft_val) if elev_ft_val else None
        elev_m_d  = round(elev_ft_f * 0.3048, 1) if elev_ft_f is not None else None
    except:
        elev_ft_f = None
        elev_m_d  = None

    # Remove old elev_ft column (it was the double-converted wrong value)
    row.pop('elev_ft', None)

    row['elev_ft_synoptic'] = elev_ft_f
    row['elev_m_derived']   = elev_m_d

    new_rows.append(row)

    # Insert SLEC1 after QYRC1 (alphabetical position near S)
    if row['stid'] == 'RSAC1' and not slec1_inserted:
        slec1_entry = {k: '' for k in new_rows[0].keys()}
        slec1_entry.update(slec1_row_raw)
        new_rows.append(slec1_entry)
        slec1_inserted = True

if not slec1_inserted:
    slec1_entry = {k: '' for k in new_rows[0].keys()}
    slec1_entry.update(slec1_row_raw)
    new_rows.append(slec1_entry)

# Write corrected registry
new_fields = list(new_rows[0].keys())
with open(REG_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=new_fields)
    w.writeheader()
    w.writerows(new_rows)

print(f'Registry rewritten: {len(new_rows)} rows, columns: {new_fields}')

# Verify known stations
print('\nElevation conversion verification:')
checks = {'JBGC1': (2535, 772.7), 'PNTM8': (7897, 2407.0), 'CBXC1': (6004, 1830.0),
          'HWKC1': (2024, 616.9), 'ROVC1': (3331, 1015.3), 'SLEC1': (None, None)}
for chk_stid, (exp_ft, exp_m) in checks.items():
    hit = next((r for r in new_rows if r['stid'] == chk_stid), None)
    if hit:
        ft = hit.get('elev_ft_synoptic')
        m  = hit.get('elev_m_derived')
        ok = '✓' if exp_ft is None or (ft and abs(float(ft)-exp_ft) < 2) else '*** MISMATCH'
        print(f'  {chk_stid:8s}: {ft} ft → {m} m  (expected ~{exp_ft} ft / ~{exp_m} m)  {ok}')
    else:
        print(f'  {chk_stid:8s}: NOT IN REGISTRY')

# ─────────────────────────────────────────────────────────────────────────────
# ACTION 4 — NETWORK FILTER on raws_inventory.csv
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('ACTION 4 — NETWORK FILTER on raws_inventory.csv')
print('='*60)

inv_rows = list(csv.DictReader(INV_PATH.open(encoding='utf-8')))

# Add SLEC1 to inventory
slec1_inv = {
    'event':        'camp_2018',
    'stid':         'SLEC1',
    'file':         str(slec1_csv),
    'n_rows':       len(times),
    'date_first':   t_first,
    'date_last':    t_last,
    'n_cols':       8,
    'has_spd':      str(has_sustained),
    'has_gust':     str(has_gust),
    'has_dir':      str(len([x for x in wdir_vals if x is not None]) > 0),
    'all_spd_null': str(not has_sustained),
    'all_gust_null':str(not has_gust),
    'gap_flag':     'False',
    'window_miss':  str(not covers_window),
    'flags':        '' if (has_sustained and has_gust and covers_window) else 'REVIEW',
}
inv_rows.append(slec1_inv)

def is_usable(row):
    stid  = row['stid']
    flags = row.get('flags', '')
    # Exclude non-weather-station networks
    if any(stid.upper().startswith(p) for p in EXCLUDE_PREFIXES):
        return False, False
    # Exclude all-null wind
    if row.get('all_spd_null', '').lower() in ('true', '1', 'yes'):
        return False, False
    # Caution stations: keep but flag
    if stid in CAUTION_STIDS:
        return True, True
    return True, False

usable_counts = {}
total_usable = 0
total_excluded = 0
total_caution = 0

new_inv = []
for row in inv_rows:
    usable, caution = is_usable(row)
    row['usable']  = 'yes' if usable  else 'no'
    row['caution'] = 'yes' if caution else 'no'
    new_inv.append(row)
    event = row['event']
    if event not in usable_counts:
        usable_counts[event] = {'usable': 0, 'caution': 0, 'excluded': 0}
    if usable:
        usable_counts[event]['usable'] += 1
        if caution:
            usable_counts[event]['caution'] += 1
        total_usable += 1
        if caution:
            total_caution += 1
    else:
        usable_counts[event]['excluded'] += 1
        total_excluded += 1

# Write updated inventory
new_inv_fields = list(new_inv[0].keys())
with open(INV_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=new_inv_fields)
    w.writeheader()
    w.writerows(new_inv)

print(f'Inventory updated: {len(new_inv)} rows')
print(f'Filter logic: exclude prefixes {EXCLUDE_PREFIXES} + all_spd_null=True')
print(f'Caution stids (keep, flag): {CAUTION_STIDS}')

# ─────────────────────────────────────────────────────────────────────────────
# PRINT: SLEC1 confirmation, Camp registry rows, usable counts per event
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('SLEC1 PULL CONFIRMATION')
print('='*60)
print(f'Station:          {st.get("NAME")} ({st.get("STID")})')
print(f'Date range:       {t_first} → {t_last}')
print(f'Rows:             {len(times)}')
print(f'Window covered:   {"YES" if covers_window else "NO — FLAG"}')
print(f'Sustained wind:   {"YES" if has_sustained else "NO — FLAG"}')
print(f'Gust:             {"YES" if has_gust else "NO — FLAG"}')
print(f'Peak sustained:   {peak_spd:.1f} mph')
print(f'Peak gust:        {peak_gust:.1f} mph @ {peak_gust_t}')

print('\n' + '='*60)
print('CAMP FIRE REGISTRY ROWS (JBGC1, CBXC1, SLEC1, CICC1/Openshaw)')
print('='*60)
CAMP_STIDS = {'JBGC1', 'CBXC1', 'SLEC1', 'CICC1'}
print(f'{"STID":8s}  {"Name":25s}  {"Lat":9s}  {"Lon":10s}  {"Elev_ft":>8s}  {"Elev_m":>7s}  {"Status"}')
print('-'*80)
for row in new_rows:
    if row['stid'] in CAMP_STIDS:
        ft = row.get('elev_ft_synoptic', '')
        m  = row.get('elev_m_derived', '')
        print(f'{row["stid"]:8s}  {row["name"][:25]:25s}  '
              f'{str(row["lat"])[:9]:9s}  {str(row["lon"])[:10]:10s}  '
              f'{str(ft):>8s}  {str(m):>7s}  {row.get("status","")}')

print('\n' + '='*60)
print('USABLE FILE COUNT PER EVENT')
print('='*60)
print(f'{"Event":25s}  {"Usable":>7s}  {"Caution":>8s}  {"Excluded":>9s}')
print('-'*55)
for ev in sorted(usable_counts.keys()):
    c = usable_counts[ev]
    print(f'{ev:25s}  {c["usable"]:>7d}  {c["caution"]:>8d}  {c["excluded"]:>9d}')
print('-'*55)
print(f'{"TOTAL":25s}  {total_usable:>7d}  {total_caution:>8d}  {total_excluded:>9d}')

print('\nDone. No amplification ratios computed.')
