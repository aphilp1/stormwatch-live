#!/usr/bin/env python3
"""
marshall_fire_20211230.py

Wind analysis for the Marshall Fire hindcast — Boulder County, CO
December 30, 2021

Fire ignited ~11:00 AM MST (18:00 UTC) near Marshall Road (Superior/Louisville)
Peak wind gusts reported 100-115 mph in foothills, 80-100 mph in burn area
Destroyed 1,084 structures; ~$2B losses

Data sources:
  700 hPa soundings: GJT (Grand Junction, upwind/west) + DNR (Denver, lee side)
                     12z Dec 30 (pre-event) + 00z Dec 31 (during/post event)
                     IEM RAOB API
  ASOS observations: KBOU, KBJC, KEIK, KDEN — IEM ASOS API
                     Window: 12z Dec 30 – 06z Dec 31 2021
  NWS LSRs:          WFO=BOU, same window
"""

import requests
import math
from datetime import datetime, timezone

# ----------------------------------------------------------------------------─
# Station locations (ASOS near fire area)
# ----------------------------------------------------------------------------─
STATIONS = {
    "Boulder (KBOU)":    {"lat": 40.0376,  "lon": -105.2264},
    "Broomfield (KBJC)": {"lat": 39.9088,  "lon": -105.1166},
    "Erie (KEIK)":       {"lat": 40.0105,  "lon": -105.0505},
    "Denver (KDEN)":     {"lat": 39.8561,  "lon": -104.6737},
}

# Marshall Fire ignition area (Superior, CO)
FIRE_LAT, FIRE_LON = 39.954, -105.168

# ----------------------------------------------------------------------------─
# Helpers
# ----------------------------------------------------------------------------─
def cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(float(deg) / 22.5) % 16]

