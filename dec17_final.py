#!/usr/bin/env python3
import sys, requests, math
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

TOKEN  = 'ad101dda8834440795ff6f4e58f9ebf9'
HOURS  = list(range(11, 22))
COUP   = [18, 19, 20, 21]   # coupled window: cold pool mixed out, NW flow at surface

# ── HRRR 3km — fetched 2026-05-09 via conda run -n hrrr311 hrrr_test.py ─────
# 00z run, fxx=11-21  |  noaa-hrrr-bdp-pds S3  |  Herbie + cfgrib
HRRR = {
    11: {"KMSO": ( 89, 11.1), "MPOI": ( 54,  9.9), "BLMM8": (228, 15.3), "TS897": (160, 14.1)},
    12: {"KMSO": ( 74, 10.4), "MPOI": ( 46,  8.2), "BLMM8": (230, 16.8), "TS897": (177, 18.0)},
    13: {"KMSO": ( 69,  9.8), "MPOI": ( 61,  4.2), "BLMM8": (240, 17.9), "TS897": (162, 12.5)},
    14: {"KMSO": (329,  4.7), "MPOI": (272,  6.9), "BLMM8": (257, 11.2), "TS897": (161,  7.3)},
    15: {"KMSO": (282, 12.5), "MPOI": (278, 16.3), "BLMM8": (266, 26.9), "TS897": (  2,  2.8)},
    16: {"KMSO": (290, 14.3), "MPOI": (272, 10.9), "BLMM8": (261, 24.9), "TS897": (344,  5.5)},
    17: {"KMSO": (297, 15.8), "MPOI": (284, 14.9), "BLMM8": (270, 21.0), "TS897": (295, 14.7)},
    18: {"KMSO": (278, 20.8), "MPOI": (267, 19.8), "BLMM8": (263, 27.2), "TS897": (263, 16.2)},
    19: {"KMSO": (304, 19.4), "MPOI": (299, 17.8), "BLMM8": (272, 22.4), "TS897": (278, 19.2)},
    20: {"KMSO": (287, 25.9), "MPOI": (284, 24.0), "BLMM8": (271, 23.7), "TS897": (282, 23.2)},
    21: {"KMSO": (283, 25.6), "MPOI": (280, 23.1), "BLMM8": (275, 21.3), "TS897": (283, 18.9)},
}

# ── WindNinja snapshot — init: 315° NW / 29 mph (700 hPa 12z OTX sounding) ──
# 12mi grid, center 46.9/-114.1, DEM shared with Case 1 — windninja_case2_wider.py
# Station coords updated to NIFC-authoritative (2026-05-28):
#   MPOI/Point Six = PNTM8: 47.04136N -113.98631W 7897ft (NOT old assumed 46.876N -114.082W)
#   BLMM8 = foothills SE Missoula: 46.82073N -114.10089W (NOT old 46.832N -114.216W)
# NOTE: HRRR values below still use old coords — re-run hrrr_test.py to update
WINDNINJA = {
    "KMSO":  (314, 28.3),   # 12mi grid — near-ambient valley floor (0.98x)
    "MPOI":  (313, 40.6),   # PNTM8 NIFC coords 7897ft — 40% terrain amplification (1.40x)
    "BLMM8": (320, 29.2),   # NIFC foothills coords — near-ambient (1.01x), sheltered
    "TS897": (323, 27.2),   # Lolo — now captured with 12mi grid (0.94x)
}

# ── Fetch GFS (Open-Meteo historical forecast ~13km) ─────────────────────────
LOCS = {
    "KMSO":  (46.916,    -114.090),
    "MPOI":  (47.04136,  -113.98631),  # PNTM8 NIFC authoritative (updated 2026-05-28)
    "BLMM8": (46.82073,  -114.10089),  # NIFC foothills SE (updated 2026-05-28, was 46.832/-114.216)
    "TS897": (46.749,    -114.066),
}
print("Fetching GFS...", end=" ", flush=True)
gfs = {}
for name, (lat, lon) in LOCS.items():
    r = requests.get("https://historical-forecast-api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon,
        "start_date": "2025-12-17", "end_date": "2025-12-17",
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "mph", "timezone": "UTC",
        "models": "gfs_global",
    }, timeout=20)
    h = r.json().get("hourly", {})
    gfs[name] = {"spd": h.get("wind_speed_10m", []), "dir": h.get("wind_direction_10m", [])}
print("done.")

