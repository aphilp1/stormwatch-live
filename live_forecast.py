"""
live_forecast.py
================

Live fire-wind outlook for any location, produced by feeding CURRENT forecast
data through the repo's own ``mechanism_classifier`` -- the same rule-based
engine and the same THRESHOLDS used on the hindcast library, now pointed at the
next 24-48 h instead of a past event.

This wires the "feature extraction" seam described in CLAUDE_CODE_HANDOFF.md,
using a free public model (Open-Meteo: surface + pressure levels) as a stand-in
for the HRRR/WindNinja pipeline. It proves the classification logic live and
emits a forecast on demand. The high-resolution terrain step (Herbie -> HRRR ->
WindNinja) remains the separate, heavier seam; this does NOT replace it.

Honest-uncertainty by design: diagnostics that a point forecast cannot observe
(satellite plume, sub-hourly downburst blast, terrain cross-ridge component) are
left as None, so the classifier skips them and reports a lower evidence_fraction
rather than guessing -- exactly as it does on real events.

Pure standard library (urllib/json): no pip, no conda. Runs under system Python.

Usage
-----
    python live_forecast.py                      # all catalogued sites
    python live_forecast.py "Yarnell AZ"         # a named place
    python live_forecast.py 39.76,-121.37        # raw lat,lon
    python live_forecast.py --json               # machine-readable, all sites
    python live_forecast.py --hours 36 "Paradise CA"
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from mechanism_classifier import (
    EventDiagnostics,
    classify,
    THRESHOLDS,
    WINDNINJA_APPLICABILITY,
)

MS_TO_MPH = 2.236936

# Minimum surface wind for a direction change to count as a real transition
# (below this, direction is light-and-variable noise). m/s.
MEANINGFUL_WIND_MS = 4.0

# Fire-weather threat gate -- physically-motivated STARTING values, to be
# calibrated against the hindcast library (same philosophy as THRESHOLDS).
# A mechanism label is only headlined when a fire-relevant wind event exists.
THREAT = {
    "critical_gust_mph": 35.0, "critical_rh_pct": 15.0,
    "elevated_gust_mph": 25.0, "elevated_rh_pct": 25.0,
}

# Catalogued fire-wind locations (coords approximate the event/RAWS anchor).
# Mirrors the hindcast_event_library so the live tool covers the same ground.
SITES = {
    "Camp Fire / Jarbo Gap, CA":   (39.76, -121.37, "America/Los_Angeles"),
    "Tubbs / Mayacamas, CA":       (38.55, -122.62, "America/Los_Angeles"),
    "Thomas / Santa Ynez, CA":     (34.52, -119.30, "America/Los_Angeles"),
    "Woolsey / Santa Monica Mts":  (34.10, -118.75, "America/Los_Angeles"),
    "Marshall / Boulder Co, CO":   (39.94, -105.18, "America/Denver"),
    "Yarnell Hill, AZ":            (34.22, -112.75, "America/Phoenix"),
    "Labor Day / W. Cascades OR":  (44.20, -122.20, "America/Los_Angeles"),
}


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def geocode(place: str):
    """Resolve 'lat,lon' or a place name to (lat, lon, label, tz)."""
    s = place.strip()
    # raw decimal coordinates
    parts = s.split(",")
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            return lat, lon, f"{lat:.3f},{lon:.3f}", "auto"
        except ValueError:
            pass
    # Try the full string, then (if it has a trailing 2-letter state) the town
    # alone filtered to that state -- Open-Meteo's geocoder dislikes "Town ST".
    US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL",
                 "IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT",
                 "NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI",
                 "SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"}
    words = s.split()
    state = words[-1].upper() if len(words) >= 2 and words[-1].upper() in US_STATES else None
    queries = [(s, None)]
    if state:
        queries.append((" ".join(words[:-1]), state))

    for q, st in queries:
        url = ("https://geocoding-api.open-meteo.com/v1/search?"
               + urllib.parse.urlencode({"name": q, "count": 10, "language": "en", "format": "json"}))
        results = _get_json(url).get("results") or []
        us = [x for x in results if x.get("country_code") == "US"]
        r = (next((x for x in us if (x.get("admin1_id") or x.get("admin1")) and st
                   and _state_abbr(x.get("admin1", "")) == st), None)
             or (us[0] if us else None) or (results[0] if results else None))
        if r:
            label = f"{r['name']}, {r.get('admin1', r.get('country_code', 'US'))}"
            return r["latitude"], r["longitude"], label, r.get("timezone", "auto")
    raise SystemExit(f'Location not found: "{place}". Try "City ST" or "lat,lon".')


_STATE_NAMES = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA",
    "colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA",
    "hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS",
    "kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD","massachusetts":"MA",
    "michigan":"MI","minnesota":"MN","mississippi":"MS","missouri":"MO","montana":"MT",
    "nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ","new mexico":"NM",
    "new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
    "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC",
    "south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT",
    "virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI","wyoming":"WY",
}


def _state_abbr(name: str) -> str:
    return _STATE_NAMES.get(name.strip().lower(), "")


def fetch_forecast(lat: float, lon: float, tz: str, hours: int):
    url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": ",".join([
            "temperature_2m", "relative_humidity_2m", "surface_pressure",
            "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "cape",
            "wind_speed_700hPa", "wind_direction_700hPa",
            "temperature_700hPa", "temperature_850hPa",
        ]),
        "wind_speed_unit": "ms", "timezone": tz, "forecast_days": 3,
    }))
    data = _get_json(url)
    h = data["hourly"]
    n = min(hours, len(h["time"]))
    return {k: (v[:n] if isinstance(v, list) else v) for k, v in h.items()}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "StormWatch-live_forecast/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Live data -> EventDiagnostics (the feature-extraction seam)
# ---------------------------------------------------------------------------

def _angdiff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def build_diagnostics(h: dict, event_id: str) -> tuple[EventDiagnostics, dict]:
    """Map a window of hourly forecast data onto the classifier's inputs.

    Returns (diagnostics, peak_summary). Only diagnostics a point forecast can
    actually support are populated; the rest stay None on purpose.
    """
    w700 = [x for x in h["wind_speed_700hPa"] if x is not None]
    cape = [x for x in h["cape"] if x is not None]
    t700 = h["temperature_700hPa"]
    t850 = h["temperature_850hPa"]
    spd = h["wind_speed_10m"]
    gust = h["wind_gusts_10m"]
    wdir = h["wind_direction_10m"]
    t2m = h["temperature_2m"]

    # --- synoptic forcing ---
    w700_max = max(w700) if w700 else None
    w700_min = min(w700) if w700 else None
    # "sustained regime" = 700 hPa flow never drops below the weak-forcing floor
    forcing_sustained = (w700_min >= THRESHOLDS["w700_weak_ms"]) if w700_min is not None else None

    # --- stability: 850->700 hPa lapse rate as a low-level proxy (~1.5 km apart) ---
    lapses = [(a - b) / 1.5 for a, b in zip(t850, t700) if a is not None and b is not None]
    low_level_lapse = (sum(lapses) / len(lapses)) if lapses else None

    # --- convection potential ---
    cape_max = max(cape) if cape else None

    # --- temporal transition (hourly resolution: shift step = 60 min) ---
    # Only count a direction change between hours where BOTH winds are
    # meaningful (>= MEANINGFUL_WIND_MS). Light-and-variable swings are not a
    # transition and would otherwise masquerade as a frontal/PBL shift.
    shifts = [_angdiff(wdir[i], wdir[i - 1]) for i in range(1, len(wdir))
              if wdir[i] is not None and wdir[i - 1] is not None
              and spd[i] is not None and spd[i - 1] is not None
              and spd[i] >= MEANINGFUL_WIND_MS and spd[i - 1] >= MEANINGFUL_WIND_MS]
    wind_shift = max(shifts) if shifts else None
    shift_dur = 60.0 if wind_shift is not None else None

    # Frontal thermodynamics (temp_drop_c / pres_rise_hpa) are deliberately
    # left None: a 24-48 h point forecast cannot separate a true frontal
    # passage from the ordinary diurnal cycle, and the classifier's design is
    # to skip a diagnostic rather than guess it.

    # --- gust ratio (downburst blast duration unobservable at 1 h -> None) ---
    ratios = [g / s for g, s in zip(gust, spd)
              if g is not None and s is not None and s >= 2.0]
    gust_ratio = max(ratios) if ratios else None

    diag = EventDiagnostics(
        event_id=event_id,
        w700_speed_ms=w700_max,
        forcing_sustained=forcing_sustained,
        low_level_lapse_ckm=low_level_lapse,
        max_cape=cape_max,
        wind_shift_deg=wind_shift,
        shift_duration_min=shift_dur,
        gust_to_sustained=gust_ratio,
        # left None on purpose (a point forecast can't see these):
        #   pgf_norm, cross_ridge_flow, critical_level, max_reflectivity_dbz,
        #   lightning_present, blast_duration_min, shift_near_sunrise,
        #   goes_cloud_top_c, plume_collocated_with_fire, local_wind_violent
    )

    # peak surface conditions for the human-facing line
    pk = _peak_surface(spd, gust, wdir, t2m, h["relative_humidity_2m"], h["time"])
    return diag, pk


def _peak_surface(spd, gust, wdir, t2m, rh, times):
    best_i, best_g = None, -1.0
    for i, g in enumerate(gust):
        if g is not None and g > best_g:
            best_g, best_i = g, i
    if best_i is None:
        return {}
    rh_vals = [v for v in rh if v is not None]
    return {
        "time": times[best_i],
        "sustained_mph": round((spd[best_i] or 0) * MS_TO_MPH, 1),
        "gust_mph": round(best_g * MS_TO_MPH, 1),
        "dir_deg": wdir[best_i],
        "temp_c": t2m[best_i],
        "rh_pct": rh[best_i],
        "min_rh_pct": min(rh_vals) if rh_vals else None,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _threat_level(pk: dict) -> str:
    """Fire-weather gate from peak gust + min RH over the window."""
    gust = pk.get("gust_mph")
    rh = pk.get("min_rh_pct")
    if gust is None:
        return "UNKNOWN"
    if rh is not None and gust >= THREAT["critical_gust_mph"] and rh <= THREAT["critical_rh_pct"]:
        return "CRITICAL"
    if rh is not None and gust >= THREAT["elevated_gust_mph"] and rh <= THREAT["elevated_rh_pct"]:
        return "ELEVATED"
    return "BENIGN"


def _headline_mechanism(r):
    """Pick the best-scored mechanism that clears the repo's evidence floor.

    score() = supportive/evaluable rewards sparse evidence, so a 1-indicator
    1.0 can outrank a well-evidenced rival. We therefore choose among only the
    mechanisms whose evidence_fraction >= min_evidence_fraction (0.34) -- the
    same threshold the classifier uses to flag LOW_CONFIDENCE.
    """
    floor = THRESHOLDS["min_evidence_fraction"]
    eligible = [(m, r.scores[m]) for m in r.scores if r.evidence_fraction[m] >= floor]
    if not eligible:
        return None
    return max(eligible, key=lambda kv: kv[1])[0]


def forecast_site(label: str, lat: float, lon: float, tz: str, hours: int) -> dict:
    h = fetch_forecast(lat, lon, tz, hours)
    diag, pk = build_diagnostics(h, label)
    r = classify(diag)

    headline = _headline_mechanism(r)
    threat = _threat_level(pk)
    verdict = WINDNINJA_APPLICABILITY[headline] if headline else "n/a (no well-evidenced mechanism)"

    out = {
        "site": label,
        "lat": lat, "lon": lon,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "window_hours": hours,
        "threat_level": threat,
        "headline_mechanism": headline.value.upper() if headline else "INDETERMINATE",
        "windninja_applicability": verdict,
        "primary_bust_axis": None,
        "evidence_fraction": {m.value: round(f, 2) for m, f in r.evidence_fraction.items()},
        "scores": {m.value: round(s, 2) for m, s in r.scores.items()},
        "peak_surface": pk,
        "drivers": {
            "w700_max_ms": diag.w700_speed_ms,
            "max_cape": diag.max_cape,
            "low_level_lapse_ckm": round(diag.low_level_lapse_ckm, 2) if diag.low_level_lapse_ckm is not None else None,
            "max_wind_shift_deg": diag.wind_shift_deg,
            "max_gust_ratio": round(diag.gust_to_sustained, 2) if diag.gust_to_sustained is not None else None,
        },
        "reasons_for_headline": r.reasons.get(headline, []) if headline else [],
    }
    if headline:
        from mechanism_classifier import PRIMARY_BUST_AXIS
        out["primary_bust_axis"] = PRIMARY_BUST_AXIS[headline]
    return out


_THREAT_MARK = {"CRITICAL": "[!!]", "ELEVATED": "[! ]", "BENIGN": "[  ]", "UNKNOWN": "[ ?]"}


def print_human(o: dict):
    pk = o.get("peak_surface", {})
    mark = _THREAT_MARK.get(o["threat_level"], "[  ]")
    print(f"\n=== {mark} {o['site']} ===")
    print(f"  threat    : {o['threat_level']}")
    print(f"  mechanism : {o['headline_mechanism']}")
    print(f"  WindNinja : {o['windninja_applicability']}")
    if o.get("primary_bust_axis"):
        print(f"  bust axis : {o['primary_bust_axis']}")
    if pk:
        d = pk.get("dir_deg")
        print(f"  peak wind : {pk['sustained_mph']} mph sustained, gust {pk['gust_mph']} mph "
              f"from {d}deg  @ {pk['time']}")
        print(f"  driest    : RH min {pk.get('min_rh_pct')}%  (peak-hour {pk.get('temp_c')}C, RH {pk.get('rh_pct')}%)")
    drv = o["drivers"]
    print(f"  drivers   : 700hPa max {drv['w700_max_ms']} m/s | CAPE {drv['max_cape']} | "
          f"lapse {drv['low_level_lapse_ckm']} C/km | max shift {drv['max_wind_shift_deg']}deg | "
          f"gust ratio {drv['max_gust_ratio']}")
    if o["reasons_for_headline"]:
        print("  fired     : " + "; ".join(o["reasons_for_headline"]))


def main(argv):
    args = list(argv)
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    hours = 24
    if "--hours" in args:
        i = args.index("--hours")
        hours = int(args[i + 1])
        del args[i:i + 2]

    if args:  # a single user-specified location
        lat, lon, label, tz = geocode(" ".join(args))
        targets = [(label, lat, lon, tz)]
    else:     # the full catalogue
        targets = [(name, lat, lon, tz) for name, (lat, lon, tz) in SITES.items()]

    results = []
    for label, lat, lon, tz in targets:
        try:
            results.append(forecast_site(label, lat, lon, tz, hours))
        except Exception as e:  # noqa: BLE001 - keep the batch going
            results.append({"site": label, "error": str(e)})

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        print(f"StormWatch Live -- fire-wind outlook (next {hours} h)")
        print(f"Engine: mechanism_classifier (repo THRESHOLDS) | Data: Open-Meteo surface+700hPa")
        for o in results:
            if "error" in o:
                print(f"\n=== {o['site']} ===\n  ERROR: {o['error']}")
            else:
                print_human(o)
        print("\nNote: point-forecast diagnostics only; high-res terrain (WindNinja) is a separate seam.")
    return results


if __name__ == "__main__":
    main(sys.argv[1:])
