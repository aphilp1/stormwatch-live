import csv, requests, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR   = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=TT321",
    "Origin":     "https://www.weather.gov",
}

TARGET = {"TT321", "TS379", "TR164"}

# Database rows
print("=== DATABASE ROWS ===")
with open(f"{BASE}/hrrr_error_dataset.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["stid"] in TARGET:
            keys = ["event_id","stid","station_name","lat","lon","elev_m","qc_flag",
                    "obs_sus_mph","obs_dir_deg","hrrr_10m_mph","speed_err",
                    "synoptic_regime","terrain_class","bc_speed","bc_dir"]
            for k in keys:
                if r.get(k): print(f"  {k}: {r[k]}")
            print()

# Synoptic metadata
print("=== SYNOPTIC METADATA ===")
r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
    "token": TOKEN, "stid": "TT321,TS379,TR164", "complete": "1"
}, headers=HDR, timeout=20)
for stn in r.json().get("STATION", []):
    print(f"\n{stn['STID']}:")
    for k in ["NAME","MNET_ID","SHORTNAME","LONGNAME","ELEVATION","ELEV_DEM",
              "LATITUDE","LONGITUDE","WIMS_ID","STATE","COUNTY","GACC","CWA","PROVIDERS"]:
        v = stn.get(k)
        if v is not None:
            print(f"  {k}: {v}")
