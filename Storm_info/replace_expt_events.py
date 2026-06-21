"""
Replace EXPT_EVENTS array in weather-alerts.html (lines 7508-7705)
with updated data reflecting actual batch results.
"""
import re

HTML = r'C:\Users\aphil\Documents\Stormwatch\weather-alerts.html'

NEW_EXPT_EVENTS = r"""const EXPT_EVENTS = [
  {
    id: 'camp_2018',
    name: 'Camp Fire',
    date: 'Nov 8, 2018',
    regime: 'diablo',
    regimeLabel: 'Diablo (offshore NorCal)',
    lat: 39.78, lng: -121.62,
    n: 12,
    anchor: 'CBXC1',
    hrrr_err: -3.6,
    wn_a_err: +6.4,
    wn_b_err: -10.8,
    status: 'pass',
    statusLabel: 'WN Niche',
    wn_stations: {
      CBXC1: { speed: 35.3, ratio: 1.219, wn_err: +6.4 }
    },
    note: 'Niche anchor. Held-out test: WN/obs 1.007 (CBXC1) and 1.128 (SLEC1) with raw HRRR BC — where HRRR alone undershot by 3–18 mph. Reality B KNOWN_FAIL: raw BC is already correctly sized here, learned correction overshoots.',
    narrative: 'The niche anchor. Two held-out exposed-ridge stations, raw HRRR BC only. CBXC1 (Colby Mtn, WN/obs=1.007): HRRR undershot −3.6 mph; WN terrain physics closed the gap. SLEC1 (Saddleback, WN/obs=1.128): steeper terrain amplified past obs — same near-obs BC, opposite terrain response. bc/obs ≤ 1 is the necessary condition; terrain geometry controls how close WN gets.\n\nReality B KNOWN_FAIL: where the raw BC is already correctly sized, the learned correction moves the answer the wrong direction. The do-no-harm gate exists for exactly this case.'
  },
  {
    id: 'tubbs_2017',
    name: 'Tubbs Fire',
    date: 'Oct 8, 2017',
    regime: 'diablo',
    regimeLabel: 'Diablo (offshore NorCal)',
    lat: 38.44, lng: -122.71,
    n: 7,
    anchor: 'HWKC1',
    hrrr_err: -0.3,
    wn_a_err: null,
    wn_b_err: null,
    status: 'hrrrok',
    statusLabel: 'HRRR OK',
    wn_stations: {},
    note: 'HRRR resolves Hawkeye Ridge accurately (ratio 0.997) — no WN correction needed at anchor. On hold: 25–44° direction offset at valley stations requires decision before batch run.',
    narrative: 'HRRR resolves Hawkeye Ridge accurately (HRRR/obs ratio 0.997) — no WindNinja correction needed at the anchor. Documented finding: systematic 25–44° direction offset at inland valley stations (WISC1, KNXC1), where surface flow channels more northerly than the 850 hPa synoptic flow. Speed is sound at the anchor; direction at valley stations is a known open issue. WN run on hold pending direction-mismatch decision.'
  },
  {
    id: 'kincade_ign_2019',
    name: 'Kincade (Ignition)',
    date: 'Oct 23–24, 2019',
    regime: 'diablo',
    regimeLabel: 'Diablo/NW (offshore NorCal)',
    lat: 38.72, lng: -122.89,
    n: 10,
    anchor: 'COWC1/HPDC1',
    hrrr_err: -8.6,
    wn_a_err: +1.6,
    wn_b_err: null,
    status: 'pass',
    statusLabel: 'WN Niche',
    wn_stations: {
      COWC1: { speed: 30.6, ratio: 1.056, wn_err: +1.6 },
      HPDC1: { speed: 34.1, ratio: 1.178, wn_err: +5.2 }
    },
    note: 'NW Diablo flow. 2 of 3 exposed-ridge stations improved: COWC1 WN_err +1.6 vs HRRR −8.6 mph, HPDC1 WN_err +5.2 vs HRRR −7.6 mph. Third ridge (HWKC1) not improved — HRRR already overshooting there.',
    narrative: 'NW Diablo ignition-night flow. Three exposed-ridge stations in the primary pool (offset ≥ 10 km). Two niche wins: COWC1 (WN_err +1.6 vs HRRR −8.6) and HPDC1 (WN_err +5.2 vs HRRR −7.6). HWKC1 not improved — HRRR slightly overshooting, WN amplified further.\n\nSix stations fell outside the domain bounds — the single 20 mi centroid domain cannot cover the full spatial spread of this event.'
  },
  {
    id: 'kincade_run_2019',
    name: 'Kincade (Run Day)',
    date: 'Oct 27, 2019',
    regime: 'diablo',
    regimeLabel: 'Diablo/NE (offshore NorCal)',
    lat: 38.72, lng: -122.85,
    n: 12,
    anchor: 'COWC1',
    hrrr_err: -10.3,
    wn_a_err: -8.1,
    wn_b_err: null,
    status: 'pass',
    statusLabel: 'WN Niche',
    wn_stations: {
      COWC1: { speed: 19.9, ratio: 0.709, wn_err: -8.1 },
      TS379: { speed: 21.9, ratio: 3.134, wn_err: +14.9 }
    },
    note: 'NE Diablo run-day. 2 of 5 exposed-ridge stations improved: COWC1 WN_err −8.1 vs HRRR −10.3 mph. TR164/HWKC1: bc/obs > 1, WN amplifies. Contrast with Ignition (NW flow) — direction change flips which ridges align.',
    narrative: 'NE Diablo peak run-day. Five exposed-ridge stations in the primary pool. Two niche wins: COWC1 (WN −8.1 vs HRRR −10.3, error reduced) and TS379 (error magnitude reduced). Three stations not improved: TR164 (ratio 3.9×) and HWKC1 have HRRR already overshooting, WN amplifies further.\n\nContrast with Kincade Ignition (NW flow): the direction shift between ignition and run day changes which ridges the BC aligns to — same stations, opposite outcomes at some sites.'
  },
  {
    id: 'thomas_2017',
    name: 'Thomas Fire',
    date: 'Dec 4–7, 2017',
    regime: 'santa_ana',
    regimeLabel: 'Santa Ana (offshore SoCal)',
    lat: 34.27, lng: -119.25,
    n: 26,
    anchor: 'WMSC1',
    hrrr_err: -35.6,
    wn_a_err: +12.8,
    wn_b_err: +10.5,
    status: 'improves',
    statusLabel: 'WN Corrects',
    wn_stations: {
      WMSC1: { speed: 58.8, ratio: 1.279, wn_err: +12.8 }
    },
    note: 'Largest HRRR error in database (−35.6 mph at WMSC1). Reality A: WN raw flips sign to +12.8 mph. Reality B (two-level corrected BC): reduces to +10.5 mph — direction solved, magnitude bounded.',
    narrative: 'Largest single-station error in the database: HRRR undershoots WMSC1 by −35.6 mph. Reality A with raw BC: WN flips the sign from −35.6 to +12.8 mph — terrain physics recovers the error direction even without learned correction. Reality B (two-level corrected BC): −32 → +10.5 mph — direction solved, magnitude tightened by 2 mph. The +10 mph residual is the current ceiling. WMSC1 is the anchor for the Santa Ana correction pipeline.'
  },
  {
    id: 'woolsey_2018',
    name: 'Woolsey Fire',
    date: 'Nov 9, 2018',
    regime: 'santa_ana',
    regimeLabel: 'Santa Ana (offshore SoCal)',
    lat: 34.07, lng: -118.74,
    n: 17,
    anchor: 'WMSC1',
    hrrr_err: -27.0,
    wn_a_err: -0.0,
    wn_b_err: +9.2,
    status: 'nails',
    statusLabel: 'WN Nails It',
    wn_stations: {
      WMSC1: { speed: 45.0, ratio: 1.000, wn_err: -0.0 }
    },
    note: 'Same anchor (WMSC1), one year later. Raw WN: ratio=1.000, WN_err=0.0 mph — perfect. Do-no-harm gate correctly blocks Reality B correction that would overshoot +9.2 mph. Gate validation case.',
    narrative: 'Same anchor station (WMSC1), peak Santa Ana one year later. Raw WindNinja achieves near-zero error — ratio 1.000 — with no correction. The bc/obs ratio was correctly sized by the raw 850 hPa BC. Reality B: do-no-harm gate fires correctly, blocking a +9.2 mph overcorrection. This is the gate\'s clearest validation: where the raw BC is already right, apply nothing.'
  },
  {
    id: 'labor_day_or2020',
    name: 'Labor Day OR',
    date: 'Sep 7–8, 2020',
    regime: 'continental',
    regimeLabel: 'Continental (downslope OR)',
    lat: 44.0, lng: -122.8,
    n: 34,
    anchor: 'Multiple',
    hrrr_err: +2.0,
    wn_a_err: null,
    wn_b_err: null,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {},
    note: 'Largest event (34 stations across 3° latitude). All stations outside single-domain bounds — multi-domain config needed for WN. HRRR slightly overshoots (+2.0 mph). Continental baseline: anchors the positive-bias side of the regime signal.',
    narrative: 'Largest event in the database: 34 stations across three concurrent Oregon fires (Beachie Creek, Holiday Farm, Lionshead). Station footprint spans 42°–45°N — too wide for a single 20 mi domain. All 34 stations fell outside domain bounds; multi-domain configuration needed before WN can run. HRRR slightly overshoots (+2.0 mph mean), consistent with the continental regime. Anchors the positive-bias side of the regime signal.'
  },
  {
    id: 'boulder_chin2021',
    name: 'Boulder Chinook',
    date: 'Feb 2021',
    regime: 'continental',
    regimeLabel: 'Continental (Chinook CO)',
    lat: 40.01, lng: -105.27,
    n: 9,
    anchor: 'CO109/RFN',
    hrrr_err: +1.5,
    wn_a_err: null,
    wn_b_err: null,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {},
    note: 'Front Range Chinook. 7 of 9 stations within 10 km of domain center — not pooled. Highest-wind stations (CO109 51 mph, RFN 53 mph) are low-offset. No exposed ridge in primary accuracy pool. Continental baseline.',
    narrative: 'Front Range Chinook. Near-zero mean HRRR error (+1.5 mph) but severe station variance — CO109 observed 51 mph while most stations saw 12–20 mph. Station cluster is dense near the domain center: 7 of 9 stations within 10 km (OK_LOW_OFFSET, not pooled). The highest-wind stations are in the low-offset group. Continental baseline: confirms HRRR has no systematic bias in Chinook regimes.'
  },
  {
    id: 'marshall_2021',
    name: 'Marshall Fire',
    date: 'Dec 30, 2021',
    regime: 'continental',
    regimeLabel: 'Continental (downslope CO)',
    lat: 39.95, lng: -105.17,
    n: 8,
    anchor: 'CEKC2',
    hrrr_err: -12.9,
    wn_a_err: +13.6,
    wn_b_err: null,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {
      CEKC2: { speed: 48.6, ratio: 1.389, wn_err: +13.6 }
    },
    note: 'Front Range downslope. 4 exposed ridges in primary pool: bc/obs > 1 at all 4. WN flips sign at CEKC2 (−12.9 → +13.6) but magnitude worsens. Outside WN niche: BC already exceeds obs before terrain physics applied.',
    narrative: 'Front Range downslope (Dec 30, 2021). Four exposed-ridge stations in the primary pool; none achieved a niche win. bc/obs > 1 at all four, so WN amplifies existing error rather than closing a gap. CEKC2: HRRR −12.9, WN +13.6 — sign flipped but magnitude worsened. LOOC2 (5 km from center, LOW_OFFSET): ratio 2.6×. Architecture verdict: bc/obs > 1 prevents WN recovery. Confirms the continental niche boundary.'
  },
  {
    id: 'missoula_dec2025',
    name: 'Missoula Dec',
    date: 'Dec 17, 2025',
    regime: 'continental',
    regimeLabel: 'Continental (downslope MT)',
    lat: 46.87, lng: -113.99,
    n: 8,
    anchor: 'PNTM8',
    hrrr_err: -5.8,
    wn_a_err: +54.2,
    wn_b_err: +17.2,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {
      PNTM8: { speed: 100.2, ratio: 2.176, wn_err: +54.2 }
    },
    note: '700 hPa BC at 84 mph (bc/obs=1.82). WN amplifies to 100 mph at PNTM8 (obs=46 mph). Reality B (corrected BC 53 mph) reduces WN_err +54→+17. Clearest bc/obs diagnostic in the dataset.',
    narrative: 'NW foehn/downslope. PNTM8 observed 46 mph — HRRR undershot by only 5.8 mph but the 700 hPa BC was 84 mph. bc/obs=1.82: WN terrain amplification drove output to 100 mph — a 54 mph overshoot. Reality B (corrected BC 53 mph): WN_err reduces to +17 mph, recovering 37 mph of error. The bc/obs diagnostic is confirmed: when the BC exceeds obs, correction is the only path. This event is the clearest demonstration.'
  },
  {
    id: 'missoula_jul2024',
    name: 'Missoula Jul',
    date: 'Jul 2024',
    regime: 'convective',
    regimeLabel: 'Convective outflow (MT)',
    lat: 46.90, lng: -113.80,
    n: 18,
    anchor: 'BLMM8',
    hrrr_err: +9.5,
    wn_a_err: +12.4,
    wn_b_err: null,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {
      BLMM8: { speed: 24.4, ratio: 2.030, wn_err: +12.4 }
    },
    note: 'Convective outflow. bc/obs > 1 at both exposed ridges — WN amplifies into overshoot. 10 stations in primary pool, 0 niche wins. Transient forcing; not a WN target. Contrast case.',
    narrative: 'Convective outflow from afternoon thunderstorm complex. 18 stations, 10 in the primary pool. Both exposed-ridge stations (BLMM8, MOMM8): bc/obs > 1, WN overshoots. The forcing is transient — not the persistent synoptic flow that WN terrain physics target. Near-zero mean HRRR error masks severe station variance. Included as a contrast case: confirms the WN niche is regime-specific, not universal.'
  },
  {
    id: 'iowa_derecho2020',
    name: 'Iowa Derecho',
    date: 'Aug 10, 2020',
    regime: 'convective',
    regimeLabel: 'Convective outflow (IA)',
    lat: 41.98, lng: -91.66,
    n: 2,
    anchor: 'HITI4',
    hrrr_err: +5.5,
    wn_a_err: -7.8,
    wn_b_err: null,
    status: 'control',
    statusLabel: 'Control Case',
    wn_stations: {
      HITI4: { speed: 13.2, ratio: 0.629, wn_err: -7.8 }
    },
    note: 'Flat-terrain negative control (Iowa plains, 2 stations). WN on flat terrain produces near-BC output — no terrain amplification. Confirms the method does not invent corrections where there is no sub-grid terrain.',
    narrative: 'Flat-terrain negative control. Two stations on the Iowa plains during the Aug 10, 2020 derecho. HRRR slightly overshoots (+5.5 mph); WN on flat terrain produces near-BC output — no terrain amplification, error stays bounded. Confirms the pipeline behaves correctly when there is no sub-grid terrain to resolve. The only non-western event in the library.'
  }
];"""

with open(HTML, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find start and end of EXPT_EVENTS
start_line = None
end_line = None
for i, line in enumerate(lines):
    if line.strip() == 'const EXPT_EVENTS = [':
        start_line = i
    if start_line is not None and i > start_line and line.strip() == '];':
        end_line = i
        break

if start_line is None or end_line is None:
    print(f'ERROR: could not find EXPT_EVENTS block (start={start_line}, end={end_line})')
    exit(1)

print(f'Found EXPT_EVENTS: lines {start_line+1}-{end_line+1} (0-indexed {start_line}-{end_line})')

new_lines = lines[:start_line] + [NEW_EXPT_EVENTS + '\n'] + lines[end_line+1:]

with open(HTML, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'Done. Replaced {end_line - start_line + 1} lines with new EXPT_EVENTS block.')

# Verify
with open(HTML, 'r', encoding='utf-8') as f:
    content = f.read()
verify_strings = ['wn_a_err', 'wn_b_err', 'WN Niche', 'WN Nails It', 'WN Corrects', 'KNOWN_FAIL', 'bc/obs > 1']
for s in verify_strings:
    found = s in content
    print(f'  {"OK" if found else "MISSING"}: {s}')
