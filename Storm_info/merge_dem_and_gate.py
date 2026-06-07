#!/usr/bin/env python3
"""
merge_dem_and_gate.py  —  Phase A completion

Reads  (never modified):
  hrrr_error_dataset.csv   — source departure database
  dem_features.csv         — terrain metrics from build_dem_features.py

Writes:
  hrrr_error_dataset_dem.csv  — merged dataset (new file)
  merge_gate_report.txt        — gate check results

DEM terrain class thresholds (western-US fire-weather RAWS, priority order):
  exposed_ridge : relief_1km >= 200 AND slope >= 4  — ridge tops + prominent summits
  canyon_gap    : relief_1km >= 150 AND slope <  4  — canyon floors + gap stations
  valley        : relief_1km <  80                  — genuinely low-relief terrain
  open          : everything else

Threshold rationale:
  slope = 4° (not 7°) because summit stations like CBXC1 (Colby Mtn, 6004 ft) have
  gentle tops (slope=5.96°) but are unambiguously exposed ridges by relief (223.6m).
  A 7° cutoff would misclassify them as canyon_gap. JBGC1 (Jarbo Gap, slope=1.22°,
  relief=385.8m) correctly stays canyon_gap under either cutoff.
  relief_1km 150/200 separation: most canyon-gap and ridge stations have relief > 200m;
  the 150 floor for canyon_gap catches moderate-relief constrictions without pulling in
  genuine foothill stations (relief 80-150, terrain=open).

Gate checks (BOTH must pass before Phase B):
  1. Structured-vs-white ratio (PROVISIONAL)
     variance(per-class mean speed_err) / pooled within-class variance.
     A ratio >> 1 is a candidate signal. It is NOT a green light on its own.
  2. Rule #0 separability (THE green light)
     OLS: speed_err ~ repr_error_flag. Run structured-vs-white on the residuals.
     repr_error_flag (elevation std within the HRRR 3-km grid cell) rises with the
     same terrain ruggedness that defines the terrain classes, so a high ratio-before
     could be a representativeness artifact. Only if the ratio SURVIVES the repr control
     does the pattern qualify as a forecast-error finding.

Run on full 164-station set. If labor_day_or2020 DEM is still missing (35 stations),
the script will flag this and refuse to issue a final gate verdict.
"""

import csv
import math
import os
import sys
import datetime
from collections import defaultdict

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE        = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
SOURCE_CSV  = os.path.join(BASE, "hrrr_error_dataset.csv")
DEM_CSV     = os.path.join(BASE, "dem_features.csv")
OUT_CSV     = os.path.join(BASE, "hrrr_error_dataset_dem.csv")
REPORT_FILE = os.path.join(BASE, "merge_gate_report.txt")

# DEM terrain class thresholds — see module docstring before changing
RIDGE_RELIEF  = 200.0  # m  — minimum relief_1km for exposed_ridge
RIDGE_SLOPE   = 4.0    # °  — minimum slope for exposed_ridge (vs canyon_gap)
CANYON_RELIEF = 150.0  # m  — minimum relief_1km for canyon_gap
VALLEY_RELIEF = 80.0   # m  — maximum relief_1km for valley


# ── Terrain classification ───────────────────────────────────────────────────

def classify_terrain_dem(slope, relief_1km):
    """
    Derive terrain_class from DEM slope and relief_1km.
    Returns class string or None if either input is missing.
    Priority: exposed_ridge → canyon_gap → valley → open
    """
    if slope is None or relief_1km is None:
        return None
    try:
        s = float(slope)
        r = float(relief_1km)
    except (TypeError, ValueError):
        return None

    if r >= RIDGE_RELIEF and s >= RIDGE_SLOPE:
        return "exposed_ridge"
    if r >= CANYON_RELIEF and s < RIDGE_SLOPE:
        return "canyon_gap"
    if r < VALLEY_RELIEF:
        return "valley"
    return "open"


# ── Statistics helpers ───────────────────────────────────────────────────────

