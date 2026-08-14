# Stormwatch — REFRAME: HRRR Forecast-Bust Detection

**Written 2026-05-31. This is a deliberate reframing of the project goal, not a drift.**
Read alongside `STORMWATCH_MASTER_STATUS.md` and `CLAUDE_CODE_RESTART.md`. When this
reframe is adopted, fold it into the master status as the new primary objective and
mark the prior point-accuracy framing as a special case within it.

---

## THE REFRAME (the new north star)

**Old question (what we tested through 2026-05-31):** Can WindNinja reproduce the
observed wind at a station? — a point-accuracy question. Requires WN to be *right*.
This narrowed to a small niche (n=2 Camp ridges) and is hard to prove.

**New question:** *What observable signals predict that HRRR will BUST — in speed,
direction, or arrival time — and can that prediction be used to improve / bound the
forecast?* This is forecast-ERROR prediction. It only requires HRRR's errors to be
*predictable*, not WN to be perfect — a weaker, more achievable, more useful claim.

**Why it's better:**
- A forecaster doesn't need a perfect number — they need to know *when not to trust
  HRRR and how it will be wrong*. That is the actual product.
- Errors can be predictable even when neither model is individually accurate.
- The HRRR↔WindNinja *disagreement* is a FREE, obs-independent signal available at
  forecast time. The core bet: where WN and HRRR diverge (and how) predicts where/how
  HRRR busts. WN becomes a DISCREPANCY DETECTOR, not a truth source.

---

## THE THREE BUST CHANNELS

| Channel | Predictor signal (knowable at forecast time) | Truth (from RAWS) | Physical signature seen so far |
|---|---|---|---|
| **Speed** | WN/HRRR speed ratio at the cell | obs sustained vs HRRR | terrain amplification HRRR can't resolve — Saddleback HRRR 0.525 |
| **Direction** | WN−HRRR dir delta; terrain rotation | obs vector-mean dir | summit/canyon rotation — WISC1 Δ36°, HGLC1 Δ46°, Jarbo |
| **Arrival/Timing** | WN-arrival vs HRRR-arrival across a time sequence | obs onset/peak hour | overnight peaks, transition lag — HMRC1, CUUC1 peaked outside 12Z |

Each channel outputs: is there a bust, how big, which direction, + a confidence.
This is exactly what `confidence_field.py` (per-cell labeled uncertainty) and
`mechanism_classifier.py` (bust-axis per mechanism) were architected to carry.

---

## TWO STEPS, ORDER NON-NEGOTIABLE

**Step 1 — FIND THE SIGNAL (diagnosis).** Measure HRRR's actual error per channel
against RAWS truth at every station, then ask what PREDICTS it. Candidate predictors,
all knowable before the bust:
- terrain: slope, aspect, local relief, elevation vs inversion lid, summit/canyon/valley
- synoptic: BC direction, speed, stability/lapse, MSLP gradient, BC level used
- **the WN−HRRR discrepancy itself** (the key obs-independent predictor)

**Step 2 — USE IT (only if Step 1 finds a real, out-of-sample signal).** Likely use is
NOT to "fix" the number but to flag untrustworthy cells and bound the error:
"HRRR says 25 mph NNE, but this is a rotating summit — expect N, possibly higher, low
confidence." That's the confidence engine. A learned correction comes later, only if
the signal is strong AND generalizes leave-one-event-out.

---

## THE HARD CONSTRAINT (why we can't skip to analysis)

You CANNOT find a signal in ~10 station-events × 3 channels — anything "found" is noise.
Finding "X predicts the bust" needs enough busts to see a pattern AND held-out events to
confirm it isn't coincidence. So the FIRST real move is building the error dataset big
enough to hunt in. We already pulled the raw material: **172 usable RAWS files across 12
events** — tonight only a handful were scored. The unlock is computing HRRR error (all 3
channels) at EVERY usable station, with terrain + synoptic + WN-discrepancy features
attached.

---

## IMMEDIATE NEXT STEP (when Claude Code is available)

Build `hrrr_error_dataset.csv` — one row per usable station-event across all 12 events
(the 172-file usable set, not tonight's handful). Columns:

ERROR (truth from RAWS — the target):
- speed_err = hrrr_10m_mph − obs_sus_mph (own-station GF) + ratio
- dir_err = circular(hrrr_10m_dir − obs_vector_mean_dir)
- arrival_err = hrrr peak/onset hour − obs peak/onset hour (NEEDS_HRRR_TS where HRRR
  time series at the cell isn't pulled yet)

CANDIDATE PREDICTORS (obs-independent, forecast-time):
- terrain: elev_m, slope, aspect, local relief (1km), summit/canyon/valley, DEM_verified
- inversion: station elev vs event inversion lid (above/below/near)
- synoptic: BC dir, BC speed, BC level, lapse/stability, MSLP gradient
- **discrepancy: wn_minus_hrrr_speed, wn_minus_hrrr_dir at the cell** (the key signal)

RULES:
- Compute only what's real; mark NEEDS_HRRR_TS / NEEDS_DEM / NEEDS_WN. No guessing.
- Dataset construction ONLY — fit nothing, claim no signal yet.
- Report COMPLETE-ROW COUNT PER CHANNEL (speed / direction / arrival) — this reality
  check tells us whether we can hunt a signal yet or still need data extraction.

Then, only after the dataset exists and a channel has enough N:
- look for whether busts cluster by a PHYSICAL predictor (state as hypothesis),
- confirm any candidate signal LEAVE-ONE-EVENT-OUT before calling it real,
- feed confirmed signals into confidence_field.py as the bust-flag / interval term.

---

## CARRY-OVER STATE (as of 2026-05-31, do not lose)

- Ridge niche (old framing): confirmed n=2, Camp CBXC1 (1.007) + SLEC1 (1.128),
  DEM/CRS-verified. Cross-event confirmation OPEN. This becomes the "speed channel,
  exposed-ridge, unrotated-flow" special case of the new bust frame.
- BOTH BC corrections (single-station, multi-station) FALSIFIED — do not revive.
- Sharpened hypothesis from tonight: the clean WN-beats-HRRR signal holds where terrain
  does NOT strongly rotate flow (Camp) and degrades where it does (Kincade summits,
  Jarbo). In the new frame this becomes: terrain-rotation is itself a DIRECTION-bust
  predictor — the same physics that broke the point test is a signal for the new one.
- ERA5 validated as trusted BC source (Tubbs/Thomas). 850 hPa is the working BC level
  across 3 events via 3 distinct mechanisms (inversion / transition timing / rotation);
  rule = pick level+hour where BC direction matches observed flow.
- Fixed-12Z scoring is a known LIMITATION — events peaking overnight (HMRC1, CUUC1) are
  missed. New frame must score/measure at each event's peak window, pre-registered.
- Data on hand: 172 usable RAWS files / 12 events; ERA5 pulls for the CA events;
  verified station registry with elevation-units fixed and CRS bug fixed.
- HRRRCast → still queued for BC_SENSITIVITY (uncertainty, NOT accuracy) AFTER signal
  work. In the new frame it provides arrival-time spread for the timing channel.

---

## ONE-LINE SUMMARY

Stop trying to make WindNinja right; start using HRRR↔WindNinja disagreement (plus
terrain + synoptic state) to PREDICT where and how HRRR's wind forecast will bust —
speed, direction, arrival — then flag/bound those busts. Build the error dataset across
all 172 stations first; hunt the signal only where N supports it; confirm
leave-one-event-out; feed confirmed signals to the confidence engine.
