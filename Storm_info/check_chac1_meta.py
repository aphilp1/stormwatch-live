import requests, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=CHAC1",
    "Origin":     "https://www.weather.gov",
}

for stid in ("CHAC1", "WMSC1"):
    r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
        "token": TOKEN, "stid": stid, "complete": "1"
    }, headers=HDR, timeout=20)
    stn = r.json().get("STATION", [{}])[0]
    print(f"{stid}: MNET={stn.get('MNET_ID')} SHORTNAME={stn.get('SHORTNAME')} "
          f"ELEV={stn.get('ELEVATION')} ELEV_DEM={stn.get('ELEV_DEM')} "
          f"WIMS={stn.get('WIMS_ID')} PROVIDERS={[p['name'] for p in stn.get('PROVIDERS',[])]}")
