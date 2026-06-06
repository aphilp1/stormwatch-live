#!/usr/bin/env python3
"""
build_hrrr_error_dataset.py — Phase A: HRRR departure database
Run in conda env hrrr311 via run_phase_a.ps1 (sets Library/bin PATH for eccodes DLLs).

One row per station-event (ALL rows including excluded, qc_flag documents why).
QC inherited from raws_inventory.csv; excluded rows get qc_flag/qc_reason but no HRRR pull.
HRRR 10m wind pulled via herbie for KEEP/CAUTION rows only.
Marks NEEDS_xxx for data not yet available. FIT NOTHING.

Output: hrrr_error_dataset.csv + phase_a_report.txt
Source of truth: primary_goal_dataset_creation_spec.md
"""

import csv, math, os, sys

# Force UTF-8 stdout so Unicode box chars don't crash on Windows CP1252 console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)  # xarray merge compat warning
from datetime import datetime
from collections import defaultdict
import numpy as np

BASE       = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
RAWS_OBS   = os.path.join(BASE, "raws_obs")
INVENTORY  = os.path.join(RAWS_OBS, "raws_inventory.csv")
REGISTRY   = os.path.join(RAWS_OBS, "raws_station_registry.csv")
OUT_CSV    = os.path.join(BASE, "hrrr_error_dataset.csv")
OUT_REPORT = os.path.join(BASE, "phase_a_report.txt")
HERBIE_CACHE = os.path.join(BASE, "_herbie_cache")

# ── HRRR version / era lookup ────────────────────────────────────────────────
# Source: HRRR operational version history
_HRRR_ERAS = [
    ("2014-09-30", "2016-08-23", "v1", "v1_era"),
    ("2016-08-23", "2018-07-12", "v2", "v2_era"),
    ("2018-07-12", "2021-12-08", "v3", "v3_era"),
    ("2021-12-08", "2099-01-01", "v4", "v4_era"),
]

def hrrr_version(date_str):
    d = date_str[:10]
    for start, end, v, era in _HRRR_ERAS:
        if start <= d < end:
            return v, era
    return "NEEDS_HRRR_VERSION", "NEEDS_HRRR_VERSION"

# ── Synoptic regime + inversion lid by event ─────────────────────────────────
# Inversion lids (m) from master status / Wyoming sounding record.
# Camp: REV sounding ~1938m; Tubbs: OAK sounding ~174m; Thomas: VBG ~1388m.
# kincade_run: 850 hPa (~1500m, downward-propagating Diablo transition).
# missoula_dec2025: cold pool below ~1800m (from master status).
# Others: NEEDS_INVERSION.
EVENT_META = {
    "camp_2018":         {"regime": "diablo_offshore",    "inv_lid_m": 1938, "approx_date": "2018-11-08"},
    "tubbs_2017":        {"regime": "diablo_offshore",    "inv_lid_m":  174, "approx_date": "2017-10-08"},
    "kincade_ign_2019":  {"regime": "diablo_offshore_NW", "inv_lid_m": None, "approx_date": "2019-10-23"},
    "kincade_run_2019":  {"regime": "diablo_offshore_NE", "inv_lid_m": 1500, "approx_date": "2019-10-27"},
    "thomas_2017":       {"regime": "santa_ana",          "inv_lid_m": 1388, "approx_date": "2017-12-04"},
    "woolsey_2018":      {"regime": "santa_ana",          "inv_lid_m": None, "approx_date": "2018-11-08"},
    "labor_day_or2020":  {"regime": "downslope_oregon",   "inv_lid_m": None, "approx_date": "2020-09-07"},
    "marshall_2021":     {"regime": "chinook_frontrange",  "inv_lid_m": None, "approx_date": "2021-12-30"},
    "boulder_chin2021":  {"regime": "chinook_frontrange",  "inv_lid_m": None, "approx_date": "2021-01-13"},
    "missoula_dec2025":  {"regime": "frontal_passage",    "inv_lid_m": 1800, "approx_date": "2025-12-17"},
    "missoula_jul2024":  {"regime": "NEEDS_REGIME",       "inv_lid_m": None, "approx_date": "2024-07-15"},
    "iowa_derecho2020":  {"regime": "derecho",            "inv_lid_m": None, "approx_date": "2020-08-10"},
}

