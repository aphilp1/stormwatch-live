#!/usr/bin/env python3
"""
hrrr_missoula_20240724.py

Wind analysis for the July 24, 2024 Missoula derecho hindcast.
Valid: 21:00 MDT July 24 = 03:00 UTC July 25, 2024

Data sources:
  700 hPa: OTX (Spokane) radiosonde, 00 UTC July 25, 2024 — IEM RAOB API
           Nearest upper-air station to Missoula (~150 mi W). Real observation.
           00 UTC = 18:00 MDT July 24 (3 hrs before event peak — pre-event free atmosphere)
  10m:     ERA5 reanalysis via Open-Meteo archive (synoptic context only, 31 km)

RAWS observations are the validation target — pull separately from WRCC or Synoptic.
"""

import requests
import math

# ── Station locations ─────────────────────────────────────────────────────────
STATIONS = {
    "Point Six":      {"lat": 46.876, "lon": -114.082},
    "Blue Mountain":  {"lat": 46.832, "lon": -114.216},
    "Lolo Portable":  {"lat": 46.749, "lon": -114.066},
    "Missoula (ref)": {"lat": 46.916, "lon": -114.090},
}

VALID_DATE   = "2024-07-25"
VALID_HOUR_UTC = 3          # 03:00 UTC = 21:00 MDT July 24

# ── Helpers ───────────────────────────────────────────────────────────────────
def cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]

def knots_to_mph(kt):
    return kt * 1.15078

# ── 700 hPa: OTX (Spokane) radiosonde, 00 UTC July 25 ────────────────────────
print()
print("Wind Analysis — Missoula Derecho  |  21:00 MDT July 24, 2024")
print("=" * 68)
print()
print("Fetching OTX (Spokane) sounding, 00 UTC July 25 (= 18:00 MDT July 24)...")

sounding_700 = {"speed_mph": None, "dir": None, "source": "OTX 00z"}
try:
    r = requests.get(
        "https://mesonet.agron.iastate.edu/json/raob.json"
        "?airport=OTX&ts=2024-07-25T00:00:00Z&fmt=json",
        timeout=15
    )
    r.raise_for_status()
    profile = r.json()["profiles"][0]["profile"]

    # Find the mandatory 700 hPa level
    lvl = next((l for l in profile if l.get("pres") == 700.0), None)

    if lvl and lvl.get("sknt") is not None and lvl.get("drct") is not None:
        sounding_700["speed_mph"] = knots_to_mph(lvl["sknt"])
        sounding_700["dir"]       = lvl["drct"]
        sounding_700["height_m"]  = lvl.get("hght")
        sounding_700["temp_c"]    = lvl.get("tmpc")
        print(f"  700 hPa: {lvl['sknt']} kt  ({sounding_700['speed_mph']:.1f} mph)  "
              f"from {lvl['drct']}°  ({cardinal(lvl['drct'])})  "
              f"at {lvl.get('hght', '?')} m  ({lvl.get('tmpc', '?')}°C)")
    else:
        print("  700 hPa mandatory level missing — check sounding availability")
except Exception as e:
    print(f"  FAILED: {e}")

# ── Also check Great Falls (TFX) for comparison — east of Divide ──────────────
print()
print("Fetching TFX (Great Falls) sounding, 00 UTC July 25 (east of Divide)...")
tfx_700 = {"speed_mph": None, "dir": None}
try:
    r2 = requests.get(
        "https://mesonet.agron.iastate.edu/json/raob.json"
        "?airport=TFX&ts=2024-07-25T00:00:00Z&fmt=json",
        timeout=15
    )
    r2.raise_for_status()
    profile2 = r2.json()["profiles"][0]["profile"]
    lvl2 = next((l for l in profile2 if l.get("pres") == 700.0), None)
    if lvl2 and lvl2.get("sknt") is not None:
        tfx_700["speed_mph"] = knots_to_mph(lvl2["sknt"])
        tfx_700["dir"]       = lvl2["drct"]
        print(f"  700 hPa: {lvl2['sknt']} kt  ({tfx_700['speed_mph']:.1f} mph)  "
              f"from {lvl2['drct']}°  ({cardinal(lvl2['drct'])})")
