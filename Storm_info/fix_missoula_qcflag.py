#!/usr/bin/env python3
"""
fix_missoula_qcflag.py
Update missoula_dec2025 rows from DROP_DATE_ERROR to KEEP/CAUTION
now that Dec 17 2025 obs have been populated.

PNTM8: KEEP  -- ridge (7897 ft), 46 mph obs, HRRR undershoots -5.8
CONM8: KEEP  -- Swan Valley exposure, NW flow direction, valid signal
STVM8: KEEP  -- Stevensville, HRRR overshoot = cold pool pattern (valid obs)
RONM8: KEEP  -- exposed site, moderate obs
PSTM8: KEEP  -- valid obs, HRRR overshoot
NINM8: CAUTION -- lower valley, SW flow during NW event = partially decoupled
BLMM8: CAUTION -- Blackfoot Valley bottom, SE flow (decoupled), 5.2 mph near-calm
FINM8: CAUTION -- Florence-Lolo valley, SW flow, 7 mph near-calm
"""

import csv, os, shutil

BASE   = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
CSV_SRC = os.path.join(BASE, "hrrr_error_dataset.csv")
CSV_DEM = os.path.join(BASE, "hrrr_error_dataset_dem.csv")

EVENT_ID = "missoula_dec2025"

QC_MAP = {
    "PNTM8": ("KEEP",    "Dec 17 2025 NW downslope corrected; ridge (7897 ft) 46 mph obs HRRR -5.8 mph undershoots; DROP_DATE_ERROR resolved"),
    "CONM8": ("KEEP",    "Dec 17 2025 NW downslope corrected; Swan Valley NW flow 16.5 mph valid; DROP_DATE_ERROR resolved"),
    "STVM8": ("KEEP",    "Dec 17 2025 NW downslope corrected; Stevensville 20 mph obs HRRR +13 mph overshoot = cold-pool pattern; DROP_DATE_ERROR resolved"),
    "RONM8": ("KEEP",    "Dec 17 2025 NW downslope corrected; 17.4 mph obs WSW flow valid; DROP_DATE_ERROR resolved"),
    "PSTM8": ("KEEP",    "Dec 17 2025 NW downslope corrected; 22.6 mph obs HRRR +9.7 mph overshoot; DROP_DATE_ERROR resolved"),
    "NINM8": ("CAUTION", "Dec 17 2025 NW downslope corrected; SW flow (partially decoupled from NW synoptic); DROP_DATE_ERROR resolved"),
    "BLMM8": ("CAUTION", "Dec 17 2025 NW downslope corrected; SE flow + 5.2 mph near-calm = Blackfoot Valley cold pool decoupled; DROP_DATE_ERROR resolved"),
    "FINM8": ("CAUTION", "Dec 17 2025 NW downslope corrected; SW flow + 7 mph near-calm = Florence-Lolo valley sheltered; DROP_DATE_ERROR resolved"),
}

def update_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames

    with open(path, newline="", encoding="utf-8") as f:
        fields = csv.DictReader(f).fieldnames

    n = 0
    for row in rows:
        if row.get("event_id") != EVENT_ID:
            continue
        stid = row["stid"]
        if stid not in QC_MAP:
            continue
        new_flag, new_reason = QC_MAP[stid]
        row["qc_flag"]   = new_flag
        row["qc_reason"] = new_reason
        n += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  Updated {n} rows in {os.path.basename(path)}")

print("Updating QC flags for missoula_dec2025 (DROP_DATE_ERROR -> KEEP/CAUTION)...")
update_csv(CSV_SRC)
update_csv(CSV_DEM)

print()
print("Result:")
with open(CSV_SRC, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("event_id") != EVENT_ID:
            continue
        print(f"  {row['stid']:<8} {row['qc_flag']:<8} obs={row['obs_sus_mph']:>6} hrrr={row['hrrr_10m_mph']:>6} err={row['speed_err']:>7}")
