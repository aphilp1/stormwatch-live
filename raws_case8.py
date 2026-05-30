#!/usr/bin/env python3
"""
raws_case8.py
=============
Case 8 -- Thomas Fire, December 4 2017
Fetch RAWS / ASOS observations for BC sweep validation.

Run: python raws_case8.py

Sources:
  KOXR  Oxnard ASOS      -- IEM ASOS (within synoptic network)
  KSBP  San Luis Obispo   -- IEM ASOS (upwind reference)
  WPNC1 Wheeler Springs   -- Synoptic API (outside WN grid but useful)
  NWS LSR peak gusts      -- documented from event summary

Key event window: 06z-18z Dec 4 2017 (pre-dawn through midday)
  Ignition: ~09:45z.  Most explosive spread: 09-14z.
"""
import sys, requests, math
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = "ad101dda8834440795ff6f4e58f9ebf9"   # Synoptic free tier

EVENT_DATE = "2017-12-04"
HOURS      = list(range(6, 19))            # 06z-18z
KEY_HOURS  = [8, 9, 10, 11, 12, 13]       # around ignition + first spread


# ---------------------------------------------------------------------------
# IEM ASOS stations
# ---------------------------------------------------------------------------

IEM_STATIONS = {
    "KOXR": (34.200, -119.207, "Oxnard/Ventura  sea level"),
    "KSBP": (35.237, -120.642, "San Luis Obispo  212ft  (upwind ref)"),
}

def fetch_iem_asos(station_id):
    r = requests.get("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", params={
        "station": station_id, "data": "all",
        "year1": "2017", "month1": "12", "day1": "4",
        "year2": "2017", "month2": "12", "day2": "4",
        "tz": "UTC", "format": "onlycomma", "latlon": "no",
        "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
    }, timeout=20)
    obs = {}
    for line in r.text.split("\n")[1:]:
        cols = line.strip().split(",")
        if len(cols) < 12 or "2017-12-04" not in (cols[1] if len(cols) > 1 else ""):
            continue
        try:
            dt = datetime.fromisoformat(cols[1])
            h = dt.hour
            spd  = float(cols[6])  * 1.15078 if cols[6]  not in ("M","","T") else None
            gust = float(cols[11]) * 1.15078 if cols[11] not in ("M","","T") else None
            dirn = float(cols[5])             if cols[5]  not in ("M","")     else None
            pri = abs(dt.minute - 53)
            if h not in obs or pri < obs[h]["p"]:
                obs[h] = {"s": spd, "g": gust, "d": dirn, "p": pri}
        except Exception:
            pass
    return obs


# ---------------------------------------------------------------------------
# Synoptic RAWS stations
# ---------------------------------------------------------------------------

SYNOPTIC_STATIONS = {
    "WPNC1": (34.522, -119.318, "Wheeler Springs ~2050ft"),
}

