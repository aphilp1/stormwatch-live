# Stormwatch Hindcast Event Library — Erratic-Wind Fire Events

A curated catalog of extreme-wind wildfire events for reconstruction, hindcasting,
and training the BC-correction algorithm. Organized by the **mechanism taxonomy**
from `mechanism_classifier.py`, because what determines whether an event is usable
is not how famous or how erratic it was — it's *which physical process* produced
the wind, and therefore whether the synoptic→WindNinja approach can model it.

## How to read this catalog

Each event carries:

- **Mechanism** — the bin from the classifier (SYNOPTIC_TERRAIN / PBL_TRANSIENT /
  CONVECTIVE_OUTFLOW / FIRE_GENERATED).
- **WindNinja** — applicability: HIGH (core use case) / PARTIAL (snapshot the
  regimes, not the transition) / NONE (out of scope, kept for contrast & classifier
  training).
- **HRRR** — data availability. **This is a hard gate for the BC pipeline.** The
  HRRR archive on AWS/GCS is reliable from roughly **mid-2016** onward (HRRRv2+);
  earlier events have no usable HRRR and can only be studied with reanalysis or as
  mechanism/historical references. Events are tagged HRRR-YES / HRRR-NO / HRRR-MARGINAL.
- **Bust axis** — which forecast channel the event most stresses (timing / speed /
  direction), i.e. what this event is good for *testing*.
- **Why it's useful** — what this specific event teaches that others don't.

### Priority tiers (suggested build order)

- **TIER 1 — Validation anchors** (in scope, HRRR-YES, well-documented, good obs):
  the spine of the training set. Build these first.
- **TIER 2 — In-scope expansion** (SYNOPTIC_TERRAIN/PBL, HRRR-YES, usable obs):
  grow N here once Tier 1 works.
- **TIER 3 — Contrast / classifier cases** (out of scope for WindNinja, but needed
  to train and stress-test the mechanism classifier; some convective/fire-generated).
- **TIER 4 — Historical / foundational** (pre-HRRR; mechanism study only, no BC loop).

> The whole point of including out-of-scope events is that the classifier must learn
> to *reject* them. A library of only clean synoptic-terrain cases can't teach the
> system where its own boundaries are.

---

## TIER 1 — Validation Anchors

### Camp Fire — 2018-11-08 — Butte County, CA  ✅ DONE
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed
- Ignition Pulga / Poe Dam (39.56, -121.44). Diablo (NE offshore gradient) flow
  channeled in the Feather River canyon. RAWS Jarbo Gap observed 52 mph gust; HRRR
  10 m ~8 mph (terrain-blind). Optimal BC 35 mph NE @ 700 hPa →
  Jarbo 49.7 (+42%), Concow 67.3 (+92%), Paradise 53.8 (+54%), Pulga 60.5 (+73%).
- **Why it's the anchor:** low domain (~300–1000 m) so 700 hPa is a clean BC with no
  terrain-extrapolation concern; the +9.8 mph speed residual is physically real.
  The Concow +92% is an open finding (strongest amplification, no station to validate).

### Missoula Dec 17 2025 cold-frontal — 2025-12-17 — Missoula, MT  ✅ DONE (Case 2)
- **Mechanism:** PBL_TRANSIENT | **WindNinja:** PARTIAL | **HRRR:** YES | **Bust axis:** timing + direction
- Cold frontal wind shift. Network: KMSO (valley ASOS), PNTM8/Point Six (ridge,
  7897 ft, NIFC coords 47.041/-113.986), BLMM8 (foothills SE), TS897 (Lolo valley).
  WindNinja init 315° NW / 29 mph from the 12z OTX 700 hPa sounding → Point Six 1.40×
  amplification, valley/sheltered sites near-ambient.
- **Why it's the anchor for the *timing* axis:** the "coupled window" (cold pool mixed
  out 18–21z) vs "decoupled" (11–13z) split is the timing-bust problem in miniature —
  WindNinja is only valid *after* coupling. This event is the empirical seed of the
  deferred timing-bust detector.
- **Two known data hazards captured here:** (1) the domain-mean raw-HRRR 700 hPa was
  unusable (frontal straddle + possible below-ground extrapolation over the high
  ridges), which is why the *sounding* value was used as BC; (2) Point Six was at wrong
  coords until 2026-05-28 — a cautionary tale for label quality.

### Thomas Fire — 2017-12-04 to 12-05 — Ventura/Santa Barbara, CA  🔨 Case 8 (planned)
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed
- Classic Santa Ana: NE gradient flow descending the Santa Ynez / Topa Topa ranges.
  One of the strongest Santa Ana events on record, extremely well documented.
- **Why it's the chosen 3rd anchor:** tests whether the BC-residual method generalizes
  across a *different mountain system* with the *same* mechanism as Camp Fire — the
  exact generalization claim the outer trainer needs.
