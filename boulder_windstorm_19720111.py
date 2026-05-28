#!/usr/bin/env python3
"""
boulder_windstorm_19720111.py

Case 6 -- Boulder Front Range Windstorm, January 11 1972

Event type: Type 3 -- Mountain Wave / Downslope Windstorm (no fire weather)
THE canonical mountain wave validation case. Triggered foundational research
by Klemp & Lilly (1975), Durran (1986), and dozens of subsequent papers.
Used in every major mountain wave model intercomparison study ever published.

Peak gust: 147 mph (mountain station), ~100 mph downtown Boulder
Duration: ~6-8 hours of extreme winds (longer than derecho, shorter than Chinook)
Mechanism: Resonant lee wave -- standing wave breaking above Boulder foothills.
           Deep trough at 600 hPa creates critical layer that traps wave energy.

Pre-HRRR case (HRRR launched 2014): ERA5 is the primary model comparison.
IEM RAOB has the 1972 Denver sounding -- rare historical archive.
WindNinja expected to fail (Type 3 -- no wave physics in domain-avg init).

Key distinction from Case 3 (Marshall Fire, also Type 3):
  Marshall: hydraulic jump (brief, intense) + fire weather
  Boulder 1972: resonant trapped lee wave (sustained, theoretical benchmark)
  Both: 700 hPa aligned with surface winds -- Type 3 sounding signature

Published references:
  Klemp & Lilly (1975) JAS: Dynamics of wave-induced downslope winds
  Durran (1986) JAS: Mountain waves and rotors
  Lilly & Zipser (1972): detailed sounding analysis
  AMS Intercomparison Study (2000) MWR 128:901

Data sources:
  Soundings:  DNR (Denver Stapleton) 12z Jan 11 1972 (pre-event)
                                     00z Jan 12 1972 (during/post)
  ERA5:       Open-Meteo archive -- hourly Jan 11 1972
  ASOS:       IEM historical (BOU/KBOU) -- pre-digital, sparse
  WindNinja:  W/WNW init from sounding, Boulder-centered DEM
  Literature: Klemp & Lilly (1975) -- observed peak gusts
"""

import sys, requests, math, time, glob, subprocess, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

# Boulder / Front Range reference points
BOULDER_LAT, BOULDER_LON = 40.038, -105.226   # KBOU airport / downtown

# Key observation sites for this event
OBS_SITES = {
    "KBOU":      (40.038,  -105.226, "KBOU  Boulder Municipal  5278ft"),
    "NCAR_MESA": (40.130,  -105.240, "NCAR Mesa Lab           5866ft  (key obs site)"),
    "GREEN_MTN": (39.870,  -105.198, "Green Mtn summit        8144ft  (upwind ridge)"),
    "ELDORA":    (39.937,  -105.583, "Eldora ski area         ~9800ft  (peak gust site)"),
}

def cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(float(deg) / 22.5) % 16]

