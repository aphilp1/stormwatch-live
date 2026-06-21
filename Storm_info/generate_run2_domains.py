"""
Generate Run 2 (reality_b) domain JSONs for each hindcast event.
Run 2 BC speed = mean observed wind across all event stations (from hrrr_error_dataset.csv).
Vectors scaled proportionally from Run 1.
Direction stays the same.
"""

import json, csv, os

GRIDS_DIR = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hindcast_grids'
CSV_PATH  = r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_error_dataset.csv'

# Load all obs keyed by event_id -> list of obs_sus_mph values
event_obs = {}
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        ev = row['event_id']
        raw = (row.get('obs_sus_mph') or '').strip()
        if raw and raw not in ('N/A', 'nan', ''):
            try:
                event_obs.setdefault(ev, []).append(float(raw))
            except ValueError:
                pass

# Compute mean obs per event
event_mean_obs = {ev: sum(vals)/len(vals) for ev, vals in event_obs.items()}
for ev, m in sorted(event_mean_obs.items()):
    print(f'  {ev}: mean_obs={m:.1f} mph  (n={len(event_obs[ev])})')

print()

# Process each run1 domain JSON
for fname in sorted(os.listdir(GRIDS_DIR)):
    if not fname.endswith('_reality_a_domain.json'):
        continue
    event_id = fname.replace('_reality_a_domain.json', '')

    if event_mean_obs.get(event_id) is None:
        print(f'SKIP {event_id} — no obs data in CSV')
        continue

    run1_path = os.path.join(GRIDS_DIR, fname)
    run2_path = os.path.join(GRIDS_DIR, f'{event_id}_reality_b_domain.json')

    with open(run1_path, encoding='utf-8') as f:
        run1 = json.load(f)

    run1_bc_raw = float(run1['bc']['speed'])

    # Detect km/h (WN sometimes outputs in km/h): if BC > 60 assume km/h
    if run1_bc_raw > 60:
        run1_bc_mph = run1_bc_raw / 1.60934
        units_note = f'{run1_bc_raw:.1f} km/h = {run1_bc_mph:.1f} mph'
        # vectors also in km/h, will be converted below
        kmh_mode = True
    else:
        run1_bc_mph = run1_bc_raw
        units_note = f'{run1_bc_mph:.1f} mph'
        kmh_mode = False

    run2_bc_mph = event_mean_obs[event_id]
    scale = run2_bc_mph / run1_bc_mph if run1_bc_mph > 0 else 1.0

    print(f'{event_id}:  BC {units_note}  ->  Run2={run2_bc_mph:.1f} mph  scale={scale:.3f}')

    run2_vectors = []
    for v in run1['vectors']:
        spd_raw = float(v.get('speed', 0) or 0)
        spd_mph = spd_raw / 1.60934 if kmh_mode else spd_raw
        run2_vectors.append({
            'lat':   v['lat'],
            'lon':   v['lon'],
            'speed': round(spd_mph * scale, 2),
            'dir':   v['dir'],
        })

    valid_spds = [v['speed'] for v in run2_vectors if v['speed'] > 0]
    run2 = {
        'event_id': event_id,
        'reality':  'B',
        'bc': {
            'speed': round(run2_bc_mph, 1),
            'dir':   run1['bc']['dir'],
            'note':  f'Mean RAWS obs {run2_bc_mph:.1f} mph (corrected from {units_note})',
        },
        'domain_dem': run1['domain_dem'],
        'stats': {
            'mean': round(sum(valid_spds)/len(valid_spds), 2) if valid_spds else 0,
            'min':  round(min(valid_spds), 2) if valid_spds else 0,
            'max':  round(max(valid_spds), 2) if valid_spds else 0,
            'n':    len(valid_spds),
        },
        'vectors': run2_vectors,
    }

    with open(run2_path, 'w', encoding='utf-8') as f:
        json.dump(run2, f, separators=(',', ':'))

    print(f'  -> {os.path.basename(run2_path)}  ({len(run2_vectors)} vectors, max={run2["stats"]["max"]:.1f} mph)')
