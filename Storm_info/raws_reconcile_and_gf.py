"""
raws_reconcile_and_gf.py
Step 0: Reconcile 7 legacy flat CSVs in raws_obs\ root.
Step 1: Gust-factor analysis from event subfolders only, usable=True.
No amplification ratios.
"""

import csv, sys, shutil, statistics
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

RAWS_ROOT   = Path('raws_obs')
INV_PATH    = RAWS_ROOT / 'raws_inventory.csv'
GF_PATH     = RAWS_ROOT / 'raws_gust_factors.csv'
LEGACY_DIR  = RAWS_ROOT / '_legacy_flat'

EVENT_WINDOWS = {
    'camp_2018':        ('2018-11-08T00:00', '2018-11-09T23:59'),
    'tubbs_2017':       ('2017-10-08T22:00', '2017-10-09T12:00'),
    'kincade_ign_2019': ('2019-10-23T00:00', '2019-10-25T23:59'),
    'kincade_run_2019': ('2019-10-27T00:00', '2019-10-28T23:59'),
    'thomas_2017':      ('2017-12-04T00:00', '2017-12-06T23:59'),
    'woolsey_2018':     ('2018-11-08T00:00', '2018-11-10T23:59'),
    'missoula_dec2025': ('2025-12-10T00:00', '2025-12-12T23:59'),
    'missoula_jul2024': ('2024-07-24T00:00', '2024-07-25T23:59'),
    'marshall_2021':    ('2021-12-30T00:00', '2022-01-01T23:59'),
    'boulder_chin2021': ('2021-01-13T00:00', '2021-01-15T23:59'),
    'iowa_derecho2020': ('2020-08-10T00:00', '2020-08-11T23:59'),
    'labor_day_or2020': ('2020-09-07T00:00', '2020-09-10T23:59'),
}

SUSPECT_LOW  = 1.1
SUSPECT_HIGH = 2.2
CAMP_FOCUS   = {'JBGC1','CBXC1','SLEC1','CICC1'}

def row_count_and_range(fpath):
    rows = list(csv.DictReader(fpath.open(encoding='utf-8', errors='replace')))
    times = [r.get('datetime_utc','')[:16] for r in rows if r.get('datetime_utc','').strip()]
    return len(rows), (times[0] if times else ''), (times[-1] if times else '')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 0 — RECONCILE LEGACY FLAT FILES
# ═══════════════════════════════════════════════════════════════════════════════
print('='*70)
print('STEP 0 — RECONCILE LEGACY FLAT CSVs')
print('='*70)

LEGACY_DIR.mkdir(exist_ok=True)

# Find root-level CSVs (not inventory/registry/summary/gust files)
SKIP_NAMES = {'raws_inventory.csv','raws_station_registry.csv',
              'pull_summary.csv','raws_gust_factors.csv','station_manifest.json'}
legacy_files = [f for f in RAWS_ROOT.glob('*.csv') if f.name not in SKIP_NAMES]
print(f'Root-level legacy CSVs found: {len(legacy_files)}')

moves   = []   # (legacy_path, action, matched_subfolder_path, note)
no_sub  = []   # files with no subfolder match → move into event folder

for lf in sorted(legacy_files):
    stid = lf.stem.split('_')[0]  # e.g. HWKC1 from HWKC1_tubbs_2017

    # Search all event subfolders for a file with matching STID
    matches = []
    for ev_dir in sorted(RAWS_ROOT.iterdir()):
        if not ev_dir.is_dir() or ev_dir.name.startswith('_'):
            continue
        for sf in ev_dir.glob(f'{stid}_*.csv'):
            matches.append(sf)

    if not matches:
        no_sub.append(lf)
        print(f'  NO SUBFOLDER MATCH: {lf.name} → needs manual placement')
        continue

    # Pick best match: prefer exact event-key match, else first
    leg_n, leg_t0, leg_t1 = row_count_and_range(lf)
    best = None
    best_score = -1
    for sf in matches:
        sf_n, sf_t0, sf_t1 = row_count_and_range(sf)
        score = sf_n  # prefer more rows
        if score > best_score:
            best_score = score
            best = (sf, sf_n, sf_t0, sf_t1)

    sf_path, sf_n, sf_t0, sf_t1 = best

    # Compare
    if sf_n >= leg_n:
        note = f'subfolder has {sf_n} rows vs legacy {leg_n} — subfolder is complete/superset'
        action = 'ARCHIVE_LEGACY'
    else:
        note = f'subfolder has {sf_n} rows vs legacy {leg_n} — legacy has MORE rows (inspect)'
        action = 'ARCHIVE_LEGACY_NOTE'

    moves.append((lf, action, sf_path, note))

