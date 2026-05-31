# NCAR RDA Pull Spec — Soundings + ERA5 Reanalysis

**For:** Claude Code (executes the pull + analysis locally)
**Companion to:** `stormwatch_test_protocol.md` (methodology), `next_gen_engine_spec.md`,
`station_registry_and_sources.md`. All protocol artifact-checks and ESCALATE
conditions apply to everything produced here.

---

## 1. What this is and how it fits the plan

This pull upgrades the **boundary condition (BC) input** to our WindNinja pipeline
from "a single HRRR forecast run, possibly truncated" to "reanalysis-quality synoptic
state with full vertical structure, plus a verifying radiosonde." It directly attacks
two things that have blocked us:

1. **The timing-thread truncation risk.** Camp Fire appeared to ignite on the *rising*
   limb of the domain-mean 700 hPa wind — but that came from a 12z HRRR run whose
   fxx window may not have reached the overnight peak. ERA5 is a continuous
   reanalysis with NO forecast-truncation problem. Re-running the timing picture on
   ERA5 either confirms "rising limb at ignition" as real, or reveals it as a
   HRRR-run artifact. This is the first experiment below.

2. **The BC quality.** Brewer & Clements characterized the Camp Fire using the 12z
   8 Nov 2018 **Reno** sounding (crest-level inversion + cross-barrier flow). ERA5 +
   the same sounding give us that vertical structure for every event, at reanalysis
   quality, as the clean upstream condition to drive WindNinja.

### What this does NOT do (be explicit — this is the coupling-question subtlety)

The coupling test we actually care about — *synoptic driver → localized terrain
response* — has two ends. **This pull gives us the synoptic INPUT end at high quality.
It does NOT give us the localized terrain-response OUTPUT end**, which is still RAWS
surface winds (gated) or the CSU-MAPS lidar (one email to SJSU). ERA5 at 0.25°
(~28 km) and a sounding will NOT show a Feather River Canyon jet — they are not
supposed to. ERA5's job here is to anchor *what the synoptic flow and inversion were
doing upstream*, not to resolve the canyon.

So the value is **sequencing**: we lock down the input side now (unblocked), so that
when RAWS access lands the coupling test is fast — only the output side remains to
plug in. A reanalysis-quality BC is a prerequisite for every coupling test we will
eventually run. Building it now is not a detour; it is the input half of the one test
that matters.

---

## 2. Access setup — USER RESPONSIBILITY (not Claude Code, not Opus)

RDA datasets require a **free registered login**. Account creation and credential
handling must be done by Alex directly — Claude cannot create accounts or complete
auth flows. Once registered:

- Create the RDA account at the dataset access page (free, "research/non-commercial").
- Configure credentials in Claude Code's local environment (RDA uses a token/cookie
  auth for programmatic access; the dataset's "Data Access" tab documents the current
  method — historically a `.netrc` / token approach).
- The **University of Wyoming** sounding archive needs NO login and serves single
  soundings immediately — use it for the fast per-event sounding (see §4).

If the RDA auth flow blocks, that is an ESCALATE-to-human item (it's an access door
designed for a human to walk through), not something to engineer around.

---

## 3. Dataset targets (verified current IDs, May 2026)

