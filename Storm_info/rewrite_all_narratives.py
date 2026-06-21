"""
Rewrite all EXPT_EVENTS note/narrative fields in weather-alerts.html
with plain-English text — no jargon, no internal pipeline terms.
"""

import re

HTML = r'C:\Users\aphil\Documents\Stormwatch\weather-alerts.html'

# Each entry: (event_id_marker, new_note, new_narrative)
# Narrative uses \\n\\n for paragraph breaks (JS string literal \n\n)
REWRITES = [
    # ── tubbs_2017 ──────────────────────────────────────────────────────────
    ('tubbs_2017',
     'Oct 8, 2017 Diablo wind event. HRRR captured ridge winds accurately. Valley stations showed a direction offset that needs investigation before a WindNinja run is meaningful.',
     'Tubbs Fire ignited during a Diablo wind event — offshore flow from the northeast across Sonoma County. At the exposed Hawkeye Ridge station (HWKC1), HRRR was nearly perfect, off by less than 1 mph. WindNinja would add nothing at a station where HRRR is already accurate.\\n\\nA complication: inland valley stations showed surface winds blowing 25–44° more northerly than the synoptic flow. When a valley channels wind differently from the upper atmosphere, WindNinja needs that to be understood and documented first. The WindNinja run is on hold until that direction question is resolved.\\n\\nRun 2: Planned after the direction investigation is complete.'),

    # ── kincade_ign_2019 ────────────────────────────────────────────────────
    ('kincade_ign_2019',
     'Oct 23–24, 2019 Kincade ignition night, NW Diablo flow. HRRR underestimated ridge stations by 7–10 mph. WindNinja recovered most of the gap at two of three ridges.',
     'Kincade Fire ignited under a northwest Diablo flow — offshore air from the north-northwest sweeping through the Mayacamas range. HRRR\'s 3km grid underestimated winds at exposed ridges by 7–10 mph.\\n\\nRun 1: WindNinja improved on HRRR at two of three ridge stations. At Cow Mountain (COWC1), WN narrowed the miss from −8.6 mph to just +1.6 mph. At Hopper (HPDC1), WN improved from −7.6 to +5.2 mph. One ridge station (Hawkeye, HWKC1) was not improved — HRRR was already running too high there and WN added to it.\\n\\nRun 2: With a corrected boundary condition, the two improved stations tighten further. Hawkeye Ridge\'s excess is addressed by the lower, more accurate BC input.'),

    # ── kincade_run_2019 ────────────────────────────────────────────────────
    ('kincade_run_2019',
     'Oct 27, 2019 Kincade peak run day, NE Diablo flow. Direction shifted NW→NE vs. ignition night. Same terrain, different alignment — different stations respond.',
     'Four days after ignition, the Kincade Fire accelerated under a northeast Diablo shift. The flow direction rotated from NW to NE, fundamentally changing which ridges channeled the strongest winds.\\n\\nRun 1: WindNinja improved on HRRR at Cow Mountain (COWC1), reducing the error from −10.3 to −8.1 mph. Some other ridge stations saw WN add to an already-high HRRR estimate. The NE vs. NW direction difference explains the pattern: the same terrain features align differently depending on the flow direction, so the stations that benefit from WindNinja correction change.\\n\\nRun 2: With a corrected boundary condition, the improvement at Cow Mountain becomes more complete. The direction-sensitive response across stations is the core lesson from this case.'),

    # ── thomas_2017 ─────────────────────────────────────────────────────────
    ('thomas_2017',
     'Dec 4–7, 2017 Thomas Fire, Santa Ana winds. Largest HRRR error in the database: −35.6 mph at Whitmore Station. WindNinja flipped the error sign and recovered most of the wind speed.',
     'The Thomas Fire burned under the largest HRRR undershoot in the hindcast library: HRRR missed the observed wind at Whitmore Station (WMSC1) by 35.6 mph. The 3km model grid simply cannot see the steep terrain funneling and acceleration that Santa Ana flow produces in the Transverse Ranges.\\n\\nRun 1: WindNinja reversed the error — flipping from −35.6 mph to +12.8 mph above observed. The terrain physics recovered the wind direction and most of the magnitude, even using the raw HRRR boundary condition. Getting the sign right when HRRR is off by 35 mph is the headline result.\\n\\nRun 2: A corrected boundary condition tightens the overshoot from +12.8 to approximately +10.5 mph. Terrain geometry sets the remaining margin.'),

    # ── woolsey_2018 ────────────────────────────────────────────────────────
    ('woolsey_2018',
     'Nov 9, 2018 Woolsey Fire, Santa Ana winds. Same anchor station as Thomas Fire (WMSC1), one year later. Raw WindNinja matched observations almost exactly.',
     'The Woolsey Fire burned under a strong Santa Ana event exactly one year after the Thomas Fire, with the same anchor station — Whitmore (WMSC1). HRRR again underestimated by 27 mph.\\n\\nRun 1: Raw WindNinja achieved near-zero error — ratio 1.000, essentially matching the observed wind speed precisely. When the atmospheric boundary condition is well-sized and terrain geometry aligns, WN resolves the acceleration exactly.\\n\\nRun 2: With a marginally corrected BC, the result is slightly worse — adding any correction to an already-correct answer overshoots. This is why StormWatch uses a safety check: if raw WN is already close to what was observed, don\'t apply further correction.'),

    # ── labor_day_or2020 ────────────────────────────────────────────────────
    ('labor_day_or2020',
     'Sep 7–8, 2020 Labor Day Oregon fires (Beachie Creek, Holiday Farm, Lionshead). 34 stations across 3° latitude — too wide for a single WindNinja domain. HRRR slightly overestimated.',
     'The 2020 Labor Day fires burned simultaneously across three Oregon fire complexes spanning nearly 200 miles north-to-south. HRRR slightly overestimated winds at an average of +2.0 mph — the first event in this library where the model runs too high rather than too low.\\n\\nWindNinja has not yet been run for this event: with 34 stations spread across three separate fire areas, no single domain can cover the full geographic extent. A multi-domain configuration is needed.\\n\\nThis event is included to show the Oregon continental downslope pattern — where HRRR tends to overestimate rather than underestimate, the opposite of the Santa Ana and Diablo cases.\\n\\nRun 2: A multi-domain WindNinja setup is planned.'),

    # ── boulder_chin2021 ────────────────────────────────────────────────────
    ('boulder_chin2021',
     'Feb 2021 Boulder Chinook. HRRR near-zero mean error (+1.5 mph) but extreme station-to-station variation. Some stations: 50+ mph. Others: 12–20 mph. Continental baseline.',
     'The February 2021 Boulder Chinook brought extreme wind variation: some stations observed 50+ mph while others just miles away saw only 12–20 mph — all in the same event, at the same time. HRRR\'s mean error of +1.5 mph masks that variance completely.\\n\\nRun 1: WindNinja has been run for this domain. Most stations were clustered too close to the center of the domain for the terrain physics to act fully — a known limitation of how WindNinja handles stations near the center of its computation area. The high-wind stations need their own domain placement to be resolved accurately.\\n\\nThis event is included as a continental baseline: it confirms that in Chinook regimes, HRRR has no systematic bias but also cannot resolve the extreme local variation.\\n\\nRun 2: A corrected BC and per-station domain placement are needed to resolve the highest-wind stations.'),

    # ── marshall_2021 ───────────────────────────────────────────────────────
    ('marshall_2021',
     'Dec 30, 2021 Marshall Fire, Front Range downslope. HRRR underestimated by 12.9 mph. WindNinja ran but worsened the result — the atmospheric input was already too high before terrain was applied.',
     'The Marshall Fire was driven by catastrophic Front Range downslope winds — the most destructive fire in Colorado history. HRRR underestimated the anchor station by nearly 13 mph.\\n\\nRun 1: WindNinja ran but did not improve the result. At all four exposed ridge stations, the HRRR boundary condition was already higher than what was observed at the surface — before terrain physics were applied. When the atmospheric input exceeds what the terrain would produce at the surface, WN\'s amplification makes the error larger, not smaller.\\n\\nMarshall confirms the same pattern seen in the convective cases: when the input is already too high, WindNinja cannot rescue the answer. The fix has to come from the boundary condition itself.\\n\\nRun 2: A corrected boundary condition matched to observed wind speeds would allow WN terrain physics to apply accurately. This is the key experiment for Front Range events.'),

    # ── missoula_dec2025 ────────────────────────────────────────────────────
    ('missoula_dec2025',
     'Dec 17, 2025 Missoula foehn (northwest downslope). HRRR upper-level input was 84 mph against 46 mph observed. WindNinja amplified to 100 mph. Corrected input brings WN within 17 mph of observed.',
     'A powerful northwest foehn channeled through the Clark Fork River corridor. The anchor station at Point Six Ridge (PNTM8) observed 46 mph sustained winds. But the upper-atmosphere wind speed that HRRR fed to WindNinja as input was 84 mph — nearly double what was observed at the surface.\\n\\nRun 1: WindNinja, driven by that 84 mph input, amplified through the terrain and produced 100 mph output at the station — a 54 mph overshoot. The terrain physics worked correctly: they amplified the input accurately through the terrain. The problem was the input.\\n\\nRun 2: With a corrected input of 53 mph — closer to what was actually occurring — WindNinja\'s output comes within 17 mph of observed, recovering 37 mph of error. This is the clearest case in the library showing that when the atmospheric boundary condition is wrong, correcting it matters enormously.'),

    # ── missoula_jul2024 ────────────────────────────────────────────────────
    ('missoula_jul2024',
     'Jul 2024 Missoula convective outflow. Afternoon thunderstorm wind event — not the sustained synoptic flow WindNinja targets. Both HRRR and WN overestimated. Included as contrast case.',
     'A summer afternoon thunderstorm complex produced gusty outflow winds across the Missoula valley. This is a fundamentally different type of wind event from the sustained mountain flows that WindNinja is designed for.\\n\\nRun 1: Both HRRR and WindNinja overestimated. The atmospheric boundary condition was set too high for what was an unsteady, short-lived event. WindNinja\'s terrain physics amplified an already-too-high input, making the overshoot larger.\\n\\nThis event is in the library as a contrast case: it shows what happens when a terrain-following wind tool is applied to conditions it wasn\'t built for. Convective outflow is short-lived, multi-directional, and driven by thunderstorm dynamics — not the kind of persistent, direction-consistent synoptic flow that WindNinja resolves accurately.\\n\\nRun 2: A corrected BC reduces the overestimation but does not solve the fundamental mismatch between WN\'s physics and convective forcing.'),

    # ── iowa_derecho2020 ────────────────────────────────────────────────────
    ('iowa_derecho2020',
     'Aug 10, 2020 Iowa Derecho, flat terrain. HRRR slightly overestimated. WindNinja on flat terrain passes through the BC without amplification — confirms the method does not invent corrections where terrain is absent.',
     'The August 2020 Iowa Derecho crossed the Midwest corn belt — flat terrain with no mountains, ridges, or canyons. Two RAWS stations recorded the event on the Iowa plains.\\n\\nRun 1: HRRR slightly overestimated by 5.5 mph. WindNinja, running on flat terrain, produced output nearly identical to the boundary condition — no terrain amplification because there is no terrain to amplify. The method behaves correctly and does not invent corrections where none are needed.\\n\\nThis is the only non-western-US event in the library, included deliberately to validate the pipeline\'s flat-terrain behavior. When there is no sub-grid terrain, WindNinja passes through the input cleanly. The terrain physics only activate when terrain is actually present.\\n\\nRun 2: A corrected BC would reduce HRRR\'s slight overestimate. On flat terrain, WN output tracks the BC directly, so the correction translates linearly.'),
]

