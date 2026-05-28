#!/usr/bin/env python3
"""
oakland_hills_fire_19911020.py

Case 7 -- Oakland Hills Fire (Tunnel Fire), October 20 1991

Event type: Type 4 -- Surface Pressure-Driven Gap/Channel Flow (fire weather)
Sub-type: Diablo wind -- NE offshore flow through Oakland/Berkeley Hills terrain
Same mechanism as Case 4 (Camp Fire) but Bay Area geography.

25 fatalities, ~3,500 structures destroyed in ~1,500 acres
RH fell to single digits; extreme chaparral/eucalyptus fuel loading

Key Type 4 signature (confirmed):
  700 hPa all soundings: W/WNW 14-20 mph (260-314 deg)
  Surface fire winds:    NE 40-65 mph (~040 deg)
  Misalignment: ~250 degrees -- definitive Type 4

Comparison with Case 4 (Camp Fire, also Type 4):
  Camp Fire:    126 mph peak, GPGI large (~5-6 mb), Feather River Canyon
  Oakland 1991: 65 mph peak,  GPGI moderate (~3-5 mb), Oakland Hills ridge/gaps

Pre-HRRR (1991): ERA5 is primary gridded model.

Data sources:
  Soundings: OAK (Oakland) 00z/12z Oct 20 + 00z Oct 21 -- full wind data available
  ASOS:      LVK (Livermore, inland), OAK, CCR (Concord) -- IEM 1991
  LSRs:      WFO=MTR (Monterey/Bay Area) -- 1991, may be unavailable
  ERA5:      Open-Meteo archive -- 3 Bay Area points
  WindNinja: NE init, Oakland Hills terrain, 12mi
"""

import sys, requests, math, time, glob, subprocess, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WINDNINJA_CLI = r"C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe"
CACHE         = r"C:\temp\windninja_cache"

FIRE_LAT, FIRE_LON = 37.853, -122.218   # Tunnel Road / Oakland Hills ignition area

ASOS_STATIONS = {
    "LVK": ("Livermore Municipal (inland E)",  37.694, -121.819),
    "OAK": ("Oakland Metropolitan Airport",    37.721, -122.220),
    "CCR": ("Buchanan Field Concord (NE)",      37.988, -122.057),
    "SFO": ("San Francisco International",     37.619, -122.375),
}

def cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(float(deg) / 22.5) % 16]

