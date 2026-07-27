"""
fire_watchlist.py
=================

StormWatch Fire Briefing (spec: Storm_info/fable_specs/06_fire_watchlist.md, v2).

A daily WRITTEN briefing, not a ranked list of index numbers. Two sections:

  Active Threats     -- real, currently-burning NIFC wildfires, ranked by the
                         incident team's own reported structures-threatened count
                         (the direct, authoritative "risk to property" number),
                         containment, and size. Each gets a real paragraph: what's
                         burning, how big, what's at stake, and what the forecast
                         wind is expected to do to it (via the repo's own
                         mechanism_classifier -- what KIND of wind event, not just
                         a number).
  Emerging Conditions -- places with NO fire yet but where an official trigger
                         (Red Flag / SPC outlook / NIFC 7-day potential) sits over
                         dry fuels and people. Grouped into regional paragraphs
                         instead of a town-by-town wall of near-duplicates.

Every fact quoted is an agency value shown as-served (NIFC ICS-209 fields, USGS
fire danger, Census population) -- the narrative sentences are deterministic
templates filled from real numbers, not a black-box score and not an LLM call
(this runs unattended in a GitHub Action; no API key, no cost, no network
dependency beyond the public data feeds it already uses).

Pure standard library. Outputs:
    python fire_watchlist.py --json-out=data/fire_watchlist.json --md-out=FIRE_WATCHLIST.md
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from live_forecast import forecast_site

METHOD_VERSION = "2.0"
UA = {"User-Agent": "StormWatchLive-FireBriefing/2.0 (github.com/aphilp1/stormwatch-live)"}

NIFC_INCIDENTS_BASE = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
                       "EGP_Active_Incidents_Prod_Public_View/FeatureServer/0/query")
MIRROR_INCIDENTS_BASE = ("https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/"
                         "USA_Wildfires_v1/FeatureServer/0/query")
SPC_FWX = "https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer"
PSP_BASE = "https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer"
NWS_ALERTS = ("https://api.weather.gov/alerts/active"
              "?event=Red%20Flag%20Warning,Fire%20Weather%20Watch&status=actual")
USGS_BASE = "https://dmsdata.cr.usgs.gov/geoserver"

MIN_FIRE_ACRES = 100          # floor for an "active threat" candidate
MAX_ACTIVE_THREATS = 8        # detailed paragraphs in the briefing
CANDIDATE_CAP = 60            # emerging-condition places scored for fuels
CLASSIFIER_CAP_ACTIVE = 12    # active fires run through the wind classifier
EMERGING_CLUSTER_DEG = (3.0, 4.0)   # lat, lon bin size for regional grouping
MAX_EMERGING_REGIONS = 4
DEDUPE_DEG = 0.25
POOL_WORKERS = 6
NEARBY_RADIUS_MI = 40          # how far to look for an exposed town near a fire

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


def haversine_mi(lat1, lon1, lat2, lon2):
    R = 3958.8
    rad = math.radians
    dlat, dlon = rad(lat2 - lat1), rad(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Compass bearing FROM point 1 TOWARD point 2."""
    rad = math.radians
    y = math.sin(rad(lon2 - lon1)) * math.cos(rad(lat2))
    x = math.cos(rad(lat1)) * math.sin(rad(lat2)) - math.sin(rad(lat1)) * math.cos(rad(lat2)) * math.cos(rad(lon2 - lon1))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass8(deg):
    return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][round(deg / 45) % 8]


def angle_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ---------------------------------------------------------------------------
# Geometry: pure-python point-in-polygon (reused for emerging-condition triggers)
# ---------------------------------------------------------------------------

def _rings(geom):
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
            yield poly


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
# Active Threats: real, currently-burning NIFC wildfires
# ---------------------------------------------------------------------------

def _incident_acres(a):
    return max(a.get("DailyAcres") or 0, a.get("CalculatedAcres") or 0, a.get("CALC_GISAcres") or 0)


