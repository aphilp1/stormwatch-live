# National Alert Trend Monitor — System Documentation

A self-learning weather watchdog for **StormWatch Live**. It watches the national
NWS alert feed every 15 minutes and answers one question: *is anything unusual
happening right now, compared to the last 18 years?* It surfaces that as push
notifications, an in-app **Event Watch** tab, and — separately — a rigorous
climate-vs-weather trend analysis.

This doc is the single reference for the whole system: plain-English overview,
architecture, every script, the in-app tab, the statistics (including the climate
methodology and its honest limits), and how to operate and rebuild it.

---

## 1. Plain-English overview

The watchdog checks every active weather alert in the United States, four times an
hour. For each kind of alert (tornado, flood, heat, fire, …) it knows what's
*normal* for this exact time of year and time of day, learned from 18 years of
history. When today is far above normal — *"54 heat advisories active, a record
for late June"* — it says so. It also looks at the whole picture (*"three kinds
of hazardous weather elevated at once"*) and finds the most similar day in
history (*"today resembles September 4, 2024"*).

It runs by itself in the cloud (GitHub Actions) — no laptop required.

**What you get:**
- **Push notifications** when something genuinely escalates (via the ntfy app)
- An **Event Watch tab** inside StormWatch Live with a live threat gauge, the
  unusual-hazard list, a trend chart, the historical analog, and a briefing
- A **climate-trends analysis** (run on demand) separating real long-term signals
  from weather noise and warning-policy changes

---

## 2. Architecture & data flow

```
                 ┌──────────────────────── OFFLINE (run occasionally, locally) ─────────────────────────┐
 NWS warning      │ backfill_iem.py ─▶ baseline_hourly.jsonl (18 yr, 66 MB, LOCAL only)                 │
 archive (IEM) ──▶│        └─▶ build_baselines.py  ─▶ baseline_model.json   (per-hazard normals)         │
                  │        └─▶ build_composite.py  ─▶ composite_model.json  (National Threat Index)      │
                  │        └─▶ build_analogs.py    ─▶ analog_library.json    (historical day twins)      │
                  │        └─▶ climate_trends.py   ─▶ climate_trends.json    (trend screen)              │
                  └────────────────────────────────────────────────────────────────────────────────────┘
                                                   │ small derived models committed to repo
                                                   ▼
 ┌───────────────────────── LIVE (every 15 min, in GitHub Actions) ──────────────────────────┐
 │ alerts_monitor.py:  fetch api.weather.gov/alerts/active  ──▶  score vs models              │
 │   ▶ data/alert_status.json   (current snapshot: tiers, threat, analog, briefing)           │
 │   ▶ data/alert_history.jsonl (append one row — the growing live time series)               │
 │   ▶ ntfy push on escalation   ▶ Claude briefing (optional, needs API key)                  │
 └────────────────────────────────────────────────────────────────────────────────────────────┘
                                                   │ same-origin committed files
                                                   ▼
 StormWatch Live (weather-alerts.html) — Event Watch tab fetches alert_status.json + history
```

