#!/usr/bin/env python3
"""
StormWatch Live — Per-STATE baselines for the Anomaly Map  [OFFLINE]

The national monitor knows what's normal for the whole country. This learns what's
normal for EACH STATE, so the live map can color a state by how statistically
unusual ITS OWN current alert activity is for this time of year and time of day.

Re-streams the IEM NWS-warning archive (2008-present), counts active VTEC EVENTS
per state per hour, and accumulates a conditional distribution per
(state, month, 6-hour bucket) as a small histogram (memory-light — counts are
small integers). Writes a compact data/state_model.json (~hundreds of KB).

Reuses backfill_iem.py's download/parse helpers. ~1 hr (re-downloads month CSVs).

Usage:  python build_state_baselines.py [--start 2008] [--end 2026]
        python build_state_baselines.py --test 2023-06     # one month, prints, no write
"""

import argparse
import csv
import io
import json
import os
import time
from collections import defaultdict
from datetime import timedelta

from backfill_iem import download_csv, parse_ts, month_bounds, LOOKBACK_DAYS, REQUEST_PAUSE
import datetime as _dt

OUT = os.path.join("data", "state_model.json")
MIN_CELL = 80           # min samples for a (state, month, bucket) cell to be kept

STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}

QUANTS = [0.5, 0.9, 0.95, 0.99, 0.999]


def hist_quantile(hist, total, q):
    """Quantile from an integer-count histogram {value: freq}."""
    target = q * total
    cum = 0
    for val in sorted(hist):
        cum += hist[val]
        if cum >= target:
            return val
    return max(hist) if hist else 0


def process_month(year, month, acc):
    """Download one month, add per-(state,month,bucket) hourly counts to acc."""
    start, end = month_bounds(year, month)
    sts = start - timedelta(days=LOOKBACK_DAYS)
    csv_text = download_csv(sts, end)

    # Per state: event_key -> [min issue, max expire]
    by_state = defaultdict(dict)
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        ugc = (row.get("ugc") or "").strip()
        if len(ugc) < 2:
            continue
        st = ugc[:2]
        if st not in STATES:
            continue
        issue = parse_ts(row.get("utc_issue"))
        expire = parse_ts(row.get("utc_expire")) or parse_ts(row.get("utc_init_expire"))
        if not issue or not expire or expire <= issue:
            continue
        key = (row.get("vtec_year"), row.get("wfo"), row.get("phenomena"),
               row.get("significance"), row.get("eventid"))
        d = by_state[st]
        ev = d.get(key)
        if ev is None:
            d[key] = [issue, expire]
        else:
            if issue < ev[0]:
                ev[0] = issue
            if expire > ev[1]:
                ev[1] = expire

    n_hours = int((end - start).total_seconds() // 3600)
    for st, events in by_state.items():
        diff = [0] * (n_hours + 1)
        for issue, expire in events.values():
            a = max(0, int((issue - start).total_seconds() // 3600))
            b = min(n_hours, int((expire - start).total_seconds() // 3600) + 1)
            if b > a:
                diff[a] += 1
                diff[b] -= 1
        running = 0
        cells = acc[st]
        for h in range(n_hours):
            running += diff[h]
            bucket = (h % 24) // 6
            cells[(month, bucket)][running] += 1
    return len(by_state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2008)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--test", type=str)
    args = ap.parse_args()
    os.makedirs("data", exist_ok=True)

    # acc[state][(month,bucket)] = {count_value: frequency}
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    now = _dt.datetime.now(_dt.timezone.utc)

    if args.test:
        y, m = map(int, args.test.split("-"))
        n = process_month(y, m, acc)
        print(f"[test {args.test}] {n} states; sample TX cells:")
        for cell, hist in list(acc.get("TX", {}).items())[:4]:
            tot = sum(hist.values())
            print(f"  month-bucket {cell}: n={tot} median={hist_quantile(hist, tot, .5)} "
                  f"p99={hist_quantile(hist, tot, .99)} max={max(hist)}")
        return 0

    for year in range(args.start, args.end + 1):
        for month in range(1, 13):
            if month_bounds(year, month)[0] > now:
                continue
            try:
                n = process_month(year, month, acc)
                print(f"[{year}-{month:02d}] {n} states", flush=True)
            except Exception as e:
                print(f"[{year}-{month:02d}] FAILED: {e}", flush=True)
            time.sleep(REQUEST_PAUSE)

    # Compact model: state -> "month-bucket" -> {n, q:[...], max}
    model = {"built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "states": {}}
    for st, cells in acc.items():
        out_cells = {}
        for (month, bucket), hist in cells.items():
            tot = sum(hist.values())
            if tot < MIN_CELL or max(hist) == 0:
                continue
            out_cells[f"{month}-{bucket}"] = {
                "n": tot,
                "q": [hist_quantile(hist, tot, q) for q in QUANTS],
                "max": int(max(hist)),
            }
        if out_cells:
            model["states"][st] = out_cells

    json.dump(model, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    size_kb = os.path.getsize(OUT) / 1024
    print(f"\nWrote {OUT} ({size_kb:.0f} KB) — {len(model['states'])} states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
