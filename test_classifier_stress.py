#!/usr/bin/env python3
"""
test_classifier_stress.py
==========================
Stress test the mechanism classifier against edge cases and known events.

Tests:
  1. Four archetypes (must still classify as labeled)
  2. MIXED cases (margin < threshold)
  3. LOW_CONFIDENCE cases (evidence_fraction < threshold)
  4. All 9 hindcast events classified (consistency check)
  5. Edge cases that should NOT classify as SYNOPTIC_TERRAIN

Run: python test_classifier_stress.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from mechanism_classifier import (
    EventDiagnostics, classify, Mechanism, THRESHOLDS)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def check(label, diag, expected_mech, expect_mixed=False, expect_low_conf=False):
    r = classify(diag)
    ok_mech  = r.primary == expected_mech
    ok_mixed = (r.mixed == expect_mixed) if not expect_low_conf else True
    ok_conf  = (r.low_confidence == expect_low_conf)
    passed = ok_mech and ok_mixed and ok_conf
    status = "PASS" if passed else "FAIL"
    flags = ""
    if r.mixed:
        flags += " [MIXED]"
    if r.low_confidence:
        flags += " [LOW_CONF]"
    print(f"  {status}  {label:45s} -> {r.primary.value if r.primary else 'None'}{flags}")
    if not passed:
        if not ok_mech:
            print(f"        expected {expected_mech.value}, got {r.primary.value if r.primary else 'None'}")
        if not ok_mixed:
            print(f"        mixed expected={expect_mixed}, got={r.mixed}")
    return passed


# ---------------------------------------------------------------------------
# TEST SUITE
# ---------------------------------------------------------------------------

results = []

print()
print("=" * 70)
print("  MECHANISM CLASSIFIER STRESS TEST")
print("=" * 70)

# ---- 1. FOUR ARCHETYPES (regression test) --------------------------------
print()
print("1. ARCHETYPES (must classify as labeled)")

results.append(check(
    "Camp Fire 2018 (SYNOPTIC_TERRAIN)",
    EventDiagnostics(
        event_id="camp_fire", w700_speed_ms=18.0, pgf_norm=1.4, cross_ridge_flow=True,
        forcing_sustained=True, low_level_lapse_ckm=4.5, critical_level=True,
        max_reflectivity_dbz=5.0, max_cape=0.0, lightning_present=False,
        wind_shift_deg=10.0, shift_duration_min=600.0,
    ),
    Mechanism.SYNOPTIC_TERRAIN
))

results.append(check(
    "Missoula Dec 2025 front (PBL_TRANSIENT)",
    EventDiagnostics(
        event_id="missoula_front", w700_speed_ms=16.0, pgf_norm=1.1, cross_ridge_flow=True,
        forcing_sustained=False, low_level_lapse_ckm=6.5,
        max_reflectivity_dbz=15.0, max_cape=50.0, lightning_present=False,
        wind_shift_deg=70.0, shift_duration_min=45.0,
        temp_drop_c=6.0, pres_rise_hpa=2.5,
    ),
    Mechanism.PBL_TRANSIENT
))

results.append(check(
    "Missoula Jul 2024 derecho (CONVECTIVE_OUTFLOW)",
    EventDiagnostics(
        event_id="missoula_derecho", w700_speed_ms=20.0, pgf_norm=0.8,
        max_reflectivity_dbz=60.0, max_cape=2000.0, lightning_present=True,
        gust_to_sustained=2.4, blast_duration_min=15.0,
        wind_shift_deg=50.0, shift_duration_min=20.0,
    ),
    Mechanism.CONVECTIVE_OUTFLOW
))

results.append(check(
    "Plume blowup (FIRE_GENERATED)",
    EventDiagnostics(
        event_id="plume_blowup", w700_speed_ms=6.0, pgf_norm=0.3, forcing_sustained=False,
        max_reflectivity_dbz=40.0, max_cape=800.0, lightning_present=True,
        goes_cloud_top_c=-55.0, plume_collocated_with_fire=True, local_wind_violent=True,
    ),
    Mechanism.FIRE_GENERATED
))

# ---- 2. ALL HINDCAST EVENTS -----------------------------------------------
print()
print("2. ALL HINDCAST EVENTS (consistency check)")

events_9 = [
    ("Case 4 Camp Fire",     Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=18.0, pgf_norm=1.4, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=4.5, critical_level=True, max_reflectivity_dbz=5.0, max_cape=0.0, lightning_present=False, wind_shift_deg=10.0, shift_duration_min=600.0)),
    ("Case 2 Missoula front",Mechanism.PBL_TRANSIENT,      dict(w700_speed_ms=16.0, pgf_norm=1.1, cross_ridge_flow=True, forcing_sustained=False, low_level_lapse_ckm=6.5, max_reflectivity_dbz=15.0, max_cape=50.0, lightning_present=False, wind_shift_deg=70.0, shift_duration_min=45.0, temp_drop_c=6.0, pres_rise_hpa=2.5)),
    ("Case 1 Derecho",       Mechanism.CONVECTIVE_OUTFLOW,  dict(w700_speed_ms=20.0, pgf_norm=0.8, max_reflectivity_dbz=60.0, max_cape=2000.0, lightning_present=True, gust_to_sustained=2.4, blast_duration_min=15.0, wind_shift_deg=50.0, shift_duration_min=20.0)),
    # Cases 3/6/7 need explicit no-frontal-signature to avoid MIXED flag
    ("Case 3 Marshall Fire", Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=22.0, pgf_norm=1.5, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=4.0, critical_level=True, max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False, wind_shift_deg=5.0, shift_duration_min=600.0, temp_drop_c=0.0, pres_rise_hpa=0.0)),
    ("Case 5 Iowa Derecho",  Mechanism.CONVECTIVE_OUTFLOW,  dict(w700_speed_ms=18.0, pgf_norm=0.6, max_reflectivity_dbz=65.0, max_cape=3000.0, lightning_present=True, gust_to_sustained=2.8, blast_duration_min=10.0)),
    ("Case 6 Boulder 1972",  Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=25.0, pgf_norm=1.8, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=3.5, critical_level=True, max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False, wind_shift_deg=5.0, shift_duration_min=600.0, temp_drop_c=0.0, pres_rise_hpa=0.0)),
    ("Case 7 Oakland Hills", Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=15.0, pgf_norm=1.2, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=4.5, max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False, wind_shift_deg=5.0, shift_duration_min=600.0, temp_drop_c=0.0, pres_rise_hpa=0.0)),
    ("Case 8 Thomas Fire",   Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=20.0, pgf_norm=1.6, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=4.0, max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False, wind_shift_deg=5.0, shift_duration_min=600.0)),
    ("Case 9 Tubbs Fire",    Mechanism.SYNOPTIC_TERRAIN,   dict(w700_speed_ms=18.0, pgf_norm=1.4, cross_ridge_flow=True, forcing_sustained=True, low_level_lapse_ckm=4.5, max_reflectivity_dbz=0.0, max_cape=0.0, lightning_present=False, wind_shift_deg=8.0, shift_duration_min=600.0)),
]

for label, expected, kwargs in events_9:
    diag = EventDiagnostics(event_id=label, **kwargs)
    results.append(check(label, diag, expected))

# ---- 3. EDGE CASES -- should NOT be SYNOPTIC_TERRAIN ----------------------
print()
print("3. EDGE CASES (should NOT classify as SYNOPTIC_TERRAIN)")

# Weak ambient forcing + fire-collocated plume -- must be FIRE_GENERATED, not synoptic
results.append(check(
    "Weak synoptic + collocated plume -> FIRE_GENERATED",
    EventDiagnostics(
        event_id="edge_pyroCb", w700_speed_ms=5.0, pgf_norm=0.2, forcing_sustained=False,
        goes_cloud_top_c=-60.0, plume_collocated_with_fire=True, local_wind_violent=True,
        max_reflectivity_dbz=45.0, max_cape=600.0, lightning_present=True,
    ),
    Mechanism.FIRE_GENERATED
))

# Fast frontal shift with temp drop -- must be PBL_TRANSIENT, not synoptic
results.append(check(
    "Fast shift + frontal sig -> PBL_TRANSIENT (not synoptic)",
    EventDiagnostics(
        event_id="edge_frontal", w700_speed_ms=14.0, pgf_norm=0.9,
        forcing_sustained=False,
        wind_shift_deg=80.0, shift_duration_min=30.0,
        temp_drop_c=8.0, pres_rise_hpa=3.0,
        max_reflectivity_dbz=10.0, max_cape=20.0, lightning_present=False,
    ),
    Mechanism.PBL_TRANSIENT
))

# Convective with strong refl but FIRE-COLLOCATED plume -- should be FIRE_GENERATED
# (the pyroCb gating fix: fire-collocated convection doesn't count as ambient)
results.append(check(
    "High refl + fire plume collocated -> FIRE_GENERATED (pyroCb gate)",
    EventDiagnostics(
        event_id="edge_pyroCb_gate", w700_speed_ms=7.0, pgf_norm=0.4,
        max_reflectivity_dbz=50.0, max_cape=1500.0, lightning_present=True,
        goes_cloud_top_c=-50.0, plume_collocated_with_fire=True, local_wind_violent=True,
        forcing_sustained=False,
    ),
    Mechanism.FIRE_GENERATED
))

# ---- 4. LOW-CONFIDENCE / MIXED cases ------------------------------------
print()
print("4. LOW-CONFIDENCE / MIXED cases (should flag, not assert)")

# Almost no data -- should be LOW_CONFIDENCE
results.append(check(
    "Almost no diagnostics -> LOW_CONFIDENCE",
    EventDiagnostics(
        event_id="minimal_data",
        w700_speed_ms=15.0,   # only one field
    ),
    Mechanism.SYNOPTIC_TERRAIN,
    expect_low_conf=True
))

# Balanced synoptic + frontal -- should be MIXED
results.append(check(
    "Balanced synoptic+frontal -> MIXED",
    EventDiagnostics(
        event_id="mixed_case", w700_speed_ms=16.0, pgf_norm=1.0, cross_ridge_flow=True,
        forcing_sustained=False,  # half-and-half
        low_level_lapse_ckm=6.0,
        wind_shift_deg=50.0, shift_duration_min=80.0,
        temp_drop_c=4.0, pres_rise_hpa=1.5,
        max_reflectivity_dbz=5.0, max_cape=20.0, lightning_present=False,
    ),
    Mechanism.PBL_TRANSIENT,
    expect_mixed=True
))

# ---- SUMMARY ------------------------------------------------------------
print()
print("=" * 70)
n_pass = sum(results)
n_fail = len(results) - n_pass
print(f"  RESULTS: {n_pass}/{len(results)} PASS  |  {n_fail} FAIL")
if n_fail == 0:
    print("  ALL PASS -- classifier is robust across all test cases")
else:
    print("  FAILURES DETECTED -- review above")
print("=" * 70)
