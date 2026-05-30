#!/usr/bin/env python3
"""
case9_reconstruction.py
=======================
Case 9 -- Tubbs Fire, October 8-9 2017
Stormwatch Hindcast Reconstruction (framework v2)

Run: python case9_reconstruction.py

Files for this case:
  case9_tubbs_fire.py       -- mechanism classification
  hrrr_700hpa_case9.py      -- HRRR 700 hPa pull with terrain guard
  windninja_case9.py        -- WindNinja 16mi grid run (26deg/24 mph)
  case9_reconstruction.py   -- this file

Status: PARTIAL -- data-blocked on verified station coordinates.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from mechanism_classifier import (
    EventDiagnostics, classify, print_result, to_hindcast_block)

# ---------------------------------------------------------------------------
# KNOWN DATA
# ---------------------------------------------------------------------------

# Terrain guard (hrrr_700hpa_case9.py)
TERRAIN_GUARD = {
    "domain_cells": 1289, "cells_flagged": 0, "min_margin_m": 1889,
    "verdict": "CLEAN -- 700 hPa safely above all terrain (1889m min margin)",
}

# HRRR 700 hPa (fxx=4, ~04:45z ignition, 00z Oct 9 run)
HRRR_700_IGNITION = {"speed_mph": 23.6, "dir_deg": 26.0,
                      "note": "NNE -- may differ from true Diablo direction of ~NE 40-45deg"}

# HRRR wind regime: DECLINING through the event
# fxx=2 (02z): 27.5 mph -> fxx=4 (04z): 23.6 mph -> fxx=10 (10z): 15.0 mph
# Fire ignited at declining wind -- same timing-bust axis as documented in Mass 2021

# WindNinja results at HRRR prior BC (24 mph @ 26 NNE)
# STATUS: WITHHELD -- coordinates are approximate, IDs not yet verified.
# Per protocol §1 prime directive: a number believed to be a coordinate
# artifact is NOT a finding and does not travel in the results list.
# Near-ambient ratios (0.84-0.96x) are consistent with WN extracting from
# a sheltered cell due to wrong coordinates -- OPPOSITE sign from Jarbo's
# 39.977 error (which pointed at MORE exposed terrain), same cause.
# Reporting "Case 9 shows weak amplification" would seed a false pattern.
# WITHHOLD until verified coordinates from live registry.
WINDNINJA_WITHHELD = {
    "ignition":   {"dir": 30, "spd": 20.2, "ratio": 0.84},
    "hawkeye":    {"dir": 31, "spd": 23.0, "ratio": 0.96},
    "santa_rosa": {"dir": None, "spd": None, "ratio": None},
    "fountgrove": {"dir": 25, "spd": 21.4, "ratio": 0.89},
}

# Validation targets (Mass & Ovens 2019 BAMS) -- GUSTS
OBSERVED_GUSTS = {
    "hawkeye":    79.0,  # max gust, 8-9 Oct -- record NE gusts back to 1993
    "santa_rosa": 68.0,  # peak gust, 2nd-strongest NE on record
}

# Camp Fire reference for cross-case comparison
CAMP_FIRE_REF = {
    "hrrr_700_speed": 25.2, "hrrr_700_dir": 50,
    "optimal_bc_speed": 28.0, "delta_speed": +3.0,
    "jarbo_ratio_corrected": 1.12,
}

# Mechanism classification
diag = EventDiagnostics(
    event_id="tubbs_fire_20171008",
    w700_speed_ms=18.0, pgf_norm=1.4, cross_ridge_flow=True,
    forcing_sustained=True, low_level_lapse_ckm=4.5, critical_level=False,
    max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False,
    wind_shift_deg=8.0, shift_duration_min=600.0,
    temp_drop_c=0.0, pres_rise_hpa=0.0,
)
result = classify(diag)


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def print_bc_audit():
    print()
    print("BC AUDIT")
    print("=" * 70)
    h = HRRR_700_IGNITION
    print(f"  HRRR 700 hPa domain mean at ignition (fxx=4, ~04:45z):")
    print(f"    {h['speed_mph']:.1f} mph @ {h['dir_deg']:.0f} deg NNE")
    print(f"    NOTE: {h['note']}")
    print()
    print(f"  Camp Fire reference: HRRR 700 was {CAMP_FIRE_REF['hrrr_700_speed']:.1f} mph "
          f"@ {CAMP_FIRE_REF['hrrr_700_dir']} NE; optimal BC ~{CAMP_FIRE_REF['optimal_bc_speed']:.0f} mph")
    print(f"  Tubbs vs Camp: similar HRRR speed (~24 vs 25 mph); direction more northerly")
    print()
    print("  DECLINING WIND REGIME:")
    print("    02z: 27.5 mph -> 04z (ignition): 23.6 mph -> 10z: 15.0 mph")
    print("    Fire ignited at declining wind. Mass 2021 documented WRF delayed")
    print("    the wind decline on Camp Fire -- same timing-bust axis applies here.")


def print_wn_audit():
    print()
    print("WINDNINJA -- WITHHELD (§1 prime directive)")
    print("=" * 70)
    print("  WN ratios (0.84-0.96x) are WITHHELD pending verified coordinates.")
    print("  Believed to be coordinate artifacts; reporting them as results risks")
    print("  seeding a false 'Case 9 shows weak amplification' pattern.")
    print()
    print("  Two unresolved explanations for the near-ambient result:")
    print("    1. COORDINATE ERROR: approx Hawkeye (38.80N, 122.90W) likely misses")
    print("       the actual ridge. WN extracts a sheltered cell (opposite-sign error")
    print("       to Jarbo 39.977 which pointed at MORE exposed terrain -- same cause).")
    print("    2. DIRECTION ERROR: true Diablo approach may be ~NE 40-45deg, not NNE 26.")
    print("       Wrong approach angle changes terrain interaction entirely.")
    print()
    print("  When verified coords + obs arrive:")
    print("    Falsifiable direction test: vary direction, hold speed, watch ridge ratios.")
    print("    If ratios move significantly between 26deg and 45deg BC: direction matters.")
    print("    If ratios don't move: neither direction nor speed is the story; answer is")
    print("    pure terrain geometry independent of approach angle.")


def print_findings():
    print()
    print("FINDINGS AND FRAMING (protocol §1)")
    print("=" * 70)
    print()
    print("  CONFIRMED (survived artifact checks):")
    print("    1. SYNOPTIC_TERRAIN, score 0.90, margin 0.70")
    print("    2. Terrain guard: clean, 1889m margin")
    print("    3. HRRR 700 hPa at ignition: 23.6 mph @ 26 NNE")
    print()
    print("  TIMING OBSERVATION (new, not selected-for, mechanistically specific):")
    print("    Wind was declining at ignition: 27.5 -> 23.6 -> 15.0 mph over 8 hours.")
    print("    Fire ignited and ran on the DECLINING LIMB of the wind curve.")
    print("    Camp Fire (Mass 2021): same declining-limb pattern documented.")
    print("    THIS is the cross-case pattern worth elevating -- it predicts that")
    print("    catastrophic runs lag peak wind, which changes when warnings should fire.")
    print("    See timing_observations.md for the dedicated thread.")
    print()
    print("  WHAT '23-28 MPH AT 700 HPA ACROSS CASES' DOES AND DOES NOT MEAN:")
    print("    Does NOT mean: these fires happened because of 23-28 mph aloft wind.")
    print("    These events were SELECTED for being catastrophic Diablo fires.")
    print("    Strong downslope fires naturally have strong-downslope winds. Circular.")
    print("    The contrast class is missing: were there 23-28 mph NE 700 hPa days")
    print("    over the same terrain that did NOT produce catastrophic fire? If so,")
    print("    700 hPa speed alone doesn't discriminate -- terrain response does.")
    print("    That contrast is buildable from HRRR archive (non-fire sample days).")
    print()
    print("    DOES support: 'HRRR aloft is consistent; terrain response is what varies'")
    print("    -- the real thesis. Synoptic winds well-forecast (both BAMS papers).")
    print("    All the action is in the terrain transfer function HRRR can't resolve.")
    print("    This also reinforces speed-bias = consistent-with-zero: if 700 hPa is")
    print("    consistently ~25 mph and a good BC, there's no speed bias to learn.")
    print("    Value lives in direction, terrain geometry, and timing.")
    print()
    print("  OPEN (data-blocked):")
    print("    A. Verified Hawkeye + Santa Rosa coordinates + observed sustained winds")
    print("    B. Direction-vary test (hold speed, sweep direction around 26-45 NNE/NE)")
    print("    C. Camp Fire Phase A sweep (Colby/Saddleback; same data gate)")


if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  CASE 9 — TUBBS FIRE  October 8-9 2017")
    print("  Stormwatch Hindcast Reconstruction (framework v2)")
    print("=" * 70)
    print_result(diag, result)
    print()
    print("HindcastEvent block:")
    print(json.dumps(to_hindcast_block(result), indent=2))
    print_bc_audit()
    print_wn_audit()
    print_findings()
    print()
    print("=" * 70)
    print("  STATUS: PARTIAL (data-blocked on verified station coords + obs)")
    print("  GitHub: committed with open items documented")
    print("=" * 70)
