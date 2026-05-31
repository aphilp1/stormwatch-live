#!/usr/bin/env python3
"""
era5_pull.py
============
Pull ERA5 reanalysis via Open-Meteo archive API -- no login required.

Open-Meteo serves ERA5 at 0.25 deg (~28 km) hourly, no auth needed.
URL: https://archive-api.open-meteo.com/v1/era5

Purpose (from ncar_rda_pull_spec.md):
  1. ERA5-vs-sounding fidelity check: compare ERA5 700 hPa at sounding
     station location/time to IEM sounding values. Match = trusted BC source.
     Divergence = ESCALATE.
  2. Timing re-test: ERA5 continuous reanalysis, no HRRR truncation artifacts.
  3. BC characterization per event: 700 hPa speed/direction as reanalysis-
     quality BC input to replace the single HRRR run.
  4. Inversion diagnostics: temperature profile for stability characterization.

Sounding cross-check stations (from soundings_cache.json):
  REV Reno NV       39.57N  -119.80W  Camp Fire, Thomas Fire
  OAK Oakland CA    37.73N  -122.22W  Tubbs, Kincade
  OTX Spokane WA    47.68N  -117.63W  Missoula

Run: python era5_pull.py
"""

import sys, json, math, requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ERA5_BASE = "https://archive-api.open-meteo.com/v1/era5"

# ---------------------------------------------------------------------------
# Station + event registry
# ---------------------------------------------------------------------------

SOUNDING_STATIONS = {
    "REV": {"lat": 39.57,  "lon": -119.80, "name": "Reno NV"},
    "OAK": {"lat": 37.73,  "lon": -122.22, "name": "Oakland CA"},
    "OTX": {"lat": 47.68,  "lon": -117.63, "name": "Spokane WA"},
    "VBG": {"lat": 34.74,  "lon": -120.57, "name": "Vandenberg CA"},  # Thomas west-side ref
}

# Events: station, date range for pull, ignition time UTC, IEM sounding values
EVENTS = {
    "camp_fire_2018": {
        "station":   "REV",
        "start":     "2018-11-07",
        "end":       "2018-11-09",
        "ignition":  "2018-11-08T14:33",
        "iem_soundings": {
            "2018-11-08T00:00": {"spd_mph": 24.2, "dir_deg": 275, "hgt_m": 2891,
                                  "inv_base_m": 170},
            "2018-11-08T12:00": {"spd_mph": 19.6, "dir_deg": 265, "hgt_m": 2940,
                                  "inv_base_m": 1938},
        },
    },
    "tubbs_fire_2017": {
        "station":   "OAK",
        "start":     "2017-10-07",
        "end":       "2017-10-10",
        "ignition":  "2017-10-09T04:45",
        # Wyoming OAK (WMO 72493) -- corrected 2026-05-30 (IEM had CWMJ alias)
        "iem_soundings": {
            "2017-10-08T00:00": {"spd_mph": 23.0, "dir_deg": 300, "hgt_m": 3139},
            "2017-10-08T12:00": {"spd_mph": 24.2, "dir_deg": 320, "hgt_m": 3102},
        },
    },
    "thomas_fire_2017": {
        "station":   "VBG",  # Vandenberg west-side ref; IEM REV alias confirmed broken
        "start":     "2017-12-03",
        "end":       "2017-12-06",
        "ignition":  "2017-12-04T09:45",
        # Wyoming VBG (WMO 72393) -- corrected 2026-05-30 (IEM had CWMJ alias)
        "iem_soundings": {
            "2017-12-04T00:00": {"spd_mph": 33.3, "dir_deg": 310, "hgt_m": 3081,
                                  "inv_base_m": 1388},
            "2017-12-04T12:00": {"spd_mph": 27.7, "dir_deg": 310, "hgt_m": 3071,
                                  "inv_base_m": 121},
        },
    },
    "kincade_2019": {
        "station":   "OAK",
        "start":     "2019-10-26",  # Oct 27 peak-wind day (was wrong Oct 23 before)
        "end":       "2019-10-28",
        "ignition":  "2019-10-24T04:27",  # fire started Oct 24; peak wind Oct 27
        # Wyoming OAK (WMO 72493) Oct 27 -- corrected 2026-05-30
        "iem_soundings": {
            "2019-10-27T00:00": {"spd_mph": 23.0, "dir_deg": 320, "hgt_m": 3116},
            "2019-10-27T12:00": {"spd_mph": 53.0, "dir_deg": 295, "hgt_m": 3045},
        },
    },
    "missoula_dec2025": {
        "station":   "OTX",
        "start":     "2025-12-16",
        "end":       "2025-12-18",
        "ignition":  None,
        "iem_soundings": {
            "2025-12-17T00:00": {"spd_mph": 28.8, "dir_deg": 330, "hgt_m": 3108,
                                  "inv_base_m": 2619},
            "2025-12-17T12:00": {"spd_mph": 28.8, "dir_deg": 315, "hgt_m": 3166,
                                  "inv_base_m": 98},
        },
    },
}

