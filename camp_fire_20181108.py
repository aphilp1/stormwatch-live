#!/usr/bin/env python3
"""
camp_fire_20181108.py

Case 4 -- Camp Fire hindcast, Butte County CA, November 8 2018

Event type: Type 4 -- Terrain Channeling / NE Downslope (fire weather)
Sub-type: Gap flow + canyon acceleration (Feather River Canyon / Jarbo Gap)

Fire ignited ~06:30 AM PST (14:30 UTC) near Camp Creek Road, Pulga CA
Destroyed Paradise CA and surrounding communities
85 fatalities, ~19,000 structures -- deadliest CA wildfire on record

Key mechanism: NE downslope flow through Feather River Canyon, accelerated
through Jarbo Gap topographic constriction. Surface high over Intermountain
West + inverted trough in Central Valley = strong NE pressure gradient.

Published studies:
  Lareau et al. (2021) BAMS: Synoptic/mesoscale evolution of Camp Fire
  Kiefer et al. (2020) Atmosphere: Meteorological analysis + simulations
  NWS Service Assessment (2019): weather.gov/media/publications/assessments/

Data sources:
  Soundings:    RNO (Reno NV, upwind) -- 12z Nov 8 (pre-fire) + 00z Nov 9 (during)
  RAWS:         JBGC1 (Jarbo Gap, ~2mi from ignition) -- Synoptic Data API
  ASOS:         RDD (Redding), RBL (Red Bluff) -- IEM API
  LSRs:         WFO=STO (Sacramento) -- IEM GeoJSON
  ERA5:         Open-Meteo archive -- 3 points
  WindNinja:    NE flow, Feather River Canyon / Pulga area, 12mi grid
"""

import sys, requests, math, time, glob, subprocess, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"
TOKEN         = 'ad101dda8834440795ff6f4e58f9ebf9'   # Synoptic Data

# Fire ignition point: Camp Creek Rd / Pulga area
FIRE_LAT, FIRE_LON = 39.896, -121.432

