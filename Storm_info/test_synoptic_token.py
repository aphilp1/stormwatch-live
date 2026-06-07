import sys, requests
sys.path.insert(0, r'C:\Users\aphil\Documents\Stormwatch')
import synoptic_config as sc
print(f"Token: ...{sc.SYNOPTIC_TOKEN[-8:]}")
r = requests.get('https://api.synopticdata.com/v2/stations/timeseries', params={
    'token': sc.SYNOPTIC_TOKEN, 'stid': 'BLMM8',
    'start': '202512170000', 'end': '202512170100',
    'vars': 'wind_speed', 'units': 'english'}, timeout=20)
s = r.json().get('SUMMARY', {})
print(f"HTTP {r.status_code} | response_code={s.get('RESPONSE_CODE')} | {s.get('RESPONSE_MESSAGE','')[:80]}")