# ---------------------------------------------------------------------------
# ERA5 fetch via Open-Meteo
# ---------------------------------------------------------------------------

PRESSURE_LEVELS = [500, 700, 850, 925]

def fetch_era5(lat: float, lon: float, start: str, end: str) -> Optional[Dict]:
    """Pull ERA5 hourly data for a point. Returns dict or None on failure."""
    hourly_vars = []
    for level in PRESSURE_LEVELS:
        hourly_vars += [
            f"wind_speed_{level}hPa",
            f"wind_direction_{level}hPa",
            f"temperature_{level}hPa",
            f"geopotential_height_{level}hPa",
        ]
    hourly_vars += ["wind_speed_10m", "wind_direction_10m",
                    "surface_pressure", "temperature_2m"]

    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": start,
        "end_date":   end,
        "hourly":     ",".join(hourly_vars),
        "wind_speed_unit": "mph",
        "timezone":  "UTC",
    }
    try:
        r = requests.get(ERA5_BASE, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        print(f"  ERA5 API error {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"  ERA5 fetch error: {e}")
        return None


def extract_at_time(data: Dict, target_time: str, var: str) -> Optional[float]:
    """Extract a single value at the closest hour to target_time."""
    times = data.get("hourly", {}).get("time", [])
    vals  = data.get("hourly", {}).get(var, [])
    if not times or not vals:
        return None
    # Find closest
    target = datetime.fromisoformat(target_time)
    best_i, best_diff = 0, float("inf")
    for i, t in enumerate(times):
        diff = abs((datetime.fromisoformat(t) - target).total_seconds())
        if diff < best_diff:
            best_diff, best_i = diff, i
    return vals[best_i] if best_i < len(vals) else None


def get_era5_700hpa_series(data: Dict) -> Tuple[List, List, List]:
    """Return (times, speeds_mph, dirs_deg) for 700 hPa."""
    times = data.get("hourly", {}).get("time", [])
    spds  = data.get("hourly", {}).get("wind_speed_700hPa", [])
    dirs  = data.get("hourly", {}).get("wind_direction_700hPa", [])
    return times, spds, dirs


# ---------------------------------------------------------------------------
# Fidelity check: ERA5 vs IEM sounding
# ---------------------------------------------------------------------------

def fidelity_check(event_name: str, era5_data: Dict,
                   iem_soundings: Dict) -> Dict:
    """Compare ERA5 700 hPa to IEM radiosonde at same time/place."""
    print(f"\n  Fidelity check: {event_name}")
    print(f"  {'Time (UTC)':^20} | {'ERA5 spd':>9} | {'IEM spd':>9} | "
          f"{'ERA5 dir':>9} | {'IEM dir':>9} | {'Δspd':>7} | {'Δdir':>7} | Verdict")
    print(f"  {'-'*20}-+-{'-'*9}-+-{'-'*9}-+-{'-'*9}-+-{'-'*9}-+-{'-'*7}-+-{'-'*7}-+-{'-'*12}")

    results = {}
    for t, iem in sorted(iem_soundings.items()):
        era5_spd = extract_at_time(era5_data, t, "wind_speed_700hPa")
        era5_dir = extract_at_time(era5_data, t, "wind_direction_700hPa")
        era5_hgt = extract_at_time(era5_data, t, "geopotential_height_700hPa")

        iem_spd = iem.get("spd_mph")
        iem_dir = iem.get("dir_deg")

        if era5_spd is None:
            print(f"  {t[:16]:^20} | {'NO DATA':>9}")
            continue

        d_spd = era5_spd - iem_spd if iem_spd else None
        d_dir = None
        if iem_dir is not None and era5_dir is not None:
            d_dir = ((era5_dir - iem_dir + 180) % 360) - 180

        spd_ok = d_spd is not None and abs(d_spd) < 5.0
        dir_ok = d_dir is not None and abs(d_dir) < 20.0
        verdict = ("MATCH ✓" if (spd_ok and dir_ok) else
                   "CLOSE" if (abs(d_spd or 99) < 10 and abs(d_dir or 99) < 30) else
                   "DIVERGE -- ESCALATE")

        d_spd_s = f"{d_spd:+.1f}" if d_spd is not None else "---"
        d_dir_s = f"{d_dir:+.0f}" if d_dir is not None else "---"
        hgt_s   = f"{era5_hgt:.0f}m" if era5_hgt else "---"

        print(f"  {t[:16]:^20} | {era5_spd:>7.1f}mph | {iem_spd or 0:>7.1f}mph | "
              f"{era5_dir or 0:>7.1f}deg | {iem_dir or 0:>7.0f}deg | "
              f"{d_spd_s:>7} | {d_dir_s:>7} | {verdict}  hgt={hgt_s}")

        results[t] = {"era5_spd": era5_spd, "era5_dir": era5_dir,
                      "era5_hgt": era5_hgt, "verdict": verdict}

    return results


# ---------------------------------------------------------------------------
# Timing re-test on ERA5
# ---------------------------------------------------------------------------

def timing_retest(event_name: str, era5_data: Dict,
                  ignition: Optional[str]) -> None:
    """ERA5 700 hPa time series -- timing re-test (no HRRR truncation)."""
    if ignition is None:
        return

    times, spds, dirs = get_era5_700hpa_series(era5_data)
    if not times:
        print(f"  No 700 hPa series for {event_name}")
        return

    spds = [s if s is not None else 0.0 for s in spds]
    peak_i = int(np.argmax(spds))
    peak_t = times[peak_i]
    peak_v = spds[peak_i]

    try:
        ign_dt  = datetime.fromisoformat(ignition)
        peak_dt = datetime.fromisoformat(peak_t)
        diff_h  = (peak_dt - ign_dt).total_seconds() / 3600
        if diff_h < -1:
            verdict = f"CONFIRMS declining limb (peak {abs(diff_h):.1f}h before ignition)"
        elif diff_h > 1:
            verdict = f"BREAKS -- peak {diff_h:.1f}h AFTER ignition"
        else:
            verdict = f"AT ignition (~{diff_h:.1f}h)"
    except Exception:
        diff_h, verdict = None, "timing error"

    # Value at ignition
    spd_ign = extract_at_time(era5_data, ignition, "wind_speed_700hPa")
    dir_ign = extract_at_time(era5_data, ignition, "wind_direction_700hPa")

    print(f"\n  ERA5 700 hPa timing -- {event_name}")
    print(f"    Ignition: {ignition}  ->  {spd_ign:.1f} mph @ {dir_ign:.0f} deg" if spd_ign else "")
    print(f"    Domain peak: {peak_v:.1f} mph at {peak_t}")
    print(f"    Verdict: {verdict}")
    print(f"    Note: ERA5 is a point, not domain-mean. Apply geometry check.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  ERA5 PULL via Open-Meteo archive (no login)")
    print("  Source: archive-api.open-meteo.com/v1/era5")
    print("  Cross-check: ERA5 700hPa vs IEM sounding at same location/time")
    print("=" * 72)

    all_results = {}

    for event_name, cfg in EVENTS.items():
        stn_id  = cfg["station"]
        stn     = SOUNDING_STATIONS[stn_id]
        print(f"\n{'='*70}")
        print(f"  {event_name}  --  {stn['name']} ({stn_id})")

        print(f"  Fetching ERA5 {cfg['start']} to {cfg['end']} ...", end=" ", flush=True)
        data = fetch_era5(stn["lat"], stn["lon"], cfg["start"], cfg["end"])
        if not data:
            print("FAILED")
            continue
        print("done.")

        # Fidelity check
        fid = fidelity_check(event_name, data, cfg["iem_soundings"])

        # Timing re-test
        timing_retest(event_name, data, cfg.get("ignition"))

        all_results[event_name] = {
            "station": stn_id, "fidelity": fid,
        }

    # Save
    with open("era5_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to era5_results.json")
    print()
    print("  For RDA ERA5 (ds633.0 OPeNDAP, full resolution + vertical profile):")
    print("    Register: https://rda.ucar.edu  (free, 'research/non-commercial')")
    print("    Then run era5_rda_pull.py (staged, pending credentials)")
