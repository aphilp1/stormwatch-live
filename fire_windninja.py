"""
fire_windninja.py
==================

LOCAL-ONLY enrichment for the Fire Briefing (fire_watchlist.py). Routes the
top active fires through the REAL HRRR/terrain WindNinja pipeline instead of
the flat Open-Meteo mechanism classifier already in data/fire_watchlist.json.

Why this is separate from fire_watchlist.py: WindNinja needs the local CLI
(C:\\WindNinja) + an SRTM DEM cache, served through the local MCP server's
/windninja endpoint (localhost:3456 -- only up when Claude Desktop is running
on this machine). It CANNOT run in the daily GitHub Action (Linux runner, no
WindNinja installed) -- consistent with the rest of the project's "WindNinja
stays local" rule. This script is a manual, on-demand supplement: run it after
fire_watchlist.py, it merges a "windninja" block into today's already-written
data/fire_watchlist.json for whichever fires it processed, and regenerates
FIRE_WATCHLIST.md. Tomorrow's automated run won't carry it forward -- rerun
by hand for a fresh set of fires.

Each fire's own forecast wind (already computed by fire_watchlist.py's
mechanism_classifier -- sustained speed + direction) is used as the WindNinja
INPUT, so this isn't a second, disconnected forecast -- it's the same
forecast wind, downscaled to real terrain.

Usage (from Documents\\Stormwatch, Claude Desktop running):
    python fire_windninja.py                 # top N active fires (default 2)
    python fire_windninja.py --n 3
    python fire_windninja.py --radius 10 --veg brush
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

from fire_watchlist import render_md

MCP_BASE = "http://localhost:3456"
JSON_PATH = "data/fire_watchlist.json"
MD_PATH = "FIRE_WATCHLIST.md"


def _get_json(url, timeout=90):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def run_windninja(lat, lon, speed, direction, radius, veg):
    url = (f"{MCP_BASE}/windninja?lat={lat}&lon={lon}&speed={speed:.1f}"
           f"&dir={direction:.0f}&radius={radius}&veg={veg}")
    return _get_json(url)


def interpret(input_speed, stats):
    mx = float(stats["max"])
    mn = float(stats["min"])
    accel = (mx / input_speed - 1) * 100 if input_speed else 0
    if accel >= 25:
        lead = (f"Terrain is materially accelerating this fire's wind: exposed ground in the "
               f"domain sees up to {mx:.0f} mph, {accel:.0f}% above the {input_speed:.0f} mph "
               f"flat-terrain forecast — the kind of local acceleration a 3 km model can't resolve.")
    elif accel >= 10:
        lead = (f"Terrain moderately accelerates the wind here: up to {mx:.0f} mph in exposed spots "
               f"vs. {input_speed:.0f} mph forecast ({accel:.0f}% higher).")
    else:
        lead = (f"Terrain doesn't add much here — resolved wind stays close to the "
               f"{input_speed:.0f} mph flat-terrain forecast (peak {mx:.0f} mph).")
    shelter = (f" Sheltered terrain (valleys, lee slopes) drops as low as {mn:.0f} mph — "
              f"expect real spread-rate variation across the fire, not a single uniform wind.")
    return lead + shelter


def main(argv):
    n = 2
    radius = 10
    veg = "brush"
    for a in argv:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        elif a.startswith("--radius="):
            radius = int(a.split("=", 1)[1])
        elif a.startswith("--veg="):
            veg = a.split("=", 1)[1]

    try:
        _get_json(f"{MCP_BASE}/health", timeout=5)
    except Exception as e:                # noqa: BLE001
        print(f"error: local MCP server not reachable at {MCP_BASE} ({e}). "
              "Start Claude Desktop and retry.", file=sys.stderr)
        return 1

    with open(JSON_PATH, encoding="utf-8") as f:
        w = json.load(f)

    fires = w.get("active_threats", [])[:n]
    if not fires:
        print("no active-threat fires in today's briefing to route.", file=sys.stderr)
        return 0

    for fire in fires:
        wind = fire.get("wind")
        if not wind:
            print(f"skip {fire['name']}: no forecast wind on record.", file=sys.stderr)
            continue
        pk = wind["peak"]
        speed, direction = pk["sustained_mph"], pk["dir_deg"]
        print(f"running WindNinja on {fire['name']} Fire ({fire['state']}): "
              f"input {speed:.1f} mph from {direction:.0f}°, radius {radius} mi, veg={veg}...",
              file=sys.stderr)
        t0 = time.time()
        try:
            result = run_windninja(fire["lat"], fire["lon"], speed, direction, radius, veg)
        except Exception as e:            # noqa: BLE001
            print(f"  failed: {e}", file=sys.stderr)
            continue
        dt = time.time() - t0
        stats = result["stats"]
        print(f"  done in {dt:.0f}s: min={stats['min']} mean={stats['mean']} max={stats['max']} mph", file=sys.stderr)
        fire["windninja"] = {
            "input_speed_mph": round(speed, 1), "input_dir_deg": round(direction),
            "radius_mi": radius, "vegetation": veg,
            "stats": stats, "dem_cached": result["input"]["demCached"],
            "narrative": interpret(speed, stats),
        }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(w, f, indent=1)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(render_md(w))
    print(f"wrote {JSON_PATH} + {MD_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
