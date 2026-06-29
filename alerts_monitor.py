#!/usr/bin/env python3
"""
StormWatch Live — National Alert Trend Monitor (Phase 1)

Pulls the full NWS active-alerts feed, counts every hazard type, and appends one
compact row to data/alert_history.jsonl. That growing log is the agent's MEMORY.

From that memory it builds a baseline ("what's normal for this hour of this part
of the year?") and scores each hazard for how unusual the current count is. When
a hazard escalates into a higher tier it writes data/alert_status.json (for the
web app to read) and fires a push notification via ntfy.sh.

The agent "learns" in the honest sense: every run adds data, so the baselines get
sharper and the anomaly scores get more trustworthy the longer it runs. No model
training, no server, no database — the repo's git history IS the time series.

Pure standard library: no pip install needed in CI.
"""

import json
import os
import sys
import time
import math
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
NWS_ALERTS = "https://api.weather.gov/alerts/active?status=actual"
# NWS requires a descriptive User-Agent or it returns 403.
USER_AGENT = "StormWatchLive-AlertMonitor (https://github.com/aphilp1/stormwatch-live)"

HISTORY_PATH = os.path.join("data", "alert_history.jsonl")
STATUS_PATH = os.path.join("data", "alert_status.json")

# ntfy.sh topic for push notifications. Set NTFY_TOPIC as a repo secret/var.
# Anyone who knows the topic name can read it, so use something unguessable.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

# Layer 5: Claude-written plain-language briefing on escalation. Needs the
# anthropic SDK installed and ANTHROPIC_API_KEY set; skipped gracefully if not.
BRIEFING_MODEL = os.environ.get("ALERT_BRIEFING_MODEL", "claude-opus-4-8").strip()

# Layer 2 model trained offline by build_baselines.py from the 18-yr IEM archive.
MODEL_PATH = os.path.join("data", "baseline_model.json")
# Layer 3 composite (National Threat Index) built by build_composite.py.
COMPOSITE_PATH = os.path.join("data", "composite_model.json")
# Layer 4 analog library (historical day twins) built by build_analogs.py.
ANALOG_PATH = os.path.join("data", "analog_library.json")

# Tiers by "surprise" = -log10(exceedance prob) against the hazard's conditional
# (this-month, this-time-of-day) 18-yr distribution. 1.3=~top 5%, 2=~top 1%,
# 3=~top 0.1%. A new record for the cell is forced to Extraordinary.
TIERS = [
    (3.0, "Extraordinary"),
    (2.0, "Significant"),
    (1.3, "Elevated"),
    (0.0, "Normal"),
]
# Only push when a hazard reaches at least this tier.
NOTIFY_FROM_TIER = "Significant"
# Magnitude gate: rarity alone isn't enough — a hazard must also be materially
# large to escalate, so "5 winter alerts in June" (rare but trivial) stays quiet.
MIN_COUNT_TO_ALERT = 5                 # absolute floor
MIN_MAX_FRACTION = 0.2                 # AND >= this fraction of the hazard's 18-yr peak


# ----------------------------------------------------------------------------
# Fetch
# ----------------------------------------------------------------------------
def fetch_active_alerts():
    """Return list of alert feature dicts, following NWS pagination."""
    alerts = []
    url = NWS_ALERTS
    pages = 0
    while url and pages < 20:
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        alerts.extend(data.get("features", []))
        url = (data.get("pagination") or {}).get("next")
        pages += 1
    return alerts


def count_by_event(alerts):
    """Count active alerts by hazard name (properties.event). All hazards."""
    counts = {}
    for a in alerts:
        ev = ((a.get("properties") or {}).get("event") or "Unknown").strip()
        counts[ev] = counts.get(ev, 0) + 1
    return counts