**Key property:** the live scorer reads only small derived model files. The 66 MB
raw archive never leaves your machine (it's gitignored and fully reproducible).

---

## 3. The five layers

| # | Layer | Script | What it contributes |
|---|---|---|---|
| 1 | **Memory** | `backfill_iem.py` | 162,144 hourly snapshots of every NWS warning, 2008–2026, reconstructed from the IEM archive into the same schema as the live feed |
| 2 | **Judgment** | `build_baselines.py` | For each hazard, the full distribution of counts conditioned on **month × time-of-day** — so it knows tornado warnings peak on spring afternoons, heat in summer |
| 3 | **Big picture** | `build_composite.py` | A **National Threat Index** (how many hazard *families* are simultaneously elevated) plus an Isolation Forest ML cross-check that catches unusual hazard *combinations* |
| 4 | **Analogy** | `build_analogs.py` | 6,691 historical days as vectors; matches today to its nearest twins |
| 5 | **Reasoning** | `alerts_monitor.py` (`generate_briefing`) | Claude turns the numbers + analog into a plain-language briefing on escalation |

### How "unusual" is measured (Layer 2 detail)
For a given hazard, the live count is ranked against all historical counts in the
same **month + 6-hour window**. The result is a "surprise" score
(`-log10(exceedance probability)`) and a tier:

- **Normal** — within the usual range for this season/time
- **Elevated** — roughly top 5%
- **Significant** — roughly top 1%
- **Extraordinary** — roughly top 0.1%, or a new 18-year record for this slot

A **magnitude gate** prevents trivial-but-rare blips (e.g. 5 winter-storm warnings
in June) from escalating: a hazard must be both rare *and* materially large
(≥ 20% of its 18-year peak) to trigger a notification or appear in the tab list.

### Validation it actually works
- The worst tornado hour in 18 years it identifies = **April 27, 2011** (the real
  Super Outbreak, 84 simultaneous warnings).
- The Isolation Forest's #1 most-anomalous hour = **Hurricane Helene** (Sept 27,
  2024) — found purely from the unusual tropical+flood+tornado combination.
- The composite index's top days = the **Dec 15 2021 derecho**, **Jan 9 2024**
  outbreak, **Oct 26 2010** "land hurricane."

---

## 4. Scripts & how to rebuild

All offline scripts are pure Python (numpy / scipy / scikit-learn). Run **in
order** to rebuild everything from scratch:

```bash
python backfill_iem.py --start 2008 --end 2026   # ~30-60 min; rebuilds the 66 MB archive
python build_baselines.py                          # per-hazard normals
python build_composite.py                          # National Threat Index + ML check
python build_analogs.py                            # historical analog library
python climate_trends.py                           # climate trend screen (research)
```

The live scorer, `alerts_monitor.py`, runs every 15 min via
`.github/workflows/alert-monitor.yml` and needs no rebuild — it just reads the
committed models. Re-run the offline builders every month or so to fold in new
data (the backfill is resumable; it only fetches new months).

**Committed (small, the live site needs them):** `baseline_model.json`,
`composite_model.json`, `analog_library.json`, `alert_history.jsonl`,
`alert_status.json`, `climate_trends.json`.
**Local only (gitignored, reproducible):** `baseline_hourly.jsonl` (66 MB),
`baseline_manifest.json`, `_backfill.log`.

---

## 5. The Event Watch tab (in StormWatch Live)

Added to `weather-alerts.html` — purely additive, no change to existing alert/map
logic. It fetches the same-origin committed files on a 5-minute interval (the
same pattern the app already uses for other `data/` files), so it works
identically on GitHub Pages and the local server, with no MCP gating.

It shows:
1. A color-coded **National Threat** gauge + a matching badge in the header
2. **Unusual right now** — the magnitude-gated unusual hazards with "normally ~N"
   baselines and RECORD tags
3. A **trend chart** of active US alerts over the recent window (from
   `alert_history.jsonl`, which grows every 15 min)
4. The **most similar past day**
5. The **Claude briefing** (when one was generated)

---

## 6. Climate-vs-weather trend analysis (`climate_trends.py`)

This is a separate, research-grade question: *over 2008–2025, are warnings
trending, and is any trend a physical (climate) signal or an artifact of how the
NWS changed its warning practices?*

### Why this is hard (and why naive analysis is wrong)
Warning **counts are a proxy** for hazard occurrence, filtered through:
- **Detection changes** — dual-pol radar (2011–2013), more storm spotters
- **Policy changes** — storm-based polygon warnings replaced county warnings
  (2007), Impact-Based Warnings (~2012→2016), "destructive" severe tags (2021),
  the 2024 heat-product overhaul ("Excessive Heat" → "Extreme Heat Warning")
