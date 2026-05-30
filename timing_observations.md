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

| Case | Event | Domain mean peak | Domain mean at ignition | Domain verdict | Control test |
|---|---|---|---|---|---|
| 4 | Camp Fire | fxx=18 (10 AM PST), 22.4 mph | 21.1 mph (fxx=14) | **BREAKS -- rising** | Not yet run |
| 9 | Tubbs Fire | fxx=14 (14z Oct 8), 24.4 mph | fxx=28 (Oct 9 04:45z) | **CONFIRMS -- 14h before** | Site leads mean +4h; ctrl LAGS mean 4h → 8h difference → NOT simple geometry |
| 8 | Thomas | Stitch required: ~midnight Dec 3-4 | fxx=33 (Dec 4 09:45z) | **CONFIRMS (stitched)** | Site leads mean +6h; ctrl leads mean +3h → 3h difference |

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

## REVISED STATUS (2026-05-30 — after Opus critique)

**The simple declining-limb thesis is WOUNDED.** Camp Fire domain mean was rising
at ignition. Until Tubbs/Thomas overnight pulls are run (full overnight coverage,
same as Camp), their post-peak claims may be truncation artifacts from the 12z run
window, not confirmed post-peak ignitions.

**The local-lead observation (fire site peaks before domain mean) has two
failure modes that prevent 700 hPa alone from resolving it:**

1. TRANSLATING-FEATURE GEOMETRY: Mass 2021 explicitly describes the shortwave/AWB
   crest propagating SE across the domain. Any spatial average over a moving feature
   smears/delays the peak vs any single point on the early/upwind side -- purely by
   geometry, no terrain required. "Fire site peaks 2h before domain mean" may just be
   "this point is on the early side of the moving max." A non-channeled control point
   in the same domain should show the same lead if geometry, different lead if terrain.

2. 700 hPa DOESN'T CONTAIN CANYON FLOW: The 700 hPa field is smooth at 3km.
   Canyon/gap flow isn't IN it -- that's the whole reason WindNinja exists. What we
   see as "Jarbo point peaks before mean" is the synoptic 700 hPa value above the
   fire site, not resolved terrain channeling. "Canyon responds faster" can't be read
   from 700 hPa alone.

**The real timing mechanism test** is: does the SURFACE (RAWS) wind at a channeled
site peak earlier, relative to the 700 hPa driver, than at a non-channeled site?
That's the surface-vs-aloft lag question, and it needs RAWS obs -- same data gate
as the amplification work.

**What the Camp Fire pull DID cleanly produce:**
  Camp Fire ignited on the RISING limb of the synoptic 700 hPa domain mean.
  This is a finding (pre-registered, BREAKS). It means Tubbs and Thomas's
  apparent post-peak ignition needs confirmation from overnight pulls.

## UPDATED STATUS (2026-05-30 — after Tubbs/Thomas overnight pulls)

Scoreboard: 2 CONFIRMS (Tubbs, Thomas), 1 BREAKS (Camp Fire).

**Tubbs control test result: antisymmetry DISSOLVED by geometry check (2026-05-30).**
Fire site peaked 4h before domain mean; control peaked 4h after. Initial read:
"not consistent with simple translating-feature geometry."
Geometry check: at the fire-site-peak time (fxx=10), flow direction was ~335 NNW.
Fire site (38.57N, -122.58W) is 0.37 deg NORTH and 0.78 deg WEST of control
(38.20N, -121.80W). For NNW flow, fire site is on the upwind side. NNW flow hits
the coastal mountains (fire site) first, then reaches the valley foothills (control).
The +4/-4 split IS consistent with translating-feature geometry -- it is purely
positional. No terrain-advance signal survived this check.
This was the last candidate finding in the timing thread. It did not survive.

**Camp Fire vs Tubbs/Thomas:** Camp Fire is the narrow gap/canyon mechanism (Feather
River Canyon). Tubbs and Thomas are broader downslope events over wider terrain. The
domain mean's timing behavior differs between these sub-types. This may itself be
informative: broader downslope peaks before ignition; narrow gap/canyon peaks after.

**Thomas archive limitation:** HRRR Dec 2017 (HRRRv2) only stores 18h forecasts from
00z run. Used stitch of Dec 3 00z (fxx=0-18) + Dec 4 00z (fxx=0-15, from Case 8).

## DATA CEILING REACHED (2026-05-30)

Every remaining timing question routes through RAWS obs or more events.
The 700 hPa domain series has been fully worked; nothing further is extractable
without either (a) RAWS surface-vs-aloft lag data or (b) a larger event library.

Thread is parked. Resume when RAWS data access comes through.

## REMAINING REQUIREMENTS BEFORE CLAIMING A FINDING

1. Contrast class: non-catastrophic SYNOPTIC_TERRAIN events same terrain and period.
   The 2/3 confirms are all selected cases -- need days when similar aloft wind did
   NOT produce catastrophic fire.

2. RAWS surface-vs-aloft lag test (gated on data access). The real timing mechanism
   question is whether the SURFACE response lags the aloft driver differently at
   channeled vs non-channeled sites. 700 hPa alone cannot answer this.

3. The Camp Fire anomaly needs explanation. If gap/canyon fires systematically differ
   from broader downslope fires in their timing structure, that is itself a finding
   that refines the mechanism classification (separate timing behavior for gap vs
   broad downslope within SYNOPTIC_TERRAIN).
