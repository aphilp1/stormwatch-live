#!/usr/bin/env python3
"""
sounding_pull.py
================
Pull radiosonde soundings from the University of Wyoming upper-air archive.
No login required -- open access.

Stations used per event (from ncar_rda_pull_spec.md + Brewer & Clements 2020):
  REV  72489  Reno, NV          -- Camp Fire crest-level sounding (paper used this)
  OAK  72493  Oakland, CA       -- Tubbs / Kincade Diablo cases
  TFX  72776  Great Falls, MT   -- Missoula cases (already used in dec17_final.py)
  OTX  72786  Spokane, WA       -- Missoula cases (already used)

Soundings pulled:
  Camp Fire   2018-11-08  00z + 12z  REV (Reno)
  Tubbs Fire  2017-10-08  00z + 12z  OAK (Oakland)
  Thomas Fire 2017-12-04  00z + 12z  REV (Reno) -- Santa Ana uses Reno as upstream ref
  Kincade     2019-10-23  00z + 12z  OAK (Oakland)

Output: per-sounding dict with mandatory levels, 700 hPa wind + inversion info.
Cross-check: ERA5 at same location/time should match -- divergence = ESCALATE.

Run: python sounding_pull.py
"""

import sys, re, math, json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import requests

sys.stdout.reconfigure(encoding="utf-8")

IEM_RAOB_BASE = "https://mesonet.agron.iastate.edu/json/raob.json"
# Note: Wyoming archive (weather.uwyo.edu/cgi-bin/sounding.py) returned 404;
# IEM RAOB API is the reliable path for historical soundings.

# Station registry (IEM uses 3-letter airport/station codes)
STATIONS = {
    "REV": {"name": "Reno NV",        "lat": 39.57, "lon": -119.80},
    "OAK": {"name": "Oakland CA",     "lat": 37.73, "lon": -122.22},
    "VBG": {"name": "Vandenberg CA",  "lat": 34.74, "lon": -120.57},  # Thomas upwind
    "TFX": {"name": "Great Falls MT", "lat": 47.46, "lon": -111.38},
    "OTX": {"name": "Spokane WA",     "lat": 47.68, "lon": -117.63},  # Missoula upwind
}

# Ridge stations per event for inversion-altitude cross-check
# Compare inversion base altitude to ridge station elevation
RIDGE_STATIONS = {
    "camp_fire_2018":    [("JBGC1 Jarbo Gap",    773)],   # m; well below 1940m inv
    "thomas_fire_2017":  [("Topa Topa ~6230ft",  1899)],  # m; check vs VBG inv
    "missoula_dec2025":  [("PNTM8 Point Six",    2408)],  # m; check vs OTX inv
    "tubbs_fire_2017":   [("Hawkeye (approx)",    600)],   # m; approx
    "kincade_2019":      [("Pine Flat Road (approx)", 400)],
}

# Events: list of (event_name, station_id, date_utc, hours_to_pull)
PULLS = [
    ("camp_fire_2018",   "REV", "2018-11-08", [0, 12]),
    ("tubbs_fire_2017",  "OAK", "2017-10-08", [0, 12]),
    ("tubbs_fire_2017",  "OAK", "2017-10-09", [0]),      # day of max spread
    ("thomas_fire_2017", "REV", "2017-12-04", [0, 12]),  # Reno -- east-side ref
    ("thomas_fire_2017", "VBG", "2017-12-04", [0, 12]),  # Vandenberg -- west-side ref
    ("kincade_2019",     "OAK", "2019-10-23", [0, 12]),
    ("kincade_2019",     "OAK", "2019-10-24", [0]),
    # Missoula -- OTX is the upwind sounding used in dec17_final.py
    ("missoula_dec2025", "OTX", "2025-12-17", [0, 12]),
]


# ---------------------------------------------------------------------------
# Wyoming archive fetch
# ---------------------------------------------------------------------------

def fetch_iem_sounding(station_id: str, year: int, month: int, day: int,
                        hour: int) -> Optional[Dict]:
    """Fetch sounding from IEM RAOB API (no login, historical)."""
    ts = f"{year}{month:02d}{day:02d}{hour:02d}00"
    try:
        r = requests.get(IEM_RAOB_BASE, params={"airport": station_id,
                                                  "ts": ts, "fmt": "json"},
                         timeout=30)
        if r.status_code == 200:
            d = r.json()
            profiles = d.get("profiles", [])
            if profiles:
                return profiles[0]  # first profile at that time
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parse sounding text
# ---------------------------------------------------------------------------

