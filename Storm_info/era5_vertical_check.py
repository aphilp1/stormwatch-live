#!/usr/bin/env python3
"""
era5_vertical_check.py  —  Vertical-structure mechanism analysis
Phase A follow-up: does HRRR fail to mix its own aloft momentum to the surface?

Three questions, ordered by weight they can bear:

Q1 (PRIMARY, N=12, no new data): HRRR internal mixing ratio
   HRRR_10m / bc_speed  grouped by regime.
   bc_speed is HRRR's own wind at the BC pressure level (already in dataset).
   If ratio is lower for offshore than continental, HRRR under-mixes in
   exactly the events where it undershoots obs.
   CONFOUND CHECK: bc_level (850 vs 700) must not be confounded with regime.

Q2 (SECONDARY, N=12, Open-Meteo 10m): ERA5 as independent truth
   ERA5_10m vs obs vs HRRR_10m.
   If ERA5_10m ≈ obs while HRRR undershoots → HRRR-specific failure.
   If ERA5_10m also undershoots → surface wind hard for all models in these events.

Q3 (CORROBORATION, n=4 offshore CDS events): HRRR_850 vs ERA5_850
   Uses existing CDS pressure-level files (camp, tubbs, thomas, kincade_ign).
   All 4 are offshore. No continental contrast. Report as spot-check only.

Run in dem conda env (has xarray, requests, numpy).
"""

import csv
import datetime
import os
import sys
import time
from collections import defaultdict

import numpy as np
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE      = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
ERA5_DIR  = r"C:\Users\aphil\Documents\Stormwatch\era5"
IN_CSV    = os.path.join(BASE, "hrrr_error_dataset_dem.csv")
REPORT    = os.path.join(BASE, "era5_vertical_report.txt")

OM_BASE   = "https://archive-api.open-meteo.com/v1/era5"
MS_TO_MPH = 2.23694

# CDS events with ERA5 pressure-level files
CDS_EVENTS = {
    "camp_2018":       "era5_pl_camp_2018.nc",
    "tubbs_2017":      "era5_pl_tubbs_2017.nc",
    "thomas_2017":     "era5_pl_thomas_2017.nc",
    "kincade_ign_2019": "era5_pl_kincade_2019.nc",
}


# ── load departure database ───────────────────────────────────────────────────

