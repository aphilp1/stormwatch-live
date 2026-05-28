#!/usr/bin/env python3
"""
marshall_fire_20211230.py

Case 3 — Marshall Fire hindcast, Boulder County CO, December 30 2021

Event type: Type 3 — Mountain Wave / Chinook Downslope (fire weather)
Fire ignited ~11:00 AM MST (18:00 UTC) near Marshall Road (Superior/Louisville)
Peak gusts 100-115 mph in foothills, 80-100 mph in burn area
Destroyed 1,084 structures; ~$2B losses; 2 fatalities

Data sources:
  700 hPa soundings: GJT (Grand Junction, upwind)
                     12z Dec 30 (pre-event, 5 AM MST)
                     00z Dec 31 (during event, 5 PM MST)
  ASOS: BOU, BJC, EIK, DEN — IEM API
  NWS LSRs: WFO=BOU
  ERA5: Open-Meteo archive
"""

import sys, requests, math, time, glob, subprocess, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

FIRE_LAT, FIRE_LON = 39.954, -105.168   # Marshall Road ignition, Superior CO

# ASOS stations (IEM format: no K prefix)
ASOS_STATIONS = {
    "BOU":  ("Boulder Municipal",         40.0376,  -105.2264),
    "BJC":  ("Rocky Mtn Metro Broomfield",39.9088,  -105.1166),
    "EIK":  ("Erie Municipal",            40.0105,  -105.0505),
    "DEN":  ("Denver International",      39.8561,  -104.6737),
}

def cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(float(deg) / 22.5) % 16]

def knots_to_mph(kt):
    return round(float(kt) * 1.15078, 1)

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371; d = math.radians
    dlat = d(lat2-lat1); dlon = d(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

print()
print("Marshall Fire Wind Analysis  |  December 30, 2021  |  Boulder County, CO")
print("Type 3 -- Mountain Wave / Chinook Downslope  |  FIRE WEATHER CASE")
print("=" * 72)

# ============================================================================
# 1. UPPER-AIR SOUNDINGS -- GJT (Grand Junction, upwind/west)
# ============================================================================
print()
print("-- 1. UPPER-AIR SOUNDINGS (IEM RAOB) ----------------------------------")
print()

SOUNDING_REQUESTS = [
    {"airport": "GJT", "ts": "2021-12-30T12:00:00Z", "label": "GJT 12z Dec 30  (5 AM MST, PRE-EVENT)"},
    {"airport": "GJT", "ts": "2021-12-31T00:00:00Z", "label": "GJT 00z Dec 31  (5 PM MST, PEAK EVENT)"},
]
LEVELS = [500.0, 700.0, 850.0]
soundings = {}

for req in SOUNDING_REQUESTS:
    key = f"{req['airport']}_{req['ts'][:13]}"
    print(f"  {req['label']}")
    try:
        r = requests.get(
            f"https://mesonet.agron.iastate.edu/json/raob.json"
            f"?airport={req['airport']}&ts={req['ts']}&fmt=json",
            timeout=20)
        r.raise_for_status()
        profile = r.json().get("profiles", [{}])[0].get("profile", [])
        result = {"levels": {}}
        for lvl_hpa in LEVELS:
            lvl = next((l for l in profile if l.get("pres") == lvl_hpa), None)
            if lvl and lvl.get("sknt") is not None:
                result["levels"][lvl_hpa] = {
                    "speed_mph": knots_to_mph(lvl["sknt"]),
                    "dir":       lvl.get("drct", 0),
                    "hght_m":    lvl.get("hght"),
                    "tmpc":      lvl.get("tmpc"),
                }
        soundings[key] = result
        for hpa, d in sorted(result["levels"].items()):
            print(f"    {hpa:.0f} hPa: {cardinal(d['dir']):>3}  {d['speed_mph']:5.1f} mph"
                  f"   ({d['hght_m']} m MSL,  {d['tmpc']}C)")
    except Exception as e:
        print(f"    ERROR: {e}")
    print()

# Extract WindNinja init from GJT 00z (peak event, 700 hPa)
wn_init = soundings.get("GJT_2021-12-31T00", {}).get("levels", {}).get(700.0)
WN_SPEED = round(wn_init["speed_mph"]) if wn_init else 31
WN_DIR   = int(wn_init["dir"])         if wn_init else 247
print(f"  WindNinja init (GJT 700hPa 00z Dec 31): {WN_DIR}deg / {WN_SPEED} mph")
print()

# ============================================================================
# 2. ASOS SURFACE OBSERVATIONS
# ============================================================================
print()
print("-- 2. ASOS SURFACE OBSERVATIONS (IEM) ---------------------------------")
print("   Window: 12z Dec 30 -> 06z Dec 31 2021  (5 AM - 11 PM MST)")
print()

all_asos = {}

for sid, (name, slat, slon) in ASOS_STATIONS.items():
    d = dist_km(FIRE_LAT, FIRE_LON, slat, slon)
    try:
        r = requests.get(
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
            params={
                "station": sid, "data": "all",
                "year1": "2021", "month1": "12", "day1": "30", "hour1": "12",
                "year2": "2021", "month2": "12", "day2": "31", "hour2": "6",
                "tz": "UTC", "format": "onlycomma", "latlon": "no",
                "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
            }, timeout=30)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split("\n") if l.strip() and not l.startswith("#")]
        if len(lines) < 2:
            print(f"  {sid} ({name}): no data returned")
            time.sleep(1); continue

        headers = lines[0].split(",")
        obs = []
        for line in lines[1:]:
            fields = line.split(",")
            if len(fields) < len(headers): continue
            row = dict(zip(headers, fields))
            try:
                spd  = float(row["sknt"])  * 1.15078 if row.get("sknt")  not in ("M","","T") else None
                gust = float(row["gust"])  * 1.15078 if row.get("gust")  not in ("M","","T") else None
                dirn = float(row["drct"])             if row.get("drct")  not in ("M","","T") else None
                obs.append({"time": row.get("valid",""), "spd": spd, "gust": gust, "dir": dirn})
            except: continue

        if not obs:
            print(f"  {sid} ({name}): no valid obs"); time.sleep(1); continue

        all_asos[sid] = obs
        peak_g = max((o for o in obs if o["gust"]), key=lambda x: x["gust"], default=None)
        peak_s = max((o for o in obs if o["spd"]),  key=lambda x: x["spd"],  default=None)
        print(f"  K{sid} ({name}) -- {d:.0f} km from ignition")
        if peak_g: print(f"    Peak gust:  {peak_g['gust']:.0f} mph at {peak_g['time']} UTC")
        if peak_s: print(f"    Peak sust.: {peak_s['spd']:.0f} mph {cardinal(peak_s['dir']) if peak_s['dir'] else '---'} at {peak_s['time']} UTC")
        print(f"    Obs count:  {len(obs)}")
    except Exception as e:
        print(f"  K{sid} ({name}): ERROR -- {e}")
    print()
    time.sleep(1.5)   # respect IEM rate limit