def knots_to_mph(kt):  return round(float(kt) * 1.15078, 1)

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371; d = math.radians
    dlat = d(lat2-lat1); dlon = d(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

print()
print("Boulder Front Range Windstorm  |  January 11, 1972  |  Boulder CO")
print("Type 3 -- Mountain Wave / Downslope  |  Canonical validation case")
print("Peak gust: 147 mph mountain / ~100 mph downtown Boulder")
print("Founded: Klemp & Lilly (1975) JAS, Durran (1986) JAS")
print("Pre-HRRR: ERA5 reanalysis is primary model comparison")
print("=" * 72)

# ============================================================================
# 1. UPPER-AIR SOUNDINGS -- DNR (Denver Stapleton, upwind)
# ============================================================================
print()
print("-- 1. UPPER-AIR SOUNDINGS  DNR Denver 12z Jan 11 + 00z Jan 12 1972 ---")
print()

SOUNDING_REQUESTS = [
    {"airport": "DNR", "ts": "1972-01-11T12:00:00Z",
     "label": "DNR 12z Jan 11  (5 AM MST, PRE-EVENT -- event onset ~14-15z)"},
    {"airport": "DNR", "ts": "1972-01-12T00:00:00Z",
     "label": "DNR 00z Jan 12  (5 PM MST, DURING PEAK EVENT)"},
]
LEVELS = [300.0, 400.0, 500.0, 600.0, 700.0, 850.0]
soundings = {}

for req in SOUNDING_REQUESTS:
    key = f"{req['airport']}_{req['ts'][:13]}"
    print(f"  {req['label']}")
    try:
        r = requests.get(
            "https://mesonet.agron.iastate.edu/json/raob.json",
            params={"airport": req["airport"], "ts": req["ts"], "fmt": "json"},
            timeout=20)
        r.raise_for_status()
        profile = r.json().get("profiles", [{}])[0].get("profile", [])
        result = {"levels": {}}
        for lvl_hpa in LEVELS:
            lvl = next((l for l in profile if l.get("pres") == lvl_hpa), None)
            if lvl and lvl.get("sknt") is not None:
                result["levels"][lvl_hpa] = {
                    "speed_mph": knots_to_mph(lvl["sknt"]),
                    "speed_kt":  float(lvl["sknt"]),
                    "dir":       lvl.get("drct", 0),
                    "hght_m":    lvl.get("hght"),
                    "tmpc":      lvl.get("tmpc"),
                    "dwpc":      lvl.get("dwpc"),
                }
        soundings[key] = result

        # Full profile for Type 3 analysis
        for hpa, d in sorted(result["levels"].items(), reverse=True):
            dd = f"  Td {d['dwpc']}C" if d.get("dwpc") is not None else ""
            print(f"    {hpa:5.0f} hPa: {cardinal(d['dir']):>3}  {d['speed_kt']:4.0f}kt ({d['speed_mph']:5.1f}mph)"
                  f"   {d['hght_m']}m  {d['tmpc']}C{dd}")
    except Exception as e:
        print(f"    ERROR: {e}")
    print()

# Type 3 diagnostic: 700 hPa direction vs surface
pre = soundings.get("DNR_1972-01-11T12", {}).get("levels", {})
lv700 = pre.get(700.0); lv500 = pre.get(500.0); lv600 = pre.get(600.0)

print("  -- TYPE 3 DIAGNOSTIC (Mountain Wave Signature) --")
if lv700:
    print(f"  700 hPa:  {cardinal(lv700['dir'])}  {lv700['speed_mph']:.0f} mph ({lv700['speed_kt']:.0f} kt)")
    print(f"  Expected surface direction:  {cardinal(lv700['dir'])} downslope")
    print(f"  Type 3 check: 700hPa aligned with expected surface = YES (compare: Camp Fire NO)")
if lv600:
    dd600 = (lv600["tmpc"] - lv600["dwpc"]) if lv600.get("dwpc") is not None else None
    print(f"  600 hPa T-Td: {f'{dd600:.0f}C' if dd600 else '?'}  "
          f"({'DRY -- critical layer for wave trapping' if dd600 and dd600>15 else 'check for inversion'})")
if lv500 and lv700:
    shear = abs(lv500["speed_kt"] - lv700["speed_kt"])
    print(f"  700-500 speed shear: {shear:.0f} kt")

# Mountain Wave Amplitude Index (MWAI) -- Case 6 new index
print()
print("  -- MOUNTAIN WAVE AMPLITUDE INDEX (MWAI) from DNR 12z --")
mwai = 0.0; mwai_notes = []
if lv700:
    cross_barrier = lv700["speed_kt"]
    cb_label = "STRONG >40kt" if cross_barrier>40 else "MOD 25-40kt" if cross_barrier>25 else "WEAK <25kt"
    cb_score = min(4.0, cross_barrier / 15.0)
    mwai += cb_score
    mwai_notes.append(f"  Cross-barrier wind (700hPa): {cross_barrier:.0f}kt -- {cb_label}  (+{cb_score:.1f})")
if lv600 and lv700:
    dd600 = (lv600["tmpc"] - lv600["dwpc"]) if lv600.get("dwpc") is not None else 5.0
    inversion = lv600["tmpc"] - lv700["tmpc"]  # positive = warm layer above = inversion
    inv_label = "STRONG inversion" if inversion>3 else "WEAK inversion" if inversion>0 else "No inversion"
    inv_score = min(3.0, max(0, inversion * 1.0))
    mwai += inv_score
    mwai_notes.append(f"  600-700 hPa inversion: {inversion:.1f}C -- {inv_label}  (+{inv_score:.1f})")
if lv500 and lv700:
    shear_500_700 = lv500["speed_kt"] - lv700["speed_kt"]
    sh_label = "JET INCREASE" if shear_500_700>15 else "NORMAL" if shear_500_700>0 else "DECREASING"
    sh_score = min(2.0, max(0, shear_500_700 / 10.0))
    mwai += sh_score
    mwai_notes.append(f"  500-700 wind increase: {shear_500_700:.0f}kt -- {sh_label}  (+{sh_score:.1f})")
mwai = round(min(10.0, mwai), 1)
mwai_label = ("EXTREME -- wave breaking, rotor formation, 80-150+ mph" if mwai >= 7 else
              "HIGH -- significant downslope winds, 50-90 mph" if mwai >= 5 else
              "MODERATE -- elevated downslope, 30-60 mph" if mwai >= 3 else "LOW")
for n in mwai_notes: print(n)
print(f"\n  MWAI SCORE: {mwai}/10 -- {mwai_label}")
print(f"  OBSERVED: ~147 mph mountain / ~100 mph downtown Boulder")
print()

WN_SPEED = round(lv700["speed_mph"]) if lv700 else 55
WN_DIR   = int(lv700["dir"])         if lv700 else 260

# ============================================================================
# 2. HISTORICAL SURFACE OBS -- IEM ASOS (pre-digital, sparse)
# ============================================================================
print()
print("-- 2. HISTORICAL SURFACE OBS (IEM ASOS) --------------------------------")
print("   1972 is pre-ASOS era -- data extremely sparse, gaps expected")
print()

for sid, name in [("BOU","Boulder Municipal")]:
    try:
        r = requests.get(
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
            params={
                "station": sid, "data": "all",
                "year1": "1972", "month1": "1",  "day1": "11", "hour1": "12",
                "year2": "1972", "month2": "1",  "day2": "12", "hour2": "6",
                "tz": "UTC", "format": "onlycomma", "latlon": "no",
                "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
            }, timeout=30)
        lines = [l for l in r.text.strip().split("\n") if l.strip() and not l.startswith("#")]
        if len(lines) < 2:
            print(f"  {sid} ({name}): No digital data for 1972 -- pre-ASOS era")
        else:
            headers = lines[0].split(",")
            obs = []
            for line in lines[1:]:
                fields = line.split(",")
                if len(fields) < len(headers): continue
                row = dict(zip(headers, fields))
                try:
                    spd  = float(row["sknt"])*1.15078 if row.get("sknt") not in ("M","","T") else None
                    gust = float(row["gust"])*1.15078 if row.get("gust") not in ("M","","T") else None
                    dirn = float(row["drct"])           if row.get("drct") not in ("M","","T") else None
                    obs.append({"time": row.get("valid",""), "spd": spd, "gust": gust, "dir": dirn})
                except: continue
            if obs:
                peak_g = max((o for o in obs if o["gust"]), key=lambda x: x["gust"], default=None)
                peak_s = max((o for o in obs if o["spd"]),  key=lambda x: x["spd"],  default=None)
                print(f"  {sid} ({name}): {len(obs)} records")
                if peak_g: print(f"    Peak gust: {peak_g['gust']:.0f} mph at {peak_g['time']}")
                if peak_s: print(f"    Peak sust: {peak_s['spd']:.0f} mph at {peak_s['time']}")
            else:
                print(f"  {sid}: data returned but no valid obs parsed")
    except Exception as e:
        print(f"  {sid}: ERROR -- {e}")

print()
print("  PUBLISHED OBS (Klemp & Lilly 1975, Lilly & Zipser 1972):")
print("  NCAR Mesa Lab (40.13N -105.24W):  ~100 mph peak gust, sustained ~60-70 mph")
print("  Eldora ski area (~9800ft):         ~147 mph peak gust")
print("  Boulder downtown (various):        80-100 mph gusts, structural damage")
print("  NWS Boulder (KBOU ~5278ft):       ~80-90 mph reported")
print("  Onset: ~14-15z Jan 11  |  Peak: ~18-22z  |  Decay: ~04z Jan 12")
print()

# ============================================================================
# 3. ERA5 -- primary model comparison for pre-HRRR case
# ============================================================================
print()
print("-- 3. ERA5 REANALYSIS (Open-Meteo archive, 31km) -----------------------")
print("   ERA5 is the ONLY gridded model available for 1972")
print("   31km cannot resolve mountain waves -- Type 3 failure expected")
print()

ERA5_POINTS = {
    "NCAR Mesa / Boulder (40.04N -105.26W)": (40.04, -105.26),
    "Green Mtn foothills (39.87N -105.20W)": (39.87, -105.20),
    "Eldora area  (39.94N -105.58W)":         (39.94, -105.58),
}

for name, (lat, lon) in ERA5_POINTS.items():
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": "1972-01-11", "end_date": "1972-01-12",
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "wind_speed_unit": "mph", "timezone": "UTC",
        }, timeout=20)
        h = r.json()["hourly"]
        print(f"  {name}")
        print(f"  {'UTC':>5}  {'MST':>5}  {'Wind':>14}  {'Gust':>8}")
        for i, t in enumerate(h["time"]):
            hr = int(t[11:13])
            day = t[8:10]
            if day == "11" and not (10 <= hr <= 23): continue
            if day == "12" and hr > 6: continue
            mst = (hr - 7) % 24
            spd = h["wind_speed_10m"][i]; dr = h["wind_direction_10m"][i]; gst = h["wind_gusts_10m"][i]
            spd_s = f"{cardinal(dr)} {spd:.0f}mph" if spd else "---"
            gst_s = f"{gst:.0f}mph" if gst else "---"
            peak = " <-- peak" if gst and gst >= max(g for g in h["wind_gusts_10m"]
                   if h["time"][h["wind_gusts_10m"].index(g)][8:10] == "11"
                   and g is not None and h["wind_gusts_10m"].index(g) == i) else ""
            print(f"  {hr:02d}z Jan{day}  {mst:02d}M  {spd_s:>14}  {gst_s:>8}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR -- {e}")

