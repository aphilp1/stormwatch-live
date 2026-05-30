#!/usr/bin/env python3
"""
wyoming_sounding_pull.py
========================
Pull radiosonde soundings from the University of Wyoming upper-air archive
using the new wsgi/sounding endpoint (replaces the defunct cgi-bin/sounding.py).

Soundings needed:
  VBG  72393  Vandenberg CA  -- Thomas Fire Dec 4 2017 12z (break IEM alias)
  OAK  72493  Oakland CA     -- Kincade Oct 27 2019 00z + 12z (peak-wind day)
  OAK  72493  Oakland CA     -- Tubbs Oct 8 2017 00z + 12z (verify inversion source)

Known issues:
  - Wyoming returns HTML pages; data is in the <h2>/<p> section, NOT <pre>
  - New format: winds now in m/s (not knots) -- confirmed by column header
  - src=FM35 required for standard RAOB data (not src=UNKNOWN)
  - Wyoming rate-limits: use retry with backoff
  - IEM VBG alias confirmed: IEM returned CWMJ for any VBG/NKX/SFO/REV query on
    2017-12-04 -- all identical (CWMJ, a Canadian station, 195m 0C surface).
    Wyoming VBG 12z Dec 4 shows 3081m, 3.8C, 310deg, 14.9 [m/s or kt?]

Units question:
  Wyoming announcement: "wind speeds are now reported in m/s rather than knots"
  Column header parse determines actual unit -- recorded in output.

Run: python wyoming_sounding_pull.py
"""

import sys, re, json, time
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://weather.uwyo.edu/wsgi/sounding"

PULLS = [
    # (label, wmo_id, datetime_str, note)
    ("VBG_thomas_12z",   72393, "2017-12-04 12:00:00", "Thomas Fire -- VBG west-side ref (IEM aliased)"),
    ("VBG_thomas_00z",   72393, "2017-12-04 00:00:00", "Thomas Fire -- VBG west-side ref 00z (may not exist)"),
    ("OAK_kincade_00z",  72493, "2019-10-27 00:00:00", "Kincade peak-wind day 00z"),
    ("OAK_kincade_12z",  72493, "2019-10-27 12:00:00", "Kincade peak-wind day 12z"),
    ("OAK_tubbs_00z",    72493, "2017-10-08 00:00:00", "Tubbs -- verify inversion (may 400)"),
    ("OAK_tubbs_12z",    72493, "2017-10-08 12:00:00", "Tubbs -- verify inversion 12z (may 400)"),
    # Cross-check: Missoula OTX Dec 17 2025 -- known from IEM (25 kt @ 315) -- verify units
    ("OTX_missoula_12z", 72786, "2025-12-17 12:00:00", "Missoula NW flow -- known 25 kt @ 315 (unit check)"),
]


def fetch_wyoming(datetime_str: str, wmo_id: int, retries: int = 3) -> tuple[str | None, str | None]:
    """Fetch Wyoming sounding HTML. Returns (html_text, error_msg)."""
    params = {
        "datetime": datetime_str,
        "id": wmo_id,
        "src": "FM35",
        "type": "TEXT:LIST",
    }
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
                print(f"    Timeout (attempt {attempt+1}), retrying in {wait}s ...")
                time.sleep(wait)
            else:
                return None, "Timeout after all retries"
        except Exception as e:
            return None, str(e)
    return None, "exhausted retries"


def extract_sounding_text(html: str) -> tuple[str | None, str | None]:
    """
    Extract the plain-text sounding data from Wyoming HTML (new wsgi format).
    Returns (data_text, error_msg).

    New Wyoming wsgi format: data is NOT in <pre> tags. It appears as:
      PRES   HGHT   TEMP   DWPT   RELH   MIXR   DRCT   SPED ...  (column header)
      hPa      m      C      C    ...    deg    m/s  ...           (units row)
      ---...                                                        (dashes)
      1003.0   121   9.6 ...                                        (data rows)

    The column is SPED (not SKNT), units are m/s (not knots) -- confirmed 2026-05-30.
    """
    # Find the data section starting with "PRES" column header
    m = re.search(r'(PRES\s+HGHT\s+TEMP.*?)(?=<h2|</div>|<hr)', html, re.DOTALL)
    if m:
        raw = m.group(1)
        # Strip any HTML tags that may appear in the data section
        text = re.sub(r'<[^>]+>', '', raw)
        text = text.strip()
        return text, None

    return None, "no PRES/HGHT column header found in HTML"


