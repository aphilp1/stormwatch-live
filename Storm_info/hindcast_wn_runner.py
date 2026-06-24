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
    # 2020 Labor Day OR fires span ~200 mi (3 complexes) — one domain can't cover.
    # Three lat-band cluster domains; runner appends the bbox catch-all too.
    'labor_day_or2020': [
        {'lat': 42.33, 'lon': -122.89, 'radius_mi': 18},   # south cluster
        {'lat': 43.48, 'lon': -122.26, 'radius_mi': 45},   # central cluster
        {'lat': 44.94, 'lon': -122.48, 'radius_mi': 30},   # north cluster
    ],
}

# Stations that require domain DEMs not yet fetched.
# fetch_dem.exe --point <lon> <lat> <buf> <buf> --buf_units miles --src srtm <out.tif>
# All camp_2018 stations now have domains configured in EVENT_DOMAINS (2026-06-21).
NEEDS_DOMAIN = {}

# Optional large single domain used ONLY for the map arrow field, so the colored
# vectors form one continuous grid over the whole event area (no inter-domain
# gaps). Per-station extraction still uses the precise EVENT_DOMAINS above.
# Fetch: fetch_dem.exe --point <lon> <lat> <buf> <buf> --buf_units miles --src srtm <out.tif>
# A DISPLAY_DOMAINS value may be a single dict OR a list of dicts. A list is
# stitched (vectors merged on a shared grid) so a very tall/wide event gets one
# continuous arrow field instead of a single 45mi-capped patch in the middle.
DISPLAY_DOMAINS = {
    'camp_2018': {'lat': 39.83, 'lon': -121.32, 'radius_mi': 35,
                  'dem_name': 'dem_39.8_-121.3_35mi.tif'},
    # 2020 Labor Day OR spans ~320 km N-S. Three overlapping 45mi tiles along
    # lon -122.3 cover the whole range (41.85-45.25 lat) continuously so the field
    # reaches the northern (Salem/Albany) and southern station clusters, not just
    # the central band. (Per-station extraction still uses EVENT_DOMAINS above.)
    'labor_day_or2020': [
        {'lat': 42.5, 'lon': -122.3, 'radius_mi': 45},
        {'lat': 43.6, 'lon': -122.3, 'radius_mi': 45},
        {'lat': 44.6, 'lon': -122.3, 'radius_mi': 45},
    ],
}