# ── QC flag mapping from raws_inventory flags ────────────────────────────────
def map_qc_flag(usable, caution, flags_str):
    """
    Map raws_inventory (usable, caution, flags) → (qc_flag, qc_reason).
    Every row gets a named status — no silent filtering.
    """
    flags = flags_str.strip() if flags_str else ""
    if usable == "yes":
        if caution == "yes":
            return "CAUTION", flags if flags else "caution_unspecified"
        return "KEEP", ""
    # Excluded — map reason
    if "ALL_SPD_NULL" in flags and "ALL_GUST_NULL" in flags:
        return "DROP_NO_WIND_DATA", flags
    if "GAP>" in flags:
        return "DROP_GAPPED", flags
    if "window_miss" in flags.lower():
        return "DROP_WINDOW_MISS", flags
    if "ALL_SPD_NULL" in flags:
        return "DROP_NO_SPEED", flags
    return "DROP_OTHER", flags if flags else "see_inventory"

# ── Terrain class heuristic (name + elevation) ───────────────────────────────
# Taxonomy from spec: exposed_ridge / canyon_gap / valley / summit_rotating / sub_inversion
# sub_inversion requires event-specific inversion lid → cannot assign at row-build time.
# summit_rotating is diagnosed after terrain rotation analysis (Phase B) — deferred.
# Heuristic assigns: exposed_ridge / canyon_gap / valley / open
# terrain_class_source column documents how it was assigned.
_CANYON_KW = {"gap", "gorge", "canyon", "creek", "river", "draw", "wash", "fork", "gulch", "narrows"}
_RIDGE_KW  = {"peak", "summit", "mountain", "lookout", "ridge", "top", "crest", "knob", "hill",
               "dome", "butte", "divide", "pass", "saddle"}
_VALLEY_KW = {"valley", "flat", "meadow", "basin", "plain", "bottom"}

def terrain_class_heuristic(name, elev_m):
    tokens = set(name.lower().replace("-", " ").replace("_", " ").split())
    if tokens & _CANYON_KW:
        return "canyon_gap", "name_heuristic"
    if tokens & _RIDGE_KW:
        return "exposed_ridge", "name_heuristic"
    if tokens & _VALLEY_KW:
        return "valley", "name_heuristic"
    try:
        e = float(elev_m)
        if e > 1500:
            return "exposed_ridge", "elev_heuristic"  # >4920 ft
        if e < 150:
            return "valley", "elev_heuristic"          # <490 ft
    except (TypeError, ValueError):
        pass
    return "open", "heuristic_unresolved"

# ── Elevation vs inversion lid ────────────────────────────────────────────────
def elev_vs_inversion(elev_m, inv_lid_m, tolerance_m=150):
    if inv_lid_m is None:
        return "NEEDS_INVERSION"
    if elev_m is None:
        return "NEEDS_ELEV"
    try:
        e, lid = float(elev_m), float(inv_lid_m)
        if e < lid - tolerance_m:
            return "below"
        if e > lid + tolerance_m:
            return "above"
        return "near"
    except (TypeError, ValueError):
        return "NEEDS_ELEV"

# ── Circular direction difference ────────────────────────────────────────────
def circ_diff(a, b):
    """a - b wrapped to [-180, 180]. Both meteorological FROM-convention degrees."""
    try:
        return round(((float(a) - float(b) + 180) % 360) - 180, 1)
    except (TypeError, ValueError):
        return None

# ── Vector-averaged direction ────────────────────────────────────────────────
def vec_avg_dir(dirs_deg):
    """Vector-mean direction from a list of meteorological degrees."""
    rads = [math.radians(float(d)) for d in dirs_deg if d is not None and str(d).strip()]
    if not rads:
        return None
    u = sum(math.sin(r) for r in rads) / len(rads)
    v = sum(math.cos(r) for r in rads) / len(rads)
    return (math.degrees(math.atan2(u, v)) + 360) % 360

# ── Parse ISO UTC string to datetime ────────────────────────────────────────
def parse_utc(s):
    try:
        return datetime.fromisoformat(s.rstrip("Z"))
    except Exception:
        return None

def hours_diff(s1, s2):
    a, b = parse_utc(s1), parse_utc(s2)
    if a and b:
        return abs((a - b).total_seconds()) / 3600
    return 9999