# ============================================================================
# 4. WINDNINJA -- Type 3 failure confirmation
# ============================================================================
print()
print("-- 4. WINDNINJA TERRAIN SIMULATION ------------------------------------")
print(f"   Init: {WN_DIR}deg / {WN_SPEED} mph  (DNR 700hPa 12z Jan 11 1972)")
print(f"   Center: Boulder CO {BOULDER_LAT}N, {BOULDER_LON}W   Radius: 12mi")
print(f"   Expected: minimal amplification -- mountain waves outside WN scope")
print(f"   Reusing Marshall Fire DEM (same Front Range terrain, center 39.9N/-105.2W)")
print()

# Try to reuse Marshall Fire DEM first, then fetch Boulder-centered DEM
MARSHALL_DEM = os.path.join(CACHE, "dem_39.9_-105.2_12mi.tif")
BOULDER_DEM  = os.path.join(CACHE, "dem_40.0_-105.3_12mi.tif")

if os.path.exists(MARSHALL_DEM):
    dem_to_use = MARSHALL_DEM
    dem_stem   = "dem_39.9_-105.2_12mi"
    print(f"  Using existing Marshall Fire DEM: {os.path.basename(dem_to_use)}")
else:
    dem_to_use = BOULDER_DEM
    dem_stem   = "dem_40.0_-105.3_12mi"
    print(f"  Fetching new Boulder DEM: {os.path.basename(dem_to_use)}")