def knots_to_mph(kt): return round(float(kt) * 1.15078, 1)

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371; d = math.radians
    dlat = d(lat2-lat1); dlon = d(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

print()
print("Oakland Hills Fire  |  October 20, 1991  |  Oakland/Berkeley Hills CA")
print("Type 4 -- Surface Pressure-Driven Gap Flow  |  Diablo Wind  |  FIRE WEATHER")
print("25 fatalities, ~3,500 structures -- same mechanism as Camp Fire (Case 4)")
print("Pre-HRRR: ERA5 is primary gridded model")
print("=" * 72)

# ============================================================================
# 1. SOUNDINGS -- OAK (Oakland), three times
# ============================================================================
print()
print("-- 1. UPPER-AIR SOUNDINGS  OAK (Oakland CA) ---------------------------")
print()

SOUNDING_REQUESTS = [
    {"airport": "OAK", "ts": "1991-10-20T00:00:00Z",
     "label": "OAK 00z Oct 20  (5 PM PDT Oct 19, PRE-EVENT)"},
    {"airport": "OAK", "ts": "1991-10-20T12:00:00Z",
     "label": "OAK 12z Oct 20  (5 AM PDT, fire ignition ~10:55 AM = 17:55z)"},
    {"airport": "OAK", "ts": "1991-10-21T00:00:00Z",
     "label": "OAK 00z Oct 21  (5 PM PDT, DURING peak fire spread)"},
]
LEVELS = [500.0, 700.0, 850.0, 925.0]
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
        profiles = r.json().get("profiles", [])
        target = next((p for p in profiles if req["ts"][:10] in str(p.get("valid",""))), None)
        if not target:
            print(f"    No profile found"); print(); continue
        profile = target.get("profile", [])
        result = {"levels": {}}
        for lvl_hpa in LEVELS:
            lvl = next((l for l in profile if l.get("pres") == lvl_hpa and l.get("sknt") is not None), None)
            if lvl:
                result["levels"][lvl_hpa] = {
                    "speed_mph": knots_to_mph(lvl["sknt"]),
                    "dir": lvl.get("drct", 0),
                    "hght_m": lvl.get("hght"),
                    "tmpc": lvl.get("tmpc"),
                }
        soundings[key] = result
        for hpa, d in sorted(result["levels"].items(), reverse=True):
            print(f"    {hpa:5.0f} hPa: {cardinal(d['dir']):>3}  {d['speed_mph']:5.1f} mph"
                  f" ({d['dir']}deg)  {d['hght_m']}m  {d['tmpc']}C")
    except Exception as e:
        print(f"    ERROR: {e}")
    print()

# Type 4 diagnostic and GPGI
pre = soundings.get("OAK_1991-10-20T12", {}).get("levels", {})
lv700 = pre.get(700.0)
print("  -- TYPE 4 DIAGNOSTIC --")
if lv700:
    print(f"  700 hPa (12z Oct 20):  {cardinal(lv700['dir'])} {lv700['speed_mph']:.0f} mph ({lv700['dir']}deg)")
    print(f"  Surface fire winds:     NE ~040deg  40-65 mph  (observed)")
    angle_diff = abs(lv700["dir"] - 40)
    if angle_diff > 180: angle_diff = 360 - angle_diff
    print(f"  Direction misalignment: {angle_diff:.0f}deg -- {'TYPE 4 CONFIRMED' if angle_diff > 90 else 'ambiguous'}")
print()

# GPGI estimate
print("  -- GAP PRESSURE GRADIENT INDEX (GPGI) --")
print("  GPGI = (SLP_interior - SLP_coast) / 50km")
print("  Interior: Livermore Valley (east of hills)")
print("  Coast:    Oakland Bay shoreline (west of hills)")
print("  Typical Diablo wind GPGI: 3-5 mb / 50km")
print("  Camp Fire GPGI for comparison: ~5-6 mb / 150km (Reno-Sacramento)")
print("  Note: Will compute from ERA5 SLP below")
print()

WN_SPEED = 30   # ERA5 surface NE init estimate
WN_DIR   = 40   # NE (Diablo wind direction)

# ============================================================================
# 2. ASOS SURFACE OBS (IEM)
# ============================================================================
print()
print("-- 2. ASOS SURFACE OBSERVATIONS (IEM) ---------------------------------")
print("   Window: 15z Oct 20 -> 03z Oct 21  (8 AM - 8 PM PDT)")
print()

all_asos = {}
for sid, (name, slat, slon) in ASOS_STATIONS.items():
    d = dist_km(FIRE_LAT, FIRE_LON, slat, slon)
    try:
        r = requests.get(
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
            params={
                "station": sid, "data": "all",
                "year1": "1991", "month1": "10", "day1": "20", "hour1": "15",
                "year2": "1991", "month2": "10", "day2": "21", "hour2": "3",
                "tz": "UTC", "format": "onlycomma", "latlon": "no",
                "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
            }, timeout=30)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split("\n") if l.strip() and not l.startswith("#")]
        if len(lines) < 2:
            print(f"  {sid} ({name}): no data returned"); time.sleep(1); continue
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
        if not obs:
            print(f"  {sid} ({name}): no valid obs"); time.sleep(1); continue
        all_asos[sid] = obs
        peak_g = max((o for o in obs if o["gust"]), key=lambda x: x["gust"], default=None)
        peak_s = max((o for o in obs if o["spd"]),  key=lambda x: x["spd"],  default=None)
        print(f"  K{sid} ({name}) -- {d:.0f} km from fire")
        if peak_g: print(f"    Peak gust:  {peak_g['gust']:.0f} mph at {peak_g['time']} UTC")
        if peak_s: print(f"    Peak sust.: {peak_s['spd']:.0f} mph {cardinal(peak_s['dir']) if peak_s['dir'] else '---'} at {peak_s['time']} UTC")
        print(f"    Obs count:  {len(obs)}")
    except Exception as e:
        print(f"  {sid}: ERROR -- {e}")
    print()
    time.sleep(1.5)