except Exception as e:
    print(f"  FAILED: {e}")

# ── 10m surface winds: Open-Meteo ERA5 per station ───────────────────────────
print()
print("Fetching 10m surface winds (ERA5) for each station...")
surface = {}
for name, loc in STATIONS.items():
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={loc['lat']}&longitude={loc['lon']}"
            f"&start_date={VALID_DATE}&end_date={VALID_DATE}"
            "&hourly=wind_speed_10m,wind_direction_10m"
            "&wind_speed_unit=mph&timezone=UTC",
            timeout=15
        )
        r.raise_for_status()
        h = r.json()["hourly"]
        surface[name] = {
            "s10": h["wind_speed_10m"][VALID_HOUR_UTC],
            "d10": h["wind_direction_10m"][VALID_HOUR_UTC],
        }
        print(f"  {name:<20}  {surface[name]['s10']:.1f} mph  "
              f"from {surface[name]['d10']}°  ({cardinal(surface[name]['d10'])})")
    except Exception as e:
        print(f"  {name}: FAILED: {e}")
        surface[name] = {"s10": None, "d10": None}

# ── Summary table ─────────────────────────────────────────────────────────────
print()
print("─" * 68)
print(f"{'Station':<20} {'── ERA5 10m ──':^24} {'── 700 hPa BC ──':^22}")
print(f"{'':20} {'mph':>6} {'dir°':>6} {'card':>7}   {'mph':>6} {'dir°':>6} {'card':>7}")
print("─" * 68)

wn_spd = sounding_700.get("speed_mph")
wn_dir = sounding_700.get("dir")

for name, v in surface.items():
    s10 = v["s10"] or 0.0
    d10 = v["d10"] or 0.0
    wn_s = f"{wn_spd:6.1f}" if wn_spd else "   N/A"
    wn_d = f"{wn_dir:6.0f}" if wn_dir else "   N/A"
    wn_c = cardinal(wn_dir) if wn_dir else "N/A"
    print(f"{name:<20} {s10:>6.1f} {d10:>6.0f} {cardinal(d10):>7}   "
          f"{wn_s} {wn_d} {wn_c:>7}")

print("─" * 68)

# ── WindNinja initialization block ────────────────────────────────────────────
print()
print("━" * 68)
print("WINDNINJA INITIALIZATION  (OTX 700 hPa — real sounding)")
if wn_spd and wn_dir:
    print(f"  wind_speed      = {wn_spd:.0f} mph")
    print(f"  wind_direction  = {wn_dir:.0f}°  (coming FROM {cardinal(wn_dir)})")
    print(f"  Source          : OTX radiosonde 00z July 25, 2024")
    print(f"  700 hPa height  : {sounding_700.get('height_m', '?')} m  "
          f"({sounding_700.get('temp_c', '?')}°C)")
else:
    print("  No 700 hPa data available — check sounding.")

print()
print("RAWS VALIDATION TARGETS  (pull observed winds for 21:00 MDT July 24)")
for name, loc in list(STATIONS.items())[:3]:
    print(f"  {name:<20}  {loc['lat']}°N  {loc['lon']}°W")
print("  Source: WRCC (wrcc.dri.edu) or Synoptic Data API")
print("━" * 68)
print()
print("NOTE: ERA5 10m values are synoptic context only — 31 km resolution,")
print("      no terrain effects. WindNinja downscales 700 hPa BC to terrain-")
print("      resolved 10m winds. RAWS obs are the validation target.")
if tfx_700.get("speed_mph"):
    print(f"\nTFX (Great Falls, east of Divide): {tfx_700['speed_mph']:.1f} mph "
          f"from {tfx_700['dir']}° ({cardinal(tfx_700['dir'])}) at 700 hPa")
    print("  Comparison shows cross-barrier wind contrast if significant.")