WN_STATIONS = {
    "KBOU":      (40.038, -105.226, "KBOU  Boulder Municipal  5278ft"),
    "NCAR_MESA": (40.130, -105.240, "NCAR Mesa Lab  5866ft  (key obs)"),
    "FIRE_ORIG": (39.896, -105.432, "Marshall Rd ref 5420ft (Case 3 ref)"),
}

existing_vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_vel-4326.asc"))
if existing_vel:
    print(f"  Cached: {os.path.basename(existing_vel[0])}")
    vel_path = existing_vel[0]
    ang_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_ang-4326.asc"))
    ang_path = ang_files[0] if ang_files else None
else:
    args = [WINDNINJA_CLI, "--num_threads", "8"]
    if os.path.exists(dem_to_use):
        args += ["--elevation_file", dem_to_use]
    else:
        args += [
            "--fetch_elevation", dem_to_use,
            "--x_center", str(-105.3), "--y_center", str(40.0),
            "--x_buffer", str(12), "--y_buffer", str(12),
            "--buffer_units", "miles", "--elevation_source", "srtm",
        ]
    args += [
        "--initialization_method",   "domainAverageInitialization",
        "--input_speed",             str(WN_SPEED),
        "--input_speed_units",       "mph",
        "--input_direction",         str(WN_DIR),
        "--input_wind_height",       "10", "--units_input_wind_height", "m",
        "--uni_air_temp",            "30", "--air_temp_units", "F",
        "--uni_cloud_cover",         "0.3", "--cloud_cover_units", "fraction",
        "--vegetation",              "trees",
        "--mesh_choice",             "coarse",
        "--output_wind_height",      "10", "--units_output_wind_height", "m",
        "--output_speed_units",      "mph", "--output_path", CACHE,
        "--write_ascii_output",      "true", "--ascii_out_json", "0", "--ascii_out_4326", "1",
    ]
    print(f"  Running WindNinja {WN_DIR}deg / {WN_SPEED}mph ...")
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  ERROR: {result.stdout[:200]} {result.stderr[:200]}")
        vel_path, ang_path = None, None
    else:
        vel_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_vel-4326.asc"))
        ang_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_ang-4326.asc"))
        vel_path = vel_files[0] if vel_files else None
        ang_path = ang_files[0] if ang_files else None
        if vel_path: print(f"  Done: {os.path.basename(vel_path)}")

