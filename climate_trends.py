#!/usr/bin/env python3
"""
StormWatch Live — Climate-vs-Weather Trend Analysis  [OFFLINE, research]

Where a climate-change signal meets the meteorological/observing record.

This asks, per hazard: over 2008-2025, is the number of NWS warnings trending,
and if so, is that trend a *physical* signal or an artifact of how the Weather
Service changed its warning practices? Naive "warnings are going up, therefore
climate change" is wrong — the alert record is confounded by policy. This script
is built to NOT make that mistake.

Methods (all standard in climatology / hydrology):
  - Mann-Kendall test: non-parametric monotonic-trend detection (tau, p), with
    tie correction. Robust to non-normal, skewed count data.
  - Theil-Sen slope: median-of-pairwise-slopes trend magnitude (robust to outliers).
  - Pettitt change-point test: finds the year of an abrupt shift (if any).
  - OBSERVING-SYSTEM AUDIT: a table of known NWS warning-practice changes. If a
    detected trend or change-point lines up with one, it is flagged as a likely
    artifact, not climate.

HONEST LIMITATIONS (printed in the output too):
  - 18 years is SHORT for climate detection (climate normals are 30 yr). This can
    catch strong trends; it is underpowered for subtle ones.
  - The endpoints sit in particular ENSO phases, which inflate/deflate apparent
    trends. Interannual variability (ENSO/PDO) is large for severe weather.
  - Warning *counts* are a proxy for hazard occurrence, filtered through detection
    (radar upgrades, more spotters) and policy (criteria, polygon vs county).
  So: results are SCREENING, not attribution. Treat "candidate signal" as
  "worth a real study," never as proof.

Output: data/climate_trends.json + a printed findings table.
Usage:  python climate_trends.py        (needs data/baseline_hourly.jsonl)
"""

import json
import math
import os
from collections import defaultdict

import numpy as np
from scipy import stats

ARCHIVE = os.path.join("data", "baseline_hourly.jsonl")
OUT = os.path.join("data", "climate_trends.json")

# Complete calendar years only (2026 is partial -> excluded from annual trends).
YEAR_START, YEAR_END = 2008, 2025

HEADLINE = [
    "Tornado Warning", "Tornado Watch", "Severe Thunderstorm Warning",
    "Flash Flood Warning", "Flood Warning", "High Wind Warning",
    "Red Flag Warning", "Fire Weather Watch", "Extreme Heat Warning",
    "Heat Advisory", "Excessive Heat Warning", "Winter Storm Warning",
    "Blizzard Warning", "Ice Storm Warning", "Hurricane Warning",
    "Tropical Storm Warning", "Dense Fog Advisory",
]

# Known NWS warning-PRACTICE changes that confound counts (year, what changed).
# If a trend/change-point lines up with one of these, suspect artifact, not climate.
OBS_CHANGES = {
    "Tornado Warning": [(2007, "storm-based polygon warnings replaced county-based"),
                        (2012, "Impact-Based Warnings pilot; expanded ~2016 nationwide")],
    "Severe Thunderstorm Warning": [(2007, "storm-based polygons"),
                                    (2021, "'destructive' damage-threat tags added")],
    "Flash Flood Warning": [(2007, "storm-based polygons"),
                            (2012, "Impact-Based / FFW tags")],
    "Extreme Heat Warning": [(2024, "'Excessive Heat Warning' renamed 'Extreme Heat Warning'; criteria updates")],
    "Excessive Heat Warning": [(2024, "renamed to 'Extreme Heat Warning' — series splits here")],
    "Heat Advisory": [(2024, "heat product overhaul (HeatRisk era)")],
    "Red Flag Warning": [(2013, "expanded fire-weather program coverage")],
    "_GLOBAL_": [(2011, "dual-pol radar rollout 2011-2013 improved detection")],
}


def mann_kendall(x):
    """Return (tau, p_two_sided, z, S). Tie-corrected normal approximation."""
    x = np.asarray(x, float)
    n = len(x)
    s = 0
    for i in range(n - 1):
        s += np.sum(np.sign(x[i + 1:] - x[i]))
    _, counts = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18.0
    if var <= 0:
        return 0.0, 1.0, 0.0, int(s)
    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    tau = s / (0.5 * n * (n - 1))
    return float(tau), float(p), float(z), int(s)