- **Terrain-height guard note:** San Bernardino peaks (San Gorgonio 3506 m) sit near/above
  the 700 hPa altitude → the guard built for Case 8 gets its hardest real test here.
  **Sample the ridgetop wind at the Topa Topa/Santa Ynez crest UPWIND of the fire**, not
  San Gorgonio off to the east, or the guard flags the wrong peaks.

---

## TIER 2 — In-Scope Expansion (SYNOPTIC_TERRAIN / PBL, HRRR-YES)

### Marshall Fire — 2021-12-30 — Boulder County, CO  ⭐ HIGH VALUE
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed + direction
- Front Range downslope windstorm, sustained ~11 hours; gusts 100–115 mph at the
  foothill base (peak 115 mph in Arvada); sustained >45 mph for 8 h. Grass→urban.
- **Why it's a standout:** the mountain wave produced a **wind reversal** — sites farther
  east (Lafayette, Broomfield) switched to opposite-direction flow. A single WindNinja
  domain must capture both the 100+ mph downslope core AND the reversal zone: the hardest
  terrain-flow test in the library. **Bonus:** studied by the NOAA/GSL HRRR team (James &
  Benjamin), so a documented HRRR baseline exists to validate against. Dense Front Range
  obs network. Winter event = stronger terrain-height-guard relevance (cold column).

### Labor Day 2020 Oregon east-wind event — 2020-09-07 to 09-08 — W. Oregon Cascades  ⭐ HIGH VALUE
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed + timing
- Rare, abrupt east "downslope" windstorm down the Cascade west-side drainages
  (McKenzie, Santiam, Clackamas). Sustained E-NE 20–30 mph, gusts 50–60 mph; 66 mph at
  Horse Creek RAWS (between Riverside & Beachie Creek fires); >100 mph at Timberline
  Lodge. Drove 5 simultaneous megafires (Beachie Creek, Holiday Farm, Riverside,
  Lionshead, Archie Creek).
- **Why useful:** multiple drainages in one synoptic event = several independent terrain-
  channeling sub-domains from a single BC; the abrupt onset (“arrived with a bang” ~4–6pm)
  is a clean *timing* test. Sparse Cascade obs is the main limitation — lean on Horse
  Creek RAWS and any portable units.

### Lahaina / Maui Fire — 2023-08-08 — West Maui, HI
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** NO (HRRR is CONUS+Alaska; **no Hawaii coverage**)
- Strong NE trades + stable layer at West Maui crest → high-amplitude mountain wave +
  gap funneling; downslope gusts 60–80 kt (≈70–92 mph). Winds locally doubled/tripled
  the 20–30 mph background.
- **Why useful despite HRRR-NO:** the *cleanest documented mountain-wave/downslope case*
  and mesoscale models nailed location/strength/timing — an excellent WindNinja terrain
  test IF an alternative BC source is used (trade-wind synoptic + sounding, or a non-HRRR
  model). **Important subtlety:** despite media framing, the peer-reviewed analysis
  (Mass & Ovens 2024) finds Hurricane Dora had little direct effect — BC comes from the
  trade/ridgetop-stability setup, not the hurricane. Flag as a known popular-vs-science
  conflict.

### Tubbs Fire — 2017-10-08 to 10-09 — Sonoma/Napa, CA
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed
- Diablo wind event; the fast overnight run into Santa Rosa (Fountaingrove/Coffey Park).
  Mayacamas terrain channeling.
- **Why useful:** same Diablo mechanism as Camp Fire but different terrain (Mayacamas vs
  Feather River) and a *nighttime* run — tests whether the BC method holds when surface
  is decoupled and only the aloft flow matters. In the existing 7-fire queue.

### Kincade Fire — 2019-10-23 — Sonoma County, CA
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed
- Geyserville Diablo event; RAWS network on the Mayacamas captured strong NE gusts;
  PSPS-era so unusually dense obs/documentation.
- **Why useful:** good obs density on terrain; pairs with Tubbs for same-region repeat.

### Glass Fire — 2020-09-27 — Napa/Sonoma, CA
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed
- Diablo-driven; overlaps Tubbs/Kincade terrain. Another Mayacamas repeat for the same
  mechanism/region — useful for per-region calibration of the BC residual.

### Woolsey Fire — 2018-11-08 — Los Angeles/Ventura, CA
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed + direction
- Santa Ana; Santa Monica Mtns channeling, run to the coast. Same calendar day as Camp
  Fire (different airmass/region). In the existing queue.
- **Why useful:** lower, more isolated terrain than Thomas (Santa Monica Mtns ~600–900 m)
  → a *clean* Santa Ana BC with minimal terrain-height-guard concern; good contrast to
  the Thomas high-terrain case.

