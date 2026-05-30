# Timing Observations — Declining-Limb Pattern

**Thread opened: 2026-05-30**

This document tracks the observation that catastrophic fire runs in SYNOPTIC_TERRAIN
events appear to occur on the DECLINING LIMB of the wind curve, not at peak wind.
This is distinct from the speed/direction BC work and belongs to Phase E (timing axis)
of the test protocol.

## Why this observation is credible

Unlike the "all fires had ~25 mph aloft wind" framing, the declining-limb observation:
- Is NOT selected-for (the selection criterion was "catastrophic fire," not "declining wind")
- Is mechanistically specific (a lag between peak aloft wind and peak surface effect)
- Is independently documented in peer-reviewed literature for Camp Fire
- Has a direct operational implication (when to issue warnings)

## Cases with evidence

### Camp Fire -- November 8, 2018
- HRRR 700 hPa (00z run): fxx=1 ~24 mph -> fxx=2 (ignition): 25.2 mph -> later declining
- Mass et al. 2021 BAMS explicitly documents WRF delayed the wind decline as a timing-bust
- Fire ignited near the peak; explosive spread coincided with declining aloft flow

### Tubbs Fire -- October 8-9, 2017
- HRRR 700 hPa (00z Oct 9 run):
  - 02z: 27.5 mph (pre-ignition peak)
  - 04z (ignition ~04:45z): 23.6 mph  <-- DECLINING
  - 06z: 19.1 mph
  - 10z: 15.0 mph
- Catastrophic overnight run into Santa Rosa occurred as winds declined
- Mass & Ovens 2019 notes Hawkeye reached record gusts -- on the declining limb

## Hypothesis (pre-registered before further testing)

The most dangerous phase of SYNOPTIC_TERRAIN fire events is the TRANSITION from
peak synoptic forcing to declining forcing, not the peak itself. Candidate mechanisms:

1. **Surface decoupling lag**: After aloft wind peaks, surface winds may stay elevated
   longer due to cold pool mixing, thermal mixing, or stable-layer breakdown.
2. **Critical-level timing**: The descending stable layer that enables downslope winds
   may not reach the surface until after the aloft peak.
3. **Fire-atmosphere coupling**: Once a fire starts, it generates its own draft,
   sustaining erratic winds after the synoptic driver weakens.

## Operational implication

If catastrophic runs reliably lag peak wind, the warning window should open at
**peak wind aloft** and remain open through the **declining limb**, not close when
aloft winds drop. Current operational approach may under-warn this window.

## What's needed to test this

1. More cases: does the declining-limb pattern hold for Thomas (Case 8), Kincade, 
   Marshall, Labor Day 2020?
2. HRRR time series around ignition for each confirmed case (already pulled for
   Camp and Tubbs; extract the peak-to-ignition timing for each)
3. Contrast class: confirmed SYNOPTIC_TERRAIN events where fire did NOT run
   catastrophically -- were those at peak or post-peak wind?

## How to populate this document

For each new hindcast case, add a row to the table below when the 700 hPa
time series is available. Note whether ignition was pre-peak, at-peak, or post-peak.

| Case | Event | Domain mean peak | Domain mean at ignition | Domain verdict | Local (fire-site) peak | Local verdict |
|---|---|---|---|---|---|---|
| 4 | Camp Fire | 22.4 mph at fxx=18 (10 AM PST) | 21.1 mph (fxx=14, 06:33 PST) | **RISING -- BREAKS** | ~20 mph at fxx=12 (04 AM PST) | Declining -- confirms |
| 9 | Tubbs Fire | 27.5 mph at fxx=2 (02z) | 23.6 mph (fxx=4, 04:45z) | **Declining -- confirms** | not yet extracted | TBD |
| 8 | Thomas Fire | 31.8 mph at fxx=6 (06z) | 28.8 mph (fxx=9, 09:45z) | **Declining -- confirms** | not yet extracted | TBD |

## AUDIT RESULT: Pre-registered prediction BROKEN for Camp Fire (2026-05-30)

Pre-registered expectation: domain mean peaks before ignition (fxx <= 14).
Actual: domain mean peaked at fxx=18, 4 hours AFTER ignition. BREAKS pattern.

Per protocol §1 prime directive: this result stands as-is. Do not rationalize.

## THE NUANCE (does not change the BREAKS verdict, but is real)

The point extractions at Jarbo Gap and fire origin tell a different story:
- Jarbo Gap 700 hPa peaked at fxx=12 (~04 AM PST), declining by ignition
- Fire origin peaked at fxx=12-13 (~04-05 AM PST), declining by ignition
- Domain mean peaked at fxx=18 (~10 AM PST), 4 hours after ignition

Possible interpretation: **terrain channeling in the Feather River Canyon peaks
EARLIER than the broader synoptic 700 hPa domain mean.** The gap/canyon flow
reaches its maximum before the large-scale 700 hPa average does, consistent with
local terrain focusing and acceleration responding faster than the synoptic driver.

If real, this is a genuinely interesting timing observation -- the LOCAL fire-site
flow peaks earlier than HRRR's domain-scale 700 hPa, which may be the relevant
quantity for both warning timing and BC quality. But this is an inference from
point extractions, not a pre-registered result, and needs verification.

## REVISED STATUS

The simple "all SYNOPTIC_TERRAIN fires ignite on the declining 700 hPa limb" is NOT
confirmed. Camp Fire's domain mean was rising at ignition.

What may be real (requires proper testing):
1. The LOCAL terrain-channeled flow at the fire site peaks EARLIER than the
   domain-scale synoptic flow -- and it is the local flow, not the domain mean,
   that is the operative timing signal.
2. Tubbs and Thomas (domain mean declining at ignition) may differ from Camp Fire
   (domain mean rising) in ways that matter for mechanism or forecast approach.

Next steps before claiming any timing finding:
1. Extract LOCAL point 700 hPa time series at fire sites for Tubbs and Thomas
   (same as just done for Camp Fire) -- do they also show local peak before ignition?
2. Contrast class: non-catastrophic days same terrain.
3. Investigate WHY Camp Fire's local flow peaked earlier than domain mean.