# ----------------------------------------------------------------------------
# Memory (history log)
# ----------------------------------------------------------------------------
def append_history(row):
    os.makedirs("data", exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    rows = []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# ----------------------------------------------------------------------------
# Baseline + scoring
# ----------------------------------------------------------------------------
def _parse_t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _hour_diff(h1, h2):
    d = abs(h1 - h2)
    return min(d, 24 - d)


def _doy_diff(d1, d2):
    d = abs(d1 - d2)
    return min(d, 365 - d)


def baseline_samples(history, event, now):
    """Past counts for this hazard at a comparable hour-of-day and time-of-year."""
    samples = []
    for row in history:
        try:
            t = _parse_t(row["t"])
        except Exception:
            continue
        if _hour_diff(t.hour, now.hour) > HOUR_WINDOW:
            continue
        if _doy_diff(t.timetuple().tm_yday, now.timetuple().tm_yday) > DOY_WINDOW:
            continue
        samples.append((row.get("by_event") or {}).get(event, 0))
    return samples


def robust_z(value, samples):
    """Median/MAD-based z-score; robust to occasional spikes in the baseline."""
    if not samples:
        return None, None, None
    s = sorted(samples)
    n = len(s)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    devs = sorted(abs(x - median) for x in s)
    mad = devs[n // 2] if n % 2 else (devs[n // 2 - 1] + devs[n // 2]) / 2
    sigma = 1.4826 * mad
    if sigma < 1e-9:
        # No spread in history: fall back to "is it above the max we've seen?"
        sigma = max(1.0, math.sqrt(median + 1))
    z = (value - median) / sigma
    return z, median, sigma


def tier_for(z):
    for thresh, label in TIERS:
        if z >= thresh:
            return label
    return "Normal"


def tier_rank(label):
    labels = [t[1] for t in TIERS][::-1]  # Normal..Extraordinary low->high
    return labels.index(label) if label in labels else 0


def trend(history, event, now, hours):
    """Count change vs ~`hours` ago (nearest sample), for momentum."""
    target = now.timestamp() - hours * 3600
    best = None
    for row in history:
        try:
            ts = _parse_t(row["t"]).timestamp()
        except Exception:
            continue
        if best is None or abs(ts - target) < abs(best[0] - target):
            best = (ts, (row.get("by_event") or {}).get(event, 0))
    return best[1] if best else None


# ----------------------------------------------------------------------------
# Layer 2: model-based scoring (negative-binomial tail vs seasonal/diurnal mean)
# Feature builder MUST stay identical to features() in build_baselines.py.
# ----------------------------------------------------------------------------
def features(doy, hour, dow):
    A = 2 * math.pi * doy / 365.25
    H = 2 * math.pi * hour / 24.0
    W = 2 * math.pi * dow / 7.0
    a1s, a1c = math.sin(A), math.cos(A)
    d1s, d1c = math.sin(H), math.cos(H)
    return [
        a1s, a1c, math.sin(2 * A), math.cos(2 * A), math.sin(3 * A), math.cos(3 * A),
        d1s, d1c, math.sin(2 * H), math.cos(2 * H), math.sin(3 * H), math.cos(3 * H),
        math.sin(W), math.cos(W),
        a1s * d1s, a1s * d1c, a1c * d1s, a1c * d1c,
    ]


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def expected_lambda(haz_model, now):
    fv = features(now.timetuple().tm_yday, now.hour, now.weekday())
    z = haz_model["intercept"] + sum(c * x for c, x in zip(haz_model["coef"], fv))
    return math.exp(min(z, 30.0))


# Exceedance probability anchored to each conditional quantile [p50,p90,p95,p99,p999].
_Q_EXCEED = [0.5, 0.1, 0.05, 0.01, 0.001]
SURPRISE_CAP = 4.0


def conditional_surprise(count, now, hm):
    """Rank `count` against the 18-yr distribution of this hazard at this month +
    time-of-day. Returns (surprise=-log10 exceedance, is_record, cell_max).
    surprise is interpolated between conditional quantiles and capped at the
    data-resolvable floor."""
    cell = hm.get("cells", {}).get(f"{now.month}-{now.hour // 6}") or hm.get("glob")
    if count <= 0 or not cell:
        return 0.0, False, None
    q = cell["q"]                                   # [p50,p90,p95,p99,p999]
    cmax, nn = cell["max"], cell["n"]
    is_record = count >= cmax
    floor_p = max(1.0 / nn, 10 ** (-SURPRISE_CAP))
    # anchors: (count_threshold, exceedance_prob), ascending threshold
    thr = list(q) + [max(cmax, q[-1] + 1e-6)]
    pex = list(_Q_EXCEED) + [floor_p]
    sup = [-math.log10(p) for p in pex]
    if count <= thr[0]:
        return 0.0, is_record, cmax
    for i in range(len(thr) - 1):
        if thr[i] <= count <= thr[i + 1]:
            span = thr[i + 1] - thr[i]
            frac = (count - thr[i]) / span if span > 1e-9 else 1.0
            return min(SURPRISE_CAP, sup[i] + frac * (sup[i + 1] - sup[i])), is_record, cmax
    return min(SURPRISE_CAP, sup[-1]), is_record, cmax


# ----------------------------------------------------------------------------
# Layer 3: National Threat Index (how unusual is the whole picture right now)
# ----------------------------------------------------------------------------
def load_composite():
    if not os.path.exists(COMPOSITE_PATH):
        return None
    try:
        return json.load(open(COMPOSITE_PATH, encoding="utf-8"))
    except Exception:
        return None


def national_threat(hazards, comp):
    """How broad is the threat right now? Counts how many hazard FAMILIES are
    simultaneously elevated (each family scored by its peak hazard's surprise).
    Family-count is robust to live-vs-archive calibration drift, unlike an
    absolute percentile. Returns a dict (tier, families_elevated, per-family)."""
    if not comp:
        return None
    families = comp.get("families", {})
    fam_surprise, elevated, significant = {}, [], 0
    for fam, hs in families.items():
        # only materially-large hazards count toward a family's elevation
        fs = max(((hazards.get(h, {}).get("surprise") or 0)
                  if hazards.get(h, {}).get("material") else 0) for h in hs) if hs else 0
        fam_surprise[fam] = round(fs, 2)
        if fs >= 2.0:                      # top ~1% for its own season/time
            significant += 1
            elevated.append(fam)
    if significant >= 4:
        tier = "Extreme"
    elif significant >= 3:
        tier = "High"
    elif significant >= 2:
        tier = "Elevated"
    else:
        tier = "Normal"
    # secondary composite (excess over families), for display/trend only
    composite = round(sum(max(0.0, s - 1.0) for s in fam_surprise.values()), 2)
    return {"tier": tier, "families_elevated": significant,
            "elevated": elevated, "family_surprise": fam_surprise,
            "composite": composite}


# ----------------------------------------------------------------------------
# Layer 4: historical-analog memory (what past day does today resemble?)
# ----------------------------------------------------------------------------
def load_analogs():
    if not os.path.exists(ANALOG_PATH):
        return None
    try:
        return json.load(open(ANALOG_PATH, encoding="utf-8"))
    except Exception:
        return None


def find_analogs(counts, analogs, now, k=3):
    """Cosine-match today's hazard-mix vector to the historical library, skipping
    the last few days (whose archive rows are just today's own warnings projected
    forward) so matches are genuine PAST events."""
    if not analogs:
        return []
    headline = analogs["headline"]
    q = [math.log1p(counts.get(h, 0)) for h in headline]
    nq = math.sqrt(sum(x * x for x in q))
    if nq < 1e-9:
        return []
    cutoff = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    out = []
    for d in analogs["library"]:
        if d["date"] >= cutoff:            # skip today's forward-projected warnings
            continue
        v = d["vec"]
        dot = sum(a * b for a, b in zip(q, v))
        nv = math.sqrt(sum(b * b for b in v)) or 1.0
        out.append((dot / (nq * nv), d))
    out.sort(key=lambda x: -x[0])
    return [{"date": d["date"], "similarity": round(s, 3),
             "peak": d["peak"]} for s, d in out[:k]]


# ----------------------------------------------------------------------------
# Layer 5: Claude reasoning — turn the stats + analogs into a plain-language brief
# ----------------------------------------------------------------------------
def generate_briefing(now, total, nt, ranked_hazards, analogs):
    """Use Claude to synthesize the numbers into a short human briefing. Returns
    the text, or None if the SDK / API key is unavailable (graceful skip)."""
    try:
        import anthropic
    except ImportError:
        print("[brief] anthropic SDK not installed — skipping briefing")
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[brief] ANTHROPIC_API_KEY unset — skipping briefing")
        return None

    # Compact, factual data for Claude to write from (no invented numbers).
    lines = [f"Time (UTC): {now:%Y-%m-%d %H:%M}", f"Total active US alerts: {total}"]
    if nt:
        lines.append(f"National Threat: {nt['tier']} "
                     f"({nt['families_elevated']} hazard families elevated: "
                     f"{', '.join(nt['elevated']) or 'none'})")
    lines.append("Most unusual hazards right now (count / typical seasonal high / record?):")
    for s, k, v in ranked_hazards[:6]:
        if v.get("surprise") is None:
            continue
        rec = " RECORD" if v.get("record") else ""
        lines.append(f"  - {k}: {v['count']} active vs ~{v.get('typical_high')} typical"
                     f" [{v['tier']}{rec}]")
    if analogs:
        a = analogs[0]
        top = ", ".join(f"{h} {n}" for h, n in a["peak"][:3])
        lines.append(f"Closest historical analog: {a['date']} (peak that day: {top})")
    data = "\n".join(lines)

    system = (
        "You are a concise severe-weather analyst writing a push-notification "
        "briefing for a weather enthusiast. Use ONLY the numbers provided — never "
        "invent counts, places, or forecasts. 2-4 short sentences, plain language, "
        "no preamble. Explain what's notable and why, and what the historical "
        "analog suggests. If activity is routine, say so briefly."
    )
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=BRIEFING_MODEL, max_tokens=400, system=system,
            messages=[{"role": "user", "content": data}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        print(f"[brief] generated ({len(text)} chars)")
        return text or None
    except Exception as e:
        print(f"[brief] failed: {e}")
        return None


# ----------------------------------------------------------------------------
# Notification
# ----------------------------------------------------------------------------
def send_push(title, message, priority="high", tags="warning"):
    if not NTFY_TOPIC:
        print("[notify] NTFY_TOPIC unset — skipping push. Message was:")
        print(f"         {title}: {message}")
        return False
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        print(f"[notify] pushed: {title}")
        return True
    except Exception as e:
        print(f"[notify] push failed: {e}")
        return False


def load_prev_status():
    if not os.path.exists(STATUS_PATH):
        return {}
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        alerts = fetch_active_alerts()
    except Exception as e:
        print(f"[fetch] failed: {e}")
        return 1

    counts = count_by_event(alerts)
    total = sum(counts.values())
    print(f"[fetch] {total} active alerts across {len(counts)} hazard types")

    # 1) Remember this snapshot BEFORE scoring (baseline = strictly past rows).
    history = load_history()
    append_history({"t": iso, "total": total, "by_event": counts})

    prev_status = load_prev_status()
    prev_tiers = (prev_status.get("hazards") or {})
    model = load_model()
    haz_models = (model or {}).get("hazards", {})

    # 2) Score every hazard active now against its 18-yr seasonal/diurnal baseline.
    hazards = {}
    escalations = []
    for event, value in sorted(counts.items(), key=lambda kv: -kv[1]):
        t1 = trend(history, event, now, 1)
        t6 = trend(history, event, now, 6)
        hm = haz_models.get(event)

        if hm:
            lam = expected_lambda(hm, now)
            surprise, is_record, cell_max = conditional_surprise(value, now, hm)
            tier = tier_for(surprise)
            if is_record and value >= MIN_COUNT_TO_ALERT:
                tier = "Extraordinary"   # new 18-yr record for this season/time
            status = "scored"
            expected = round(lam, 2)
            sr = round(surprise, 2)
        else:
            # Hazard not in the model (too rare to fit): no false alarms.
            tier, status, expected, sr, is_record, cell_max = \
                "Unmodeled", "unmodeled", None, None, False, None

        hazards[event] = {
            "count": value,
            "expected": expected,        # smooth seasonal/diurnal mean for right now
            "typical_high": cell_max,    # 18-yr max for this month + time-of-day
            "record": bool(is_record),
            "surprise": sr,              # -log10 conditional exceedance (higher = rarer)
            "tier": tier,
            "delta_1h": (value - t1) if t1 is not None else None,
            "delta_6h": (value - t6) if t6 is not None else None,
        }

        # Escalation = crossed into a higher tier than last run, AND materially
        # large (absolute floor + a real fraction of this hazard's historical peak).
        prev_tier = (prev_tiers.get(event) or {}).get("tier", "Normal")
        mag_gate = max(MIN_COUNT_TO_ALERT, MIN_MAX_FRACTION * hm["max"]) if hm else 1e9
        hazards[event]["material"] = bool(hm and value >= mag_gate)
        if (
            status == "scored"
            and value >= mag_gate
            and tier_rank(tier) >= tier_rank(NOTIFY_FROM_TIER)
            and tier_rank(tier) > tier_rank(prev_tier)
        ):
            escalations.append((event, hazards[event]))

    # 2b) National Threat Index — how broad is the threat right now (how many
    #     hazard families are simultaneously elevated).
    comp = load_composite()
    nt = national_threat(hazards, comp)
    if nt:
        elev = ", ".join(nt["elevated"]) or "none"
        print(f"[index] National Threat: {nt['tier']} "
              f"({nt['families_elevated']} families elevated: {elev})")
    # 2c) Historical analogs — what past day does today most resemble?
    analogs = find_analogs(counts, load_analogs(), now)
    if analogs:
        a = analogs[0]
        top = ", ".join(f"{h}:{n}" for h, n in a["peak"][:3])
        print(f"[analog] today most resembles {a['date']} "
              f"(sim {a['similarity']}) — {top}")

    prev_nt = (prev_status.get("national_threat") or {}).get("tier", "Normal")
    nt_rank = {"Normal": 0, "Elevated": 1, "High": 2, "Extreme": 3}
    if nt and nt_rank.get(nt["tier"], 0) >= 2 and nt_rank.get(nt["tier"], 0) > nt_rank.get(prev_nt, 0):
        send_push(
            f"National Threat: {nt['tier']}",
            f"{nt['families_elevated']} hazard families are simultaneously elevated "
            f"across the U.S. right now: {', '.join(nt['elevated'])}.",
            priority="urgent" if nt["tier"] == "Extreme" else "high", tags="rotating_light",
        )

    # 2d) Claude briefing when something is escalating or the picture is broad.
    ranked = sorted(((v.get("surprise") or 0, k, v) for k, v in hazards.items()),
                    reverse=True)
    briefing = None
    nt_high = nt and nt["tier"] in ("High", "Extreme")
    if escalations or nt_high:
        briefing = generate_briefing(now, total, nt, ranked, analogs)
        if briefing:
            send_push("Weather Briefing", briefing,
                      priority="urgent" if nt and nt["tier"] == "Extreme" else "high",
                      tags="satellite")

    # 3) Write status for the web app + next run's de-dup.
    status_doc = {
        "updated": iso,
        "total_active": total,
        "hazard_types": len(counts),
        "history_rows": len(history) + 1,
        "model_built": (model or {}).get("built"),
        "model_coverage": (model or {}).get("coverage"),
        "national_threat": nt,
        "analogs": analogs,
        "briefing": briefing,
        "hazards": hazards,
    }
    os.makedirs("data", exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status_doc, f, indent=2)

    # 4) Push on escalations.
    for event, h in escalations:
        trend_bits = []
        if h["delta_1h"] is not None:
            trend_bits.append(f"{h['delta_1h']:+d} in 1h")
        if h["delta_6h"] is not None:
            trend_bits.append(f"{h['delta_6h']:+d} in 6h")
        trend_str = (" · " + ", ".join(trend_bits)) if trend_bits else ""
        rec = " — a new 18-yr record for this time of year!" if h["record"] else ""
        title = f"{h['tier']}: {event}"
        msg = (
            f"{h['count']} active nationwide vs a typical seasonal high of "
            f"~{h['typical_high']} for this date & time{rec}{trend_str}"
        )
        send_push(title, msg, priority="urgent" if h["tier"] == "Extraordinary" else "high")

    if not escalations:
        unmodeled = sum(1 for v in hazards.values() if v["tier"] == "Unmodeled")
        print(f"[score] no new escalations ({unmodeled} hazards unmodeled)")
    # Show the current standouts for visibility.
    ranked = sorted(((v.get("surprise") or 0, k, v) for k, v in hazards.items()), reverse=True)
    for s, k, v in ranked[:5]:
        if v.get("surprise") is not None:
            print(f"   {k:32s} {v['count']:4d} active  exp~{v['expected']:.1f}  "
                  f"surprise={v['surprise']:.2f}  [{v['tier']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
