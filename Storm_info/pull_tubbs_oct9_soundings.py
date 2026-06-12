#!/usr/bin/env python3
"""
pull_tubbs_oct9_soundings.py
============================
Pull OAK 700/850 hPa soundings for Oct 9 2017 (Tubbs destructive run day)
and merge into wyoming_soundings.json without overwriting existing entries.

Purpose: Clear the Tubbs withheld status by providing an independent
verification of which pressure level (700 vs 850) matches the observed
NNE wind direction at stations like HWKC1 during the destructive run.
"""
import sys, re, json, time
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://weather.uwyo.edu/wsgi/sounding"

NEW_PULLS = [
    ("OAK_tubbs_oct9_00z", 72493, "2017-10-09 00:00:00", "Tubbs destructive run -- OAK 00z Oct 9"),
    ("OAK_tubbs_oct9_12z", 72493, "2017-10-09 12:00:00", "Tubbs destructive run -- OAK 12z Oct 9"),
]


def fetch_wyoming(datetime_str, wmo_id, retries=3):
    params = {"datetime": datetime_str, "id": wmo_id, "src": "FM35", "type": "TEXT:LIST"}
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=45)
            if r.status_code == 200:
                return r.text, None
            elif r.status_code == 400:
                return None, f"400 -- no data for WMO {wmo_id} at {datetime_str}"
            else:
                return None, f"HTTP {r.status_code}"
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"    Timeout, retrying in {wait}s...")
                time.sleep(wait)
            else:
                return None, "Timeout after all retries"
        except Exception as e:
            return None, str(e)
    return None, "exhausted retries"


def extract_sounding_text(html):
    m = re.search(r'(PRES\s+HGHT\s+TEMP.*?)(?=<h2|</div>|<hr)', html, re.DOTALL)
    if m:
        raw = m.group(1)
        text = re.sub(r'<[^>]+>', '', raw).strip()
        return text, None
    return None, "no PRES/HGHT column header found in HTML"


def parse_column_headers(data_text):
    lines = data_text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'PRES' in stripped and 'HGHT' in stripped:
            cols = stripped.split()
            if i + 1 < len(lines):
                unit_line = lines[i + 1].strip().lower()
                if 'm/s' in unit_line:
                    return cols, 'm/s'
                elif 'kts' in unit_line or 'kt' in unit_line:
                    return cols, 'knots'
            return cols, 'm/s'
    return None, 'unknown'


def parse_sounding(data_text):
    cols, wind_unit = parse_column_headers(data_text)
    lines = data_text.split('\n')
    levels = []
    in_data = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^-+$', stripped):
            if cols:
                in_data = True
            continue
        if not in_data:
            continue
        if stripped.startswith('Station') or '<' in stripped or stripped.startswith('Lifted'):
            break
        parts = stripped.split()
        if len(parts) < 7:
            continue
        try:
            pres = float(parts[0])
            hght = float(parts[1])
            temp = float(parts[2])
            drct = float(parts[6]) if parts[6] != 'M' else None
            spd_raw = float(parts[7]) if parts[7] != 'M' else None
            spd_mph = None
            if spd_raw is not None:
                if wind_unit == 'm/s':
                    spd_mph = spd_raw * 2.23694
                elif wind_unit == 'knots':
                    spd_mph = spd_raw * 1.15078
            levels.append({'pres_hPa': pres, 'hght_m': hght, 'temp_c': temp,
                            'drct_deg': drct, 'spd_raw': spd_raw, 'spd_mph': spd_mph,
                            'wind_unit': wind_unit})
        except (ValueError, IndexError):
            continue
    return {'levels': levels, 'wind_unit': wind_unit}


def get_level(levels, target_hPa, tol=25.0):
    best, best_diff = None, float('inf')
    for lev in levels:
        diff = abs(lev['pres_hPa'] - target_hPa)
        if diff < best_diff and diff <= tol:
            best_diff = diff
            best = lev
    return best


