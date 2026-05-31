"""
raws_gust_factors.py
Establish empirical gust factors per station-event. Usable files only.
No amplification ratios. No downstream computation.

Outputs:
  raws_obs/raws_gust_factors.csv   — per station-event
  printed: per-event median + spread, full Camp table
"""

import csv, sys, statistics
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

RAWS_ROOT  = Path('raws_obs')
INV_PATH   = RAWS_ROOT / 'raws_inventory.csv'
OUT_PATH   = RAWS_ROOT / 'raws_gust_factors.csv'

# Event windows (UTC) — compute gust factors over full CSV but note coverage
EVENT_WINDOWS = {
    'camp_2018':         ('2018-11-08T00:00', '2018-11-09T23:59'),
    'tubbs_2017':        ('2017-10-08T22:00', '2017-10-09T12:00'),
    'kincade_ign_2019':  ('2019-10-23T00:00', '2019-10-25T23:59'),
    'kincade_run_2019':  ('2019-10-27T00:00', '2019-10-28T23:59'),
    'thomas_2017':       ('2017-12-04T00:00', '2017-12-06T23:59'),
    'woolsey_2018':      ('2018-11-08T00:00', '2018-11-10T23:59'),
    'missoula_dec2025':  ('2025-12-10T00:00', '2025-12-12T23:59'),
    'missoula_jul2024':  ('2024-07-24T00:00', '2024-07-25T23:59'),
    'marshall_2021':     ('2021-12-30T00:00', '2022-01-01T23:59'),
    'boulder_chin2021':  ('2021-01-13T00:00', '2021-01-15T23:59'),
    'iowa_derecho2020':  ('2020-08-10T00:00', '2020-08-11T23:59'),
    'labor_day_or2020':  ('2020-09-07T00:00', '2020-09-10T23:59'),
}

SUSPECT_LOW  = 1.1
SUSPECT_HIGH = 2.2
CAMP_REF_STID   = 'JBGC1'
CAMP_REF_FACTOR = 1.625   # 52 gust / 32 sustained, pre-registered

# Camp stations to print in full
CAMP_FOCUS = {'JBGC1', 'CBXC1', 'SLEC1', 'CICC1'}

# ─── Load inventory ───────────────────────────────────────────────────────────
inv = [r for r in csv.DictReader(INV_PATH.open(encoding='utf-8'))
       if r.get('usable', '').lower() == 'yes']
print(f'Usable files: {len(inv)}')

# ─── Process each file ────────────────────────────────────────────────────────
results = []   # one dict per usable station-event

