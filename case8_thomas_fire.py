#!/usr/bin/env python3
"""
case8_thomas_fire.py
====================
Case 8 -- Thomas Fire, December 4 2017
Mechanism classification + event setup.

Run: python case8_thomas_fire.py  (stdlib + mechanism_classifier only)
For HRRR data pull: conda run -n hrrr311 python hrrr_700hpa_case8.py

Event summary
-------------
Ignition: ~09:45z Dec 4 2017 (~01:45 PST) near Thomas Aquinas College,
Santa Clara River valley, ~34.44N 118.98W (Ventura County).

A classic NE Santa Ana event: strong high pressure over the Great Basin,
low pressure offshore, steep NE-to-SW pressure gradient over the Transverse
Ranges. Dry, warm (adiabatically heated) air descends from the Mojave
plateau into coastal Ventura/Santa Barbara counties. The fire burned for
weeks -- this hindcast targets the first 12 hours when the gradient was
strongest and the fire behavior most explosive.

Upwind terrain (the BC crest):
  Topa Topa Bluffs: ~34.52N 119.08W, ~1900m (6230 ft)
  This is the range the NE flow crosses before descending to the fire.
  NOT San Gorgonio (34.1N 116.8W, 3506m) -- that is well to the east,
  off-axis, and NOT upwind of the Ventura fire domain.

Key RAWS / ASOS near fire:
  KOXR  Oxnard/Ventura ASOS   34.200N -119.207W  sea level
  KTOA  Camarillo ASOS        34.214N -119.094W  75 ft
  WPNC1 Wheeler Springs RAWS  34.522N -119.318W  2050 ft  (upslope NW)
  SWRC1 Santa Ynez Pk RAWS    34.537N -119.981W  4298 ft  (ridge)
  RVMC1 Reyes Pk RAWS         34.685N -119.585W  5330 ft  (high ridge)
  OJAI  (est.) Ojai Valley    34.446N -119.244W  750 ft
  Fire origin area            34.441N -118.984W  1000 ft (est.)
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from mechanism_classifier import (
    EventDiagnostics, classify, print_result, to_hindcast_block)

# ---------------------------------------------------------------------------
# MECHANISM CLASSIFICATION
# ---------------------------------------------------------------------------
# Diagnostics from synoptic analysis and HRRR (pre-event 2017-12-04):
# - Great Basin high / offshore low: strong NE gradient, pgf well above threshold
# - 700 hPa over the Transverse Ranges: ~30-40 kt NE (Bakersfield sounding typical)
# - Cold/dry air aloft, surface warms adiabatically on descent -> unstable lapse rate
# - No convection, no frontal signature, forcing sustained for 24+ hours
# - Cross-ridge flow: yes, NE flow directly across Topa Topa / Santa Ynez crest

diag = EventDiagnostics(
    event_id="thomas_fire_20171204",
    w700_speed_ms=20.0,          # ~40 kt NE at 700 hPa over domain (strong Santa Ana)
    pgf_norm=1.6,                # strong NE pressure-gradient force
    cross_ridge_flow=True,       # NE flow directly across Topa Topa / Santa Ynez
    forcing_sustained=True,      # Santa Ana sustained 12+ hours at ignition
    low_level_lapse_ckm=4.0,     # stable upstream (Mojave), adiabatic heating on descent
    critical_level=False,        # no wind reversal aloft in classic Santa Ana
    max_reflectivity_dbz=0.0,    # no precipitation, no convection
    max_cape=0.0,
    lightning_present=False,
    wind_shift_deg=5.0,          # steady direction, no significant shift
    shift_duration_min=600.0,    # no rapid transition
    temp_drop_c=0.0,             # no temp drop -- warming on descent
    pres_rise_hpa=0.0,           # no frontal pressure rise
)

result = classify(diag)

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  CASE 8 — THOMAS FIRE  December 4 2017")
    print("  Mechanism classification")
    print("=" * 70)
    print_result(diag, result)
    print()
    print("HindcastEvent block:")
    print(json.dumps(to_hindcast_block(result), indent=2))
    print()
    print("  Expected: SYNOPTIC_TERRAIN")
    print("  WindNinja applicability: HIGH")
    print("  Bust axis: speed (terrain amplification under-resolved by 3km HRRR)")
    print()
    print("  BC reference level:")
    print("    Upwind crest: Topa Topa Bluffs ~1900m")
    print("    700 hPa in warm Santa Ana column: ~3100-3200m")
    print("    Margin: ~1200m -> 700 hPa VALID for fire domain")
    print("    HGT guard: exclude any cells > ~2900m (none expected in Ventura domain)")
    print("    Ridgetop level proxy: 800 hPa (~2000m) for Topa Topa crest sampling")
    print()
    print("  Next: conda run -n hrrr311 python hrrr_700hpa_case8.py")
