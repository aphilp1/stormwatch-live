import csv, os, shutil, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"

REASONS = {
    "TR164": (
        "Portable RAWS (MNF02 PORTABLE, Mendocino NF); deployed for fire ops, non-standard siting; "
        "obs 8 mph while HRRR 30 mph + bc 26 mph = wind shadow deployment; "
        "same coordinates as TS379 but opposite wind direction — both obs suspect; "
        "not a fixed met station; exclude from terrain class analysis"
    ),
    "TS379": (
        "Portable RAWS (MNF04 PORTABLE, Mendocino NF); deployed for fire ops, non-standard siting; "
        "obs 7 mph / 223 deg SW during NE Diablo event = wake/reverse flow at deployment position; "
        "same coordinates as TR164; ELEV_DEM 2858 ft vs station 3600 ft = DEM sampling error; "
        "not a fixed met station; exclude from terrain class analysis"
    ),
    "TT321": (
        "Portable RAWS (LPF05 PORTABLE, Los Padres NF Cerro Norte); deployed for fire ops, non-standard siting; "
        "obs 8 mph / 311 deg NNW during Santa Ana event (bc_dir 87 deg E) = decoupled from synoptic; "
        "ELEV_DEM 7844 ft is DEM sampling artifact; station-reported 4534 ft is correct; "
        "not a fixed met station; exclude from terrain class analysis"
    ),
}

for fname in ("hrrr_error_dataset.csv", "hrrr_error_dataset_dem.csv"):
    path = os.path.join(BASE, fname)
    bak  = path + ".pre_portable_flag.bak"
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
        if row["stid"] in REASONS and row["qc_flag"] == "KEEP":
            row["qc_flag"]   = "CAUTION"
            row["qc_reason"] = REASONS[row["stid"]]
            n += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {fname}: flagged {n} portable stations CAUTION")

# Show updated valley mean
print()
OFFSHORE = ("diablo", "santa_ana")
with open(os.path.join(BASE, "hrrr_error_dataset.csv"), newline="", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))

for label, flags in [("KEEP only", ("KEEP",)), ("KEEP+CAUTION", ("KEEP","CAUTION"))]:
    neg, pos, total = [], [], []
    for r in all_rows:
        if r["qc_flag"] not in flags:
            continue
        if not any(t in r.get("synoptic_regime","") for t in OFFSHORE):
            continue
        try:
            se = float(r["speed_err"])
        except:
            continue
        total.append(se)
        (neg if se < 0 else pos).append(se)
    print(f"  {label}: all N={len(total)} mean={np.mean(total):+.2f} | "
          f"ridge N={len(neg)} mean={np.mean(neg):+.2f} | "
          f"valley N={len(pos)} mean={np.mean(pos):+.2f}")
