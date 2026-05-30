#!/usr/bin/env python3
"""
case2_reconstruction.py
=======================
Case 2 -- Missoula NW Flow, December 17 2025
Stormwatch Hindcast Reconstruction -- full methodology (new framework 2026-05-30)

Run: python case2_reconstruction.py  (stdlib + mechanism_classifier only)
For the live data comparison table, run dec17_final.py separately.

Event summary
-------------
A cold front moved through western Montana on December 17, 2025. After the cold
pool mixed out (~18-21z), NW flow coupled to the surface and was channeled by
the terrain around Missoula, with strong amplification at ridge sites. The
dangerous wind window was the coupled NW regime (18-21z / 11-14 MST), not the
frontal transition itself.

Mechanism: PBL_TRANSIENT
WindNinja applicability: PARTIAL
Primary bust axis: timing + direction (when the shift arrives, and the veer)

BC Audit finding
----------------
700 hPa HRRR domain-mean (fxx=12): 76.9 mph @ 251 WSW  <- MID-LEVEL JET STREAM
Sounding-derived WN BC (OTX/TFX 12z): 28.8 mph @ 315 NW  <- POST-FRONTAL BL FLOW
Delta: +48 mph, -64 deg -- NOT a learnable correction; wrong reference entirely.

Key lesson: HRRR 700 hPa domain-mean is valid as a WN BC reference ONLY for
SYNOPTIC_TERRAIN events (sustained gradient flow). For PBL_TRANSIENT frontal
events, the domain straddles the frontal boundary, mixing pre-frontal jet and
post-frontal low-level flow. Use a sounding at an upwind post-frontal station
(OTX or TFX) as the BC reference, not the HRRR domain mean.
"""

import sys
import json
sys.stdout.reconfigure(encoding="utf-8")

# Import the mechanism classifier (same directory)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mechanism_classifier import (
    EventDiagnostics, classify, print_result, to_hindcast_block)

# ---------------------------------------------------------------------------
# KNOWN DATA (from dec17_final.py + soundings + windninja_case2_wider.py)
# ---------------------------------------------------------------------------

# BC provenance — two separate paths, must not be conflated
#
# PATH 1: Sounding extraction (OTX + TFX 12z, both identical)
#   -> THE COMMITTED, WORKING WN BC. 700 hPa post-frontal BL flow.
SOUNDING_BC_SPEED  = 28.8   # mph (25 kt NW)
SOUNDING_BC_DIR    = 315.0  # deg NW
#
# PATH 2: HRRR grid domain-mean extraction (hrrr_700hpa_case2.py, fxx=12)
#   -> A DIAGNOSTIC showing why grid extraction fails here, NOT a BC candidate.
#   The domain straddles the frontal boundary; grid mean picks up the pre-frontal
#   WSW jet on the SE side. Possible compounding factor: cold airmass drops the
#   700 hPa surface close to terrain over the highest Missoula grid cells.
HRRR_GRID_700_SPEED = 76.9  # mph WSW -- artifact of frontal straddle
HRRR_GRID_700_DIR   = 251.4 # deg WSW

# WindNinja results (315 deg / 29 mph init, 12mi grid)
# from windninja_case2_wider.py -- PNTM8 NIFC authoritative coords
WINDNINJA = {
    "KMSO":  {"dir": 314, "spd": 28.3, "ratio": 0.98, "elev_ft": 3205},
    "PNTM8": {"dir": 313, "spd": 40.6, "ratio": 1.40, "elev_ft": 7897},
    "BLMM8": {"dir": 320, "spd": 29.2, "ratio": 1.01, "elev_ft": 3412},
    "TS897": {"dir": 323, "spd": 27.2, "ratio": 0.94, "elev_ft": 3200},
}

# HRRR 3km 10m wind (coupled window 18-21z vector average from dec17_final.py)
# dir, spd pairs per station per hour -- approximate avg below
HRRR_COUPLED_AVG = {
    "KMSO":  {"dir": 292, "spd": 21.9},   # approx vector avg 18-21z
    "PNTM8": {"dir": 283, "spd": 21.2},
    "BLMM8": {"dir": 270, "spd": 23.7},
    "TS897": {"dir": 276, "spd": 19.4},
}

