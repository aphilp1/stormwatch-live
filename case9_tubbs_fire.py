#!/usr/bin/env python3
"""
case9_tubbs_fire.py
===================
Case 9 -- Tubbs Fire, October 8-9 2017
Mechanism classification + event setup.

Run: python case9_tubbs_fire.py

Event summary
-------------
Ignition: ~04:45z Oct 9 2017 (~21:45 PDT Oct 8) near Calistoga, CA
          ~38.57N 122.58W (start near Tubbs Lane / Calistoga area)

Classic NE Diablo wind event: building high pressure over the Great Basin
+ coastal trough → strong NE downslope flow over the Mayacamas Mountains.
Fire ran SW and then W toward Fountaingrove/Coffey Park in Santa Rosa.
Mechanism same as Camp Fire (SYNOPTIC_TERRAIN) but different terrain system:
Mayacamas range vs Feather River Canyon. Tests generalization.

Validation stations (Mass & Ovens 2019 BAMS):
  Hawkeye RAWS    ~45km NW of Santa Rosa  Max gust 79 mph (69 kt) -- record NE
  Santa Rosa RAWS  Santa Rosa area         Peak gust 68 mph (59 kt) -- 2nd record NE
  Atlas Peak RAWS  REJECTED (tree shelter) -- same failure mode as wrong coords

BC reference level: 700 hPa (Mayacamas range peaks ~1300m; 700 hPa ~3100m in
warm Oct airmass = ~1800m margin -- SAFE, terrain guard should show 0 flagged)
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from mechanism_classifier import (
    EventDiagnostics, classify, print_result, to_hindcast_block)

# ---------------------------------------------------------------------------
# MECHANISM CLASSIFICATION
# ---------------------------------------------------------------------------
# Diagnostics from synoptic analysis (Mass & Ovens 2019 + pre-event synoptic):
# - Classic offshore Diablo pattern: building SLP over Intermountain West + coastal trough
# - 700 hPa NE flow well above threshold over Mayacamas range
# - Dry, warm (offshore), stable layer near crest typical of Diablo events
# - No convection, no frontal signature
# - Forcing sustained through the night and into morning Oct 9
# - Cross-ridge: NE flow directly crosses the Mayacamas range crest

diag = EventDiagnostics(
    event_id="tubbs_fire_20171008",
    w700_speed_ms=18.0,           # strong NE flow at 700 hPa (typical Diablo)
    pgf_norm=1.4,                 # strong Great Basin high / coastal trough gradient
    cross_ridge_flow=True,        # NE flow crosses Mayacamas crest
    forcing_sustained=True,       # sustained through the night
    low_level_lapse_ckm=4.5,      # stable low-level layer typical of offshore Diablo
    critical_level=False,         # no strong wind reversal aloft in clean Diablo
    max_reflectivity_dbz=0.0,     # no precipitation, no convection
    max_cape=0.0,
    lightning_present=False,
    wind_shift_deg=8.0,           # steady NE, no significant directional shift
    shift_duration_min=600.0,     # not a transient -- regime maintained
    temp_drop_c=0.0,              # no temp drop (offshore warming on descent)
    pres_rise_hpa=0.0,
)

result = classify(diag)

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  CASE 9 — TUBBS FIRE  October 8-9 2017")
    print("  Mechanism classification")
    print("=" * 70)
    print_result(diag, result)
    print()
    print("HindcastEvent block:")
    print(json.dumps(to_hindcast_block(result), indent=2))
    print()
    print("  Expected: SYNOPTIC_TERRAIN")
    print("  Bust axis: speed (same as Camp Fire, different terrain)")
    print()
    print("  Key contrast with Camp Fire:")
    print("    Camp Fire: Feather River Canyon gap flow, narrow channeling")
    print("    Tubbs Fire: Mayacamas range crest, broader downslope")
    print("    Both SYNOPTIC_TERRAIN -- tests generalization of the BC method")
    print()
    print("  Validation targets (Mass & Ovens 2019 BAMS):")
    print("    Hawkeye RAWS:    max gust 79 mph (69 kt) -- record NE")
    print("    Santa Rosa RAWS: peak gust 68 mph (59 kt) -- 2nd record NE")
    print("    Atlas Peak:      REJECTED (tree shelter) -- protocol §2.3")
    print()
    print("  Station IDs: need lookup from MesoWest/Synoptic")
    print("  Next: conda run -n hrrr311 python hrrr_700hpa_case9.py")
