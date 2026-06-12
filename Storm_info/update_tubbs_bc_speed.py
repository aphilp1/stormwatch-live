#!/usr/bin/env python3
"""
update_tubbs_bc_speed.py
========================
Apply time-aligned bc_speed to all active Tubbs rows in hrrr_error_dataset.csv.
Same discipline as bc_dir: unconditional replacement with physically correct
(station-own-peak-hour) value. Also recomputes hrrr_coupling_frac = hrrr_10m/bc_speed.

Values sourced from time_aligned_bc.csv (already computed; no new HRRR pulls needed).
"""
import csv, shutil, os

BASE = r'C:\Users\aphil\Documents\Stormwatch\Storm_info'
DB   = os.path.join(BASE, 'hrrr_error_dataset.csv')
ALN  = os.path.join(BASE, 'time_aligned_bc.csv')

# Load aligned values for Tubbs
aligned = {}   # stid -> (bc_speed_aligned, offset_h)
with open(ALN, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('event_id') != 'tubbs_2017':
            continue
        try:
            spd = float(r['bc_speed_aligned'])
            aligned[r['stid']] = (spd, r.get('offset_h',''))
        except Exception:
            pass

print("Aligned bc_speed values from time_aligned_bc.csv:")
for stid, (spd, off) in sorted(aligned.items()):
    print(f"  {stid:<8} bc_speed_aligned={spd:.2f}  offset_h={off}")
print()

# Load DB
all_rows = []
with open(DB, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        all_rows.append(r)

# Backup
backup = DB.replace('.csv', '_pre_tubbs_bc_speed.csv')
shutil.copy2(DB, backup)
print(f"Backup: {backup}")

# Print before/after
print()
print("=" * 75)
print("BEFORE / AFTER — bc_speed and hrrr_coupling_frac")
print("=" * 75)
print(f"  {'stid':<8} {'hrrr_10m':>9} {'obs':>7} {'bc_OLD':>8} {'bc_NEW':>8} {'cf_OLD':>8} {'cf_NEW':>8}  note")
print("  " + "-" * 75)

n_updated = 0
for r in all_rows:
    if r.get('event_id') != 'tubbs_2017':
        continue
    if r.get('qc_flag') not in ('KEEP', 'CAUTION'):
        continue
    stid = r['stid']
    if stid not in aligned:
        continue

    bc_old = float(r['bc_speed']) if r.get('bc_speed') not in ('', 'nan', 'NaN') else None
    h10    = float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph') not in ('', 'nan') else None
    obs    = float(r['obs_sus_mph']) if r.get('obs_sus_mph') not in ('', 'nan') else None
    bc_new, off = aligned[stid]

    cf_old = h10 / bc_old if (h10 and bc_old) else None
    cf_new = h10 / bc_new if (h10 and bc_new) else None

    note = ''
    if bc_old is not None and abs(bc_new - bc_old) > 10:
        note = f'LARGE_SHIFT({bc_new-bc_old:+.1f})'

    print(f"  {stid:<8} {h10 or 0:>9.2f} {obs or 0:>7.1f} {bc_old or 0:>8.2f} "
          f"{bc_new:>8.2f} {cf_old or 0:>8.4f} {cf_new or 0:>8.4f}  {note}")

    # Update
    r['bc_speed'] = f'{bc_new:.2f}'
    if cf_new is not None:
        r['hrrr_coupling_frac'] = f'{cf_new:.4f}'
    n_updated += 1

print()

# Write back
with open(DB, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

print(f"Updated bc_speed + hrrr_coupling_frac for {n_updated} Tubbs rows.")
print(f"Backup at: {backup}")
