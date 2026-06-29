#!/usr/bin/env python3
"""
StormWatch Live — Baseline Count Models (Path C, Layer 2)  [OFFLINE TRAINER]

Learns, per hazard, the EXPECTED number of active alerts as a smooth function of
season + time of day (and their interaction), from the 18-year IEM archive built
in Layer 1. Fits a Poisson regression on harmonic features, then estimates
overdispersion so the live scorer can compute a calibrated negative-binomial
tail probability ("how rare is the current count, really?").

Heavy lifting (numpy/sklearn) happens HERE, offline. Output is a tiny coefficient
file, data/baseline_model.json, that the live monitor evaluates with pure stdlib.

Feature vector for a timestamp (season + diurnal + interaction), NO constant term
(intercept fit separately) — MUST stay identical to features() in alerts_monitor.py:

  annual k=1..3 : sin/cos(2*pi*k*doy/365.25)          (6)
  diurnal k=1..3: sin/cos(2*pi*k*hour/24)             (6)
  weekly        : sin/cos(2*pi*dow/7)                  (2)
  interaction   : annual1{sin,cos} x diurnal1{sin,cos} (4)
                                                 total 18

Usage:  python build_baselines.py
"""

import json
import math
import os
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import PoissonRegressor

ARCHIVE = os.path.join("data", "baseline_hourly.jsonl")
LIVE_HISTORY = os.path.join("data", "alert_history.jsonl")   # folded in if present
MODEL_OUT = os.path.join("data", "baseline_model.json")

# Only model hazards with enough signal to fit a seasonal curve.
MIN_NONZERO_HOURS = 200
MIN_TOTAL = 500
MIN_CELL = 100             # min samples for a (month, hour-bucket) cell to be trusted

FEATURE_ORDER = [
    "ann1_sin", "ann1_cos", "ann2_sin", "ann2_cos", "ann3_sin", "ann3_cos",
    "diu1_sin", "diu1_cos", "diu2_sin", "diu2_cos", "diu3_sin", "diu3_cos",
    "wk_sin", "wk_cos",
    "ann1sin_diu1sin", "ann1sin_diu1cos", "ann1cos_diu1sin", "ann1cos_diu1cos",
]


def features(doy, hour, dow):
    """18-dim feature vector (no constant). Pure math so it ports to the live scorer."""
    A = 2 * math.pi * doy / 365.25
    H = 2 * math.pi * hour / 24.0
    W = 2 * math.pi * dow / 7.0
    a1s, a1c = math.sin(A), math.cos(A)
    d1s, d1c = math.sin(H), math.cos(H)
    return [
        a1s, a1c, math.sin(2 * A), math.cos(2 * A), math.sin(3 * A), math.cos(3 * A),
        d1s, d1c, math.sin(2 * H), math.cos(2 * H), math.sin(3 * H), math.cos(3 * H),
        math.sin(W), math.cos(W),
        a1s * d1s, a1s * d1c, a1c * d1s, a1c * d1c,
    ]


def load_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def parse_t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def main():
    rows = load_rows(ARCHIVE) + load_rows(LIVE_HISTORY)
    if not rows:
        print("No archive found. Run backfill_iem.py first.")
        return 2
    # Deduplicate by timestamp (archive + any live overlap), keep latest.
    by_t = {}
    for r in rows:
        by_t[r["t"]] = r
    rows = [by_t[t] for t in sorted(by_t)]
    print(f"Loaded {len(rows)} hourly snapshots "
          f"({rows[0]['t']} -> {rows[-1]['t']})")

    # Time features (shared across hazards) + the universe of hazard names.
    times = [parse_t(r["t"]) for r in rows]
    X = np.array([features(t.timetuple().tm_yday, t.hour, t.weekday()) for t in times],
                 dtype=float)
    n = len(rows)

    hazards = {}
    for r in rows:
        for h in r["by_event"]:
            hazards[h] = hazards.get(h, 0) + 1

    model = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive_rows": n,
        "coverage": [rows[0]["t"], rows[-1]["t"]],
        "feature_order": FEATURE_ORDER,
        "hazards": {},
    }

    # Conditional cells: month (1-12) x 6-hour UTC bucket (0-3). Each cell pools
    # ~18yr x ~30d x 6h ~= 3200 samples, enough to resolve the seasonal/diurnal
    # count distribution. The live scorer asks "where does the current count rank
    # among [this month][this time-of-day] counts over 18 years?"
    months = np.array([t.month for t in times])
    hbucket = np.array([t.hour // 6 for t in times])

    def qsummary(arr):
        if arr.size == 0 or arr.max() == 0:
            return None
        qs = [round(float(np.quantile(arr, p)), 2) for p in (0.5, 0.9, 0.95, 0.99, 0.999)]
        return {"n": int(arr.size), "q": qs, "max": int(arr.max())}

    fitted, skipped = 0, 0
    for haz in sorted(hazards):
        y = np.array([r["by_event"].get(haz, 0) for r in rows], dtype=float)
        nonzero = int((y > 0).sum())
        total = float(y.sum())
        if nonzero < MIN_NONZERO_HOURS or total < MIN_TOTAL:
            skipped += 1
            continue

        # Smooth seasonal/diurnal mean (for "expected ~N" display only).
        reg = PoissonRegressor(alpha=1e-4, max_iter=500, fit_intercept=True)
        reg.fit(X, y)

        # Conditional count distribution per cell, plus a global fallback.
        cells = {}
        for m in range(1, 13):
            for hb in range(4):
                c = qsummary(y[(months == m) & (hbucket == hb)])
                if c and c["n"] >= MIN_CELL:
                    cells[f"{m}-{hb}"] = c

        model["hazards"][haz] = {
            "intercept": float(reg.intercept_),
            "coef": [float(c) for c in reg.coef_],
            "cells": cells,                 # "month-hourbucket" -> {n, q, max}
            "glob": qsummary(y),            # fallback if a cell is too sparse
            "mean": round(float(y.mean()), 3),
            "max": int(y.max()),
            "nonzero_hours": nonzero,
        }
        fitted += 1

    os.makedirs("data", exist_ok=True)
    with open(MODEL_OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    size_kb = os.path.getsize(MODEL_OUT) / 1024
    print(f"Fitted {fitted} hazards, skipped {skipped} sparse ones.")
    print(f"Wrote {MODEL_OUT} ({size_kb:.1f} KB)")

    # --- Quick sanity check: score the Apr 27 2011 super outbreak ---
    print("\nSanity check — Tornado Warning model:")
    tw = model["hazards"].get("Tornado Warning")
    if tw:
        for label, t in [("Apr 27 2011 21Z (outbreak)", datetime(2011, 4, 27, 21, tzinfo=timezone.utc)),
                         ("Jan 15 2011 21Z (quiet)", datetime(2011, 1, 15, 21, tzinfo=timezone.utc))]:
            fv = features(t.timetuple().tm_yday, t.hour, t.weekday())
            lam = math.exp(tw["intercept"] + sum(c * x for c, x in zip(tw["coef"], fv)))
            print(f"  expected lambda {label:30s} = {lam:6.2f}  (observed peak that day: see archive)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