def parse_column_headers(data_text: str) -> tuple[list[str] | None, str]:
    """
    Find the column header row and determine wind units.
    New Wyoming format has two header rows:
      Row 1: PRES  HGHT  TEMP  DWPT  RELH  MIXR  DRCT  SPED  THTA  THTE  THTV
      Row 2: hPa   m     C     C     %     g/kg  deg   m/s   K     K     K
    The unit 'm/s' appears in row 2 if the new format is in use.
    """
    lines = data_text.split('\n')
    cols = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'PRES' in stripped and 'HGHT' in stripped:
            cols = stripped.split()
            # Check the NEXT line for unit labels
            if i + 1 < len(lines):
                unit_line = lines[i + 1].strip().lower()
                if 'm/s' in unit_line:
                    return cols, 'm/s'
                elif 'kts' in unit_line or 'kt' in unit_line:
                    return cols, 'knots'
            # Fallback: check column name
            if 'SPED' in stripped:
                return cols, 'm/s'
            elif 'SKNT' in stripped:
                return cols, 'knots'
            return cols, 'unknown'
    return None, 'unknown'


def parse_sounding(data_text: str) -> dict:
    """Parse Wyoming TEXT:LIST sounding into levels."""
    cols, wind_unit = parse_column_headers(data_text)

    lines = data_text.split('\n')
    levels = []
    in_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Start data after the dashed separator line
        if re.match(r'^-+$', stripped):
            if cols:
                in_data = True
            continue

        if not in_data:
            continue

        # Stop at next section header
        if stripped.startswith('Station') or '<' in stripped or stripped.startswith('Lifted'):
            break

        parts = stripped.split()
        if len(parts) < 7:
            continue
        try:
            pres = float(parts[0])
            hght = float(parts[1])
            temp = float(parts[2])
            dwpt = float(parts[3])
            drct = float(parts[6]) if parts[6] != 'M' else None
            spd_raw = float(parts[7]) if parts[7] != 'M' else None

            # Convert to mph
            if spd_raw is not None:
                if wind_unit == 'm/s':
                    spd_mph = spd_raw * 2.23694
                elif wind_unit == 'knots':
                    spd_mph = spd_raw * 1.15078
                else:
                    spd_mph = None  # unknown unit -- flag
            else:
                spd_mph = None

            levels.append({
                'pres_hPa': pres,
                'hght_m':   hght,
                'temp_c':   temp,
                'dwpt_c':   dwpt,
                'drct_deg': drct,
                'spd_raw':  spd_raw,
                'spd_mph':  spd_mph,
                'wind_unit': wind_unit,
            })
        except (ValueError, IndexError):
            continue

    return {'levels': levels, 'wind_unit': wind_unit, 'col_headers': cols}


def get_level(levels: list, target_hPa: float, tol: float = 25.0) -> dict | None:
    best, best_diff = None, float('inf')
    for lev in levels:
        diff = abs(lev['pres_hPa'] - target_hPa)
        if diff < best_diff and diff <= tol:
            best_diff = diff
            best = lev
    return best


def find_inversion(levels: list, search_top_hPa: float = 600.0) -> dict | None:
    """Find lowest temperature inversion above surface."""
    levs = [l for l in levels if l['pres_hPa'] >= search_top_hPa and l['temp_c'] is not None]
    levs.sort(key=lambda x: x['pres_hPa'], reverse=True)  # surface → top
    for i in range(1, len(levs) - 1):
        prev, curr = levs[i - 1], levs[i]
        if curr['temp_c'] > prev['temp_c'] and curr['pres_hPa'] < prev['pres_hPa']:
            return {
                'base_hPa':   prev['pres_hPa'],
                'top_hPa':    curr['pres_hPa'],
                'base_hght_m': prev['hght_m'],
                'top_hght_m':  curr['hght_m'],
                'strength_c':  curr['temp_c'] - prev['temp_c'],
            }
    return None


