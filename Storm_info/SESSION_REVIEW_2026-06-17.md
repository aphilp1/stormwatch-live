# StormWatch HindC — Full Session Review · 2026-06-17
**For external audit · Claude Web**
**Covers: all changes made in the June 17 evening session**

Source files:
- `weather-alerts.html` — StormWatch Live app (HindC tab + station popup)
- `Storm_info/HINDC_REVIEW.md` — primary audit document for findings/narratives
- `Storm_info/STORMWATCH_MASTER_STATUS.md` — authoritative findings ledger
- `Storm_info/hrrr_error_dataset.csv` — 164 active rows, source of all numbers

GitHub: https://github.com/aphilp1/stormwatch-live
Latest commit: b38b83a (as of this session)

---

## Part 1 — What Changed This Session

### 1.1 SLEC1 framing (the primary fix)

**Problem:** The popup showed three rows (obs / HRRR / 850 hPa BC) but omitted the WindNinja
output — the actual deliverable. Without it, a viewer concludes "just use 850 hPa instead of
10m HRRR," which is not the claim and omits WindNinja entirely.

When the WN output is computed (WN/obs ratio × obs speed), SLEC1's story inverts:
- obs = 35.0 mph
- BC = 33.5 mph (already 1.5 mph below obs; bc/obs = 0.96)
- WN output = 1.128 × 35.0 = **39.5 mph** (overshot obs by 4.5 mph)

SLEC1 is not a niche win — it is the bc/obs ≈ 1 boundary case where WN's terrain
amplification pushed an already-near-right BC past the target.

CBXC1 is the clean case:
- obs = 29.0 mph
- HRRR = 25.4 mph (genuine 3.6 mph gap; HRRR/obs = 0.875)
- BC = 32.9 mph
- WN output = 1.007 × 29.0 = **29.2 mph** (matched obs)

**What was changed:**
1. **Popup** — added a 4th row: "WN 30m Hindcast (output)" in amber, showing the WN output
   speed and WN/obs ratio for CBXC1 and SLEC1 (stored in `wn_stations` object in EXPT_EVENTS).
2. **Camp Fire card narrative** — rewrote to lead with CBXC1 as the clean recovery and frame
   SLEC1 explicitly as the bc/obs ≈ 1 boundary (BC near-right, WN amplified past target).
3. **HINDC_REVIEW.md Finding 3** — removed the intro rule ("bc/obs ≤ ~1 → closes gap;
   >1 → overshoots") which contradicted CBXC1's actual data (CBXC1 bc/obs = 1.135 yet WN
   matched obs). Replaced with two-station evidence leading directly to the terrain-geometry finding.
4. **HINDC_REVIEW.md Current State** — separated the two ratios: CBXC1 as clean recovery,
   SLEC1 as bc/obs ≈ 1 boundary case, not a co-equal win.
5. **HINDC_REVIEW.md table row** — "−3 to −18 mph" relabeled as
   "−3.6 (CBXC1) · −18.3 (SLEC1) — range across 2 anchors."
6. **STORMWATCH_MASTER_STATUS.md** — updated SLEC1 HRRR/obs from 0.525 → 0.477 with
   reconciliation note.

### 1.2 SLEC1 HRRR ratio reconciliation

**Problem:** Earlier analyses (MASTER_STATUS, hglc1_stage2.py, thomas_stage2.py) recorded
SLEC1 HRRR/obs = 0.525. The current authoritative CSV gives:
`hrrr_10m_mph = 16.7 / obs_sus_mph = 34.99 = 0.477`

0.525 and 0.477 cannot both be right. The discrepancy likely reflects a different HRRR
extraction or observation window used in the original WN runs vs. the current CSV.

**Resolution:** 0.477 is correct per the current CSV (the source of truth). All narrative text
now uses 0.477. The WN/obs ratio (1.128) is unaffected — WN uses the 850 hPa BC (33.5 mph),
not the 10m HRRR value.

The older scripts should not be cited for the HRRR/obs ratio. This is documented in
HINDC_REVIEW.md Known Open Issues.

### 1.3 Popup logic improvements (three new flags)

**Context:** Reviewing QYRC1 (Quincy Rd, Camp Fire) showed a near-calm station (obs = 2 mph)
where the popup presented:
- A 172° direction flip between obs and HRRR (noise, not signal at 2 mph)
- An 850 hPa BC of 16.9 mph (bc/obs = 8.4) labeled "WN input" with no warning
- "+1.5 mph — near-zero error" framing that read as a validation success