def knots_to_mph(kt):
    return round(float(kt) * 1.15078, 1)

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371
    d = math.radians
    dlat = d(lat2 - lat1); dlon = d(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def fmt_wind(spd_mph, direction):
    if spd_mph is None or direction is None:
        return "  ---"
    return f"{cardinal(direction):>3}  {spd_mph:5.1f} mph"

# ----------------------------------------------------------------------------─
# 1. Upper-air soundings — GJT (Grand Junction) and DNR (Denver)
#    12z Dec 30 2021 (pre-event, 5 AM MST) + 00z Dec 31 2021 (peak event, 5 PM MST)
# ----------------------------------------------------------------------------─
print()
print("Marshall Fire Wind Analysis  |  December 30, 2021  |  Boulder County, CO")
print("=" * 72)
print()
print("-- UPPER-AIR SOUNDINGS (IEM RAOB) ------------------------------------─")
print()

SOUNDING_REQUESTS = [
    {"airport": "GJT", "ts": "2021-12-30T12:00:00Z", "label": "Grand Junction (GJT) — 12z Dec 30 (5 AM MST, PRE-EVENT)"},
    {"airport": "GJT", "ts": "2021-12-31T00:00:00Z", "label": "Grand Junction (GJT) — 00z Dec 31 (5 PM MST, DURING EVENT)"},
    {"airport": "DNR", "ts": "2021-12-30T12:00:00Z", "label": "Denver (DNR) — 12z Dec 30 (5 AM MST, PRE-EVENT)"},
    {"airport": "DNR", "ts": "2021-12-31T00:00:00Z", "label": "Denver (DNR) — 00z Dec 31 (5 PM MST, DURING EVENT)"},
]

LEVELS = [500.0, 700.0, 850.0]

soundings = {}
for req in SOUNDING_REQUESTS:
    key = f"{req['airport']}_{req['ts'][:13]}"
    print(f"  Fetching {req['label']} ...")
    try:
        url = (f"https://mesonet.agron.iastate.edu/json/raob.json"
               f"?airport={req['airport']}&ts={req['ts']}&fmt=json")
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        profiles = data.get("profiles", [])
        if not profiles:
            print(f"    !! No profile returned")
            continue
        profile = profiles[0]["profile"]
        result = {"label": req["label"], "levels": {}}
        for lvl_hpa in LEVELS:
            lvl = next((l for l in profile if l.get("pres") == lvl_hpa), None)
            if lvl and lvl.get("sknt") is not None and lvl.get("drct") is not None:
                result["levels"][lvl_hpa] = {
                    "speed_mph": knots_to_mph(lvl["sknt"]),
                    "dir":       lvl["drct"],
                    "hght_m":    lvl.get("hght"),
                    "tmpc":      lvl.get("tmpc"),
                }
        soundings[key] = result
        for hpa, d in result["levels"].items():
            print(f"    {hpa:.0f} hPa: {fmt_wind(d['speed_mph'], d['dir'])}  "
                  f"({d['hght_m']} m MSL, {d['tmpc']}°C)")
    except Exception as e:
        print(f"    !! Error: {e}")
    print()

# ----------------------------------------------------------------------------─
# 2. ASOS surface observations — 12z Dec 30 through 06z Dec 31
#    Pull all obs, then extract peak gust and hourly summary
# ----------------------------------------------------------------------------─
print()
print("-- ASOS SURFACE OBSERVATIONS (IEM) ------------------------------------")
print()
print("  Window: 12:00 UTC Dec 30 → 06:00 UTC Dec 31, 2021")
print("  (= 5 AM MST Dec 30 → 11 PM MST Dec 30)")
print()

ASOS_IDS = {
    "KBOU": "Boulder Municipal",
    "KBJC": "Rocky Mtn Metro (Broomfield)",
    "KEIK": "Erie Municipal",
    "KDEN": "Denver International",
}

all_asos = {}

for sid, name in ASOS_IDS.items():
    url = (
        f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
        f"?station={sid}"
        f"&data=all"
        f"&year1=2021&month1=12&day1=30&hour1=12&minute1=0"
        f"&year2=2021&month2=12&day2=31&hour2=6&minute2=0"
        f"&tz=UTC&format=comma&latlon=no&elev=no&report_type=1,3"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split("\n") if not l.startswith("#") and l.strip()]
        # Find header line
        header_idx = next((i for i, l in enumerate(lines) if l.startswith("station")), None)
        if header_idx is None:
            print(f"  {sid} ({name}): no data returned")
            continue
        headers = lines[header_idx].split(",")
        obs_lines = lines[header_idx + 1:]

        obs = []
        for line in obs_lines:
            fields = line.split(",")
            if len(fields) < len(headers):
                continue
            row = dict(zip(headers, fields))
            try:
                gust = float(row.get("gust", "M") or "M") if row.get("gust", "M") not in ("M", "") else None
                wspd = float(row.get("sknt", "M") or "M") if row.get("sknt", "M") not in ("M", "") else None
                wdir = float(row.get("drct", "M") or "M") if row.get("drct", "M") not in ("M", "") else None
                obs.append({
                    "time": row.get("valid", ""),
                    "wspd_kt": wspd,
                    "wdir": wdir,
                    "gust_kt": gust,
                })
            except (ValueError, TypeError):
                continue

        if not obs:
            print(f"  {sid} ({name}): no valid obs parsed")
            continue

        all_asos[sid] = obs

        # Peak gust
        gusts = [(o["time"], o["gust_kt"]) for o in obs if o["gust_kt"] is not None]
        peak = max(gusts, key=lambda x: x[1]) if gusts else None
        peak_str = (f"{knots_to_mph(peak[1]):.0f} mph gust at {peak[0]} UTC"
                    if peak else "no gusts recorded")

        # Peak sustained
        sustn = [(o["time"], o["wspd_kt"], o["wdir"]) for o in obs if o["wspd_kt"] is not None]
        peak_s = max(sustn, key=lambda x: x[1]) if sustn else None
        peak_s_str = (f"{knots_to_mph(peak_s[1]):.0f} mph sustained {cardinal(peak_s[2])} at {peak_s[0]} UTC"
                      if peak_s else "---")

        dist = dist_km(FIRE_LAT, FIRE_LON, STATIONS.get(f"Boulder (KBOU)", {}).get("lat", FIRE_LAT),
                       STATIONS.get(f"Boulder (KBOU)", {}).get("lon", FIRE_LON))

        print(f"  {sid} — {name}")
        print(f"    Peak gust:      {peak_str}")
        print(f"    Peak sustained: {peak_s_str}")
        print(f"    Obs count:      {len(obs)}")
        print()

    except Exception as e:
        print(f"  {sid} ({name}): ERROR — {e}")
        print()

# ----------------------------------------------------------------------------─
# 3. Hourly wind table — KBOU and KBJC during fire window (17z-03z)
# ----------------------------------------------------------------------------─
print()
print("-- HOURLY WIND TABLE — KBOU & KBJC  (17z Dec 30 – 03z Dec 31) --------")
print()
print(f"  {'UTC':>18}  {'KBOU Sustained':>18}  {'KBOU Gust':>12}  {'KBJC Sustained':>18}  {'KBJC Gust':>12}")
print("  " + "-"*86)

def get_hour_obs(obs_list, hour_str):
    """Return obs closest to given hour string (e.g. '2021-12-30 18:00')"""
    matches = [o for o in obs_list if o["time"].startswith(hour_str)]
    return matches[0] if matches else None

FIRE_HOURS = [
    "2021-12-30 17:", "2021-12-30 18:", "2021-12-30 19:",
    "2021-12-30 20:", "2021-12-30 21:", "2021-12-30 22:",
    "2021-12-30 23:", "2021-12-31 00:", "2021-12-31 01:",
    "2021-12-31 02:", "2021-12-31 03:",
]

bou_obs = all_asos.get("KBOU", [])
bjc_obs = all_asos.get("KBJC", [])

for h in FIRE_HOURS:
    # Get best obs for this hour window
    bou_h = [o for o in bou_obs if o["time"].startswith(h)]
    bjc_h = [o for o in bjc_obs if o["time"].startswith(h)]

    def peak_in_hour(obs_list):
        gusts = [o for o in obs_list if o["gust_kt"] is not None]
        sustn = [o for o in obs_list if o["wspd_kt"] is not None]
        pg = max(gusts, key=lambda x: x["gust_kt"])["gust_kt"] if gusts else None
        if sustn:
            ps = max(sustn, key=lambda x: x["wspd_kt"])
            return ps["wspd_kt"], ps["wdir"], pg
        return None, None, pg

    bs, bd, bg = peak_in_hour(bou_h)
    js, jd, jg = peak_in_hour(bjc_h)

    label = h[5:16]
    mst = f"({int(h[8:10])-7 if int(h[8:10])>=7 else int(h[8:10])+17:02d}:xx MST)"

    def fmt(spd, dr, gust):
        s = f"{cardinal(dr)} {knots_to_mph(spd):.0f}mph" if spd is not None else "---"
        g = f"{knots_to_mph(gust):.0f}mph" if gust is not None else "---"
        return f"{s:>18}", f"{g:>12}"

    bs_s, bg_s = fmt(bs, bd, bg)
    js_s, jg_s = fmt(js, jd, jg)
    print(f"  {label} {mst}  {bs_s}  {bg_s}  {js_s}  {jg_s}")

# ----------------------------------------------------------------------------─
# 4. NWS Local Storm Reports — WFO BOU
# ----------------------------------------------------------------------------─
print()
print()
print("-- NWS LOCAL STORM REPORTS (WFO=BOU) ----------------------------------")
print("  Window: 15:00 UTC Dec 30 → 06:00 UTC Dec 31 (= 8 AM–11 PM MST)")
print()

try:
    lsr_url = (
        "https://mesonet.agron.iastate.edu/geojson/lsr.php"
        "?wfo=BOU"
        "&sts=2021-12-30T15:00:00Z"
        "&ets=2021-12-31T06:00:00Z"
        "&fmt=json"
    )
    r = requests.get(lsr_url, timeout=20)
    r.raise_for_status()
    lsr_data = r.json()
    features = lsr_data.get("features", [])

    wind_lsrs = [f for f in features
                 if f["properties"].get("type", "") in ("G", "N", "H", "W", "D", "F")]

    print(f"  Total LSRs returned: {len(features)}")
    print(f"  Wind-related LSRs:   {len(wind_lsrs)}")
    print()

    if wind_lsrs:
        # Sort by magnitude descending
        def lsr_mag(f):
            try:
                return float(f["properties"].get("magnitude", 0) or 0)
            except:
                return 0

        wind_lsrs.sort(key=lsr_mag, reverse=True)

        print(f"  {'UTC Time':>18}  {'Type':>5}  {'Magnitude':>10}  {'Location'}")
        print("  " + "-"*72)
        for f in wind_lsrs[:25]:
            p = f["properties"]
            mag = p.get("magnitude", "")
            mag_str = f"{mag} mph" if mag else "---"
            typ = p.get("type", "?")
            valid = p.get("valid", "")[:16]
            city = p.get("city", "?")
            county = p.get("county", "")
            dist_from_fire = ""
            coords = f.get("geometry", {}).get("coordinates", [])
            if coords and len(coords) == 2:
                d = dist_km(FIRE_LAT, FIRE_LON, coords[1], coords[0])
                dist_from_fire = f"  ({d:.1f} km from fire)"
            print(f"  {valid:>18}  {typ:>5}  {mag_str:>10}  {city}, {county}{dist_from_fire}")
    else:
        print("  No wind LSRs found — try expanding time window or check WFO")
except Exception as e:
    print(f"  ERROR fetching LSRs: {e}")

# ----------------------------------------------------------------------------─
# 5. Open-Meteo ERA5 surface winds at fire-area locations
# ----------------------------------------------------------------------------─
print()
print()
print("-- ERA5 SURFACE WINDS (Open-Meteo, 31km) ------------------------------")
print("  Synoptic context only — cannot resolve terrain acceleration")
print()

ERA5_POINTS = {
    "Superior/fire area":  {"lat": 39.954,  "lon": -105.168},
    "Boulder foothills":   {"lat": 40.050,  "lon": -105.300},
    "Jefferson Co plains": {"lat": 39.850,  "lon": -105.050},
}

for name, pt in ERA5_POINTS.items():
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={pt['lat']}&longitude={pt['lon']}"
        f"&start_date=2021-12-30&end_date=2021-12-31"
        f"&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        f"&wind_speed_unit=mph&timezone=UTC"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        d = r.json()
        times  = d["hourly"]["time"]
        speeds = d["hourly"]["wind_speed_10m"]
        dirs   = d["hourly"]["wind_direction_10m"]
        gusts  = d["hourly"]["wind_gusts_10m"]

        print(f"  {name}  ({pt['lat']}°N, {pt['lon']}°W)")
        print(f"  {'UTC':>5}  {'Wind':>16}  {'Gust':>8}")
        for i, t in enumerate(times):
            # Show 15z-02z window
            hour = int(t[11:13])
            if not (15 <= hour <= 23 or hour <= 3):
                continue
            spd = speeds[i]; dr = dirs[i]; gst = gusts[i]
            spd_s = f"{cardinal(dr)} {spd:.0f}mph" if spd is not None else "---"
            gst_s = f"{gst:.0f}mph" if gst is not None else "---"
            mst_h = (hour - 7) % 24
            print(f"  {hour:02d}z ({mst_h:02d} MST)  {spd_s:>16}  {gst_s:>8}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR — {e}")
        print()

# ----------------------------------------------------------------------------─
# 6. WindNinja initialization summary
# ----------------------------------------------------------------------------─
print()
print("-- WINDNINJA INITIALIZATION (from soundings above) --------------------")
print()
print("  Use 700 hPa GJT 00z Dec 31 (peak event, upwind station)")
print("  Confirm values from sounding output above.")
print()
print("  Location center: Superior/Louisville area")
print("  Approx lat/lon:  39.95°N, 105.15°W")
print("  Target stations for WN comparison:")
for sid, info in STATIONS.items():
    d = dist_km(FIRE_LAT, FIRE_LON, info["lat"], info["lon"])
    print(f"    {sid:28s}  {info['lat']}°N, {info['lon']}°W  (~{d:.0f} km from ignition)")
print()
print("Done.")
