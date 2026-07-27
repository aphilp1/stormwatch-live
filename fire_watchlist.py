"""
fire_watchlist.py
=================

National Fire Watchlist (spec: Storm_info/fable_specs/06_fire_watchlist.md).

Finds the CONUS communities where the three ingredients of a dangerous fire
event converge in the next 1-7 days:

  trigger  -- official fire-weather areas: NWS Red Flag Warnings / Fire Weather
              Watches, SPC Fire Weather Outlooks (D1/D2), and NIFC Predictive
              Services 7-Day Significant Fire Potential risk polygons
  fuels    -- USGS fire-danger point values (WFPI index, WLFP large-fire %,
              WFSP spread %), max of place center + ~9 km ring
  exposure -- Census place population / housing units (data/place_exposure.json)

plus the repo's own wind-mechanism classifier (live_forecast.forecast_site) on
the top candidates: what KIND of wind event, and how models tend to miss it.

Every displayed ingredient is an authoritative agency value quoted as-is; the
ranking formula is documented in the spec and embedded in the JSON output.
Missing feeds are flagged, never guessed.

Pure standard library. Outputs:
    python fire_watchlist.py --json > data/fire_watchlist.json
    python fire_watchlist.py --md   > FIRE_WATCHLIST.md
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from live_forecast import forecast_site

METHOD_VERSION = "1.0"
UA = {"User-Agent": "StormWatchLive-FireWatchlist/1.0 (github.com/aphilp1/stormwatch-live)"}

SPC_FWX = "https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer"
PSP_BASE = "https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer"
NWS_ALERTS = ("https://api.weather.gov/alerts/active"
              "?event=Red%20Flag%20Warning,Fire%20Weather%20Watch&status=actual")
USGS_BASE = "https://dmsdata.cr.usgs.gov/geoserver"

CANDIDATE_CAP = 60      # places scored for fuels
CLASSIFIER_CAP = 25     # places run through the wind-mechanism classifier
OUTPUT_CAP = 15         # final watchlist length
DEDUPE_DEG = 0.25       # keep highest-pop place per grid cell of this size
# Each individual request is fast (~0.5 s) -- a modest thread pool cuts the two
# sequential-HTTP-loop stages from minutes to well under one, while staying far
# below anything that looks like hammering a free government endpoint.
POOL_WORKERS = 6

SPC_DN = {5: "Elevated", 8: "Critical", 10: "Extreme"}
SPC_PTS = {5: 1.0, 8: 2.0, 10: 3.0}


def _get_json(url, timeout=45, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:            # noqa: BLE001 - retry then surface
            last = e
            time.sleep(2 * (i + 1))
    raise last


# ---------------------------------------------------------------------------
# Geometry: pure-python point-in-polygon with bbox prefilter
# ---------------------------------------------------------------------------

def _rings(geom):
    """Yield outer rings (list of [lon, lat]) from a GeoJSON (Multi)Polygon."""
    if not geom:
        return
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    elif geom["type"] == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from _rings(g)
        return
    else:
        return
    for poly in polys:
        if poly:
            yield poly            # full ring list: [outer, hole1, ...]


def _pip_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


class Region:
    """One trigger polygon set with a precomputed bbox for cheap rejection."""

    def __init__(self, geom, tag, detail):
        self.polys = list(_rings(geom))
        self.tag = tag
        self.detail = detail
        xs, ys = [], []
        for poly in self.polys:
            for x, y in poly[0]:
                xs.append(x)
                ys.append(y)
        self.bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def contains(self, lon, lat):
        if not self.bbox:
            return False
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            return False
        for poly in self.polys:
            if _pip_ring(lon, lat, poly[0]):
                if all(not _pip_ring(lon, lat, hole) for hole in poly[1:]):
                    return True
        return False


# ---------------------------------------------------------------------------
# Trigger polygons
# ---------------------------------------------------------------------------

def fetch_spc_regions():
    regions = []
    layers = [(1, "spc", 1), (2, "spc_dryltg", 1), (4, "spc", 2), (5, "spc_dryltg", 2)]
    for lyr, tag, day in layers:
        try:
            d = _get_json(f"{SPC_FWX}/{lyr}/query?where=1%3D1&outFields=dn&f=geojson")
        except Exception as e:            # noqa: BLE001
            print(f"warn: SPC layer {lyr} failed: {e}", file=sys.stderr)
            continue
        for f in d.get("features", []):
            dn = (f.get("properties") or {}).get("dn") or 0
            if dn > 0 and f.get("geometry"):
                regions.append(Region(f["geometry"], tag, {"day": day, "dn": dn}))
    return regions


def fetch_psp_regions():
    regions = []
    for lyr in range(7):                  # 0=Day1 ... 6=Day7
        try:
            d = _get_json(f"{PSP_BASE}/{lyr}/query?where=1%3D1&outFields=type"
                          "&maxAllowableOffset=0.01&geometryPrecision=3"
                          "&returnGeometry=true&f=geojson", timeout=60)
        except Exception as e:            # noqa: BLE001
            print(f"warn: PSP day {lyr + 1} failed: {e}", file=sys.stderr)
            continue
        for f in d.get("features", []):
            t = (f.get("properties") or {}).get("type")
            if t in ("CRITICAL", "IGNITION") and f.get("geometry"):
                regions.append(Region(f["geometry"], "psp", {"day": lyr + 1, "type": t}))
    return regions


def fetch_redflag_regions():
    regions = []
    try:
        d = _get_json(NWS_ALERTS)
    except Exception as e:                # noqa: BLE001
        print(f"warn: NWS alerts failed: {e}", file=sys.stderr)
        return regions
    zone_cache = {}
    for f in d.get("features", []):
        props = f.get("properties") or {}
        kind = "warning" if props.get("event") == "Red Flag Warning" else "watch"
        detail = {"kind": kind, "headline": props.get("headline") or props.get("event")}
        if f.get("geometry"):
            regions.append(Region(f["geometry"], "redflag", detail))
            continue
        for zurl in (props.get("affectedZones") or []):
            geom = zone_cache.get(zurl)
            if geom is None:
                try:
                    geom = _get_json(zurl).get("geometry")
                except Exception:         # noqa: BLE001
                    geom = {}
                zone_cache[zurl] = geom
                time.sleep(0.1)
            if geom:
                regions.append(Region(geom, "redflag", detail))
    return regions


# ---------------------------------------------------------------------------
# Fuels: USGS fire-danger GetFeatureInfo (semantics verified in spec 05)
#   WFPI  PALETTE_INDEX 0-247 = value, >=248 mask
#   WLFP/WFSP GRAY_INDEX = percent; >=248 mask (WLFP mask codes are x10)
# ---------------------------------------------------------------------------

def _gfi(product, lat, lon):
    name = f"{product}-forecast-1_conus_day_data"
    dd = 0.01
    url = (f"{USGS_BASE}/firedanger_{name}/wms?SERVICE=WMS&VERSION=1.3.0"
           f"&REQUEST=GetFeatureInfo&LAYERS={name}&QUERY_LAYERS={name}&CRS=CRS:84"
           f"&BBOX={lon - dd:.4f},{lat - dd:.4f},{lon + dd:.4f},{lat + dd:.4f}"
           "&WIDTH=101&HEIGHT=101&I=50&J=50&INFO_FORMAT=application%2Fjson")
    try:
        d = _get_json(url, timeout=30, tries=2)
    except Exception:                     # noqa: BLE001
        return None
    feats = d.get("features") or []
    if not feats:
        return None                       # outside CONUS raster
    p = feats[0].get("properties") or {}
    v = p.get("PALETTE_INDEX", p.get("GRAY_INDEX"))
    return v if isinstance(v, (int, float)) else None


def fuels_at(lat, lon):
    """Max of center + 4-point ~9 km ring per product; None = no valid cell."""
    pts = [(lat, lon), (lat + 0.08, lon), (lat - 0.08, lon),
           (lat, lon + 0.10), (lat, lon - 0.10)]
    out = {}
    for prod in ("wfpi", "wlfp", "wfsp"):
        best = None
        for i, (la, lo) in enumerate(pts):
            v = _gfi(prod, la, lo)
            if v is not None and v < 248:
                best = v if best is None else max(best, v)
            if i == 0 and best is not None:
                # center cell valid: one ring point is enough to catch a hotter edge
                v2 = _gfi(prod, pts[1][0], pts[1][1])
                if v2 is not None and v2 < 248:
                    best = max(best, v2)
                break
        out[prod] = best
    return out


# ---------------------------------------------------------------------------
# Scoring (formula documented in spec 06; embedded in JSON for transparency)
# ---------------------------------------------------------------------------

FORMULA = ("risk_index = trigger_pts * (1 + fuels_pct/25) * log10(population); "
           "trigger_pts = redflag(2 warn|1 watch) + SPC(1 Elev|2 Crit|3 Extr, +0.5 dry-ltg) "
           "+ PSP days (D1 1.5, D2-3 1.0, D4-7 0.5, cap 3) + wind(2 CRITICAL|1 ELEVATED)")


def trigger_points(hits):
    pts = 0.0
    rf = hits.get("redflag")
    if rf:
        pts += 2.0 if rf["kind"] == "warning" else 1.0
    spc = hits.get("spc")
    if spc:
        pts += max(SPC_PTS.get(h["dn"], 0) for h in spc)
    if hits.get("spc_dryltg"):
        pts += 0.5
    psp_days = sorted({h["day"] for h in hits.get("psp", [])})
    psp_pts = sum(1.5 if d == 1 else 1.0 if d <= 3 else 0.5 for d in psp_days)
    pts += min(psp_pts, 3.0)
    return pts, psp_days


def fuels_pct(fu):
    """Authoritative probability if available, else scaled WFPI (flagged)."""
    probs = [v for v in (fu.get("wlfp"), fu.get("wfsp")) if v is not None]
    if probs:
        return max(probs), "wlfp/wfsp"
    if fu.get("wfpi") is not None:
        return fu["wfpi"] / 150 * 20, "wfpi"
    return 0.0, "none"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_watchlist():
    places = json.load(open("data/place_exposure.json", encoding="utf-8"))["places"]

    print("fetching trigger polygons...", file=sys.stderr)
    regions = fetch_spc_regions() + fetch_psp_regions() + fetch_redflag_regions()
    n_by = {}
    for r in regions:
        n_by[r.tag] = n_by.get(r.tag, 0) + 1
    print(f"regions: {n_by}", file=sys.stderr)

    print("filtering candidates...", file=sys.stderr)
    cands = []
    for p in places:
        hits = {}
        for r in regions:
            if r.contains(p["lon"], p["lat"]):
                if r.tag == "redflag":
                    cur = hits.get("redflag")
                    if not cur or (cur["kind"] == "watch" and r.detail["kind"] == "warning"):
                        hits["redflag"] = r.detail
                else:
                    hits.setdefault(r.tag, []).append(r.detail)
        if hits:
            cands.append((p, hits))

    # dedupe: one place (highest pop) per DEDUPE_DEG grid cell
    best = {}
    for p, hits in cands:
        key = (round(p["lat"] / DEDUPE_DEG), round(p["lon"] / DEDUPE_DEG))
        if key not in best or p["pop"] > best[key][0]["pop"]:
            best[key] = (p, hits)
    # Cap by trigger-weighted priority, NOT raw population — a Red Flag Warning over a
    # small town (Salmon ID, pop 3k) must beat a Day-6 potential hit at a big city.
    def _prio(t):
        p, hits = t
        return trigger_points(hits)[0] * math.log10(max(p["pop"], 10))
    cands = sorted(best.values(), key=lambda t: -_prio(t))[:CANDIDATE_CAP]
    print(f"candidates after dedupe/cap: {len(cands)}", file=sys.stderr)

    print(f"querying USGS fuels ({len(cands)} places, {POOL_WORKERS} workers)...", file=sys.stderr)
    def _score_one(item):
        p, hits = item
        fu = fuels_at(p["lat"], p["lon"])
        fpct, fsrc = fuels_pct(fu)
        tpts, psp_days = trigger_points(hits)
        prelim = tpts * (1 + fpct / 25) * math.log10(max(p["pop"], 10))
        return {"place": p, "hits": hits, "fuels": fu, "fuels_pct": round(fpct, 1),
                "fuels_source": fsrc, "psp_days": psp_days,
                "trigger_pts_base": tpts, "prelim": prelim}
    with ThreadPoolExecutor(max_workers=POOL_WORKERS) as ex:
        scored = list(ex.map(_score_one, cands))
    scored.sort(key=lambda s: -s["prelim"])

    print(f"running wind-mechanism classifier on top {CLASSIFIER_CAP} candidates...", file=sys.stderr)
    top = scored[:CLASSIFIER_CAP]
    def _classify_one(s):
        p = s["place"]
        try:
            return forecast_site(f'{p["n"]}, {p["st"]}', p["lat"], p["lon"], "auto", 24)
        except Exception as e:            # noqa: BLE001
            print(f'warn: classifier failed for {p["n"]}: {e}', file=sys.stderr)
            return None
    with ThreadPoolExecutor(max_workers=POOL_WORKERS) as ex:
        winds = list(ex.map(_classify_one, top))
    for s, wind in zip(top, winds):
        s["wind"] = wind

    entries = []
    for s in scored[:CLASSIFIER_CAP]:
        p, hits, w = s["place"], s["hits"], s.get("wind")
        wind_pts = 0.0
        if w:
            wind_pts = {"CRITICAL": 2.0, "ELEVATED": 1.0}.get(w["threat_level"], 0.0)
        tpts = s["trigger_pts_base"] + wind_pts
        risk = tpts * (1 + s["fuels_pct"] / 25) * math.log10(max(p["pop"], 10))
        spc_best = max((h["dn"] for h in hits.get("spc", [])), default=None)
        entry = {
            "rank": 0,
            "name": p["n"], "state": p["st"], "lat": p["lat"], "lon": p["lon"],
            "population": p["pop"], "housing_units": p["hu"],
            "risk_index": round(risk, 1),
            "trigger_pts": round(tpts, 1),
            "red_flag": hits.get("redflag"),
            "spc_category": SPC_DN.get(spc_best),
            "spc_dry_lightning": bool(hits.get("spc_dryltg")),
            "psp_days": s["psp_days"],
            "fuels": {"wfpi": s["fuels"].get("wfpi"),
                      "wlfp_pct": s["fuels"].get("wlfp"),
                      "wfsp_pct": s["fuels"].get("wfsp"),
                      "pct_used": s["fuels_pct"], "source": s["fuels_source"]},
        }
        if w:
            entry["wind"] = {
                "threat_level": w["threat_level"],
                "mechanism": w["headline_mechanism"],
                "windninja_applicability": w["windninja_applicability"],
                "bust_axis": w["primary_bust_axis"],
                "peak": w["peak_surface"],
            }
        entries.append(entry)

    entries.sort(key=lambda e: -e["risk_index"])
    entries = entries[:OUTPUT_CAP]
    for i, e in enumerate(entries):
        e["rank"] = i + 1

    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "method_version": METHOD_VERSION,
        "formula": FORMULA,
        "coverage": "CONUS incorporated places + CDPs, population >= 1,000",
        "note": ("Ranks where official fire-weather triggers, dry fuels, and population "
                 "converge. Conditions ranking, not an ignition forecast."),
        "counts": {"trigger_regions": n_by, "candidates": len(cands)},
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def render_md(w):
    L = ["# 🎯 StormWatch Fire Watchlist",
         "",
         f"*Generated {w['generated_utc']} · method v{w['method_version']} · "
         "CONUS communities where official fire-weather triggers, dry fuels, and "
         "people converge (1-7 days). Not an ignition forecast.*",
         ""]
    if not w["entries"]:
        L.append("**No convergence today** — no populated place sits inside an active "
                 "Red Flag / SPC fire-weather / PSP significant-potential area.")
    for e in w["entries"]:
        L.append(f"## {e['rank']}. {e['name']}, {e['state']} — index {e['risk_index']}")
        L.append(f"*Population {e['population']:,} · {e['housing_units']:,} housing units*")
        trig = []
        if e["red_flag"]:
            trig.append(f"**Red Flag {e['red_flag']['kind'].upper()}**")
        if e["spc_category"]:
            trig.append(f"SPC **{e['spc_category']}**"
                        + (" + dry lightning" if e["spc_dry_lightning"] else ""))
        if e["psp_days"]:
            trig.append("PSP significant potential day(s) "
                        + ",".join(map(str, e["psp_days"])))
        L.append("- Trigger: " + (" · ".join(trig) if trig else "wind forecast only"))
        f = e["fuels"]
        fu = []
        if f["wfpi"] is not None:
            fu.append(f"WFPI {f['wfpi']}/247")
        if f["wlfp_pct"] is not None:
            fu.append(f"large-fire {f['wlfp_pct']:.0f}%")
        if f["wfsp_pct"] is not None:
            fu.append(f"spread {f['wfsp_pct']:.0f}%")
        L.append("- Fuels (USGS): " + (" · ".join(fu) if fu else "no valid cell"))
        if e.get("wind"):
            wd = e["wind"]
            pk = wd["peak"]
            L.append(f"- Wind: **{wd['threat_level']}** · {wd['mechanism']} · "
                     f"peak {pk['sustained_mph']:.0f}/{pk['gust_mph']:.0f} mph, "
                     f"RH {pk['min_rh_pct']}% · WindNinja: {wd['windninja_applicability']}")
        L.append("")
    L.append("---")
    L.append("*Sources: NWS (alerts) · SPC (fire wx outlooks) · NIFC Predictive Services "
             "(7-day potential) · USGS EROS (WFPI/WLFP/WFSP) · US Census (ACS 2023). "
             f"Formula: `{w['formula']}`*")
    return "\n".join(L)


def main(argv):
    # --json-out/--md-out write BOTH files from one computed result (the pipeline is
    # expensive -- ~60 sequential USGS calls + ~25 Open-Meteo calls, no concurrency by
    # design to stay polite to free government endpoints -- never run it twice per day).
    json_out = next((a.split("=", 1)[1] for a in argv if a.startswith("--json-out=")), None)
    md_out = next((a.split("=", 1)[1] for a in argv if a.startswith("--md-out=")), None)
    w = build_watchlist()
    if json_out or md_out:
        if json_out:
            with open(json_out, "w", encoding="utf-8") as f:
                json.dump(w, f, indent=1)
        if md_out:
            with open(md_out, "w", encoding="utf-8") as f:
                f.write(render_md(w))
    elif "--md" in argv:
        sys.stdout.write(render_md(w))
    else:
        sys.stdout.write(json.dumps(w, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