with open(HTML, 'r', encoding='utf-8') as f:
    content = f.read()

total = 0
for event_id, new_note, new_narrative in REWRITES:
    # Find the event block by its id field
    marker = f"id: '{event_id}'"
    pos = content.find(marker)
    if pos == -1:
        print(f'  SKIP {event_id} — id marker not found')
        continue

    # Replace note field
    note_pattern = re.compile(r"(note:\s*')((?:[^'\\]|\\.)*)(')", re.DOTALL)
    # Find from pos forward
    section = content[pos:pos+3000]
    m = note_pattern.search(section)
    if m:
        old_note_full = m.group(0)
        new_note_full = f"note: '{new_note}'"
        section = section[:m.start()] + new_note_full + section[m.end():]
        content = content[:pos] + section + content[pos+3000:]
        print(f'  {event_id}: note replaced')
        total += 1

    # Re-find pos after modification
    pos = content.find(f"id: '{event_id}'")
    section = content[pos:pos+4000]

    # Replace narrative field
    narr_pattern = re.compile(r"(narrative:\s*')((?:[^'\\]|\\.)*)(')", re.DOTALL)
    m = narr_pattern.search(section)
    if m:
        old_narr_full = m.group(0)
        new_narr_full = f"narrative: '{new_narrative}'"
        section = section[:m.start()] + new_narr_full + section[m.end():]
        content = content[:pos] + section + content[pos+4000:]
        print(f'  {event_id}: narrative replaced')
        total += 1

with open(HTML, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nDone. {total} replacements across {len(REWRITES)} events.')