print()
print(f'{"Legacy file":40s}  {"Action":20s}  {"Matched subfolder":45s}')
print('-'*115)
for lf, action, sf_path, note in moves:
    print(f'  {lf.name:38s}  {action:20s}  {sf_path.relative_to(RAWS_ROOT)}')
    print(f'    {note}')

# Execute moves to _legacy_flat_
print()
for lf, action, sf_path, note in moves:
    dest = LEGACY_DIR / lf.name
    shutil.move(str(lf), str(dest))
    # Also move companion JSON if present
    json_src = lf.with_suffix('.json')
    if json_src.exists():
        shutil.move(str(json_src), str(LEGACY_DIR / json_src.name))
    print(f'  MOVED → _legacy_flat_/{lf.name}')

for lf in no_sub:
    print(f'  SKIPPED (no match): {lf.name}')

# Update inventory: mark legacy entries as archived
inv_rows = list(csv.DictReader(INV_PATH.open(encoding='utf-8')))

# Event keys that correspond to the legacy root files (from inventory)
LEGACY_EVENT_KEYS = {
    'thomas_chuchupate_2017', 'kincade_ignition_2019',
    'thomas_rosevalley_2017', 'missoula_2025',
}
archived_stids = {lf.stem.split('_')[0] for lf, _, _, _ in moves}

updated_inv = []
n_archived = 0
for row in inv_rows:
    fpath = Path(row.get('file',''))
    # Mark as archived if file is now in _legacy_flat_ or event key is a legacy alias
    is_legacy_event = row['event'] in LEGACY_EVENT_KEYS
    is_root_file    = not any(part in str(fpath) for part in
                              [f'\\{e}\\' for e in EVENT_WINDOWS.keys()])
    # More precise: file was in root (no subfolder component matching an event key)
    in_root = RAWS_ROOT / fpath.name == fpath or \
              str(fpath).count('\\') <= str(RAWS_ROOT).count('\\') + 1

    if row['stid'] in archived_stids and (is_legacy_event or in_root):
        row['usable']   = 'archived'
        row['caution']  = 'no'
        row['flags']    = (row.get('flags','') + ' | MOVED_TO_LEGACY_FLAT').strip(' | ')
        n_archived += 1
    updated_inv.append(row)

fields = list(updated_inv[0].keys())
with open(INV_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(updated_inv)

print(f'\nInventory updated: {n_archived} entries marked usable=archived')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — COUNT USABLE FROM EVENT SUBFOLDERS ONLY
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*70)
print('STEP 1 — USABLE FILE COUNT FROM EVENT SUBFOLDERS ONLY')
print('='*70)

# Load updated inventory
inv_rows = list(csv.DictReader(INV_PATH.open(encoding='utf-8')))

# Only usable=yes files whose path is inside an event subfolder
def in_event_subfolder(fpath_str):
    p = Path(fpath_str)
    # Must have an event folder component (parent name is an event key)
    return p.parent.name in EVENT_WINDOWS

usable = [r for r in inv_rows
          if r.get('usable','').lower() == 'yes'
          and in_event_subfolder(r.get('file',''))]

print(f'Usable files from event subfolders: {len(usable)}')
if len(usable) > 172:
    print(f'*** STOP: {len(usable)} > 172 — legacy duplicate leaked in. Investigate.')
    sys.exit(1)

# Per-event breakdown
from collections import Counter
ev_counts = Counter(r['event'] for r in usable)
print()
for ev in sorted(ev_counts):
    print(f'  {ev:25s}: {ev_counts[ev]}')

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2+3+4+5 — GUST FACTOR ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('='*70)
print('STEPS 2-5 — GUST FACTOR ANALYSIS')
print('='*70)

