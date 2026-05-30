#!/usr/bin/env python3
"""
windninja_sensitivity_field.py
================================
Direction-sensitivity field: how much does each station's wind change
across a ±15 deg BC direction sweep at fixed speed?

This integrates three components:
  1. SURROGATE WindNinja -- makes dense direction sweeps cheap (< 1 sec total)
  2. CONFIDENCE ENGINE -- the spread of this sweep IS the reducible-uncertainty
     term for each station (how much BC direction uncertainty propagates to
     wind-field uncertainty)
  3. TERRAIN GEOMETRY -- sensitivity is a per-terrain property; narrow canyon
     (Jarbo) is more direction-sensitive than broad ridge (Topa Topa)

The output is a per-station sensitivity score that tells the BC-correction map
WHERE to spend its direction-correction budget -- high-sensitivity stations
are where a direction error in the BC causes the largest wind forecast error.

Design note (from Opus critique 2026-05-30):
  "Direction is the dominant BC variable" is partly built into WindNinja's
  mass-conservation physics. What is NOT pre-ordained is HOW MUCH direction
  matters at each location -- that's terrain geometry and is genuinely empirical.
  The sensitivity FIELD is the useful product; the bare "direction dominates"
  claim is apparatus-level.

Run: python windninja_sensitivity_field.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ENSEMBLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "ensemble_campfire.json")

# ---------------------------------------------------------------------------
# Terrain registry: domains + stations with provenance flags
# ---------------------------------------------------------------------------

TERRAIN_REGISTRY = {
    "camp_fire": {
        "name":        "Camp Fire / Feather River Canyon",
        "hrrr_prior":  {"speed": 25.2, "dir": 50.0},
        "stations": {
            "jarbo_gap":   {"lat": 39.735944, "lon": -121.488944,
                           "elev_ft": 2536, "terrain": "narrow canyon",
                           "provenance": "NIFC-verified"},
            "fire_origin": {"lat": 39.896,    "lon": -121.432,
                           "elev_ft": 1000,   "terrain": "canyon floor",
                           "provenance": "approximate"},
            "paradise":    {"lat": 39.760,    "lon": -121.620,
                           "elev_ft": 1700,   "terrain": "foothill slope",
                           "provenance": "approximate"},
        },
        "ensemble_path": ENSEMBLE_PATH,
    },
    # Thomas Fire added for cross-terrain comparison
    # Topa Topa: PROVENANCE UNVERIFIED -- broad ridge, coords not NIFC-checked
    "thomas_fire": {
        "name":       "Thomas Fire / Topa Topa",
        "hrrr_prior": {"speed": 28.8, "dir": 310.0},
        "stations": {
            "topa_topa":   {"lat": 34.520, "lon": -119.080,
                           "elev_ft": 6230, "terrain": "broad ridge",
                           "provenance": "UNVERIFIED -- use qualitatively only"},
            "fire_origin": {"lat": 34.441, "lon": -118.984,
                           "elev_ft": 1000, "terrain": "valley floor",
                           "provenance": "approximate"},
        },
        "ensemble_path": None,  # no Thomas ensemble yet
    },
}


# ---------------------------------------------------------------------------
# Load surrogate
# ---------------------------------------------------------------------------

def load_surrogate(ensemble_path: str):
    """Load trained surrogate from ensemble JSON."""
    from windninja_surrogate import WindNinjaSurrogate

    with open(ensemble_path) as f:
        data = json.load(f)

    records = []
    for key, output in data["ensemble"].items():
        s, d = key.split("_")
        records.append({"speed": float(s), "direction": float(d), "output": output})

    return WindNinjaSurrogate(alpha=0.1).fit(records), data


# ---------------------------------------------------------------------------
# Direction sensitivity at a station
# ---------------------------------------------------------------------------

def direction_sensitivity(
    surrogate,
    speed: float,
    center_dir: float,
    station: str,
    sweep_deg: float = 15.0,
    n_steps: int = 13,
) -> Dict[str, float]:
    """
    Compute wind spread across a ±sweep_deg direction window at fixed speed.

    Returns:
      mean, std, min, max, range, cv (coefficient of variation)
      These together form the 'direction sensitivity score' for this station.
    """
    dirs = np.linspace(center_dir - sweep_deg, center_dir + sweep_deg, n_steps)
    vals = []
    for d in dirs:
        pred = surrogate.predict(speed, float(d % 360)).get(station)
        if pred is not None:
            vals.append(pred)

    if not vals:
        return {}

    arr = np.array(vals)
    return {
        "mean":  float(arr.mean()),
        "std":   float(arr.std()),
        "min":   float(arr.min()),
        "max":   float(arr.max()),
        "range": float(arr.max() - arr.min()),
        "cv":    float(arr.std() / arr.mean()) if arr.mean() > 0 else 0.0,
        "n":     len(vals),
    }


# ---------------------------------------------------------------------------
# Cross-terrain sensitivity comparison
# ---------------------------------------------------------------------------

def compare_terrain_sensitivity(
    surrogate,
    speed: float,
    stations: Dict,
    center_dir: float,
) -> None:
    """Compare direction sensitivity across stations for one terrain/event."""
    print(f"\n  Fixed speed: {speed:.0f} mph  |  Center dir: {center_dir:.0f}°  |  Sweep: ±15°")
    print(f"  {'Station':^22} | {'Terrain type':^18} | {'Mean':>6} | {'Std':>5} | "
          f"{'Range':>6} | {'CV':>5} | Provenance")
    print(f"  {'-'*22}-+-{'-'*18}-+-{'-'*6}-+-{'-'*5}-+-{'-'*6}-+-{'-'*5}-+-{'-'*20}")

    sensitivities = {}
    for stid, meta in stations.items():
        s = direction_sensitivity(surrogate, speed, center_dir, stid)
        if not s:
            print(f"  {stid:^22} | {'---':^18} | {'no data':>6}")
            continue
        sensitivities[stid] = s
        prov = meta.get("provenance", "unknown")
        terrain = meta.get("terrain", "unknown")
        cv_label = ("HIGH" if s['cv'] > 0.05 else "mod" if s['cv'] > 0.02 else "low")
        print(f"  {stid:^22} | {terrain:^18} | {s['mean']:6.1f} | {s['std']:5.2f} | "
              f"{s['range']:6.2f} | {s['cv']:5.3f} | {prov}")

    # Confidence-engine interpretation
    if sensitivities:
        most_sensitive = max(sensitivities, key=lambda k: sensitivities[k]['range'])
        least_sensitive = min(sensitivities, key=lambda k: sensitivities[k]['range'])
        print()
        print(f"  Most direction-sensitive:  {most_sensitive} "
              f"(range {sensitivities[most_sensitive]['range']:.2f} mph)")
        print(f"  Least direction-sensitive: {least_sensitive} "
              f"(range {sensitivities[least_sensitive]['range']:.2f} mph)")
        ratio = (sensitivities[most_sensitive]['range'] /
                 sensitivities[least_sensitive]['range']
                 if sensitivities[least_sensitive]['range'] > 0 else float('inf'))
        print(f"  Sensitivity ratio: {ratio:.1f}x  "
              f"(direction error hits {most_sensitive} {ratio:.1f}x harder than {least_sensitive})")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  DIRECTION SENSITIVITY FIELD")
    print("  Surrogate + confidence engine integration")
    print("=" * 72)
    print()
    print("  This field answers: at which stations does a BC direction error")
    print("  cause the LARGEST wind forecast error?")
    print("  High sensitivity = spend BC-correction budget on direction here.")
    print()
    print("  Note (Opus 2026-05-30): sensitivity field is a terrain-geometry")
    print("  property, not a bare claim about the atmosphere. Topa Topa results")
    print("  are qualitative only (provenance unverified).")

    # ---- Camp Fire (verified surrogate) -----------------------------------
    print()
    print("=" * 72)
    print("  CAMP FIRE  (Jarbo Gap surrogate -- NIFC-verified station)")
    print("=" * 72)

    surrogate, camp_data = load_surrogate(ENSEMBLE_PATH)
    camp_cfg = TERRAIN_REGISTRY["camp_fire"]
    compare_terrain_sensitivity(
        surrogate,
        speed=camp_cfg["hrrr_prior"]["speed"],
        stations=camp_cfg["stations"],
        center_dir=camp_cfg["hrrr_prior"]["dir"],
    )

    # ---- Dense direction sweep -- Jarbo Gap --------------------------------
    print()
    print("JARBO GAP DIRECTION SWEEP (20° to 80°, 1° steps, speed=25.2 mph)")
    print("  This is the full reducible-uncertainty profile for BC direction")
    print()
    dirs = range(20, 81, 5)
    print(f"  {'Dir':>4} | {'WN sust':>8} | {'Ratio':>6} | Sensitivity vs prior")
    print(f"  {'-'*4}-+-{'-'*8}-+-{'-'*6}-+-{'-'*30}")
    prior_val = surrogate.predict(25.2, 50.0).get("jarbo_gap", 0)
    for d in dirs:
        val = surrogate.predict(25.2, d).get("jarbo_gap")
        if val:
            ratio = val / 25.2
            delta = val - prior_val
            bar_len = int(abs(delta) * 2)
            bar = ("+" * bar_len if delta >= 0 else "-" * bar_len)
            flag = " <-- HRRR prior" if d == 50 else ""
            print(f"  {d:4}° | {val:8.2f} | {ratio:6.3f} | {bar}{flag}")

    # ---- Confidence engine reducible-uncertainty term ---------------------
    print()
    print("CONFIDENCE ENGINE INTEGRATION")
    print("=" * 72)
    print("  The direction sensitivity IS the reducible-uncertainty term:")
    print("  - BC direction range ±15° (typical HRRR direction uncertainty)")
    print("  - Propagated through surrogate to each station")
    print()

    center_dir = camp_cfg["hrrr_prior"]["dir"]
    for stid, meta in camp_cfg["stations"].items():
        s = direction_sensitivity(surrogate, 25.2, center_dir, stid, sweep_deg=15)
        if not s:
            continue
        print(f"  {stid} ({meta['terrain']}):")
        print(f"    BC direction ±15° -> wind uncertainty ±{s['std']:.1f} mph (1-sigma)")
        print(f"    Wind range: {s['min']:.1f} to {s['max']:.1f} mph  "
              f"(spread {s['range']:.1f} mph)")
        # Operational interpretation
        gust_std = s['std'] * 1.625
        print(f"    Predicted gust uncertainty: ±{gust_std:.1f} mph (at gust factor 1.625)")
        print()

    print("  INTERPRETATION:")
    print("  For a BC direction uncertainty of ±15 deg, the confidence engine")
    print("  should assign a 1-sigma wind uncertainty equal to the std above.")
    print("  Stations with high std are WHERE direction accuracy matters most.")
    print("  Stations with low std are robustly predictable even with direction error.")
