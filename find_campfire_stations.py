#!/usr/bin/env python3
"""
find_campfire_stations.py
=========================
Discover RAWS / ASOS station IDs near the Camp Fire area.
Once we have IDs, fetch Nov 8 2018 data via IEM.

Run: python find_campfire_stations.py
"""
import sys, requests, math, json
sys.stdout.reconfigure(encoding="utf-8")

# Camp Fire area center
FIRE_LAT, FIRE_LON = 39.8, -121.5
RADIUS_MILES = 35

def haversine_mi(lat1, lon1, lat2, lon2):
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ---------------------------------------------------------------------------
# 1. IEM network station list
# ---------------------------------------------------------------------------

def get_iem_network_stations(network):
    """Fetch IEM station metadata for a given network code."""
    r = requests.get(f"https://mesonet.agron.iastate.edu/api/1/stations.json",
                     params={"network": network}, timeout=30)
    if r.status_code != 200:
        return []
    return r.json().get("data", [])


def find_nearby(stations, lat, lon, radius_mi):
    nearby = []
    for s in stations:
        slat = s.get("lat") or s.get("latitude")
        slon = s.get("lon") or s.get("longitude")
        if slat is None or slon is None:
            continue
        d = haversine_mi(lat, lon, float(slat), float(slon))
        if d <= radius_mi:
            nearby.append({**s, "_dist_mi": round(d, 1)})
    return sorted(nearby, key=lambda x: x["_dist_mi"])


# ---------------------------------------------------------------------------
# 2. IEM ASOS fetch (debug version -- print raw response)
# ---------------------------------------------------------------------------

def fetch_iem_asos_raw(station_id):
    r = requests.get("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", params={
        "station": station_id, "data": "all",
        "year1": "2018", "month1": "11", "day1": "8",
        "year2": "2018", "month2": "11", "day2": "8",
        "tz": "UTC", "format": "onlycomma", "latlon": "no",
        "missing": "M", "trace": "T", "direct": "no", "report_type": "1",
    }, timeout=20)
    return r.text


# ---------------------------------------------------------------------------
# 3. IEM RAWS fetch for a specific station
# ---------------------------------------------------------------------------

def fetch_iem_raws_station(station_id):
    """
    IEM RAWS archive. Station IDs are typically the MesoWest/RAWS ID.
    Returns raw text of the response.
    """
    r = requests.get("https://mesonet.agron.iastate.edu/request/raws/fe.py", params={
        "station": station_id,
        "year1": "2018", "month1": "11", "day1": "8", "hour1": "6",
        "year2": "2018", "month2": "11", "day2": "8", "hour2": "18",
        "what": "download", "delim": "comma",
    }, timeout=30)
    return r.text


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  Discovering RAWS/ASOS stations near Camp Fire (39.8N, -121.5W)")
    print("=" * 70)

    # Try several IEM network codes for California RAWS
    raws_networks = ["CA_RAWS", "BIG_RAWS", "RAWS", "CA_DRI"]
    asos_networks = ["CA_ASOS", "ASOS"]

    found_raws = []
    for net in raws_networks:
        print(f"\n  IEM network '{net}'...", end=" ", flush=True)
        stns = get_iem_network_stations(net)
        print(f"{len(stns)} stations total.", end=" ")
        nearby = find_nearby(stns, FIRE_LAT, FIRE_LON, RADIUS_MILES)
        print(f"{len(nearby)} within {RADIUS_MILES}mi.")
        if nearby:
            found_raws.extend(nearby)
            for s in nearby[:15]:
                sid  = s.get("id") or s.get("stid") or s.get("station_id", "?")
                name = s.get("name", "?")
                lat  = s.get("lat") or s.get("latitude", "?")
                lon  = s.get("lon") or s.get("longitude", "?")
                elev = s.get("elevation", "?")
                dist = s["_dist_mi"]
                print(f"    {sid:10s} {name:35s} {lat}N {lon}W  elev={elev}ft  {dist}mi")
            break   # stop once we find a working network

    found_asos = []
    for net in asos_networks:
        print(f"\n  IEM network '{net}'...", end=" ", flush=True)
        stns = get_iem_network_stations(net)
        print(f"{len(stns)} stations total.", end=" ")
        nearby = find_nearby(stns, FIRE_LAT, FIRE_LON, RADIUS_MILES)
        print(f"{len(nearby)} within {RADIUS_MILES}mi.")
        if nearby:
            found_asos.extend(nearby)
            for s in nearby[:8]:
                sid  = s.get("id") or s.get("stid") or "?"
                name = s.get("name", "?")
                dist = s["_dist_mi"]
                print(f"    {sid:10s} {name:35s}  {dist}mi")
            break

    # Try Chico ASOS with debug output
    print()
    print("  IEM ASOS test -- Chico (CIC), first 5 lines of response:")
    raw = fetch_iem_asos_raw("CIC")
    for line in raw.split("\n")[:8]:
        if line.strip():
            print(f"    {line[:100]}")

    # Try fetching RAWS data for any found stations
    if found_raws:
        print()
        print("  IEM RAWS fetch test -- first 3 stations:")
        for s in found_raws[:3]:
            sid = s.get("id") or s.get("stid") or s.get("station_id", "?")
            print(f"\n  Fetching {sid} ({s.get('name','?')})...")
            raw = fetch_iem_raws_station(sid)
            lines = [l for l in raw.split("\n") if l.strip()]
            print(f"    {len(lines)} lines returned")
            for line in lines[:6]:
                print(f"    {line[:100]}")
    else:
        print()
        print("  No RAWS stations found via IEM networks.")
        print("  Try manual station ID lookup via:")
        print("    https://www.wrcc.dri.edu/cgi-bin/wea_find.pl (WRCC RAWS finder)")
        print("    https://www.nifc.gov/nifc_web/NIFC_Main/assets/docs/RAWS-Locations.pdf")
        print("    https://famit.nwcg.gov/applications/FireFamily")
