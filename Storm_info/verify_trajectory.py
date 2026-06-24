#!/usr/bin/env python3
"""
verify_trajectory.py — §8 independent recompute of the trajectory metrics.

Reads the COMMITTED <event>_station_results.json, recomputes rmse and
peak_offset_h straight from each station's raw `curves` arrays, and confirms
they match the persisted metric values. Same contract as the four-way
recompute: against committed files, never a summary. Pure stdlib — runs in any
python (no herbie / WN needed).

  python verify_trajectory.py --event camp_2018
  python verify_trajectory.py --all
"""

import argparse
import json
import math
import os

BASE       = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
OUTPUT_DIR = os.path.join(BASE, "hindcast_grids")
MODELS     = ('hrrr_10m', 'hrrr_bc', 'wn10m', 'wn850')
RMSE_TOL   = 1e-3   # persisted rmse is rounded to 3 dp

ALL_EVENTS = [
    'camp_2018', 'kincade_run_2019', 'kincade_ign_2019', 'woolsey_2018',
    'thomas_2017', 'missoula_dec2025', 'labor_day_or2020', 'boulder_chin2021',
    'marshall_2021', 'iowa_derecho2020', 'missoula_jul2024', 'tubbs_2017',
]


def rmse(model, obs):
    pairs = [(m, o) for m, o in zip(model, obs) if m is not None and o is not None]
    if not pairs:
        return None
    return math.sqrt(sum((m - o) ** 2 for m, o in pairs) / len(pairs))


def argmax_idx(arr):
    best_i = best_v = None
    for i, v in enumerate(arr):
        if v is None:
            continue
        if best_v is None or v > best_v:
            best_v, best_i = v, i
    return best_i


def peak_offset(model, obs):
    mi, oi = argmax_idx(model), argmax_idx(obs)
    if mi is None or oi is None:
        return None
    return mi - oi


def verify_event(event_id):
    path = os.path.join(OUTPUT_DIR, f"{event_id}_station_results.json")
    if not os.path.exists(path):
        print(f"  {event_id}: no station_results.json — SKIP")
        return (0, 0, 0)
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    stations = data.get('stations', [])
    n_traj = checks = fails = 0
    for r in stations:
        traj = r.get('trajectory')
        if not traj:
            continue
        n_traj += 1
        obs = traj['curves']['obs']
        for m in MODELS:
            # ── rmse ──
            want = traj['rmse'].get(m)
            got  = rmse(traj['curves'][m], obs)
            checks += 1
            if want is None or got is None:
                if want is not None or got is not None:
                    fails += 1
                    print(f"    FAIL {r['stid']} rmse[{m}]: persisted={want} recomputed={got}")
            elif abs(want - got) > RMSE_TOL:
                fails += 1
                print(f"    FAIL {r['stid']} rmse[{m}]: persisted={want} recomputed={got:.3f}")
            # ── peak_offset_h ──
            want_p = traj['peak_offset_h'].get(m)
            got_p  = peak_offset(traj['curves'][m], obs)
            checks += 1
            if want_p != got_p:
                fails += 1
                print(f"    FAIL {r['stid']} peak_offset_h[{m}]: persisted={want_p} recomputed={got_p}")
    status = "ALL MATCH" if fails == 0 else f"{fails} MISMATCH"
    print(f"  {event_id:<22} stations_with_trajectory={n_traj:>3}  checks={checks:>4}  {status}")
    return (n_traj, checks, fails)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Independent recompute of trajectory metrics (§8)')
    ap.add_argument('--event', default='camp_2018')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    events = ALL_EVENTS if args.all else [args.event]
    print("TRAJECTORY VERIFY — recompute rmse + peak_offset_h from committed curves")
    tot_t = tot_c = tot_f = 0
    for ev in events:
        nt, c, fa = verify_event(ev)
        tot_t += nt; tot_c += c; tot_f += fa
    print(f"\nTOTAL  trajectory_stations={tot_t}  checks={tot_c}  "
          f"{'ALL MATCH' if tot_f == 0 else str(tot_f) + ' MISMATCH'}")
    raise SystemExit(1 if tot_f else 0)