# ASOS stations (IEM format, no K prefix)
ASOS_STATIONS = {
    "RDD": ("Redding Municipal",  40.5090, -122.2934),
    "RBL": ("Red Bluff Municipal",40.1503, -122.2516),
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
print("Camp Fire Wind Analysis  |  November 8, 2018  |  Butte County, CA")
print("Type 4 -- Terrain Channeling / NE Downslope  |  FIRE WEATHER CASE")
print("Feather River Canyon / Jarbo Gap gap flow")
print("=" * 72)

# ============================================================================
# 1. UPPER-AIR SOUNDINGS -- RNO (Reno NV, upwind of Sierra Nevada)
# ============================================================================
print()
print("-- 1. UPPER-AIR SOUNDINGS  RNO (Reno NV, upwind) ----------------------")
print()

SOUNDING_REQUESTS = [
    {"airport": "RNO", "ts": "2018-11-08T12:00:00Z",
     "label": "RNO 12z Nov 8  (4 AM PST, PRE-FIRE -- ignition at 14:30z)"},
    {"airport": "RNO", "ts": "2018-11-09T00:00:00Z",
     "label": "RNO 00z Nov 9  (4 PM PST, DURING FIRE SPREAD)"},
]
LEVELS = [500.0, 700.0, 850.0]
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

# Extract WindNinja init from RNO 12z Nov 8, 700 hPa (pre-fire crest-level flow)
wn_lvl = soundings.get("RNO_2018-11-08T12", {}).get("levels", {}).get(700.0)
if wn_lvl:
    WN_SPEED = round(wn_lvl["speed_mph"])
    WN_DIR   = int(wn_lvl["dir"])
else:
    WN_SPEED, WN_DIR = 34, 40   # fallback: ~30kt NE from literature
print(f"  WindNinja init (RNO 700hPa 12z Nov 8): {WN_DIR}deg / {WN_SPEED} mph")
print(f"  Literature: ~30kt (~34mph) from NE at crest level near ignition time")
print()

# ============================================================================
# 2. RAWS -- JBGC1 Jarbo Gap (closest obs to ignition, ~2mi)
# ============================================================================
print()
print("-- 2. RAWS  JBGC1 Jarbo Gap  (~2 mi from ignition) --------------------")
print("   Window: 06z Nov 8 -> 22z Nov 8  (10 PM Nov 7 -> 2 PM Nov 8 PST)")
print()

try:
    r = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params={
        "stid": "JBGC1",
        "start": "201811080600", "end": "201811082200",
        "vars": "wind_speed,wind_gust,wind_direction,relative_humidity,air_temp",
        "units": "english", "token": TOKEN,
    }, timeout=30)
    r.raise_for_status()
    stn = r.json().get("STATION", [{}])[0]
    obs_raw = stn.get("OBSERVATIONS", {})
    times = obs_raw.get("date_time", [])
    spds  = obs_raw.get("wind_speed_set_1",     [None]*len(times))
    gusts = obs_raw.get("wind_gust_set_1",      [None]*len(times))
    dirs  = obs_raw.get("wind_direction_set_1", [None]*len(times))
    rhs   = obs_raw.get("relative_humidity_set_1", [None]*len(times))
    temps = obs_raw.get("air_temp_set_1",       [None]*len(times))

    if times:
        jarbo_obs = []
        print(f"  {'UTC':>16}  {'PST':>5}  {'Dir':>5}  {'Sust':>8}  {'Gust':>8}  {'RH':>5}  {'Temp':>7}")
        print("  " + "-" * 60)
        for i, t in enumerate(times):
            dt = datetime.fromisoformat(t.replace("Z",""))
            pst_h = (dt.hour - 8) % 24
            pst_day = "Nov7" if dt.hour < 8 else "Nov8"
            spd_s  = f"{spds[i]:.0f} mph"  if spds[i]  is not None else "---"
            gust_s = f"{gusts[i]:.0f} mph" if gusts[i] is not None else "---"
            dir_s  = f"{cardinal(dirs[i])}"  if dirs[i]  is not None else "---"
            rh_s   = f"{rhs[i]:.0f}%"      if rhs[i]   is not None else "---"
            tmp_s  = f"{temps[i]:.0f}F"    if temps[i] is not None else "---"
            print(f"  {t[:16]:>16}  {pst_h:02d}{pst_day}  {dir_s:>5}  {spd_s:>8}  {gust_s:>8}  {rh_s:>5}  {tmp_s:>7}")
            jarbo_obs.append({
                "time": t, "spd": spds[i], "gust": gusts[i],
                "dir": dirs[i], "rh": rhs[i], "temp": temps[i]
            })
        # Peak values
        peak_g  = max((o for o in jarbo_obs if o["gust"]), key=lambda x: x["gust"], default=None)
        peak_s  = max((o for o in jarbo_obs if o["spd"]),  key=lambda x: x["spd"],  default=None)
        min_rh  = min((o for o in jarbo_obs if o["rh"]),   key=lambda x: x["rh"],   default=None)
        print(f"\n  Peak gust:  {peak_g['gust']:.0f} mph at {peak_g['time'][:16]}" if peak_g else "")
        print(f"  Peak sust.: {peak_s['spd']:.0f} mph at {peak_s['time'][:16]}" if peak_s else "")
        print(f"  Min RH:     {min_rh['rh']:.0f}% at {min_rh['time'][:16]}" if min_rh else "")
    else:
        print("  No data returned -- station may not be in Synoptic network for this date")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ============================================================================
# 3. ASOS -- RDD and RBL (valley floor stations)
# ============================================================================
print()
print("-- 3. ASOS SURFACE OBSERVATIONS (IEM) ---------------------------------")
print("   Window: 12z Nov 8 -> 06z Nov 9  (4 AM - 10 PM PST Nov 8)")
print()

all_asos = {}
for sid, (name, slat, slon) in ASOS_STATIONS.items():
    d = dist_km(FIRE_LAT, FIRE_LON, slat, slon)
    try:
        r = requests.get(
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
            params={
                "station": sid, "data": "all",
                "year1": "2018", "month1": "11", "day1": "8",  "hour1": "12",
                "year2": "2018", "month2": "11", "day2": "9",  "hour2": "6",
                "tz": "UTC", "format": "onlycomma", "latlon": "no",
                "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
            }, timeout=30)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split("\n") if l.strip() and not l.startswith("#")]
        if len(lines) < 2:
            print(f"  {sid} ({name}): no data"); time.sleep(1); continue
        headers = lines[0].split(",")
        obs = []
        for line in lines[1:]:
            fields = line.split(",")
            if len(fields) < len(headers): continue
            row = dict(zip(headers, fields))
            try:
                spd  = float(row["sknt"]) * 1.15078 if row.get("sknt") not in ("M","","T") else None
                gust = float(row["gust"]) * 1.15078 if row.get("gust") not in ("M","","T") else None
                dirn = float(row["drct"])             if row.get("drct") not in ("M","","T") else None
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
        print(f"  {sid}: ERROR -- {e}")
    print()
    time.sleep(1.5)

