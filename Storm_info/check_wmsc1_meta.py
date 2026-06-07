import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=WMSC1",
    "Origin":     "https://www.weather.gov",
}

r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
    "token": TOKEN, "stid": "WMSC1", "complete": "1"
}, headers=HDR, timeout=20)

print(f"HTTP {r.status_code}")
data = r.json()
stn = data.get("STATION", [{}])[0]

# Print everything useful
for k, v in stn.items():
    print(f"  {k}: {v}")