results = []

for row in usable:
    event   = row['event']
    stid    = row['stid']
    fpath   = Path(row['file'])
    caution = row.get('caution','no').lower() == 'yes'

    if not fpath.exists():
        results.append({'event':event,'stid':stid,'status':'FILE_NOT_FOUND'})
        continue

    obs = list(csv.DictReader(fpath.open(encoding='utf-8', errors='replace')))
    if not obs:
        results.append({'event':event,'stid':stid,'status':'EMPTY'})
        continue

    cols = list(obs[0].keys())
    spd_col  = next((c for c in cols if 'wind_speed_mph'  in c), None)
    gust_col = next((c for c in cols if 'wind_gust_mph'   in c), None)
    dir_col  = next((c for c in cols if 'wind_dir_deg'    in c), None)

    has_spd  = spd_col  is not None
    has_gust = gust_col is not None

    win_start, win_end = EVENT_WINDOWS.get(event, ('',''))

    all_gusts, all_spds, pairs = [], [], []

    for r in obs:
        t = r.get('datetime_utc','')[:16]
        in_win = (not win_start) or (win_start <= t <= win_end)
        try:
            g = float(r.get(gust_col,'') or '') if has_gust else None
        except: g = None
        try:
            s = float(r.get(spd_col,'')  or '') if has_spd  else None
        except: s = None

        if has_gust and g is not None and in_win:
            all_gusts.append((t, g))
        if has_spd  and s is not None and in_win:
            all_spds.append((t, s))
        if has_spd and has_gust and s is not None and g is not None and in_win:
            if s > 0 and g >= s:
                pairs.append((t, s, g))

    # Peak gust and concurrent sustained
    peak_gust_t = peak_gust_val = peak_spd_conc = peak_ratio = None
    if all_gusts:
        peak_gust_t, peak_gust_val = max(all_gusts, key=lambda x: x[1])
        spd_at_peak = next((s for t,s in all_spds if t == peak_gust_t), None)
        if spd_at_peak and spd_at_peak > 0:
            peak_spd_conc = spd_at_peak
            peak_ratio    = round(peak_gust_val / spd_at_peak, 3)

    # Median of per-obs gust/sustained ratios (within event window)
    per_obs = [g/s for _,s,g in pairs if s > 0]
    median_ratio = round(statistics.median(per_obs), 3) if per_obs else None

    peak_gust_mph = max((g for _,g in all_gusts), default=None)
    peak_spd_mph  = max((s for _,s in all_spds),  default=None)

    flags = []
    if caution:                               flags.append('CAUTION_GAP')
    if not has_spd:                           flags.append('NO_SPD_COL')
    if not has_gust:                          flags.append('NO_GUST_COL')
    if has_spd and has_gust and not pairs:    flags.append('NO_CONCURRENT_PAIRS')
    if peak_ratio is not None:
        if peak_ratio < SUSPECT_LOW:          flags.append(f'SUSPECT_LOW_PEAK')
        elif peak_ratio > SUSPECT_HIGH:       flags.append(f'SUSPECT_HIGH_PEAK')
    if median_ratio is not None:
        if median_ratio < SUSPECT_LOW:        flags.append(f'SUSPECT_LOW_MED')
        elif median_ratio > SUSPECT_HIGH:     flags.append(f'SUSPECT_HIGH_MED')

    results.append({
        'event':               event,
        'stid':                stid,
        'has_sustained':       has_spd,
        'has_gust':            has_gust,
        'n_window_pairs':      len(pairs),
        'peak_gust_mph':       round(peak_gust_mph, 2) if peak_gust_mph is not None else '',
        'peak_gust_time':      peak_gust_t or '',
        'peak_spd_concurrent': round(peak_spd_conc, 2) if peak_spd_conc is not None else '',
        'peak_gust_factor':    peak_ratio if peak_ratio is not None else '',
        'median_gust_factor':  median_ratio if median_ratio is not None else '',
        'caution':             caution,
        'status':              'FLAG' if flags else 'OK',
        'flags':               ' | '.join(flags),
    })

