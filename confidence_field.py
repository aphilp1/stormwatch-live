#!/usr/bin/env python3
"""
confidence_field.py
===================
Per-station confidence labeling for the WindNinja terrain wind field.

Given a BC input and the pre-computed ensemble + sensitivity results,
assigns labeled confidence scores to each station. The labels answer:
"Should you trust this wind prediction here, and why?"

LABELS (one or more per station):
  BC_SENSITIVITY  High terrain-geometry sensitivity to BC direction error.
                  A direction correction here gives outsized forecast improvement.
  AMPLIFICATION   Terrain amplification at this station relative to BC.
                  Split into: STRONG (>1.3x), MODERATE (1.1-1.3x),
                  AMBIENT (0.9-1.1x), SHELTERED (<0.9x).
  JUMP_REGIME     Station is in or near a hydraulic jump / rotor zone.
                  WindNinja is structurally invalid here — treat as method-out-of-scope.
                  Peak = floor, not ceiling. Route to WRF/WRF-SFIRE.
  OOD             Requested BC is outside the ensemble training envelope.
                  Prediction is extrapolation, not interpolation.
  BC_INVALID      700 hPa is extrapolated below terrain at this domain.
                  High-terrain guard triggered. Use ridgetop-level wind instead.

CONFIDENCE SCORE [0.0 – 1.0]:
  Derived from ensemble spread at the HRRR prior BC:
    - Direction uncertainty: sensitivity std at ±15° (from sensitivity_results.json)
    - Speed uncertainty: ensemble std at prior direction (from ensemble_campfire.json)
  Combined as: 1 / (1 + direction_cv + speed_cv)
  High score = tight ensemble at this station = prediction trustworthy.
  Low score  = wide ensemble = BC error propagates strongly here.

EMPIRICAL FINDING (from sensitivity field, 2026-05-30):
  Direction is the TERRAIN-GEOMETRY-SENSITIVE variable (17.2x ratio at Camp Fire:
  Jarbo narrow canyon vs Paradise open slope). Speed scales ~linearly at all
  stations through mass conservation. The 17.2x ratio is what sets BC_SENSITIVITY
  HIGH vs LOW — not an unconditional "direction dominates" claim.

Inputs:
  ensemble_campfire.json   -- 25-member WN ensemble, station stats, HRRR prior
  sensitivity_results.json -- per-station direction sweep results

Run: python confidence_field.py
"""

from __future__ import annotations

import json
import math
import sys
from typing import Dict, List, Optional

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Thresholds (record when changed -- per protocol)
# ---------------------------------------------------------------------------

THRESHOLDS = {
    # Direction sweep range (mph, ±15°) that triggers HIGH vs LOW sensitivity
    "bc_sensitivity_high_mph": 2.0,
    "bc_sensitivity_mod_mph":  0.5,

    # Amplification ratio brackets
    "amp_strong":   1.30,
    "amp_moderate": 1.10,
    "amp_ambient_lo": 0.90,

    # CV threshold for low-confidence flag
    "cv_low_confidence": 0.15,

    # OOD: fractional margin beyond training envelope
    "ood_margin_pct": 0.05,

    # BC_INVALID: 700 hPa within this many meters of terrain
    "bc_invalid_clearance_m": 200.0,
}


# ---------------------------------------------------------------------------
# Known hydraulic-jump / rotor stations (method-out-of-scope per literature)
# ---------------------------------------------------------------------------

JUMP_REGIME_STATIONS = {
    "stirling_city": "Documented rotor (Brewer & Clements 2020) -- CAL FIRE PG&E station",
}


# ---------------------------------------------------------------------------
# Domain-level 700 hPa terrain guard
# ---------------------------------------------------------------------------

