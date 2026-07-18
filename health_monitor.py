#!/usr/bin/env python3
"""
StormWatch Live — Service Health Monitor ("check-ins")

Pings every external service StormWatch depends on with one tiny real request,
writes the scoreboard to data/health_status.json (read by diagnostics.html),
appends one compact row to data/health_history.jsonl, and — if an NTFY_TOPIC
secret is set — pushes a notification when a service goes DOWN or comes BACK.

Pure standard library: no pip install needed in CI. Companion to
alerts_monitor.py (same repo pattern: the git history is the time series).
"""

import json
import os
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

USER_AGENT = "StormWatchLive-HealthMonitor (https://github.com/aphilp1/stormwatch-live)"
STATUS_PATH = os.path.join("data", "health_status.json")
HISTORY_PATH = os.path.join("data", "health_history.jsonl")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
TIMEOUT = 25

ARC = "?where=1%3D1&outFields=OBJECTID&returnGeometry=false&resultRecordCount=1&f=json"

# name, url, kind  — kind: "json:<key>" requires that key in the parsed JSON,
# "text:<marker>" requires the marker substring, "reach" just needs HTTP < 500.
CHECKS = [
    ("Public site (GitHub Pages)", "https://aphilp1.github.io/stormwatch-live/weather-alerts.html", "text:StormWatch"),
    ("Cloud backend health", "https://stormwatch.stormwatch-live.workers.dev/health", "json:status"),
    ("Cloud Fire agent", "https://stormwatch.stormwatch-live.workers.dev/fire-agent?lat=34.05&lon=-118.25", "json:riskScore"),
    ("NWS active alerts", "https://api.weather.gov/alerts/active/count", "json:total"),
    ("NWS points API", "https://api.weather.gov/points/39.7392,-104.9847", "json:properties"),
    ("NIFC active incidents", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/EGP_Active_Incidents_Prod_Public_View/FeatureServer/0/query" + ARC, "json:features"),
    ("WFIGS perimeters", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query" + ARC, "json:features"),
    ("WFIGS daily perimeters", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Daily_Perimeters_Public/FeatureServer/0/query" + ARC, "json:features"),
    ("VIIRS heat detections", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/VIIRS_Heat_Detections/FeatureServer/0/query" + ARC, "json:features"),
    ("RAWS stations", "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/PublicView_RAWS/FeatureServer/1/query" + ARC.replace("OBJECTID", "StationID"), "json:features"),
    ("NIFC 7-day fire potential", "https://fsapps.nwcg.gov/psp/arcgis/rest/services/npsg/outlooks_forecast/MapServer/0/query" + ARC.replace("OBJECTID", "drynesscode"), "json:features"),
    ("SPC fire weather", "https://mapservices.weather.noaa.gov/vector/rest/services/fire_weather/SPC_firewx/MapServer?f=json", "json:layers"),
    ("USGS fire danger raster", "https://dmsdata.cr.usgs.gov/geoserver/firedanger_wfpi-forecast-1_conus_day_data/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&LAYERS=wfpi-forecast-1_conus_day_data&QUERY_LAYERS=wfpi-forecast-1_conus_day_data&CRS=CRS:84&BBOX=-116.24,43.37,-116.22,43.39&WIDTH=101&HEIGHT=101&I=50&J=50&INFO_FORMAT=application%2Fjson", "json:features"),
    ("RainViewer radar", "https://api.rainviewer.com/public/weather-maps.json", "json:radar"),
    ("IEM model WMS", "https://mesonet.agron.iastate.edu/cgi-bin/wms/hrrr/refd.cgi?service=WMS&request=GetCapabilities", "reach"),
    ("River gauges", "https://mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query" + ARC.replace("OBJECTID", "gaugelid"), "json:features"),
    ("USGS streamflow", "https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items?f=json&parameter_code=00060&limit=1", "json:features"),
    ("Montana Mesonet", "https://mesonet.climate.umt.edu/api/v2/stations/?type=json&active=true", "json_list"),
    ("CARTO basemap", "https://a.basemaps.cartocdn.com/light_all/4/4/6.png", "reach"),
    ("CDN libraries", "https://cdn.jsdelivr.net/npm/leaflet-velocity@1.7.0/dist/leaflet-velocity.min.js", "reach"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)


def run_check(name, url, kind):
    t0 = time.time()
    try:
        with fetch(url) as r:
            code = r.getcode()
            body = r.read(400_000)
        ms = int((time.time() - t0) * 1000)
        if code >= 500:
            return {"name": name, "status": "fail", "note": f"HTTP {code}", "ms": ms}
        if kind == "reach":
            return {"name": name, "status": "ok", "note": f"HTTP {code}", "ms": ms}
        if kind.startswith("text:"):
            ok = kind[5:].encode() in body
            return {"name": name, "status": "ok" if ok else "warn",
                    "note": "live" if ok else "unexpected body", "ms": ms}
        data = json.loads(body)
        if kind == "json_list":
            ok = isinstance(data, list) and len(data) > 0
        else:
            key = kind.split(":", 1)[1]
            ok = isinstance(data, dict) and key in data and "error" not in data
        return {"name": name, "status": "ok" if ok else "warn",
                "note": "live data" if ok else "unexpected payload", "ms": ms}
    except Exception as e:  # noqa: BLE001 — any failure = service unreachable
        ms = int((time.time() - t0) * 1000)
        reason = getattr(e, "code", None) or getattr(e, "reason", None) or type(e).__name__
        return {"name": name, "status": "fail", "note": str(reason)[:80], "ms": ms}


def notify(title, message, priority="high"):
    if not NTFY_TOPIC:
        return
    try:
        req = urllib.request.Request(
            f"{NTFY_SERVER}/{NTFY_TOPIC}", data=message.encode(),
            headers={"User-Agent": USER_AGENT, "Title": title,
                     "Priority": priority, "Tags": "stethoscope"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:  # noqa: BLE001 — never let a push failure kill the run
        print(f"ntfy push failed: {e}")


def main():
    now = datetime.now(timezone.utc)
    results = [run_check(*c) for c in CHECKS]
    for r in results:
        print(f"[{r['status'].upper():4}] {r['name']} ({r['ms']} ms) {r['note']}")

    prev_down = set()
    try:
        with open(STATUS_PATH, encoding="utf-8") as f:
            prev_down = {r["name"] for r in json.load(f).get("results", []) if r["status"] == "fail"}
    except (OSError, ValueError):
        pass

    down = {r["name"] for r in results if r["status"] == "fail"}
    new_down, recovered = down - prev_down, prev_down - down
    if new_down:
        notify("StormWatch service DOWN",
               "Failing: " + ", ".join(sorted(new_down)) +
               f"\nTotal down: {len(down)}/{len(results)}. See diagnostics.html.")
    if recovered and not new_down:
        notify("StormWatch service recovered",
               "Back up: " + ", ".join(sorted(recovered)), priority="default")

    os.makedirs("data", exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({"checked_utc": now.isoformat(timespec="seconds"), "results": results}, f, indent=1)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now.isoformat(timespec="seconds"),
                            "ok": sum(r["status"] == "ok" for r in results),
                            "warn": sum(r["status"] == "warn" for r in results),
                            "fail": sorted(down)}) + "\n")
    print(f"\n{len(results)} checks: {len(results) - len(down)} up, {len(down)} down.")


if __name__ == "__main__":
    main()