# ── Fetch KMSO obs (IEM ASOS, best obs near :53 each hour) ───────────────────
print("Fetching KMSO obs...", end=" ", flush=True)
r2 = requests.get("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", params={
    "station": "MSO", "data": "all",
    "year1": "2025", "month1": "12", "day1": "17",
    "year2": "2025", "month2": "12", "day2": "17",
    "tz": "UTC", "format": "onlycomma", "latlon": "no",
    "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
}, timeout=20)
kmso = {}
for line in r2.text.split("\n")[1:]:
    cols = line.strip().split(",")
    if len(cols) < 12 or "2025-12-17" not in (cols[1] if len(cols) > 1 else ""):
        continue
    try:
        dt = datetime.fromisoformat(cols[1]); h = dt.hour
        spd  = float(cols[6])  * 1.15078 if cols[6]  not in ("M", "") else None
        gust = float(cols[11]) * 1.15078 if cols[11] not in ("M", "") else None
        dirn = float(cols[5])             if cols[5]  not in ("M", "") else None
        pri  = abs(dt.minute - 53)
        if h not in kmso or pri < kmso[h]["p"]:
            kmso[h] = {"s": spd, "g": gust, "d": dirn, "p": pri}
    except Exception:
        pass
print("done.")

# ── Fetch BLMM8 obs (Synoptic Data, hourly at :01) ────────────────────────────
print("Fetching BLMM8 obs...", end=" ", flush=True)
r3 = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params={
    "stid": "BLMM8", "start": "202512171000", "end": "202512172200",
    "vars": "wind_speed,wind_gust,wind_direction", "units": "english", "token": TOKEN,
}, timeout=30)
blmm8 = {}
stn = r3.json().get("STATION", [{}])[0]
obs = stn.get("OBSERVATIONS", {})
spds  = obs.get("wind_speed_set_1", [])
gusts = obs.get("wind_gust_set_1", [])
dirs  = obs.get("wind_direction_set_1", [])
for i, t in enumerate(obs.get("date_time", [])):
    dt = datetime.fromisoformat(t.replace("Z", ""))
    blmm8[dt.hour] = {
        "s": spds[i]  if i < len(spds)  else None,
        "g": gusts[i] if i < len(gusts) else None,
        "d": dirs[i]  if i < len(dirs)  else None,
    }
print("done.")

# ── Format helpers ────────────────────────────────────────────────────────────
def fd(v):  return f"{v:3.0f}" if v is not None else "  M"
def fs(v):  return f"{v:4.1f}" if v is not None else "   M"
def fg(v):  return f"{v:4.0f}" if v is not None else "   M"
def fds(d, s):   return f"{fd(d)} {fs(s)}"
def fdsg(d,s,g): return f"{fd(d)} {fs(s)} {fg(g)}"

def gd(name, h): lst = gfs[name]["dir"]; return lst[h] if h < len(lst) else None
def gs(name, h): lst = gfs[name]["spd"]; return lst[h] if h < len(lst) else None

def hv(stid, h, idx): return HRRR.get(h, {}).get(stid, (None, None))[idx]

def vec_avg(pairs):
    """Vector-average (dir, spd) pairs — correct for circular direction."""
    valid = [(d, s) for d, s in pairs if d is not None and s is not None]
    if not valid:
        return None, None
    us = [-s * math.sin(math.radians(d)) for d, s in valid]
    vs = [-s * math.cos(math.radians(d)) for d, s in valid]
    mu, mv = sum(us) / len(us), sum(vs) / len(vs)
    spd  = math.sqrt(mu**2 + mv**2)
    dirn = math.degrees(math.atan2(-mu, -mv)) % 360
    return dirn, spd

# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 90)
print("  December 17, 2025 -- Full Wind Comparison: Obs + HRRR 3km + GFS 13km + WindNinja")
print("  700 hPa 12z: 25 kt / 28.8 mph from 315 NW  (OTX = TFX sounding)  |  MST = UTC-7")
print("  WindNinja init: 315 deg / 29 mph  |  Cold pool decoupled 11-13z; coupled 18-21z")
print("=" * 90)

# ── TABLE 1: Observations + HRRR hourly ──────────────────────────────────────
print()
print("  TABLE 1 — Observations vs HRRR 3km (hourly 11-21z)")
print(f"  {'UTC':>3} {'MST':>3} | {'-- KMSO obs 3205ft --':^21} | {'-- BLMM8 obs 3412ft --':^21}"
      f" | {'HRRR':^8} | {'HRRR':^8} | {'HRRR':^8} | {'HRRR':^8}")
print(f"  {'':3} {'':3} | {'Dir   Spd  Gust':^21} | {'Dir   Spd  Gust':^21}"
      f" | {'KMSO':^8} | {'PtSix':^8} | {'BluMt':^8} | {'Lolo':^8}")
print(f"  {'':3} {'':3} | {'':21} | {'':21}"
      f" | {'Dir  Spd':^8} | {'Dir  Spd':^8} | {'Dir  Spd':^8} | {'Dir  Spd':^8}")
print("  " + "-" * 86)

for h in HOURS:
    m = h - 7
    k = kmso.get(h, {})
    b = blmm8.get(h, {})
    print(
        f"  {h:02d}z {m:02d}M"
        f" | {fdsg(k.get('d'), k.get('s'), k.get('g')):^21}"
        f" | {fdsg(b.get('d'), b.get('s'), b.get('g')):^21}"
        f" | {fds(hv('KMSO', h, 0),  hv('KMSO',  h, 1)):^8}"
        f" | {fds(hv('MPOI', h, 0),  hv('MPOI',  h, 1)):^8}"
        f" | {fds(hv('BLMM8',h, 0),  hv('BLMM8', h, 1)):^8}"
        f" | {fds(hv('TS897',h, 0),  hv('TS897', h, 1)):^8}"
    )