def parse_iem_sounding(profile: Dict) -> Optional[Dict]:
    """Convert IEM RAOB profile dict to our internal format."""
    raw_levels = profile.get("profile", [])
    if not raw_levels:
        return None

    levels = []
    for lev in raw_levels:
        pres = lev.get("pres")
        hght = lev.get("hght")
        temp = lev.get("tmpc")
        dwpt = lev.get("dwpc")
        drct = lev.get("drct")
        sknt = lev.get("sknt")
        if pres is None:
            continue
        spd_mph = sknt * 1.15078 if sknt is not None else None
        levels.append({
            "pres_hPa": float(pres),
            "hght_m":   float(hght) if hght is not None else None,
            "temp_c":   float(temp) if temp is not None else None,
            "dwpt_c":   float(dwpt) if dwpt is not None else None,
            "drct_deg": float(drct) if drct is not None else None,
            "sknt":     float(sknt) if sknt is not None else None,
            "spd_mph":  spd_mph,
        })

    return {
        "station": {"id": profile.get("station"), "valid": profile.get("valid")},
        "levels": levels,
    }


# ---------------------------------------------------------------------------
# Extract key diagnostics
# ---------------------------------------------------------------------------

def get_level(sounding: Dict, target_hPa: float,
              tolerance: float = 25.0) -> Optional[Dict]:
    """Find the closest level to target_hPa."""
    closest = None
    best_diff = float("inf")
    for lev in sounding["levels"]:
        diff = abs(lev["pres_hPa"] - target_hPa)
        if diff < best_diff and diff <= tolerance:
            best_diff = diff
            closest = lev
    return closest


def find_inversion(sounding: Dict, search_top_hPa: float = 600.0) -> Optional[Dict]:
    """Find the lowest temperature inversion above the surface."""
    levs = [l for l in sounding["levels"]
            if l["pres_hPa"] >= search_top_hPa and l["temp_c"] is not None]
    levs.sort(key=lambda x: x["pres_hPa"], reverse=True)  # surface to top

    for i in range(1, len(levs) - 1):
        prev = levs[i - 1]
        curr = levs[i]
        # Inversion = temperature INCREASES with altitude (decreases with pressure)
        if curr["temp_c"] > prev["temp_c"] and curr["pres_hPa"] < prev["pres_hPa"]:
            return {
                "base_hPa":  prev["pres_hPa"],
                "top_hPa":   curr["pres_hPa"],
                "base_hght": prev["hght_m"],
                "top_hght":  curr["hght_m"],
                "strength_c": curr["temp_c"] - prev["temp_c"],
            }
    return None


