import csv, sys, numpy as np
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'C:\Users\aphil\Documents\Stormwatch\Storm_info\dem_features.csv', newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

print(f'Total rows: {len(rows)}')
print(f'Columns: {list(rows[0].keys())}')
print()

for col in ['slope', 'relief_1km', 'elev_residual_m', 'aspect', 'repr_error_flag']:
    vals = []
    for r in rows:
        try: vals.append(float(r[col]))
        except: pass
    if vals:
        v = np.array(vals)
        print(f'{col}: N={len(v)} min={v.min():.1f} p10={np.percentile(v,10):.1f} '
              f'median={np.median(v):.1f} p90={np.percentile(v,90):.1f} max={v.max():.1f}')

print()
print('terrain_class:', dict(Counter(r['terrain_class'] for r in rows)))
print('elev_qc:', dict(Counter(r['elev_qc'] for r in rows)))
print()

# Show a sample of each terrain class
for tc in ['exposed_ridge', 'canyon_gap', 'valley', 'open']:
    sample = [(r['stid'], r['event_id'], r['slope'], r['relief_1km'], r['aspect'])
              for r in rows if r['terrain_class'] == tc][:3]
    print(f'{tc} samples: {sample}')
