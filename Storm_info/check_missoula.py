import csv

rows = []
with open(r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_error_dataset.csv') as f:
    for r in csv.DictReader(f):
        if r['event_id'] == 'missoula_dec2025':
            rows.append(r)

print(f'N rows: {len(rows)}')
print()
print(f"{'stid':<10} {'qc_flag':<22} {'peak_dt_utc':<24} {'obs_sus':>8} {'hrrr_10m':>9} {'speed_err':>10}")
for r in rows:
    print(f"{r['stid']:<10} {r['qc_flag']:<22} {r['peak_dt_utc']:<24} "
          f"{r['obs_sus_mph']:>8} {r['hrrr_10m_mph']:>9} {r['speed_err']:>10}")
