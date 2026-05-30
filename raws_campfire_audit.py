from synoptic_config import SYNOPTIC_API_KEY, SYNOPTIC_TOKEN
#!/usr/bin/env python3
"""
raws_campfire_audit.py
======================
Fetch Camp Fire (Nov 8 2018) RAWS / ASOS wind observations for the
BC sweep validation and amplification held-out test.

PRE-REGISTERED PREDICTIONS (set before any data was viewed, 2026-05-30):
  BC speed from sweep: 33-37 mph
  BC direction: 35-55 deg NE
  Concow WN prediction at 35 mph BC: 67.3 mph sustained
  Gust factor convention: GUST_FACTOR=1.0 for both sweeps (WN sustained vs obs)
  If 52 mph Jarbo was a gust and observed sustained was meaningfully lower,
  revision required -- but convention is locked before looking.

Two sweep designs (kept on separate station partitions):
  Sweep A: ALL 4 stations   -> BC label for outer trainer (speed-bias test)
  Sweep B: Jarbo + Paradise -> BC held-out Concow + Pulga (amplification test)

Data strategy:
  1. Synoptic radius search near fire (~39.8N, -121.5W, 30mi radius) to
     identify available stations -- free tier may not cover 2018
  2. IEM ASOS for KCIC (Chico, nearest ASOS valley reference)
  3. IEM RAWS archive for known station IDs (fallback if Synoptic 2018 blocked)
  4. Report BOTH wind_speed (sustained) AND wind_gust for each station

Run: python raws_campfire_audit.py
"""
import sys, requests, json
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = SYNOPTIC_TOKEN  # see synoptic_config.py

EVENT_DATE  = "2018-11-08"
START_UTC   = "201811080600"    # 06z start (pre-ignition)
END_UTC     = "201811081800"    # 18z end
KEY_HOURS   = list(range(12, 18))   # 12-17z (ignition ~14:30z + first hours)

# Known approximate locations for the four BC stations
# (used to cross-reference radius search results)
BC_STATIONS = {
    "jarbo_gap": (39.735944, -121.488944, 52.0),   # confirmed 52 mph -- observed what?
    "concow":    (39.600, -121.530, None),   # Concow community / Berry Creek area
    "paradise":  (39.760, -121.620, None),   # Town of Paradise
    "pulga":     (39.896, -121.432, None),   # Poe Dam / fire ignition area
}

# Additional reference station
IEM_ASOS_STATIONS = {
    "CIC": (39.795, -121.858, "Chico ASOS -- valley floor reference"),
}


# ---------------------------------------------------------------------------
# 1. SYNOPTIC RADIUS SEARCH — discover all stations in the fire area
# ---------------------------------------------------------------------------

def synoptic_radius_search():
    """Find all stations within 30 miles of Camp Fire area."""
    print("Synoptic radius search (39.8N, -121.5W, 30mi)...", end=" ", flush=True)
    r = requests.get("https://api.synopticdata.com/v2/stations/metadata", params={
        "radius": "39.8,-121.5,30",
        "network": "2",   # RAWS network
        "token": TOKEN,
    }, timeout=30)
    if r.status_code != 200:
        print(f"FAILED ({r.status_code})")
        return []
    data = r.json()
    stations = data.get("STATION", [])
    print(f"{len(stations)} stations found.")
    return stations


def synoptic_timeseries(stids, start=START_UTC, end=END_UTC):
    """Fetch sustained + gust time series for a list of station IDs."""
    if not stids:
        return {}
    r = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params={
        "stid": ",".join(stids),
        "start": start, "end": end,
        "vars": "wind_speed,wind_gust,wind_direction",
        "units": "english",
        "token": TOKEN,
    }, timeout=30)
    if r.status_code != 200:
        return {}
    data = r.json()
    if data.get("SUMMARY", {}).get("RESPONSE_CODE") != 1:
        return {}
    result = {}
    for stn in data.get("STATION", []):
        stid = stn["STID"]
        obs = stn.get("OBSERVATIONS", {})
        result[stid] = {
            "name": stn.get("NAME", stid),
            "lat":  float(stn.get("LATITUDE", 0)),
            "lon":  float(stn.get("LONGITUDE", 0)),
            "elev": stn.get("ELEVATION"),
            "times": obs.get("date_time", []),
            "spd":  obs.get("wind_speed_set_1", []),
            "gust": obs.get("wind_gust_set_1", []),
            "dir":  obs.get("wind_direction_set_1", []),
        }
    return result


# ---------------------------------------------------------------------------
# 2. IEM ASOS FALLBACK for Chico (KCIC)
# ---------------------------------------------------------------------------