Three fixes applied to `makeStationPopup()` in `weather-alerts.html`:

**Fix A — Direction suppression below 5 mph**
Directions on obs and HRRR bars are suppressed when speed < 5 mph (CALM_FLOOR).
An italicized note appears: "Direction suppressed below 5 mph — unreliable at near-calm speeds."
BC direction is always shown (the synoptic flow is meaningful regardless of surface speed).

**Fix B — bc/obs decoupling flag**
When bc/obs > 3, an orange warning banner appears below the BC bar:
`⚠ bc/obs X× — BC much stronger than surface obs; do-no-harm gate required before running WN`
Threshold is 3 (not 2) to avoid false positives on continental Chinook events where 850 hPa
is legitimately stronger than surface (e.g., Marshall Front Range: bc/obs 2.9, obs = 23 mph).

**Fix C — Near-calm error description**
When obs < 5 mph, the error line changes from "HRRR vs. station obs: near-zero error" to
"calm / sheltered — do-no-harm, not a WN target." The error value color changes from the
HRRR-error color to grey (#8a9eb8) so it doesn't read as a directional signal.

**Data sweep results (164 active stations):**
- 5 stations with obs < 5 mph: all also have bc/obs > 5 (direction + calm flags trigger)
- 33 stations with bc/obs > 3: Missoula Dec cold pool (7), Labor Day OR (6),
  Thomas Santa Ana (5), Missoula Jul convective (6), Camp sheltered (3), others
- 0 stations missing BC data: all KEEP/CAUTION rows have bc_speed populated

---

## Part 2 — Current Popup Logic (Full Description)

### 2.1 Function signature
`makeStationPopup(row, err, obs, hrrr, bc, obsDir, col, wnSpd)`

- `row` — CSV row object (all station fields)
- `err` — speed_err = hrrr_10m_mph − obs_sus_mph (HRRR error, negative = undershoot)
- `obs`, `hrrr`, `bc` — speed values in mph
- `obsDir` — observed wind direction (degrees FROM)
- `col` — bar color for HRRR (red if undershoot, blue if overshoot)
- `wnSpd` — WN output speed in mph, or null if WN not yet run

### 2.2 Display rows (in order)

| Row | Color | Label | Direction | Note |
|-----|-------|-------|-----------|------|
| 1 | Green #44dd88 | RAWS Station Obs | obsDir if obs ≥ 5 mph | — |
| 2 | err-color | HRRR 3km Forecast | hrrrDir if hrrr ≥ 5 mph | — |
| — | orange banner | ⚠ direction suppressed | — | only if obs < 5 mph |
| 3 | Purple #b09af8 | HRRR {level} BC (WN input) | bcDir always | — |
| — | orange banner | ⚠ bc/obs X× — gate required | — | only if bc/obs > 3 |
| 4 | Amber #f59e0b | WN 30m Hindcast (output) | none | WN/obs ratio | only if wnSpd ≠ null |
| footer | — | error value + description | — | grey if obs < 5 mph |
| footer | — | Slope · Relief · Elev | — | terrain metadata |

### 2.3 Error description logic

```
if obs < 5 mph:        "calm / sheltered — do-no-harm, not a WN target"
elif err < −2:         "HRRR undershoots obs"
elif err > +2:         "HRRR overshoots obs"
else:                  "near-zero error"
```

### 2.4 WN output row

Only appears for stations in `ev.wn_stations` (currently only Camp Fire CBXC1/SLEC1):
- CBXC1: speed = 29.2 mph, ratio = 1.007
- SLEC1: speed = 39.5 mph, ratio = 1.128

WN/obs ratio displayed is computed live from `wnSpd / obs` (not from stored ratio).
The `maxSpd` for bar scaling includes wnSpd, so bars stay proportional to the highest value.

---

## Part 3 — Worked Examples for Audit

### 3.1 CBXC1 — clean niche (Camp Fire)

| Field | Value | Source |
|-------|-------|--------|
| obs | 28.99 mph @ 69.3° | CSV |
| HRRR | 25.37 mph @ 98.0° | CSV |
| HRRR err | −3.62 mph (HRRR/obs 0.875) | CSV |
| 850 hPa BC | 32.93 mph @ 85.8° | CSV |
| bc/obs | 1.135 | computed |
| WN output | 29.2 mph | 1.007 × 28.99 |
| WN/obs displayed | 1.007 | 29.2 / 28.99 |

Popup shows: 4 bars. No flags (bc/obs 1.135 < 3; obs 29 mph > 5). HRRR error says "HRRR
undershoots obs." Amber WN bar lands at 29.2, visually on top of the green obs bar.

**Check:** bc/obs = 1.135 > 1, yet WN matched obs. This DOES NOT violate Finding 3 (the
rule was removed for this reason). The finding now leads with what happened, not a rule.

### 3.2 SLEC1 — bc/obs ≈ 1 boundary (Camp Fire)

| Field | Value | Source |
|-------|-------|--------|
| obs | 34.99 mph @ 52.0° | CSV |
| HRRR | 16.70 mph @ 64.7° | CSV |
| HRRR err | −18.29 mph (HRRR/obs **0.477**) | CSV |
| 850 hPa BC | 33.51 mph @ 81.3° | CSV |
| bc/obs | 0.957 | computed |
| WN output | 39.5 mph | 1.128 × 34.99 |
| WN/obs displayed | 1.129 | 39.5 / 34.99 |

Popup shows: 4 bars. No flags (bc/obs 0.957 < 3; obs 35 mph > 5). HRRR error says "HRRR
undershoots obs." Amber WN bar at 39.5 visually extends past the green obs bar at 35.0 —
the overshoot is visible.

**Check:** WN/obs displayed = 1.129 (computed from 39.5/34.99). Stored ratio = 1.128.
Difference of 0.001 is a rounding artifact (39.5 is 1.128 × 34.99 = 39.47, rounded to 39.5;
39.5/34.99 = 1.1289 → rounds to 1.129). Not material; one decimal place would eliminate it.

**Note on HRRR direction:** obs @ 52°, HRRR @ 64.7° — 12.7° difference. Both are above
5 mph, so both directions display. The 12.7° gap is within normal model error range.
The 850 hPa BC @ 81.3° is 29.3° more easterly than obs — WN inherits this direction offset.

### 3.3 QYRC1 — near-calm, decoupled (Camp Fire)

| Field | Value | Source |
|-------|-------|--------|
| obs | 2.0 mph @ 59° | CSV |
| HRRR | 3.5 mph @ 231° | CSV |
| HRRR err | +1.5 mph | CSV |
| 850 hPa BC | 16.9 mph @ 93° | CSV |
| bc/obs | 8.4 | computed |

Popup shows: 3 bars (no WN). Directions suppressed on obs and HRRR with note. Orange
bc/obs banner: "⚠ bc/obs 8.4× — BC much stronger than surface obs; do-no-harm gate
required before running WN." Error line: "calm / sheltered — do-no-harm, not a WN target"
in grey. bc direction @ 93° still displayed (synoptic flow is meaningful).

**HRRR direction @ 231° vs obs @ 59°:** 172° flip. At 2 mph this is pure noise; direction
is now suppressed. If directions were shown, a viewer would see alarming disagreement on what
is actually a calm station.

### 3.4 Missoula Dec STVM8 — cold pool, non-calm (bc/obs > 3)

| Field | Value | Source |
|-------|-------|--------|
| obs | 20.0 mph | CSV |
| HRRR | 33.1 mph | computed from err +13.1 |
| HRRR err | +13.1 mph (HRRR overshoots) | CSV |
| 700 hPa BC | 88.5 mph | CSV |
| bc/obs | 4.4 | computed |

Valley station. 700 hPa jet overhead at 88.5 mph while the cold pool traps 20 mph surface.
Popup shows: 3 bars. Orange banner fires (bc/obs 4.4 > 3). Error says "HRRR overshoots obs."
Directions shown (obs 20 mph > 5). No WN row.

**This is the correct display:** the gate is required here. Running WN with 88.5 mph BC
would produce output far exceeding the 20 mph surface observation.

---

## Part 4 — Current HINDC_REVIEW.md Status

### What was changed

**Finding 3:** Original intro stated "bc/obs ≤ ~1 → WN closes gap; bc/obs > 1 → overshoots."
This rule contradicts CBXC1 (bc/obs = 1.135 > 1, yet WN matched obs). The rule was removed.
Finding 3 now leads with the two-station evidence and the terrain-geometry finding:
- CBXC1: recovery (WN/obs ≈ 1.0, genuine HRRR gap existed; gentle slope 5.96°, WN decelerated)
- SLEC1: mild overshoot (WN/obs 1.128; steeper slope 11.2°, WN amplified past near-obs BC)
- Same near-obs BC, opposite terrain response — terrain geometry determines the outcome

**Current State:** Was "WN/obs 1.007 and 1.128" as co-equal niche wins.
Now: CBXC1 labeled clean recovery; SLEC1 labeled bc/obs ≈ 1 boundary case, not a clean win.

**Table row:** "−3 to −18 mph" → "−3.6 (CBXC1) · −18.3 (SLEC1) — range across 2 anchors"

**Known Open Issues:** Added SLEC1 HRRR ratio reconciliation (0.525 vs 0.477).

### What was NOT changed (remains from prior sessions)

- Finding 1 (regime signal): offshore mean −3.9 mph, continental +0.5 mph. These are
  event-level means, correctly labeled. Not station-level figures.
- Finding 2 (resolution cause): ERA5 vs HRRR comparison. Not changed.
- Finding 4 (architecture): Thomas −32 → +11 mph flip. Do-no-harm gate at Woolsey.
  Not changed.
- All 12 event narratives except Camp Fire. Not changed.

---

## Part 5 — Things for Claude Web to Check

### Check 1: Finding 3 internal consistency
Does the terrain-geometry finding hold against the two-station arithmetic?
CBXC1: bc/obs=1.135 (higher), slope 5.96°, WN decelerated → WN/obs 1.007.
SLEC1: bc/obs=0.957 (lower), slope 11.2°, WN amplified → WN/obs 1.128.
The finding claims terrain geometry (not bc/obs) determines WN's direction of movement.
Check this against Part 3 worked examples — the inversion of bc/obs values is the key test.

### Check 2: SLEC1 overshoot
Is WN/obs 1.128 correctly characterized as an overshoot rather than a win?
Check: obs = 35.0, WN output = 39.5, overshoot = 4.5 mph, bc/obs = 0.96.
Does the current narrative call this a win anywhere it shouldn't?

### Check 3: CBXC1 bc/obs anomaly
CBXC1 has bc/obs = 1.135 (BC exceeds obs) yet WN output = 29.2 ≈ obs. The removed rule
("bc/obs > 1 → WN overshoots") would have predicted overshoot here. The current text does
NOT make a prediction about CBXC1's bc/obs, it just reports what happened. Is this handled
correctly, or does any remaining text imply bc/obs < 1 was required for CBXC1 to work?

### Check 4: HRRR/obs ratio
Is 0.477 used consistently for SLEC1 throughout HINDC_REVIEW.md? Is 0.525 gone?
(grep for 0.525 — should return zero hits in HINDC_REVIEW.md)

### Check 5: bc/obs flag threshold
The flag fires at bc/obs > 3. Is this threshold appropriate, or are there cases where
it fires incorrectly (giving a misleading warning) or fails to fire (missing a real problem)?
The 33 stations flagged are listed in Part 1.3 data sweep results above.

### Check 6: Near-calm obs < 5 mph handling
Does the "calm / sheltered — do-no-harm" framing correctly describe what these stations
represent? Are there any near-calm stations that are genuinely fire-weather cases where this
framing is wrong?

### Check 7: Two-comparison principle
The established framing requires exactly two comparisons: HRRR vs. station obs, and WN
hindcast vs. station obs. Does the popup consistently show only these two? Is there any row
or label that implies a third comparison (e.g., BC vs. obs as a standalone metric)?

---

## Part 6 — Known Remaining Gaps (not fixed this session)

1. **WN output only available for Camp Fire CBXC1/SLEC1.** 8 events still show 3-bar popup
   with no WN row. These are correctly labeled "In Progress" in the event cards.

2. **SLEC1 WN direction unknown.** WN output direction is not stored (wn_minus_hrrr_dir:
   NEEDS_WN in CSV). The WN row shows speed + WN/obs ratio but no direction arrow.

3. **WN/obs rounding:** Displayed ratio (39.5/34.99 = 1.129) differs from stored ratio
   (1.128) by 0.001 due to rounding of stored speed to one decimal. Not material.

4. **CBXC1 bc/obs = 1.135 is unexplained.** Why does WN not overshoot when bc > obs?
   Likely: CBXC1's terrain geometry in the WN DEM caused mild deceleration rather than
   amplification (slope 5.96°, relief 224m — relatively gentle). The data shows it; the
   mechanism is physically plausible but not quantified.

5. **Tubbs direction mismatch** (25–44° ENE structural offset at inland stations): withheld.

6. **RRFS ladder**: blocked on NOAA RDHPCS.

---

*Commit: b38b83a · 2026-06-17*
*Review document: SESSION_REVIEW_2026-06-17.md*
*Primary audit document: HINDC_REVIEW.md*
*Raw URL: https://raw.githubusercontent.com/aphilp1/stormwatch-live/master/Storm_info/SESSION_REVIEW_2026-06-17.md*
