"""
Pull REV (Reno NV, WMO 72489) soundings for 2018-11-08 00z and 12z
from Wyoming wsgi (src=FM35). Append to wyoming_soundings.json.

Alias check: REV is in the Great Basin at ~1516m elevation.
Surface temperature in early November should be ~5-15C; Canadian CWMJ
data would show obviously wrong surface conditions. Station WMO must
be 72489 in the HTML sidebar to confirm it's real REV data.
"""
import sys, re, json, time, requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://weather.uwyo.edu/wsgi/sounding"
OUT  = "wyoming_soundings.json"
MS_TO_MPH = 2.23694
G0 = 9.80665

# Reuse parsing from wyoming_sounding_pull.py
def fetch_wyoming(dt_str, wmo, retries=3):
    params = {"datetime": dt_str, "id": wmo, "src": "FM35", "type": "TEXT:LIST"}
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=45)
            if r.status_code == 200: return r.text, None
            if r.status_code == 400: return None, f"400 no data"
            return None, f"HTTP {r.status_code}"
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f"  Timeout attempt {attempt+1}, retrying in 15s...")
                time.sleep(15)
            else: return None, "Timeout"
    return None, "exhausted retries"

def extract_data(html):
    m = re.search(r"(PRES\s+HGHT\s+TEMP.*?)(?=<h2|</div>|<hr)", html, re.DOTALL)
    if not m: return None, "no PRES/HGHT header found"
    return re.sub(r"<[^>]+>", "", m.group(1)).strip(), None

def parse_sounding(data_text):
    lines = data_text.split("\n")
    wind_unit = "unknown"
    cols = None
    in_data = False
    levels = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "PRES" in stripped and "HGHT" in stripped:
            cols = stripped.split()
            if i + 1 < len(lines):
                uline = lines[i+1].strip().lower()
                wind_unit = "m/s" if "m/s" in uline else ("knots" if "kt" in uline else "unknown")
            if "SPED" in stripped: wind_unit = "m/s"
            continue
        if re.match(r"^-+$", stripped):
            if cols: in_data = True
            continue
        if not in_data: continue
        if stripped.startswith("Station") or "<" in stripped or stripped.startswith("Lifted"):
            break
        parts = stripped.split()
        if len(parts) < 7: continue
        try:
            pres = float(parts[0]); hght = float(parts[1])
            temp = float(parts[2]); drct = float(parts[6])
            spd_raw = float(parts[7]) if parts[7] != "M" else None
            spd_mph = None
            if spd_raw is not None:
                spd_mph = spd_raw * (2.23694 if wind_unit == "m/s" else 1.15078)
            levels.append({"pres_hPa": pres, "hght_m": hght, "temp_c": temp,
                           "drct_deg": drct, "spd_raw": spd_raw, "spd_mph": spd_mph})
        except (ValueError, IndexError): continue
    return {"levels": levels, "wind_unit": wind_unit}

def get_level(levels, target_hPa, tol=25.0):
    best, best_diff = None, float("inf")
    for lev in levels:
        diff = abs(lev["pres_hPa"] - target_hPa)
        if diff < best_diff and diff <= tol:
            best_diff = diff; best = lev
    return best

def find_inversion(levels):
    levs = [l for l in levels if l["pres_hPa"] >= 600 and l["temp_c"] is not None]
    levs.sort(key=lambda x: x["pres_hPa"], reverse=True)
    for i in range(1, len(levs)-1):
        prev, curr = levs[i-1], levs[i]
        if curr["temp_c"] > prev["temp_c"] and curr["pres_hPa"] < prev["pres_hPa"]:
            return {"base_hPa": prev["pres_hPa"], "top_hPa": curr["pres_hPa"],
                    "base_hght_m": prev["hght_m"], "top_hght_m": curr["hght_m"],
                    "strength_c": curr["temp_c"] - prev["temp_c"]}
    return None

WMO = 72489  # REV Reno NV
PULLS = [
    ("REV_camp_00z", "2018-11-08 00:00:00", "Camp Fire REV 00z — Wyoming wsgi src=FM35"),
    ("REV_camp_12z", "2018-11-08 12:00:00", "Camp Fire REV 12z — Wyoming wsgi src=FM35"),
]