| Dataset | What | Coverage | Access | Use |
|---|---|---|---|---|
| **ds633.0** | ERA5, 0.25° pressure levels (netCDF-4) | 1979→near-present | login + **OPeNDAP subset** | Primary synoptic BC reference |
| **ds633.6** | ERA5 model-level (137 hybrid levels) | 1979→present | login + OPeNDAP | Optional: finer vertical near crest |
| **ds337.0** | NCEP ADP global upper-air + sfc (PREPBUFR) | 1997→present | login + "Get a subset"→netCDF/ASCII | Systematic multi-event sounding extraction |
| **ds351.0** | NCEP ADP global upper-air (sonde-only product) | 1999→present | login | "little_r" product feeds WRF later |
| **Wyoming archive** | Single radiosonde profiles | historical | **open, browser, no login** | Fast per-event sounding (paper's source) |

Note: RDA absorbed the CDG/GDEX catalogs in Aug 2025; you may see `gdex.ucar.edu`
mirror URLs — `rda.ucar.edu/datasets/dXXXXXX/` is canonical.

---

## 4. Exact pull spec

### 4a. ERA5 pressure-level (ds633.0) — the workhorse

**Bounding box (all CA events):** lat **35–42°N**, lon **−124 to −117°W**.
(Tighten per-event later if needed; one box covers Camp, Tubbs, Thomas, Kincade.)

**Variables:**
- `u`, `v` wind components (→ speed + direction via `vec_avg`; never average raw deg)
- `z` geopotential (→ geopotential height; needed for the terrain-height guard and
  to confirm 700 hPa sits above terrain per event)
- `t` temperature (→ inversion structure / crest-level stability)
- `r` relative humidity (→ dryness context; secondary)
- single-level: `msl` (mean sea-level pressure) for the inverted-trough analysis

**Pressure levels:** **500, 700, 850, 925, 1000 hPa** minimum. **700 hPa is the BC
reference level** — but apply the HGT:700 guard per event (high domains: confirm 700
is above terrain; if not, use the lowest valid level above crest and flag).

**Time windows (hourly):**

| Event | Window (local) | Ignition |
|---|---|---|
| Camp Fire | 7–9 Nov 2018 | ~06:33 PST 8 Nov 2018 |
| Tubbs | 8–10 Oct 2017 | night 8–9 Oct 2017 |
| Thomas | 4–6 Dec 2017 | evening ~4 Dec 2017 |
| Kincade (Case 10) | 23–25 Oct 2019 | ~21:27 PDT 23 Oct 2019 |

Pull in UTC; convert with the correct PST/PDT offset per event (Camp/Kincade span the
Nov/Oct DST boundary — verify offset, this is a known footgun).

**Method:** OPeNDAP regional subset (request the box+levels+time slice, do NOT
download global files). A CA-box, 5-level, 3-day hourly subset is small.

### 4b. Soundings

- **Fast path (do first, no login):** University of Wyoming upper-air archive
  (`weather.uwyo.edu/upperair/sounding.html`). Pull:
  - **Reno, NV (REV)** — the Sierra/Camp Fire crest-level sounding the paper used
    (verify the WMO station number in the interface before scripting; do not assume).
  - **Oakland, CA (OAK)** — the Bay Area sounding for Tubbs/Kincade (Diablo cases).
  - Times: 00z and 12z bracketing each ignition.
- **Systematic path (login):** ds337.0 "Get a subset" → netCDF, same station list +
  windows, for reproducible multi-event extraction.

**Cross-check discipline (protocol §2.1 analog for soundings):** the ERA5 vertical
profile at the sounding's location/time should resemble the observed sounding. If
ERA5 matches the Reno sounding's inversion height and 700 hPa wind, ERA5 is a trusted
BC source. If it diverges, that is itself a finding about reanalysis fidelity in
complex terrain — ESCALATE it, don't bury it.

---

## 5. Experiments to run once pulled (ordered for cleanest signal)

1. **Timing re-test on ERA5 (highest priority — resolves a parked thread).**
   Extract the ERA5 700 hPa wind time series at each fire site AND domain-mean over
   the box, for Camp/Tubbs/Thomas. Compare ignition timing to the wind-evolution
   limb. Because ERA5 has no forecast truncation, this adjudicates whether Camp's
   "rising limb at ignition" was real or a 12z-HRRR artifact. Pre-register the
   expectation before looking: if Mass 2021's sunrise-peak description is right,
   ERA5 should show Camp peaking near/just-before the 06:33 ignition.
   **Apply the same domain-mean-vs-point and propagation-geometry checks that killed
   the Tubbs antisymmetry** — a point leading the mean is translating-feature geometry
   until a control point on the same propagation axis proves otherwise.

2. **Characterize the clean BC per event.** For each event at ignition ±hours:
   700 hPa speed + direction (vec_avg), geopotential height (guard check), crest-level
   inversion height/strength from `t`. This is the reanalysis-quality upstream
   condition — the BC that drives WindNinja, replacing the hand-tuned / single-run BC.

3. **ERA5-vs-sounding fidelity check** (§4b cross-check). Trust-or-flag ERA5 as a BC
   source before relying on it.

4. **Stage as WindNinja BC input.** Feed the characterized BC into the BC sweep
   apparatus so that when RAWS lands, the input side is locked and only the held-out
   surface validation (Colby/Saddleback) remains. This is the join point with the
   confidence engine: an ensemble of ERA5-derived BCs → WindNinja ensemble →
   `confidence_field.py` → per-cell confidence, all obs-independent.

---

## 6. Conventions & checks that apply (from the protocol)

- **vec_avg for all direction work** (u/v decomposition); never average raw degrees;
  regress direction as sin/cos, reconstruct with atan2.
- **Domain-mean ≠ point.** Label which is which everywhere; a point leading the mean
  is geometry until a control proves terrain.
- **700 hPa validity:** run the HGT:700 guard per event; high domains may need a
  higher valid level.
- **Provenance on every number:** coordinates+source, level, time-matching, UTC↔local
  offset used. The DST boundary on Camp/Kincade is a live error source.
- **ESCALATE:** any finding that survives the checks; any ERA5-vs-sounding divergence;
  any result that revises a prior committed result (e.g. if ERA5 overturns the Camp
  timing picture); any auth dead-end.
- **Negative results count.** "ERA5 confirms HRRR timing" or "ERA5 700 hPa is a clean
  BC" are findings, not non-events.

---

## 7. Where this sits in the master plan

- This is **Phase A/E input work**: it hardens the BC (Phase A) and re-opens the
  timing thread (Phase E) using unblocked data.
- It does **not** close the coupling test — that needs the RAWS/lidar output side,
  still gated. Treat **RAWS research-tier token + WRCC outreach + the SJSU/CSU-MAPS
  lidar ask** as the parallel critical path; this pull makes that path fast when it
  lands.
- It feeds the **confidence engine** and the **surrogate WindNinja**: ERA5-derived BC
  ensembles are exactly the input distribution both need, and none of it waits on obs.

**One-line summary:** pull the synoptic input at reanalysis quality now, so that the
moment the terrain-response output unlocks, the coupling test runs immediately —
and in the meantime, re-adjudicate the Camp Fire timing question that the truncated
HRRR run left unresolved.