# Save
gf_fields = ['event','stid','has_sustained','has_gust','n_window_pairs',
             'peak_gust_mph','peak_gust_time','peak_spd_concurrent',
             'peak_gust_factor','median_gust_factor','caution','status','flags']
with open(GF_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=gf_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)
print(f'Saved → {GF_PATH}  ({len(results)} rows)\n')

# ─── Per-event summary ────────────────────────────────────────────────────────
print('='*70)
print('PER-EVENT GUST FACTOR SUMMARY')
print('='*70)
print(f'{"Event":25s}  {"N":>3s}  {"Med_GF":>7s}  {"Min":>6s}  {"Max":>6s}  '
      f'{"Flagged":>7s}  Note')
print('-'*75)

for ev in sorted(ev_counts.keys()):
    ev_rows = [r for r in results if r['event'] == ev]
    meds = [float(r['median_gust_factor']) for r in ev_rows
            if r.get('median_gust_factor') not in ('', None)]
    flags_n = sum(1 for r in ev_rows if r['status'] == 'FLAG')

    if not meds:
        print(f'{ev:25s}  {len(ev_rows):>3d}  {"—":>7s}  {"—":>6s}  {"—":>6s}  '
              f'{flags_n:>7d}  no pairs')
        continue

    ev_med = statistics.median(meds)
    note = ''
    if ev == 'camp_2018':
        note = f'anchor JBGC1=1.625'

    print(f'{ev:25s}  {len(ev_rows):>3d}  {ev_med:>7.3f}  {min(meds):>6.3f}  '
          f'{max(meds):>6.3f}  {flags_n:>7d}  {note}')

# ─── Full Camp table ──────────────────────────────────────────────────────────
print()
print('='*70)
print('CAMP FIRE — FULL PER-STATION TABLE (usable, event window)')
print(f'Pre-registered anchor: JBGC1 peak_GF = 1.625  (52 gust / 32 sustained)')
print('='*70)
print(f'{"":3s}{"STID":8s}  {"Peak_G":>7s}  {"Conc_S":>7s}  {"PeakGF":>7s}  '
      f'{"Med_GF":>7s}  {"N_pairs":>7s}  {"Status":6s}  Flags')
print('-'*85)

camp = [r for r in results if r['event'] == 'camp_2018']
camp.sort(key=lambda r: (0 if r['stid'] in CAMP_FOCUS else 1, r['stid']))

for r in camp:
    mk = '>>>' if r['stid'] in CAMP_FOCUS else '   '
    pg = f'{r["peak_gust_mph"]:.1f}'        if r['peak_gust_mph']        != '' else '—'
    cs = f'{r["peak_spd_concurrent"]:.1f}'  if r['peak_spd_concurrent']  != '' else '—'
    pf = f'{r["peak_gust_factor"]:.3f}'     if r['peak_gust_factor']     != '' else '—'
    mf = f'{r["median_gust_factor"]:.3f}'   if r['median_gust_factor']   != '' else '—'
    np = str(r['n_window_pairs'])
    print(f'{mk}{r["stid"]:8s}  {pg:>7s}  {cs:>7s}  {pf:>7s}  '
          f'{mf:>7s}  {np:>7s}  {r["status"]:6s}  {r["flags"]}')

# ─── All flagged stations ─────────────────────────────────────────────────────
flagged = [r for r in results
           if r['status'] == 'FLAG' and r.get('median_gust_factor') not in ('',None)]
if flagged:
    print()
    print('='*70)
    print('FLAGGED STATIONS (review before use in BC sweep)')
    print('='*70)
    print(f'{"Event":22s}  {"STID":10s}  {"Med_GF":>7s}  {"Peak_GF":>8s}  Flags')
    print('-'*75)
    for r in sorted(flagged, key=lambda x:(x['event'],x['stid'])):
        print(f'{r["event"]:22s}  {r["stid"]:10s}  '
              f'{str(r["median_gust_factor"]):>7s}  '
              f'{str(r["peak_gust_factor"]):>8s}  {r["flags"]}')

print()
print('No amplification ratios computed. Gust factors established only.')
