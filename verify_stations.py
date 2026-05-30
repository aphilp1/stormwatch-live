import sys, requests
sys.path.insert(0, r"C:\Users\aphil\Documents\Stormwatch")
sys.stdout.reconfigure(encoding="utf-8")
from synoptic_config import SYNOPTIC_TOKEN

stids = "JBGC1,CICC1,SLEC1,CBXC1,HMRC1"
r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
    "stid": stids, "token": SYNOPTIC_TOKEN
}, timeout=20)
print(f"Status: {r.status_code}")
data = r.json()
summary = data.get("SUMMARY", {})
print(f"Response code: {summary.get('RESPONSE_CODE')}  Message: {summary.get('RESPONSE_MESSAGE')}")
for s in data.get("STATION", []):
    lat  = s.get("LATITUDE", "?")
    lon  = s.get("LONGITUDE", "?")
    elev = s.get("ELEVATION", "?")
    name = s.get("NAME", "?")
    stid = s.get("STID", "?")
    print(f"  {stid:8s}  {name:30s}  lat={lat:9s}  lon={lon:10s}  elev={elev}ft")