# Run order for --all. tubbs_2017 is INCLUDED as of 2026-06-23 (run-with-caveat
# decision): WN run is valid for speed; the BC/obs direction mismatch at 4
# valley/open stations (NVHC1, WISC1, KELC1, KNXC1, 25-66° more northerly) is a
# documented, direction-only caveat — speed scoring is direction-independent.
ALL_EVENTS = [
    'camp_2018',
    'kincade_run_2019', 'kincade_ign_2019',
    'woolsey_2018', 'thomas_2017',
    'missoula_dec2025', 'labor_day_or2020',
    'boulder_chin2021', 'marshall_2021',
    'iowa_derecho2020', 'missoula_jul2024',
    'tubbs_2017',
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
        # No hand-tuned domains: one auto-sized domain covering all stations.
        configs = [bbox_domain(stations)]
    else:
        # Hand-tuned tight domains take priority (listed first → matched first);
        # append the auto bbox domain as a catch-all so stations not covered by a
        # tight domain still get a value instead of OUT_OF_DOMAIN.
        configs = list(configs) + [bbox_domain(stations)]
    result = []
    for c in configs:
        d = dict(c)
        d['dem_path'] = get_dem_path(c['lat'], c['lon'], c['radius_mi'],
                                     c.get('dem_name'))
        result.append(d)
    return result


# ── Auto domain sizing ────────────────────────────────────────────────────────

def bbox_domain(stations, margin_mi=8, cap_mi=45):
    """Single domain (bbox center + radius in miles) covering all stations.
    Used as the auto display domain and the auto fallback when an event has no
    hand-tuned EVENT_DOMAINS. Radius is capped so a few far-flung stations don't
    force an enormous DEM (those land OUT_OF_DOMAIN and are reported as such)."""
    lat = (min(s['lat'] for s in stations) + max(s['lat'] for s in stations)) / 2
    lon = (min(s['lon'] for s in stations) + max(s['lon'] for s in stations)) / 2
    maxd_km = max(offset_km(lat, lon, s['lat'], s['lon']) for s in stations)
    radius_mi = min(cap_mi, int(maxd_km / 1.60934) + margin_mi)
    return {'lat': round(lat, 2), 'lon': round(lon, 2), 'radius_mi': radius_mi}


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
        # The filename encodes the mesh CELL SIZE (e.g. ..._762m_vel-4326.asc).
        # This runner always runs coarse mesh = the LARGEST cell size. If a manual
        # fine/medium-mesh experiment left extra ASCs in the shared cache, the old
        # glob()[0] could silently return the fine one (this caused SLEC1=57 vs the
        # coarse 49.1 — see POSTMORTEM_2026-06-22). Pick the coarsest match
        # deterministically, and match the ang ASC to the SAME cell tag.
        def _cell_m(p):
            tok = os.path.basename(p).split('_')[-2]
            try: return int(tok.rstrip('m'))
            except ValueError: return 0
        vel = max(cached_vel, key=_cell_m)
        cell_tag = os.path.basename(vel).split('_')[-2]
        cached_ang = glob_mod.glob(
            os.path.join(WN_CACHE, f'{dem_stem}_{dir_int}_{spd_int}_{cell_tag}_ang-4326.asc'))
        print(f"  [cached] {os.path.basename(vel)}")
        return vel, (cached_ang[0] if cached_ang else None)

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
                    'hrrr_10m_dir':    float(r['hrrr_10m_dir']) if r.get('hrrr_10m_dir', '') not in ('', 'N/A') else None,
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

    # Event-median wind that drives the DISPLAY field. Use the HRRR 10m wind, NOT
    # the aloft BC: the 700 mb aloft wind (~80 mph) makes WindNinja overshoot the
    # whole grid to 80-120 mph (an all-red, unreadable field) when the surface was
    # 5-46 mph. The 10m-driven field matches observations and the WN(10m) analysis.
    # SPEED from the HRRR 10m wind (realistic surface magnitude, no aloft overshoot).
    h10s = sorted(s['hrrr_10m'] for s in stations if s.get('hrrr_10m'))
    if h10s:
        median_spd = h10s[len(h10s) // 2]
        field_label = '10m'
    else:
        bc_speeds = sorted(s['bc_speed'] for s in stations)
        median_spd = bc_speeds[len(bc_speeds) // 2]
        field_label = 'BC'
    # DIRECTION from the aloft (BC) wind — the synoptic flow, robust. The 10m
    # surface dirs scatter and circular-average to nonsense with few stations
    # (Iowa derecho: 2 stations S + NNE -> a meaningless E mean; the 850 dirs are
    # W + WNW = the real westerly flow).
    median_dir = circ_mean_deg([s['bc_dir'] for s in stations])

    # ── Run WN once per domain with the median display wind ─────────────────
    print(f"\n[WN domain runs]  median {field_label}={median_spd:.0f} mph @ {median_dir:.0f}°")
    for d in domains:
        vel, ang = run_wn(d['dem_path'], median_spd, median_dir, veg)
        d['vel_path'] = vel
        d['ang_path'] = ang

    # ── Domain display vectors ───────────────────────────────────────────────
    # Prefer a single large DISPLAY domain so the arrow field is one continuous
    # grid over the whole area (no inter-domain gaps). Fall back to merging the
    # per-station EVENT_DOMAINS (deduped on a ~0.02deg grid) if none is configured.
    # Always drive the field from a single large domain (hand-tuned if given,
    # else auto-sized to the station bbox) so the arrows form one continuous grid.
    disp = DISPLAY_DOMAINS.get(event_id) or bbox_domain(stations)
    disp_list = disp if isinstance(disp, list) else [disp]
    field_vectors = []
    field_source = []
    field_cells = set()
    for dd in disp_list:
        disp_dem = get_dem_path(dd['lat'], dd['lon'], dd['radius_mi'], dd.get('dem_name'))
        if not ensure_dem(disp_dem, dd['lat'], dd['lon'], dd['radius_mi']):
            continue
        dvel, dang = run_wn(disp_dem, median_spd, median_dir, veg)
        if not dvel:
            continue
        field_source.append(os.path.basename(disp_dem))
        # Merge tiles on a shared ~0.02deg grid so overlapping tiles don't
        # double-draw and the stitched field reads as one continuous grid.
        for v in asc_to_vectors(dvel, dang, target_per_axis=34):
            cell = (round(v['lat'] / 0.02), round(v['lon'] / 0.02))
            if cell in field_cells:
                continue
            field_cells.add(cell); field_vectors.append(v)
    if not field_vectors:
        seen_cells = set()
        counts = []
        for d in domains:
            if not d.get('vel_path'):
                continue
            kept = 0
            for v in asc_to_vectors(d['vel_path'], d.get('ang_path'), target_per_axis=16):
                cell = (round(v['lat'] / 0.02), round(v['lon'] / 0.02))
                if cell in seen_cells:
                    continue
                seen_cells.add(cell); field_vectors.append(v); kept += 1
            counts.append((os.path.basename(d['dem_path']), kept))
        field_source = [n for n, _ in counts]
    if field_vectors:
        speeds = [v['speed'] for v in field_vectors]
        print(f"\n[Domain display]  {len(field_vectors)} vectors  source={field_source}  "
              f"mean={sum(speeds)/len(speeds):.1f} min={min(speeds):.1f} max={max(speeds):.1f} mph")
        domain_out = {
            'event_id':   event_id,
            'reality':    'A',
            'bc':         {'speed': round(median_spd, 1), 'dir': round(median_dir, 1)},
            'domain_dem': field_source,
            'stats':      {'mean': round(sum(speeds)/len(speeds), 2),
                           'min':  round(min(speeds), 2),
                           'max':  round(max(speeds), 2),
                           'n':    len(field_vectors)},
            'vectors':    field_vectors,
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

        # WN initialized from HRRR 10m wind — SAME domain / mesh / extraction as
        # the 850 run; only the input wind differs (one-variable change for the
        # 2x2). run_wn's cache key is (dem,dir,spd,cell): 10m vs 850 differ in
        # dir/spd so they get distinct ASCs; identical (dir,spd) legitimately
        # share the same WN field (output is fully determined by dem+dir+spd+mesh).
        wn10_spd = None
        if s.get('hrrr_10m') and s.get('hrrr_10m_dir') is not None:
            vel10, _ = run_wn(assigned['dem_path'], s['hrrr_10m'], s['hrrr_10m_dir'], veg)
            wn10_spd = read_asc_at(vel10, s['lat'], s['lon']) if vel10 else None

        result = {**s,
                  'wn_speed_a':       round(wn_spd, 2),
                  'wn_dir_a':         round(wn_dir, 1) if wn_dir is not None else None,
                  'wn_err_a':         wn_err,
                  'wn_speed_b_10m':   round(wn10_spd, 2) if wn10_spd is not None else None,
                  'wn_err_b_10m':     round(wn10_spd - s['obs_sus'], 2) if wn10_spd is not None else None,
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
                # A "win" means WN actually lands near obs (within 25%), NOT merely
                # that |wn_err| < |hrrr_err| — the old test flagged SLEC1 (ratio 1.40,
                # a +40% overshoot) as a win. See POSTMORTEM_2026-06-22.
                within  = ratio is not None and abs(ratio - 1) <= 0.25
                closer  = (r.get('hrrr_err') is not None and
                           abs(r['wn_err_a']) < abs(r['hrrr_err']))
                flag    = " NICHE WIN" if within else (" (closer, not in band)" if closer else "")
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

    # ── Four-way scoring: HRRR 10m | HRRR 850 | WN(10m) | WN(850) vs obs ──────
    # Scored only at non-near-calm stations (obs>=5 AND bc/obs<=3). obs is the
    # scoring truth, NOT a fit target. Separates "is 850 the wrong level?" from
    # "does WN downscaling help?".
    names = ['HRRR10m', 'HRRR850', 'WN10m', 'WN850']
    scored = [r for r in station_results
              if r.get('wn_speed_a') is not None and r.get('wn_speed_b_10m') is not None
              and r.get('hrrr_10m') is not None and (r.get('obs_sus') or 0) >= 5
              and r.get('bc_speed') and (r['bc_speed'] / r['obs_sus']) <= 3]
    scoring = {'n_scored': len(scored), 'closest_of_four': {n: 0 for n in names},
               'wn10_beats_hrrr10m': 0, 'wn10_beats_wn850': 0, 'rows': []}
    if scored:
        print(f"\n  FOUR-WAY SCORING ({len(scored)} scorable stations) — |error vs obs|, mph:")
        print(f"    {'STID':<8}{'HRRR10m':>9}{'HRRR850':>9}{'WN10m':>8}{'WN850':>8}  closest")
        for r in scored:
            o = r['obs_sus']
            e = [abs(r['hrrr_10m'] - o), abs(r['bc_speed'] - o),
                 abs(r['wn_speed_b_10m'] - o), abs(r['wn_speed_a'] - o)]
            ci = e.index(min(e))
            scoring['closest_of_four'][names[ci]] += 1
            if e[2] < e[0]: scoring['wn10_beats_hrrr10m'] += 1
            if e[2] < e[3]: scoring['wn10_beats_wn850'] += 1
            scoring['rows'].append({'stid': r['stid'],
                                    'err': {names[i]: round(e[i], 2) for i in range(4)},
                                    'closest': names[ci]})
            print(f"    {r['stid']:<8}{e[0]:>9.1f}{e[1]:>9.1f}{e[2]:>8.1f}{e[3]:>8.1f}  {names[ci]}")
        print(f"    closest-of-four: " + "  ".join(f"{n}={scoring['closest_of_four'][n]}" for n in names))
        print(f"    WN(10m) beats raw HRRR 10m at {scoring['wn10_beats_hrrr10m']}/{len(scored)} stations")
        print(f"    WN(10m) beats WN(850)      at {scoring['wn10_beats_wn850']}/{len(scored)} stations")

    # ── Save station results ─────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, f"{event_id}_station_results.json")
    with open(out_path, 'w') as fh:
        json.dump({'event_id': event_id, 'four_way_scoring': scoring,
                   'stations': station_results}, fh, indent=2, default=str)
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
                        help='Run all 12 events (tubbs_2017 included — direction caveat)')
    args = parser.parse_args()

    if args.all:
        for ev in ALL_EVENTS:
            run_event(ev, reality_b=args.reality_b, veg=args.veg)
    else:
        run_event(args.event, reality_b=args.reality_b, veg=args.veg)