# ============================================================================
# 4. Hourly table -- RDD fire window (13z-23z)
# ============================================================================
print()
print("-- 4. HOURLY TABLE  KRDD  (13z-23z Nov 8 = 5 AM - 3 PM PST) -----------")
print()
print(f"  {'UTC':>14}  {'KRDD Sust':>12}  {'KRDD Gust':>10}")
print("  " + "-" * 42)
for hour in range(13, 24):
    pst = hour - 8
    prefix = f"2018-11-08 {hour:02d}:"
    matches = [o for o in all_asos.get("RDD", []) if o["time"].startswith(prefix)]
    peak_g = max((o["gust"] for o in matches if o["gust"]), default=None)
    peak_s = max((o for o in matches if o["spd"]), key=lambda x: x["spd"], default=None)
    ss = f"{cardinal(peak_s['dir'])} {peak_s['spd']:.0f}mph" if peak_s and peak_s["dir"] else ("---" if not peak_s else f"{peak_s['spd']:.0f}mph")
    gs = f"{peak_g:.0f}mph" if peak_g else "---"
    print(f"  {hour:02d}z Nov8 ({pst:02d}M)  {ss:>12}  {gs:>10}")

# ============================================================================
# 5. NWS LSRs -- WFO=STO (Sacramento)
# ============================================================================
print()
print()
print("-- 5. NWS LOCAL STORM REPORTS (WFO=STO Sacramento) --------------------")
print("   Window: 12z Nov 8 -> 06z Nov 9  (fire ignition through evening)")
print()
try:
    r = requests.get(
        "https://mesonet.agron.iastate.edu/geojson/lsr.php",
        params={"wfo": "STO", "sts": "201811081200", "ets": "201811090600"},
        timeout=20)
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
        for f in wind_lsrs[:25]:
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
# 6. ERA5 -- 3 points: Jarbo Gap, Paradise, Sacramento Valley
# ============================================================================
print()
print()
print("-- 6. ERA5 SURFACE WINDS (Open-Meteo 31km) ----------------------------")
print("   Key gradient: canyon/foothills vs valley floor")
print()

ERA5_POINTS = {
    "Jarbo Gap / canyon (39.95N -121.45W)": (39.95,  -121.45),
    "Paradise foothills (39.75N -121.60W)": (39.75,  -121.60),
    "Sacramento Valley  (39.50N -121.95W)": (39.50,  -121.95),
}

for name, (lat, lon) in ERA5_POINTS.items():
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": "2018-11-08", "end_date": "2018-11-08",
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "wind_speed_unit": "mph", "timezone": "UTC",
        }, timeout=20)
        h = r.json()["hourly"]
        print(f"  {name}")
        print(f"  {'UTC':>5}  {'PST':>5}  {'Wind':>14}  {'Gust':>8}")
        for i, t in enumerate(h["time"]):
            hr = int(t[11:13])
            if not (10 <= hr <= 23): continue
            pst = (hr - 8) % 24
            spd = h["wind_speed_10m"][i]; dr = h["wind_direction_10m"][i]; gst = h["wind_gusts_10m"][i]
            spd_s = f"{cardinal(dr)} {spd:.0f}mph" if spd else "---"
            gst_s = f"{gst:.0f}mph" if gst else "---"
            print(f"  {hr:02d}z    {pst:02d}M  {spd_s:>14}  {gst_s:>8}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR -- {e}")

# ============================================================================
# 7. HRRR placeholder
# ============================================================================
print()
print("-- 7. HRRR 3km (run via conda) -----------------------------------------")
print()
print("  conda run -n hrrr311 python hrrr_case4_campfire.py")
print("  Suggested: 12z Nov 8 run, fxx=2-12 covers 14z-00z (ignition window)")
print()

HRRR = {}  # fill after conda run
print("  HRRR: not yet run -- pending")

# ============================================================================
# 8. WindNinja terrain simulation
# ============================================================================
print()
print("-- 8. WINDNINJA TERRAIN SIMULATION ------------------------------------")
print(f"   Init: {WN_DIR}deg / {WN_SPEED} mph")
print(f"   Center: {FIRE_LAT}N, {FIRE_LON}W  (Jarbo Gap / Pulga)   Radius: 12mi")
print(f"   Key: can WindNinja resolve Feather River Canyon acceleration?")
print()

