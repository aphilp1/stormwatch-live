#!/usr/bin/env python3
"""
fix_regime_labels.py — One-time audit fix for two incorrect regime labels.

Corrections (grounded in hindcast_event_library.md, regime_definitions.md):
  iowa_derecho2020:  derecho       → convective_outflow
                     (event library Tier 3: CONVECTIVE_OUTFLOW, MCS bow-echo)
  missoula_jul2024:  NEEDS_REGIME  → convective_outflow
                     (event library Tier 3: CONVECTIVE_OUTFLOW, LSR 72-109 mph downdraft)

Kincade NW/NE: UNCHANGED. Station registry documents that kincade_ign_2019 had NW
ignition winds and kincade_run_2019 had NE run-phase winds (Oct 23 vs Oct 27 2019).
The split was made on meteorological grounds before departure analysis was run.

Applies to: hrrr_error_dataset.csv + hrrr_error_dataset_dem.csv
"""

import csv
import os
import shutil

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"

FIXES = {
    "iowa_derecho2020":  "convective_outflow",
    "missoula_jul2024":  "convective_outflow",
}

def fix_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if "synoptic_regime" not in fieldnames:
        print(f"  SKIP {os.path.basename(path)} — no synoptic_regime column")
        return

    changed = 0
    for row in rows:
        eid = row.get("event_id", "")
        if eid in FIXES:
            old = row["synoptic_regime"]
            new = FIXES[eid]
            if old != new:
                row["synoptic_regime"] = new
                changed += 1
                print(f"  {eid}: {old!r} → {new!r}")

    if changed == 0:
        print(f"  {os.path.basename(path)}: no changes needed")
        return

    backup = path + ".pre_audit_bak"
    shutil.copy2(path, backup)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {os.path.basename(path)}: {changed} rows updated (backup: {os.path.basename(backup)})")


for fname in ("hrrr_error_dataset.csv", "hrrr_error_dataset_dem.csv"):
    path = os.path.join(BASE, fname)
    if os.path.exists(path):
        print(f"\n{fname}:")
        fix_csv(path)
    else:
        print(f"\n{fname}: NOT FOUND — skip")

print("\nDone. Run merge_dem_and_gate.py to regenerate hrrr_error_dataset_dem.csv if needed.")
