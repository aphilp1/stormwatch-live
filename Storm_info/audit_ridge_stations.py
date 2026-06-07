import csv, requests, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=JBGC1",
    "Origin":     "https://www.weather.gov",
}
OFFSHORE = ("diablo", "santa_ana")

# Collect all unique offshore ridge stations (neg speed_err, KEEP/CAUTION, exclude CHAC1)
ridge_stids = {}
with open(f"{BASE}/hrrr_error_dataset.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["qc_flag"] not in ("KEEP", "CAUTION"):
            continue
        if not any(t in r.get("synoptic_regime", "") for t in OFFSHORE):
            continue
        if r["stid"] == "CHAC1":
            continue
        try:
            se = float(r["speed_err"])
        except:
            continue
        if se < 0:
            stid = r["stid"]
            if stid not in ridge_stids:
                ridge_stids[stid] = {"speed_errs": [], "events": [], "db_elev": float(r["elev_m"])}
            ridge_stids[stid]["speed_errs"].append(se)
            ridge_stids[stid]["events"].append(r["event_id"])

print(f"Unique offshore ridge stations: {len(ridge_stids)}")
print(f"Stations: {', '.join(sorted(ridge_stids))}")
print()

# Pull metadata for all in one call
stids_str = ",".join(sorted(ridge_stids))
r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
    "token": TOKEN, "stid": stids_str, "complete": "1"
}, headers=HDR, timeout=30)

meta = {}
for stn in r.json().get("STATION", []):
    meta[stn["STID"]] = stn

# Report
ELEV_FLAG_FT = 200   # flag if ELEV vs ELEV_DEM differ by >200 ft

print(f"{'stid':<8} {'net':<6} {'mnet':>4} {'wims':>6} {'elev_stn':>9} {'elev_dem':>9} {'delta_ft':>9}  {'flag':<18} {'mean_err':>8}  events")
print("-" * 110)

flags = []
for stid in sorted(ridge_stids, key=lambda s: np.mean(ridge_stids[s]["speed_errs"])):
    d  = ridge_stids[stid]
    m  = meta.get(stid, {})
    mnet      = m.get("MNET_ID", "?")
    shortname = m.get("SHORTNAME", "?")[:6]
    wims      = m.get("WIMS_ID", "") or ""
    elev_stn  = m.get("ELEVATION", None)
    elev_dem  = m.get("ELEV_DEM",  None)
    providers = [p["name"][:20] for p in m.get("PROVIDERS", [])]

    delta_str = ""
    flag_str  = ""
    if elev_stn and elev_dem:
        delta = abs(float(elev_stn) - float(elev_dem))
        delta_str = f"{delta:>9.0f}"
        if delta > ELEV_FLAG_FT:
            flag_str = f"ELEV_ERR +{delta:.0f}ft"
            flags.append((stid, delta, float(elev_stn), float(elev_dem)))
    else:
        delta_str = "       ?"

    not_raws = (mnet != 2 and mnet != "2")
    if not_raws:
        flag_str = f"NOT_RAWS mnet={mnet}"

    mean_err  = np.mean(d["speed_errs"])
    evts      = list(dict.fromkeys(d["events"]))   # unique, order preserved
    evt_str   = " ".join(e.replace("_201","_").replace("_202","_")
                          .replace("17","17").replace("18","18").replace("19","19").replace("20","20")
                         for e in evts)

    print(f"  {stid:<8} {shortname:<6} {str(mnet):>4} {str(wims):>6} "
          f"{str(elev_stn or '?'):>9} {str(elev_dem or '?'):>9} {delta_str}  "
          f"{flag_str:<18} {mean_err:>+8.2f}  {evt_str}")

print()
if flags:
    print(f"ELEVATION FLAGS (>{ELEV_FLAG_FT} ft discrepancy):")
    for stid, delta, estn, edem in sorted(flags, key=lambda x: -x[1]):
        print(f"  {stid}: station={estn:.0f} ft  DEM={edem:.0f} ft  delta={delta:.0f} ft")
else:
    print("No elevation flags.")
