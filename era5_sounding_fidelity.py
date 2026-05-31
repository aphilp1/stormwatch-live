#!/usr/bin/env python
"""
era5_sounding_fidelity.py  v2 — Trust-or-flag ERA5 as a BC source.

Changes from v1:
  - Observed values READ from wyoming_soundings.json at runtime (no hardcoding).
  - Dates aligned to actual UTC launch days from the JSON.
  - Provenance printed on every number.
  - 700 hPa AND 850 hPa comparison for Camp/REV (BC-level question §2.4).
  - Per-event box boundary so Thomas uses S=34N (VBG inside), others keep S=35N.
  - Soft "good agreement / divergence" tag only — no verdicts written to disk.

Spec: stormwatch_test_protocol.md; era5_bc_characterization.md §8.
Source for observed: wyoming_soundings.json (Wyoming wsgi src=FM35 — canonical).
Run: python era5_sounding_fidelity.py [era5-dir]
"""

import os, sys, json
import numpy as np

try:
    import xarray as xr
except ImportError:
    sys.exit("xarray not installed: conda install -n hrrr311 -c conda-forge xarray netcdf4")

MS_TO_MPH = 2.23694
G0 = 9.80665
ERA5_DIR = sys.argv[1] if len(sys.argv) > 1 else "./era5"

# ---------------------------------------------------------------------------
# Station registry (WMO radiosonde launch sites)
# ---------------------------------------------------------------------------
STATIONS = {
    "REV": {"name": "Reno NV",       "lat": 39.57, "lon": -119.80, "elev_m": 1516, "wmo": 72489},
    "OAK": {"name": "Oakland CA",     "lat": 37.75, "lon": -122.22, "elev_m":    6, "wmo": 72493},
    "VBG": {"name": "Vandenberg CA",  "lat": 34.75, "lon": -120.57, "elev_m":  100, "wmo": 72393},
}

# Per-event: which event file, which station, which UTC dates, box south boundary.
# Dates are the ACTUAL UTC launch days from wyoming_soundings.json — not guesses.
CHECKS = {
    "tubbs_2017":  {"station": "OAK", "date": "2017-10-08", "times": ["00:00", "12:00"],
                    "box_s": 35.0,
                    "wy_keys": ["OAK_tubbs_00z", "OAK_tubbs_12z"]},
    "thomas_2017": {"station": "VBG", "date": "2017-12-04", "times": ["00:00", "12:00"],
                    "box_s": 34.0,  # extended south so VBG (34.75N) is inside
                    "wy_keys": ["VBG_thomas_00z", "VBG_thomas_12z"]},
    "camp_2018":   {"station": "REV", "date": "2018-11-08", "times": ["00:00", "12:00"],
                    "box_s": 35.0,
                    "wy_keys": ["REV_camp_00z", "REV_camp_12z"],
                    "extra_levels": [850]},  # BC-level question: 700 above inversion?
}

# ---------------------------------------------------------------------------
# Load observed from wyoming_soundings.json
# ---------------------------------------------------------------------------
WY_FILE = os.path.join(ERA5_DIR, "..", "wyoming_soundings.json")
if not os.path.exists(WY_FILE):
    WY_FILE = "wyoming_soundings.json"
if not os.path.exists(WY_FILE):
    sys.exit(f"wyoming_soundings.json not found (looked in {WY_FILE!r})")

with open(WY_FILE) as f:
    WY = json.load(f)
print(f"Loaded wyoming_soundings.json ({len(WY)} records): {list(WY)}")

def get_obs(wy_key):
    """Return observed 700hPa values + extra levels from wyoming_soundings.json."""
    if wy_key not in WY:
        return None
    rec = WY[wy_key]
    l7 = rec.get("700hPa", {})
    inv = rec.get("inversion")
    return {
        "source":    f"Wyoming wsgi src=FM35, {rec.get('note','')}",
        "datetime":  rec["datetime"],
        "wind_unit": rec["wind_unit"],
        "700hPa": {
            "spd_mph": l7.get("spd_mph"),
            "drct_deg": l7.get("drct_deg"),
            "hght_m": l7.get("hght_m"),
        },
        "850hPa": rec.get("850hPa"),  # may be None for OAK/VBG records
        "inversion": inv,
    }

# ---------------------------------------------------------------------------
# ERA5 helpers
# ---------------------------------------------------------------------------
def _find(ds, names):
    for n in names:
        if n in ds.variables or n in ds.coords or n in ds.dims:
            return n
    return None

def speed_dir(u, v):
    spd = float(np.sqrt(u**2 + v**2) * MS_TO_MPH)
    drc = float((270.0 - np.degrees(np.arctan2(v, u))) % 360.0)
    return spd, drc

