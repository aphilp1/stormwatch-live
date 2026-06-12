#!/usr/bin/env python3
"""
merge_all_remaining_dem.py — Merge all remaining NEEDS_DEM rows in one pass
============================================================================
Reads dem_features.csv (already complete for 163 of 164 active stations) and
writes slope/aspect/relief_1km/repr_error_flag/terrain_class into
hrrr_error_dataset.csv for all remaining NEEDS_DEM rows.

CUUC1/woolsey_2018 is the one station not in dem_features.csv (it was added to
the database after the last DEM build). It is handled by copying the
CUUC1/thomas_2017 entry (same physical station, same lat/lon/elevation).

Terrain classification rules (from merge_dem_and_gate.py — DO NOT CHANGE):
  exposed_ridge : relief_1km >= 200 AND slope >= 4 deg
  canyon_gap    : relief_1km >= 150 AND slope <  4 deg
  valley        : relief_1km <  80
  open          : everything else
  (slope is in degrees throughout; thresholds are degrees)

Columns written to hrrr_error_dataset.csv:
  slope              — degrees (from dem_features.csv)
  aspect             — degrees, 0=N clockwise (from dem_features.csv)
  relief_1km         — m, max-min within 1km radius (from dem_features.csv)
  repr_error_flag    — elevation std within 3km radius (from dem_features.csv)
  terrain_class      — re-derived from above thresholds
  terrain_class_source — 'dem_verified' or 'dem_flag'
  dem_verified       — 'yes' or 'flag' (based on elev_qc)
  dem_elev_m         — DEM-derived elevation (m)
  elev_residual_m    — dem_elev_m - registry elev_m

Run (any Python, no conda needed — reads from pre-built dem_features.csv):
  python merge_all_remaining_dem.py
"""
import csv, shutil, os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE    = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
MAIN    = os.path.join(BASE, 'hrrr_error_dataset.csv')
DEM_CSV = os.path.join(BASE, 'dem_features.csv')

DEM_COLS = ['slope', 'aspect', 'relief_1km', 'repr_error_flag',
            'terrain_class', 'terrain_class_source', 'dem_verified',
            'dem_elev_m', 'elev_residual_m']


# ── Terrain classification (must match merge_dem_and_gate.py) ─────────────────

def classify_terrain(slope_deg, relief_m):
    """slope in degrees, relief in meters. Returns class string."""
    try:
        s = float(slope_deg)
        r = float(relief_m)
    except (TypeError, ValueError):
        return None
    if r >= 200.0 and s >= 4.0:
        return 'exposed_ridge'
    if r >= 150.0 and s < 4.0:
        return 'canyon_gap'
    if r < 80.0:
        return 'valley'
    return 'open'


# ── Load dem_features.csv ─────────────────────────────────────────────────────