### East Troublesome Fire — 2020-10-21 — Grand County, CO
- **Mechanism:** SYNOPTIC_TERRAIN (with possible plume-assisted run) | **WindNinja:** HIGH/PARTIAL | **HRRR:** YES | **Bust axis:** speed
- Extreme wind-driven run (~100k+ acres in a night) up to and over the Continental Divide.
- **Why useful (and caution):** a high-elevation Rockies case → strong terrain-height-guard
  test (like Marshall but forested/higher). Caution: the most explosive phase had plume
  involvement, so it may classify MIXED — a good real test of the classifier's MIXED flag.

### North Complex / Bear Fire — 2020-09-08 to 09-09 — Plumas/Butte, CA
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** HIGH | **HRRR:** YES | **Bust axis:** speed + timing
- The N-NE wind-driven run into Berry Creek — same Feather River country as Camp Fire,
  same drainage system, different season (Sept, the Labor Day synoptic pattern).
- **Why useful:** near-identical terrain to your anchor but a *different synoptic driver* —
  isolates terrain response from synoptic forcing in the BC residual.

### Almeda Fire — 2020-09-08 — Jackson County, OR
- **Mechanism:** SYNOPTIC_TERRAIN | **WindNinja:** PARTIAL (lower-relief Rogue Valley) | **HRRR:** YES | **Bust axis:** speed
- Part of the Labor Day east-wind event but in the Rogue Valley; grass/urban corridor
  (Ashland–Talent–Phoenix–Medford).