# ============================================================================
# 3. HOURLY WIND TABLE -- BOU and BJC (17z-03z fire window)
# ============================================================================
print()
print("-- 3. HOURLY WIND TABLE  KBOU & KBJC  (17z Dec 30 - 03z Dec 31) ------")
print()
print(f"  {'UTC':>14}  {'KBOU Sust':>12}  {'KBOU Gust':>10}  {'KBJC Sust':>12}  {'KBJC Gust':>10}")
print("  " + "-" * 64)

FIRE_HOURS_UTC = [
    ("2021-12-30", 17), ("2021-12-30", 18), ("2021-12-30", 19),
    ("2021-12-30", 20), ("2021-12-30", 21), ("2021-12-30", 22),
    ("2021-12-30", 23), ("2021-12-31",  0), ("2021-12-31",  1),
    ("2021-12-31",  2), ("2021-12-31",  3),
]

def best_in_hour(obs_list, date_str, hour):
    prefix = f"{date_str} {hour:02d}:"
    matches = [o for o in obs_list if o["time"].startswith(prefix)]
    pg = max((o["gust"] for o in matches if o["gust"]), default=None)
    ps_obs = max((o for o in matches if o["spd"]), key=lambda x: x["spd"], default=None)
    return (ps_obs["spd"] if ps_obs else None,
            ps_obs["dir"] if ps_obs else None,
            pg)

for date_str, hour in FIRE_HOURS_UTC:
    mst = (hour - 7) % 24
    day_label = "Dec30" if date_str.endswith("30") else "Dec31"
    label = f"{hour:02d}z {day_label} ({mst:02d}M)"
    bs, bd, bg = best_in_hour(all_asos.get("BOU", []), date_str, hour)
    js, jd, jg = best_in_hour(all_asos.get("BJC", []), date_str, hour)
    def fmt(s, d, g):
        ss = f"{cardinal(d)} {s:.0f}mph" if s and d else ("---" if not s else f"{s:.0f}mph")
        gs = f"{g:.0f}mph" if g else "---"
        return f"{ss:>12}", f"{gs:>10}"
    bs_s, bg_s = fmt(bs, bd, bg)
    js_s, jg_s = fmt(js, jd, jg)
    print(f"  {label:>14}  {bs_s}  {bg_s}  {js_s}  {jg_s}")

# ============================================================================
# 4. NWS LOCAL STORM REPORTS -- WFO BOU
# ============================================================================
print()
print()
print("-- 4. NWS LOCAL STORM REPORTS (WFO=BOU) --------------------------------")
print("   Window: 15z Dec 30 - 06z Dec 31  (8 AM - 11 PM MST)")
print()