def find_inversion(levels, search_top_hPa=600.0):
    levs = [l for l in levels if l['pres_hPa'] >= search_top_hPa and l['temp_c'] is not None]
    levs.sort(key=lambda x: x['pres_hPa'], reverse=True)
    for i in range(1, len(levs)):
        prev, curr = levs[i - 1], levs[i]
        if curr['temp_c'] > prev['temp_c'] and curr['pres_hPa'] < prev['pres_hPa']:
            return {
                'base_hPa': prev['pres_hPa'], 'top_hPa': curr['pres_hPa'],
                'base_hght_m': prev['hght_m'], 'top_hght_m': curr['hght_m'],
                'strength_c': curr['temp_c'] - prev['temp_c'],
            }
    return None


if __name__ == "__main__":
    json_path = "wyoming_soundings.json"
    try:
        with open(json_path) as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing entries from {json_path}")
    except FileNotFoundError:
        existing = {}
        print("No existing soundings file; creating new.")

    print()
    new_results = {}

    for label, wmo, dt_str, note in NEW_PULLS:
        print(f"Fetching {label}  ({dt_str})")
        html, err = fetch_wyoming(dt_str, wmo)
        if err:
            print(f"  FAIL: {err}\n")
            continue

        data_text, parse_err = extract_sounding_text(html)
        if parse_err or not data_text:
            print(f"  PARSE FAIL: {parse_err}")
            with open(f"wyoming_raw_{label}.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  Saved raw HTML to wyoming_raw_{label}.html\n")
            continue

        sounding = parse_sounding(data_text)
        levels = sounding['levels']
        wind_unit = sounding['wind_unit']

        l700 = get_level(levels, 700)
        l850 = get_level(levels, 850)
        inv = find_inversion(levels)

        print(f"  wind_unit={wind_unit}  levels_parsed={len(levels)}")
        if l700:
            print(f"  700 hPa: {l700['spd_mph']:.1f} mph @ {l700['drct_deg']:.0f}°  hgt={l700['hght_m']:.0f}m")
        if l850:
            print(f"  850 hPa: {l850['spd_mph']:.1f} mph @ {l850['drct_deg']:.0f}°  hgt={l850['hght_m']:.0f}m")
        if inv:
            print(f"  Inversion: {inv['base_hght_m']:.0f}m – {inv['top_hght_m']:.0f}m  (+{inv['strength_c']:.1f}°C)")
        else:
            print("  Inversion: none detected")
        print()

        new_results[label] = {
            'wmo': wmo, 'datetime': dt_str, 'note': note,
            'wind_unit': wind_unit,
            '700hPa': {
                'spd_mph': l700['spd_mph'] if l700 else None,
                'spd_raw': l700['spd_raw'] if l700 else None,
                'drct_deg': l700['drct_deg'] if l700 else None,
                'hght_m': l700['hght_m'] if l700 else None,
                'temp_c': l700['temp_c'] if l700 else None,
            },
            '850hPa': {
                'spd_mph': l850['spd_mph'] if l850 else None,
                'spd_raw': l850['spd_raw'] if l850 else None,
                'drct_deg': l850['drct_deg'] if l850 else None,
                'hght_m': l850['hght_m'] if l850 else None,
                'temp_c': l850['temp_c'] if l850 else None,
            },
            'inversion': inv,
        }
        time.sleep(3)

    # Merge and save
    merged = {**existing, **new_results}
    with open(json_path, "w") as f:
        json.dump(merged, f, indent=2, default=str)
    print(f"Saved {len(merged)} total entries to {json_path}")

    # Summary comparison
    print()
    print("=" * 70)
    print("  DIRECTION VERIFICATION — Tubbs Oct 9 destructive run")
    print("  HWKC1 obs peak: 48 mph @ 35.7° NNE  (06:56Z Oct 9)")
    print("  WISC1 obs peak: 35 mph @ 15.3° NNE  (07:36Z Oct 9)")
    print("=" * 70)
    for label in ["OAK_tubbs_oct9_00z", "OAK_tubbs_oct9_12z"]:
        if label in new_results:
            r = new_results[label]
            l7, l8 = r['700hPa'], r['850hPa']
            t = r['datetime']
            spd7 = f"{l7['spd_mph']:.1f}mph@{l7['drct_deg']:.0f}°" if l7['spd_mph'] else "---"
            spd8 = f"{l8['spd_mph']:.1f}mph@{l8['drct_deg']:.0f}°" if l8['spd_mph'] else "---"
            print(f"  {t[:13]}  700={spd7:20}  850={spd8}")
