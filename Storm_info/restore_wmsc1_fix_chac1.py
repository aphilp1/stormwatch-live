import csv, os, shutil, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"

WMSC1_REASON = (
    "BLM/USFS Interagency RAWS (MNET=2, WIMS=45426), standard fire weather wind instrumentation; "
    "two-event cross-confirmation Thomas -35.65 and Woolsey -27.04 mph, dir_err <8 degrees both; "
    "station-reported elevation 4930 ft is WRONG — Synoptic ELEV_DEM = 3779.5 ft (1152m) is correct; "
    "terrain_class exposed_ridge pending DEM re-verification at corrected elevation; "
    "error magnitude extraordinary but instrument and location are valid fire weather RAWS"
)

CHAC1_REASON = (
    "BLM/USFS RAWS (instrument valid) but geographically peripheral to Camp Fire — "
    "~30 mi east + 10 mi north of Jarbo Gap in different watershed (Plumas County); "
    "bc_speed 16.7 mph vs Camp mean ~30 mph confirms different met environment; "
    "HRRR near-calm (1.4 mph) is correct for that grid cell, not a model failure; "
    "dir_err 53 degrees (obs NNE vs HRRR/BC ESE) = different flow regime; "
    "station not in Camp Fire fire-weather zone"
)

for fname in ("hrrr_error_dataset.csv", "hrrr_error_dataset_dem.csv"):
    path = os.path.join(BASE, fname)
    bak  = path + ".pre_wmsc1_restore.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
        fields = reader.fieldnames
    with open(path, newline="", encoding="utf-8") as f:
        fields = csv.DictReader(f).fieldnames

    n_wmsc1 = n_chac1 = 0
    for row in rows:
        if row["stid"] == "WMSC1":
            row["qc_flag"]   = "KEEP"
            row["qc_reason"] = WMSC1_REASON
            row["elev_m"]    = "1152.0"   # Synoptic ELEV_DEM 3779.5 ft
            n_wmsc1 += 1
        elif row["stid"] == "CHAC1" and row["event_id"] == "camp_2018":
            row["qc_reason"] = CHAC1_REASON   # qc_flag stays DROP, reason corrected
            n_chac1 += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {fname}: WMSC1 KEEP ({n_wmsc1} rows), CHAC1 reason corrected ({n_chac1} rows)")

# Final ridge mean
print()
with open(os.path.join(BASE, "hrrr_error_dataset.csv"), newline="", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))

OFFSHORE = ("diablo", "santa_ana")
neg, pos, total = [], [], []
for r in all_rows:
    if r["qc_flag"] not in ("KEEP","CAUTION"):
        continue
    if not any(t in r.get("synoptic_regime","") for t in OFFSHORE):
        continue
    try:
        se = float(r["speed_err"])
    except:
        continue
    total.append(se)
    (neg if se < 0 else pos).append(se)

print(f"Final offshore (CHAC1 DROP, WMSC1 KEEP):")
print(f"  All N={len(total)} mean={np.mean(total):+.2f}")
print(f"  Ridge (neg) N={len(neg)} mean={np.mean(neg):+.2f}")
print(f"  Valley (pos) N={len(pos)} mean={np.mean(pos):+.2f}")
