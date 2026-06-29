#!/usr/bin/env python3
"""
StormWatch Live — National Threat Index + ML anomaly check (Path C, Layer 3) [OFFLINE]

Layer 2 grades each hazard on its own. Layer 3 looks at the WHOLE PICTURE: how
unusual is the current *combination* of elevated hazards versus 18 years of hours?
A day with simultaneously high tornado + severe + flash-flood activity is a
"national severe weather day" even if no single hazard sets a record.

Two things happen here, both offline:
  1. Compute each archive hour's multi-hazard SURPRISE vector (from Layer 2's
     conditional model), reduce to a composite "activity" score, and store the
     historical distribution so the live scorer can report today's percentile
     (a 0-100 National Threat Index) using pure stdlib.
  2. Train an Isolation Forest on the surprise vectors as an independent ML cross-
     check, and print the most anomalous hours it finds — these should be the
     famous outbreaks/storms, confirming the index tracks real events.

Output: data/composite_model.json  (headline hazard list + composite percentiles)
Usage:  python build_composite.py
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import IsolationForest

import alerts_monitor as A   # reuse conditional_surprise / expected_lambda

ARCHIVE = os.path.join("data", "baseline_hourly.jsonl")
MODEL = os.path.join("data", "baseline_model.json")
OUT = os.path.join("data", "composite_model.json")

# Headline hazards grouped into FAMILIES. The composite takes the max surprise
# within each family before summing, so one weather regime (e.g. heat+fire, or
# severe+tornado) counts once per family instead of multiplying correlated alerts.
FAMILIES = {
    "severe": ["Tornado Warning", "Tornado Watch", "Severe Thunderstorm Warning",
               "Severe Thunderstorm Watch"],
    "flood": ["Flash Flood Warning", "Flood Warning"],
    "wind": ["High Wind Warning", "Wind Advisory"],
    "fire": ["Red Flag Warning", "Fire Weather Watch"],
    "heat": ["Extreme Heat Warning", "Heat Advisory"],
    "winter": ["Winter Storm Warning", "Blizzard Warning", "Ice Storm Warning"],
    "tropical": ["Hurricane Warning", "Tropical Storm Warning"],
}
HEADLINE = [h for fam in FAMILIES.values() for h in fam]


def parse_t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def main():
    rows = [json.loads(l) for l in open(ARCHIVE, encoding="utf-8") if l.strip()]
    rows.sort(key=lambda r: r["t"])
    model = json.load(open(MODEL, encoding="utf-8"))["hazards"]
    headline = [h for h in HEADLINE if h in model]
    print(f"{len(rows)} hours; {len(headline)} headline hazards modeled")

    times = [parse_t(r["t"]) for r in rows]
    # Surprise matrix: per hour, per headline hazard (season/time-conditioned).
    S = np.zeros((len(rows), len(headline)), dtype=float)
    for j, haz in enumerate(headline):
        hm = model[haz]
        for i, r in enumerate(rows):
            c = r["by_event"].get(haz, 0)
            if c:
                s, _, _ = A.conditional_surprise(c, times[i], hm)
                S[i, j] = s

    # Composite "activity": sum over FAMILIES of the family's peak excess anomaly,
    # so correlated alerts in one regime don't multiply the score.
    col = {h: j for j, h in enumerate(headline)}
    composite = np.zeros(len(rows))
    for fam, hs in FAMILIES.items():
        idx = [col[h] for h in hs if h in col]
        if idx:
            composite += np.clip(S[:, idx].max(axis=1) - 1.0, 0, None)

    # Historical distribution -> percentile lookup for the live index.
    pctls = [50, 75, 90, 95, 97.5, 99, 99.5, 99.9, 99.97, 99.99]
    table = [[p, round(float(np.percentile(composite, p)), 3)] for p in pctls]
    cmax = float(composite.max())

    # --- ML cross-check: Isolation Forest on the surprise vectors ---
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=0)
    iso.fit(S)
    anom = -iso.score_samples(S)            # higher = more anomalous

    def top(score, k=8):
        idx = np.argsort(score)[::-1][:k]
        return [(rows[i]["t"], round(float(score[i]), 2),
                 sorted(((h, rows[i]["by_event"].get(h, 0)) for h in headline
                         if rows[i]["by_event"].get(h, 0) > 0),
                        key=lambda kv: -kv[1])[:4]) for i in idx]

    print("\nMost anomalous hours by COMPOSITE index:")
    for t, sc, haz in top(composite):
        print(f"  {t}  idx={sc:6.2f}  " + ", ".join(f"{h}:{n}" for h, n in haz))
    print("\nMost anomalous hours by ISOLATION FOREST (independent ML):")
    for t, sc, haz in top(anom):
        print(f"  {t}  if={sc:5.2f}  " + ", ".join(f"{h}:{n}" for h, n in haz))

    out = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "headline": headline,
        "families": FAMILIES,
        "composite_pctl": table,     # [[percentile, composite_value], ...]
        "composite_max": round(cmax, 3),
        "hours": len(rows),
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