DOMAIN_GUARD = {
    "camp_fire": {
        "max_terrain_m": 1938,   # Reno 12z sounding inversion base (empirical ceiling)
        "hgt_700_m":     2850,   # approximate 700 hPa height Nov 2018 (warm column)
        "clearance_m":   912,    # 2850 - 1938; well above threshold
        "bc_invalid":    False,  # SAFE: all terrain sub-700 hPa
        "note": "Whole domain sub-inversion (Brewer & Clements 2020 confirms); "
                "700 hPa is ~912m above max terrain. BC_INVALID = False.",
    },
    "missoula_dec2025": {
        "max_terrain_m": 2408,   # PNTM8 ridgetop (NIFC-confirmed)
        "hgt_700_m":     3166,   # OTX 12z sounding (IEM, confirmed valid)
        "clearance_m":   758,    # 3166 - 2408; above threshold
        "bc_invalid":    False,  # SAFE for PNTM8; marginal for lower stations
        "note": "PNTM8 7897ft (2408m) has 758m clearance to 700 hPa. Safe. "
                "Lower-elevation stations well below — no guard needed.",
    },
}


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_inputs(ensemble_path: str, sensitivity_path: str) -> tuple[dict, dict]:
    with open(ensemble_path)   as f: ensemble    = json.load(f)
    with open(sensitivity_path) as f: sensitivity = json.load(f)
    return ensemble, sensitivity


# ---------------------------------------------------------------------------
# Label computation
# ---------------------------------------------------------------------------

def label_bc_sensitivity(dir_range_mph: float) -> tuple[str, str]:
    """Assign BC_SENSITIVITY label and reason from direction sweep range."""
    hi = THRESHOLDS["bc_sensitivity_high_mph"]
    mo = THRESHOLDS["bc_sensitivity_mod_mph"]
    if dir_range_mph >= hi:
        level = "HIGH"
        reason = (f"direction range {dir_range_mph:.2f} mph at ±15° "
                  f">= threshold {hi} mph — terrain amplifies direction errors strongly")
    elif dir_range_mph >= mo:
        level = "MODERATE"
        reason = (f"direction range {dir_range_mph:.2f} mph at ±15° "
                  f"in [{mo}, {hi}) mph — moderate direction sensitivity")
    else:
        level = "LOW"
        reason = (f"direction range {dir_range_mph:.2f} mph at ±15° "
                  f"< threshold {mo} mph — terrain is direction-insensitive here")
    return f"BC_SENSITIVITY:{level}", reason


def label_amplification(wn_speed: float, bc_speed: float) -> tuple[str, str]:
    """Assign AMPLIFICATION label from WN output / BC input ratio."""
    ratio = wn_speed / bc_speed if bc_speed > 0 else 0.0
    st = THRESHOLDS["amp_strong"]
    mo = THRESHOLDS["amp_moderate"]
    lo = THRESHOLDS["amp_ambient_lo"]
    if ratio >= st:
        level = "STRONG"
    elif ratio >= mo:
        level = "MODERATE"
    elif ratio >= lo:
        level = "AMBIENT"
    else:
        level = "SHELTERED"
    reason = f"WN {wn_speed:.1f} mph / BC {bc_speed:.1f} mph = {ratio:.2f}x ({level})"
    return f"AMPLIFICATION:{level}", reason


def check_jump_regime(station_id: str) -> Optional[tuple[str, str]]:
    """Return JUMP_REGIME label if station is in a known rotor zone."""
    if station_id in JUMP_REGIME_STATIONS:
        reason = JUMP_REGIME_STATIONS[station_id]
        return "JUMP_REGIME:OUT_OF_SCOPE", reason
    return None


def check_ood(bc_speed: float, bc_dir: float,
              speed_min: float, speed_max: float,
              dir_min: float, dir_max: float) -> tuple[str, str]:
    """Check if BC is outside ensemble training envelope."""
    margin_pct = THRESHOLDS["ood_margin_pct"]
    spd_lo = speed_min * (1 - margin_pct)
    spd_hi = speed_max * (1 + margin_pct)
    dir_lo = dir_min - 5.0
    dir_hi = dir_max + 5.0

    ood_reasons = []
    if bc_speed < spd_lo or bc_speed > spd_hi:
        ood_reasons.append(f"speed {bc_speed:.1f} outside [{spd_lo:.1f}, {spd_hi:.1f}] mph")
    bc_dir_norm = bc_dir % 360
    if bc_dir_norm < dir_lo or bc_dir_norm > dir_hi:
        ood_reasons.append(f"dir {bc_dir:.0f}° outside [{dir_lo:.0f}, {dir_hi:.0f}]°")

    if ood_reasons:
        return "OOD:TRUE", "BC outside training envelope: " + "; ".join(ood_reasons)
    return "OOD:FALSE", f"BC within ensemble envelope [{spd_lo:.0f}-{spd_hi:.0f}mph, {dir_lo:.0f}-{dir_hi:.0f}deg]"


