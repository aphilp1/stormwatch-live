import csv, numpy as np, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_error_dataset.csv', newline='', encoding='utf-8') as f:
    rows = [r for r in csv.DictReader(f)
            if r['qc_flag'] in ('KEEP','CAUTION')
            and r['event_id'] == 'camp_2018']

all_errs  = [float(r['speed_err']) for r in rows]
neg_errs  = [e for e in all_errs if e < 0]
neg_stids = [(r['stid'], float(r['speed_err'])) for r in rows if float(r['speed_err']) < 0]

print(f"Camp all stations: N={len(all_errs)}, mean={np.mean(all_errs):+.2f}")
print(f"Camp ridge (neg):  N={len(neg_errs)}, mean={np.mean(neg_errs):+.2f}")
print()
print("Neg-sign stations:")
for s, e in sorted(neg_stids, key=lambda x: x[1]):
    flag = " <-- DROP (upwind HADS, not Camp signal)" if s == 'CHAC1' else ""
    print(f"  {s}: {e:+.2f}{flag}")

# Recalculate without CHAC1
neg_no_chac = [e for s,e in neg_stids if s != 'CHAC1']
print()
print(f"Camp ridge mean WITH CHAC1:    {np.mean(neg_errs):+.2f}  (N={len(neg_errs)})")
print(f"Camp ridge mean WITHOUT CHAC1: {np.mean(neg_no_chac):+.2f}  (N={len(neg_no_chac)})")