def fetch_synoptic(station_id):
    r = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params={
        "stid": station_id,
        "start": "201712040600", "end": "201712041900",
        "vars": "wind_speed,wind_gust,wind_direction",
        "units": "english", "token": TOKEN,
    }, timeout=30)
    obs = {}
    try:
        stn = r.json().get("STATION", [{}])[0]
        data = stn.get("OBSERVATIONS", {})
        spds  = data.get("wind_speed_set_1", [])
        gusts = data.get("wind_gust_set_1", [])
        dirs  = data.get("wind_direction_set_1", [])
        for i, t in enumerate(data.get("date_time", [])):
            dt = datetime.fromisoformat(t.replace("Z",""))
            obs[dt.hour] = {
                "s": spds[i]  if i < len(spds)  else None,
                "g": gusts[i] if i < len(gusts) else None,
                "d": dirs[i]  if i < len(dirs)  else None,
            }
    except Exception as e:
        print(f"  Synoptic error for {station_id}: {e}")
    return obs


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def fd(v): return f"{v:3.0f}" if v is not None else "  M"
def fs(v): return f"{v:4.1f}" if v is not None else "   M"
def fg(v): return f"{v:4.0f}" if v is not None else "   M"
def fds(d,s):    return f"{fd(d)}/{fs(s)}"
def fdsg(d,s,g): return f"{fd(d)}/{fs(s)}/{fg(g)}"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("Fetching Thomas Fire Dec 4 2017 surface obs...")

    iem_data = {}
    for sid in IEM_STATIONS:
        print(f"  IEM ASOS {sid}...", end=" ", flush=True)
        iem_data[sid] = fetch_iem_asos(sid)
        print("done.")

    syn_data = {}
    for sid in SYNOPTIC_STATIONS:
        print(f"  Synoptic {sid}...", end=" ", flush=True)
        syn_data[sid] = fetch_synoptic(sid)
        print("done.")

    print()
    print("=" * 88)
    print("  Thomas Fire  December 4 2017  Surface Obs  (UTC)")
    print("  BC reference: HRRR 700 hPa = 28.8 mph @ 310 NW  | WN HRRR-prior run: 29 mph @ 310")
    print("=" * 88)

    print()
    print(f"  TABLE 1 — KOXR Oxnard / KSBP SLO  (IEM ASOS, Dir/Spd/Gust mph)")
    print(f"  {'UTC':>3} | {'-- KOXR Oxnard (coast) --':^26} | {'-- KSBP SLO (upwind) --':^25}")
    print(f"  {'':3} | {'Dir  Spd  Gust':^26} | {'Dir  Spd  Gust':^25}")
    print("  " + "-" * 58)
    for h in HOURS:
        ko = iem_data["KOXR"].get(h, {})
        ks = iem_data["KSBP"].get(h, {})
        flag = " <-- ignition" if h == 9 else ""
        print(f"  {h:02d}z | {fdsg(ko.get('d'), ko.get('s'), ko.get('g')):^26} | "
              f"{fdsg(ks.get('d'), ks.get('s'), ks.get('g')):^25}{flag}")

    print()
    print(f"  TABLE 2 — Wheeler Springs RAWS (Synoptic, Dir/Spd/Gust mph)")
    print(f"  {'UTC':>3} | {'-- WPNC1 Wheeler Springs --':^28}")
    print(f"  {'':3} | {'Dir  Spd  Gust':^28}")
    print("  " + "-" * 36)
    for h in HOURS:
        wp = syn_data["WPNC1"].get(h, {})
        flag = " <-- ignition" if h == 9 else ""
        print(f"  {h:02d}z | {fdsg(wp.get('d'), wp.get('s'), wp.get('g')):^28}{flag}")

    # Summary of peak gusts for BC sweep
    print()
    print("  PEAK GUSTS DURING KEY WINDOW (06-14z) -- for bc_label_generator:")
    print("  Station        | Peak Gust | Hour | Notes")
    print("  " + "-" * 52)
    for sid, label_info in [("KOXR", IEM_STATIONS["KOXR"]),
                              ("KSBP", IEM_STATIONS["KSBP"])]:
        obs = iem_data[sid]
        peak = max(
            [(h, d.get("g") or d.get("s") or 0) for h, d in obs.items()
             if h in KEY_HOURS],
            key=lambda x: x[1], default=(None, None))
        if peak[1]:
            print(f"  {sid:12s}   | {peak[1]:5.0f} mph  | {peak[0]:02d}z  | {label_info[2]}")
        else:
            print(f"  {sid:12s}   |   ---     |  --  | no data")

    for sid, label_info in [("WPNC1", SYNOPTIC_STATIONS["WPNC1"])]:
        obs = syn_data[sid]
        peak = max(
            [(h, d.get("g") or d.get("s") or 0) for h, d in obs.items()
             if h in KEY_HOURS],
            key=lambda x: x[1], default=(None, None))
        if peak[1]:
            print(f"  {sid:12s}   | {peak[1]:5.0f} mph  | {peak[0]:02d}z  | {label_info[2]}")
        else:
            print(f"  {sid:12s}   |   ---     |  --  | no data")

    print()
    print("  NWS LSR verified gusts (from event summary, Dec 4 2017):")
    print("    Santa Paula  ~60 mph gust  (NWS Oxnard)  -- documented fire start")
    print("    Ventura      ~70 mph gust  (NWS Oxnard)  -- as fire entered city")
    print("    Ojai/Meiners Oaks  ~65 mph (multiple reports)")
    print()
    print("  COPY OBSERVED GUSTS INTO bc_label_generator.py OBSERVED_GUSTS dict")
    print("  once RAWS gusts are confirmed above.")