try:
    r = requests.get(
        "https://mesonet.agron.iastate.edu/geojson/lsr.php",
        params={
            "wfo": "BOU",
            "sts": "202112301500",
            "ets": "202112310600",
        }, timeout=20)
    r.raise_for_status()
    features = r.json().get("features", [])
    wind_lsrs = [f for f in features
                 if f["properties"].get("type","") in ("G","N","W","H","D","F","M")]
    print(f"  Total LSRs: {len(features)}   Wind-related: {len(wind_lsrs)}")
    print()
    if wind_lsrs:
        wind_lsrs.sort(key=lambda f: float(f["properties"].get("magnitude") or 0), reverse=True)
        print(f"  {'UTC Time':>16}  {'Type':>4}  {'Mag':>8}  {'Location':40}  {'km from fire'}")
        print("  " + "-" * 82)
        for f in wind_lsrs[:30]:
            p = f["properties"]
            mag = p.get("magnitude","")
            mag_s = f"{mag} mph" if mag else "---"
            coords = f.get("geometry",{}).get("coordinates",[])
            dist_s = f"{dist_km(FIRE_LAT, FIRE_LON, coords[1], coords[0]):.0f} km" if len(coords)==2 else "---"
            loc = f"{p.get('city','?')}, {p.get('county','')}"
            print(f"  {p.get('valid','')[:16]:>16}  {p.get('type','?'):>4}  {mag_s:>8}  {loc:40}  {dist_s}")
except Exception as e:
    print(f"  ERROR: {e}")

# ============================================================================
# 5. ERA5 SURFACE WINDS
# ============================================================================
print()
print()
print("-- 5. ERA5 SURFACE WINDS (Open-Meteo 31km) -----------------------------")
print("   Synoptic context — 31km partially resolves Front Range foothills gradient")
print()

ERA5_POINTS = {
    "Boulder foothills (40.05N -105.30W)":  (40.050, -105.300),
    "Superior/fire area (39.95N -105.17W)": (39.954, -105.168),
    "Jefferson Co plains (39.85N -105.05W)":(39.850, -105.050),
}

era5_results = {}
for name, (lat, lon) in ERA5_POINTS.items():
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": "2021-12-30", "end_date": "2021-12-31",
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "wind_speed_unit": "mph", "timezone": "UTC",
        }, timeout=20)
        h = r.json()["hourly"]
        era5_results[name] = h
        print(f"  {name}")
        print(f"  {'UTC':>5}  {'MST':>5}  {'Wind':>14}  {'Gust':>8}")
        for i, t in enumerate(h["time"]):
            hr = int(t[11:13])
            if not (15 <= hr <= 23 or 0 <= hr <= 4):
                continue
            mst = (hr - 7) % 24
            spd = h["wind_speed_10m"][i]; dr = h["wind_direction_10m"][i]; gst = h["wind_gusts_10m"][i]
            spd_s = f"{cardinal(dr)} {spd:.0f}mph" if spd is not None else "---"
            gst_s = f"{gst:.0f}mph" if gst is not None else "---"
            print(f"  {hr:02d}z    {mst:02d}M  {spd_s:>14}  {gst_s:>8}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR -- {e}")

# ============================================================================
# 6. HRRR -- placeholder (run via conda hrrr311)
# ============================================================================
print()
print("-- 6. HRRR 3km (run via conda) -----------------------------------------")
print()
print("  To fetch HRRR for this event:")
print("  conda run -n hrrr311 python hrrr_case3_marshall.py")
print()
print("  Suggested: 12z Dec 30 run, fxx=3-18 covers 15z-06z")
print("             (= 8 AM MST ignition window through midnight)")
print()

# Hardcoded HRRR values (fill in after running hrrr_case3_marshall.py)
HRRR = {
    # fxx: {sid: (dir, spd_mph)}  -- fill after conda run
    # 18z (11 MST, fire ignition) from 12z Dec 30 run (fxx=6)
}
if HRRR:
    print("  HRRR values loaded.")
else:
    print("  HRRR: not yet run -- values pending")

# ============================================================================
# 7. WINDNINJA TERRAIN SIMULATION
# ============================================================================
print()
print("-- 7. WINDNINJA TERRAIN SIMULATION ------------------------------------")
print(f"   Init: {WN_DIR}deg / {WN_SPEED} mph  (GJT 700hPa 00z Dec 31)")
print(f"   Center: {FIRE_LAT}N, {FIRE_LON}W   Radius: 12mi")
print()

CENTER_LAT = FIRE_LAT
CENTER_LON = FIRE_LON
RADIUS_MI  = 12
VEGETATION = "brush"   # Front Range foothills -- mixed brush/grass

