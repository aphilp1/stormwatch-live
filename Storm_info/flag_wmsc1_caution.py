import csv, os, shutil, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
REASON = (
    "HADS hydro station (rain/flood focus, non-standard wind sensor height/siting); "
    "elevation in database 1502.7m (4929 ft) but real elevation ~1128m (3700 ft) — "
    "1229 ft discrepancy corrupts terrain_class exposed_ridge (elev_heuristic); "
    "this IS the elevation error that blocked WN test; "
    "error magnitude -35.65/-27.04 mph extraordinary even among ridge stations; "
    "ENE direction and Castaic location plausible for Santa Ana but sensor validity unverified; "
    "pending: correct elevation, verify sensor height/position, re-evaluate terrain_class"
)

for fname in ("hrrr_error_dataset.csv", "hrrr_error_dataset_dem.csv"):
    path = os.path.join(BASE, fname)
    bak  = path + ".pre_wmsc1_caution.bak"
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
        if row["stid"] == "WMSC1":
            row["qc_flag"]   = "CAUTION"
            row["qc_reason"] = REASON
            row["elev_m"]    = "1127.8"   # ~3700 ft corrected
            n += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {fname}: CAUTION + elevation corrected for {n} rows")

# Show impact on ridge mean with WMSC1 as CAUTION (excluded from KEEP-only analysis)
print()
print("Impact on offshore ridge mean (KEEP-only vs KEEP+CAUTION):")
with open(os.path.join(BASE, "hrrr_error_dataset.csv"), newline="", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))

OFFSHORE = ("diablo", "santa_ana")

for label, flags in [("KEEP+CAUTION", ("KEEP","CAUTION")), ("KEEP only", ("KEEP",))]:
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
