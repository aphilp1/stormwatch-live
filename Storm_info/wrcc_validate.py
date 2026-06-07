#!/usr/bin/env python3
"""
wrcc_validate.py
================
Cross-validate WRCC RAWS obs against Synoptic values in hrrr_error_dataset.csv.
Loads all WRCC CSVs from wrcc_obs/{event}/, finds peak sustained + gust in the
fire-weather window, and compares to the departure-database obs.

WRCC CSV format (4 header rows, then data):
  Row 1: station name
  Rows 2-4: column labels
  Data: MM/DD/YYYY, hh:mm, Precip(mm), Wind_avg(m/s), Wind_dir(deg),
        Air_temp(C), Fuel_temp(C), RH(%), Battery, Pressure(mbar),
        Fuel_moisture, Gust_dir(deg), Gust_speed(m/s), Solar_rad(W/m2)

Run: conda run -n hrrr311 python wrcc_validate.py
"""

import csv, os, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE    = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
WRCC    = os.path.join(BASE, 'wrcc_obs')
DB_FILE = os.path.join(BASE, 'hrrr_error_dataset.csv')

MS_TO_MPH = 2.23694

# ── Event windows (LST inclusive, MM/DD/YYYY) ─────────────────────────────────
EVENTS = {
    'camp_2018':    {'start': '11/7/18',  'end': '11/9/18',  'label': 'Camp Fire'},
    'tubbs_2017':   {'start': '10/8/17',  'end': '10/10/17', 'label': 'Tubbs Fire'},
    'kincade_2019': {'start': '10/23/19', 'end': '10/27/19', 'label': 'Kincade Fire'},
    'thomas_2017':  {'start': '12/4/17',  'end': '12/8/17',  'label': 'Thomas Fire'},
    'woolsey_2018': {'start': '11/8/18',  'end': '11/12/18', 'label': 'Woolsey Fire'},
}

# ── Station name → Synoptic STID mapping ─────────────────────────────────────
# Add new entries as more WRCC files are downloaded.
NAME_TO_STID = {
    # Camp Fire (confirmed first pull)
    'jarbo gap':         'JBGC1',
    'colby mountain':    'CBXC1',
    'humburg summit':    'HMRC1',
    'humbug summit':     'HMRC1',
    'openshaw':          'PKCC1',
    # Tubbs / Kincade (confirmed first pull)
    'hawkeye':           'HWKC1',
    'atlas peak':        'ATLC1',
    'santa rosa':        'RSAC1',
    # Thomas / Woolsey (second pull targets)
    'rose valley ii':    'ROVC1',
    'rose valley 2':     'ROVC1',
    'chuchupate':        'CUUC1',
    'warm springs':      'WMSC1',
}


# ── Load departure database obs ───────────────────────────────────────────────
db = {}   # (stid, event_id) → obs_sus_mph
with open(DB_FILE, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            db[(r['stid'], r['event_id'])] = float(r['obs_sus_mph'])
        except (ValueError, KeyError):
            pass


# ── Parse one WRCC CSV ────────────────────────────────────────────────────────
def parse_wrcc(path):
    """Return (station_name, [(date_str, avg_mph, gust_mph), ...])."""
    station_name = None
    rows = []
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    if not lines:
        return None, []

    # Row 0: station name
    station_name = lines[0].split(',')[0].strip().strip(':').strip().strip('﻿')

    # Row 1 (index 1): units row — find gust column as last column containing 'm/s'
    # Col 3 is always avg wind speed (m/s); the second m/s column is gust speed.
    gust_col = 12  # default fallback
    if len(lines) > 1:
        unit_parts = [p.strip() for p in lines[1].split(',')]
        ms_cols = [i for i, u in enumerate(unit_parts) if u.lower() == 'm/s']
        if len(ms_cols) >= 2:
            gust_col = ms_cols[-1]   # last m/s column = gust speed

    min_cols = max(gust_col + 1, 5)

    for line in lines[4:]:          # skip 4 header rows
        parts = line.strip().split(',')
        if len(parts) < min_cols:
            continue
        date_str = parts[0].strip()
        if not date_str or date_str.startswith(':'):
            continue
        try:
            avg_mph  = float(parts[3])       * MS_TO_MPH
            gust_mph = float(parts[gust_col]) * MS_TO_MPH
            rows.append((date_str, avg_mph, gust_mph))
        except (ValueError, IndexError):
            continue

    return station_name, rows


def in_window(date_str, start, end):
    """True if date_str (M/D/YY or MM/DD/YYYY) falls in [start, end]."""
    from datetime import datetime
    for fmt in ('%m/%d/%y', '%m/%d/%Y'):
        try:
            d = datetime.strptime(date_str, fmt)
            s = datetime.strptime(start, fmt)
            e = datetime.strptime(end, fmt)
            return s <= d <= e
        except ValueError:
            continue
    return False


# ── Main loop ─────────────────────────────────────────────────────────────────
print('WRCC cross-validation report')
print('=' * 72)

any_event_found = False

for event_id, ev in EVENTS.items():
    event_dir = os.path.join(WRCC, event_id)
    if not os.path.isdir(event_dir):
        continue
    csvs = [f for f in os.listdir(event_dir) if f.lower().endswith('.csv')]
    if not csvs:
        continue

    any_event_found = True
    print(f'\n{ev["label"]} ({event_id})  window: {ev["start"]} – {ev["end"]}')
    print(f'  {"WRCC station":<22} {"STID":<8} {"WRCC_sus":>9} {"WRCC_gust":>10} '
          f'{"Synoptic":>9} {"match?":>7}')
    print('  ' + '-' * 68)

    for fname in sorted(csvs):
        fpath = os.path.join(event_dir, fname)
        station_name, data_rows = parse_wrcc(fpath)
        if station_name is None:
            print(f'  [could not parse {fname}]')
            continue

        # Filter to event window
        window_rows = [(d, a, g) for d, a, g in data_rows
                       if in_window(d, ev['start'], ev['end'])]

        if not window_rows:
            print(f'  {station_name:<22}  — no data in window —')
            continue

        peak_sus  = max(r[1] for r in window_rows)
        peak_gust = max(r[2] for r in window_rows)

        # Look up STID
        stid = NAME_TO_STID.get(station_name.lower())
        if stid is None:
            # Try partial match
            for key, sid in NAME_TO_STID.items():
                if key in station_name.lower() or station_name.lower() in key:
                    stid = sid
                    break

        synoptic_obs = db.get((stid, event_id)) if stid else None

        if synoptic_obs is not None:
            delta = abs(peak_sus - synoptic_obs)
            match = 'EXACT' if delta < 1.0 else (f'Δ{delta:+.1f}' if delta < 5 else f'MISMATCH Δ{delta:+.1f}')
        else:
            match = 'no DB entry' if stid else '?stid'

        stid_str = stid or '???'
        syn_str  = f'{synoptic_obs:.1f}' if synoptic_obs is not None else '  —'

        print(f'  {station_name:<22} {stid_str:<8} {peak_sus:>9.1f} {peak_gust:>10.1f} '
              f'{syn_str:>9} {match:>7}')
        print(f'    file: {fname}')

if not any_event_found:
    print('\nNo WRCC data directories found with CSV files.')
    print('Download from https://raws.dri.edu/ and place in:')
    print('  wrcc_obs/thomas_2017/   ← ROVC1 (Rose Valley II), CUUC1 (Chuchupate)')
    print('  wrcc_obs/woolsey_2018/  ← ROVC1 (Rose Valley II), optionally WMSC1')

print()
print('Done.')