# ── Load obs-side peak for one station-event ─────────────────────────────────
def load_obs_peak(csv_path):
    """
    Return dict with peak obs info. Peak = max sustained wind in pull window.
    Direction = vector average over ±1h around the peak.
    Returns None if no valid obs.
    """
    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    spd = float(row["wind_speed_mph"]) if row.get("wind_speed_mph","").strip() else None
                except ValueError:
                    spd = None
                try:
                    dr = float(row["wind_dir_deg"]) if row.get("wind_dir_deg","").strip() else None
                except ValueError:
                    dr = None
                try:
                    gst = float(row["wind_gust_mph"]) if row.get("wind_gust_mph","").strip() else None
                except ValueError:
                    gst = None
                dt = row.get("datetime_utc", "").strip()
                if spd is not None:
                    rows.append({"dt": dt, "spd": spd, "dir": dr, "gust": gst})
    except Exception:
        return None

    nonzero = [r for r in rows if r["spd"] > 0]
    if not nonzero:
        return None

    peak = max(nonzero, key=lambda r: r["spd"])
    peak_dt = peak["dt"]

    window = [r for r in rows if hours_diff(r["dt"], peak_dt) <= 1.0 and r["dir"] is not None]
    obs_dir = vec_avg_dir([r["dir"] for r in window])

    pt = parse_utc(peak_dt)
    peak_hour_dt = pt.replace(minute=0, second=0, microsecond=0) if pt else None

    return {
        "obs_sus_mph":  round(peak["spd"], 2),
        "obs_gust_mph": round(peak["gust"], 2) if peak["gust"] is not None else None,
        "obs_dir_deg":  round(obs_dir, 1)      if obs_dir is not None      else None,
        "peak_dt_utc":  peak_dt,
        "peak_hour_dt": peak_hour_dt,
    }

# ── HRRR 10m wind pull via herbie ─────────────────────────────────────────────
_HRRR_CACHE = {}  # (date_str, hour_int) → xarray Dataset (merged u10+v10) or None

def get_hrrr_10m(date_str, hour):
    """Pull HRRR 10m wind U and V for a given UTC date and hour via herbie."""
    key = (date_str, hour)
    if key in _HRRR_CACHE:
        return _HRRR_CACHE[key]

    result = None
    try:
        from herbie import Herbie
        import xarray as xr
        dt_str = f"{date_str} {hour:02d}:00"
        print(f"  Herbie: {dt_str}Z ...", end=" ", flush=True)
        H = Herbie(dt_str, model="hrrr", product="sfc", fxx=0,
                   priority=["aws", "google"], save_dir=HERBIE_CACHE)
        ds_u = H.xarray(":UGRD:10 m above ground:")
        ds_v = H.xarray(":VGRD:10 m above ground:")
        result = xr.merge([ds_u, ds_v])
        print("OK", flush=True)
    except Exception as e:
        print(f"FAIL ({e})", flush=True)

    _HRRR_CACHE[key] = result
    return result

def extract_hrrr_point(ds, lat, lon):
    """
    Extract HRRR 10m speed (mph) and meteorological FROM direction (deg) at lat/lon.
    Handles HRRR's Lambert Conformal 2D grid by distance search.
    Returns (speed_mph, dir_deg) or (None, None).
    """
    if ds is None:
        return None, None
    try:
        lon360 = lon % 360
        lat_c  = ds.coords.get("latitude", ds.coords.get("lat"))
        lon_c  = ds.coords.get("longitude", ds.coords.get("lon"))
        if lat_c is None or lon_c is None:
            return None, None

        lats = lat_c.values
        lons = lon_c.values % 360
        dist2 = (lats - lat) ** 2 + (lons - lon360) ** 2
        ij = np.unravel_index(dist2.argmin(), dist2.shape)

        def get_comp(ds_local, key_upper):
            for vname in ds_local.data_vars:
                if key_upper in vname.upper():
                    arr = ds_local[vname].values
                    if arr.ndim == 2:
                        return float(arr[ij])
                    elif arr.ndim == 3:
                        return float(arr[0][ij])
            return None

        u_val = get_comp(ds, "UGRD") or get_comp(ds, "U10")
        v_val = get_comp(ds, "VGRD") or get_comp(ds, "V10")

        if u_val is None or v_val is None:
            return None, None

        speed_mph = math.sqrt(u_val**2 + v_val**2) * 2.23694
        # WMO met FROM direction: (270 − atan2(v, u)) mod 360
        # Verified: FROM N (u=0,v<0) → atan2(-|v|,0)=−90 → 270−(−90)=360=0° ✓
        dir_deg = (270.0 - math.degrees(math.atan2(v_val, u_val))) % 360
        return round(speed_mph, 2), round(dir_deg, 1)

    except Exception as e:
        print(f"      extract failed ({e})", flush=True)
        return None, None