dem_raw = {}
with open(DEM_CSV, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        key = (r['stid'], r['event_id'])
        dem_raw[key] = r

print(f'DEM features loaded: {len(dem_raw)} entries from {os.path.basename(DEM_CSV)}')

# Synthesize CUUC1/woolsey_2018 from CUUC1/thomas_2017 (identical coordinates)
cuuc_thomas = dem_raw.get(('CUUC1', 'thomas_2017'))
if cuuc_thomas:
    cuuc_woolsey = dict(cuuc_thomas)
    cuuc_woolsey['event_id'] = 'woolsey_2018'
    cuuc_woolsey['elev_m_reg'] = '1609.3'  # woolsey registry elevation
    cuuc_woolsey['elev_residual_m'] = str(
        round(float(cuuc_woolsey['dem_elev_m']) - 1609.3, 1))
    dem_raw[('CUUC1', 'woolsey_2018')] = cuuc_woolsey
    print(f'  Synthesized CUUC1/woolsey_2018 from CUUC1/thomas_2017 '
          f'(slope={cuuc_woolsey["slope"]}deg relief={cuuc_woolsey["relief_1km"]}m)')
else:
    print('  WARNING: CUUC1/thomas_2017 not found in dem_features.csv — '
          'CUUC1/woolsey_2018 will remain NEEDS_DEM')

print()


# ── Build merged DEM lookup (re-classify terrain) ────────────────────────────

dem_merged = {}
for (stid, eid), raw in dem_raw.items():
    slope   = raw.get('slope', '')
    relief  = raw.get('relief_1km', '')
    aspect  = raw.get('aspect', '')
    repr_ef = raw.get('repr_error_flag', '')
    elev    = raw.get('dem_elev_m', '')
    resid   = raw.get('elev_residual_m', '')
    elev_qc = raw.get('elev_qc', 'OK')

    tc = classify_terrain(slope, relief)
    if tc is None:
        continue

    if elev_qc == 'FLAG_LARGE_RESIDUAL':
        tc_src       = 'dem_flag'
        dem_verified = 'flag'
    else:
        tc_src       = 'dem_verified'
        dem_verified = 'yes'

    dem_merged[(stid, eid)] = {
        'slope':               slope,
        'aspect':              aspect,
        'relief_1km':          relief,
        'repr_error_flag':     repr_ef,
        'terrain_class':       tc,
        'terrain_class_source': tc_src,
        'dem_verified':        dem_verified,
        'dem_elev_m':          elev,
        'elev_residual_m':     resid,
    }

print(f'Terrain classified: {len(dem_merged)} stations')


# ── Load main DB ──────────────────────────────────────────────────────────────

all_rows = []
with open(MAIN, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    all_rows = list(reader)

# Ensure output columns exist
for col in DEM_COLS:
    if col not in fieldnames:
        fieldnames.append(col)

# Backup
backup = MAIN.replace('.csv', '_pre_all_remaining_dem.csv')
shutil.copy2(MAIN, backup)
print(f'Backup: {backup}')
print()


# ── Merge ─────────────────────────────────────────────────────────────────────

print('=' * 100)
print('MERGE — terrain class before -> after, per event')
print('=' * 100)

n_updated = 0
n_skipped = 0
n_already  = 0
event_counts = {}

for row in all_rows:
    if row.get('qc_flag') not in ('KEEP', 'CAUTION', 'DROP_OTHER'):
        continue
    if row.get('slope', '') != 'NEEDS_DEM':
        n_already += 1
        continue

    key = (row['stid'], row['event_id'])
    vals = dem_merged.get(key)
    if vals is None:
        print(f'  SKIP (no DEM entry): {row["stid"]}/{row["event_id"]}')
        n_skipped += 1
        continue

    slope_old = row.get('slope', '')
    tc_old    = row.get('terrain_class', '')

    for col in DEM_COLS:
        row[col] = vals[col]

    ev = row['event_id']
    event_counts[ev] = event_counts.get(ev, 0) + 1

    if tc_old != vals['terrain_class']:
        print(f'  {row["stid"]:<8} / {ev:<22}  tc: {tc_old:<18} -> {vals["terrain_class"]:<18}  '
              f'slope={vals["slope"]}deg  relief={vals["relief_1km"]}m')
    n_updated += 1


# ── Write back ────────────────────────────────────────────────────────────────

with open(MAIN, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print()
print(f'Merged DEM for {n_updated} rows across {len(event_counts)} events.')
print(f'Skipped (no DEM entry): {n_skipped}')
print(f'Already had DEM: {n_already}')
print()
print('Per-event results:')
for ev, cnt in sorted(event_counts.items()):
    print(f'  {ev}: {cnt} rows merged')


# ── Verify ────────────────────────────────────────────────────────────────────

print()
print('=' * 70)
print('VERIFICATION — NEEDS_DEM remaining in active rows')
print('=' * 70)
remaining = {}
for row in all_rows:
    if row.get('qc_flag') in ('KEEP', 'CAUTION') and row.get('slope', '') == 'NEEDS_DEM':
        remaining.setdefault(row['event_id'], []).append(row['stid'])

if remaining:
    for ev, stids in sorted(remaining.items()):
        print(f'  {ev}: {len(stids)} still NEEDS_DEM -> {stids}')
    print(f'\nTotal remaining: {sum(len(v) for v in remaining.values())}')
else:
    print('  0 NEEDS_DEM rows in active (KEEP/CAUTION) set -- ALL COMPLETE')
print()

# Terrain class distribution
tc_dist = {}
for row in all_rows:
    if row.get('qc_flag') in ('KEEP', 'CAUTION'):
        tc = row.get('terrain_class', 'unknown')
        tc_dist[tc] = tc_dist.get(tc, 0) + 1
print('Terrain class distribution (active rows):')
for tc, n in sorted(tc_dist.items()):
    print(f'  {tc:<20}: {n}')
