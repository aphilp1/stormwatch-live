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

| Case | Event | Peak 700 hPa (mph) | At ignition (mph) | Ignition timing | Note |
|---|---|---|---|---|---|
| 4 | Camp Fire | unknown (overnight) | 25.2 mph (fxx=2, 14z) | likely post-peak | Only fxx=1-5 pulled; overnight peak not captured. Mass 2021 documents declining winds. |
| 9 | Tubbs Fire | 27.5 mph (fxx=2, 02z) | 23.6 mph (fxx=4, 04z) | **post-peak** | Clear 2-hour decline before ignition in extracted window |
| 8 | Thomas Fire | 31.8 mph (fxx=6, 06z) | 28.8 mph (fxx=9, 09z) | **post-peak** | Clear 3-hour decline before ignition |

Tubbs and Thomas: clearly post-peak in extracted windows.
Camp Fire: requires a longer pull (overnight 12z Nov 7 - 12z Nov 8) to confirm.
TODO: extend Camp Fire HRRR pull to 00z Nov 8 run to capture overnight peak.

Not yet a finding (n=2-3, all selected cases) -- needs:
1. Camp Fire overnight pull to confirm or deny
2. Contrast class (non-catastrophic SYNOPTIC_TERRAIN events same terrain)
