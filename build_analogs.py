#!/usr/bin/env python3
"""
StormWatch Live — Historical-Analog Memory (Path C, Layer 4)  [OFFLINE]

Case-based reasoning over 18 years. Represents each DAY as a vector of its peak
hazard activity, so the live monitor can answer "what past day does today most
resemble?" — e.g. a tornado-heavy spring afternoon matching April 27 2011, or a
hot/dry/windy day matching a past fire-weather outbreak.

Builds data/analog_library.json: one compact record per active day
  { date, vec (log1p peak counts over headline hazards), peak (top hazards) }
The live scorer (pure stdlib) cosine-matches today's vector against the library.

Usage:  python build_analogs.py
"""

import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone

ARCHIVE = os.path.join("data", "baseline_hourly.jsonl")
COMPOSITE = os.path.join("data", "composite_model.json")
OUT = os.path.join("data", "analog_library.json")

MIN_DAY_ACTIVITY = 8        # skip near-empty days (sum of headline peaks)


def main():
    headline = json.load(open(COMPOSITE, encoding="utf-8"))["headline"]
    hidx = {h: i for i, h in enumerate(headline)}

    # Peak (max simultaneous) count of each headline hazard per UTC day.
    daily = defaultdict(lambda: [0] * len(headline))
    for line in open(ARCHIVE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        day = r["t"][:10]
        row = daily[day]
        for h, c in r["by_event"].items():
            j = hidx.get(h)
            if j is not None and c > row[j]:
                row[j] = c

    library = []
    for day, peaks in sorted(daily.items()):
        if sum(peaks) < MIN_DAY_ACTIVITY:
            continue
        vec = [round(math.log1p(c), 4) for c in peaks]
        top = sorted(((headline[j], peaks[j]) for j in range(len(headline)) if peaks[j] > 0),
                     key=lambda kv: -kv[1])[:4]
        library.append({"date": day, "vec": vec, "peak": top})

    out = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "headline": headline,
        "days": len(library),
        "library": library,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    size_kb = os.path.getsize(OUT) / 1024
    print(f"Indexed {len(library)} active days -> {OUT} ({size_kb:.0f} KB)")

    # Sanity: what does the 2011 super-outbreak day match? (self + similar days)
    def cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1
        nb = math.sqrt(sum(y * y for y in b)) or 1
        return dot / (na * nb)

    lib = {d["date"]: d for d in library}
    if "2011-04-27" in lib:
        q = lib["2011-04-27"]["vec"]
        sims = sorted(((cos(q, d["vec"]), d["date"], d["peak"]) for d in library
                       if d["date"] != "2011-04-27"), reverse=True)[:5]
        print("\nDays most similar to 2011-04-27 (super outbreak):")
        for s, dt, peak in sims:
            print(f"  {dt}  sim={s:.3f}  " + ", ".join(f"{h}:{n}" for h, n in peak[:3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
