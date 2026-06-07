#!/usr/bin/env python3
"""
regime_event_gate.py  —  Event-level regime departure analysis
Phase A follow-up: correct unit of analysis for regime.

WHY event-level, not station-level:
  Regime does not vary within an event — every station in camp_2018 is "diablo,"
  every station in thomas_2017 is "santa_ana." Running structured-vs-white on
  164 stations inflates N by treating co-located stations as independent. The
  honest unit is the event: collapse each event to a mean/median departure, then
  compare ~12 event-level numbers across regimes. This is a small-N descriptive
  analysis, not a significance test.

Output:
  1. Per-event summary (mean/median speed_err and dir_err, regime, n stations)
  2. Per-regime summary (event means ± spread, n events)
  3. Leave-one-regime-out: drop each regime, report whether offshore-undershoot
     pattern holds in the remainder
  4. Single-event regime flags (hypothesis only, not findings)
"""

import csv
import os
import sys
import datetime
from collections import defaultdict

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE       = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
IN_CSV     = os.path.join(BASE, "hrrr_error_dataset_dem.csv")
REPORT     = os.path.join(BASE, "regime_event_report.txt")

# ── load ──────────────────────────────────────────────────────────────────────

station_rows = []
with open(IN_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        try:
            speed_err = float(r["speed_err"])
        except (ValueError, TypeError):
            continue
        try:
            dir_err = float(r["dir_err"])
        except (ValueError, TypeError):
            dir_err = None
        regime = r.get("synoptic_regime", "").strip() or "unknown"
        station_rows.append({
            "event_id":  r["event_id"],
            "stid":      r["stid"],
            "speed_err": speed_err,
            "dir_err":   dir_err,
            "regime":    regime,
        })

# ── collapse to event level ───────────────────────────────────────────────────

event_data = defaultdict(lambda: {"speed_errs": [], "dir_errs": [], "regime": None})
for r in station_rows:
    ev = event_data[r["event_id"]]
    ev["speed_errs"].append(r["speed_err"])
    if r["dir_err"] is not None:
        ev["dir_errs"].append(r["dir_err"])
    ev["regime"] = r["regime"]  # same for all stations in event

events = []
for eid, ev in sorted(event_data.items()):
    sp = np.array(ev["speed_errs"])
    de = np.array(ev["dir_errs"]) if ev["dir_errs"] else None
    events.append({
        "event_id":       eid,
        "regime":         ev["regime"],
        "n_stations":     len(sp),
        "mean_speed_err": float(np.mean(sp)),
        "med_speed_err":  float(np.median(sp)),
        "std_speed_err":  float(np.std(sp)),
        "mean_dir_err":   float(np.mean(de))   if de is not None else None,
        "med_dir_err":    float(np.median(de)) if de is not None else None,
    })

n_events = len(events)
events_sorted = sorted(events, key=lambda e: e["mean_speed_err"])

# ── regime summaries ──────────────────────────────────────────────────────────

regime_events = defaultdict(list)
for ev in events:
    regime_events[ev["regime"]].append(ev)

# Regimes sorted by mean-of-event-means
regime_order = sorted(
    regime_events.keys(),
    key=lambda r: np.mean([e["mean_speed_err"] for e in regime_events[r]])
)

# ── leave-one-regime-out ──────────────────────────────────────────────────────

# Grand mean of all event-level speed_errs
all_means = [e["mean_speed_err"] for e in events if e["regime"] != "NEEDS_REGIME"]
grand_mean = np.mean(all_means)

loro_results = []
for drop_regime in regime_order:
    if drop_regime == "NEEDS_REGIME":
        continue
    remaining = [e["mean_speed_err"] for e in events
                 if e["regime"] not in (drop_regime, "NEEDS_REGIME")]
    if not remaining:
        continue
    rem_mean = np.mean(remaining)
    n_rem = len(remaining)
    loro_results.append({
        "dropped":  drop_regime,
        "n_drop":   len(regime_events[drop_regime]),
        "n_remain": n_rem,
        "mean_rem": rem_mean,
        "delta":    rem_mean - grand_mean,
    })

# ── build report ──────────────────────────────────────────────────────────────

lines = []
def w(s=""): lines.append(s)

w("=" * 70)
w("REGIME EVENT-LEVEL DEPARTURE REPORT")
w(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
w("=" * 70)
w()
w(f"Total active station-events: {len(station_rows)}")
w(f"Collapsed to:                {n_events} events (effective N = {n_events})")
w(f"Regimes represented:         {len(regime_events)}")
w()
w("NOTE: This is a small-N descriptive analysis. With ~12 events across")
w("~5-6 regimes, no regime has enough events for a significance test.")
w("Single-event regimes are hypotheses, not findings.")
w()

# Per-event table
w("─" * 70)
w("PER-EVENT SUMMARY  (sorted by mean speed_err, low → high)")
w(f"  {'event_id':<25} {'regime':<25} {'n':>4}  {'mean':>6}  {'med':>6}  {'std':>6}  dir_mean")
w()
for ev in events_sorted:
    dm = f"{ev['mean_dir_err']:+6.1f}°" if ev["mean_dir_err"] is not None else "   N/A"
    w(
        f"  {ev['event_id']:<25} {ev['regime']:<25} {ev['n_stations']:>4}"
        f"  {ev['mean_speed_err']:>+6.2f}  {ev['med_speed_err']:>+6.2f}"
        f"  {ev['std_speed_err']:>6.2f}  {dm}"
    )
w()

# Per-regime summary
w("─" * 70)
w("PER-REGIME SUMMARY  (unit: event means)")
w(f"  {'regime':<25} {'n_ev':>5}  {'mean_of_means':>14}  {'range':>16}  note")
w()
for reg in regime_order:
    evs = regime_events[reg]
    ev_means = [e["mean_speed_err"] for e in evs]
    m = np.mean(ev_means)
    mn, mx = min(ev_means), max(ev_means)
    note = "** SINGLE EVENT — hypothesis only **" if len(evs) == 1 else ""
    if reg == "NEEDS_REGIME":
        note = "excluded from regime analysis"
    w(
        f"  {reg:<25} {len(evs):>5}  {m:>+14.2f}  [{mn:>+6.2f},{mx:>+6.2f}]  {note}"
    )
w()
w(f"  Grand mean (excl. NEEDS_REGIME): {grand_mean:+.2f} mph")
w()

# Leave-one-regime-out
w("─" * 70)
w("LEAVE-ONE-REGIME-OUT")
w("  Drop each regime in turn; report mean of remaining events.")
w(f"  Grand mean (all, excl NEEDS_REGIME): {grand_mean:+.2f} mph  (n={len(all_means)} events)")
w()
w(f"  {'dropped regime':<25} {'n_drop':>6}  {'n_remain':>8}  {'mean_remain':>12}  {'Δ vs grand':>10}")
w()
for r in loro_results:
    w(
        f"  {r['dropped']:<25} {r['n_drop']:>6}  {r['n_remain']:>8}"
        f"  {r['mean_rem']:>+12.2f}  {r['delta']:>+10.2f}"
    )
w()
w("  Interpretation:")
w("  A large |Δ| means that regime is load-bearing — the pattern changes if you drop it.")
w("  A small |Δ| means the pattern is robust to removing that regime.")
w()

# Narrative verdict
# Four-category grouping per regime_definitions.md
offshore_regimes    = [r for r in regime_order if any(x in r for x in ("santa_ana", "diablo"))]
continental_regimes = [r for r in regime_order if any(x in r for x in ("chinook", "downslope"))]
frontal_regimes     = [r for r in regime_order if "frontal_passage" in r]
convective_regimes  = [r for r in regime_order if "convective_outflow" in r]

w("─" * 70)
w("FOUR-REGIME SPLIT (event-level, per regime_definitions.md)")
w("  Negative speed_err = HRRR undershoots (underbias).")
w()

def regime_block(label, reg_list, note=""):
    if not reg_list:
        return
    evs = [e["mean_speed_err"] for r in reg_list for e in regime_events[r]]
    n = len(evs)
    m = np.mean(evs)
    single = [r for r in reg_list if len(regime_events[r]) == 1]
    hyp = "  ** hypothesis only (single-event regimes present) **" if single else ""
    w(f"  {label} ({', '.join(reg_list)})")
    w(f"    Events: {n}  |  mean: {m:+.2f} mph{hyp}")
    if note:
        w(f"    Note: {note}")
    w()

regime_block("OFFSHORE_GRADIENT",    offshore_regimes)
regime_block("CONTINENTAL_DOWNSLOPE",continental_regimes)
regime_block("FRONTAL_PASSAGE",      frontal_regimes,
             "single event — hypothesis only; similar underbias to offshore")
regime_block("CONVECTIVE_OUTFLOW",   convective_regimes,
             "out-of-scope contrast cases; HRRR error mechanism differs")

if offshore_regimes and continental_regimes:
    off_means = [e["mean_speed_err"] for r in offshore_regimes for e in regime_events[r]]
    con_means = [e["mean_speed_err"] for r in continental_regimes for e in regime_events[r]]
    off_grand = np.mean(off_means)
    con_grand = np.mean(con_means)
    split_mph = con_grand - off_grand
    w(f"  OFFSHORE vs CONTINENTAL split: {split_mph:+.2f} mph (continental − offshore)")
    w(f"  Offshore N={len(off_means)} events mean={off_grand:+.2f} mph  |  Continental N={len(con_means)} events mean={con_grand:+.2f} mph")
    w()
    w("  Physical interpretation:")
    w("  Negative speed_err = HRRR undershoots observed wind (underbias).")
    if off_grand < -2 and con_grand > -1:
        w(f"  HRRR runs ~{abs(off_grand):.1f} mph slow in offshore-gradient fire events,")
        w(f"  near-zero bias in continental/downslope events.")
        w("  This is a flow-regime property, not a terrain property (terrain gate: FAILED).")
        w("  Finding: HRRR underbias is concentrated in offshore-gradient regimes.")
        w("  Implication: terrain-keyed correction (WindNinja) is the wrong lever.")
        w("  Better path: regime-conditioned bias characterization (flag-and-bound,")
        w("  rung 1 improvement) — defensible on current N=12 event library.")
    w()

w("─" * 70)
w(f"  Effective N: {n_events} events  |  Station rows (pseudoreplication if used as N): {len(station_rows)}")
w("  Do not report station-level N for regime comparisons.")
w()
w("END OF REGIME EVENT REPORT")

report_str = "\n".join(lines)
print(report_str)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(report_str + "\n")
print(f"\nReport → {REPORT}")
