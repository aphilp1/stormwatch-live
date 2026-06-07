#!/usr/bin/env python3
"""
regime_gate.py  —  Regime-conditioned departure analysis
Phase A follow-up: terrain gate failed; test synoptic_regime as grouping variable.

Dataset : hrrr_error_dataset_dem.csv  (164 active rows)
Outcome : speed_err  (HRRR 10m mph − obs sustained mph)

Gate logic (mirrors merge_dem_and_gate.py):
  1. Structured-vs-white ratio on synoptic_regime.
  2. Rule #0: OLS(speed_err ~ repr_error_flag) → residuals → regime s/w.
     repr_error_flag is station-level; it can inflate a regime ratio if regimes
     cluster geographically by terrain ruggedness. If ratio survives → real signal.

Run in any env with numpy (dem env works fine).
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
REPORT     = os.path.join(BASE, "regime_gate_report.txt")


# ── helpers ───────────────────────────────────────────────────────────────────

def structured_vs_white(groups):
    """
    groups: dict of label → list of float values.
    Returns (ratio, between_var, pooled_within_var).
    """
    all_vals = [v for vals in groups.values() for v in vals]
    overall_mean = np.mean(all_vals)

    group_means = {k: np.mean(v) for k, v in groups.items()}
    group_ns    = {k: len(v)     for k, v in groups.items()}
    n_total     = len(all_vals)

    # Between-class variance (weighted by group size)
    between = sum(
        group_ns[k] * (group_means[k] - overall_mean) ** 2
        for k in groups
    ) / n_total

    # Pooled within-class variance
    within_num = sum(
        sum((v - group_means[k]) ** 2 for v in vals)
        for k, vals in groups.items()
    )
    within = within_num / n_total

    ratio = between / within if within > 0 else float("nan")
    return ratio, between, within


def ols_residuals(X, y):
    """OLS y ~ 1 + X, return (residuals, slope, intercept, r2)."""
    Xm = np.column_stack([np.ones(len(X)), X])
    beta, _, _, _ = np.linalg.lstsq(Xm, y, rcond=None)
    pred  = Xm @ beta
    resid = y - pred
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return resid, float(beta[1]), float(beta[0]), r2


# ── load data ─────────────────────────────────────────────────────────────────

rows = []
with open(IN_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        try:
            speed_err = float(r["speed_err"])
        except (ValueError, TypeError):
            continue
        regime = r.get("synoptic_regime", "").strip() or "unknown"
        try:
            repr_ef = float(r["repr_error_flag"])
        except (ValueError, TypeError):
            repr_ef = None
        rows.append({
            "stid":            r["stid"],
            "event_id":        r["event_id"],
            "speed_err":       speed_err,
            "synoptic_regime": regime,
            "terrain_class":   r.get("terrain_class", "open"),
            "repr_error_flag": repr_ef,
        })

n_total = len(rows)

# Rows usable for Rule #0 (need repr_error_flag)
rows_r0 = [r for r in rows if r["repr_error_flag"] is not None]

# ── build groups ──────────────────────────────────────────────────────────────

regime_groups = defaultdict(list)
for r in rows:
    regime_groups[r["synoptic_regime"]].append(r["speed_err"])

# Sort by mean speed_err for readability
sorted_regimes = sorted(regime_groups.keys(), key=lambda k: np.mean(regime_groups[k]))

# ── gate 1 ────────────────────────────────────────────────────────────────────

ratio1, between1, within1 = structured_vs_white(regime_groups)

# ── gate 2 — Rule #0 ─────────────────────────────────────────────────────────

X_r0   = np.array([r["repr_error_flag"] for r in rows_r0])
y_r0   = np.array([r["speed_err"]       for r in rows_r0])
resid_r0, slope_r0, intercept_r0, r2_r0 = ols_residuals(X_r0, y_r0)

regime_groups_r0 = defaultdict(list)
for i, r in enumerate(rows_r0):
    regime_groups_r0[r["synoptic_regime"]].append(float(resid_r0[i]))

ratio2, between2, within2 = structured_vs_white(regime_groups_r0)

ratio_retained = (ratio2 / ratio1) if ratio1 > 0 else float("nan")

# ── verdict ───────────────────────────────────────────────────────────────────

gate1_pass = ratio1 > 1.0
gate2_pass = ratio2 > 1.0 and ratio_retained >= 0.70

if gate1_pass and gate2_pass:
    verdict = "PHASE B GREEN LIGHT — regime signal is real and survives repr control."
elif gate1_pass and not gate2_pass:
    verdict = "PHASE B RED — regime ratio > 1 but collapses after repr control (representativeness artifact)."
elif not gate1_pass:
    verdict = "PHASE B RED — no regime structure in speed departures (ratio ≤ 1)."
else:
    verdict = "INDETERMINATE"

# ── write report ─────────────────────────────────────────────────────────────

lines = []
def w(s=""): lines.append(s)

w("=" * 70)
w("REGIME GATE REPORT  —  Phase A follow-up")
w(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
w("=" * 70)
w()
w(f"Dataset: {IN_CSV}")
w(f"Active rows (KEEP+CAUTION) with numeric speed_err: {n_total}")
w(f"Rows with repr_error_flag for Rule #0:             {len(rows_r0)}")
w()

w("─" * 70)
w("GATE 1: STRUCTURED-VS-WHITE on synoptic_regime  (PROVISIONAL)")
w(f"  speed_err (HRRR 10m mph − obs)  n={n_total}")
w()
for reg in sorted_regimes:
    vals = regime_groups[reg]
    w(f"  {reg:<30} n={len(vals):4d}  mean={np.mean(vals):+7.2f}  std={np.std(vals):6.2f}")
w()
w(f"  Between-regime variance:  {between1:.4f}")
w(f"  Pooled within-regime:     {within1:.4f}")
w(f"  RATIO:                    {ratio1:.4f}  {'> 1 — structured' if gate1_pass else '<= 1 — white'}")
w()

w("─" * 70)
w("GATE 2: RULE #0 SEPARABILITY  (THE green light)")
w("  Q: Does regime explain speed_err AFTER controlling for repr_error_flag?")
w("  Why: rugged-terrain regimes (e.g. santa_ana) could inflate ratio via")
w("       station-level representativeness mismatch, not true forecast error.")
w()
w(f"  Step 1 — OLS  n={len(rows_r0)}:")
w(f"    speed_err = {intercept_r0:+.2f} + {slope_r0:+.4f} × repr_error_flag   R²={r2_r0:.3f}")
w()
w(f"  Step 2 — Structured-vs-white on OLS residuals  n={len(rows_r0)}:")
w()
sorted_r0 = sorted(regime_groups_r0.keys(), key=lambda k: np.mean(regime_groups_r0[k]))
for reg in sorted_r0:
    vals = regime_groups_r0[reg]
    w(f"  {reg:<30} n={len(vals):4d}  mean={np.mean(vals):+7.2f}  std={np.std(vals):6.2f}")
w()
w(f"  Between-regime variance:  {between2:.4f}")
w(f"  Pooled within-regime:     {within2:.4f}")
w(f"  RATIO after control:      {ratio2:.4f}")
w()
w(f"  Ratio before repr control: {ratio1:.4f}")
w(f"  Ratio after  repr control: {ratio2:.4f}")
w(f"  Ratio retained:            {ratio_retained:.1%}")
w()

# Rule #0 interpretation
if not gate1_pass:
    w("  Rule #0: MOOT — Gate 1 already failed (ratio ≤ 1).")
elif gate2_pass:
    w(f"  Rule #0: PASSES — ratio retained {ratio_retained:.1%} ≥ 70%, still > 1.")
    w("  Regime signal is not explained by station-level representativeness.")
else:
    w(f"  Rule #0: FAILS — ratio collapsed after repr control ({ratio_retained:.1%} retained).")
    w("  Apparent regime signal was a representativeness artifact.")

w()
w("─" * 70)
w("VERDICT")
w(f"  {verdict}")
w()
w("END OF REGIME GATE REPORT")

report_str = "\n".join(lines)
print(report_str)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write(report_str + "\n")

print(f"\nReport → {REPORT}")