# ============================================================================
# 3. HOURLY TABLE -- LVK and OAK
# ============================================================================
print()
print("-- 3. HOURLY TABLE  KLVK (inland) vs KOAK (bay shore)  15z-01z -------")
print("   Livermore (inland/east) vs Oakland Airport (bay/west)")
print("   Pressure gradient = LVK pressure MINUS OAK pressure = GPGI driver")
print()
print(f"  {'UTC':>14}  {'KLVK Sust':>12}  {'KLVK Gust':>10}  {'KOAK Sust':>12}  {'KOAK Gust':>10}")
print("  " + "-" * 64)
for hour in range(15, 26):
    utc_h = hour % 24
    day   = "Oct20" if hour < 24 else "Oct21"
    pdt   = (utc_h - 7) % 24
    prefix = f"1991-10-20 {utc_h:02d}:" if hour < 24 else f"1991-10-21 {utc_h:02d}:"
    def peak(sid):
        matches = [o for o in all_asos.get(sid,[]) if o["time"].startswith(prefix)]
        pg = max((o["gust"] for o in matches if o["gust"]), default=None)
        ps = max((o for o in matches if o["spd"]), key=lambda x: x["spd"], default=None)
        return ps, pg
    ls, lg = peak("LVK"); os, og = peak("OAK")
    def fmt(s, g):
        ss = f"{cardinal(s['dir'])} {s['spd']:.0f}mph" if s and s.get("dir") else (f"{s['spd']:.0f}mph" if s else "---")
        gs = f"{g:.0f}mph" if g else "---"
        return f"{ss:>12}", f"{gs:>10}"
    ls_s, lg_s = fmt(ls, lg); os_s, og_s = fmt(os, og)
    print(f"  {utc_h:02d}z {day} ({pdt:02d}M)  {ls_s}  {lg_s}  {os_s}  {og_s}")

# ============================================================================
# 4. NWS LSRs
# ============================================================================
print()
print()
print("-- 4. NWS LOCAL STORM REPORTS (WFO=MTR San Francisco Bay Area) --------")
print("   Window: 15z Oct 20 -> 06z Oct 21  (note: 1991 LSRs may be sparse)")
print()
try:
    r = requests.get(
        "https://mesonet.agron.iastate.edu/geojson/lsr.php",
        params={"wfo": "MTR", "sts": "199110201500", "ets": "199110210600"},
        timeout=20)
    r.raise_for_status()
    features = r.json().get("features", [])
    wind_lsrs = [f for f in features
                 if f["properties"].get("type","") in ("G","N","W","H","D","F","M")]
    print(f"  Total LSRs: {len(features)}   Wind-related: {len(wind_lsrs)}")
    if wind_lsrs:
        wind_lsrs.sort(key=lambda f: float(f["properties"].get("magnitude") or 0), reverse=True)
        print(f"  {'UTC':>16}  {'Type':>4}  {'Mag':>8}  {'Location':40}  {'km from fire'}")
        print("  " + "-" * 80)
        for f in wind_lsrs[:20]:
            p = f["properties"]
            mag = p.get("magnitude","")
            mag_s = f"{mag} mph" if mag else "---"
            coords = f.get("geometry",{}).get("coordinates",[])
            dist_s = f"{dist_km(FIRE_LAT, FIRE_LON, coords[1], coords[0]):.0f} km" if len(coords)==2 else "---"
            print(f"  {p.get('valid','')[:16]:>16}  {p.get('type','?'):>4}  {mag_s:>8}  {p.get('city','?'):40}  {dist_s}")
    else:
        print("  No wind LSRs found -- 1991 pre-digital LSR archive likely sparse")