for row in inv:
    event   = row['event']
    stid    = row['stid']
    fpath   = Path(row['file'])
    caution = row.get('caution', 'no').lower() == 'yes'

    if not fpath.exists():
        # Try finding file under event subfolder
        alt = RAWS_ROOT / event / fpath.name
        if alt.exists():
            fpath = alt
        else:
            results.append({'event': event, 'stid': stid,
                            'status': 'FILE_NOT_FOUND', 'caution': caution})
            continue

    rows = list(csv.DictReader(fpath.open(encoding='utf-8', errors='replace')))
    if not rows:
        results.append({'event': event, 'stid': stid,
                        'status': 'EMPTY', 'caution': caution})
        continue

    cols = list(rows[0].keys())
    spd_col  = next((c for c in cols if 'wind_speed_mph'  in c), None)
    gust_col = next((c for c in cols if 'wind_gust_mph'   in c), None)
    dir_col  = next((c for c in cols if 'wind_dir_deg'    in c), None)
    time_col = 'datetime_utc'

    has_spd  = spd_col  is not None
    has_gust = gust_col is not None

    if not has_spd and not has_gust:
        results.append({'event': event, 'stid': stid,
                        'status': 'NO_WIND_COLS', 'caution': caution,
                        'has_sustained': False, 'has_gust': False})
        continue

    # Parse values
    win = EVENT_WINDOWS.get(event, ('', ''))
    win_start, win_end = win

    pairs = []          # (time, spd, gust) where both non-null, within event window
    all_gusts = []      # for peak regardless of sustained availability
    all_spds  = []

    for r in rows:
        t = r.get(time_col, '')[:16]
        in_window = (not win_start) or (win_start <= t <= win_end)

        try:
            g = float(r.get(gust_col, '') or '') if has_gust else None
        except:
            g = None
        try:
            s = float(r.get(spd_col, '')  or '') if has_spd  else None
        except:
            s = None

        if has_gust and g is not None and in_window:
            all_gusts.append((t, g))
        if has_spd and s is not None and in_window:
            all_spds.append((t, s))
        if has_spd and has_gust and s is not None and g is not None and in_window:
            if s > 0 and g >= s:   # physical: gust >= sustained
                pairs.append((t, s, g))

    peak_gust_t = peak_gust_val = peak_spd_concurrent = None
    peak_ratio  = None
    median_ratio = None
    n_pairs      = len(pairs)

    # Peak gust / concurrent sustained
    if all_gusts:
        peak_gust_t, peak_gust_val = max(all_gusts, key=lambda x: x[1])
        # Find concurrent sustained at same timestamp
        spd_at_peak = next((s for t, s in all_spds if t == peak_gust_t), None)
        if spd_at_peak and spd_at_peak > 0:
            peak_ratio = round(peak_gust_val / spd_at_peak, 3)
            peak_spd_concurrent = spd_at_peak

    # Median of per-obs gust/sustained ratios
    per_obs_ratios = [g / s for _, s, g in pairs if s > 0]
    if per_obs_ratios:
        median_ratio = round(statistics.median(per_obs_ratios), 3)

    # Peak values (for context only, NOT for amplification)
    peak_gust_mph = max((g for _, g in all_gusts), default=None) if all_gusts else None
    peak_spd_mph  = max((s for _, s in all_spds),  default=None) if all_spds  else None

    # Flags
    flags = []
    if caution:
        flags.append('CAUTION_GAP')
    if not has_gust:
        flags.append('GUST_ONLY_MISSING')
    if not has_spd:
        flags.append('SPD_ONLY_MISSING')
    if has_spd and has_gust and n_pairs == 0:
        flags.append('NO_CONCURRENT_PAIRS')
    if peak_ratio is not None:
        if peak_ratio < SUSPECT_LOW:
            flags.append(f'SUSPECT_LOW_PEAK({peak_ratio})')
        elif peak_ratio > SUSPECT_HIGH:
            flags.append(f'SUSPECT_HIGH_PEAK({peak_ratio})')
    if median_ratio is not None:
        if median_ratio < SUSPECT_LOW:
            flags.append(f'SUSPECT_LOW_MED({median_ratio})')
        elif median_ratio > SUSPECT_HIGH:
            flags.append(f'SUSPECT_HIGH_MED({median_ratio})')

    results.append({
        'event':              event,
        'stid':               stid,
        'has_sustained':      has_spd,
        'has_gust':           has_gust,
        'n_window_pairs':     n_pairs,
        'peak_gust_mph':      round(peak_gust_mph, 2) if peak_gust_mph else '',
        'peak_gust_time':     peak_gust_t or '',
        'peak_spd_concurrent':round(peak_spd_concurrent, 2) if peak_spd_concurrent else '',
        'peak_gust_factor':   peak_ratio if peak_ratio else '',
        'median_gust_factor': median_ratio if median_ratio else '',
        'caution':            caution,
        'status':             'OK' if not flags else 'FLAG',
        'flags':              ' | '.join(flags) if flags else '',
    })

# ─── Save CSV ─────────────────────────────────────────────────────────────────
fields = ['event','stid','has_sustained','has_gust','n_window_pairs',
          'peak_gust_mph','peak_gust_time','peak_spd_concurrent',
          'peak_gust_factor','median_gust_factor','caution','status','flags']
with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)
print(f'Saved → {OUT_PATH}  ({len(results)} rows)\n')

# ─── Per-event summary ────────────────────────────────────────────────────────
print('='*72)
print('PER-EVENT GUST FACTOR SUMMARY (usable files, event window only)')
print('='*72)
print(f'{"Event":25s}  {"N":>3s}  {"Median_GF":>10s}  {"Min_GF":>7s}  '
      f'{"Max_GF":>7s}  {"N_flagged":>10s}  Note')
