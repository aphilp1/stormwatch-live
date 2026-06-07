#!/usr/bin/env python3
"""
flow_coupling_draft.py  --  Draft station-level exposure tag for Phase B

Produces flow_coupling in {coupled, sheltered, intermediate} for each
active station-event row. DRAFT ONLY -- writes to derived frame, does
not modify hrrr_error_dataset.csv.

Rule (three-tier, with cold-pool extension):

TIER 1 -- terrain_class:
  valley                        -> SHELTERED (terrain_valley)
  portable RAWS (TR164/TS379/TT321) -> SHELTERED (portable_raws)

TIER 2 -- relief_1km + slope + terrain_class:
  exposed_ridge, relief >= 150m -> candidate COUPLED
  exposed_ridge, relief <  150m -> INTERMEDIATE (low-relief ridge)
  canyon_gap, relief >= 300m    -> COUPLED (high-relief canyon funnels flow)
  canyon_gap, relief <  300m    -> INTERMEDIATE
  open, relief < 50m AND slope < 3  -> SHELTERED (flat open, no terrain enhancement)
  open, relief >= 200m AND slope >= 8 -> candidate COUPLED
  open, otherwise               -> INTERMEDIATE

TIER 3 -- aspect vs flow direction (bc_dir):
  angle_diff = circular_dist(aspect, bc_dir)
  Upslope face (angle_diff <= 90):  confirm COUPLED; keep INTERMEDIATE
  Lee face     (angle_diff > 90):   COUPLED -> INTERMEDIATE; INTERMEDIATE -> INTERMEDIATE
  (if bc_dir or aspect missing: skip aspect check, preserve tier-2 label)

COLD-POOL EXTENSION (continental_downslope + chinook_frontrange + frontal_passage):
  Station below event median elevation AND terrain_class in (valley, open) with low slope
  -> SHELTERED (cold_pool_decoupled) -- flagged separately so user can review

Borderline cases flagged explicitly in output.

FINALIZED DECISIONS (2026-06-07):
  - WMSC1 (thomas/woolsey): INTERMEDIATE despite relief=506/507m.
    Rule: exposed_ridge + adiff=151°/134° (lee) → tier-3 demote.
    Rationale: lee-facing geometry is correct; those −35.6/−27.0 errors likely
    reflect lee-wave/rotor physics, NOT windward terrain enhancement. Promoting
    to coupled would contaminate the enhancement signal with a rotor outlier.
    WMSC1 flagged for Phase B: WN recovers both events when BC is right-sized
    (woolsey full recovery, thomas partial). Not a rotor — terrain physics work here.
    Outstanding question: why is bc/obs > 1 in thomas but < 1 in woolsey?
  - CEKC2 (marshall): INTERMEDIATE at adiff=88°. Held at 90° threshold.
    Error value (-12.9) does NOT drive assignment — geometry does.
  - PSTM8 (missoula_dec2025): COUPLED (canyon_gap rule correct), se=+9.7.
    Known limitation: high relief overestimates coupling in canyon_gap when
    canyon orientation blocks flow. Noted, not fixed — would require canyon
    orientation geometry, a future refinement.

USAGE CONSTRAINT: Apply within-regime only.
  Offshore/Diablo → coupled stations underbias (mean −6.89 mph, 75% neg)
  Chinook/frontrange → coupled stations overbias (BTAC2 +19.1, SOPC2 +16.7)
  Pooling regimes cancels the signal. Never run pooled.
  "geometry sets coupling, error never does"
"""

import csv, sys, numpy as np
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"

PORTABLES = {"TR164", "TS379", "TT321"}
CONTINENTAL_REGIMES = ("chinook", "downslope", "frontal", "continental")

def circ_diff(a, b):
    """Circular angular distance between two bearings, 0-180."""
    d = abs(a - b) % 360
    return min(d, 360 - d)

