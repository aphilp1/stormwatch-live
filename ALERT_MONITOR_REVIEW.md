# Alert Trend Monitor — Review Plan (for tomorrow)

Built 2026-06-27. **Nothing is pushed yet** — your live site is untouched and the
agent is NOT collecting data until you push. The learning clock starts at push.

---

## 1. What got built (review these 2 files first)

- **`alerts_monitor.py`** — fetches the full national NWS alerts feed, counts all
  hazard types, appends to `data/alert_history.jsonl` (its memory), scores each
  hazard vs a seasonal+hourly baseline, writes `data/alert_status.json`, pushes
  on escalation. Pure Python stdlib (no installs).
- **`.github/workflows/alert-monitor.yml`** — runs it every 15 min, commits data
  back. Mirrors your existing `daily-fire-wind.yml` conventions.

Seed data from today's live test (459 alerts, 31 hazard types):
- `data/alert_history.jsonl` (1 row)
- `data/alert_status.json` (all hazards "Calibrating" — correct for cold start)

## 2. Re-run it yourself to see it work

```
cd C:\Users\aphil\Documents\Stormwatch
python alerts_monitor.py
```
Expect: `[fetch] N active alerts across M hazard types` then `no new escalations`.

## 3. How the "learns" logic works (skim before approving)

- Baseline = past counts at same hour-of-day (±1h) and time-of-year (±10 days).
- Robust z-score (median/MAD): z≥2 Elevated, z≥3 Significant, z≥4 Extraordinary.
- Won't score until ≥24 comparable past samples exist → blind for first ~days.
- Tunable knobs near top of `alerts_monitor.py`: TIERS, MIN_SAMPLES, HOUR_WINDOW,
  DOY_WINDOW, NOTIFY_FROM_TIER, MIN_COUNT_TO_ALERT.

## 4. Go-live checklist (do these to switch it on)

- [ ] Install **ntfy** app (phone/desktop), subscribe to an unguessable topic
      (e.g. `stormwatch-aphil-7x9q2`)
- [ ] GitHub → repo → Settings → Secrets and variables → Actions → New secret:
      name `NTFY_TOPIC`, value = your topic
- [ ] Confirm `.gitignore` does NOT exclude `data/*.jsonl` or `data/*.json`
      (the history file MUST be committed — it's the agent's memory)
- [ ] Commit + push: `alerts_monitor.py`, the workflow, and the `data/` seed files
- [ ] In Actions tab, hit "Run workflow" once manually to confirm it runs green
- [ ] Send yourself a test push (optional): set NTFY_TOPIC locally and trigger

## 5. Decisions parked for you

- **Push only** for now (chosen). Phase 2 options when ready:
  - In-app "Event Watch" panel reading `alert_status.json`
  - Outbreak detection (cluster alert polygons already in the app)
  - Claude-written plain-language briefings on escalation (needs ANTHROPIC_API_KEY)
- **Cadence:** every 15 min. Dial down to `*/30` if commit noise bothers you.

## 6. Open questions to decide tomorrow

1. Topic name for ntfy?
2. Keep 15-min cadence or 30?
3. Push from "Significant" (z≥3) or only "Extraordinary" (z≥4)? (currently z≥3)
4. Commit the seed `data/` files, or start the history clean on push?

---

## 8. PATH C — BUILT (2026-06-28). The full "powerful learning machine".

All five layers are built locally and validated. **Nothing is pushed.**

**Offline build scripts** (run in order to rebuild everything from scratch):
1. `backfill_iem.py --start 2008 --end 2026` → `data/baseline_hourly.jsonl`
   (162,144 hourly snapshots, 18 yrs; 66MB, gitignored/local-only)
2. `build_baselines.py` → `data/baseline_model.json` (per-hazard seasonal/diurnal
   conditional count distributions; 531KB)
3. `build_composite.py` → `data/composite_model.json` (National Threat Index +
   Isolation Forest ML cross-check)
4. `build_analogs.py` → `data/analog_library.json` (6,691 day vectors; 1.5MB)

**Live scorer** `alerts_monitor.py` (pure stdlib + optional anthropic SDK) reads
the derived models each run and produces, per hazard: count, expected, surprise,
tier, record-flag; plus a National Threat tier, top-3 historical analogs, and
(on escalation) a Claude-written briefing.

**Validation highlights** — the system independently rediscovered real events:
- Worst tornado hour in 18 yrs = Apr 27 2011 (the Super Outbreak), 84 warnings
- Isolation Forest's #1 anomaly = Hurricane Helene (Sep 27 2024)
- Today's nearest analog, threat index, and per-hazard grades all read sensibly

**What WILL be committed** (small): baseline_model.json, composite_model.json,
analog_library.json, alert_history.jsonl, alert_status.json.
**Kept LOCAL** (gitignored, reproducible): baseline_hourly.jsonl (66MB), manifest, log.

**Go-live additions to §4 checklist:**
- [ ] Confirm `data/baseline_hourly.jsonl` is gitignored before committing (66MB)
- [ ] (Optional, for briefings) add repo secret `ANTHROPIC_API_KEY`
- [ ] The alert-monitor workflow now `pip install anthropic` — no action needed

---

## 7. "A VERY POWERFUL LEARNING MACHINE" — the original roadmap (now built, see §8)

No single magic model. Power = layering the right method per level, fed by DATA.
The #1 lever is data, and we don't have to wait for it to accumulate live.

**Layers, weakest → most powerful:**
1. Baselines (median/MAD per hour/season) — BUILT. Needs weeks.
2. Count models — Poisson / negative-binomial PER REGION, not just national.
   Proper probability of "how rare"; catches regional outbreaks the national
   number washes out. Add day-of-week + Fourier seasonal terms.
3. ML anomaly detection — Isolation Forest / forecast-residuals on the full
   multi-hazard vector. Finds weird COMBINATIONS, not just single spikes.
4. Analog memory (case-based reasoning) — store every past significant event;
   match new patterns to historical twins ("looks like April 2011 setup").
   This is the part that feels genuinely smart.
5. LLM reasoning (Claude) — synthesize/explain/cross-reference on top. Not
   "learning" but real intelligence; can do retrieval over the analog library.

**THE UNLOCK — backfill the archive (do this first if going powerful):**
- Iowa Environmental Mesonet (IEM) archives EVERY NWS warning since the 1980s.
  Download decades in one pull → day-one deep baselines (no blind period),
  real training data for Layer 3, and a full event library for Layer 4.
- IEM "VTEC" / warnings archive + their request scripts are the source.

**Infra note:** user already runs A100 GPUs on RunPod (Earth2 project) — the
heavy ML end is within reach, not a from-scratch lift.

**Decision for tomorrow:** how far to push —
  (A) Solidify Phase 1 (push, collect, baselines) and grow from there, OR
  (B) Backfill decades of IEM history now + build count models (Layer 2), OR
  (C) Full stack: backfill + ML anomaly detection + analog memory + LLM layer.