dem_stem  = f"dem_{round(CENTER_LAT,1)}_{round(CENTER_LON,1)}_{RADIUS_MI}mi"
dem_path  = os.path.join(CACHE, f"{dem_stem}.tif")

WN_STATIONS = {
    "BOU":  (40.0376,  -105.2264, "KBOU 5278ft Boulder"),
    "BJC":  (39.9088,  -105.1166, "KBJC 5673ft Broomfield"),
    "EIK":  (40.0105,  -105.0505, "KEIK 5130ft Erie"),
    "FIRE": (39.954,   -105.168,  "Marshall Rd fire origin"),
}

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

# Check for existing WN output
existing_vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_vel-4326.asc"))

if existing_vel:
    print(f"  Cached output found: {os.path.basename(existing_vel[0])}")
    vel_path = existing_vel[0]
    existing_ang = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_ang-4326.asc"))
    ang_path = existing_ang[0] if existing_ang else None
else:
    print(f"  Running WindNinja...")
    if not os.path.exists(dem_path):
        args_fetch = [
            WINDNINJA_CLI, "--num_threads", "8",
            "--fetch_elevation", dem_path,
            "--x_center", str(CENTER_LON), "--y_center", str(CENTER_LAT),
            "--x_buffer", str(RADIUS_MI), "--y_buffer", str(RADIUS_MI),
            "--buffer_units", "miles", "--elevation_source", "srtm",
            "--initialization_method", "domainAverageInitialization",
            "--input_speed", str(WN_SPEED), "--input_speed_units", "mph",
            "--input_direction", str(WN_DIR),
            "--input_wind_height", "10", "--units_input_wind_height", "m",
            "--uni_air_temp", "35", "--air_temp_units", "F",
            "--uni_cloud_cover", "0.3", "--cloud_cover_units", "fraction",
            "--vegetation", VEGETATION, "--mesh_choice", "coarse",
            "--output_wind_height", "10", "--units_output_wind_height", "m",
            "--output_speed_units", "mph", "--output_path", CACHE,
            "--write_ascii_output", "true", "--ascii_out_json", "0", "--ascii_out_4326", "1",
        ]
        result = subprocess.run(args_fetch, capture_output=True, text=True, timeout=600)
    else:
        args_run = [
            WINDNINJA_CLI, "--num_threads", "8",
            "--elevation_file", dem_path,
            "--initialization_method", "domainAverageInitialization",
            "--input_speed", str(WN_SPEED), "--input_speed_units", "mph",
            "--input_direction", str(WN_DIR),
            "--input_wind_height", "10", "--units_input_wind_height", "m",
            "--uni_air_temp", "35", "--air_temp_units", "F",
            "--uni_cloud_cover", "0.3", "--cloud_cover_units", "fraction",
            "--vegetation", VEGETATION, "--mesh_choice", "coarse",
            "--output_wind_height", "10", "--units_output_wind_height", "m",
            "--output_speed_units", "mph", "--output_path", CACHE,
            "--write_ascii_output", "true", "--ascii_out_json", "0", "--ascii_out_4326", "1",
        ]
        result = subprocess.run(args_run, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        print(f"  ERROR (exit {result.returncode}):")
        print(f"  stdout: {result.stdout[:400]}")
        print(f"  stderr: {result.stderr[:400]}")
        vel_path, ang_path = None, None
    else:
        vel_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_vel-4326.asc"))
        ang_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_ang-4326.asc"))
        vel_path = vel_files[0] if vel_files else None
        ang_path = ang_files[0] if ang_files else None
        if vel_path: print(f"  Done: {os.path.basename(vel_path)}")

if vel_path:
    vel_hdr, vel_data = read_asc(vel_path)
    ang_hdr, ang_data = read_asc(ang_path) if ang_path else (None, None)
    s_lat = vel_hdr['yllcorner']; n_lat = s_lat + int(vel_hdr['nrows'])*vel_hdr['cellsize']
    print(f"\n  Grid extent: {s_lat:.3f}-{n_lat:.3f}N")
    print(f"\n  {'Station':^28} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*28}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*22}")
    for stid, (lat, lon, label) in WN_STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        if spd is None:
            print(f"  {label:^28} | {'---':>6} | {'---':>8} | {'---':>8} | outside grid")
        else:
            ratio = spd / WN_SPEED
            flag = " *** EXTREME" if ratio > 2.0 else (" ** strong amp" if ratio > 1.5 else
                   (" * amplified" if ratio > 1.2 else (" sheltered" if ratio < 0.8 else "")))
            ang_s = f"{ang:.0f}deg" if ang else "---"
            print(f"  {label:^28} | {ang_s:>6} | {spd:>6.1f}mph | {ratio:>7.2f}x |{flag}")
    print(f"\n  Init: {WN_SPEED} mph from {WN_DIR}deg  |  ERA5 foothills gusts: 78-88 mph")

print()
print("Done.")