def structured_vs_white(values_by_class):
    """
    Structured-vs-white ratio: variance(class means) / pooled within-class variance.
    Returns (ratio, class_stats, between_var, pooled_within) or None if < 2 classes
    with n >= 3 each.
    class_stats: dict of {cls: {"n", "mean", "std"}}
    """
    classes = {k: v for k, v in values_by_class.items() if len(v) >= 3}
    if len(classes) < 2:
        return None

    class_stats = {}
    means = []
    weighted_ss = []
    dof_within = 0

    for cls, vals in sorted(classes.items()):
        arr = np.array(vals, dtype=float)
        n = len(arr)
        m = float(np.mean(arr))
        s = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        class_stats[cls] = {"n": n, "mean": m, "std": s}
        means.append(m)
        weighted_ss.append((n - 1) * s ** 2)
        dof_within += n - 1

    between_var = float(np.var(means, ddof=1)) if len(means) > 1 else 0.0
    pooled_within = sum(weighted_ss) / dof_within if dof_within > 0 else 0.0
    ratio = between_var / pooled_within if pooled_within > 0 else float("inf")

    return ratio, class_stats, between_var, pooled_within


def ols_residuals(X, y):
    """
    OLS y = a + b*X.  Returns (residuals, slope_b, intercept_a, r2).
    """
    Xm = np.column_stack([np.ones(len(X)), X])
    beta, _, _, _ = np.linalg.lstsq(Xm, y, rcond=None)
    y_pred = Xm @ beta
    resid = y - y_pred
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return resid, float(beta[1]), float(beta[0]), r2


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # ── Load DEM features ─────────────────────────────────────────────────────
    dem_lookup = {}
    with open(DEM_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dem_lookup[(row["stid"], row["event_id"])] = row

    # ── Load source and determine column order ────────────────────────────────
    with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        source_fieldnames = list(reader.fieldnames)
        source_rows = list(reader)

    # New columns to append (not already in source)
    new_cols = ["dem_elev_m", "elev_residual_m", "elev_qc_dem"]
    out_fieldnames = source_fieldnames + [c for c in new_cols if c not in source_fieldnames]

    # ── Merge ─────────────────────────────────────────────────────────────────
    merged_rows = []
    dem_verified_keys = set()
    dem_flagged_keys = set()
    dem_missing_keys = set()
    class_changes = []

    for row in source_rows:
        row = dict(row)
        for c in new_cols:
            if c not in row:
                row[c] = "NEEDS_DEM"

        key = (row["stid"], row["event_id"])
        dem = dem_lookup.get(key)
        elev_qc = dem.get("elev_qc", "") if dem else ""

        if dem is None or elev_qc == "DEM_FETCH_FAIL":
            dem_missing_keys.add(key)
            merged_rows.append(row)
            continue

        # Fill continuous DEM columns
        row["dem_elev_m"]      = dem.get("dem_elev_m", "")
        row["elev_residual_m"] = dem.get("elev_residual_m", "")
        row["elev_qc_dem"]     = elev_qc

        for col in ("slope", "aspect", "relief_1km", "repr_error_flag"):
            v = dem.get(col)
            if v not in (None, "", "None"):
                row[col] = v

        # Derive terrain class from DEM
        new_class = classify_terrain_dem(row.get("slope"), row.get("relief_1km"))
        old_class = row.get("terrain_class", "open")

        if new_class is not None:
            if new_class != old_class:
                class_changes.append((key, old_class, new_class))
            row["terrain_class"] = new_class
            if elev_qc == "FLAG_LARGE_RESIDUAL":
                row["terrain_class_source"] = "dem_flag"
                row["dem_verified"] = "flag"
                dem_flagged_keys.add(key)
            else:
                row["terrain_class_source"] = "dem_verified"
                row["dem_verified"] = "yes"
                dem_verified_keys.add(key)
        else:
            dem_missing_keys.add(key)

        merged_rows.append(row)

    # ── Write merged CSV ──────────────────────────────────────────────────────
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged_rows)

    # ── Gate analysis: active rows only ──────────────────────────────────────
    active = [r for r in merged_rows if r.get("qc_flag") in ("KEEP", "CAUTION")]
    active_keys = {(r["stid"], r["event_id"]) for r in active}

    dem_active_keys = (dem_verified_keys | dem_flagged_keys) & active_keys
    labday_active   = [r for r in active if r.get("event_id") == "labor_day_or2020"]
    labday_dem_keys = dem_active_keys & {(r["stid"], r["event_id"]) for r in labday_active}
    labday_missing  = len(labday_active) - len(labday_dem_keys)
    full_coverage   = (labday_missing == 0)

    # Collect gate rows: active + DEM terrain class + numeric speed_err
    gate_rows = []
    for r in active:
        key = (r["stid"], r["event_id"])
        if key not in dem_active_keys:
            continue
        try:
            speed_err = float(r["speed_err"])
        except (ValueError, TypeError):
            continue
        gate_rows.append({
            "stid":            r["stid"],
            "event_id":        r["event_id"],
            "speed_err":       speed_err,
            "terrain_class":   r["terrain_class"],
            "repr_error_flag": r.get("repr_error_flag", "NEEDS_DEM"),
        })

    # ── Gate 1: Structured-vs-white ───────────────────────────────────────────
    by_class = defaultdict(list)
    for r in gate_rows:
        by_class[r["terrain_class"]].append(r["speed_err"])
    svw = structured_vs_white(dict(by_class))

    # ── Gate 2: Rule #0 — terrain signal after controlling repr_error_flag ────
    r0_rows = []
    for r in gate_rows:
        try:
            repr_v = float(r["repr_error_flag"])
            r0_rows.append((r["speed_err"], repr_v, r["terrain_class"]))
        except (ValueError, TypeError):
            pass

    rule0 = None
    if len(r0_rows) >= 10:
        y_arr = np.array([x[0] for x in r0_rows])
        X_arr = np.array([x[1] for x in r0_rows])
        resids, b_slope, b_int, r2 = ols_residuals(X_arr, y_arr)

        by_class_resid = defaultdict(list)
        for i, (_, _, tc) in enumerate(r0_rows):
            by_class_resid[tc].append(float(resids[i]))

        rule0 = {
            "n":       len(r0_rows),
            "b_slope": b_slope,
            "b_int":   b_int,
            "r2":      r2,
            "svw":     structured_vs_white(dict(by_class_resid)),
        }

    # ── Build report ──────────────────────────────────────────────────────────
    lines = []
    W = "=" * 70

    lines += [
        W,
        "MERGE + GATE REPORT  —  Phase A completion",
        f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        W,
    ]

    # --- Merge summary --------------------------------------------------------
    lines += ["", "── MERGE SUMMARY " + "─" * 53]
    lines.append(f"  Source rows (all):       {len(source_rows)}")
    lines.append(f"  Active (KEEP+CAUTION):   {len(active)}")
    lines.append(f"  Active with real DEM:    {len(dem_active_keys)}  (terrain_class_source = dem_*)")
    lines.append(f"    of which dem_verified: {len(dem_verified_keys & active_keys)}")
    lines.append(f"    of which dem_flag:     {len(dem_flagged_keys & active_keys)}"
                 "  (elev residual > 50 m — treat with caution)")
    lines.append(f"  Active missing DEM:      {len(active) - len(dem_active_keys)}"
                 "  (labor_day_or2020 + any NODATA)")
    if labday_missing > 0:
        lines.append(f"  labor_day_or2020 gap:    {labday_missing} stations")
        lines.append("  *** Run refetch_labor_day_dem.py before running gate on full 164. ***")
    else:
        lines.append("  labor_day_or2020:        DEM complete (0 missing)")

    lines.append(f"\n  Terrain class distribution (active DEM rows, n={len(dem_active_keys)}):")
    tc_counts = defaultdict(int)
    for r in active:
        if (r["stid"], r["event_id"]) in dem_active_keys:
            tc_counts[r["terrain_class"]] += 1
    for tc in sorted(tc_counts):
        lines.append(f"    {tc:<20} n={tc_counts[tc]}")

    if class_changes:
        summary = defaultdict(int)
        for _, old, new in class_changes:
            summary[f"{old} → {new}"] += 1
        lines.append(f"\n  Heuristic→DEM class changes ({len(class_changes)} total):")
        for k in sorted(summary):
            lines.append(f"    {k}: {summary[k]}")

    lines.append(f"\n  Rows with thresholds: exposed_ridge ≥{RIDGE_RELIEF}m relief + ≥{RIDGE_SLOPE}°,"
                 f" canyon_gap ≥{CANYON_RELIEF}m + <{RIDGE_SLOPE}°, valley <{VALLEY_RELIEF}m, else open")

    # --- Gate 1 ---------------------------------------------------------------
    lines += [
        "",
        "─" * 70,
        "GATE 1: STRUCTURED-VS-WHITE  (PROVISIONAL — does not clear Phase B alone)",
        f"  Dataset: {len(gate_rows)} active rows with DEM terrain class",
    ]
    if not full_coverage:
        lines.append(f"  WARNING: {len(active) - len(dem_active_keys)} active rows lack DEM.")
        lines.append("           Ratio below is on a non-random subset (labor_day_or2020 missing).")
        lines.append("           Do NOT treat this as a valid gate verdict.")

    if svw is None:
        lines.append("  INSUFFICIENT DATA for structured-vs-white check.")
    else:
        ratio, cs, bv, pw = svw
        lines.append(f"\n  speed_err (hrrr_10m_mph − obs_sus_mph)  n={len(gate_rows)}")
        for cls in sorted(cs):
            s = cs[cls]
            lines.append(f"    {cls:<20} n={s['n']:4d}  mean={s['mean']:+7.2f}  std={s['std']:6.2f}")
        lines.append(f"  Between-class variance: {bv:.4f}")
        lines.append(f"  Pooled within-class:    {pw:.4f}")
        lines.append(f"  RATIO:                  {ratio:.4f}  {'> 1 — candidate signal' if ratio > 1 else '≤ 1 — white'}")
        lines.append("  Status: PROVISIONAL — see rule #0 below.")

    # --- Gate 2 ---------------------------------------------------------------
    lines += [
        "",
        "─" * 70,
        "GATE 2: RULE #0 SEPARABILITY  (THE green light)",
        "  Q: Does terrain class explain speed_err AFTER controlling for repr_error_flag?",
        "  Method: OLS(speed_err ~ repr_error_flag) → residuals → structured-vs-white",
        "  Why: repr_error_flag (elevation std in HRRR 3-km cell) is collinear with terrain",
        "       ruggedness by construction. A high ratio-before that collapses here was",
        "       measuring HRRR-grid representativeness, not forecast error.",
    ]

    if rule0 is None:
        lines.append("  INSUFFICIENT DATA for rule #0 (need repr_error_flag values).")
    else:
        lines.append(
            f"\n  Step 1 — OLS  n={rule0['n']}: "
            f"speed_err = {rule0['b_int']:+.2f} + {rule0['b_slope']:+.4f} × repr_error_flag   "
            f"R²={rule0['r2']:.3f}"
        )
        if rule0["r2"] > 0.05:
            lines.append("    repr_error_flag explains meaningful speed_err variance → collinearity risk is real.")
        else:
            lines.append("    repr_error_flag explains little speed_err variance → collinearity risk is low.")

        r0svw = rule0["svw"]
        lines.append(f"\n  Step 2 — Structured-vs-white on OLS residuals  n={rule0['n']}:")
        if r0svw is None:
            lines.append("    INSUFFICIENT DATA for residual check.")
        else:
            r0ratio, r0cs, r0bv, r0pw = r0svw
            for cls in sorted(r0cs):
                s = r0cs[cls]
                lines.append(f"    {cls:<20} n={s['n']:4d}  mean={s['mean']:+7.2f}  std={s['std']:6.2f}")
            lines.append(f"    Between-class variance: {r0bv:.4f}")
            lines.append(f"    Pooled within-class:    {r0pw:.4f}")
            lines.append(f"    RATIO:                  {r0ratio:.4f}")

            if svw is not None:
                ratio_before = svw[0]
                lines.append(f"\n  Ratio before repr control: {ratio_before:.4f}")
                lines.append(f"  Ratio after  repr control: {r0ratio:.4f}")
                if ratio_before > 0:
                    fraction_remaining = r0ratio / ratio_before
                else:
                    fraction_remaining = None

                if fraction_remaining is not None:
                    if fraction_remaining < 0.30:
                        rule0_verdict = "FAILS"
                        interpretation = (
                            "Terrain signal collapses after repr control (< 30% remains).\n"
                            "  → Pattern was a HRRR-grid representativeness artifact.\n"
                            "  → Do NOT proceed to Phase B terrain-class analysis."
                        )
                    elif fraction_remaining < 0.70:
                        rule0_verdict = "PARTIAL"
                        interpretation = (
                            "Terrain signal substantially weakens after repr control (30–70% remains).\n"
                            "  → Partial representativeness confound.\n"
                            "  → repr_error_flag should enter Phase B as a covariate, not a control."
                        )
                    else:
                        if r0ratio > 1.0:
                            rule0_verdict = "PASSES"
                            interpretation = (
                                "Terrain signal survives repr control (> 70% remains, ratio-after > 1).\n"
                                "  → Terrain class explains speed_err beyond representativeness.\n"
                                "  → Phase B terrain analysis is warranted."
                            )
                        else:
                            rule0_verdict = "INDETERMINATE"
                            interpretation = (
                                "Ratio survives control but remains ≤ 1 (no terrain signal to protect).\n"
                                "  → Regime-level analysis (synoptic_regime) shows more signal than terrain."
                            )
                    lines.append(f"  Rule #0: {rule0_verdict}")
                    for il in interpretation.split("\n"):
                        lines.append(f"  {il}")

    # --- Regime note ----------------------------------------------------------
    lines += [
        "",
        "─" * 70,
        "NOTE: Synoptic-regime signal (descriptive, not gated):",
        "  Regime structure was stronger than terrain structure in Phase A heuristic run.",
        "  santa_ana / frontal_passage show ~−5 mph mean HRRR underbias.",
        "  chinook / downslope_oregon near zero.",
        "  If terrain gate fails, regime-conditioned departure analysis is the natural next step.",
    ]

    # --- Verdict --------------------------------------------------------------
    lines += ["", "─" * 70, "VERDICT"]

    if not full_coverage:
        lines += [
            "  INCOMPLETE: labor_day_or2020 DEM missing ({} stations).".format(labday_missing),
            "  Re-run merge_dem_and_gate.py after refetch_labor_day_dem.py completes.",
            "  No valid gate verdict until all 164 active stations have DEM.",
        ]
    elif svw is None or rule0 is None or rule0["svw"] is None:
        lines.append("  INSUFFICIENT DATA for gate verdict.")
    else:
        ratio_before = svw[0]
        r0ratio      = rule0["svw"][0]
        if ratio_before <= 1.0:
            lines += [
                "  GATE 1 FAILS: No terrain structure in speed departures (ratio ≤ 1).",
                "  → Terrain class does not predict HRRR bust magnitude.",
                "  Regime-level analysis is the recommended next path.",
            ]
        elif rule0["r2"] > 0.05 and r0ratio <= 1.0:
            lines += [
                "  GATE 1 passes, RULE #0 FAILS.",
                "  → Terrain-class structure collapses after repr_error_flag control.",
                "  → The pattern is a representativeness artifact, not a forecast-error finding.",
                "  Regime-level analysis is the recommended next path.",
            ]
        elif r0ratio <= 1.0:
            lines += [
                "  GATE 1 passes, RULE #0: no terrain signal surviving repr control.",
                "  → Consider regime-conditioned terrain analysis (within each regime).",
            ]
        else:
            lines += [
                "  GATE 1 PASSES. RULE #0 PASSES.",
                "  → Terrain class explains speed_err independently of representativeness.",
                "  → Phase B terrain analysis is warranted. Proceed with repr_error_flag",
                "     as a covariate rather than a control in any regression model.",
            ]

    lines += ["", "END OF REPORT"]
    report = "\n".join(lines)

    print(report)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nMerged CSV   → {OUT_CSV}")
    print(f"Report       → {REPORT_FILE}")


if __name__ == "__main__":
    main()
