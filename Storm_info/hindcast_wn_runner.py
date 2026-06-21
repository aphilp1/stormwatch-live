#!/usr/bin/env python3
"""
hindcast_wn_runner.py v2 — WindNinja hindcast runner (Option B: direct CLI)

Per-station MCP approach replaced: WN CLI runs once per domain on a large cached
DEM; all stations extracted by bilinear interpolation from the full ASC grid.
This eliminates the domain-center artifact that inflated per-station runs.

BC source:  HRRR f00 operational analysis via Herbie (hrrr_bc_pull.py)
            850 hPa offshore events, 700 hPa continental events.
            Time-aligned to each station's peak observation hour (offshore).
DEM source: SRTM cached in WN_CACHE by prior MCP/anchor-test runs.

Validated baseline:
  camp_2018/CBXC1: dem_40.0_-121.3_20mi.tif, bc=32.93@85.8°, WN_err=+6.4 mph
  (wn_anchor_test.py, commit 3f5b0af)

Usage:
  conda run -n hrrr311 python hindcast_wn_runner.py --event camp_2018
  conda run -n hrrr311 python hindcast_wn_runner.py --event camp_2018 --reality-b
  conda run -n hrrr311 python hindcast_wn_runner.py --all
"""

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import glob as glob_mod

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WN_CLI     = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
FETCH_EXE  = r'C:\WindNinja\WindNinja-3.12.2\bin\fetch_dem.exe'
WN_CACHE   = r'C:\temp\windninja_cache'
BASE       = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"

# Offset policy: stations within MIN_OFFSET_KM of their domain center receive
# the OK_LOW_OFFSET flag — extracted, reported, but not pooled into primary
# accuracy metrics. Rationale: SLEC1 at 5.1 km offset vs CBXC1 at 25 km
# showed a 25% ratio swing driven purely by domain centering amplification in
# domainAverageInitialization. 10 km is the cutoff between demonstrably clean
# (JBGC1 at 14 km, CBXC1 at 25 km) and demonstrably risky (SLEC1 at 5 km).
MIN_OFFSET_KM = 10.0
CSV_PATH   = os.path.join(BASE, "hrrr_error_dataset.csv")
OUTPUT_DIR = os.path.join(BASE, "hindcast_grids")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Reality B corrected BC values (two-level pipeline, commit 3f5b0af)
# camp/CBXC1 is KNOWN_FAIL (learned correction overshoots; raw BC already correct)
# thomas/WMSC1 is the PASS case (direction correction cuts error from -10 to+10.5)
REALITY_B_BC = {
    ('camp_2018',       'CBXC1'):  {'speed': 16.6,  'dir':  85.8, 'note': 'flat/2-level KNOWN_FAIL — raw already correct'},
    ('thomas_2017',     'WMSC1'):  {'speed': 49.4,  'dir':  58.0, 'note': '2-level PASS — direction solved'},
    ('woolsey_2018',    'WMSC1'):  {'speed': 47.1,  'dir':  63.6, 'note': 'flat corrected — do-no-harm gate fired on raw'},
    ('missoula_dec2025','PNTM8'):  {'speed': 53.4,  'dir': 275.4, 'note': 'LOO corrected — large improvement'},
}

