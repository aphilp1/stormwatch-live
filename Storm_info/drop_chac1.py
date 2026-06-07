import csv, os, shutil, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
REASON = (
    "upwind HADS hydro station (Plumas County, ~35 mi NNE of Camp ignition); "
    "HRRR correctly calm (1.4 mph) at that grid cell — different met environment; "
    "bc_speed 16.7 mph vs Camp mean ~30 mph; obs likely local terrain channel "
    "unrelated to Diablo signal; dir_err 53 degrees confirms flow regime mismatch"
)

for fname in ("hrrr_error_dataset.csv", "hrrr_error_dataset_dem.csv"):
    path = os.path.join(BASE, fname)
    bak  = path + ".pre_chac1_drop.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
        fields = reader.fieldnames
    with open(path, newline="", encoding="utf-8") as f:
        fields = csv.DictReader(f).fieldnames

    n = 0
    for row in rows:
        if row["stid"] == "CHAC1" and row["event_id"] == "camp_2018":
            row["qc_flag"]   = "DROP"
            row["qc_reason"] = REASON
            n += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {fname}: flagged {n} rows DROP")

# Recalculate corrected offshore ridge mean
print()
with open(os.path.join(BASE, "hrrr_error_dataset.csv"), newline="", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))

OFFSHORE = ("diablo", "santa_ana")
neg, pos, all_off = [], [], []
for r in all_rows:
    if r["qc_flag"] not in ("KEEP", "CAUTION"):
        continue
    if not any(t in r.get("synoptic_regime","") for t in OFFSHORE):
        continue
    try:
        se = float(r["speed_err"])
    except:
        continue
    all_off.append(se)
    if se < 0:
        neg.append((r["stid"], r["event_id"], se))
    else:
        pos.append(se)

print(f"Corrected offshore (CHAC1 removed):")
print(f"  All stations:  N={len(all_off)}, mean={np.mean(all_off):+.2f}")
print(f"  Ridge (neg):   N={len(neg)}, mean={np.mean([e for _,_,e in neg]):+.2f}")
print(f"  Valley (pos):  N={len(pos)}, mean={np.mean(pos):+.2f}")
print()
print("Ridge stations (for reference):")
for stid, eid, e in sorted(neg, key=lambda x: x[2]):
    print(f"  {stid:<8} {eid:<25} {e:+.2f}")