# ── TABLE 2: GFS hourly ───────────────────────────────────────────────────────
print()
print("  TABLE 2 — GFS 13km (hourly 11-21z, Open-Meteo historical forecast)")
print(f"  {'UTC':>3} {'MST':>3} | {'GFS KMSO':^8} | {'GFS PtSix':^9} | {'GFS BluMt':^9} | {'GFS Lolo':^8}")
print(f"  {'':3} {'':3} | {'Dir  Spd':^8} | {'Dir  Spd':^9} | {'Dir  Spd':^9} | {'Dir  Spd':^8}")
print("  " + "-" * 52)

for h in HOURS:
    m = h - 7
    print(
        f"  {h:02d}z {m:02d}M"
        f" | {fds(gd('KMSO', h),  gs('KMSO', h)):^8}"
        f" | {fds(gd('MPOI', h),  gs('MPOI', h)):^9}"
        f" | {fds(gd('BLMM8', h), gs('BLMM8', h)):^9}"
        f" | {fds(gd('TS897', h), gs('TS897', h)):^8}"
    )

# ── TABLE 3: WindNinja validation — coupled period (18-21z avg) ───────────────
print()
print("  TABLE 3 — WindNinja Validation: coupled period 18-21z avg (11-14 MST)")
print("  WindNinja initialized at 315 deg NW / 29 mph (free-atmosphere 700 hPa flow)")
print("  Compare against this window: cold pool fully mixed out, surface coupled to aloft")
print()

STATIONS = [
    ("KMSO",  "KMSO  3205ft", "kmso"),
    ("MPOI",  "PtSix 6300ft", None),
    ("BLMM8", "BluMt 3412ft", "blmm8"),
    ("TS897", "Lolo  3200ft", None),
]

print(f"  {'Station':^14} | {'Obs avg 18-21z':^15} | {'HRRR avg 18-21z':^15}"
      f" | {'GFS avg 18-21z':^15} | {'WindNinja':^15}")
print(f"  {'':^14} | {'Dir    Spd':^15} | {'Dir    Spd':^15}"
      f" | {'Dir    Spd':^15} | {'Dir    Spd':^15}")
print("  " + "-" * 82)

for stid, label, obs_src in STATIONS:
    # Obs vector average over coupled hours
    if obs_src == "kmso":
        obs_pairs = [(kmso.get(h, {}).get("d"), kmso.get(h, {}).get("s")) for h in COUP]
    elif obs_src == "blmm8":
        obs_pairs = [(blmm8.get(h, {}).get("d"), blmm8.get(h, {}).get("s")) for h in COUP]
    else:
        obs_pairs = []
    od, os_ = vec_avg(obs_pairs)

    # HRRR vector average
    hrrr_pairs = [(hv(stid, h, 0), hv(stid, h, 1)) for h in COUP]
    hd, hs = vec_avg(hrrr_pairs)

    # GFS vector average
    gfs_pairs = [(gd(stid, h), gs(stid, h)) for h in COUP]
    gd_, gs_ = vec_avg(gfs_pairs)

    # WindNinja (single snapshot, not time-averaged)
    wn = WINDNINJA.get(stid)
    if wn:
        wn_str = f"{fds(wn[0], wn[1]):^15}"
    else:
        wn_str = f"{'[ run WN ]':^15}"

    obs_str = f"{fds(od, os_):^15}" if od is not None else f"{'blocked/no obs':^15}"
    print(
        f"  {label:^14}"
        f" | {obs_str}"
        f" | {fds(hd, hs):^15}"
        f" | {fds(gd_, gs_):^15}"
        f" | {wn_str}"
    )

print()
print("  WindNinja: terrain-resolved snapshot — not a time average.")
print("             If WN run: fill WINDNINJA dict at top of this script, re-run.")
print()
print("  Obs sources:")
print("    KMSO  = IEM ASOS real obs, valley floor 3205ft")
print("    BLMM8 = Synoptic real obs 3412ft (coord uncertainty: may be near E. Missoula)")
print("    MPOI (Point Six 6300ft) = BLOCKED: WRCC >30 day, not in Synoptic network")
print("    TS897 (Lolo Portable)   = BLOCKED: WRCC >30 day, wrong station in Synoptic")
print()
print("  Model sources:")
print("    HRRR = 3km CONUS, 00z run Dec 17 2025, AWS S3 noaa-hrrr-bdp-pds (fetched via Herbie)")
print("    GFS  = Open-Meteo historical forecast archive, ~13km")
print("    WindNinja = terrain-resolved, init 315deg/29mph — install at firelab.org/project/windninja")
