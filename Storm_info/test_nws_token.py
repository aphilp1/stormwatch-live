import requests
TOKEN = "7c76618b66c74aee913bdbae4b448bdd"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.weather.gov/wrh/timeseries?site=BLMM8",
    "Origin":     "https://www.weather.gov",
}
r = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params={
    "token": TOKEN, "stid": "BLMM8",
    "start": "202512170000", "end": "202512170100",
    "vars": "wind_speed", "units": "english"}, headers=HDR, timeout=20)
s = r.json().get("SUMMARY", {})
print(f"HTTP {r.status_code} | response_code={s.get('RESPONSE_CODE')} | {s.get('RESPONSE_MESSAGE','')[:80]}")