except Exception as e:
    print(f"  ERROR: {e}")

# ============================================================================
# 5. ERA5 -- Bay Area transect + SLP for GPGI
# ============================================================================
print()
print()
print("-- 5. ERA5 SURFACE WINDS + SLP (Open-Meteo archive 31km) --------------")
print("   Key: SLP gradient between Livermore (inland) and Oakland (bay)")
print("   captures GPGI -- the Type 4 forecasting driver")
print()

ERA5_POINTS = {
    "Oakland Hills / fire area  (37.85N -122.22W)": (37.85, -122.22),
    "Livermore Valley   (37.69N -121.82W)  inland":  (37.69, -121.82),
    "San Francisco Bay  (37.72N -122.22W)  coast":   (37.72, -122.22),
}

era5_slp = {}
for name, (lat, lon) in ERA5_POINTS.items():
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": "1991-10-20", "end_date": "1991-10-20",
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure",
            "wind_speed_unit": "mph", "timezone": "UTC",
        }, timeout=20)
        h = r.json()["hourly"]
        slp_vals = h.get("surface_pressure",[])
        era5_slp[name] = h
        print(f"  {name}")
        print(f"  {'UTC':>5} {'PDT':>5} {'Wind':>14} {'Gust':>8} {'SLP':>8}")
        for i, t in enumerate(h["time"]):
            hr = int(t[11:13])
            if not (13 <= hr <= 23): continue
            pdt = (hr - 7) % 24
            spd = h["wind_speed_10m"][i]; dr = h["wind_direction_10m"][i]
            gst = h["wind_gusts_10m"][i]; slp = slp_vals[i] if i < len(slp_vals) else None
            spd_s = f"{cardinal(dr)} {spd:.0f}mph" if spd else "---"
            gst_s = f"{gst:.0f}mph" if gst else "---"
            slp_s = f"{slp:.1f}hPa" if slp else "---"
            print(f"  {hr:02d}z    {pdt:02d}M  {spd_s:>14}  {gst_s:>8}  {slp_s:>8}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR -- {e}")

# GPGI from ERA5 SLP
print("  -- GPGI from ERA5 SLP (Livermore - Oakland / 50km) --")
try:
    lvk_slp = era5_slp.get("Livermore Valley   (37.69N -121.82W)  inland",{}).get("surface_pressure",[])
    oak_slp = era5_slp.get("San Francisco Bay  (37.72N -122.22W)  coast",{}).get("surface_pressure",[])
    times   = era5_slp.get("Oakland Hills / fire area  (37.85N -122.22W)",{}).get("time",[])
    if lvk_slp and oak_slp:
        print(f"  {'UTC':>5} {'PDT':>5} {'LVK SLP':>10} {'OAK SLP':>10} {'Gradient':>10} {'GPGI flag'}")
        print("  " + "-" * 56)
        for i, t in enumerate(times):
            hr = int(t[11:13])
            if not (13 <= hr <= 23): continue
            pdt = (hr - 7) % 24
            if i < len(lvk_slp) and i < len(oak_slp) and lvk_slp[i] and oak_slp[i]:
                grad = lvk_slp[i] - oak_slp[i]
                flag = ("*** EXTREME >5mb" if grad > 5 else
                        "** STRONG 3-5mb" if grad > 3 else
                        "* MOD 1-3mb" if grad > 1 else "weak")
                print(f"  {hr:02d}z    {pdt:02d}M  {lvk_slp[i]:>10.1f}  {oak_slp[i]:>10.1f}  {grad:>9.1f}mb  {flag}")
