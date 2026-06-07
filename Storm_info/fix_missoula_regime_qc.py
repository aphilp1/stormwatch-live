#!/usr/bin/env python3
"""
fix_missoula_regime_qc.py

Two changes to all 8 missoula_dec2025 rows:
  1. synoptic_regime: frontal_passage -> continental_downslope
     Physical grounds: NW flow descending west face of Continental Divide;
     foehn mechanism; cold-pool decoupled downslope windstorm (same class
     as boulder_chin2021 / chinook_frontrange).

  2. qc_flag: KEEP -> DROP_DATE_ERROR
     Database captured Dec 9-11 frontal event, not the Dec 17 2025 downslope
     event. Valley RAWS (KMSO 18-22 mph) were sheltered by cold pool; elevated
     sites hit 88-90 mph. Pending Synoptic re-pull at Dec 17 dates.
     Row may be high-value once corrected: if PNTM8 (ridge) obs available,
     this is a terrain-channeling departure case comparable to Camp Fire ridge stations.

Applied to both hrrr_error_dataset.csv and hrrr_error_dataset_dem.csv.
"""

import csv, os, shutil

BASE  = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
FILES = [
    os.path.join(BASE, "hrrr_error_dataset.csv"),
    os.path.join(BASE, "hrrr_error_dataset_dem.csv"),
]

EVENT_ID   = "missoula_dec2025"
NEW_REGIME = "continental_downslope"
NEW_FLAG   = "DROP_DATE_ERROR"
NEW_REASON = (
    "date error: captured Dec 9-11 frontal event; true event Dec 17 2025 "
    "(NW foehn/downslope, 88-90 mph at elevated sites, valley sheltered by cold pool); "
    "regime corrected to continental_downslope; pending Synoptic re-pull for Dec 17 obs"
)

for path in FILES:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows   = list(reader)

    bak = path + ".pre_missoula_qc.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

    changed = 0
    for row in rows:
        if row.get("event_id") != EVENT_ID:
            continue
        row["synoptic_regime"] = NEW_REGIME
        row["qc_flag"]         = NEW_FLAG
        row["qc_reason"]       = NEW_REASON
        changed += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Updated {changed} rows in {os.path.basename(path)}")

print()
print("Verification — missoula_dec2025 rows after update:")
with open(FILES[0], newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["event_id"] == EVENT_ID:
            print(f"  {r['stid']:<8} flag={r['qc_flag']:<18} regime={r['synoptic_regime']}")