print('-'*85)

events_ordered = [
    'camp_2018','tubbs_2017','kincade_ign_2019','kincade_run_2019',
    'thomas_2017','woolsey_2018','missoula_dec2025','missoula_jul2024',
    'marshall_2021','boulder_chin2021','iowa_derecho2020','labor_day_or2020',
]
# include legacy event keys
all_events = sorted({r['event'] for r in results})
for ev in events_ordered + [e for e in all_events if e not in events_ordered]:
    ev_rows = [r for r in results if r['event'] == ev]
    med_vals = [float(r['median_gust_factor']) for r in ev_rows
                if r.get('median_gust_factor') not in ('', None)]
    flag_n   = sum(1 for r in ev_rows if r['status'] == 'FLAG')
    no_both  = sum(1 for r in ev_rows if not r.get('has_sustained') or not r.get('has_gust'))

    if not med_vals:
        print(f'{ev:25s}  {len(ev_rows):>3d}  {"—":>10s}  {"—":>7s}  '
              f'{"—":>7s}  {flag_n:>10d}  no concurrent pairs')
        continue

    ev_median = round(statistics.median(med_vals), 3)
    ev_min    = round(min(med_vals), 3)
    ev_max    = round(max(med_vals), 3)

    note = ''
    if ev == 'camp_2018':
        note = f'ref JBGC1={CAMP_REF_FACTOR}'
    if no_both:
        note += f' | {no_both} gust-only'

    print(f'{ev:25s}  {len(ev_rows):>3d}  {ev_median:>10.3f}  {ev_min:>7.3f}  '
          f'{ev_max:>7.3f}  {flag_n:>10d}  {note}')

# ─── Camp per-station table ───────────────────────────────────────────────────
print()
print('='*72)
print('CAMP FIRE — PER-STATION GUST FACTORS (all usable, full detail)')
print(f'Reference anchor: JBGC1 peak_GF target = {CAMP_REF_FACTOR}')
print('='*72)
print(f'{"STID":8s}  {"Peak_gust":>10s}  {"Conc_spd":>9s}  {"Peak_GF":>8s}  '
      f'{"Med_GF":>7s}  {"N_pairs":>8s}  {"Status":6s}  Flags')
print('-'*90)

camp_rows = [r for r in results if r['event'] == 'camp_2018']
# Sort: focus stations first, then alphabetical
camp_rows.sort(key=lambda r: (0 if r['stid'] in CAMP_FOCUS else 1, r['stid']))

for r in camp_rows:
    pk_g  = str(r.get('peak_gust_mph','—'))
    pk_s  = str(r.get('peak_spd_concurrent','—'))
    pk_gf = str(r.get('peak_gust_factor','—'))
    md_gf = str(r.get('median_gust_factor','—'))
    npairs = str(r.get('n_window_pairs','—'))
    flags  = r.get('flags','')

    # Highlight focus stations
    marker = '>>>' if r['stid'] in CAMP_FOCUS else '   '
    print(f'{marker}{r["stid"]:8s}  {pk_g:>10s}  {pk_s:>9s}  {pk_gf:>8s}  '
          f'{md_gf:>7s}  {npairs:>8s}  {r["status"]:6s}  {flags}')

# ─── Flagged stations across all events ──────────────────────────────────────
flagged = [r for r in results if r['status'] == 'FLAG'
           and r.get('median_gust_factor') not in ('', None)]
if flagged:
    print()
    print('='*72)
    print('FLAGGED STATIONS WITH NUMERIC FACTORS (need review before use)')
    print('='*72)
    print(f'{"Event":22s}  {"STID":10s}  {"Med_GF":>7s}  {"Peak_GF":>8s}  Flags')
    print('-'*75)
    for r in sorted(flagged, key=lambda x: (x['event'], x['stid'])):
        print(f'{r["event"]:22s}  {r["stid"]:10s}  '
              f'{str(r["median_gust_factor"]):>7s}  '
              f'{str(r["peak_gust_factor"]):>8s}  {r["flags"]}')

print()
print('No amplification ratios computed. Gust factors only.')
