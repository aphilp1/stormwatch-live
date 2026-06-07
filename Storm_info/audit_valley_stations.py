import csv, requests, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=KNXC1",
    "Origin":     "https://www.weather.gov",
}
OFFSHORE = ("diablo", "santa_ana")

# Collect all unique offshore valley stations (pos speed_err, KEEP/CAUTION)
valley_stids = {}
with open(f"{BASE}/hrrr_error_dataset.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["qc_flag"] not in ("KEEP", "CAUTION"):
            continue
        if not any(t in r.get("synoptic_regime", "") for t in OFFSHORE):
            continue
        try:
            se = float(r["speed_err"])
        except:
            continue
        if se >= 0:
            stid = r["stid"]
            if stid not in valley_stids:
                valley_stids[stid] = {"speed_errs": [], "events": [], "db_elev": r["elev_m"]}
            valley_stids[stid]["speed_errs"].append(se)
            valley_stids[stid]["events"].append(r["event_id"])

print(f"Unique offshore valley/sheltered stations: {len(valley_stids)}")
print(f"Stations: {', '.join(sorted(valley_stids))}")
print()

stids_str = ",".join(sorted(valley_stids))
r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
    "token": TOKEN, "stid": stids_str, "complete": "1"
}, headers=HDR, timeout=30)

meta = {}
for stn in r.json().get("STATION", []):
    meta[stn["STID"]] = stn

ELEV_FLAG_FT = 200

print(f"{'stid':<8} {'net':<8} {'mnet':>4} {'wims':>6} {'elev_stn':>9} {'elev_dem':>9} {'delta_ft':>9}  {'flag':<22} {'mean_err':>8}  events")
print("-" * 116)

flags = []
not_raws = []
for stid in sorted(valley_stids, key=lambda s: -np.mean(valley_stids[s]["speed_errs"])):
    d  = valley_stids[stid]
    m  = meta.get(stid, {})
    mnet      = m.get("MNET_ID", "?")
    shortname = (m.get("SHORTNAME") or "?")[:8]
    wims      = m.get("WIMS_ID", "") or ""
    elev_stn  = m.get("ELEVATION", None)
    elev_dem  = m.get("ELEV_DEM",  None)

    delta_str = "       ?"
    flag_str  = ""
    if elev_stn is not None and elev_dem is not None:
        delta = abs(float(elev_stn) - float(elev_dem))
        delta_str = f"{delta:>9.0f}"
        if delta > ELEV_FLAG_FT:
            flag_str = f"ELEV_ERR +{delta:.0f}ft"
            flags.append((stid, delta, float(elev_stn), float(elev_dem)))

    if str(mnet) != "2":
        flag_str = f"NOT_RAWS mnet={mnet}"
        not_raws.append(stid)

    mean_err = np.mean(d["speed_errs"])
    evts = list(dict.fromkeys(d["events"]))
    evt_str = " ".join(evts)

    print(f"  {stid:<8} {shortname:<8} {str(mnet):>4} {str(wims):>6} "
          f"{str(elev_stn or '?'):>9} {str(elev_dem or '?'):>9} {delta_str}  "
          f"{flag_str:<22} {mean_err:>+8.2f}  {evt_str}")

print()
if flags:
    print(f"ELEVATION FLAGS (>{ELEV_FLAG_FT} ft discrepancy):")
    for stid, delta, estn, edem in sorted(flags, key=lambda x: -x[1]):
        print(f"  {stid}: station={estn:.0f} ft  DEM={edem:.0f} ft  delta={delta:.0f} ft")
else:
    print("No elevation flags.")

print()
if not_raws:
    print(f"NON-RAWS STATIONS: {not_raws}")
else:
    print("All valley stations confirmed RAWS (MNET_ID=2).")