def fetch_iem_asos(station_id):
    r = requests.get("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", params={
        "station": station_id, "data": "all",
        "year1": "2018", "month1": "11", "day1": "8",
        "year2": "2018", "month2": "11", "day2": "8",
        "tz": "UTC", "format": "onlycomma", "latlon": "no",
        "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
    }, timeout=20)
    obs = {}
    for line in r.text.split("\n")[1:]:
        cols = line.strip().split(",")
        if len(cols) < 12 or "2018-11-08" not in (cols[1] if len(cols) > 1 else ""):
            continue
        try:
            dt = datetime.fromisoformat(cols[1])
            h = dt.hour
            spd  = float(cols[6])  * 1.15078 if cols[6]  not in ("M","","T") else None
            gust = float(cols[11]) * 1.15078 if cols[11] not in ("M","","T") else None
            dirn = float(cols[5])             if cols[5]  not in ("M","")     else None
            pri  = abs(dt.minute - 53)
            if h not in obs or pri < obs[h]["p"]:
                obs[h] = {"s": spd, "g": gust, "d": dirn, "p": pri}
        except Exception:
            pass
    return obs


# ---------------------------------------------------------------------------
# 3. IEM RAWS FALLBACK for specific station IDs
# ---------------------------------------------------------------------------

def fetch_iem_raws(station_id):
    """
    IEM RAWS archive — goes back further than Synoptic free tier.
    URL: mesonet.agron.iastate.edu/request/raws/fe.py
    """
    r = requests.get("https://mesonet.agron.iastate.edu/request/raws/fe.py", params={
        "station": station_id,
        "year1": "2018", "month1": "11", "day1": "8", "hour1": "6",
        "year2": "2018", "month2": "11", "day2": "8", "hour2": "18",
        "vars": "wind_speed,wind_gust,wind_direction",
        "what": "download", "delim": "comma",
    }, timeout=30)
    obs = {}
    lines = r.text.split("\n")
    # IEM RAWS format varies -- try to parse
    for line in lines[1:]:
        cols = line.strip().split(",")
        if len(cols) < 4:
            continue
        try:
            dt = datetime.fromisoformat(cols[0].replace("Z","").replace("T"," "))
            h  = dt.hour
            # column positions depend on header -- store raw and sort later
            obs.setdefault("raw", []).append(cols)
            obs.setdefault("times", []).append(dt)
        except Exception:
            pass
    return obs


# ---------------------------------------------------------------------------
# PRINT HELPERS
# ---------------------------------------------------------------------------

def fd(v): return f"{v:3.0f}" if v is not None else "  M"
def fs(v): return f"{v:5.1f}" if v is not None else "    M"
def fg(v): return f"{v:5.1f}" if v is not None else "    M"