except Exception as e:
    print(f"  GPGI error: {e}")
print()

# ============================================================================
# 6. WINDNINJA
# ============================================================================
print()
print("-- 6. WINDNINJA TERRAIN SIMULATION ------------------------------------")
print(f"   Init: {WN_DIR}deg NE / {WN_SPEED} mph  (ERA5 surface, Diablo wind direction)")
print(f"   Note: 700hPa sounding shows WNW {lv700['dir'] if lv700 else 297}deg/{lv700['speed_mph'] if lv700 else 17:.0f}mph")
print(f"   WN initialized with SURFACE flow (Type 4 correct approach -- not 700hPa)")
print(f"   Center: {FIRE_LAT}N, {FIRE_LON}W   Radius: 12mi")
print()

dem_stem = f"dem_{round(FIRE_LAT,1)}_{round(FIRE_LON,1)}_{12}mi"
dem_path = os.path.join(CACHE, f"{dem_stem}.tif")

WN_STATIONS = {
    "FIRE":  (37.853, -122.218, "Tunnel Rd fire origin  Oakland Hills"),
    "OAK":   (37.721, -122.220, "KOAK Oakland Airport   bay shore"),
    "LVK":   (37.694, -121.819, "KLVK Livermore         inland valley"),
    "CCR":   (37.988, -122.057, "KCCR Concord           NE inland"),
    "RIDGE": (37.870, -122.100, "Diablo foothills ridge ~1800ft"),
}

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
            "--x_center", str(FIRE_LON), "--y_center", str(FIRE_LAT),
            "--x_buffer", "12", "--y_buffer", "12",
            "--buffer_units", "miles", "--elevation_source", "srtm",
        ]
    args += [
        "--initialization_method",   "domainAverageInitialization",
        "--input_speed",             str(WN_SPEED),
        "--input_speed_units",       "mph",
        "--input_direction",         str(WN_DIR),
        "--input_wind_height",       "10", "--units_input_wind_height", "m",
        "--uni_air_temp",            "75", "--air_temp_units", "F",
        "--uni_cloud_cover",         "0.0", "--cloud_cover_units", "fraction",
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
    s_lat = vel_hdr['yllcorner']; n_lat = s_lat + int(vel_hdr['nrows'])*vel_hdr['cellsize']
    print(f"\n  Grid res ~{res_m:.0f}m  Extent {s_lat:.3f}-{n_lat:.3f}N")
    print(f"\n  {'Station':^38} | {'WN Dir':>6} | {'WN Spd':>8} | {'vs Init':>8} | Notes")
    print(f"  {'-'*38}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*26}")
    for stid, (lat, lon, label) in WN_STATIONS.items():
        spd = extract_point(vel_hdr, vel_data, lat, lon)
        ang = extract_point(ang_hdr, ang_data, lat, lon) if ang_data else None
        if spd is None:
            print(f"  {label:^38} | {'---':>6} | {'outside':>8} | {'---':>8} |")
        else:
            ratio = spd / WN_SPEED
            note = ("** channel amp" if ratio > 1.3 else
                    "* ridge amp" if ratio > 1.1 else
                    "sheltered" if ratio < 0.8 else "near-ambient")
            ang_s = f"{ang:.0f}deg" if ang else "---"
            print(f"  {label:^38} | {ang_s:>6} | {spd:>6.1f}mph | {ratio:>7.2f}x | {note}")
    print(f"\n  Init: {WN_SPEED} mph NE  |  Observed: ~40-65 mph NE at fire area")
    print(f"  Published peak gust: ~65 mph at Diablo Gap RAWS / 40-55 mph in fire area")
    print(f"  Type 4: WN captures terrain channeling signal unlike Type 3 (Marshall/Boulder)")

print()
print("Done.")
