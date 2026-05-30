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
# NOTE: Hawkeye and Santa Rosa coordinates are APPROXIMATE -- IDs not yet verified.
# All results below carry the §2.1 caveat: approximate coordinates = suspect ratio.
WINDNINJA_HRRR_PRIOR = {
    "ignition":   {"dir": 30, "spd": 20.2, "ratio": 0.84,
                   "note": "slightly sheltered from NNE flow"},
    "hawkeye":    {"dir": 31, "spd": 23.0, "ratio": 0.96,
                   "note": "near-ambient -- COORDINATE SUSPECT (approx only)"},
    "santa_rosa": {"dir": None, "spd": None, "ratio": None,
                   "note": "outside 16mi grid (18.1mi from center)"},
    "fountgrove": {"dir": 25, "spd": 21.4, "ratio": 0.89,
                   "note": "slightly sheltered"},
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
    print("WINDNINJA AUDIT -- HRRR prior BC (24 mph @ 26 NNE)")
    print("=" * 70)
    print("  ALL RESULTS CARRY §2.1 CAVEAT: Hawkeye/Santa Rosa coordinates")
    print("  are APPROXIMATE (IDs not yet verified from live registry).")
    print("  Near-ambient ratios (0.84-0.96x) may reflect coordinate error,")
    print("  not actual terrain behavior. Do not interpret until coords confirmed.")
    print()
    print(f"  {'Station':^22} | {'WN sust':>8} | {'Ratio':>6} | {'Obs gust':>9} | Notes")
    print(f"  {'-'*22}-+-{'-'*8}-+-{'-'*6}-+-{'-'*9}-+-{'-'*30}")
    for stid, wn in WINDNINJA_HRRR_PRIOR.items():
        if wn["spd"] is None:
            print(f"  {stid:^22} | {'---':>8} | {'---':>6} | {'---':>9} | {wn['note']}")
            continue
        og = OBSERVED_GUSTS.get(stid)
        og_s = f"{og:.0f} mph" if og else "TBD"
        print(f"  {stid:^22} | {wn['spd']:>6.1f}mph | {wn['ratio']:>6.2f}x | "
              f"{og_s:>9} | {wn['note']}")
    print()
    print("  Hawkeye observed gust 79 mph >> WN prediction 23.0 mph (near-ambient).")
    print("  Implied sustained ~49 mph (at gust factor ~1.625) far exceeds WN output.")
    print("  This gap has two candidate explanations (protocol §1):")
    print("    1. COORDINATE ERROR: approx coords (38.80N, 122.90W) miss the")
    print("       actual Hawkeye ridge. WN extracts a sheltered cell.")
    print("    2. DIRECTION ERROR: true Diablo at Mayacamas may be ~NE 40-45deg,")
    print("       not NNE 26deg. Wrong approach angle changes terrain interaction.")
    print("  Both must be resolved before any ratio is trusted. Pending: verified")
    print("  Hawkeye station coordinates from Synoptic/WRCC registry.")


def print_findings():
    print()
    print("KEY FINDINGS AND OPEN QUESTIONS")
    print("=" * 70)
    print()
    print("  CONFIRMED:")
    print("    1. SYNOPTIC_TERRAIN mechanism, score 0.90, margin 0.70")
    print("    2. Terrain guard: clean (1889m margin; Mayacamas <1324m)")
    print("    3. HRRR 700 hPa: 23.6 mph @ 26 NNE at ignition")
    print("       Similar speed to Camp Fire (25.2 mph) -- different direction")
    print("    4. Declining wind regime -- timing-bust axis same as Camp Fire")
    print()
    print("  OPEN (data-blocked):")
    print("    A. Verified Hawkeye + Santa Rosa coordinates (Synoptic research tier)")
    print("    B. Observed sustained winds (RAWS time series for gust-factor resolution)")
    print("    C. BC sweep (direction especially -- 26 NNE may be wrong approach angle)")
    print("    D. Colby/Saddleback Camp Fire sweep (Phase A; same data gate)")
    print()
    print("  CROSS-CASE NOTE:")
    print("    Tubbs HRRR 700: 23.6 mph @ 26 NNE")
    print("    Camp Fire HRRR 700: 25.2 mph @ 50 NE")
    print("    Both ~24-25 mph at 700 hPa for fires producing 60-80 mph gusts.")
    print("    If Tubbs BC also resolves to ~28 mph after sweep, that strengthens")
    print("    the (small) speed-bias signal. If direction shifts substantially,")
    print("    direction becomes the more informative BC component for Diablo events.")


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
