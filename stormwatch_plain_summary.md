# StormWatch — HRRR / WindNinja BC Correction: Plain-Language Summary

---

## The problem we started with

During big fire weather events — Santa Ana winds, Diablo winds, the kind that drove Camp
Fire and Thomas Fire — the HRRR weather model consistently undershoots the real wind speed
at exposed ridge stations. A ridge station might measure 46 mph while HRRR says 10 mph.
That's not a small rounding error; it's a factor of 4. StormWatch is built on HRRR data, so
StormWatch inherits that miss.

## What WindNinja is

A separate tool that takes a single "background" wind number and runs terrain physics on
it — channeling through gaps, acceleration over ridges, deflection off slopes. It doesn't
have its own weather forecast; you give it a wind and it downscales it to every spot on a
DEM (a terrain map). The question was: if you feed WindNinja the right background wind
number, can it recover the ridge station reading that HRRR misses?

## What "BC" means

Boundary condition — the background wind you hand to WindNinja. We've been pulling it from
HRRR's 850 hPa or 700 hPa level (roughly 5,000–10,000 feet up), the atmospheric layer that
matters for fire-spread weather. The hypothesis was that HRRR gets the aloft wind
approximately right but fails to mix it down to the surface. WindNinja's terrain physics
does the mixing.

## What we spent the last several sessions doing

Testing whether that hypothesis holds, and if so, building a systematic way to correct the
BC input before handing it to WindNinja. The work broke into layers:

1. **Phase A** established that the underbias is real and structured — it happens at exposed
   ridge stations in offshore/Santa Ana regimes, not randomly everywhere. The average miss
   at those stations is about 7 mph, but the worst cases are 20–35 mph.

2. **The outer trainer** found that three observable features — the strength of the 700 hPa
   wind, the pressure gradient, and how coupled the boundary layer is — can predict how much
   to correct the BC input, with real out-of-sample signal (RMSE halved vs. doing nothing).

3. **The timing fix** found that for long multi-day events like Thomas Fire, we were
   accidentally pulling the BC from the wrong hour — the December 5th peak instead of
   December 7th when a specific station actually peaked. That alone accounted for most of the
   anomalous readings.

4. **The inner rule** addressed a subtler problem: even if the event-level correction points
   the right way for 20 out of 21 stations, one station (WMSC1, Warm Springs) needed
   correction in the opposite direction. It needed more BC input, not less, because its
   particular valley channeling means WindNinja amplifies whatever you give it. The terrain
   geometry (high relief, steep slope) identifies that station as a "WN will amplify here"
   case, and you should not reduce its BC even when the event average says reduce.

5. **The final test** ran WindNinja at four real stations with the two-level pipeline live.
   At WMSC1/Thomas Fire, the error went from −32 mph (flat correction, wrong direction) to
   +11 mph (two-level, right direction). The mechanism works as designed.

---

## What it means for StormWatch

The pipeline now exists to take a HRRR forecast, identify ridge stations where the aloft
wind isn't reaching the surface, correct the BC input using event-level synoptic features
plus terrain geometry, and run WindNinja to produce a downscaled wind estimate that is
closer to what RAWS stations actually measure.

That's the direction of the product: better wind at the stations that matter most during
fire weather — the exposed ridges where fires explode. The two-level architecture is the
mechanism that makes it possible to do this station-by-station without accidentally pushing
the wrong stations in the wrong direction.

## Where it stands

The two-level architecture is **validated as a mechanism**: it correctly flips the one
station whose station-level direction disagreed with the event-level correction (WMSC1),
and changes nothing at the stations that already agreed. The direction logic is solved.

What remains is **magnitude calibration**. Across the four test stations, the correction
beats the naive flat correction everywhere, but it only beats raw (uncorrected) BC at some
of them — because the correction magnitude is still sized to the event average, not the
individual station. WMSC1/Thomas overshoots to +11 mph (it needed about +15, the event
average supplied about +19). That is the one refinement step left, and it is a much smaller
problem than the factor-of-4 miss we started with.
