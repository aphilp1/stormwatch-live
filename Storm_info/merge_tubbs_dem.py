#!/usr/bin/env python3
"""
merge_tubbs_dem.py
==================
Merge DEM features (slope, aspect, relief_1km, repr_error_flag, terrain_class,
terrain_class_source, dem_verified) from hrrr_error_dataset_dem.csv into
hrrr_error_dataset.csv for all Tubbs rows with NEEDS_DEM values.

Source: hrrr_error_dataset_dem.csv (post-audit, terrain_class verified).
No HRRR or DEM re-fetch required — all values already computed.
"""
import csv, shutil, os

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
MAIN = os.path.join(BASE, 'hrrr_error_dataset.csv')
DEM  = os.path.join(BASE, 'hrrr_error_dataset_dem.csv')

DEM_COLS = ['slope', 'aspect', 'relief_1km', 'repr_error_flag',
            'terrain_class', 'terrain_class_source', 'dem_verified']

# Load DEM source for tubbs_2017
dem_vals = {}   # (stid, event_id) -> dict
with open(DEM, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('event_id') != 'tubbs_2017':
            continue
        key = (r['stid'], r['event_id'])
        dem_vals[key] = {c: r.get(c, '') for c in DEM_COLS}

print(f"DEM source rows for tubbs_2017: {len(dem_vals)}")
for (stid, eid), vals in sorted(dem_vals.items()):
    print(f"  {stid:<8} slope={vals['slope']:>6} aspect={vals['aspect']:>6} "
          f"relief={vals['relief_1km']:>6}  tc={vals['terrain_class']:<15} "
          f"dem_verified={vals['dem_verified']}")
print()

# Load main DB
all_rows = []
with open(MAIN, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        all_rows.append(r)

# Backup
backup = MAIN.replace('.csv', '_pre_tubbs_dem.csv')
shutil.copy2(MAIN, backup)
print(f"Backup: {backup}\n")

# Merge — print before/after for changed rows
print("=" * 90)
print("MERGE - slope/aspect/relief/terrain_class before -> after")
print("=" * 90)
print(f"  {'stid':<8} {'slope_old':>10} {'slope_new':>10}  {'relief_old':>10} {'relief_new':>10}  "
      f"{'tc_old':>15} {'tc_new':>15}  {'verified'}")
print("  " + "-" * 88)

n_updated = 0
for r in all_rows:
    if r.get('event_id') != 'tubbs_2017':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION', 'DROP_OTHER'):
        continue
    key = (r['stid'], r['event_id'])
    if key not in dem_vals:
        continue

    # Only update rows that currently have NEEDS_DEM
    if r.get('slope', '') != 'NEEDS_DEM':
        continue

    vals = dem_vals[key]
    slope_old = r.get('slope', '')
    relief_old = r.get('relief_1km', '')
    tc_old = r.get('terrain_class', '')

    for col in DEM_COLS:
        r[col] = vals[col]
    r['terrain_class_source'] = 'dem_verified'

    print(f"  {r['stid']:<8} {slope_old:>10} {r['slope']:>10}  "
          f"{relief_old:>10} {r['relief_1km']:>10}  "
          f"{tc_old:>15} {r['terrain_class']:>15}  {r['dem_verified']}")
    n_updated += 1

print()

# Write back
with open(MAIN, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f"Merged DEM for {n_updated} rows. Backup: {backup}")