def ang_diff(a, b):
    return abs(((a - b + 180) % 360) - 180)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin(np.radians(lat2-lat1)/2)**2 +
         np.cos(p1)*np.cos(p2)*np.sin(np.radians(lon2-lon1)/2)**2)
    return float(2*R*np.arcsin(np.sqrt(a)))

def era5_at(ds, lat, lon, when_str, levels_hPa):
    """
    Extract ERA5 wind at given (lat, lon, time) for each pressure level.
    Returns dict keyed by level_hPa with {spd_mph, dir_deg, grid, offset_km, era5_time}.
    """
    latn = _find(ds, ["latitude", "lat"])
    lonn = _find(ds, ["longitude", "lon"])
    levn = _find(ds, ["pressure_level", "level"])
    tname = _find(ds, ["valid_time", "time"])
    uvar = _find(ds, ["u", "u_component_of_wind"])
    vvar = _find(ds, ["v", "v_component_of_wind"])
    tvar = _find(ds, ["t", "temperature"])

    lon_q = lon
    if float(ds[lonn].max()) > 180 and lon < 0:
        lon_q = lon % 360

    pt = ds.sel({latn: lat, lonn: lon_q}, method="nearest")
    glat = float(pt[latn]); glon = float(pt[lonn])
    if glon > 180: glon -= 360
    offset_km = haversine_km(lat, lon, glat, glon)

    target_t = np.datetime64(when_str.replace(" ", "T"))
    pt = pt.sel({tname: target_t}, method="nearest")
    era5_time = str(np.datetime_as_string(pt[tname].values, unit="h")) + "Z"
    # warn if ERA5 time is >1h from requested
    diff_h = abs((pt[tname].values - target_t) / np.timedelta64(1, "h"))

    results = {}
    for lev in levels_hPa:
        u = float(pt[uvar].sel({levn: lev}))
        v = float(pt[vvar].sel({levn: lev}))
        spd, drc = speed_dir(u, v)
        results[lev] = {"spd_mph": spd, "dir_deg": drc,
                        "grid": (glat, glon), "offset_km": offset_km,
                        "era5_time": era5_time, "time_offset_h": float(diff_h)}
    return results

def era5_temp_profile(ds, lat, lon, when_str):
    """Return [(hPa, hght_m, tempC)] for all pressure levels at this point+time."""
    latn = _find(ds, ["latitude", "lat"])
    lonn = _find(ds, ["longitude", "lon"])
    levn = _find(ds, ["pressure_level", "level"])
    tname = _find(ds, ["valid_time", "time"])
    tvar = _find(ds, ["t", "temperature"])
    zvar = _find(ds, ["z", "geopotential"])
    if not tvar or not zvar:
        return []

    lon_q = lon if float(ds[lonn].max()) <= 180 else lon % 360
    pt = ds.sel({latn: lat, lonn: lon_q}, method="nearest")
    target_t = np.datetime64(when_str.replace(" ", "T"))
    pt = pt.sel({tname: target_t}, method="nearest")

    levs = [int(x) for x in np.atleast_1d(pt[levn].values)]
    prof = []
    for lev in levs:
        tC = float(pt[tvar].sel({levn: lev})) - 273.15
        h  = float(pt[zvar].sel({levn: lev})) / G0
        prof.append((lev, h, tC))
    prof.sort(key=lambda r: r[1])
    return prof