def pettitt(x):
    """Pettitt change-point test. Return (change_index, approx_p)."""
    x = np.asarray(x, float)
    n = len(x)
    r = stats.rankdata(x)
    U = np.array([2 * np.sum(r[:k]) - k * (n + 1) for k in range(1, n + 1)])
    K = int(np.argmax(np.abs(U)))
    Kstat = abs(U[K])
    p = 2.0 * math.exp(-6.0 * Kstat ** 2 / (n ** 3 + n ** 2))
    return K, float(min(1.0, p))


def near_obs_change(haz, year, window=1):
    hits = list(OBS_CHANGES.get(haz, [])) + OBS_CHANGES["_GLOBAL_"]
    return [desc for (yr, desc) in hits if abs(yr - year) <= window]


def main():
    if not os.path.exists(ARCHIVE):
        print("Need data/baseline_hourly.jsonl — run backfill_iem.py first.")
        return 2

    # Annual aggregates per hazard: total warning-hours and annual peak.
    years = list(range(YEAR_START, YEAR_END + 1))
    tot = defaultdict(lambda: defaultdict(float))   # haz -> year -> sum hourly counts
    pk = defaultdict(lambda: defaultdict(int))      # haz -> year -> max simultaneous
    for line in open(ARCHIVE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        y = int(r["t"][:4])
        if y < YEAR_START or y > YEAR_END:
            continue
        for h, c in r["by_event"].items():
            tot[h][y] += c
            if c > pk[h][y]:
                pk[h][y] = c

    results = []
    for haz in HEADLINE:
        if haz not in tot:
            continue
        series = np.array([tot[haz].get(y, 0.0) for y in years])
        if series.sum() < 500 or (series > 0).sum() < 10:
            continue  # too sparse to analyze

        tau, p, z, S = mann_kendall(series)
        slope, intercept, lo, hi = stats.theilslopes(series, years)
        cp_idx, cp_p = pettitt(series)
        cp_year = years[cp_idx]
        mean = series.mean()
        # percent change over the record from the robust slope
        pct = (slope * (len(years) - 1)) / mean * 100 if mean > 0 else 0.0

        direction = "increasing" if tau > 0 else "decreasing" if tau < 0 else "flat"
        sig = p < 0.05
        cp_sig = cp_p < 0.05
        obs_flags = near_obs_change(haz, cp_year) if cp_sig else []

        # Verdict logic — conservative.
        if not sig:
            verdict = "No significant trend"
        elif cp_sig and obs_flags:
            verdict = "Likely observing-system artifact"
        elif cp_sig and not obs_flags:
            verdict = "Candidate signal — abrupt shift, no known policy change (verify)"
        else:
            verdict = "Candidate signal — gradual trend (verify against ENSO/policy)"

        results.append({
            "hazard": haz,
            "years": [years[0], years[-1]],
            "annual_mean_hours": round(mean, 1),
            "mk_tau": round(tau, 3),
            "mk_p": round(p, 4),
            "direction": direction,
            "theilsen_slope_per_yr": round(float(slope), 2),
            "pct_change_over_record": round(pct, 1),
            "changepoint_year": cp_year,
            "changepoint_p": round(cp_p, 4),
            "obs_change_flags": obs_flags,
            "verdict": verdict,
        })

    results.sort(key=lambda r: (r["verdict"], r["mk_p"]))
    doc = {
        "method": "Mann-Kendall + Theil-Sen + Pettitt, with NWS observing-system audit",
        "window": f"{YEAR_START}-{YEAR_END} (complete years; 2026 partial excluded)",
        "caveats": [
            "18 years is short for climate detection (normals are 30 yr).",
            "Endpoints sit in particular ENSO phases; interannual variability is large.",
            "Counts are a proxy filtered through detection + policy changes.",
            "This is SCREENING, not attribution. 'Candidate' != proof.",
        ],
        "results": results,
    }
    os.makedirs("data", exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1)

    # ---- printed findings ----
    print(f"CLIMATE-VS-WEATHER TREND SCREEN  ({YEAR_START}-{YEAR_END})\n")
    print(f"{'hazard':30s}{'dir':>11s}{'%/record':>10s}{'MK p':>8s}  verdict")
    for r in results:
        print(f"{r['hazard']:30s}{r['direction']:>11s}{r['pct_change_over_record']:>9.0f}%"
              f"{r['mk_p']:>8.3f}  {r['verdict']}")
    print("\nCAVEATS:")
    for c in doc["caveats"]:
        print(f"  - {c}")
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