CENTER_LAT = FIRE_LAT
CENTER_LON = FIRE_LON
RADIUS_MI  = 12
VEGETATION = "brush"

WN_STATIONS = {
    "JARBO": (39.977,  -121.422, "Jarbo Gap RAWS  ~2mi from ignition"),
    "FIRE":  (39.896,  -121.432, "Camp Creek Rd   fire origin"),
    "PARA":  (39.760,  -121.620, "Paradise        6mi W of ignition"),
    "RDD":   (40.509,  -122.293, "KRDD Redding    valley floor"),
}

dem_stem = f"dem_{round(CENTER_LAT,1)}_{round(CENTER_LON,1)}_{RADIUS_MI}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")

existing_vel = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_vel-4326.asc"))

if existing_vel:
    print(f"  Cached: {os.path.basename(existing_vel[0])}")
    vel_path = existing_vel[0]
    ang_files = glob.glob(os.path.join(CACHE, f"{dem_stem}_{WN_DIR}_{WN_SPEED}_*_ang-4326.asc"))
    ang_path = ang_files[0] if ang_files else None
else:
    args = [WINDNINJA_CLI, "--num_threads", "8"]
    if os.path.exists(dem_path):
        args += ["--elevation_file", dem_path]
    else:
        args += [
            "--fetch_elevation", dem_path,
            "--x_center", str(CENTER_LON), "--y_center", str(CENTER_LAT),
            "--x_buffer", str(RADIUS_MI),  "--y_buffer", str(RADIUS_MI),
            "--buffer_units", "miles", "--elevation_source", "srtm",
        ]
    args += [
        "--initialization_method",   "domainAverageInitialization",
        "--input_speed",             str(WN_SPEED),
        "--input_speed_units",       "mph",
        "--input_direction",         str(WN_DIR),
        "--input_wind_height",       "10", "--units_input_wind_height", "m",
        "--uni_air_temp",            "45", "--air_temp_units", "F",
        "--uni_cloud_cover",         "0.1", "--cloud_cover_units", "fraction",
        "--vegetation",              VEGETATION,
        "--mesh_choice",             "coarse",
        "--output_wind_height",      "10", "--units_output_wind_height", "m",
        "--output_speed_units",      "mph", "--output_path", CACHE,
        "--write_ascii_output",      "true",
        "--ascii_out_json",          "0",
        "--ascii_out_4326",          "1",
    ]
    print(f"  Running WindNinja {WN_DIR}deg / {WN_SPEED}mph ...")
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  ERROR (exit {result.returncode}): {result.stdout[:300]} {result.stderr[:300]}")
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
    s_lat = vel_hdr['yllcorner']; n_lat = s_lat + int(vel_hdr['nrows'])*vel_hdr['cellsize']
    w_lon = vel_hdr['xllcorner']; e_lon = w_lon + int(vel_hdr['ncols'])*vel_hdr['cellsize']
    res_m = vel_hdr['cellsize'] * 111000
    print(f"\n  Grid: {int(vel_hdr['ncols'])}x{int(vel_hdr['nrows'])}  res~{res_m:.0f}m  "
          f"Extent: {s_lat:.3f}-{n_lat:.3f}N  {w_lon:.3f}-{e_lon:.3f}W")
    print(f"\n  {'Station':^35} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*35}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*24}")
    for stid, (lat, lon, label) in WN_STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        if spd is None:
            print(f"  {label:^35} | {'---':>6} | {'---':>8} | {'---':>8} | outside grid")
        else:
            ratio = spd / WN_SPEED
            flag = (" *** EXTREME >2x" if ratio > 2.0 else
                    " ** strong amp >1.5x" if ratio > 1.5 else
                    " * amplified >1.2x" if ratio > 1.2 else
                    " sheltered <0.8x" if ratio < 0.8 else "")
            ang_s = f"{ang:.0f}deg" if ang else "---"
            print(f"  {label:^35} | {ang_s:>6} | {spd:>6.1f}mph | {ratio:>7.2f}x |{flag}")
    print(f"\n  Init: {WN_SPEED} mph from {WN_DIR}deg")
    print(f"  Jarbo Gap observed: 32 mph sust / 52 mph gusts at 12z")
    print(f"  Literature crest-level: ~30kt (~34mph) NE at ignition (14z)")

print()
print("Done.")