# Domain configurations per event.
# Each entry: list of {lat, lon, radius_mi} dicts. TIF must exist in WN_CACHE.
# Domain center ≠ station location. Stations must be offset from domain center to
# avoid the terrain-amplification artifact from domainAverageInitialization.
#
# camp primary  (40.0,-121.3) r=20mi: validated; CBXC1 offset=25km (WN_err=+6.4)
# camp eastern  (39.6,-120.9) r=14mi: projected TIF from fetch_dem.exe; SLEC1 offset=5km
# camp southern / northwestern: NEEDS_DOMAIN (DEMs not yet fetched)
EVENT_DOMAINS = {
    'camp_2018': [
        {'lat': 40.0, 'lon': -121.3, 'radius_mi': 20},
        # SLEC1 eastern domain re-placed 2026-06-21: center moved S/W so SLEC1
        # sits ~13km from center (was 5km OK_LOW_OFFSET artifact = inflated 49.3).
        {'lat': 39.55, 'lon': -120.95, 'radius_mi': 15},
        # Added 2026-06-21: cover the 6 previously-uncovered stations, each
        # placed >=10km from its domain center per the offset policy.
        {'lat': 39.5, 'lon': -121.4, 'radius_mi': 20},   # southern: BNGC1, PKCC1, CICC1
        {'lat': 40.0, 'lon': -121.8, 'radius_mi': 20},   # northwest: CSTC1, PSWC1
        {'lat': 40.2, 'lon': -121.3, 'radius_mi': 15},   # northeast: CESC1
    ],
    'thomas_2017': [
        {'lat': 34.6, 'lon': -118.58, 'radius_mi': 20,
         'dem_name': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif'},
    ],
    'woolsey_2018': [
        {'lat': 34.6, 'lon': -118.58, 'radius_mi': 20,
         'dem_name': 'dem_34.60_-118.58_20mi_wmsc1_utm.tif'},
    ],
}

# Stations that require domain DEMs not yet fetched.
# fetch_dem.exe --point <lon> <lat> <buf> <buf> --buf_units miles --src srtm <out.tif>
# All camp_2018 stations now have domains configured in EVENT_DOMAINS (2026-06-21).
NEEDS_DOMAIN = {}

# Run order for --all (tubbs_2017 excluded — direction mismatch pending)
ALL_EVENTS = [
    'camp_2018',
    'kincade_run_2019', 'kincade_ign_2019',
    'woolsey_2018', 'thomas_2017',
    'missoula_dec2025', 'labor_day_or2020',
    'boulder_chin2021', 'marshall_2021',
    'iowa_derecho2020', 'missoula_jul2024',
]


# ── DEM path helpers ──────────────────────────────────────────────────────────

def dem_stem_from_path(dem_path):
    return os.path.splitext(os.path.basename(dem_path))[0]


def get_dem_path(lat, lon, radius_mi, dem_name=None):
    """Return the expected TIF path for a domain config."""
    if dem_name:
        return os.path.join(WN_CACHE, dem_name)
    lat_key = f"{round(round(lat * 10) / 10, 1):.1f}"
    lon_key = f"{round(round(lon * 10) / 10, 1):.1f}"
    return os.path.join(WN_CACHE, f"dem_{lat_key}_{lon_key}_{radius_mi}mi.tif")


def ensure_dem(dem_path, lat, lon, radius_mi):
    """
    Return True if the DEM TIF exists.  If not, fetch it via fetch_dem.exe.
    center lat/lon and radius_mi must match the expected filename.
    """
    if os.path.exists(dem_path):
        return True
    print(f"  [DEM fetch] {os.path.basename(dem_path)}", flush=True)
    args = [FETCH_EXE,
            '--point', str(lon), str(lat), str(radius_mi), str(radius_mi),
            '--buf_units', 'miles', '--src', 'srtm',
            dem_path]
    res = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if res.returncode == 0 and os.path.exists(dem_path):
        print(f"    OK  {os.path.getsize(dem_path)//1024} KB")
        return True
    print(f"    FAIL  {res.stderr[-300:]}")
    return False


def get_event_domains(event_id, stations):
    """Return list of domain dicts with resolved 'dem_path' key."""
    configs = EVENT_DOMAINS.get(event_id)
    if configs is None:
        lat = sum(s['lat'] for s in stations) / len(stations)
        lon = sum(s['lon'] for s in stations) / len(stations)
        lat_r = round(round(lat * 10) / 10, 1)
        lon_r = round(round(lon * 10) / 10, 1)
        configs = [{'lat': lat_r, 'lon': lon_r, 'radius_mi': 20}]
    result = []
    for c in configs:
        d = dict(c)
        d['dem_path'] = get_dem_path(c['lat'], c['lon'], c['radius_mi'],
                                     c.get('dem_name'))
        result.append(d)
    return result


# ── WindNinja CLI ─────────────────────────────────────────────────────────────

def run_wn(dem_path, speed, direction, veg='trees'):
    """
    Run WN CLI on a cached DEM TIF. Returns (vel_asc_path, ang_asc_path).
    Caches by checking for existing output files first.
    Speed rounded to integer mph; direction rounded to integer degrees.
    """
    if not os.path.exists(dem_path):
        print(f"  [ERROR] DEM not found: {dem_path}")
        return None, None

    dem_stem = dem_stem_from_path(dem_path)
    spd_int  = int(round(speed))
    dir_int  = int(round(direction)) % 360

    cached_vel = glob_mod.glob(
        os.path.join(WN_CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    if cached_vel:
        cached_ang = glob_mod.glob(
            os.path.join(WN_CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
        print(f"  [cached] {os.path.basename(cached_vel[0])}")
        return cached_vel[0], (cached_ang[0] if cached_ang else None)

    args = [
        WN_CLI, '--num_threads', '6',
        '--elevation_file',           dem_path,
        '--initialization_method',    'domainAverageInitialization',
        '--input_speed',              str(spd_int),
        '--input_speed_units',        'mph',
        '--input_direction',          str(dir_int),
        '--input_wind_height',        '10',
        '--units_input_wind_height',  'm',
        '--uni_air_temp',             '50',
        '--air_temp_units',           'F',
        '--uni_cloud_cover',          '0.1',
        '--cloud_cover_units',        'fraction',
        '--vegetation',               veg,
        '--mesh_choice',              'coarse',
        '--output_wind_height',       '10',
        '--units_output_wind_height', 'm',
        '--output_speed_units',       'mph',
        '--output_path',              WN_CACHE,
        '--write_ascii_output',       'true',
        '--ascii_out_json',           '0',
        '--ascii_out_4326',           '1',
    ]
    print(f"  Running WN: {spd_int} mph @ {dir_int}° on {dem_stem}...", end=' ', flush=True)
    res = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        print(f"ERROR\n  WN stderr: {res.stderr[-600:]}")
        return None, None
    print("done")

    vel = glob_mod.glob(
        os.path.join(WN_CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_vel-4326.asc'))
    ang = glob_mod.glob(
        os.path.join(WN_CACHE, f'{dem_stem}_{dir_int}_{spd_int}_*_ang-4326.asc'))
    if not vel:
        print(f"  [ERROR] No vel ASC found after WN run. stdout: {res.stdout[-400:]}")
    return (vel[0] if vel else None), (ang[0] if ang else None)


# ── ASC readers ───────────────────────────────────────────────────────────────

def read_asc_header(path):
    """Return header dict from ASC file without loading full data array."""
    hdr = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
                if len(hdr) >= 6:
                    break
    return hdr


def asc_bounds(path):
    """Return (lat_min, lat_max, lon_min, lon_max) from ASC header."""
    h = read_asc_header(path)
    xll   = h['xllcorner']; yll = h['yllcorner']
    cell  = h['cellsize']
    nrows = int(h['nrows']); ncols = int(h['ncols'])
    return yll, yll + nrows * cell, xll, xll + ncols * cell


def read_asc_full(path):
    """Parse ASC file into (header_dict, numpy_array)."""
    hdr, data = {}, []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
                hdr[parts[0].lower()] = float(parts[1])
            else:
                try:
                    data.append([float(v) for v in parts])
                except ValueError:
                    pass
    return hdr, np.array(data)


def read_asc_at(path, lat, lon):
    """
    Bilinear interpolation of ASC grid value at exact lat/lon.
    Returns None for: missing file, outside grid bounds, or nodata cell.
    NEVER extrapolates — a coerced value is worse than an explicit None.
    """
    if path is None or not os.path.exists(path):
        return None
    hdr, arr = read_asc_full(path)
    nrows  = int(hdr['nrows']); ncols = int(hdr['ncols'])
    xll    = hdr['xllcorner']; yll   = hdr['yllcorner']
    cell   = hdr['cellsize']
    nodata = hdr.get('nodata_value', -9999)

    col_f = (lon - xll) / cell
    row_f = (nrows - 1) - (lat - yll) / cell

    # Strict bounds: must be within the grid for valid bilinear interpolation.
    # Anything outside returns None — never clamp and extrapolate.
    if not (0.0 <= col_f <= ncols - 1 and 0.0 <= row_f <= nrows - 1):
        return None

    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols - 2))
    ri = max(0, min(ri, nrows - 2))

    val = (arr[ri,   ci  ] * (1 - rr) * (1 - cr) +
           arr[ri,   ci+1] * (1 - rr) * cr        +
           arr[ri+1, ci  ] * rr       * (1 - cr)  +
           arr[ri+1, ci+1] * rr       * cr)
    return float(val) if abs(val - nodata) > 1 else None


def asc_to_vectors(vel_path, ang_path, target_per_axis=20):
    """
    Sample the full ASC grid for map display.
    step is computed so roughly target_per_axis samples appear in the shorter axis.
    For a 63-cell coarse mesh (step=3): ~21×21 = ~441 vectors.
    For a 700-cell fine mesh (step=35): ~20×20 = ~400 vectors.
    """
    if vel_path is None or not os.path.exists(vel_path):
        return []
    hdr_v, arr_v = read_asc_full(vel_path)
    hdr_a, arr_a = (read_asc_full(ang_path)
                    if ang_path and os.path.exists(ang_path)
                    else ({}, None))
    nrows  = int(hdr_v['nrows']); ncols = int(hdr_v['ncols'])
    xll    = hdr_v['xllcorner']; yll   = hdr_v['yllcorner']
    cell   = hdr_v['cellsize']
    nodata = hdr_v.get('nodata_value', -9999)

    step = max(1, min(nrows, ncols) // target_per_axis)

    vectors = []
    for ri in range(0, nrows, step):
        for ci in range(0, ncols, step):
            spd = float(arr_v[ri, ci])
            if abs(spd - nodata) < 1 or spd < 0:
                continue
            # row 0 = top (max lat); convert to cell-center lat/lon
            lat = yll + (nrows - ri - 0.5) * cell
            lon = xll + (ci + 0.5) * cell
            ang = float(arr_a[ri, ci]) if arr_a is not None else None
            vectors.append({'lat': round(lat, 5), 'lon': round(lon, 5),
                            'speed': round(spd, 2), 'dir': round(ang, 1) if ang else None})
    return vectors


# ── CSV loader ────────────────────────────────────────────────────────────────

def load_event_stations(event_id):
    """Load KEEP stations with BC and obs for the given event."""
    rows = []
    seen = set()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['event_id'] != event_id:
                continue
            if r.get('qc_flag', '') == 'DROP':
                continue
            key = (r['event_id'], r['stid'])
            if key in seen:
                continue
            seen.add(key)
            if r.get('bc_speed', '') in ('', 'NEEDS_BC'):
                continue
            if r.get('obs_sus_mph', '') in ('', 'N/A'):
                continue
            try:
                rows.append({
                    'stid':            r['stid'],
                    'lat':             float(r['lat']),
                    'lon':             float(r['lon']),
                    'bc_speed':        float(r['bc_speed']),
                    'bc_dir':          float(r['bc_dir']),
                    'bc_level':        r.get('bc_level', ''),
                    'obs_sus':         float(r['obs_sus_mph']),
                    'obs_dir':         float(r['obs_dir_deg']) if r.get('obs_dir_deg', '') not in ('', 'N/A') else None,
                    'hrrr_10m':        float(r['hrrr_10m_mph']) if r.get('hrrr_10m_mph', '') not in ('', 'N/A') else None,
                    'hrrr_err':        float(r['speed_err'])    if r.get('speed_err', '')    not in ('', 'N/A') else None,
                    'terrain_class':   r.get('terrain_class', ''),
                    'synoptic_regime': r.get('synoptic_regime', ''),
                    'dem_elev_m':      r.get('dem_elev_m', ''),
                })
            except (ValueError, KeyError):
                continue
    return rows


def circ_mean_deg(dirs):
    us = [math.sin(math.radians(d)) for d in dirs]
    vs = [math.cos(math.radians(d)) for d in dirs]
    return math.degrees(math.atan2(sum(us) / len(us), sum(vs) / len(vs))) % 360


def offset_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def find_domain_for_station(s, domains):
    """
    Return the first domain whose vel ASC strictly contains s['lat'],s['lon'].
    No margin: a station at the edge gets OUTSIDE_ASC_GRID from read_asc_at,
    not a coerced extrapolated value.
    """
    for d in domains:
        vel = d.get('vel_path')
        if not vel or not os.path.exists(vel):
            continue
        lat_min, lat_max, lon_min, lon_max = asc_bounds(vel)
        if lat_min <= s['lat'] <= lat_max and lon_min <= s['lon'] <= lon_max:
            return d
    return None


def extraction_reason(vel, lat, lon):
    """Classify why read_asc_at returned None for an assigned station."""
    if vel is None or not os.path.exists(vel):
        return 'WN_FAILED'
    lat_min, lat_max, lon_min, lon_max = asc_bounds(vel)
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        return 'NODATA_AT_POINT'
    return 'OUTSIDE_ASC_GRID'


# ── Main event runner ─────────────────────────────────────────────────────────

def run_event(event_id, reality_b=False, veg='trees'):
    stations = load_event_stations(event_id)
    if not stations:
        print(f"No stations with BC+obs found for {event_id}")
        return None

    print(f"\n{'='*68}")
    print(f"HINDCAST  {event_id}   ({len(stations)} stations)  "
          f"regime={stations[0]['synoptic_regime']}  BC={stations[0]['bc_level']} hPa")
    print(f"{'='*68}")

    domains = get_event_domains(event_id, stations)
    for d in domains:
        if not ensure_dem(d['dem_path'], d['lat'], d['lon'], d['radius_mi']):
            print(f"  [ERROR] DEM unavailable and auto-fetch failed: {d['dem_path']}")
            return None

    # Event-median BC for domain display vectors
    bc_speeds = sorted(s['bc_speed'] for s in stations)
    median_spd = bc_speeds[len(bc_speeds) // 2]
    median_dir = circ_mean_deg([s['bc_dir'] for s in stations])

    # ── Run WN once per domain with median BC (for display) ─────────────────
    print(f"\n[WN domain runs]  median BC={median_spd:.0f} mph @ {median_dir:.0f}°")
    for d in domains:
        vel, ang = run_wn(d['dem_path'], median_spd, median_dir, veg)
        d['vel_path'] = vel
        d['ang_path'] = ang

    # ── Domain display vectors from primary ──────────────────────────────────
    primary = domains[0]
    if primary.get('vel_path'):
        vectors = asc_to_vectors(primary['vel_path'], primary.get('ang_path'))
        speeds  = [v['speed'] for v in vectors]
        step_used = max(1, min(
            int(primary['vel_path'].split('_')[-2].replace('m','') if False else 0), 1))
        print(f"\n[Domain display]  {len(vectors)} vectors  "
              f"mean={sum(speeds)/len(speeds):.1f} min={min(speeds):.1f} max={max(speeds):.1f} mph")
        domain_out = {
            'event_id':   event_id,
            'reality':    'A',
            'bc':         {'speed': round(median_spd, 1), 'dir': round(median_dir, 1)},
            'domain_dem': os.path.basename(primary['dem_path']),
            'stats':      {'mean': round(sum(speeds)/len(speeds), 2),
                           'min':  round(min(speeds), 2),
                           'max':  round(max(speeds), 2),
                           'n':    len(vectors)},
            'vectors':    vectors,
        }
        out_path = os.path.join(OUTPUT_DIR, f"{event_id}_reality_a_domain.json")
        with open(out_path, 'w') as fh:
            json.dump(domain_out, fh, indent=2)
        print(f"  Saved: {out_path}")

    # ── Per-station Reality A ────────────────────────────────────────────────
    print(f"\n[Reality A — per-station]")
    print(f"{'STID':<8} {'BC':>10} {'Obs':>7} {'WN-A':>7} {'H_err':>7} {'WN_err':>7}  status / terrain")
    print('-' * 75)

    # Needs-domain registry for this event
    needs_domain = NEEDS_DOMAIN.get(event_id, {})

    station_results = []
    for s in stations:
        stid = s['stid']

        # Pre-registered as needing a domain that hasn't been fetched yet
        if stid in needs_domain:
            result = {**s, 'wn_speed_a': None, 'wn_dir_a': None, 'wn_err_a': None,
                      'wn_note': 'NEEDS_DOMAIN', 'domain': needs_domain[stid]}
            station_results.append(result)
            print(f"{stid:<8}  NEEDS_DOMAIN — {needs_domain[stid]}")
            continue

        # Find the domain whose ASC grid strictly contains this station
        assigned = find_domain_for_station(s, domains)

        if assigned is None:
            result = {**s, 'wn_speed_a': None, 'wn_dir_a': None, 'wn_err_a': None,
                      'wn_note': 'OUT_OF_DOMAIN',
                      'domain': f"no domain covers ({s['lat']:.4f},{s['lon']:.4f})"}
            station_results.append(result)
            print(f"{stid:<8}  OUT_OF_DOMAIN  ({s['lat']:.4f},{s['lon']:.4f})")
            continue

        # Run WN with this station's own BC (cached if same speed/dir already run)
        vel, ang = run_wn(assigned['dem_path'], s['bc_speed'], s['bc_dir'], veg)
        wn_spd = read_asc_at(vel, s['lat'], s['lon']) if vel else None
        wn_dir = read_asc_at(ang, s['lat'], s['lon']) if ang else None

        # Domain provenance stamp
        d_center = (assigned['lat'], assigned['lon'])
        d_offset  = offset_km(s['lat'], s['lon'], d_center[0], d_center[1])
        dem_label = os.path.basename(assigned['dem_path'])

        if wn_spd is None:
            reason = extraction_reason(vel, s['lat'], s['lon'])
            result = {**s, 'wn_speed_a': None, 'wn_dir_a': None, 'wn_err_a': None,
                      'wn_note': reason,
                      'domain': dem_label,
                      'domain_center': d_center,
                      'domain_offset_km': round(d_offset, 1)}
            station_results.append(result)
            print(f"{stid:<8}  {reason}  (offset={d_offset:.0f}km)  {s['terrain_class']}")
            continue

        wn_err  = round(wn_spd - s['obs_sus'], 2)
        wn_note = 'OK_LOW_OFFSET' if d_offset < MIN_OFFSET_KM else 'OK'
        result = {**s,
                  'wn_speed_a':       round(wn_spd, 2),
                  'wn_dir_a':         round(wn_dir, 1) if wn_dir is not None else None,
                  'wn_err_a':         wn_err,
                  'wn_note':          wn_note,
                  'domain':           dem_label,
                  'domain_center':    d_center,
                  'domain_offset_km': round(d_offset, 1)}
        station_results.append(result)

        bc_str = f"{s['bc_speed']:.0f}@{s['bc_dir']:.0f}°"
        h_str  = f"{s['hrrr_err']:+.1f}" if s['hrrr_err'] is not None else "  N/A"
        print(f"{stid:<8} {bc_str:>10} {s['obs_sus']:>7.1f} {wn_spd:>7.1f}"
              f" {h_str:>7} {wn_err:>+7.1f}  {wn_note}/{s['terrain_class']} off={d_offset:.0f}km")

    # ── Reality B (where pre-computed) ──────────────────────────────────────
    b_list = [(s, REALITY_B_BC[(event_id, s['stid'])])
              for s in stations if (event_id, s['stid']) in REALITY_B_BC]
    if reality_b and b_list:
        print(f"\n[Reality B — corrected BC]")
        print(f"{'STID':<8} {'BC-raw':>10} {'BC-corr':>10} {'WN-A_err':>9} {'WN-B_err':>9} {'|Δ|':>7}  note")
        print('-' * 75)
        for s, bc_b in b_list:
            assigned = find_domain_for_station(s, domains)
            if assigned is None:
                print(f"{s['stid']:<8}  OUT_OF_DOMAIN — no domain for Reality B")
                continue
            vel_b, _ = run_wn(assigned['dem_path'], bc_b['speed'], bc_b['dir'], veg)
            wn_b  = read_asc_at(vel_b, s['lat'], s['lon']) if vel_b else None
            err_b = round(wn_b - s['obs_sus'], 2) if wn_b is not None else None
            rA    = next((r for r in station_results if r['stid'] == s['stid']), None)
            err_a = rA['wn_err_a'] if rA else None
            delta = round(abs(err_a or 0) - abs(err_b or 0), 2)
            if rA:
                rA['wn_speed_b'] = round(wn_b, 2) if wn_b is not None else None
                rA['wn_err_b']   = err_b
                rA['bc_b_note']  = bc_b['note']
            bc_raw  = f"{s['bc_speed']:.1f}@{s['bc_dir']:.0f}°"
            bc_corr = f"{bc_b['speed']:.1f}@{bc_b['dir']:.0f}°"
            e_a_str = f"{err_a:+.1f}" if err_a is not None else "  N/A"
            e_b_str = f"{err_b:+.1f}" if err_b is not None else "  N/A"
            print(f"{s['stid']:<8} {bc_raw:>10} {bc_corr:>10} {e_a_str:>9} {e_b_str:>9} {delta:>+7.1f}  {bc_b['note']}")
    elif reality_b:
        print(f"\n[Reality B] No pre-computed corrected BC for {event_id}.")

    # ── Summary — terrain-stratified, never aggregate mean ───────────────────
    # OK: offset ≥ MIN_OFFSET_KM — primary accuracy pool.
    # OK_LOW_OFFSET: offset < MIN_OFFSET_KM — extracted, reported, not pooled
    #   (domain-center amplification makes these ratios untrustworthy for pooling).
    # exposed_ridge always reported per-station — it is the niche target.
    # Never compute a cross-terrain mean: WN degrades non-ridge stations.
    primary_dem = os.path.basename(domains[0]['dem_path'])
    ok_pool    = [r for r in station_results
                  if r.get('wn_note') == 'OK' and r.get('wn_err_a') is not None]
    low_offset = [r for r in station_results
                  if r.get('wn_note') == 'OK_LOW_OFFSET' and r.get('wn_err_a') is not None]
    excluded   = [r for r in station_results
                  if r.get('wn_note') not in ('OK', 'OK_LOW_OFFSET')]

    def print_terrain_block(pool, label):
        if not pool:
            return
        print(f"\n  {label}  (N={len(pool)})")
        ridges = [r for r in pool if r.get('terrain_class') == 'exposed_ridge']
        others = [r for r in pool if r.get('terrain_class') != 'exposed_ridge']
        if ridges:
            print(f"    exposed_ridge ({len(ridges)}) — niche target, per-station:")
            for r in ridges:
                h_str   = f"HRRR={r['hrrr_err']:+.1f}" if r.get('hrrr_err') is not None else "HRRR=N/A"
                ratio   = r['wn_speed_a'] / r['obs_sus'] if r.get('obs_sus') else None
                r_str   = f"ratio={ratio:.3f}" if ratio is not None else ""
                imp     = (r.get('hrrr_err') is not None and
                           abs(r['wn_err_a']) < abs(r['hrrr_err']))
                flag    = " NICHE WIN" if imp else ""
                print(f"      {r['stid']:<8} WN_err={r['wn_err_a']:+.1f}  {h_str}  {r_str}"
                      f"  off={r.get('domain_offset_km','?')}km{flag}")
        if others:
            by_cls = {}
            for r in others:
                by_cls.setdefault(r.get('terrain_class', 'unknown'), []).append(r)
            for cls, rs in sorted(by_cls.items()):
                n_imp  = sum(1 for r in rs
                             if r.get('hrrr_err') is not None
                             and abs(r['wn_err_a']) < abs(r['hrrr_err']))
                mean_e = sum(r['wn_err_a'] for r in rs) / len(rs)
                print(f"    {cls} ({len(rs)}) — WN_err mean={mean_e:+.1f}  improved={n_imp}/{len(rs)}"
                      f"  [not niche]")

    print(f"\n{'─'*68}")
    print(f"SUMMARY  {event_id}")
    print_terrain_block(ok_pool,
                        f"OK (offset ≥ {MIN_OFFSET_KM:.0f}km, primary pool) — dom={primary_dem}")
    print_terrain_block(low_offset,
                        f"OK_LOW_OFFSET (offset < {MIN_OFFSET_KM:.0f}km — reported, not pooled)")

    other_domain = [r for r in ok_pool + low_offset if r.get('domain') != primary_dem]
    if other_domain:
        print(f"\n  Note: {len(other_domain)} station(s) on secondary domain(s) — "
              f"different terrain-amplification context:")
        for r in other_domain:
            print(f"    {r['stid']}: dom={r['domain']} off={r.get('domain_offset_km','?')}km"
                  f" WN_err={r['wn_err_a']:+.1f}")

    if excluded:
        by_reason = {}
        for r in excluded:
            by_reason.setdefault(r.get('wn_note', '?'), []).append(r['stid'])
        print(f"\n  Excluded ({len(excluded)} stations):")
        for reason, stids in sorted(by_reason.items()):
            print(f"    {reason}: {', '.join(stids)}")

    # ── Save station results ─────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, f"{event_id}_station_results.json")
    with open(out_path, 'w') as fh:
        json.dump({'event_id': event_id, 'stations': station_results}, fh,
                  indent=2, default=str)
    print(f"\nStation results: {out_path}")
    return station_results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WindNinja hindcast runner v2 (direct CLI)')
    parser.add_argument('--event',     default='camp_2018',
                        help='Event ID from hrrr_error_dataset.csv')
    parser.add_argument('--reality-b', action='store_true',
                        help='Also run Reality B corrected BC where pre-computed')
    parser.add_argument('--veg',       default='trees',
                        choices=['grass', 'brush', 'trees'],
                        help='WindNinja vegetation type (default: trees)')
    parser.add_argument('--all',       action='store_true',
                        help='Run all 11 events (excludes tubbs_2017 — direction flag)')
    args = parser.parse_args()

    if args.all:
        for ev in ALL_EVENTS:
            run_event(ev, reality_b=args.reality_b, veg=args.veg)
    else:
        run_event(args.event, reality_b=args.reality_b, veg=args.veg)
