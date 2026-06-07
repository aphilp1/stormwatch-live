import csv, datetime
from collections import defaultdict

rows = []
with open(r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_error_dataset_dem.csv') as f:
    for r in csv.DictReader(f):
        if r.get('qc_flag') not in ('KEEP','CAUTION'):
            continue
        try:
            float(r['speed_err'])
        except Exception:
            continue
        rows.append(r)

by_event = defaultdict(list)
for r in rows:
    by_event[r['event_id']].append(r)

print(f"{'event_id':<25} {'regime':<28} {'n':>3}  {'peak_dt_utc (median)'}")
for eid in sorted(by_event):
    ev = by_event[eid]
    regime = ev[0].get('synoptic_regime', '?')
    dts = []
    for r in ev:
        try:
            dts.append(datetime.datetime.fromisoformat(r['peak_dt_utc'].replace('Z', '+00:00')))
        except Exception:
            pass
    if dts:
        dts.sort()
        med = dts[len(dts) // 2]
        print(f"{eid:<25} {regime:<28} {len(ev):>3}  {med.strftime('%Y-%m-%d %HZ')}")