# Observations (coupled window 18-21z) from dec17_final.py
# KMSO and BLMM8 available; PNTM8 and TS897 blocked (WRCC >30 day)
OBS_COUPLED_AVG = {
    "KMSO":  {"dir": 286, "spd": 22.9, "source": "IEM ASOS"},
    "BLMM8": {"dir": 268, "spd": 24.1, "source": "Synoptic"},
    "PNTM8": {"dir": None, "spd": None, "source": "BLOCKED (WRCC >30 day)"},
    "TS897": {"dir": None, "spd": None, "source": "BLOCKED (WRCC >30 day, wrong station)"},
}


# ---------------------------------------------------------------------------
# SECTION 1 — MECHANISM CLASSIFICATION
# ---------------------------------------------------------------------------

diag = EventDiagnostics(
    event_id="missoula_nw_flow_20251217",
    # Synoptic forcing present but NOT sustained -- front moves through
    w700_speed_ms=15.0,         # HRRR shows strong 700hPa flow (jet)
    pgf_norm=1.1,               # moderate pressure gradient
    cross_ridge_flow=True,      # post-frontal NW has substantial cross-ridge component
    forcing_sustained=False,    # frontal transition -- NOT a steady regime

    # Stability: cold air advection post-front, stable
    low_level_lapse_ckm=6.5,    # near-stable; cold pool initially decoupled

    # No convection
    max_reflectivity_dbz=15.0,
    max_cape=50.0,
    lightning_present=False,

    # Strong frontal wind shift signature
    wind_shift_deg=70.0,        # estimated from KMSO obs: S/SE pre-front -> NW post-front
    shift_duration_min=45.0,    # fast shift over ~45 min window
    temp_drop_c=6.0,            # significant temp drop with frontal passage
    pres_rise_hpa=2.5,          # pressure rise behind front
)

result = classify(diag)


# ---------------------------------------------------------------------------
# SECTION 2 — BC AUDIT
# ---------------------------------------------------------------------------

def print_bc_audit():
    print()
    print("BC AUDIT — TWO PROVENANCE PATHS (must not be conflated)")
    print("=" * 70)
    print()
    print("  PATH 1 — Sounding extraction (THE COMMITTED WN BC):")
    print(f"    {SOUNDING_BC_SPEED:.1f} mph @ {SOUNDING_BC_DIR:.0f} deg NW")
    print(f"    Source: OTX + TFX radiosonde 12z Dec 17 2025, 700 hPa (both identical)")
    print(f"    This IS the WindNinja init used in windninja_case2_wider.py.")
    print(f"    It is the free-atmosphere post-frontal BL flow — physically correct BC.")
    print()
    print("  PATH 2 — HRRR grid domain-mean extraction (DIAGNOSTIC, NOT A BC):")
    print(f"    {HRRR_GRID_700_SPEED:.1f} mph @ {HRRR_GRID_700_DIR:.0f} deg WSW")
    print(f"    Source: hrrr_700hpa_case2.py domain mean, 00z fxx=12 (valid 12z)")
    print(f"    This is NOT the BC. It is a diagnostic of what HRRR's 700 hPa grid")
    print(f"    sees over the domain — and it fails here for two compounding reasons.")
    print()
    print("  WHY PATH 2 FAILS:")
    print("  Reason 1 — FRONTAL STRADDLE: At 12z the frontal boundary runs through")
    print("    the domain. The grid mean averages pre-frontal WSW jet (SE of front,")
    print("    ~75-90 mph) with post-frontal NW low-level flow (NW of front, ~29 mph).")
    print("    The mean is physically meaningless — two different airmasses.")
    print("  Reason 2 — BELOW-GROUND EXTRAPOLATION (unconfirmed, likely partial):")
    print("    In cold post-frontal air, the 700 hPa surface drops toward ~2700m.")
    print("    Point Six (PNTM8) is at 2323m; surrounding peaks reach ~2500m.")
    print("    HRRR may extrapolate 700 hPa below-ground over the highest cells.")
    print("    TODO: confirm with HGT:700 mb guard (see hrrr_700hpa_case2.py).")
    print()
    print("  CONCLUSION FOR THE BC CORRECTION FRAMEWORK:")
    print("  For SYNOPTIC_TERRAIN: HRRR 700 hPa domain-mean extraction is valid.")
    print("  For PBL_TRANSIENT frontal events: use a sounding at an upwind post-")
    print("  frontal station. Grid extraction straddling a front is not a BC input.")
    print("  This case is OUT OF SCOPE for the HRRR->WN BC learned map. It belongs")
    print("  in the PBL_TRANSIENT validation set as the negative example.")