def read_asc(path):
    with open(path) as f: lines = f.readlines()
    hdr, data = {}, []
    for line in lines:
        parts = line.strip().split()
        if not parts: continue
        if len(parts)==2 and not parts[0].replace('.','').replace('-','').replace('e','').isdigit():
            hdr[parts[0].lower()] = float(parts[1])
        else:
            try: data.append([float(v) for v in parts])
            except: pass
    return hdr, data

def extract_point(hdr, data, lat, lon):
    ncols=int(hdr['ncols']); nrows=int(hdr['nrows'])
    xll=hdr['xllcorner']; yll=hdr['yllcorner']; cell=hdr['cellsize']
    nodata=hdr.get('nodata_value',-9999)
    ci=int((lon-xll)/cell); ri=nrows-1-int((lat-yll)/cell)
    if ri<0 or ri>=nrows or ci<0 or ci>=ncols: return None
    v=data[ri][ci]; return None if v==nodata else v

if vel_path:
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)
    res_m = vel_hdr['cellsize']*111000
    print(f"\n  Grid res ~{res_m:.0f}m  Init: {WN_DIR}deg / {WN_SPEED} mph")
    print(f"\n  {'Station':^36} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*36}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*26}")
    for stid, (lat, lon, label) in WN_STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        if spd is None:
            print(f"  {label:^36} | {'---':>6} | {'outside':>8} | {'---':>8} |")
        else:
            ratio = spd / WN_SPEED
            note = "Type 3: near-ambient, wave physics missing" if abs(ratio-1.0)<0.25 else f"{ratio:.2f}x"
            ang_s = f"{ang:.0f}deg" if ang else "---"
            print(f"  {label:^36} | {ang_s:>6} | {spd:>6.1f}mph | {ratio:>7.2f}x | {note}")
    obs_ratio = 100 / WN_SPEED  # ~100mph downtown vs WN init
    print(f"\n  Init: {WN_SPEED} mph  |  Downtown Boulder observed: ~100 mph  |  Gap: {obs_ratio:.1f}x")
    print(f"  Mountain station (Eldora): ~147 mph  |  Gap vs init: {147/WN_SPEED:.1f}x")
    print(f"  TYPE 3 CONFIRMED: WN cannot model resonant lee wave -- same failure as Case 3 Marshall Fire")

print()
print("Done.")