def print_station_table(stid, data, label=""):
    name = data.get("name", stid)
    elev = data.get("elev", "?")
    lat  = data.get("lat", 0)
    lon  = data.get("lon", 0)
    print(f"\n  {label or name}  ({stid})  {lat:.3f}N {lon:.3f}W  elev={elev}ft")
    print(f"  {'UTC':>3} | {'Dir':>4} | {'Sust':>6} | {'Gust':>6} | ratio")
    print(f"  {'-'*3}-+-{'-'*4}-+-{'-'*6}-+-{'-'*6}-+-{'-'*8}")

    times = data.get("times", [])
    spds  = data.get("spd", [])
    gusts = data.get("gust", [])
    dirs  = data.get("dir", [])

    peak_sust = peak_gust = 0.0
    peak_sust_h = peak_gust_h = None

    for i, t in enumerate(times):
        try:
            h = int(t[11:13])
        except Exception:
            continue
        if h < 6 or h > 18:
            continue
        s = spds[i]  if i < len(spds)  else None
        g = gusts[i] if i < len(gusts) else None
        d = dirs[i]  if i < len(dirs)  else None
        flag = " <-- ignition" if h == 14 else ""
        ratio_s = f"{g/s:.2f}x" if (g and s and s > 0) else "  ---"
        print(f"  {h:02d}z | {fd(d)} | {fs(s)} | {fg(g)} | {ratio_s}{flag}")
        if s and s > peak_sust:
            peak_sust, peak_sust_h = s, h
        if g and g > peak_gust:
            peak_gust, peak_gust_h = g, h

    if peak_sust > 0:
        print(f"  Peak sustained: {peak_sust:.1f} mph at {peak_sust_h:02d}z")
    if peak_gust > 0:
        print(f"  Peak gust:      {peak_gust:.1f} mph at {peak_gust_h:02d}z")
        if peak_sust > 0:
            print(f"  Peak gust/sust ratio: {peak_gust/peak_sust:.2f}x")
    return peak_sust, peak_gust


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 72)
    print("  CAMP FIRE  November 8 2018 — RAWS Audit Fetch")
    print("  PRE-REGISTERED: BC sweep 33-37 mph, Concow WN prediction 67.3 mph sustained")
    print("  GUST FACTOR CONVENTION: 1.0 (WN sustained vs obs), committed before fetch")
    print("=" * 72)

    # --- Step 1: Synoptic radius search ---
    print()
    print("STEP 1: Synoptic radius search for RAWS stations")
    nearby = synoptic_radius_search()
    if nearby:
        print(f"\n  Stations within 30mi of 39.8N/-121.5W:")
        for stn in nearby[:20]:
            print(f"    {stn.get('STID','?'):8s} {stn.get('NAME','?'):30s} "
                  f"{stn.get('LATITUDE','?')}N {stn.get('LONGITUDE','?')}W")
        station_ids = [s.get("STID") for s in nearby if s.get("STID")]

        # --- Step 2: Try fetching 2018 data from Synoptic ---
        print()
        print(f"STEP 2: Synoptic timeseries for {len(station_ids)} stations (Nov 8 2018)")
        syn_data = synoptic_timeseries(station_ids)

        if syn_data:
            print(f"  {len(syn_data)} stations returned data.")
            print()
            print("  STATION DATA (06-18z UTC, sustained + gust):")
            peaks = {}
            for stid, data in syn_data.items():
                ps, pg = print_station_table(stid, data)
                peaks[stid] = (ps, pg)
        else:
            print("  No data returned -- 2018 likely outside Synoptic free-tier range.")
    else:
        print("  Radius search returned nothing.")
        syn_data = {}

    # --- Step 3: IEM ASOS for Chico ---
    print()
    print("STEP 3: IEM ASOS -- Chico KCIC (valley floor reference)")
    kcic = fetch_iem_asos("CIC")
    if kcic:
        print(f"\n  KCIC Chico  (valley floor, 39.795N -121.858W)")
        print(f"  {'UTC':>3} | {'Dir':>4} | {'Sust':>6} | {'Gust':>6} | flag")
        print(f"  {'-'*3}-+-{'-'*4}-+-{'-'*6}-+-{'-'*6}-+-{'-'*16}")
        for h in range(6, 19):
            obs = kcic.get(h, {})
            flag = " <-- ignition ~14:30z" if h == 14 else ""
            print(f"  {h:02d}z | {fd(obs.get('d'))} | {fs(obs.get('s'))} | "
                  f"{fg(obs.get('g'))} |{flag}")
    else:
        print("  IEM ASOS fetch returned nothing.")

    # --- Step 4: IEM RAWS for known Camp Fire area station IDs ---
    # Try IDs we can guess from naming conventions; report what works
    print()
    print("STEP 4: IEM RAWS archive attempts for Camp Fire area station IDs")
    candidate_ids = [
        "JRBC1",  # Jarbo Gap, CA? (guessing naming convention)
        "BNSC1",  # Brush/Berry Creek area?
        "PDKC1",  # Paradise?
        "CNKC1",  # Concow?
        "CGCC1",  # Canyon Creek?
    ]
    for sid in candidate_ids:
        print(f"  Trying {sid}...", end=" ", flush=True)
        try:
            data = fetch_iem_raws(sid)
            if data.get("times"):
                print(f"  {len(data['times'])} obs returned -- parsing")
                # IEM RAWS format TBD -- just report raw header
                r2 = requests.get("https://mesonet.agron.iastate.edu/request/raws/fe.py",
                    params={"station": sid, "year1": "2018", "month1": "11", "day1": "8",
                            "hour1": "6", "year2": "2018", "month2": "11", "day2": "8",
                            "hour2": "18", "what": "download", "delim": "comma"}, timeout=20)
                lines = [l for l in r2.text.split("\n") if l.strip()]
                if lines:
                    print(f"    Header: {lines[0][:80]}")
                    for l in lines[1:5]:
                        print(f"    {l[:80]}")
            else:
                print("no data")
        except Exception as e:
            print(f"error: {e}")

    # --- Summary: what to fill into bc_label_generator ---
    print()
    print("=" * 72)
    print("  SUMMARY FOR bc_label_generator.py OBSERVED_GUSTS:")
    print("  (fill from peak sustained values above, GUST_FACTOR=1.0 convention)")
    print()
    print("  OBSERVED_GUSTS = {")
    print('    "jarbo_gap": 52.0,   # confirmed, NEED sustained vs gust clarified')
    print('    "concow":    <fill>,  # from Synoptic/IEM above')
    print('    "paradise":  <fill>,')
    print('    "pulga":     <fill>,')
    print("  }")
    print()
    print("  Note: 52 mph at Jarbo Gap -- was this gust or sustained?")
    print("  Check above time series for gust/sustained ratio at Jarbo.")
    print("  This determines the GUST_FACTOR convention for both sweeps.")
