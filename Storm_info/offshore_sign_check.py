#!/usr/bin/env python3
"""
offshore_sign_check.py
Check per-station speed_err sign consistency within offshore events.

Phase A used event-level means (correct for regime inference).
Phase B question: are offshore events coherent (consistent negative sign across
stations) or composite (ridge underbias + valley overshoot canceling)?
If composite, the event mean -3.91 understates the true ridge underbias,
and the WindNinja benchmark must be set against ridge-station underbias, not
the event mean.
"""

import csv, os, sys
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE   = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
IN_CSV = os.path.join(BASE, "hrrr_error_dataset.csv")

OFFSHORE_TAGS = ("diablo", "santa_ana")

rows = []
with open(IN_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        regime = r.get("synoptic_regime", "")
        if not any(t in regime for t in OFFSHORE_TAGS):
            continue
        try:
            se  = float(r["speed_err"])
            obs = float(r["obs_sus_mph"])
            h10 = float(r["hrrr_10m_mph"])
        except Exception:
            continue
        rows.append({
            "event_id": r["event_id"],
            "stid":     r["stid"],
            "regime":   regime,
            "qc_flag":  r["qc_flag"],
            "speed_err": se,
            "obs_sus":   obs,
            "hrrr_10m":  h10,
        })

from collections import defaultdict
by_event = defaultdict(list)
for r in rows:
    by_event[r["event_id"]].append(r)

print("=" * 72)
print("OFFSHORE EVENT SIGN CONSISTENCY CHECK")
print("  Positive speed_err = HRRR overshoots (valley / sheltered signature)")
print("  Negative speed_err = HRRR undershoots (ridge / exposed signature)")
print("=" * 72)
print()

event_coherence = {}
for eid in sorted(by_event.keys()):
    ev = by_event[eid]
    regime = ev[0]["regime"]
    errs = [r["speed_err"] for r in ev]
    n_neg = sum(1 for e in errs if e < 0)
    n_pos = sum(1 for e in errs if e >= 0)
    mean_err = np.mean(errs)

    # coherence: all negative = fully coherent; mixed = composite
    pct_neg = 100 * n_neg / len(errs)
    coherent = pct_neg >= 80
    label = "COHERENT" if pct_neg >= 80 else ("MOSTLY" if pct_neg >= 60 else "COMPOSITE")

    print(f"  {eid:<25} ({regime})")
    print(f"    N={len(errs)} stations | neg={n_neg} ({pct_neg:.0f}%) pos={n_pos} | "
          f"mean={mean_err:+.2f} | {label}")

    # Show all station errors sorted
    for r in sorted(ev, key=lambda x: x["speed_err"]):
        flag = " [CAUTION]" if r["qc_flag"] == "CAUTION" else ""
        print(f"      {r['stid']:<8} err={r['speed_err']:>+6.2f}  obs={r['obs_sus']:>5.1f}  "
              f"hrrr={r['hrrr_10m']:>5.1f}{flag}")

    event_coherence[eid] = {
        "n": len(errs), "n_neg": n_neg, "pct_neg": pct_neg,
        "mean_err": mean_err, "label": label,
        "neg_mean": np.mean([e for e in errs if e < 0]) if n_neg else None,
        "pos_mean": np.mean([e for e in errs if e >= 0]) if n_pos else None,
    }
    print()

# Summary
print("-" * 72)
print("SUMMARY")
print()
print(f"  {'event_id':<25} {'N':>3} {'%neg':>5} {'mean':>7} {'label':<12} "
      f"{'ridge-only':>10} {'valley-only':>12}")
for eid, d in sorted(event_coherence.items(), key=lambda x: -x[1]["pct_neg"]):
    r_str = f"{d['neg_mean']:+.2f}" if d["neg_mean"] is not None else "N/A"
    v_str = f"{d['pos_mean']:+.2f}" if d["pos_mean"] is not None else "N/A"
    print(f"  {eid:<25} {d['n']:>3} {d['pct_neg']:>4.0f}% {d['mean_err']:>+7.2f} "
          f"{d['label']:<12} {r_str:>10} {v_str:>12}")

all_errs = [r["speed_err"] for r in rows]
all_neg  = [e for e in all_errs if e < 0]
all_pos  = [e for e in all_errs if e >= 0]
print()
print(f"  Overall offshore: N={len(all_errs)} stations | mean={np.mean(all_errs):+.2f}")
print(f"    Ridge-signal stations (neg): N={len(all_neg)} | mean={np.mean(all_neg):+.2f}")
print(f"    Valley/sheltered  (pos):     N={len(all_pos)} | mean={np.mean(all_pos):+.2f}")
print()
print("IMPLICATION FOR WINDNINJA BENCHMARK:")
if np.mean(all_neg) < -4.5:
    print(f"  True ridge underbias (neg-only mean = {np.mean(all_neg):+.2f}) is larger than")
    print(f"  event-mean headline ({np.mean(all_errs):+.2f}). WindNinja benchmark should")
    print(f"  target ridge-station underbias, NOT the diluted event mean.")
else:
    print(f"  Offshore events appear largely coherent. Event mean ({np.mean(all_errs):+.2f})")
    print(f"  is a reasonable benchmark. Check station-level DEM tags in Phase B.")