- **Why useful:** lower-relief test — checks whether the BC method adds value where terrain
  channeling is modest (a useful negative/low-amplification control vs Camp Fire's canyon).

---

## TIER 3 — Contrast / Classifier Cases (out of scope for WindNinja)

> These exist to **train and stress-test the mechanism classifier** and to define the
> boundary of the BC pipeline. They are deliberately the cases WindNinja should NOT be
> trusted on.

### Missoula July 2024 derecho — 2024-07-24 — Missoula, MT  ✅ already ruled out
- **Mechanism:** CONVECTIVE_OUTFLOW | **WindNinja:** NONE | **HRRR:** YES | **Bust axis:** timing + speed
- LSR gusts 72–109 mph from convective downdrafts. The canonical "wrong event type"
  contrast already used to validate the WindNinja exclusion logic.

### Yarnell Hill Fire — 2013-06-30 — Yavapai County, AZ
- **Mechanism:** CONVECTIVE_OUTFLOW | **WindNinja:** NONE | **HRRR:** MARGINAL (early HRRR; verify archive) | **Bust axis:** timing + direction
- Outflow from a collapsing thunderstorm reversed the surface wind, killing 19 Granite
  Mountain Hotshots. THE canonical convective-outflow fire fatality.
- **Why essential:** the textbook case the classifier MUST bin as CONVECTIVE_OUTFLOW (not
  synoptic) — a sudden, thunderstorm-driven direction reversal. If the classifier ever
  calls this SYNOPTIC_TERRAIN, the safety logic is broken. Also the strongest argument for
  why the *timing/direction* axis matters operationally.

### Carr Fire — 2018-07-26 — Shasta County, CA
- **Mechanism:** FIRE_GENERATED | **WindNinja:** NONE | **HRRR:** YES | **Bust axis:** all
- Produced a documented **fire-generated tornado** (EF-3-equivalent vortex) near Redding —
  the fire made its own wind.
- **Why essential:** the cleanest CONUS FIRE_GENERATED case with rich documentation; tests
  the classifier's pyro/plume gating (the fix we made for the pyroCb tie). Background
  synoptic flow was modest, so it stresses the "violent local wind under weak ambient
  forcing" exclusion diagnostic.

### Creek Fire — 2020-09-04 — Fresno/Madera, CA (Sierra NF)
- **Mechanism:** FIRE_GENERATED | **WindNinja:** NONE | **HRRR:** YES | **Bust axis:** all
- One of the largest documented pyroCb events in CONUS; plume-dominated growth.
- **Why useful:** an extreme pyroconvection case for the classifier — high reflectivity/CAPE
  that is fire-made, not ambient. Direct test of `plume_collocated_with_fire` gating.

### Pedrógão Grande — 2017-06-17 — central Portugal
- **Mechanism:** CONVECTIVE_OUTFLOW (downburst-driven) | **WindNinja:** NONE | **HRRR:** NO (Europe) | **Bust axis:** timing + speed
- Downburst/thunderstorm-outflow-driven blowup that killed 60+; a non-CONUS analog to
  Yarnell.
- **Why useful:** international contrast case; reinforces that convective outflow is a
  global failure mode for terrain-only methods. Mechanism study only (no HRRR).

---

## TIER 4 — Historical / Foundational (pre-HRRR; mechanism study only)

> No usable HRRR; cannot run the BC loop. Valuable for mechanism taxonomy, fatality-
> pattern study, and as narrative anchors for why the program exists.

### Black Saturday — 2009-02-07 — Victoria, Australia
- **Mechanism:** PBL_TRANSIENT | **WindNinja:** PARTIAL (conceptually) | **HRRR:** NO | **Bust axis:** timing + direction
- The textbook **wind-change** disaster: a cool SW frontal change swung the wind and
  turned long fire flanks into head fires. 173 deaths.
- **Why foundational:** the global archetype of the PBL_TRANSIENT/timing-bust failure —
  the same physics as Missoula Dec 17, at catastrophic scale. The "when does the change
  arrive" question, made lethal.

### South Canyon / Storm King Mtn — 1994-07-06 — Colorado
- **Mechanism:** PBL_TRANSIENT (dry cold-front wind shift) | **WindNinja:** PARTIAL | **HRRR:** NO | **Bust axis:** timing + speed
- A passing dry cold front sharply increased and shifted winds; 14 firefighters died on
  steep terrain. Mechanism: frontal wind shift + terrain (a hybrid of your two in-scope bins).

### Oakland Hills / Tunnel Fire — 1991-10-20 — Oakland, CA
- **Mechanism:** SYNOPTIC_TERRAIN (Diablo) | **WindNinja:** PARTIAL (conceptually) | **HRRR:** NO | **Bust axis:** speed
- Diablo-driven urban firestorm; same mechanism as Camp/Tubbs, decades earlier.

### Mann Gulch — 1949-08-05 — Montana
- **Mechanism:** terrain + (debated) slope/wind interaction | **WindNinja:** N/A | **HRRR:** NO | **Bust axis:** n/a
- The foundational wildland-fire-behavior fatality case (Maclean, *Young Men and Fire*).
  Included for completeness and mechanism-history context; no quantitative use.

---

## Coverage map (what the library tests)

| Mechanism | Tier-1/2 in-scope count | Terrain systems covered | Gaps to fill |
|---|---|---|---|
| SYNOPTIC_TERRAIN | ~10 | Feather R., Mayacamas, Santa Ynez, Santa Monica, Front Range, Cascades, W. Maui, Rockies | More gap-wind (vs downslope) cases; non-CA low-relief |
| PBL_TRANSIENT | 2 (Missoula; +historical) | N. Rockies | Need a HRRR-era CA/Great Basin frontal-shift fire |
| CONVECTIVE_OUTFLOW | 2–3 | N. Rockies, AZ | More HRRR-era CONUS outflow cases |
| FIRE_GENERATED | 2 | N. CA, Sierra | More pyroCb cases for gating robustness |

### Recommended ingestion order
1. **Marshall + Labor Day 2020** — both HIGH VALUE, HRRR-YES, dense docs; biggest N gain.
2. **Tubbs + Kincade + Glass** — Mayacamas cluster; same region, fast per-region calibration.
3. **Woolsey** (clean Santa Ana, pairs with Thomas) then **North Complex** (Camp terrain, new driver).
4. **Yarnell + Carr** — wire the classifier's reject/MIXED behavior against the canonical
   convective and fire-generated cases.
5. **Lahaina** — only once a non-HRRR BC path exists (it's the best mountain-wave case but
   needs an alternative forcing source).

---

## Schema mapping note (for P2 HindcastEvent)

Each entry above maps to a `HindcastEvent` record. Minimum fields to populate per event:
`event_id`, `date`, `domain_center (lat,lon)`, `ignition (lat,lon)`, `mechanism`
(from classifier), `windninja_applicability`, `hrrr_available` (bool), `bust_axis`,
`station_network` (RAWS/ASOS ids + authoritative coords), `bc_source`
(700hPa sounding | HRRR domain-mean | ridgetop-level), and `notes`. Attach the
`mechanism_classifier.to_hindcast_block()` output once diagnostics are populated.

## Data-availability reminders (from lessons already learned)
- **HRRR archive:** reliable ~mid-2016+; CONUS + Alaska only (no Hawaii → Lahaina needs
  an alternative BC source).
- **Historical RAWS:** Synoptic free tier lacks history; WRCC blocks >30-day data without
  an access code (wrcc@dri.edu). Budget for this on every pre-30-day case.
- **Soundings (RAOB):** ~12-hourly, sparse — use for *mechanism diagnosis* (inversion,
  critical level, mountain-wave setup) and as the BC source where domain-mean HRRR fails
  (e.g. Missoula). Validate HRRR pseudo-soundings against the nearest real RAOB.
- **Terrain-height guard:** mandatory for high-terrain domains (Marshall, Thomas, East
  Troublesome, Lahaina) — check HGT:700mb vs local terrain, flag cells within ~200 m.