def fetch_active_fires():
    where = urllib.parse.quote("Incident_Type_Kind LIKE '%WF%' AND PercentContained < 100")
    fields = ("Name,DailyAcres,CalculatedAcres,CALC_GISAcres,PercentContained,POOState,County,"
              "Discovery_Date,CALC_TotalStructuresThreatened,TotalIncidentPersonnel,IrwinID")
    url = (f"{NIFC_INCIDENTS_BASE}?where={where}&outFields={fields}"
           "&outSR=4326&returnGeometry=true&f=json&resultRecordCount=2000")
    mirrored = False
    try:
        d = _get_json(url, timeout=40)
        if "error" in d:
            raise RuntimeError(d["error"])
    except Exception as e:                # noqa: BLE001
        print(f"warn: NIFC incidents failed ({e}), trying Esri mirror", file=sys.stderr)
        mwhere = urllib.parse.quote("IncidentTypeCategory = 'WF' AND PercentContained < 100")
        mfields = ("IncidentName,DailyAcres,CalculatedAcres,PercentContained,POOState,POOCounty,"
                   "FireDiscoveryDateTime,TotalIncidentPersonnel,IrwinID,ResidencesDestroyed,OtherStructuresDestroyed")
        murl = (f"{MIRROR_INCIDENTS_BASE}?where={mwhere}&outFields={mfields}"
                "&outSR=4326&returnGeometry=true&f=json&resultRecordCount=2000")
        d = _get_json(murl, timeout=40)
        mirrored = True

    fires = []
    for f in d.get("features", []):
        a = f["attributes"]
        g = f.get("geometry")
        if not g:
            continue
        if mirrored:
            acres = max(a.get("DailyAcres") or 0, a.get("CalculatedAcres") or 0)
            structs = None    # mirror has no "threatened" field, only destroyed-to-date
            name, state, county = a.get("IncidentName"), a.get("POOState"), a.get("POOCounty")
            personnel = a.get("TotalIncidentPersonnel")
        else:
            acres = _incident_acres(a)
            structs = a.get("CALC_TotalStructuresThreatened")
            name, state, county = a.get("Name"), a.get("POOState"), a.get("County")
            personnel = a.get("TotalIncidentPersonnel")
        if acres < MIN_FIRE_ACRES:
            continue
        fires.append({
            "name": (name or "Unnamed Fire").title(), "state": (state or "").replace("US-", ""),
            "county": county, "acres": acres, "pct_contained": a.get("PercentContained"),
            "structures_threatened": structs, "personnel": personnel,
            "lat": g["y"], "lon": g["x"], "mirrored": mirrored,
        })
    return fires


def nearest_places(lat, lon, places, radius_mi=NEARBY_RADIUS_MI, limit=3):
    hits = []
    for p in places:
        if abs(p["lat"] - lat) > 1.0 or abs(p["lon"] - lon) > 1.3:
            continue                       # cheap bbox prefilter (~1 deg ~ 60-70 mi)
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d <= radius_mi:
            hits.append((d, p))
    hits.sort(key=lambda t: t[0])
    return hits[:limit]


def wind_narrative(wind, fire_lat, fire_lon, nearby):
    """Prose describing the forecast wind at a fire, incl. whether it favors a nearby town."""
    if not wind:
        return "A forecast wind read wasn't available for this fire today."
    pk = wind["peak_surface"]
    mech = wind["headline_mechanism"]
    threat = wind["threat_level"]
    gust, sustained, rh = pk["gust_mph"], pk["sustained_mph"], pk["min_rh_pct"]

    lead = {
        "CRITICAL": f"Forecast conditions over the next 24 hours are critical for fire behavior: "
                    f"gusts to {gust:.0f} mph with humidity dropping as low as {rh}%.",
        "ELEVATED": f"Forecast winds will be locally gusty (up to {gust:.0f} mph, sustained near "
                    f"{sustained:.0f}) with humidity as low as {rh}%.",
        "BENIGN": f"Winds are expected to stay comparatively light over the next 24 hours "
                  f"(gusts near {gust:.0f} mph), which should limit further wind-driven spread for now.",
    }.get(threat, f"Peak forecast gust is {gust:.0f} mph, humidity as low as {rh}%.")

    mech_note = {
        "SYNOPTIC_TERRAIN": " This is a sustained, terrain-channeled wind regime — the setup "
                            "our WindNinja terrain downscaling is built to resolve.",
        "PBL_TRANSIENT": " A wind shift is expected during the window — the kind of transition "
                         "that is hardest for a 3 km forecast model to time and place precisely.",
        "CONVECTIVE_OUTFLOW": " Any thunderstorm outflow nearby could produce a sudden, "
                              "hard-to-predict wind reversal on the fire's flank.",
    }.get(mech, "")

    toward = ""
    if nearby and pk.get("dir_deg") is not None:
        downwind = (pk["dir_deg"] + 180) % 360
        d0, place0 = nearby[0]
        bearing = bearing_deg(fire_lat, fire_lon, place0["lat"], place0["lon"])
        if angle_diff(downwind, bearing) <= 45:
            toward = (f" Forecast wind direction ({compass8(pk['dir_deg'])}, blowing toward the "
                      f"{compass8(downwind)}) favors pushing the fire toward {place0['n']}, "
                      f"{d0:.0f} miles away.")
        else:
            toward = (f" Forecast wind ({compass8(pk['dir_deg'])}) is not currently aligned toward "
                      f"{place0['n']}, the nearest community of size, {d0:.0f} miles away.")
    return lead + mech_note + toward