existing = {}
try:
    with open(OUT) as f: existing = json.load(f)
    print(f"Loaded {OUT}: {len(existing)} existing records")
except FileNotFoundError:
    print(f"{OUT} not found — will create")

for key, dt_str, note in PULLS:
    print(f"\nFetching {key} ({dt_str}) ...")
    html, err = fetch_wyoming(dt_str, WMO)
    if err:
        print(f"  FAIL: {err} — STOP, do not store")
        sys.exit(1)

    # Alias check: confirm HTML mentions station 72489, not CWMJ
    if "72489" not in html and "CWMJ" in html.upper():
        print(f"  ALIAS DETECTED: response contains CWMJ, not WMO 72489 — STOP")
        sys.exit(1)
    if "72489" not in html:
        print(f"  WARNING: WMO 72489 not found in HTML. Inspecting ...")
        sidebar = re.findall(r"<li>.*?</li>", html, re.DOTALL)[:3]
        for s in sidebar: print(f"    {re.sub(r'<[^>]+>', '', s).strip()}")
        # surface temp sanity check
    else:
        print(f"  Station WMO 72489 confirmed in HTML")

    data_text, parse_err = extract_data(html)
    if parse_err:
        print(f"  PARSE FAIL: {parse_err} — STOP")
        sys.exit(1)

    sounding = parse_sounding(data_text)
    levels = sounding["levels"]
    wind_unit = sounding["wind_unit"]
    print(f"  Parsed {len(levels)} levels, wind_unit={wind_unit}")

    # Surface sanity: Reno Nov 2018 surface temp should be >-10C and <25C
    if levels:
        sfc = levels[0]
        print(f"  Surface: {sfc['pres_hPa']} hPa, {sfc['hght_m']:.0f}m, {sfc['temp_c']:.1f}C")
        if not (-10 < sfc["temp_c"] < 25):
            print(f"  SUSPECT surface temp {sfc['temp_c']:.1f}C — may not be Reno — STOP")
            sys.exit(1)

    l700 = get_level(levels, 700)
    l850 = get_level(levels, 850)
    inv   = find_inversion(levels)

    if not l700:
        print("  ERROR: no 700 hPa level found — STOP")
        sys.exit(1)

    print(f"  700 hPa: {l700['spd_mph']:.1f} mph ({l700['spd_raw']} {wind_unit}) "
          f"@ {l700['drct_deg']:.0f}deg  hgt={l700['hght_m']:.0f}m")
    if l850:
        print(f"  850 hPa: {l850['spd_mph']:.1f} mph ({l850['spd_raw']} {wind_unit}) "
              f"@ {l850['drct_deg']:.0f}deg  hgt={l850['hght_m']:.0f}m")
    if inv:
        print(f"  Inversion: base {inv['base_hght_m']:.0f}m top {inv['top_hght_m']:.0f}m "
              f"(+{inv['strength_c']:.1f}C)")
    else:
        print("  Inversion: none detected")

    record = {
        "wmo": WMO, "datetime": dt_str, "note": note, "wind_unit": wind_unit,
        "700hPa": {
            "spd_mph": l700["spd_mph"], "spd_raw": l700["spd_raw"],
            "drct_deg": l700["drct_deg"], "hght_m": l700["hght_m"],
            "temp_c": l700["temp_c"],
        },
        "850hPa": {
            "spd_mph": l850["spd_mph"] if l850 else None,
            "spd_raw": l850["spd_raw"] if l850 else None,
            "drct_deg": l850["drct_deg"] if l850 else None,
            "hght_m": l850["hght_m"] if l850 else None,
        } if l850 else None,
        "inversion": inv,
    }
    existing[key] = record
    print(f"  Added key '{key}' to {OUT}")
    time.sleep(3)

with open(OUT, "w") as f:
    json.dump(existing, f, indent=2)
print(f"\nSaved {OUT} with {len(existing)} records")