# ── Haversine distance (km) ───────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
    return R * 2 * math.asin(math.sqrt(a))

# ── Spatial cluster assignment (per event, within ~5 km) ─────────────────────
def assign_spatial_clusters(rows_by_event, radius_km=5.0):
    """
    Assign spatial_cluster_id = "E-{event}-C{n}" to stations within radius_km of each other
    in the same event. Returns dict keyed by (event_id, stid).
    """
    cluster_map = {}
    for event, rows in rows_by_event.items():
        cluster_id = 0
        assigned = {}
        for i, r in enumerate(rows):
            key_i = (r["event_id"], r["stid"])
            if key_i in assigned:
                continue
            cluster_id += 1
            label = f"{event[:4]}-C{cluster_id:02d}"
            assigned[key_i] = label
            for j in range(i + 1, len(rows)):
                key_j = (rows[j]["event_id"], rows[j]["stid"])
                if key_j not in assigned:
                    try:
                        d = haversine_km(float(r["lat"]), float(r["lon"]),
                                         float(rows[j]["lat"]), float(rows[j]["lon"]))
                        if d <= radius_km:
                            assigned[key_j] = label
                    except (ValueError, TypeError):
                        pass
        cluster_map.update(assigned)
    return cluster_map

# ── Correlation-aware count ───────────────────────────────────────────────────
def correlation_aware_count(rows, radius_km=10.0):
    """Count independent station-events: stations within radius_km in same event = 1."""
    by_event = defaultdict(list)
    for r in rows:
        by_event[r["event_id"]].append(r)

    independent = 0
    for ev_rows in by_event.values():
        counted = [False] * len(ev_rows)
        for i, r in enumerate(ev_rows):
            if counted[i]:
                continue
            independent += 1
            for j in range(i + 1, len(ev_rows)):
                if not counted[j]:
                    try:
                        d = haversine_km(float(r["lat"]), float(r["lon"]),
                                         float(ev_rows[j]["lat"]), float(ev_rows[j]["lon"]))
                        if d < radius_km:
                            counted[j] = True
                    except (ValueError, TypeError):
                        pass
    return independent

# ── NEEDS_xxx check ───────────────────────────────────────────────────────────
def is_real(v):
    return v is not None and not str(v).startswith("NEEDS_") and v not in ("MISSING", "N/A", "")

# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(HERBIE_CACHE, exist_ok=True)

    print("=" * 70)
    print("Phase A — build_hrrr_error_dataset.py (v2 — full schema)")
    print(f"Run: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 70)

    # ── Load ALL inventory rows ───────────────────────────────────────────────
    all_inventory = []
    with open(INVENTORY, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            all_inventory.append(row)
    print(f"Loaded {len(all_inventory)} total station-events from inventory.")
    n_usable = sum(1 for r in all_inventory if r.get("usable","") == "yes")
    print(f"  usable=yes: {n_usable}  |  excluded: {len(all_inventory) - n_usable}")

    # ── Load station registry ─────────────────────────────────────────────────
    registry = {}
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            registry[row["stid"]] = row

    # ── Phase 1: build rows for all inventory entries ────────────────────────
    print(f"\nBuilding {len(all_inventory)} rows ...\n")

    dataset_by_event = defaultdict(list)
    dataset = []

    for inv in all_inventory:
        event   = inv["event"].strip()
        stid    = inv["stid"].strip()
        csv_rel = inv["file"].strip()
        csv_path = os.path.join(BASE, csv_rel)

        reg           = registry.get(stid, {})
        station_name  = reg.get("name", stid)

        try:
            lat = float(reg.get("lat", ""))
            lon = float(reg.get("lon", ""))
        except ValueError:
            lat = lon = None

        try:
            elev_m = float(reg.get("elev_m_derived", ""))
        except (ValueError, TypeError):
            elev_m = None

        usable  = inv.get("usable", "").strip()
        caution = inv.get("caution", "").strip()
        flags   = inv.get("flags", "").strip()
        qc_flag, qc_reason = map_qc_flag(usable, caution, flags)

        active = qc_flag in ("KEEP", "CAUTION")

        # Terrain class
        tc, tc_src = terrain_class_heuristic(station_name, elev_m) if station_name else ("MISSING", "")

        # HRRR version (use event approx date since peak_dt not yet known)
        meta       = EVENT_META.get(event, {})
        approx     = meta.get("approx_date", "2020-01-01")
        hrrr_v, hrrr_era = hrrr_version(approx)
        regime     = meta.get("regime", "NEEDS_REGIME")
        inv_lid    = meta.get("inv_lid_m")

        # Elevation vs inversion
        ev_inv = elev_vs_inversion(elev_m, inv_lid)

        # For excluded rows: minimal row, skip HRRR pull
        if not active:
            row = {
                "event_id":           event,
                "stid":               stid,
                "station_name":       station_name,
                "lat":                lat if lat is not None else "MISSING",
                "lon":                lon if lon is not None else "MISSING",
                "state":              reg.get("state", ""),
                "qc_flag":            qc_flag,
                "qc_reason":          qc_reason,
                "obs_sus_mph":        "N/A",
                "obs_gust_mph":       "N/A",
                "obs_dir_deg":        "N/A",
                "peak_dt_utc":        "N/A",
                "peak_hour_utc":      "N/A",
                "hrrr_10m_mph":       "N/A",
                "hrrr_10m_dir":       "N/A",
                "speed_err":          "N/A",
                "speed_ratio":        "N/A",
                "dir_err":            "N/A",
                "arrival_err":        "N/A",
                "elev_m":             round(elev_m, 1) if elev_m is not None else "MISSING",
                "slope":              "NEEDS_DEM",
                "aspect":             "NEEDS_DEM",
                "relief_1km":         "NEEDS_DEM",
                "terrain_class":      tc,
                "terrain_class_source": tc_src,
                "dem_verified":       "no",
                "elev_vs_inversion":  ev_inv,
                "bc_dir":             "NEEDS_BC",
                "bc_speed":           "NEEDS_BC",
                "bc_level":           "NEEDS_BC",
                "lapse_stability":    "NEEDS_BC",
                "mslp_grad":          "NEEDS_BC",
                "wn_minus_hrrr_speed": "NEEDS_WN",
                "wn_minus_hrrr_dir":   "NEEDS_WN",
                "hrrr_version":       hrrr_v,
                "hrrr_era":           hrrr_era,
                "synoptic_regime":    regime,
                "spatial_cluster_id": "PENDING",
                "repr_error_flag":    "NEEDS_DEM",
            }
            dataset.append(row)
            if lat is not None and lon is not None:
                dataset_by_event[event].append(row)
            continue

        # ── Active rows: compute obs peak, pull HRRR ──────────────────────────
        obs = load_obs_peak(csv_path)
        if obs is None or obs["peak_hour_dt"] is None:
            # No valid obs despite usable=yes — treat as excluded with reason
            row = {
                "event_id": event, "stid": stid, "station_name": station_name,
                "lat": lat if lat is not None else "MISSING",
                "lon": lon if lon is not None else "MISSING",
                "state": reg.get("state", ""),
                "qc_flag": "DROP_NO_VALID_OBS",
                "qc_reason": "csv_had_no_nonzero_speed_or_bad_timestamp",
                "obs_sus_mph": "N/A", "obs_gust_mph": "N/A", "obs_dir_deg": "N/A",
                "peak_dt_utc": "N/A", "peak_hour_utc": "N/A",
                "hrrr_10m_mph": "N/A", "hrrr_10m_dir": "N/A",
                "speed_err": "N/A", "speed_ratio": "N/A", "dir_err": "N/A", "arrival_err": "N/A",
                "elev_m": round(elev_m, 1) if elev_m is not None else "MISSING",
                "slope": "NEEDS_DEM", "aspect": "NEEDS_DEM", "relief_1km": "NEEDS_DEM",
                "terrain_class": tc, "terrain_class_source": tc_src, "dem_verified": "no",
                "elev_vs_inversion": ev_inv,
                "bc_dir": "NEEDS_BC", "bc_speed": "NEEDS_BC", "bc_level": "NEEDS_BC",
                "lapse_stability": "NEEDS_BC", "mslp_grad": "NEEDS_BC",
                "wn_minus_hrrr_speed": "NEEDS_WN", "wn_minus_hrrr_dir": "NEEDS_WN",
                "hrrr_version": hrrr_v, "hrrr_era": hrrr_era,
                "synoptic_regime": regime, "spatial_cluster_id": "PENDING",
                "repr_error_flag": "NEEDS_DEM",
            }
            dataset.append(row)
            continue

        peak_date_str = obs["peak_hour_dt"].strftime("%Y-%m-%d")
        peak_hour_int = obs["peak_hour_dt"].hour
        peak_hour_iso = obs["peak_hour_dt"].strftime("%Y-%m-%dT%H:00Z")

        # Re-derive hrrr_version from actual peak date (more accurate than event approx)
        hrrr_v, hrrr_era = hrrr_version(peak_date_str)

        # HRRR 10m pull
        hrrr_ds = get_hrrr_10m(peak_date_str, peak_hour_int) if lat is not None else None
        hrrr_speed, hrrr_dir = extract_hrrr_point(hrrr_ds, lat, lon) if (hrrr_ds is not None and lat is not None) else (None, None)

        speed_err = speed_ratio = dir_err = None
        if hrrr_speed is not None:
            speed_err   = round(hrrr_speed - obs["obs_sus_mph"], 2)
            speed_ratio = round(hrrr_speed / obs["obs_sus_mph"], 3) if obs["obs_sus_mph"] > 0 else None
        if hrrr_dir is not None and obs["obs_dir_deg"] is not None:
            dir_err = circ_diff(hrrr_dir, obs["obs_dir_deg"])

        ev_inv = elev_vs_inversion(elev_m, inv_lid)

        row = {
            # Identity
            "event_id":            event,
            "stid":                stid,
            "station_name":        station_name,
            "lat":                 lat,
            "lon":                 lon,
            "state":               reg.get("state", ""),
            # QC
            "qc_flag":             qc_flag,
            "qc_reason":           qc_reason,
            # Obs side
            "obs_sus_mph":         obs["obs_sus_mph"],
            "obs_gust_mph":        obs["obs_gust_mph"]  if obs["obs_gust_mph"]  is not None else "MISSING",
            "obs_dir_deg":         obs["obs_dir_deg"]   if obs["obs_dir_deg"]   is not None else "MISSING",
            "peak_dt_utc":         obs["peak_dt_utc"],
            "peak_hour_utc":       peak_hour_iso,
            # HRRR 10m side
            "hrrr_10m_mph":        hrrr_speed  if hrrr_speed is not None else "NEEDS_HRRR_10M",
            "hrrr_10m_dir":        hrrr_dir    if hrrr_dir   is not None else "NEEDS_HRRR_10M",
            # Error channels (targets)
            "speed_err":           speed_err   if speed_err   is not None else "NEEDS_HRRR_10M",
            "speed_ratio":         speed_ratio if speed_ratio is not None else "NEEDS_HRRR_10M",
            "dir_err":             dir_err     if dir_err     is not None else "NEEDS_HRRR_10M",
            "arrival_err":         "NEEDS_HRRR_TS",
            # Terrain predictors (obs-independent)
            "elev_m":              round(elev_m, 1) if elev_m is not None else "MISSING",
            "slope":               "NEEDS_DEM",
            "aspect":              "NEEDS_DEM",
            "relief_1km":          "NEEDS_DEM",
            "terrain_class":       tc,
            "terrain_class_source": tc_src,
            "dem_verified":        "no",
            # Synoptic predictors
            "elev_vs_inversion":   ev_inv,
            "bc_dir":              "NEEDS_BC",
            "bc_speed":            "NEEDS_BC",
            "bc_level":            "NEEDS_BC",
            "lapse_stability":     "NEEDS_BC",
            "mslp_grad":           "NEEDS_BC",
            # WindNinja discrepancy
            "wn_minus_hrrr_speed": "NEEDS_WN",
            "wn_minus_hrrr_dir":   "NEEDS_WN",
            # Nonstationarity / validation tags
            "hrrr_version":        hrrr_v,
            "hrrr_era":            hrrr_era,
            "synoptic_regime":     regime,
            "spatial_cluster_id":  "PENDING",   # assigned below
            # Representativeness
            "repr_error_flag":     "NEEDS_DEM",
        }
        dataset.append(row)
        if lat is not None and lon is not None:
            dataset_by_event[event].append(row)

    print(f"\n{'─'*60}")
    print(f"Built {len(dataset)} rows ({n_usable} active + {len(dataset)-n_usable} excluded/flags).")

    # ── Assign spatial clusters ───────────────────────────────────────────────
    cluster_map = assign_spatial_clusters(dataset_by_event, radius_km=5.0)
    for row in dataset:
        key = (row["event_id"], row["stid"])
        row["spatial_cluster_id"] = cluster_map.get(key, "ISOLATED")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    cols = list(dataset[0].keys())
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(dataset)
    print(f"\nWrote {len(dataset)} rows → {OUT_CSV}")

    # ────────────────────────────────────────────────────────────────────────
    # PHASE A REPORT
    # ────────────────────────────────────────────────────────────────────────
    keep_rows  = [r for r in dataset if r["qc_flag"] in ("KEEP", "CAUTION")]
    speed_rows = [r for r in keep_rows if is_real(r["speed_err"])]
    dir_rows   = [r for r in keep_rows if is_real(r["dir_err"])]

    R = []
    def line(s=""): R.append(s)

    line("=" * 70)
    line("PHASE A REPORT — HRRR Departure Database")
    line(f"Generated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    line("=" * 70)
    line()
    line(f"Total rows in dataset: {len(dataset)}")

    qc_counts = defaultdict(int)
    for r in dataset:
        qc_counts[r["qc_flag"]] += 1
    for k in sorted(qc_counts.keys()):
        line(f"  {k:<30} {qc_counts[k]:5d} rows")
    line()

    # ── Row counts per channel ────────────────────────────────────────────────
    line(f"ACTIVE rows (KEEP + CAUTION): {len(keep_rows)}")
    line(f"  Speed channel  (speed_err complete): {len(speed_rows)}")
    line(f"  Direction channel (dir_err complete): {len(dir_rows)}")
    line(f"  Arrival channel: 0  (all NEEDS_HRRR_TS)")
    line()

    # ── By event ──────────────────────────────────────────────────────────────
    line(f"Events: {len(set(r['event_id'] for r in keep_rows))}")
    for ev in sorted(set(r["event_id"] for r in keep_rows)):
        ev_keep  = [r for r in keep_rows if r["event_id"] == ev]
        ev_speed = sum(1 for r in ev_keep if is_real(r["speed_err"]))
        ev_dir   = sum(1 for r in ev_keep if is_real(r["dir_err"]))
        regime   = ev_keep[0]["synoptic_regime"]
        hrrr_v   = ev_keep[0]["hrrr_version"]
        line(f"  {ev:<25} n={len(ev_keep):3d}  spd_ok={ev_speed:3d}  dir_ok={ev_dir:3d}"
             f"  {regime}  {hrrr_v}")
    line()

    # ── Correlation-aware count ───────────────────────────────────────────────
    corr_speed = correlation_aware_count(speed_rows)
    corr_dir   = correlation_aware_count(dir_rows)
    line("Correlation-aware counts (stations within 10 km / same event = 1 independent):")
    line(f"  Speed channel:     raw={len(speed_rows)}, independent≈{corr_speed}")
    line(f"  Direction channel: raw={len(dir_rows)}, independent≈{corr_dir}")
    line(f"  Effective N for leave-one-regime-out ≈ {len(set(r['event_id'] for r in speed_rows))} events")
    line()

    # ── Spatial cluster summary ───────────────────────────────────────────────
    cluster_ids = set(r["spatial_cluster_id"] for r in keep_rows if r["spatial_cluster_id"] not in ("PENDING","ISOLATED",""))
    line(f"Spatial clusters assigned: {len(cluster_ids)} clusters across {len(keep_rows)} active rows")
    n_isolated = sum(1 for r in keep_rows if r["spatial_cluster_id"] == "ISOLATED")
    line(f"  Isolated stations (no neighbor within 5 km): {n_isolated}")
    line()

    # ────────────────────────────────────────────────────────────────────────
    # STRUCTURED-VS-WHITE DEPARTURE CHECK
    # ────────────────────────────────────────────────────────────────────────
    line("─" * 70)
    line("STRUCTURED-VS-WHITE DEPARTURE CHECK")
    line("Variance(per-class mean departures) ÷ pooled within-class variance.")
    line("Ratio >> 1 → terrain-structured (signal). Ratio ≈ 1 → white w.r.t. terrain.")
    line("NOTE: terrain_class is a name/elevation heuristic — DEM verification needed.")
    line()

    for ch_name, ch_rows, col in [
        ("speed_err  (hrrr_10m_mph − obs_sus_mph)", speed_rows, "speed_err"),
        ("dir_err    (circular hrrr_10m_dir − obs_dir)", dir_rows, "dir_err"),
    ]:
        line(f"Channel: {ch_name}")
        by_class = defaultdict(list)
        for r in ch_rows:
            v = r.get(col)
            if is_real(v):
                try:
                    by_class[r["terrain_class"]].append(float(v))
                except ValueError:
                    pass

        classes  = sorted(by_class.keys())
        n_total  = sum(len(v) for v in by_class.values())
        line(f"  Classes with data: {classes}  (n total={n_total})")

        if len(classes) < 2:
            line("  Cannot compute between-bin spread: fewer than 2 classes with data.")
            line()
            continue

        class_means     = {}
        within_sq       = []
        for tc in classes:
            vals = np.array(by_class[tc])
            m    = float(np.mean(vals))
            class_means[tc] = m
            within_sq.extend(((vals - m) ** 2).tolist())
            line(f"    {tc:<20} n={len(vals):4d}  mean={m:+7.2f}  std={float(np.std(vals)):6.2f}")

        between_var = float(np.var(list(class_means.values()), ddof=0))
        within_var  = float(np.mean(within_sq)) if within_sq else 0.0
        ratio       = between_var / within_var if within_var > 0 else float("inf")

        line(f"  Between-bin variance (of class means): {between_var:.3f}")
        line(f"  Within-bin variance  (pooled):         {within_var:.3f}")
        line(f"  RATIO between/within:                  {ratio:.3f}")
        interp = ("Departures appear white w.r.t. terrain class — no exploitable structure."
                  if ratio < 0.5 else
                  f"Weak-to-moderate terrain structure (ratio {ratio:.2f}) — verify with DEM classes."
                  if ratio < 1.5 else
                  f"TERRAIN STRUCTURE PRESENT (ratio {ratio:.2f}) — Phase B go-signal for this channel.")
        line(f"  Interpretation: {interp}")
        line()

    # ── By regime ─────────────────────────────────────────────────────────────
    if speed_rows:
        line("─" * 70)
        line("SPEED_ERR by synoptic regime (descriptive):")
        by_regime = defaultdict(list)
        for r in speed_rows:
            if is_real(r["speed_err"]):
                try:
                    by_regime[r["synoptic_regime"]].append(float(r["speed_err"]))
                except ValueError:
                    pass
        for rg in sorted(by_regime):
            vals = by_regime[rg]
            line(f"  {rg:<28} n={len(vals):4d}  mean={np.mean(vals):+6.2f}  std={np.std(vals):5.2f}")
        line()

    # ── Inversion coverage ────────────────────────────────────────────────────
    line("─" * 70)
    line("INVERSION COVERAGE (elev_vs_inversion):")
    inv_counts = defaultdict(int)
    for r in keep_rows:
        inv_counts[r["elev_vs_inversion"]] += 1
    for k in sorted(inv_counts.keys()):
        line(f"  {k:<25} {inv_counts[k]:5d} rows")
    line()

    # ── NEEDS_xxx summary ─────────────────────────────────────────────────────
    line("─" * 70)
    line("NEEDS_xxx flag summary (data to fill in Phase B+):")
    needs_counts = defaultdict(int)
    for r in dataset:
        for v in r.values():
            s = str(v)
            if s.startswith("NEEDS_"):
                needs_counts[s] += 1
    for k in sorted(needs_counts.keys()):
        line(f"  {k:<35} {needs_counts[k]:5d} cells")
    line()

    # ── Go/no-go ──────────────────────────────────────────────────────────────
    line("─" * 70)
    line("PHASE A ASSESSMENT:")
    line(f"  Speed channel:  {len(speed_rows)} complete rows / {corr_speed} independent /"
         f" {len(set(r['event_id'] for r in speed_rows))} events")
    line(f"  Direction:      {len(dir_rows)} complete rows / {corr_dir} independent")
    line(f"  Arrival:        0 complete rows (NEEDS_HRRR_TS for all)")
    line(f"  Terrain class:  heuristic only — DEM verification before crediting terrain signal")
    line(f"  repr_error_flag: NEEDS_DEM for all — separability pre-condition (spec rule #0)")
    line(f"                   cannot be run until DEM roughness is computed per cell")
    line()
    line("END OF PHASE A REPORT")

    report_text = "\n".join(R)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n" + report_text)
    print(f"\nReport written → {OUT_REPORT}")


if __name__ == "__main__":
    main()