def detect_inversion_from_profile(prof):
    """First temperature increase with height (coarse 5-level)."""
    for i in range(len(prof)-1):
        _, h0, t0 = prof[i]; _, h1, t1 = prof[i+1]
        if t1 > t0:
            return (h0, h1)
    return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    print()
    for event, c in CHECKS.items():
        st = STATIONS[c["station"]]
        path = os.path.join(ERA5_DIR, f"era5_pl_{event}.nc")
        extra_levels = c.get("extra_levels", [])
        all_levels = [700] + extra_levels

        print(f"{'='*72}")
        print(f"  {event}  |  station {c['station']} ({st['name']}, "
              f"WMO {st['wmo']}, {st['lat']}N {st['lon']}E, elev {st['elev_m']}m)")
        print(f"  Sounding UTC date: {c['date']}  |  ERA5 box S={c['box_s']}N")

        if not os.path.exists(path):
            print(f"  [skip] {path} not found"); print(); continue

        # Coverage check
        in_box = (c["box_s"] <= st["lat"] <= 42.0) and (-124.0 <= st["lon"] <= -117.0)
        if not in_box:
            print(f"  [COVERAGE] {c['station']} ({st['lat']}N) is outside box "
                  f"S={c['box_s']}N. Nearest in-box point used — interpret with care.")

        ds = xr.open_dataset(path)

        for i, t in enumerate(c["times"]):
            wy_key = c["wy_keys"][i]
            obs = get_obs(wy_key)
            when = f"{c['date']} {t}"

            print(f"\n  --- {t}Z ---")

            # Provenance: observed
            if obs:
                o7 = obs["700hPa"]
                inv = obs.get("inversion")
                print(f"  OBS source:  {obs['source']}")
                print(f"  OBS datetime (UTC): {obs['datetime']}")
                print(f"  OBS 700hPa: {o7['spd_mph']:.1f} mph @ {o7['drct_deg']:.0f}deg  "
                      f"hgt={o7['hght_m']:.0f}m  (raw {obs['wind_unit']})")
                if inv:
                    print(f"  OBS inversion: {inv['base_hght_m']:.0f}–{inv['top_hght_m']:.0f}m "
                          f"(+{inv['strength_c']:.1f}C)")
                else:
                    print(f"  OBS inversion: none in file")
            else:
                print(f"  OBS: key '{wy_key}' not in wyoming_soundings.json — skipping comparison")

            # ERA5 extraction
            try:
                era5 = era5_at(ds, st["lat"], st["lon"], when, all_levels)
            except Exception as e:
                print(f"  ERA5: [error] {e}"); continue

            e_ref = era5[700]
            print(f"  ERA5 grid:   ({e_ref['grid'][0]:.2f}N, {e_ref['grid'][1]:.2f}E), "
                  f"{e_ref['offset_km']:.0f} km from station")
            t_tag = "exact" if e_ref['time_offset_h'] < 0.5 else f"+{e_ref['time_offset_h']:.1f}h off"
            print(f"  ERA5 time:   {e_ref['era5_time']} ({t_tag})")
            print(f"  ERA5 700hPa: {e_ref['spd_mph']:.1f} mph @ {e_ref['dir_deg']:.0f}deg")

            # 700 hPa comparison
            if obs:
                o7 = obs["700hPa"]
                ds_spd = e_ref["spd_mph"] - o7["spd_mph"]
                dd     = ang_diff(e_ref["dir_deg"], o7["drct_deg"])
                tag = ("good agreement" if abs(ds_spd) <= 6 and dd <= 25
                       else "DIVERGENCE — investigate")
                print(f"  DELTA 700: speed {ds_spd:+.1f} mph, dir {dd:.0f}deg  -> {tag}")

            # Extra levels (Camp 850 hPa BC-level question)
            for lev in extra_levels:
                e_lev = era5[lev]
                print(f"  ERA5 {lev}hPa: {e_lev['spd_mph']:.1f} mph @ {e_lev['dir_deg']:.0f}deg")
                if obs and obs.get("850hPa") and lev == 850:
                    o8 = obs["850hPa"]
                    if o8 and o8.get("spd_mph") is not None:
                        ds8 = e_lev["spd_mph"] - o8["spd_mph"]
                        dd8 = ang_diff(e_lev["dir_deg"], o8["drct_deg"])
                        tag8 = ("good agreement" if abs(ds8) <= 6 and dd8 <= 25
                                else "DIVERGENCE — investigate")
                        print(f"  OBS  850hPa: {o8['spd_mph']:.1f} mph @ {o8['drct_deg']:.0f}deg  "
                              f"(raw {obs['wind_unit']})")
                        print(f"  DELTA 850: speed {ds8:+.1f} mph, dir {dd8:.0f}deg  -> {tag8}")

            # ERA5 temperature profile + inversion for Camp (BC-level question)
            if extra_levels:
                prof = era5_temp_profile(ds, st["lat"], st["lon"], when)
                era5_inv = detect_inversion_from_profile(prof)
                if era5_inv:
                    print(f"  ERA5 stable layer: {era5_inv[0]:.0f}–{era5_inv[1]:.0f}m (coarse 5-level)")
                else:
                    print(f"  ERA5 stable layer: none resolved (5-level only)")

                # Level-vs-inversion check: is 700 hPa above or below the inversion?
                wy_inv_base = (obs["inversion"]["base_hght_m"]
                               if obs and obs.get("inversion") else None)
                e700_hgt = o7["hght_m"] if obs else None  # use obs height as proxy
                if wy_inv_base and e700_hgt:
                    rel = "ABOVE" if e700_hgt > wy_inv_base else "BELOW"
                    print(f"  BC-level check: 700hPa ({e700_hgt:.0f}m) is {rel} "
                          f"the OBS inversion base ({wy_inv_base:.0f}m)")
                    if rel == "ABOVE":
                        print(f"    -> 700hPa samples free-atmosphere flow, not the sub-inversion "
                              f"gap flow. Consider 850hPa or ridgetop-level wind as BC.")

        ds.close()
        print()

    print("="*72)
    print("READING THE RESULTS:")
    print("  good agreement  -> ERA5 tracks the verified sounding; trusted BC source.")
    print("  DIVERGENCE      -> investigate cause before relying on ERA5 as BC.")
    print("  BC-level check  -> ABOVE inversion = wrong layer for sub-inversion gap flow.")
    print("  No verdicts written to disk. Escalate real divergences per protocol.")

if __name__ == "__main__":
    run()
