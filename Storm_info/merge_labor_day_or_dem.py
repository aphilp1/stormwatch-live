#!/usr/bin/env python3
"""
merge_labor_day_or_dem.py
=========================
Merge DEM features from hrrr_error_dataset_dem.csv into hrrr_error_dataset.csv
for all labor_day_or2020 rows with NEEDS_DEM values.
"""
import csv, shutil, os

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
MAIN = os.path.join(BASE, 'hrrr_error_dataset.csv')
DEM  = os.path.join(BASE, 'hrrr_error_dataset_dem.csv')

DEM_COLS = ['slope', 'aspect', 'relief_1km', 'repr_error_flag',
            'terrain_class', 'terrain_class_source', 'dem_verified']

# Load DEM source for labor_day_or2020
dem_vals = {}
with open(DEM, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('event_id') != 'labor_day_or2020':
            continue
        key = (r['stid'], r['event_id'])
        if key not in dem_vals:
            dem_vals[key] = {c: r.get(c, '') for c in DEM_COLS}

print(f'DEM source rows for labor_day_or2020: {len(dem_vals)}')
for (stid, _), vals in sorted(dem_vals.items()):
    print(f'  {stid:<8} slope={vals["slope"]:>6} aspect={vals["aspect"]:>9} '
          f'relief={vals["relief_1km"]:>6}  tc={vals["terrain_class"]:<18} '
          f'dem_verified={vals["dem_verified"]}')
print()

# Load main DB
all_rows = []
with open(MAIN, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        all_rows.append(r)

# Backup
backup = MAIN.replace('.csv', '_pre_labor_day_or_dem.csv')
shutil.copy2(MAIN, backup)
print(f'Backup: {backup}\n')

print('=' * 100)
print('MERGE - slope/aspect/relief/terrain_class before -> after')
print('=' * 100)
print(f'  {"stid":<8} {"slope_old":>10} {"slope_new":>10}  {"relief_old":>10} {"relief_new":>10}  '
      f'{"tc_old":>18} {"tc_new":>18}')
print('  ' + '-' * 95)

n_updated = 0
for r in all_rows:
    if r.get('event_id') != 'labor_day_or2020':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION', 'DROP_OTHER'):
        continue
    if r.get('slope', '') != 'NEEDS_DEM':
        continue
    key = (r['stid'], r['event_id'])
    if key not in dem_vals:
        print(f'  WARNING: no DEM for {r["stid"]}')
        continue

    vals = dem_vals[key]
    slope_old = r.get('slope', '')
    relief_old = r.get('relief_1km', '')
    tc_old = r.get('terrain_class', '')

    for col in DEM_COLS:
        r[col] = vals[col]

    print(f'  {r["stid"]:<8} {slope_old:>10} {r["slope"]:>10}  '
          f'{relief_old:>10} {r["relief_1km"]:>10}  '
          f'{tc_old:>18} {r["terrain_class"]:>18}')
    n_updated += 1

print()

# Write back
with open(MAIN, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f'Merged DEM for {n_updated} rows.')

# Verify
remaining = [r for r in all_rows
             if r.get('event_id') == 'labor_day_or2020'
             and r.get('slope', '') == 'NEEDS_DEM']
print(f'NEEDS_DEM remaining after merge: {len(remaining)}')