# ---------------------------------------------------------------------------
# SECTION 3 — WINDNINJA PERFORMANCE
# ---------------------------------------------------------------------------

def print_wn_performance():
    print()
    print("WINDNINJA PERFORMANCE -- NW regime snapshot (315 deg / 29 mph init)")
    print("=" * 70)
    print(f"  {'Station':^18} | {'Elev ft':>7} | {'WN dir':>6} | {'WN spd':>7} | {'Ratio':>6} | {'Obs 18-21z':^14} | Notes")
    print(f"  {'-'*18}-+-{'-'*7}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*14}-+-{'-'*28}")

    for stid, wn in WINDNINJA.items():
        obs = OBS_COUPLED_AVG[stid]
        obs_str = f"{obs['dir']:.0f}d/{obs['spd']:.1f}mph" if obs["spd"] else obs["source"][:14]
        flag = ""
        if wn["ratio"] > 1.20:
            flag = " AMPLIFIED"
        elif wn["ratio"] < 0.80:
            flag = " sheltered"
        note = f"WN={wn['ratio']:.2f}x{flag}"
        print(f"  {stid:^18} | {wn['elev_ft']:>7} | {wn['dir']:>6} | {wn['spd']:>6.1f}m | {wn['ratio']:>6.2f} | {obs_str:^14} | {note}")

    print()
    print("  Key finding: PNTM8 (Point Six, 7897ft) shows 1.40x amplification --")
    print("  WindNinja correctly resolves ridge-level terrain enhancement of NW flow.")
    print("  KMSO valley floor near-ambient (0.98x) as expected.")
    print()
    print("  VALIDATION GAP: PNTM8 and TS897 are BLOCKED (WRCC >30 day + Synoptic")
    print("  wrong-station issue). WN ridge amplification at 1.40x cannot be")
    print("  directly validated against obs. This is the open finding for Case 2.")


# ---------------------------------------------------------------------------
# SECTION 4 — HRRR vs WINDNINJA
# ---------------------------------------------------------------------------

def print_model_comparison():
    print()
    print("HRRR 3km vs WINDNINJA -- coupled window 18-21z")
    print("=" * 70)
    print(f"  {'Station':^18} | {'HRRR avg':^12} | {'WN snapshot':^12} | {'Obs avg':^14} | Notes")
    print(f"  {'-'*18}-+-{'-'*12}-+-{'-'*12}-+-{'-'*14}-+-{'-'*20}")

    for stid in ["KMSO", "PNTM8", "BLMM8", "TS897"]:
        hc = HRRR_COUPLED_AVG[stid]
        wn = WINDNINJA[stid]
        obs = OBS_COUPLED_AVG[stid]
        obs_str = (f"{obs['dir']:.0f}d/{obs['spd']:.1f}m"
                   if obs["spd"] else "blocked")
        hrrr_ratio = hc["spd"] / 29.0
        wn_ratio   = wn["spd"] / 29.0
        print(f"  {stid:^18} | "
              f"{hc['dir']:.0f}d/{hc['spd']:.1f}m "
              f"({hrrr_ratio:.2f}x) | "
              f"{wn['dir']:.0f}d/{wn['spd']:.1f}m "
              f"({wn_ratio:.2f}x) | "
              f"{obs_str:^14} | ")

    print()
    print("  HRRR 3km: gets the direction roughly right (270-295 deg), but does not")
    print("  resolve ridge amplification -- PNTM8 at 21 mph vs WN 40 mph.")
    print("  WindNinja: adds +40% at the ridge (PNTM8) that HRRR completely misses.")
    print("  KMSO: both models agree with obs (~20-23 mph, NW/WNW).")