def fire_paragraph(fire, wind, nearby):
    acres_s = f"{fire['acres']:,.0f}"
    where = ", ".join(x for x in (fire["county"] and f"{fire['county']} County", fire["state"]) if x)
    lead = f"The {fire['name']} Fire"
    if where:
        lead += f" in {where}"
    lead += f" has burned {acres_s} acres and is {fire['pct_contained']}% contained."

    stakes = []
    st = fire.get("structures_threatened")
    if st:
        stakes.append(f"NIFC's incident team reports **{st:,} structures threatened**.")
    elif st == 0 and nearby:
        d0, place0 = nearby[0]
        stakes.append(f"No structures are currently reported threatened, though {place0['n']} "
                      f"(pop. {place0['pop']:,}) sits {d0:.0f} miles away.")
    if fire.get("personnel"):
        stakes.append(f"{fire['personnel']:,} personnel are assigned.")
    if fire.get("mirrored"):
        stakes.append("(NIFC's primary feed was unavailable today — this record is from the "
                      "Esri Living Atlas mirror, which does not carry a structures-threatened field.)")

    wind_txt = wind_narrative(wind, fire["lat"], fire["lon"], nearby)
    return " ".join([lead] + stakes + [wind_txt])


def fire_threat_score(fire):
    st = fire.get("structures_threatened") or 0
    contained = fire.get("pct_contained") or 0
    return math.log1p(st) * 3 + (1 - contained / 100) * 2 + math.log10(fire["acres"] + 1)


# ---------------------------------------------------------------------------
# Emerging Conditions: trigger x fuels x exposure, grouped into regions
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
    for lyr in range(7):
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
        detail = {"kind": kind}
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
            if geom:
                regions.append(Region(geom, "redflag", detail))
    return regions


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
        return None
    p = feats[0].get("properties") or {}
    v = p.get("PALETTE_INDEX", p.get("GRAY_INDEX"))
    return v if isinstance(v, (int, float)) else None


def fuels_at(lat, lon):
    pts = [(lat, lon), (lat + 0.08, lon)]
    out = {}
    for prod in ("wfpi", "wlfp", "wfsp"):
        best = None
        for la, lo in pts:
            v = _gfi(prod, la, lo)
            if v is not None and v < 248:
                best = v if best is None else max(best, v)
        out[prod] = best
    return out


def fuels_pct(fu):
    probs = [v for v in (fu.get("wlfp"), fu.get("wfsp")) if v is not None]
    if probs:
        return max(probs), "wlfp/wfsp"
    if fu.get("wfpi") is not None:
        return fu["wfpi"] / 150 * 20, "wfpi"
    return 0.0, "none"


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


