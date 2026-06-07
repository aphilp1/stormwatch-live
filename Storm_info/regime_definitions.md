# Synoptic Regime Definitions — Stormwatch Departure Database

**Purpose:** Operational regime taxonomy for classifying fire-weather wind events in the
departure database. Each definition is written to be applied to a NEW event without
seeing its HRRR departure — the label must be assignable from synoptic analysis alone.

These definitions lock the classification scheme before library expansion. New events
get classified by these rules, not by their departure profile.

---

## Top-level regime classes

### OFFSHORE_GRADIENT
**One-line definition:** A synoptic-scale inland high drives surface flow toward the
Pacific coast through terrain drainages and gaps; the surface pressure gradient is
primarily oriented inland-to-coast (or coast-parallel but offshore-directed).

**Physical mechanism:** SYNOPTIC_TERRAIN. WindNinja applicable (HIGH).
**Key discriminator:** Pressure gradient vector has a seaward component. Flow descends
toward the ocean, not toward an interior basin.

Sub-tags (fine-grained; use when gradient orientation is documented):
- `santa_ana` — NE→SW, Southern California (Santa Ana Mountains, San Gabriel, San Bernardino, Santa Ynez ranges)
- `diablo_offshore_NW` — NW→SE gradient, Northern California (documented case: Kincade ignition Oct 23 2019)
- `diablo_offshore_NE` — NE→SW gradient, Northern California Diablo (canonical Diablo; documented case: Kincade run Oct 27 2019, Camp Fire, Tubbs)
- `diablo_offshore` — use when NW/NE sub-tag cannot be determined from available synoptic data

**Current events (as of 2026-06-07):**
| event_id | sub-tag | basis |
|----------|---------|-------|
| woolsey_2018 | santa_ana | NE gradient, Santa Monica Mtns |
| thomas_2017 | santa_ana | NE gradient, Santa Ynez/Topa Topa |
| tubbs_2017 | diablo_offshore_NE | NE Diablo, Mayacamas channeling |
| camp_2018 | diablo_offshore_NE | NE gradient, Feather River canyon |
| kincade_ign_2019 | diablo_offshore_NW | NW ignition winds, documented pre-analysis (station_registry) |
| kincade_run_2019 | diablo_offshore_NE | NE run-phase winds, Oct 27 flow shift |

---

### CONTINENTAL_DOWNSLOPE
**One-line definition:** Synoptic or thermally enhanced flow descends from interior
mountain crests toward interior basins, plains, or coastal valleys; pressure gradient
is interior-to-interior with no seaward component; flow stays within continental airmass.

**Physical mechanism:** SYNOPTIC_TERRAIN. WindNinja applicable (HIGH).
**Key discriminator:** Flow moves from high terrain to lower terrain, but the destination
is an interior valley or plain — not the ocean. No marine influence in the forcing.

Sub-tags:
- `chinook_frontrange` — Continental Divide → Colorado/Montana Front Range; classic
  mountain-wave windstorm with downslope jet
- `downslope_oregon` — Cascade east face → western Cascade drainages; east-to-west
  cross-barrier flow driven by inland high

**Current events:**
| event_id | sub-tag | basis |
|----------|---------|-------|
| boulder_chin2021 | chinook_frontrange | Front Range downslope, CO |
| marshall_2021 | chinook_frontrange | Front Range downslope, CO |
| labor_day_or2020 | downslope_oregon | E-NE Cascade downslope, OR |

---

### FRONTAL_PASSAGE
**One-line definition:** Strong surface winds driven by a rapidly moving cold frontal
boundary; the wind event is primarily a consequence of the synoptic pressure gradient
associated with a cold-air intrusion, not terrain amplification of a sustained ambient flow.

**Physical mechanism:** PBL_TRANSIENT. WindNinja applicable (PARTIAL — valid during
the coupled post-frontal window, not during the frontal passage itself).
**Key discriminator:** The primary forcing is the frontal pressure gradient, not a
quasi-steady synoptic high. Wind direction shifts with frontal passage. Event is
time-bounded by frontal timing, not by diurnal cycle.

**Current events:**
| event_id | sub-tag | basis |
|----------|---------|-------|
| missoula_dec2025 | frontal_passage | Cold frontal wind shift, event library PBL_TRANSIENT |

*Note: Single event — hypothesis only, not a finding.*

---

### CONVECTIVE_OUTFLOW
**One-line definition:** Winds driven by mesoscale convective system (MCS) downdraft,
derecho, or organized thunderstorm outflow; the forcing is thunderstorm dynamics, not
synoptic pressure gradient; wind direction is locally unpredictable from synoptic
analysis alone and may reverse during the event.

**Physical mechanism:** CONVECTIVE_OUTFLOW (Tier 3 contrast case). WindNinja NOT
applicable. Included in departure database as mechanism-classifier training cases.
**Key discriminator:** Wind event is collocated with radar-detected convective
precipitation or documented convective downdraft/outflow. LSRs typically report
thunderstorm wind damage.

**Current events:**
| event_id | sub-tag | basis |
|----------|---------|-------|
| iowa_derecho2020 | derecho_mcs | Bow-echo MCS, event library CONVECTIVE_OUTFLOW |
| missoula_jul2024 | convective_downdraft | LSR 72–109 mph downdraft gusts, event library explicitly CONVECTIVE_OUTFLOW |

---

## What this taxonomy rules out

- A `frontal_passage` event is NOT `offshore_gradient` even if post-frontal flow
  happens to be offshore-directed in some locations.
- `continental_downslope` and `offshore_gradient` are both SYNOPTIC_TERRAIN but differ
  in gradient orientation — a chinook does not become a diablo because its flow happens
  to move toward lower terrain.
- `convective_outflow` events must NOT be grouped with either offshore or continental
  regimes in departure analysis — their dynamics are qualitatively different and the
  HRRR error mechanism is different (timing/speed of convective initiation vs.
  terrain-blind synoptic underbias).

---

## Application rule for new events

1. Check mechanism_classifier.py output — what does it bin the event as?
2. If SYNOPTIC_TERRAIN: is the gradient seaward (OFFSHORE_GRADIENT) or interior
   (CONTINENTAL_DOWNSLOPE)? Use surface analysis at peak-wind time.
3. If PBL_TRANSIENT: use FRONTAL_PASSAGE.
4. If CONVECTIVE_OUTFLOW or FIRE_GENERATED: use CONVECTIVE_OUTFLOW. Do not use for
   the departure signal analysis (out of scope for the bias characterization finding).
5. If ambiguous (MIXED): note as NEEDS_REGIME and do not include in regime group counts.

---

*Last updated: 2026-06-07. Lock date for library expansion.*