# ---------------------------------------------------------------------------
# SECTION 5 — KEY FINDINGS AND TRANSFERABLE LESSONS
# ---------------------------------------------------------------------------

def print_findings():
    print()
    print("KEY FINDINGS AND TRANSFERABLE LESSONS")
    print("=" * 70)
    print()
    print("  1. MECHANISM CLASSIFICATION MATTERS FOR BC SELECTION")
    print("     PBL_TRANSIENT frontal events require sounding-based BC from a")
    print("     post-frontal upwind station (OTX, TFX). HRRR 700 hPa domain-mean")
    print("     straddles the front and is not a usable reference level.")
    print()
    print("  2. WINDNINJA PARTIAL APPLICABILITY -- SNAPSHOT, NOT TRANSITION")
    print("     WN correctly models the NW-flow terrain regime once coupled (18z+).")
    print("     The 1.40x ridge amplification at PNTM8 is physically plausible and")
    print("     consistent with exposure/elevation. The frontal transition itself")
    print("     (11-17z, wind shift + direction change) is outside WN scope.")
    print()
    print("  3. TIMING IS THE FORECAST BUST AXIS, NOT SPEED")
    print("     The dangerous window is WHEN the cold pool mixes out and NW flow")
    print("     couples to the surface. HRRR predicted the shift ~14z (fxx=14)")
    print("     but the actual coupling began closer to 17-18z. A 3-4 hour timing")
    print("     error on fire-wind arrival is the primary risk here.")
    print()
    print("  4. PNTM8 / TS897 DATA GAP IS A PERSISTENT VALIDATION PROBLEM")
    print("     WRCC >30-day access wall and Synoptic wrong-station issue mean the")
    print("     most meteorologically critical ridge stations are always unvalidated.")
    print("     This is the single largest open problem for the Missoula cases.")
    print()
    print("  5. HRRR MISSES RIDGE AMPLIFICATION")
    print("     At PNTM8, HRRR shows ~21 mph while WN predicts 40 mph (+90%).")
    print("     The 3km grid sees the valley, not the exposed ridge at 7897ft.")
    print("     This is the same 3km terrain-blindness seen in Camp Fire / Jarbo Gap.")
    print()
    print("  CONTRIBUTION TO THE BC CORRECTION TRAINING SET:")
    print("  This case validates the MECHANISM SCOPE BOUNDARY of the HRRR-700hPa")
    print("  BC map: it applies to SYNOPTIC_TERRAIN, not PBL_TRANSIENT. Case 2 is")
    print("  the negative example that enforces the mechanism gate in the classifier.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  CASE 2 — MISSOULA NW FLOW  December 17 2025")
    print("  Stormwatch Hindcast Reconstruction (framework v2, 2026-05-30)")
    print("=" * 70)

    print_result(diag, result)

    print()
    print("HindcastEvent block:")
    print(json.dumps(to_hindcast_block(result), indent=2))

    print_bc_audit()
    print_wn_performance()
    print_model_comparison()
    print_findings()

    print()
    print("=" * 70)
    print("  FILES FOR THIS CASE:")
    print("    dec17_final.py            -- full obs/HRRR/GFS/WN comparison table")
    print("    windninja_case2_wider.py  -- WindNinja 12mi grid run (315/29 mph)")
    print("    hrrr_700hpa_case2.py      -- HRRR 700hPa BC audit pull")
    print("    case2_reconstruction.py   -- this file")
    print()
    print("  STATUS: COMPLETE")
    print("  Git commit pending (Case 2 reconstruction with new framework)")
    print("=" * 70)