def bc_from_sounding(sounding: Dict) -> Dict:
    """Extract the BC-relevant diagnostics from a sounding."""
    l700 = get_level(sounding, 700)
    l500 = get_level(sounding, 500)
    l850 = get_level(sounding, 850)
    inv  = find_inversion(sounding)

    result = {
        "700hPa": {
            "pres":   l700["pres_hPa"] if l700 else None,
            "hght_m": l700["hght_m"]   if l700 else None,
            "temp_c": l700["temp_c"]   if l700 else None,
            "dir_deg": l700["drct_deg"] if l700 else None,
            "spd_mph": l700["spd_mph"] if l700 else None,
        },
        "500hPa": {
            "dir_deg": l500["drct_deg"] if l500 else None,
            "spd_mph": l500["spd_mph"] if l500 else None,
        },
        "850hPa": {
            "dir_deg": l850["drct_deg"] if l850 else None,
            "spd_mph": l850["spd_mph"] if l850 else None,
        },
        "inversion": inv,
        "700_hgt_m": l700["hght_m"] if l700 else None,
    }

    # Shear 700-850
    if l700 and l850 and l700["spd_mph"] and l850["spd_mph"]:
        result["shear_700_850_mph"] = abs(l700["spd_mph"] - l850["spd_mph"])

    return result


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  WYOMING SOUNDING PULL  --  Camp Fire, Tubbs, Thomas, Kincade")
    print("  Source: weather.uwyo.edu (open access, no login)")
    print("  Per ncar_rda_pull_spec.md experiment order")
    print("=" * 72)

    results = {}

    for event, station_id, date_str, hours in PULLS:
        stn = STATIONS[station_id]
        dt  = datetime.strptime(date_str, "%Y-%m-%d")

        for hour in hours:
            label = f"{event}  {station_id}  {date_str} {hour:02d}z"
            sys.stdout.write(f"\r  Fetching {label} ...     ")
            sys.stdout.flush()

            profile = fetch_iem_sounding(
                station_id, dt.year, dt.month, dt.day, hour)

            if not profile:
                print(f"\r  NO DATA: {label}")
                continue

            parsed = parse_iem_sounding(profile)
            if not parsed:
                print(f"\r  PARSE FAIL: {label}")
                continue

            bc = bc_from_sounding(parsed)
            key = f"{event}_{station_id}_{date_str}_{hour:02d}z"
            results[key] = {"event": event, "station": station_id,
                            "date": date_str, "hour": hour, "bc": bc}

            l7 = bc["700hPa"]
            inv = bc["inversion"]

            spd_s = f"{l7['spd_mph']:.0f}mph" if l7["spd_mph"] else "---"
            dir_s = f"{l7['dir_deg']:.0f}°"   if l7["dir_deg"] else "---"
            hgt_s = f"{l7['hght_m']:.0f}m"    if l7["hght_m"]  else "---"
            inv_s = (f"INV @{inv['base_hght']:.0f}-{inv['top_hght']:.0f}m "
                     f"(+{inv['strength_c']:.1f}°C)"
                     if inv else "no inversion")

            print(f"\r  {station_id} {date_str} {hour:02d}z | "
                  f"700hPa: {spd_s} @ {dir_s}  hgt={hgt_s} | {inv_s}")

    # ---------------------------------------------------------------------------
    # Summary table for BC audit
    # ---------------------------------------------------------------------------
    print()
    print("=" * 72)
    print("  BC SUMMARY TABLE (for WindNinja BC reference)")
    print("=" * 72)
    print(f"  {'Event':^20} | {'Stn':>4} | {'Date/Hr':^12} | "
          f"{'700hPa spd':>10} | {'700hPa dir':>10} | {'700hPa hgt':>10} | Inversion")
    print(f"  {'-'*20}-+-{'-'*4}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*20}")

    for key, r in sorted(results.items()):
        l7  = r["bc"]["700hPa"]
        inv = r["bc"]["inversion"]
        spd_s = f"{l7['spd_mph']:.1f} mph" if l7["spd_mph"] else "---"
        dir_s = f"{l7['dir_deg']:.0f} deg" if l7["dir_deg"] else "---"
        hgt_s = f"{l7['hght_m']:.0f} m"   if l7["hght_m"]  else "---"
        inv_s = f"+{inv['strength_c']:.1f}°C @{inv['base_hght']:.0f}m" if inv else "none"
        print(f"  {r['event']:^20} | {r['station']:>4} | "
              f"{r['date']} {r['hour']:02d}z | "
              f"{spd_s:>10} | {dir_s:>10} | {hgt_s:>10} | {inv_s}")

    # ---------------------------------------------------------------------------
    # Inversion-altitude cross-check: which ridge stations are above the lid?
    # ---------------------------------------------------------------------------
    print()
    print("=" * 72)
    print("  INVERSION-ALTITUDE TERRAIN CHECK")
    print("  Compare inversion base to ridge station elevation per event")
    print("  Below inversion lid = station samples gap flow (sub-inversion)")
    print("  Above inversion lid = station samples free-atmosphere flow (aloft)")
    print("=" * 72)

    # Collect best inversion per event (use 12z if available, else 00z)
    event_inversions = {}
    for key, r in results.items():
        ev = r["event"]
        inv = r["bc"]["inversion"]
        if inv is None:
            continue
        # Prefer 12z
        if ev not in event_inversions or r["hour"] == 12:
            event_inversions[ev] = {
                "station": r["station"], "date": r["date"], "hour": r["hour"],
                "inv_base_m": inv["base_hght"], "inv_top_m": inv["top_hght"],
                "inv_strength_c": inv["strength_c"],
                "stn_700_hgt": r["bc"]["700hPa"].get("hght_m"),
            }

    for event, ridge_stns in RIDGE_STATIONS.items():
        inv_data = event_inversions.get(event)
        print(f"\n  {event}")
        if not inv_data:
            print(f"    No inversion data available")
            continue
        inv_base = inv_data["inv_base_m"]
        inv_top  = inv_data["inv_top_m"]
        h700     = inv_data["stn_700_hgt"]
        print(f"    Sounding: {inv_data['station']} {inv_data['date']} {inv_data['hour']:02d}z")
        print(f"    Inversion: {inv_base:.0f}–{inv_top:.0f}m base–top "
              f"(+{inv_data['inv_strength_c']:.1f}°C)")
        if h700:
            print(f"    700 hPa level: {h700:.0f}m  "
                  f"(above inversion: {h700 - inv_top:.0f}m clearance)")
        for ridge_name, ridge_m in ridge_stns:
            if ridge_m < inv_base:
                verdict = f"BELOW lid by {inv_base - ridge_m:.0f}m -- samples gap flow ✓"
            elif ridge_m > inv_top:
                verdict = f"ABOVE lid by {ridge_m - inv_top:.0f}m -- samples free-atm flow"
            else:
                verdict = f"IN the inversion layer -- transition zone"
            print(f"    {ridge_name:30s} {ridge_m:5.0f}m  -> {verdict}")

    # Save for downstream use
    out_path = "soundings_cache.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to {out_path}")
    print()
    print("  NEXT STEP:")
    print("  1. Register at rda.ucar.edu (free) for ERA5 ds633.0 OPeNDAP access.")
    print("  2. Compare ERA5 700hPa at sounding location/time to the values above.")
    print("     ERA5 should match -- divergence = ESCALATE (ncar_rda_pull_spec.md §4b).")
    print("  3. Run era5_pull.py once RDA token is configured.")