So "warnings are up → climate change" is a trap. This tool is built to avoid it.

### Methods (all standard in climatology/hydrology)
- **Mann-Kendall test** — non-parametric monotonic-trend detection (tau, p), tie-
  corrected. Robust to skewed count data.
- **Theil-Sen slope** — robust trend magnitude (median of pairwise slopes).
- **Pettitt change-point test** — locates the year of any abrupt shift.
- **Observing-system audit** — a table of known NWS practice changes; if a trend's
  change-point lines up with one, it's flagged a likely artifact, not climate.

### Findings (2008–2025 screen)
- **Heat is the clear signal.** Heat Advisory **+134%** (p=0.002) and Extreme Heat
  Warning **+137%** (p=0.049) are both significantly increasing. Heat is the most
  robust, least-confounded climate signal in the warning record — this is exactly
  where climate change meets the meteorological record.
- **Convective & tropical hazards show no significant trend** — tornado, severe
  thunderstorm, flash flood, hurricane, tropical storm, winter storm all return
  *no significant trend*. This is the scientifically honest result: in an 18-year
  record these are dominated by ENSO-driven interannual swings and policy
  confounds, and are not expected to show a clean short-record trend.

### Honest limitations (these are part of the output)
- **18 years is short.** Climate normals are 30 years. This catches strong trends;
  it is underpowered for subtle ones.
- **ENSO endpoints.** The first/last years sit in particular El Niño/La Niña
  phases, which can inflate or deflate an apparent trend.
- **Proxy + policy confound.** Even the heat signal partly overlaps the 2024 heat-
  product overhaul; it should be verified against a station-temperature record.
- **This is SCREENING, not attribution.** "Candidate signal" means *worth a real
  study*, never *proof*. Attribution needs physical data (temperatures, reanalysis)
  and longer records.

### Sensible next steps
- Correlate annual series with ENSO (ONI) and global-temperature anomaly indices.
- Cross-check the heat signal against RAWS/ASOS station temperatures (you already
  have a RAWS pipeline) and NOAA HeatRisk.
- Extend to a peaks-over-threshold / extreme-value (GPD/GEV) analysis of the worst
  days, where a climate signal often appears before the mean shifts.

---

## 7. Operating it

**It's already live** and self-runs every 15 min. To finish activation:
1. **Push notifications:** install the **ntfy** app, subscribe to an unguessable
   topic, add it as the repo secret `NTFY_TOPIC`.
2. **Claude briefings (optional):** add the repo secret `ANTHROPIC_API_KEY`. The
   workflow already `pip install`s the SDK; without the key, briefings skip
   gracefully. Model is `claude-opus-4-8` (override with `ALERT_BRIEFING_MODEL`,
   e.g. `claude-haiku-4-5` for lower cost).
3. **Manual test:** GitHub → Actions → "National Alert Trend Monitor" → Run
   workflow.

**Monitoring:** every run commits a snapshot; `git log` shows the cadence. The
`alert_history.jsonl` file grows ~96 rows/day and feeds the Event Watch trend chart.

---

## 8. File map

| File | Role |
|---|---|
| `backfill_iem.py` | Layer 1 — build the 18-yr hourly archive from IEM |
| `build_baselines.py` | Layer 2 — per-hazard seasonal/diurnal normals |
| `build_composite.py` | Layer 3 — National Threat Index + Isolation Forest |
| `build_analogs.py` | Layer 4 — historical analog library |
| `climate_trends.py` | Climate-vs-weather trend screen |
| `alerts_monitor.py` | Live scorer (every 15 min) + Layer 5 Claude briefing |
| `.github/workflows/alert-monitor.yml` | The 15-min schedule |
| `weather-alerts.html` | StormWatch Live app + the Event Watch tab |
| `ALERT_MONITOR_REVIEW.md` | The original review/go-live checklist |
| `ALERT_MONITOR_SYSTEM.md` | This document |
```