if __name__ == "__main__":
    print("=" * 72)
    print("  WYOMING SOUNDING PULL (new wsgi endpoint)")
    print("  Fixing: VBG IEM alias, Kincade date, Tubbs inversion verification")
    print("=" * 72)
    print()

    results = {}

    for label, wmo, dt_str, note in PULLS:
        print(f"  Fetching {label}  (WMO {wmo}, {dt_str})")
        print(f"    Note: {note}")

        html, err = fetch_wyoming(dt_str, wmo)
        if err:
            print(f"    FAIL: {err}")
            print()
            continue

        data_text, parse_err = extract_sounding_text(html)
        if parse_err or not data_text:
            print(f"    PARSE FAIL: {parse_err}")
            # Save raw for debugging
            with open(f"wyoming_raw_{label}.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"    Saved raw HTML to wyoming_raw_{label}.html for inspection")
            print()
            continue

        sounding = parse_sounding(data_text)
        levels = sounding['levels']
        wind_unit = sounding['wind_unit']
        col_headers = sounding['col_headers']

        print(f"    Wind unit from header: {wind_unit}  |  levels parsed: {len(levels)}")
        if col_headers:
            print(f"    Column headers: {col_headers}")

        l700 = get_level(levels, 700)
        l850 = get_level(levels, 850)
        l500 = get_level(levels, 500)
        inv   = find_inversion(levels)

        if l700:
            spd_s = f"{l700['spd_mph']:.1f} mph" if l700['spd_mph'] else f"{l700['spd_raw']} {wind_unit}"
            dir_s = f"{l700['drct_deg']:.0f}°" if l700['drct_deg'] is not None else "---"
            hgt_s = f"{l700['hght_m']:.0f}m"
            print(f"    700hPa: {spd_s} @ {dir_s}  hgt={hgt_s}  temp={l700['temp_c']:.1f}°C")
        else:
            print("    700hPa: not found")

        if inv:
            print(f"    Inversion: base {inv['base_hght_m']:.0f}m – top {inv['top_hght_m']:.0f}m  "
                  f"(+{inv['strength_c']:.1f}°C)")
        else:
            print("    Inversion: none detected")

        # Cross-check for unit calibration (OTX Missoula -- known 25 kt @ 315)
        if 'missoula' in label and l700:
            print(f"    UNIT CHECK: IEM source = 28.8 mph (25 kt) @ 315°")
            print(f"    Wyoming raw = {l700['spd_raw']} {wind_unit} @ {l700['drct_deg']}°")
            if l700['spd_raw']:
                kt_interp = l700['spd_raw'] * 1.15078
                ms_interp = l700['spd_raw'] * 2.23694
                print(f"    If knots: {kt_interp:.1f} mph | If m/s: {ms_interp:.1f} mph")
                print(f"    Expected ~28.8 mph -> best interpretation: "
                      f"{'knots' if abs(kt_interp - 28.8) < abs(ms_interp - 28.8) else 'm/s'}")

        results[label] = {
            'wmo': wmo, 'datetime': dt_str, 'note': note,
            'wind_unit': wind_unit,
            '700hPa': {
                'spd_mph': l700['spd_mph'] if l700 else None,
                'spd_raw': l700['spd_raw'] if l700 else None,
                'dir_deg': l700['drct_deg'] if l700 else None,
                'hght_m':  l700['hght_m'] if l700 else None,
                'temp_c':  l700['temp_c'] if l700 else None,
            },
            'inversion': inv,
        }

        print()
        time.sleep(3)  # be polite to Wyoming server

    # Save
    with open("wyoming_soundings.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("  Saved to wyoming_soundings.json")
    print()

    # Summary
    print("=" * 72)
    print("  SUMMARY TABLE")
    print("=" * 72)
    hdr = f"  {'Label':25} | {'700hPa speed':14} | {'Dir':6} | {'Hgt':8} | Inversion"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for label, r in results.items():
        l7 = r['700hPa']
        inv = r['inversion']
        spd = f"{l7['spd_mph']:.1f} mph" if l7['spd_mph'] else "---"
        dr  = f"{l7['dir_deg']:.0f}°" if l7['dir_deg'] else "---"
        hgt = f"{l7['hght_m']:.0f}m" if l7['hght_m'] else "---"
        inv_s = (f"+{inv['strength_c']:.1f}°C @{inv['base_hght_m']:.0f}m"
                 if inv else "none")
        print(f"  {label:25} | {spd:14} | {dr:6} | {hgt:8} | {inv_s}")