def find_emerging_candidates(places):
    regions = fetch_spc_regions() + fetch_psp_regions() + fetch_redflag_regions()
    region_counts = {}
    for r in regions:
        region_counts[r.tag] = region_counts.get(r.tag, 0) + 1

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

    best = {}
    for p, hits in cands:
        key = (round(p["lat"] / DEDUPE_DEG), round(p["lon"] / DEDUPE_DEG))
        if key not in best or p["pop"] > best[key][0]["pop"]:
            best[key] = (p, hits)

    def _prio(t):
        p, hits = t
        return trigger_points(hits)[0] * math.log10(max(p["pop"], 10))
    cands = sorted(best.values(), key=lambda t: -_prio(t))[:CANDIDATE_CAP]

    def _score_one(item):
        p, hits = item
        fu = fuels_at(p["lat"], p["lon"])
        fpct, fsrc = fuels_pct(fu)
        tpts, psp_days = trigger_points(hits)
        return {"place": p, "hits": hits, "fuels_pct": round(fpct, 1), "fuels_source": fsrc,
                "psp_days": psp_days, "trigger_pts": tpts}
    with ThreadPoolExecutor(max_workers=POOL_WORKERS) as ex:
        scored = list(ex.map(_score_one, cands))
    return scored, region_counts


def cluster_regions(scored):
    """Group emerging-condition places into ~lat/lon bins so the briefing reads as a
    handful of regional paragraphs instead of a wall of near-duplicate small towns."""
    bins = {}
    latbin, lonbin = EMERGING_CLUSTER_DEG
    for s in scored:
        p = s["place"]
        key = (round(p["lat"] / latbin), round(p["lon"] / lonbin))
        bins.setdefault(key, []).append(s)

    clusters = []
    for members in bins.values():
        members.sort(key=lambda s: -s["place"]["pop"])
        total_weight = sum(m["trigger_pts"] * math.log10(max(m["place"]["pop"], 10)) for m in members)
        clusters.append({"members": members, "weight": total_weight})
    clusters.sort(key=lambda c: -c["weight"])
    return clusters[:MAX_EMERGING_REGIONS]