rows = []
with open(IN_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        try:
            speed_err = float(r["speed_err"])
        except (ValueError, TypeError):
            continue

        def _f(key):
            try:
                return float(r[key])
            except (ValueError, TypeError):
                return None

        bc_speed = _f("bc_speed")
        bc_dir   = _f("bc_dir")
        bc_level = r.get("bc_level", "").strip()
        hrrr_10m = _f("hrrr_10m_mph")
        obs_sus  = _f("obs_sus_mph")
        lat      = _f("lat")
        lon      = _f("lon")
        peak_dt  = r.get("peak_dt_utc", "").strip()
        regime   = r.get("synoptic_regime", "").strip() or "unknown"

        rows.append({
            "stid":       r["stid"],
            "event_id":   r["event_id"],
            "speed_err":  speed_err,
            "hrrr_10m":   hrrr_10m,
            "obs_sus":    obs_sus,
            "bc_speed":   bc_speed,
            "bc_dir":     bc_dir,
            "bc_level":   bc_level,
            "lat":        lat,
            "lon":        lon,
            "peak_dt":    peak_dt,
            "regime":     regime,
        })

n_total = len(rows)

# ── per-event summary data ────────────────────────────────────────────────────

event_meta = {}
by_event   = defaultdict(list)
for r in rows:
    by_event[r["event_id"]].append(r)

for eid, ev_rows in by_event.items():
    lats  = [r["lat"] for r in ev_rows if r["lat"] is not None]
    lons  = [r["lon"] for r in ev_rows if r["lon"] is not None]
    regime = ev_rows[0]["regime"]

    # Peak date: parse peak_dt timestamps, take the median date
    dates = []
    for r in ev_rows:
        try:
            dates.append(datetime.datetime.fromisoformat(
                r["peak_dt"].replace("Z", "+00:00")
            ))
        except Exception:
            pass

    peak_dt_utc = None
    peak_hour   = None
    peak_date   = None
    if dates:
        dates.sort()
        mid = dates[len(dates) // 2]
        peak_dt_utc = mid
        peak_hour   = mid.hour
        peak_date   = mid.strftime("%Y-%m-%d")

    # bc_level: check for consistency within event
    bc_levels = [r["bc_level"] for r in ev_rows if r["bc_level"]]
    bc_level_mode = max(set(bc_levels), key=bc_levels.count) if bc_levels else None

    event_meta[eid] = {
        "regime":       regime,
        "n_stations":   len(ev_rows),
        "ctr_lat":      float(np.mean(lats)) if lats else None,
        "ctr_lon":      float(np.mean(lons)) if lons else None,
        "peak_date":    peak_date,
        "peak_hour":    peak_hour,
        "bc_level":     bc_level_mode,
        "mean_speed_err": float(np.mean([r["speed_err"] for r in ev_rows])),
    }

# ── Q1: HRRR internal mixing ratio ───────────────────────────────────────────
# CONFOUND CHECK: is bc_level confounded with regime?

lines = []
def w(s=""): lines.append(s)

w("=" * 70)
w("ERA5 VERTICAL STRUCTURE REPORT  —  Phase A mechanism analysis")
w(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
w("=" * 70)
w()
w("Q1 (PRIMARY, N=12): HRRR internal mixing ratio HRRR_10m / bc_speed")
w("─" * 70)
w()

# bc_level × regime table
w("  CONFOUND CHECK: bc_level distribution by event (must not track regime)")
w()
w(f"  {'event_id':<25} {'regime':<25} {'bc_level':<10} {'mean_speed_err':>14}")
for eid in sorted(event_meta.keys()):
    m = event_meta[eid]
    w(f"  {eid:<25} {m['regime']:<25} {str(m['bc_level']):<10} {m['mean_speed_err']:>+14.2f}")
w()

# Check if offshore/continental splits by bc_level
offshore_levels = [event_meta[e]["bc_level"] for e in event_meta
                   if any(x in event_meta[e]["regime"]
                          for x in ("santa_ana", "diablo", "frontal"))]
continental_levels = [event_meta[e]["bc_level"] for e in event_meta
                      if any(x in event_meta[e]["regime"]
                             for x in ("chinook", "downslope"))]
w(f"  Offshore bc_levels:     {offshore_levels}")
w(f"  Continental bc_levels:  {continental_levels}")

offshore_unique   = set(x for x in offshore_levels if x)
continental_unique = set(x for x in continental_levels if x)
if offshore_unique == continental_unique or not (offshore_unique and continental_unique):
    confound = False
    w("  CONFOUND: NOT detected — bc_level is consistent across regimes.")
elif offshore_unique != continental_unique:
    confound = True
    w(f"  CONFOUND: DETECTED — offshore uses {offshore_unique}, continental uses {continental_unique}.")
    w("  Mixing ratio will be reported separately by bc_level.")
w()

# Compute per-station mixing ratio
station_ratios = []
for r in rows:
    if r["bc_speed"] and r["hrrr_10m"] and r["bc_speed"] > 2.0 and r["hrrr_10m"] is not None:
        ratio = r["hrrr_10m"] / r["bc_speed"]
        station_ratios.append({
            "event_id":  r["event_id"],
            "stid":      r["stid"],
            "regime":    r["regime"],
            "bc_level":  r["bc_level"],
            "ratio":     ratio,
            "hrrr_10m":  r["hrrr_10m"],
            "bc_speed":  r["bc_speed"],
            "obs_sus":   r["obs_sus"],
            "speed_err": r["speed_err"],
        })

# Collapse to event level
event_ratios = {}
for sr in station_ratios:
    eid = sr["event_id"]
    if eid not in event_ratios:
        event_ratios[eid] = {
            "ratios": [], "regime": sr["regime"], "bc_level": sr["bc_level"],
            "hrrr_10ms": [], "bc_speeds": [], "speed_errs": [],
        }
    event_ratios[eid]["ratios"].append(sr["ratio"])
    event_ratios[eid]["hrrr_10ms"].append(sr["hrrr_10m"])
    event_ratios[eid]["bc_speeds"].append(sr["bc_speed"])
    event_ratios[eid]["speed_errs"].append(sr["speed_err"])

event_ratio_summary = {}
for eid, d in event_ratios.items():
    event_ratio_summary[eid] = {
        "regime":        d["regime"],
        "bc_level":      d["bc_level"],
        "mean_ratio":    float(np.mean(d["ratios"])),
        "mean_hrrr_10m": float(np.mean(d["hrrr_10ms"])),
        "mean_bc_speed": float(np.mean(d["bc_speeds"])),
        "mean_speed_err": float(np.mean(d["speed_errs"])),
        "n":             len(d["ratios"]),
    }

# Report event-level ratios sorted by regime/ratio
w("  HRRR_10m / bc_speed  (event means, sorted by ratio)")
w(f"  {'event_id':<25} {'regime':<25} {'bc_lev':<7} {'ratio':>7}  "
  f"{'HRRR_10m':>9}  {'bc_speed':>9}  {'speed_err':>10}")
w()
for eid, d in sorted(event_ratio_summary.items(), key=lambda x: x[1]["mean_ratio"]):
    w(f"  {eid:<25} {d['regime']:<25} {str(d['bc_level']):<7} {d['mean_ratio']:>7.3f}  "
      f"{d['mean_hrrr_10m']:>9.1f}  {d['mean_bc_speed']:>9.1f}  {d['mean_speed_err']:>+10.2f}")
w()

# Group by offshore vs continental
OFFSHORE = ("santa_ana", "diablo", "frontal_passage")
CONTINENTAL = ("chinook", "downslope")

off_ratios = [d["mean_ratio"] for d in event_ratio_summary.values()
              if any(x in d["regime"] for x in OFFSHORE)]
con_ratios = [d["mean_ratio"] for d in event_ratio_summary.values()
              if any(x in d["regime"] for x in CONTINENTAL)]

w("  Regime-group means (event-level ratios):")
if off_ratios:
    w(f"    OFFSHORE_GRADIENT    (N={len(off_ratios)}): mean ratio = {np.mean(off_ratios):.3f}")
if con_ratios:
    w(f"    CONTINENTAL_DOWNSLOPE (N={len(con_ratios)}): mean ratio = {np.mean(con_ratios):.3f}")
if off_ratios and con_ratios:
    diff = np.mean(con_ratios) - np.mean(off_ratios)
    w(f"    Δ (continental − offshore): {diff:+.3f}")
    if diff > 0.05:
        w("    → HRRR mixes MORE of its aloft wind to the surface in continental events.")
        w("      In offshore events, HRRR is carrying less of bc_speed to the 10m level.")
    elif diff < -0.05:
        w("    → HRRR mixes MORE in offshore events (unexpected; check bc_level confound).")
    else:
        w("    → No meaningful mixing ratio difference between regimes.")
w()


# ── Q2: ERA5 10m via Open-Meteo ───────────────────────────────────────────────

w("─" * 70)
w("Q2 (SECONDARY, N=12): ERA5_10m vs obs vs HRRR_10m (Open-Meteo)")
w()
w("  Pulling ERA5 10m wind at event centroid, peak hour...")
w()

era5_event = {}
events_sorted = sorted(event_meta.keys())

for eid in events_sorted:
    m = event_meta[eid]
    if not m["peak_date"] or m["ctr_lat"] is None:
        w(f"  {eid}: SKIP (no peak date or centroid)")
        era5_event[eid] = None
        continue

    params = {
        "latitude":        m["ctr_lat"],
        "longitude":       m["ctr_lon"],
        "start_date":      m["peak_date"],
        "end_date":        m["peak_date"],
        "hourly":          "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "mph",
        "timezone":        "UTC",
    }
    try:
        r = requests.get(OM_BASE, params=params, timeout=30)
        if r.status_code != 200:
            w(f"  {eid}: HTTP {r.status_code}")
            era5_event[eid] = None
            continue

        hourly = r.json().get("hourly", {})
        spds   = hourly.get("wind_speed_10m", [])
        dirs   = hourly.get("wind_direction_10m", [])
        h      = m["peak_hour"] or 12
        if h < len(spds) and spds[h] is not None:
            era5_event[eid] = {"speed": float(spds[h]), "dir": float(dirs[h]) if dirs[h] is not None else None}
        else:
            era5_event[eid] = None
            w(f"  {eid}: null at hour {h}")
    except Exception as e:
        w(f"  {eid}: ERROR {e}")
        era5_event[eid] = None
    time.sleep(0.3)  # polite

# event-level obs and HRRR means
event_surface = {}
for eid, ev_rows in by_event.items():
    obs_vals  = [r["obs_sus"]  for r in ev_rows if r["obs_sus"]  is not None]
    hrrr_vals = [r["hrrr_10m"] for r in ev_rows if r["hrrr_10m"] is not None]
    event_surface[eid] = {
        "mean_obs":    float(np.mean(obs_vals))  if obs_vals  else None,
        "mean_hrrr":   float(np.mean(hrrr_vals)) if hrrr_vals else None,
        "regime":      event_meta[eid]["regime"],
    }

w("  ERA5_10m vs HRRR_10m vs obs  (event-level, at centroid peak-hour)")
w(f"  {'event_id':<25} {'regime':<25} {'obs':>7}  {'HRRR_10m':>9}  "
  f"{'ERA5_10m':>9}  {'HRRR_err':>9}  {'ERA5_err':>9}")
w()

era5_err_offshore = []
era5_err_continental = []
hrrr_err_offshore = []
hrrr_err_continental = []

for eid in sorted(events_sorted, key=lambda e: event_meta[e]["regime"]):
    es  = event_surface.get(eid, {})
    e5  = era5_event.get(eid)
    obs  = es.get("mean_obs")
    hrrr = es.get("mean_hrrr")
    regime = event_meta[eid]["regime"]
    e5_spd = e5["speed"] if e5 else None

    hrrr_err_str = f"{hrrr - obs:+7.1f}" if (hrrr is not None and obs is not None) else "    N/A"
    era5_err_str = f"{e5_spd - obs:+7.1f}" if (e5_spd is not None and obs is not None) else "    N/A"
    e5_str   = f"{e5_spd:7.1f}" if e5_spd is not None else "    N/A"
    obs_str  = f"{obs:5.1f}" if obs is not None else "  N/A"
    hrrr_str = f"{hrrr:7.1f}" if hrrr is not None else "    N/A"

    w(f"  {eid:<25} {regime:<25} {obs_str}  {hrrr_str}  {e5_str}  {hrrr_err_str}  {era5_err_str}")

    is_off = any(x in regime for x in OFFSHORE)
    is_con = any(x in regime for x in CONTINENTAL)
    if e5_spd is not None and obs is not None and hrrr is not None:
        if is_off:
            era5_err_offshore.append(e5_spd - obs)
            hrrr_err_offshore.append(hrrr - obs)
        elif is_con:
            era5_err_continental.append(e5_spd - obs)
            hrrr_err_continental.append(hrrr - obs)

w()
w("  Regime-group mean errors vs obs (event-level):")
if era5_err_offshore:
    w(f"    OFFSHORE — HRRR_10m err: {np.mean(hrrr_err_offshore):+.2f} mph  |  "
      f"ERA5_10m err: {np.mean(era5_err_offshore):+.2f} mph   (N={len(era5_err_offshore)})")
if era5_err_continental:
    w(f"    CONTINENTAL — HRRR_10m err: {np.mean(hrrr_err_continental):+.2f} mph  |  "
      f"ERA5_10m err: {np.mean(era5_err_continental):+.2f} mph   (N={len(era5_err_continental)})")
w()
if era5_err_offshore and hrrr_err_offshore:
    hrrr_off = np.mean(hrrr_err_offshore)
    era5_off = np.mean(era5_err_offshore)
    if abs(era5_off) < abs(hrrr_off) * 0.5:
        w("  → ERA5_10m is substantially closer to obs than HRRR_10m in offshore events.")
        w("    HRRR-specific failure at the surface. ERA5 captures more surface wind.")
    elif abs(era5_off) > abs(hrrr_off) * 0.8:
        w("  → ERA5_10m also undershoots in offshore events (similar magnitude to HRRR).")
        w("    Surface wind in these events is hard for reanalysis broadly — not HRRR-specific.")
    else:
        w("  → ERA5_10m captures more surface wind than HRRR but still undershoots obs.")
        w("    HRRR has an additional surface deficit beyond the general reanalysis limitation.")
w()


# ── Q3: CDS 850 cross-check ───────────────────────────────────────────────────

w("─" * 70)
w("Q3 (CORROBORATION, n=4 offshore CDS events): HRRR_bc_speed vs ERA5_850")
w("  All 4 are offshore. No continental contrast. N=4 spot-check only.")
w()

try:
    import xarray as xr

    def vec_speed_dir(u, v):
        spd = float(np.sqrt(float(u)**2 + float(v)**2)) * MS_TO_MPH
        d   = float((270.0 - np.degrees(np.arctan2(float(v), float(u)))) % 360.0)
        return spd, d

    for eid, nc_name in sorted(CDS_EVENTS.items()):
        nc_path = os.path.join(ERA5_DIR, nc_name)
        if not os.path.exists(nc_path):
            w(f"  {eid}: CDS file not found ({nc_name})")
            continue

        m     = event_meta.get(eid)
        er    = event_ratio_summary.get(eid)
        if m is None or m["peak_date"] is None:
            w(f"  {eid}: no peak date in event_meta")
            continue

        peak_hour = m["peak_hour"] if m["peak_hour"] is not None else 12
        regime_lbl = m["regime"] if m["regime"] else "unknown"

        ds = xr.open_dataset(nc_path)
        tname = "valid_time" if "valid_time" in ds.coords else "time"
        lev   = "pressure_level" if "pressure_level" in ds.coords else "level"

        target = np.datetime64(
            f"{m['peak_date']}T{peak_hour:02d}:00:00"
        )
        t_idx = int(np.argmin(np.abs(ds[tname].values - target)))

        u850 = float(ds["u"].sel({lev: 850}).isel({tname: t_idx}).mean())
        v850 = float(ds["v"].sel({lev: 850}).isel({tname: t_idx}).mean())
        era5_850_spd, era5_850_dir = vec_speed_dir(u850, v850)
        ds.close()

        hrrr_bc     = er["mean_bc_speed"] if er else None
        er_bc_level = er["bc_level"]      if er else "N/A"
        hrrr_bc_str = f"{hrrr_bc:.1f}"   if hrrr_bc is not None else "N/A"
        delta       = (hrrr_bc - era5_850_spd) if hrrr_bc is not None else None
        delta_str   = f"{delta:+.1f}"    if delta is not None else "N/A"

        w(f"  {eid:<25} ({regime_lbl})")
        w(f"    ERA5 850 hPa (CDS, domain-mean): {era5_850_spd:.1f} mph @ {era5_850_dir:.0f}°")
        w(f"    HRRR bc_speed (event-mean):      {hrrr_bc_str} mph  (bc_level={er_bc_level})")
        w(f"    Δ HRRR−ERA5 (aloft):             {delta_str} mph")
        w()

    w("  Interpretation: if HRRR_bc_speed ≈ ERA5_850 → HRRR's aloft is correct,")
    w("  the deficit is in the surface layer (consistent with Q1 mixing ratio).")
    w("  If HRRR_bc_speed << ERA5_850 → HRRR is also slow aloft (the forcing is too weak).")

except ImportError:
    w("  xarray not available in this env — Q3 CDS check skipped.")
    w("  Run in hrrr311 env for Q3.")
w()


# ── Summary verdict ───────────────────────────────────────────────────────────

w("─" * 70)
w("MECHANISM VERDICT")
w()

if off_ratios and con_ratios:
    ratio_diff = np.mean(con_ratios) - np.mean(off_ratios)
    era5_support = (bool(era5_err_offshore) and
                    abs(np.mean(era5_err_offshore)) < abs(np.mean(hrrr_err_offshore)) * 0.6)

    if ratio_diff > 0.05 and era5_support:
        w("  MECHANISM SUPPORTED: HRRR-specific surface mixing deficit in offshore events.")
        w(f"  - Internal ratio: continental {np.mean(con_ratios):.3f} > offshore {np.mean(off_ratios):.3f} (Δ={ratio_diff:+.3f})")
        if era5_err_offshore:
            w(f"  - ERA5_10m substantially closer to obs than HRRR in offshore events.")
        w("  HRRR carries less of its own aloft momentum to the surface in offshore-gradient flow.")
    elif ratio_diff > 0.05 and not era5_support:
        w("  PARTIAL: Internal mixing ratio shows offshore deficit,")
        w("  but ERA5_10m also undershoots — not entirely HRRR-specific.")
        w("  The down-mixing problem may be broader than HRRR alone.")
    elif ratio_diff <= 0.05:
        w("  NOT SUPPORTED: No meaningful mixing ratio difference by regime.")
        w("  The ~4 mph offshore underbias is not explained by HRRR mixing failure.")
        w("  Consider: HRRR's 10m output may be accurate relative to its aloft wind,")
        w("  but the aloft wind itself is biased.")
    if confound:
        w()
        w("  WARNING: bc_level confound detected — ratio difference may reflect")
        w("  level choice (850 vs 700), not regime-specific mixing. Interpret with caution.")

w()
w(f"  Effective N: 12 events  |  Station rows: {n_total} (pseudoreplication if used as N)")
w("END OF VERTICAL STRUCTURE REPORT")

report_str = "\n".join(lines)
print(report_str)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(report_str + "\n")
print(f"\nReport → {REPORT}")