# ── Load departure database ───────────────────────────────────────────────────
dep = {}
with open(f"{BASE}/hrrr_error_dataset.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["qc_flag"] not in ("KEEP", "CAUTION"):
            continue
        key = (r["stid"], r["event_id"])
        try:
            bc_dir = float(r["bc_dir"]) if r.get("bc_dir") else None
        except:
            bc_dir = None
        dep[key] = {
            "regime":    r.get("synoptic_regime", ""),
            "bc_dir":    bc_dir,
            "qc_flag":   r["qc_flag"],
            "speed_err": float(r["speed_err"]) if r.get("speed_err") else None,
            "obs_dir":   (float(r["obs_dir_deg"]) if r.get("obs_dir_deg") and r["obs_dir_deg"] not in ("", "MISSING") else None),
            "dem_elev":  (float(r["elev_m"]) if r.get("elev_m") and r["elev_m"] not in ("", "MISSING") else None),
        }

# ── Load DEM features ─────────────────────────────────────────────────────────
dem = {}
with open(f"{BASE}/dem_features.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        key = (r["stid"], r["event_id"])
        try:
            slope   = float(r["slope"])
            relief  = float(r["relief_1km"])
            aspect  = float(r["aspect"]) if r.get("aspect") else None
        except:
            slope = relief = 0.0; aspect = None
        dem[key] = {
            "slope":    slope,
            "relief":   relief,
            "aspect":   aspect,
            "tc":       r["terrain_class"],
            "elev_qc":  r["elev_qc"],
            "dem_elev": float(r["dem_elev_m"]) if r.get("dem_elev_m") else None,
        }

# ── Compute event median elevation (for cold-pool check) ─────────────────────
event_elev = defaultdict(list)
for (stid, eid), d in dep.items():
    if d["dem_elev"]:
        event_elev[eid].append(d["dem_elev"])
event_med_elev = {eid: np.median(v) for eid, v in event_elev.items()}

# ── Assign flow_coupling ──────────────────────────────────────────────────────
def assign(stid, eid, d_dep, d_dem):
    tc      = d_dem["tc"]
    slope   = d_dem["slope"]
    relief  = d_dem["relief"]
    aspect  = d_dem["aspect"]
    bc_dir  = d_dep["bc_dir"]
    regime  = d_dep["regime"]
    elev    = d_dem["dem_elev"] or d_dep["dem_elev"]
    med_elev = event_med_elev.get(eid, None)

    # Portables
    if stid in PORTABLES:
        return "sheltered", "portable_raws", False

    # Tier 1 -- valley always sheltered
    if tc == "valley":
        return "sheltered", "terrain_valley", False

    # Compute aspect-vs-flow
    if aspect is not None and bc_dir is not None:
        adiff = circ_diff(aspect, bc_dir)
        facing = adiff <= 90   # True = upslope/into-flow face
    else:
        adiff = None
        facing = None   # unknown

    # Tier 2 -- terrain_class + relief + slope
    if tc == "exposed_ridge":
        if relief >= 150:
            tier2 = "coupled"
        else:
            tier2 = "intermediate"
    elif tc == "canyon_gap":
        tier2 = "coupled" if relief >= 300 else "intermediate"
    elif tc == "open":
        if relief < 50 and slope < 3:
            tier2 = "sheltered"
        elif relief >= 200 and slope >= 8:
            tier2 = "coupled"
        else:
            tier2 = "intermediate"
    else:
        tier2 = "intermediate"

    # Tier 3 -- aspect vs flow
    if facing is False:   # lee face
        if tier2 == "coupled":
            tier2 = "intermediate"
        reason_suffix = "_lee"
    elif facing is True:
        reason_suffix = "_upslope"
    else:
        reason_suffix = "_aspect_unknown"

    reason = f"{tc}_r{relief:.0f}s{slope:.0f}{reason_suffix}"

    # Cold-pool extension -- continental events, station below median elevation
    if tier2 in ("intermediate", "sheltered"):
        is_continental = any(t in regime for t in CONTINENTAL_REGIMES)
        if is_continental and elev is not None and med_elev is not None:
            if elev < (med_elev - 200):   # > 200m below event median
                return "sheltered", reason + "_cold_pool", True

    # Borderline flag: within 20m of relief thresholds, or within 1deg of slope thresholds
    borderline = (
        (tc == "exposed_ridge" and 130 <= relief <= 170) or
        (tc == "canyon_gap"    and 260 <= relief <= 340) or
        (tc == "open" and 40 <= relief <= 60 and slope < 4) or
        (tc == "open" and 180 <= relief <= 220 and 6 <= slope <= 10) or
        (adiff is not None and 80 <= adiff <= 100)
    )

    return tier2, reason, borderline

# ── Run and collect ───────────────────────────────────────────────────────────
results = []
for (stid, eid), d_dep in sorted(dep.items()):
    if (stid, eid) not in dem:
        coupling, reason, borderline = "intermediate", "no_dem_data", False
    else:
        d_dem = dem[(stid, eid)]
        coupling, reason, borderline = assign(stid, eid, d_dep, d_dem)

    results.append({
        "stid": stid, "event_id": eid,
        "regime":    d_dep["regime"],
        "tc":        dem.get((stid, eid), {}).get("tc", "?"),
        "relief":    dem.get((stid, eid), {}).get("relief", None),
        "slope":     dem.get((stid, eid), {}).get("slope", None),
        "aspect":    dem.get((stid, eid), {}).get("aspect", None),
        "bc_dir":    d_dep["bc_dir"],
        "adiff":     (circ_diff(dem[(stid, eid)]["aspect"], d_dep["bc_dir"])
                      if (stid,eid) in dem and dem[(stid,eid)]["aspect"] and d_dep["bc_dir"]
                      else None),
        "flow_coupling": coupling,
        "reason":    reason,
        "borderline": borderline,
        "speed_err": d_dep["speed_err"],
        "qc_flag":   d_dep["qc_flag"],
    })

# ── Print full table ──────────────────────────────────────────────────────────
from collections import Counter
print("=" * 100)
print("FLOW COUPLING DRAFT ASSIGNMENTS")
print("=" * 100)
print()
print(f"{'stid':<8} {'event_id':<25} {'tc':<14} {'rel':>5} {'slp':>4} {'adiff':>6} "
      f"{'coupling':<14} {'flag':<5} {'se':>7}  reason")
print("-" * 100)

for r in sorted(results, key=lambda x: (x["flow_coupling"], x["event_id"], x["stid"])):
    bl = "BORD" if r["borderline"] else ""
    adiff_s = f"{r['adiff']:.0f}" if r["adiff"] is not None else "?"
    rel_s   = f"{r['relief']:.0f}" if r["relief"] is not None else "?"
    slp_s   = f"{r['slope']:.1f}" if r["slope"] is not None else "?"
    se_s    = f"{r['speed_err']:+.1f}" if r["speed_err"] is not None else "?"
    print(f"  {r['stid']:<8} {r['event_id']:<25} {r['tc']:<14} {rel_s:>5} {slp_s:>4} "
          f"{adiff_s:>6} {r['flow_coupling']:<14} {bl:<5} {se_s:>7}  {r['reason']}")

# ── Summary counts ────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("SUMMARY")
print()
counts = Counter(r["flow_coupling"] for r in results)
print(f"  coupled:      {counts['coupled']:>3}")
print(f"  intermediate: {counts['intermediate']:>3}")
print(f"  sheltered:    {counts['sheltered']:>3}")
print(f"  borderline:   {sum(1 for r in results if r['borderline']):>3}")
print()

# ── Speed_err by coupling ─────────────────────────────────────────────────────
print("Speed_err by flow_coupling (all regimes):")
for cat in ("coupled", "intermediate", "sheltered"):
    errs = [r["speed_err"] for r in results if r["flow_coupling"] == cat and r["speed_err"] is not None]
    if errs:
        print(f"  {cat:<14} N={len(errs):>3}  mean={np.mean(errs):>+6.2f}  "
              f"std={np.std(errs):>5.2f}  "
              f"neg%={100*sum(1 for e in errs if e<0)/len(errs):.0f}%")
print()

# ── Speed_err by coupling, OFFSHORE only ─────────────────────────────────────
OFFSHORE_TAGS = ("diablo", "santa_ana")
print("Speed_err by flow_coupling (OFFSHORE events only):")
for cat in ("coupled", "intermediate", "sheltered"):
    errs = [r["speed_err"] for r in results
            if r["flow_coupling"] == cat and r["speed_err"] is not None
            and any(t in r["regime"] for t in OFFSHORE_TAGS)]
    if errs:
        print(f"  {cat:<14} N={len(errs):>3}  mean={np.mean(errs):>+6.2f}  "
              f"std={np.std(errs):>5.2f}  "
              f"neg%={100*sum(1 for e in errs if e<0)/len(errs):.0f}%")
print()

# ── Borderline cases detail ───────────────────────────────────────────────────
borderlines = [r for r in results if r["borderline"]]
if borderlines:
    print(f"BORDERLINE CASES ({len(borderlines)}) -- threshold-sensitive assignments:")
    print(f"  {'stid':<8} {'event_id':<25} {'tc':<14} {'rel':>5} {'slp':>4} "
          f"{'adiff':>6} {'coupling':<14} {'se':>7}  reason")
    for r in borderlines:
        adiff_s = f"{r['adiff']:.0f}" if r["adiff"] is not None else "?"
        se_s    = f"{r['speed_err']:+.1f}" if r["speed_err"] is not None else "?"
        rel_s2  = f"{r['relief']:.0f}" if r["relief"] is not None else "?"
        slp_s2  = f"{r['slope']:.1f}"  if r["slope"]   is not None else "?"
        print(f"  {r['stid']:<8} {r['event_id']:<25} {r['tc']:<14} "
              f"{rel_s2:>5} {slp_s2:>4} {adiff_s:>6} "
              f"{r['flow_coupling']:<14} {se_s:>7}  {r['reason']}")

# ── Write derived CSV ─────────────────────────────────────────────────────────
OUT = f"{BASE}/flow_coupling_draft.csv"
fields = ["stid","event_id","regime","tc","relief","slope","aspect","bc_dir",
          "adiff","flow_coupling","reason","borderline","speed_err","qc_flag"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(results)
print(f"\nDraft written -> {OUT}")
