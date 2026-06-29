#!/usr/bin/env python3
"""
StormWatch Live — IEM Historical Backfill (Path C, Layer 1)

THE UNLOCK. Downloads the NWS Watch/Warning/Advisory archive from the Iowa
Environmental Mesonet (every warning ever issued, back decades) and reconstructs
an HOURLY time series of "how many alerts of each type were active" — in the
EXACT same schema as the live collector (alerts_monitor.py). The moment this
finishes, the scorer has years of directly comparable history: no blind period.

Source:  https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py
  - returns one CSV row per county/zone segment of a warning
  - columns: wfo, utc_issue, utc_expire, phenomena, significance, eventid, vtec_year, ...
  - LIMIT: 1 year per request when not filtered by state/wfo/phenomena
            -> we chunk by MONTH (well under the limit, keeps each file modest)

Method per month:
  1. Download CSV for [month_start - LOOKBACK, month_end]  (lookback catches
     long-lived warnings issued just before the month that are still active in it).
  2. Dedupe county-segments to unique VTEC EVENTS = (vtec_year, wfo, phenomena,
     significance, eventid). An event's active interval = [min(issue), max(expire)]
     across its segments. This matches the live feed, which counts alerts (events),
     not zones.
  3. Difference-array sweep: each event adds +1 to every hour it's active for its
     hazard. Prefix-sum -> active-count per hour per hazard. O(events + hours).
  4. Emit one {"t","by_event"} row per hour into data/baseline_hourly.jsonl.

Resumable (skips months already in data/baseline_manifest.json) and polite
(sleeps between requests). Pure standard library.

Usage:
  python backfill_iem.py --start 2010 --end 2024      # full run, monthly chunks
  python backfill_iem.py --test 2023-06               # one month -> data/_test_backfill.jsonl
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py"
USER_AGENT = "StormWatchLive-Backfill (https://github.com/aphilp1/stormwatch-live)"

OUT_PATH = os.path.join("data", "baseline_hourly.jsonl")
MANIFEST_PATH = os.path.join("data", "baseline_manifest.json")
LOOKBACK_DAYS = 10          # catch long warnings issued just before a month
REQUEST_PAUSE = 3.0         # seconds between IEM requests (be polite)
HTTP_RETRIES = 3

# ---------------------------------------------------------------------------
# VTEC code -> current NWS hazard display name.
# We key by CURRENT names so the archive lines up with what the live feed emits
# today (e.g. EH.W is now "Extreme Heat Warning"), staying internally consistent
# across all years. Covers the hazards that matter; rare codes fall back to "PH.S".
# ---------------------------------------------------------------------------
SIG = {"W": "Warning", "A": "Watch", "Y": "Advisory", "S": "Statement",
       "F": "Forecast", "O": "Outlook", "N": "Synopsis"}

PHEN = {
    "TO": "Tornado", "SV": "Severe Thunderstorm", "FF": "Flash Flood",
    "FL": "Flood", "FA": "Flood", "MA": "Marine", "EH": "Extreme Heat",
    "HT": "Heat", "EC": "Extreme Cold", "WC": "Wind Chill", "FW": "Fire Weather",
    "HW": "High Wind", "WI": "Wind", "WS": "Winter Storm", "WW": "Winter Weather",
    "BZ": "Blizzard", "IS": "Ice Storm", "ZR": "Freezing Rain", "LE": "Lake Effect Snow",
    "WND": "Wind", "DS": "Dust Storm", "DU": "Blowing Dust", "FG": "Dense Fog",
    "SM": "Dense Smoke", "HU": "Hurricane", "TR": "Tropical Storm", "TY": "Typhoon",
    "SS": "Storm Surge", "TS": "Tsunami", "CF": "Coastal Flood", "LS": "Lakeshore Flood",
    "SU": "High Surf", "RP": "Rip Current", "SC": "Small Craft", "GL": "Gale",
    "SR": "Storm", "HF": "Hurricane Force Wind", "SE": "Hazardous Seas",
    "AF": "Ashfall", "AS": "Air Stagnation", "FZ": "Freeze", "FR": "Frost",
    "HZ": "Hard Freeze", "EW": "Extreme Wind", "SQ": "Snow Squall", "BW": "Brisk Wind",
    "LW": "Lake Wind", "ZF": "Freezing Fog", "UP": "Heavy Freezing Spray",
    "AQ": "Air Quality", "CW": "Cold Weather",
}

# Special cases where name != "<phen> <sig>".
OVERRIDES = {
    ("FW", "W"): "Red Flag Warning",
    ("FW", "A"): "Fire Weather Watch",
    ("FA", "Y"): "Flood Advisory",
    ("FA", "W"): "Areal Flood Warning",
    ("FA", "A"): "Flood Watch",
    ("MA", "W"): "Marine Warning",
    ("SV", "A"): "Severe Thunderstorm Watch",
}


def hazard_name(phen, sig):
    if (phen, sig) in OVERRIDES:
        return OVERRIDES[(phen, sig)]
    p = PHEN.get(phen)
    s = SIG.get(sig)
    if p and s:
        return f"{p} {s}"
    return f"{phen}.{sig}"          # unmapped: stable code string


# ---------------------------------------------------------------------------
def parse_ts(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def download_csv(sts, ets):
    """Stream the IEM CSV for [sts, ets] to a string. Retries on transient errors."""
    q = (f"{IEM_URL}?accept=csv&timeopt=1"
         f"&sts={sts.strftime('%Y-%m-%dT%H:%MZ')}"
         f"&ets={ets.strftime('%Y-%m-%dT%H:%MZ')}")
    last = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(q, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e
            print(f"  [http] attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"download failed after {HTTP_RETRIES} tries: {last}")


def reconstruct_month(csv_text, month_start, month_end):
    """Return list of {"t","by_event"} rows, one per hour in [month_start,month_end)."""
    # 1) Dedupe segments -> unique events with [min issue, max expire] + hazard.
    events = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        issue = parse_ts(row.get("utc_issue"))
        expire = parse_ts(row.get("utc_expire")) or parse_ts(row.get("utc_init_expire"))
        if not issue or not expire or expire <= issue:
            continue
        key = (row.get("vtec_year"), row.get("wfo"), row.get("phenomena"),
               row.get("significance"), row.get("eventid"))
        ev = events.get(key)
        if ev is None:
            events[key] = [issue, expire,
                           hazard_name(row.get("phenomena", ""), row.get("significance", ""))]
        else:
            if issue < ev[0]:
                ev[0] = issue
            if expire > ev[1]:
                ev[1] = expire

    # 2) Hourly difference-array sweep per hazard over the month.
    n_hours = int((month_end - month_start).total_seconds() // 3600)
    diffs = {}   # hazard -> list[n_hours+1] of int deltas
    for issue, expire, haz in events.values():
        start_idx = int((issue - month_start).total_seconds() // 3600)
        end_idx = int((expire - month_start).total_seconds() // 3600) + 1  # active through its expire hour
        start_idx = max(0, start_idx)
        end_idx = min(n_hours, end_idx)
        if end_idx <= start_idx:
            continue
        d = diffs.get(haz)
        if d is None:
            d = [0] * (n_hours + 1)
            diffs[haz] = d
        d[start_idx] += 1
        d[end_idx] -= 1

    # 3) Prefix-sum -> per-hour counts; emit compact rows (non-zero hazards only).
    rows = []
    running = {haz: 0 for haz in diffs}
    for h in range(n_hours):
        by_event = {}
        for haz, d in diffs.items():
            running[haz] += d[h]
            if running[haz] > 0:
                by_event[haz] = running[haz]
        t = (month_start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%MZ")
        rows.append({"t": t, "by_event": by_event})
    return rows


def month_bounds(year, month):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = (datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12
           else datetime(year, month + 1, 1, tzinfo=timezone.utc))
    return start, end


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        try:
            return set(json.load(open(MANIFEST_PATH, encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_manifest(done):
    os.makedirs("data", exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f, indent=0)


def do_month(year, month, out_path):
    start, end = month_bounds(year, month)
    sts = start - timedelta(days=LOOKBACK_DAYS)
    print(f"[{year}-{month:02d}] downloading {sts:%Y-%m-%d}..{end:%Y-%m-%d} ...")
    csv_text = download_csv(sts, end)
    rows = reconstruct_month(csv_text, start, end)
    total_events = max((max(r["by_event"].values(), default=0) for r in rows), default=0)
    with open(out_path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"[{year}-{month:02d}] wrote {len(rows)} hourly rows "
          f"(peak single-hazard active = {total_events})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, help="start year (full run)")
    ap.add_argument("--end", type=int, help="end year inclusive (full run)")
    ap.add_argument("--test", type=str, help="single month YYYY-MM -> data/_test_backfill.jsonl")
    args = ap.parse_args()
    os.makedirs("data", exist_ok=True)

    if args.test:
        y, m = map(int, args.test.split("-"))
        out = os.path.join("data", "_test_backfill.jsonl")
        open(out, "w").close()  # fresh
        do_month(y, m, out)
        print(f"\nTest written to {out}")
        return 0

    if not (args.start and args.end):
        print("Provide --start/--end for a full run, or --test YYYY-MM.")
        return 2

    done = load_manifest()
    for year in range(args.start, args.end + 1):
        for month in range(1, 13):
            tag = f"{year}-{month:02d}"
            # don't backfill into the future
            if month_bounds(year, month)[0] > datetime.now(timezone.utc):
                continue
            if tag in done:
                print(f"[{tag}] already done, skipping")
                continue
            try:
                do_month(year, month, OUT_PATH)
                done.add(tag)
                save_manifest(done)
            except Exception as e:
                print(f"[{tag}] FAILED: {e} (will retry on next run)")
            time.sleep(REQUEST_PAUSE)
    print(f"\nBackfill complete through {args.end}. Archive: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