def region_paragraph(cluster):
    members = cluster["members"]
    top_names = [f"{m['place']['n']}" for m in members[:5]]
    states = sorted({m["place"]["st"] for m in members})
    place_str = ", ".join(top_names[:-1]) + (f", and {top_names[-1]}" if len(top_names) > 1 else top_names[0])
    n_more = len(members) - len(top_names)
    plural = len(members) > 1 or n_more > 0

    spc_cats = [h["dn"] for m in members for h in m["hits"].get("spc", [])]
    best_spc = SPC_DN.get(max(spc_cats)) if spc_cats else None
    psp_days = sorted({d for m in members for d in m["psp_days"]})
    fuels_vals = [m["fuels_pct"] for m in members if m["fuels_pct"] > 0]
    has_redflag = any(m["hits"].get("redflag") for m in members)

    lead = f"A fire-weather pattern is developing over {', '.join(states)}: {place_str}"
    if n_more > 0:
        lead += f" and {n_more} other communities"
    lead += " sit under" if plural else " sits under"

    trig_bits = []
    if has_redflag:
        trig_bits.append("an active Red Flag Warning or Watch")
    if best_spc:
        trig_bits.append(f"SPC's **{best_spc}** fire-weather category")
    if psp_days:
        trig_bits.append(f"NIFC's Significant Fire Potential outlook (day{'s' if len(psp_days)>1 else ''} "
                         + ",".join(map(str, psp_days)) + ")")
    lead += " " + " and ".join(trig_bits) + "."

    fuels_txt = ""
    if fuels_vals:
        fuels_txt = (f" USGS fire-danger models put the local large-fire/spread probability as high as "
                     f"{max(fuels_vals):.0f}% in spots.")

    tail = (" No fire has been reported yet, but the combination of dry fuels and elevated fire "
            "weather is exactly the kind that produces a fast-moving run if an ignition occurs.")
    return lead + fuels_txt + tail


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_briefing():
    places = json.load(open("data/place_exposure.json", encoding="utf-8"))["places"]

    print("fetching active fires...", file=sys.stderr)
    fires = fetch_active_fires()
    fires.sort(key=lambda f: -fire_threat_score(f))
    top_fires = fires[:MAX_ACTIVE_THREATS]
    print(f"active uncontained wildfires >= {MIN_FIRE_ACRES}ac: {len(fires)}, detailing top {len(top_fires)}",
          file=sys.stderr)

    print("running wind classifier on active fires...", file=sys.stderr)
    classify_set = top_fires[:CLASSIFIER_CAP_ACTIVE]
    def _classify(f):
        try:
            return forecast_site(f["name"], f["lat"], f["lon"], "auto", 24)
        except Exception as e:            # noqa: BLE001
            print(f'warn: classifier failed for {f["name"]}: {e}', file=sys.stderr)
            return None
    with ThreadPoolExecutor(max_workers=POOL_WORKERS) as ex:
        winds = list(ex.map(_classify, classify_set))

    active_entries = []
    for fire, wind in zip(top_fires, winds):
        nearby_raw = nearest_places(fire["lat"], fire["lon"], places)
        nearby = [{"n": p["n"], "st": p["st"], "pop": p["pop"], "distance_mi": round(d, 1)}
                  for d, p in nearby_raw]
        narrative = fire_paragraph(fire, wind, nearby_raw)
        entry = {**fire, "nearby_places": nearby, "narrative": narrative}
        if wind:
            entry["wind"] = {"threat_level": wind["threat_level"], "mechanism": wind["headline_mechanism"],
                             "windninja_applicability": wind["windninja_applicability"],
                             "peak": wind["peak_surface"]}
        active_entries.append(entry)

    print("scoring emerging conditions...", file=sys.stderr)
    scored, region_counts = find_emerging_candidates(places)
    clusters = cluster_regions(scored)
    emerging_entries = []
    for c in clusters:
        lead_place = c["members"][0]["place"]
        emerging_entries.append({
            "lat": lead_place["lat"], "lon": lead_place["lon"],
            "states": sorted({m["place"]["st"] for m in c["members"]}),
            "places": [m["place"]["n"] for m in c["members"][:8]],
            "narrative": region_paragraph(c),
        })

    if active_entries:
        lead = active_entries[0]
        st_txt = f", threatening {lead['structures_threatened']:,} structures" if lead.get("structures_threatened") else ""
        headline = (f"{len(fires)} active wildfire{'s are' if len(fires)!=1 else ' is'} burning uncontained "
                   f"in the US today. The most serious is the {lead['name']} Fire in {lead['state']}"
                   f"{st_txt}.")
    elif emerging_entries:
        headline = ("No wildfire is currently threatening a populated area. The most fire-weather-favorable "
                   f"conditions today are over {', '.join(emerging_entries[0]['states'])}.")
    else:
        headline = "No active wildfire threats and no significant fire-weather convergence found today."

    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "method_version": METHOD_VERSION,
        "headline": headline,
        "counts": {"active_uncontained_fires": len(fires), "trigger_regions": region_counts,
                  "emerging_candidates": len(scored)},
        "active_threats": active_entries,
        "emerging_conditions": emerging_entries,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def render_md(w):
    L = ["# 🔥 StormWatch Fire Briefing", "",
         f"*Generated {w['generated_utc']} · method v{w['method_version']} · CONUS. "
         "Every fact is quoted from NIFC/SPC/USGS/Census as reported — the wind read is "
         "StormWatch's own mechanism classifier.*", "",
         f"**{w['headline']}**", ""]

    if w["active_threats"]:
        L.append("## Active Threats")
        L.append("")
        for f in w["active_threats"]:
            L.append(f"### {f['name']} Fire — {f['state']}")
            L.append(f['narrative'])
            L.append("")
    if w["emerging_conditions"]:
        L.append("## Emerging Conditions to Watch")
        L.append("")
        for e in w["emerging_conditions"]:
            L.append(e["narrative"])
            L.append("")
    if not w["active_threats"] and not w["emerging_conditions"]:
        L.append("Nothing meets the bar today.")
    L.append("---")
    L.append("*Sources: NIFC (active incidents, ICS-209 fields) · NWS (alerts) · SPC (fire weather "
             "outlooks) · NIFC Predictive Services (7-day potential) · USGS EROS (fire danger) · "
             "US Census (ACS 2023). Wind read: StormWatch's own mechanism_classifier.*")
    return "\n".join(L)


def main(argv):
    json_out = next((a.split("=", 1)[1] for a in argv if a.startswith("--json-out=")), None)
    md_out = next((a.split("=", 1)[1] for a in argv if a.startswith("--md-out=")), None)
    w = build_briefing()
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