def check_bc_invalid(domain_id: str) -> tuple[str, str]:
    """Check 700 hPa terrain guard for this domain."""
    guard = DOMAIN_GUARD.get(domain_id)
    if guard is None:
        return "BC_INVALID:UNKNOWN", "Domain not in guard registry"
    if guard["bc_invalid"]:
        return ("BC_INVALID:TRUE",
                f"700 hPa clearance {guard['clearance_m']:.0f}m < "
                f"threshold {THRESHOLDS['bc_invalid_clearance_m']:.0f}m. {guard['note']}")
    return ("BC_INVALID:FALSE",
            f"700 hPa clearance {guard['clearance_m']:.0f}m > "
            f"threshold {THRESHOLDS['bc_invalid_clearance_m']:.0f}m. {guard['note']}")


def confidence_score(dir_cv: float, spd_cv: float) -> float:
    """Combined confidence score [0, 1]. Higher = more confident."""
    return float(1.0 / (1.0 + dir_cv + spd_cv))


# ---------------------------------------------------------------------------
# Per-station confidence field
# ---------------------------------------------------------------------------

def compute_station_confidence(
    station_id:   str,
    domain_id:    str,
    bc_speed:     float,
    bc_dir:       float,
    ensemble:     dict,
    sensitivity:  dict,
) -> dict:
    """Compute full confidence record for one station at a given BC."""

    # --- Ensemble stats at this station ---
    stats = ensemble.get("station_stats", {}).get(station_id, {})
    wn_at_prior = None

    # Find closest ensemble member to the HRRR prior
    prior_speed = ensemble["hrrr_prior"]["speed"]
    prior_dir   = ensemble["hrrr_prior"]["dir"]
    best_dist, best_val = float("inf"), None
    for key, member in ensemble["ensemble"].items():
        s, d = map(float, key.split("_"))
        dist = math.sqrt((s - prior_speed)**2 + ((d - prior_dir + 180) % 360 - 180)**2)
        if dist < best_dist and member.get(station_id) is not None:
            best_dist = dist
            best_val  = member[station_id]
    wn_at_prior = best_val

    # --- Direction sensitivity for this station ---
    sens = sensitivity.get("stations", {}).get(station_id, {})
    dir_sens = sens.get("dir_sensitivity", {})
    dir_range = dir_sens.get("range", 0.0)
    dir_std   = dir_sens.get("std", 0.0)
    dir_cv    = dir_std / wn_at_prior if (wn_at_prior and wn_at_prior > 0) else 0.0

    # Speed CV from ensemble stats
    spd_cv = stats.get("cv", 0.0)

    # --- BC envelope ---
    ens_keys  = list(ensemble["ensemble"].keys())
    all_speeds = [float(k.split("_")[0]) for k in ens_keys]
    all_dirs   = [float(k.split("_")[1]) for k in ens_keys]
    spd_min, spd_max = min(all_speeds), max(all_speeds)
    dir_min, dir_max = min(all_dirs),   max(all_dirs)

    # --- Compute labels ---
    labels  = []
    reasons = {}

    lbl, rsn = label_bc_sensitivity(dir_range)
    labels.append(lbl); reasons["BC_SENSITIVITY"] = rsn

    if wn_at_prior is not None:
        lbl, rsn = label_amplification(wn_at_prior, prior_speed)
        labels.append(lbl); reasons["AMPLIFICATION"] = rsn

    jump = check_jump_regime(station_id)
    if jump:
        lbl, rsn = jump
        labels.append(lbl); reasons["JUMP_REGIME"] = rsn

    lbl, rsn = check_ood(bc_speed, bc_dir, spd_min, spd_max, dir_min, dir_max)
    labels.append(lbl); reasons["OOD"] = rsn

    lbl, rsn = check_bc_invalid(domain_id)
    labels.append(lbl); reasons["BC_INVALID"] = rsn

    score = confidence_score(dir_cv, spd_cv)

    # Action recommendation
    bc_sens_level = [l for l in labels if "BC_SENSITIVITY" in l][0].split(":")[1]
    amp_level     = [l for l in labels if "AMPLIFICATION" in l][0].split(":")[1] if wn_at_prior else "UNKNOWN"
    jump_active   = any("JUMP_REGIME" in l and "OUT_OF_SCOPE" in l for l in labels)

    if jump_active:
        action = ("JUMP_REGIME active: WindNinja output invalid here. "
                  "Use WRF/WRF-SFIRE. Treat WN value as floor, not ceiling.")
    elif bc_sens_level == "HIGH":
        action = ("BC direction correction has highest leverage. "
                  "Prioritise direction accuracy over speed correction.")
    elif amp_level == "STRONG":
        action = ("Strong terrain amplification. Verify BC validity (inversion check). "
                  "High value site for observational validation.")
    elif amp_level == "SHELTERED":
        action = ("Sheltered location. WindNinja likely over-predicts "
                  "(sub-resolution terrain shelter). Ground-truth before trusting.")
    else:
        action = ("Moderate confidence. Review OOD and BC_INVALID flags above.")

    return {
        "confidence":    score,
        "labels":        labels,
        "reasons":       reasons,
        "wn_at_prior":   wn_at_prior,
        "dir_range_mph": dir_range,
        "dir_cv":        dir_cv,
        "spd_cv":        spd_cv,
        "action":        action,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def run_self_test(ensemble: dict, sensitivity: dict) -> bool:
    """Verify key invariants hold. Returns True if all pass."""
    print("  SELF-TEST")
    print("  " + "-" * 60)
    passed = 0; failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}  {detail}")

    # 1. Jarbo Gap should be BC_SENSITIVITY:HIGH (range 3.58 mph > 2.0 threshold)
    rec = compute_station_confidence(
        "jarbo_gap", "camp_fire", 25.2, 50.0, ensemble, sensitivity)
    jarbo_sens = [l for l in rec["labels"] if "BC_SENSITIVITY" in l][0]
    check("Jarbo BC_SENSITIVITY == HIGH",
          jarbo_sens == "BC_SENSITIVITY:HIGH",
          f"got {jarbo_sens}, dir_range={rec['dir_range_mph']:.2f}")

    # 2. Paradise should be BC_SENSITIVITY:LOW (range 0.21 mph < 0.5 threshold)
    rec_par = compute_station_confidence(
        "paradise", "camp_fire", 25.2, 50.0, ensemble, sensitivity)
    par_sens = [l for l in rec_par["labels"] if "BC_SENSITIVITY" in l][0]
    check("Paradise BC_SENSITIVITY == LOW",
          par_sens == "BC_SENSITIVITY:LOW",
          f"got {par_sens}, dir_range={rec_par['dir_range_mph']:.2f}")

    # 3. Jarbo confidence < Paradise confidence (more uncertainty at canyon)
    check("Jarbo confidence < Paradise confidence",
          rec["confidence"] < rec_par["confidence"],
          f"jarbo={rec['confidence']:.3f}, paradise={rec_par['confidence']:.3f}")

    # 4. Camp Fire BC_INVALID:FALSE (sub-terrain 700 hPa is safe)
    bc_inv = [l for l in rec["labels"] if "BC_INVALID" in l][0]
    check("Camp Fire BC_INVALID == FALSE",
          bc_inv == "BC_INVALID:FALSE",
          f"got {bc_inv}")

    # 5. HRRR prior BC is in-distribution (OOD:FALSE)
    ood = [l for l in rec["labels"] if "OOD" in l][0]
    check("HRRR prior BC is OOD:FALSE",
          ood == "OOD:FALSE",
          f"got {ood}")

    # 6. Out-of-range BC triggers OOD:TRUE
    rec_ood = compute_station_confidence(
        "jarbo_gap", "camp_fire", 60.0, 180.0, ensemble, sensitivity)
    ood_far = [l for l in rec_ood["labels"] if "OOD" in l][0]
    check("Far-OOD BC triggers OOD:TRUE",
          ood_far == "OOD:TRUE",
          f"got {ood_far}")

    # 7. Stirling City triggers JUMP_REGIME
    jump_check = check_jump_regime("stirling_city")
    check("stirling_city triggers JUMP_REGIME",
          jump_check is not None and "OUT_OF_SCOPE" in jump_check[0])

    # 8. Amplification at Jarbo prior is MODERATE or STRONG (ratio ~1.15x)
    amp = [l for l in rec["labels"] if "AMPLIFICATION" in l][0]
    check("Jarbo AMPLIFICATION is MODERATE or STRONG",
          any(x in amp for x in ["MODERATE", "STRONG"]),
          f"got {amp}, wn_at_prior={rec['wn_at_prior']}")

    print(f"  {'='*60}")
    print(f"  {passed} passed / {failed} failed")
    return failed == 0


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CONFIDENCE FIELD  --  Camp Fire domain")
    print("  Per-station labels: BC_SENSITIVITY, AMPLIFICATION, JUMP_REGIME,")
    print("  OOD, BC_INVALID")
    print("=" * 72)
    print()

    ensemble, sensitivity = load_inputs(
        "ensemble_campfire.json", "sensitivity_results.json")

    # Run self-test first
    all_passed = run_self_test(ensemble, sensitivity)
    print()

    if not all_passed:
        print("  Self-test FAILED -- do not proceed to results")
        sys.exit(1)

    # Compute confidence field at HRRR prior BC for all stations
    DOMAIN_ID = "camp_fire"
    bc_speed  = ensemble["hrrr_prior"]["speed"]
    bc_dir    = ensemble["hrrr_prior"]["dir"]

    station_ids = list(ensemble["station_stats"].keys())

    print("=" * 72)
    print(f"  CONFIDENCE FIELD at HRRR prior BC: {bc_speed} mph @ {bc_dir}°")
    print(f"  Domain: {DOMAIN_ID}")
    print("=" * 72)

    field_results = {}

    for stid in station_ids:
        rec = compute_station_confidence(
            stid, DOMAIN_ID, bc_speed, bc_dir, ensemble, sensitivity)
        field_results[stid] = rec

        print(f"\n  {stid}")
        print(f"    Confidence score: {rec['confidence']:.3f}  "
              f"(dir_cv={rec['dir_cv']:.3f}, spd_cv={rec['spd_cv']:.3f})")
        print(f"    WN at prior:      {rec['wn_at_prior']:.1f} mph" if rec['wn_at_prior'] else "")
        print(f"    Labels:           {', '.join(rec['labels'])}")
        for lbl_key, reason in rec["reasons"].items():
            print(f"      {lbl_key}: {reason}")
        print(f"    Action: {rec['action']}")

    # Summary ranking by confidence
    print()
    print("=" * 72)
    print("  CONFIDENCE RANKING  (highest to lowest)")
    print("=" * 72)
    ranked = sorted(field_results.items(), key=lambda x: -x[1]["confidence"])
    print(f"\n  {'Station':^20} | {'Score':>6} | {'BC_SENS':^12} | {'AMP':^18} | {'WN mph':>7}")
    print(f"  {'-'*20}-+-{'-'*6}-+-{'-'*12}-+-{'-'*18}-+-{'-'*7}")
    for stid, rec in ranked:
        sens  = [l for l in rec["labels"] if "BC_SENSITIVITY" in l][0].split(":")[1]
        amp   = [l for l in rec["labels"] if "AMPLIFICATION"  in l][0].split(":")[1] if rec["wn_at_prior"] else "---"
        wn    = f"{rec['wn_at_prior']:.1f}" if rec["wn_at_prior"] else "---"
        print(f"  {stid:^20} | {rec['confidence']:6.3f} | {sens:^12} | {amp:^18} | {wn:>7}")

    print()
    print("  KEY INSIGHT:")
    print("  Higher confidence score = tighter ensemble at this station = more trustworthy.")
    print("  Lower score  = wider ensemble = BC error propagates strongly here.")
    print("  BC_SENSITIVITY:HIGH is WHERE a direction correction gives the most value.")
    print()
    print("  EMPIRICAL NOTE: direction is terrain-geometry-sensitive (17.2x Jarbo vs")
    print("  open terrain). Speed scales ~linearly at all stations (terrain-insensitive).")
    print("  These labels reflect WHERE direction uncertainty matters most, not a claim")
    print("  that direction universally dominates speed.")

    # Save
    out = {
        "domain":    DOMAIN_ID,
        "bc_input":  {"speed": bc_speed, "dir": bc_dir},
        "thresholds": THRESHOLDS,
        "stations":  field_results,
        "ranking":   [s for s, _ in ranked],
    }
    with open("confidence_field_results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("  Results saved to confidence_field_results.json")
