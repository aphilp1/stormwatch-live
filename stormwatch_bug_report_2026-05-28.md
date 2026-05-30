# StormWatch MCP — QA Bug Report

**Date:** 2026-05-28
**Tester:** Claude (Anthropic)
**Scope:** Read-only QA sweep of all 32 `mcp__stormwatch__*` tools

---

## Executive Summary

A read-only sweep of ~85 tool calls across the 32 StormWatch MCP tools surfaced **24 distinct issues**:

| Severity | Count |
| --- | --- |
| Critical | 4 |
| High | 7 |
| Medium | 7 |
| Low | 4 |
| Cosmetic | 2 |

### Top 3 most important findings

1. **Geocoder silently resolves famous US locations to wrong places.** "Pikes Peak Colorado" returns *Dry Branch, Georgia*. "San Juan PR" returns *San Juan Primero, Guanajuato (Mexico)*. "San Juan Puerto Rico" returns *San Juan Puerto Montaña, Guerrero (Mexico)*. This corrupts **every location-based tool** (`get_point_forecast`, `get_terrain_wind`, `get_air_quality`, `get_weather_briefing`, etc.) and produces dangerously confident-looking but wrong output (e.g. WindNinja terrain analysis for "Pikes Peak" reported "MILD terrain influence" because it actually analyzed Georgia farmland).
2. **`get_impact_forecast` — the documented "most actionable briefing" — misses active Red Flag Warnings.** Phoenix AZ on 2026-05-28 has 2 active Red Flag Warnings (returned by `get_active_alerts` and the All-Hazards Briefing). The Impact Forecast for Phoenix reports "✅ NO ACTIVE NWS ALERTS for this location." This is a safety-critical data-flow break.
3. **`get_lightning_potential` LP index is stuck at 0.0 everywhere.** Tested at Wichita KS (CAPE 1240 J/kg), Tampa FL (CAPE 910 J/kg), Miami FL (CAPE 2180 J/kg HIGH) and Phoenix (CAPE 0). The hourly `LP` value is always `0.0`. Only the categorical label changes (based on CAPE alone). The lightning potential index field is non-functional.

---

## Methodology

**Locations tested:** Denver CO, Phoenix AZ, Miami FL, Wichita KS, Honolulu HI, San Juan PR, Fairbanks AK, Seattle WA, New Orleans LA, Tulsa OK, Aspen CO, Steamboat Springs CO, Lake Tahoe CA, Mammoth Lakes CA, Snoqualmie Pass WA, Jackson Hole WY, Boise ID, Tampa FL, Oklahoma City OK, San Francisco CA, Outer Banks NC, Springfield (no state), Pikes Peak CO, "North Pole", Equatorial Pacific (0,-140), London UK, ZIP codes 12345 / 90210, garbage strings, invalid lat/lon (999,999), invalid state codes (ZZ, XX, "  ", "California", "ca"), future dates (2030), pre-ERA5 dates (1850), non-date strings.

**Approach:**
- One normal call per tool category to establish baseline.
- Edge-case probing: international, oceanic, invalid input, extreme dates, etc.
- Cross-tool consistency for Phoenix (alerts, briefing, impact, fire trio), Miami (lightning + all-hazards), Denver (point vs briefing vs multi-location), Tulsa (gauge vs river summary), and Honolulu (river summary at multiple radii).

**Tools covered:** All 32 tools. ~85 calls total.

---

## Findings

### CRITICAL

#### BUG-001 — Geocoder resolves famous US locations to wrong places (multi-tool)
- **Tools affected:** All location-input tools — confirmed in `get_point_forecast`, `get_air_quality`, `get_terrain_wind`, `get_weather_briefing` (likely all downstream tools).
- **Severity:** Critical
- **Inputs:**
  - `location: "Pikes Peak Colorado"`
  - `location: "San Juan PR"`
  - `location: "San Juan Puerto Rico"`
- **Observed:**
  - Pikes Peak → "Dry Branch, Georgia" (75°F at 1AM, Overcast). WindNinja result: "MILD terrain influence" with peak gusts +12% (Georgia farmland).
  - "San Juan PR" → "San Juan Primero, Guanajuato" (Mexico).
  - "San Juan Puerto Rico" → "San Juan Puerto Montaña, Guerrero" (Mexico). Forecast 53°F at 1AM in May — obviously not Caribbean.
- **Expected:** Either a correct match (Pikes Peak, CO ~38.84/-105.04; San Juan, PR ~18.47/-66.11) or a clarifying error.
- **Evidence:** `get_terrain_wind(location="Pikes Peak Colorado", wind_speed=40, wind_direction=315)` header reads `Terrain Wind Analysis — Dry Branch, Georgia`. `get_weather_briefing(location="San Juan PR")` header reads `Weather Briefing — San Juan Primero, Guanajuato`.
- **Notes:** Geocoder appears to prefer the highest-population (or alphabetic?) match without weighting state abbreviation suffix or famous-place names. Critical because the user has no way to tell the answer is wrong unless they read the echoed header.

#### BUG-002 — `get_impact_forecast` misses active NWS alerts
- **Tool:** `get_impact_forecast`
- **Severity:** Critical (safety-relevant)
- **Inputs:** `location: "Phoenix AZ"`
- **Observed:** Output says `✅ NO ACTIVE NWS ALERTS for this location.` and `24-HOUR WEATHER STORY: Temps: 65°F – 92°F` (nothing else).
- **Expected:** Should include the active **Red Flag Warning** (returned by `get_active_alerts(state="AZ")` and reflected in `get_all_hazards_briefing(location="Phoenix AZ")`). It should also flag the EXTREME fire environment (per `get_fire_weather_environment`).
- **Evidence:**
  - `get_active_alerts(state="AZ")` → 2 Red Flag Warnings, Severity: Severe.
  - `get_all_hazards_briefing(location="Phoenix AZ")` → `⚠️  PRIORITY: [SEVERE] Red Flag Warning`.
  - `get_impact_forecast(location="Phoenix AZ")` → `✅ NO ACTIVE NWS ALERTS`.
- **Notes:** Documented as the most actionable briefing. Likely the alert-county/zone intersection logic is broken for Phoenix (Maricopa Co.) vs. the Red Flag for "Little Colorado River Valley in Apache/Coconino" — but the user asks for "Phoenix" expecting state-relevant context; the briefing should mention area-wide fire weather risk at minimum.

#### BUG-003 — `get_lightning_potential` LP index hard-stuck at 0.0
- **Tool:** `get_lightning_potential`
- **Severity:** Critical (field is non-functional)
- **Inputs:** `location: "Wichita Kansas"`, `"Tampa FL"`, `"Miami FL"`, `"Phoenix AZ"`
- **Observed:** Every hourly row reads `LP 0.0 — <label>`. Even with CAPE 2180 J/kg (Miami, HIGH instability), `LP 0.0`. With CAPE 0 (Phoenix), also `LP 0.0`. The categorical label moves with CAPE but the LP numeric does not.
- **Expected:** A non-zero LP index when CAPE is elevated; LP 0 when conditions truly suppressive.
- **Evidence:** Miami sample row: `1:00 AM: CAPE 2180 J/kg | LP 0.0 — LOW-MOD`. Phoenix sample: `1:00 AM: CAPE 0 J/kg | LP 0.0 — LOW`. Help-text says "LP index >10 = active cells likely" — so LP is on a 0–25+ scale; always-0 is clearly broken.
- **Notes:** Likely a unit/parsing mismatch in the Open-Meteo LP field (e.g. wrong variable name, divide-by-1000 issue, or returning all-NaN that's being coerced to 0).

#### BUG-004 — `get_snowpack_conditions` reports 4388 SNOTEL stations + permanent "Data temporarily unavailable" everywhere
- **Tool:** `get_snowpack_conditions`
- **Severity:** Critical (tool is functionally non-operational)
- **Inputs:** `Steamboat Springs CO`, `Lake Tahoe CA`, `Aspen CO (radius 50)`, `Miami FL`
- **Observed:** All four return `SNOTEL stations within X mi (4388 found): Data temporarily unavailable.` The "4388 found" count is identical across all locations including Miami FL (no SNOTEL coverage). NRCS has ~800 active SNOTEL stations nationwide, not 4388.
- **Expected:** Real per-location station counts and actual SWE/snow-depth readings.
- **Evidence:** Same `4388` count for Lake Tahoe and Miami; "Data temporarily unavailable" never resolves.
- **Notes:** Two layered bugs: (a) station count appears to be a global constant or a count of all metadata rows (not filtered by radius); (b) AWDB REST API call is failing universally.

---

### HIGH

#### BUG-005 — `get_space_weather` returns `Kp: NaN`
- **Tool:** `get_space_weather`
- **Severity:** High
- **Inputs:** (no args)
- **Observed:** `Current Kp: NaN — QUIET — calm geomagnetic conditions`
- **Expected:** Numeric Kp value (typically 0–9 scale).
- **Evidence:** Raw output: `Current Kp: NaN`.
- **Notes:** Aurora visibility / alerts sections still rendered. Suggests the planetary-Kp parser is dividing-by-zero or hitting a missing field. The categorical label "QUIET" is presumably defaulting to NaN < threshold.

#### BUG-006 — Cross-tool temperature disagreement between `get_point_forecast` and `get_weather_briefing` for the same location
- **Tools:** `get_point_forecast`, `get_weather_briefing`
- **Severity:** High
- **Inputs:** `location: "Phoenix AZ"`
- **Observed:**
  - `get_point_forecast`: 1:00 AM 70°F, 12:00 PM 86°F
  - `get_weather_briefing`: 1:00 AM 77°F, 11:00 AM 85°F
  - 7°F gap at 1 AM for the same place, same time. Briefing also includes a 12:00 AM row (79°F) the point forecast omits.
- **Expected:** Same source → same numbers.
- **Evidence:** Side-by-side outputs captured. Note: `get_all_hazards_briefing(Phoenix AZ)` shows `CURRENT CONDITIONS: 79°F` — matches the briefing path, not the point-forecast path.
- **Notes:** Likely two different upstream providers (NWS vs Open-Meteo) silently used by different tools. Either reconcile or label the data source clearly.

#### BUG-007 — `get_all_hazards_briefing` and `get_impact_forecast` accept and "work" for non-US locations
- **Tools:** `get_all_hazards_briefing`, `get_impact_forecast`, `get_weather_briefing`
- **Severity:** High
- **Inputs:** `location: "London UK"`
- **Observed:** All three produce reports for London that say `✅ No active NWS alerts. Conditions quiet for this area.` and include SPC outlooks/CONUS-only products. Impact Forecast even shows London at 87°F with CAPE 1740 J/kg "thunderstorm potential" labelled like a US briefing.
- **Expected:** Should refuse politely with "NWS/SPC/USGS gauges cover the US only" or at minimum flag the location is outside coverage.
- **Evidence:** `ALL-HAZARDS BRIEFING — London, England ... ALERTS: No active NWS alerts for this area.`
- **Notes:** Misleads agents into reporting US-style situational awareness for non-US points.

#### BUG-008 — Mismatch between `get_fire_risk_score` rating bucket and `get_fire_weather_environment` rating
- **Tools:** `get_fire_risk_score`, `get_fire_weather_environment`
- **Severity:** High
- **Inputs:** `location: "Phoenix AZ"` and `"Denver Colorado"`
- **Observed:**
  - Phoenix: `Fire Risk: 6.0/10 — HIGH` vs environment `FIRE ENVIRONMENT: EXTREME` (with "Camp Fire analog" callout).
  - Denver: `Fire Risk: 1.0/10 — LOW-MODERATE` vs environment `ELEVATED` (Denver actually has 62 dry days of 90).
- **Expected:** Score-to-label thresholds should align with the environment severity ladder (LOW / ELEVATED / CRITICAL / EXTREME).
- **Evidence:** Phoenix has 86 of 90 dry days, RH 14%, "Camp Fire analog", but the score downgrades to HIGH rather than EXTREME. Denver score 1.0 mapped to LOW-MODERATE seems mis-bucketed (1/10 should be LOW).
- **Notes:** Risk-bucket math and labels need a unified rubric across the three fire tools.

#### BUG-009 — `get_active_alerts` leaks raw NWS errors for invalid state codes
- **Tool:** `get_active_alerts`
- **Severity:** High (UX) / leaky abstraction
- **Inputs:** `state: "ZZ"`, `state: "XX"`, `state: "  "`
- **Observed:** All three return raw string `NWS API error: 400`. No human-friendly hint about valid codes.
- **Expected:** Validate state code against the 50-state + territory list and return a friendly message ("Use a 2-letter US state code, e.g. OK").
- **Evidence:** Multiple identical 400 strings observed.
- **Notes:** Contrast with `get_active_alerts(state="California")` which surfaces a (verbose) Zod validation error — also leaky but at least labelled.

#### BUG-010 — `get_historical_weather` leaks raw 400 errors for any invalid date
- **Tool:** `get_historical_weather`
- **Severity:** High (UX)
- **Inputs:** `2030-01-01` (future), `1850-04-15` (pre-ERA5), `"not-a-date"`
- **Observed:** All return `Historical weather API error: 400`. No hint about valid date range.
- **Expected:** Validate date is in YYYY-MM-DD format and between 1940-01-01 (ERA5 start) and today. Document the floor.
- **Evidence:** Three identical error responses.

#### BUG-011 — `get_nearest_gauge` leaks sentinel `-999` forecast values and impossible "12/31/1" dates
- **Tool:** `get_nearest_gauge`
- **Severity:** High (data quality)
- **Inputs:** `location: "Tulsa OK"`
- **Observed:** `Forecast: fcst_not_current (-999 ft by 12/31/1, 7:03:58 PM)` — i.e. -999 sentinel stage value and a date in year 0001.
- **Expected:** Filter out `-999` / unknown forecast and either omit the forecast row or print "Forecast: not current".
- **Evidence:** Verbatim from Tulsa gauge response.
- **Notes:** The Fairbanks AK gauge call returned a clean forecast — so the upstream sometimes provides real data and sometimes the sentinel. The tool must guard.

---

### MEDIUM

#### BUG-012 — `get_marine_weather` accepts inland and non-US locations without warning
- **Tool:** `get_marine_weather`
- **Severity:** Medium
- **Inputs:** `location: "Denver Colorado"`, `location: "51.5,-0.1"` (London)
- **Observed:** Returns a "Marine Forecast" for Denver and London with `Waves ?` (no wave data) but populated wind data — mimicking a successful response.
- **Expected:** Refuse with "no marine data within X km — try a coastal location".
- **Evidence:** `Marine Forecast — Denver, Colorado` ... `Thu 1:00 AM: Waves ? | Wind 1 mph`.

#### BUG-013 — `get_air_quality` accepts equatorial Pacific (0,-140) without warning
- **Tool:** `get_air_quality` (and `get_point_forecast`)
- **Severity:** Medium
- **Inputs:** `location: "0,-140"`
- **Observed:** Returns AQI 32 — Good for "0.0000, -140.0000" with PM/ozone values. Likely from Open-Meteo model output extrapolated over ocean; numerically plausible but semantically misleading.
- **Expected:** Either flag "model-only output over remote ocean" or reject.

#### BUG-014 — `get_climate_context` "Record range" mis-labelled as record but only uses 10-year window
- **Tool:** `get_climate_context`
- **Severity:** Medium
- **Inputs:** `location: "London UK"`
- **Observed:** Today's forecast 87°F vs `Record range: 61°F – 76°F (for this date)`. Today is 11°F above the labelled "record". Tool simply says "well above normal" without flagging the apparent record-breaking.
- **Expected:** Either rename to "10-year range" (it's the ERA5 2015–2024 range, not the all-time record) or flag when today's forecast exceeds the labelled range.
- **Evidence:** Header notes `10-YEAR AVERAGE FOR 05/28 (2015–2024)` but the sub-row is captioned `Record range`. Misleading.

#### BUG-015 — Disagreement between EPA AirNow surface reading and Open-Meteo modelled AQI in `get_smoke_situation`
- **Tool:** `get_smoke_situation`
- **Severity:** Medium (data quality)
- **Inputs:** `location: "Phoenix AZ"`
- **Observed:** AirNow surface AQI 57 (Moderate) vs Open-Meteo model AQI 49 (Good) — straddles the Good/Moderate threshold. Tool prints both without reconciling. The standalone `get_air_quality(Phoenix AZ)` reports AQI 49 (Good), matching the Open-Meteo path, not AirNow. End user reading `get_air_quality` will see "Good" while a meteorologist looking at the surface station says "Moderate".
- **Expected:** Either default `get_air_quality` to AirNow surface readings when available, or label sources in `get_air_quality` like the smoke tool does.

#### BUG-016 — `get_all_hazards_briefing` truncates alert area names and uses inconsistent severity labels
- **Tool:** `get_all_hazards_briefing`
- **Severity:** Medium
- **Inputs:** `location: "Miami FL"`
- **Observed:** `ACTIVE ALERTS — FL (5 total): [WATCH/ADV] Rip Current Statement (×4) (+1 more)` — area names stripped. Severity tag `WATCH/ADV` differs from severity in `get_active_alerts` and `get_watch_warning_summary` which use `[SEVERE]`, `[MODERATE]`, `[MINOR]`, `[EXTREME]`.
- **Expected:** Match the severity taxonomy of the other alert tools, and keep at least one identifying area string.

#### BUG-017 — `get_drought_conditions` returns empty result with no error for non-US (London)
- **Tool:** `get_drought_conditions`
- **Severity:** Medium
- **Inputs:** `location: "London UK"`
- **Observed:** Returns just a header and `Source:` line, no data and no error message.
- **Expected:** "US Drought Monitor covers US only" or similar.

#### BUG-018 — `get_river_summary` includes empty-name and Unknown-status gauges
- **Tool:** `get_river_summary`
- **Severity:** Medium (data quality)
- **Inputs:** `location: "New Orleans LA"` (default radius), `location: "Tulsa OK", radius_miles=10`
- **Observed:**
  - New Orleans: 142 of 167 gauges fall into `[Unknown]` (no flood status known) — that's 85%.
  - Tulsa 10-mi: 6 gauges, 1 with empty name field rendered as ` — Arkansas River — 7.65 ft (6 km away)`.
- **Expected:** Either exclude unnamed gauges or hide the `[Unknown]` tail behind a flag; the noise drowns out actionable data.

---

### LOW

#### BUG-019 — `get_fire_weather_environment` formats "Since 0.10\" rain: today day" / "1 days"
- **Tool:** `get_fire_weather_environment`
- **Severity:** Low (cosmetic + grammatical)
- **Inputs:** Miami FL, Denver CO, Honolulu HI
- **Observed:** 
  - Miami: `Since 0.10" rain: today day`
  - Denver: `Since 0.10" rain: today day`
  - Honolulu: `Since 0.10" rain: 1 days`
- **Expected:** "today" or "0 days" / "1 day" with proper singular/plural.

#### BUG-020 — `get_drought_conditions` prints "Honolulu County County, HI"
- **Tool:** `get_drought_conditions`
- **Severity:** Low (cosmetic)
- **Inputs:** `location: "Honolulu HI"`
- **Observed:** `Honolulu County County, HI` — duplicated "County".
- **Expected:** `Honolulu County, HI`.

#### BUG-021 — `get_all_hazards_briefing` prints alert section twice (header + body)
- **Tool:** `get_all_hazards_briefing`
- **Severity:** Low (UX)
- **Inputs:** `London UK`, `Wichita Kansas`
- **Observed:** Both lines render: `✅ No active NWS alerts. Conditions quiet for ...` followed by `ALERTS: No active NWS alerts for ...`
- **Expected:** Single line.

#### BUG-022 — `get_storm_reports` accepts invalid state codes silently
- **Tool:** `get_storm_reports`
- **Severity:** Low (UX)
- **Inputs:** `state: "XX"`
- **Observed:** Returns `No storm reports for XX today.` rather than rejecting the invalid code.
- **Expected:** Validate state code (zod schema is missing the length check that `get_active_alerts` has).

---

### COSMETIC

#### BUG-023 — Validation errors are raw Zod JSON, not friendly messages
- **Tools:** `get_active_alerts` (state too long), `get_multi_location_comparison` (array too small)
- **Severity:** Cosmetic
- **Observed:** Output is a Zod JSON error structure (multi-line `origin`/`code`/`maximum` shape) instead of a one-line user message.
- **Expected:** "State must be a 2-letter code, e.g. OK" / "Provide 2–5 locations".

#### BUG-024 — `get_active_alerts` for state="ca" works but doc says "Two-letter US state code, e.g. OK, TX, FL"
- **Severity:** Cosmetic
- **Notes:** Lowercase accepted by NWS endpoint — fine, but document or normalize. Minor consistency note.

---

## Tools that passed (normal-case calls returning sensible data)

The following tools handled at least one realistic call without errors and with internally plausible output (though some appear in bugs above for cross-tool / edge-case behavior):

- `get_active_alerts` (US states OK, AZ, CA, FL, NC, AK, VA)
- `get_watch_warning_summary` (OK, AZ)
- `get_severe_outlook` (day=1, day=2)
- `get_storm_reports` (national + filtered by valid state)
- `get_point_forecast` (Denver, Phoenix, Wichita, Fairbanks, OKC, etc.)
- `get_weather_briefing` (Wichita, Phoenix)
- `get_air_quality` (Phoenix, Boise, OKC, London)
- `get_aviation_weather` (KDEN, KJFK, KSFO, KOKC, EGLL, IATA→ICAO mapping)
- `get_marine_weather` (Miami, Outer Banks — coastal)
- `get_fire_weather_outlook` (returned graceful "not available" — possibly correct given SPC issuance timing)
- `get_fire_weather_environment` (Phoenix EXTREME, Denver ELEVATED, Miami NORMAL — directionally correct)
- `get_fire_risk_score` (Phoenix HIGH, Denver LOW-MOD, Miami LOW — directionally OK)
- `get_smoke_situation` (Boise, Phoenix)
- `get_hms_smoke` (Boise, Phoenix — national summary populated)
- `get_airnow_stations` (Phoenix, Boise — multi-station listings)
- `get_river_summary` (New Orleans, Honolulu — though noisy "Unknown" tail)
- `get_nearest_gauge` (Fairbanks clean, Tulsa with -999 issue)
- `get_drought_conditions` (Phoenix, Honolulu — though "County County" cosmetic bug)
- `get_avalanche_forecast` (graceful "not available" or "no zone found")
- `get_earthquake_activity` (San Francisco, Honolulu, OKC)
- `get_tropical_weather` (no-storm response sensible)
- `get_seasonal_outlook` (Minneapolis, London)
- `get_historical_weather` (Boston 2024-05-28)
- `get_climate_context` (Seattle, Phoenix — Phoenix internally consistent)
- `get_multi_location_comparison` (Denver/Miami/Seattle 3-city)
- `get_compare_model_forecasts` → spelled `compare_model_forecasts` (Denver, useful spread output)
- `get_terrain_wind` (Glenwood Springs, Aspen, Wichita — when geocoder picks correctly)
- `get_impact_forecast` (Wichita — clean output)
- `get_all_hazards_briefing` (Phoenix — apart from missing fire context)

---

## Patterns / Recommendations

1. **Centralize geocoding.** The Pikes Peak / San Juan PR misroutes are the most damaging issue. Add a state-code-aware tiebreaker (if the input contains "CO" or "Colorado", filter results to that state) and an "ambiguous match" warning when the top result is in a different state than the suffix. Bias toward Nominatim/US-Census results when the input matches a known US toponym list (mountains, national parks, well-known cities).
2. **Plumb alerts into every "briefing"-style tool.** Bug-002 (impact forecast missing Red Flag) and Bug-016 (truncated alert text in all-hazards) suggest the alert-aggregation layer should be a single shared function. Currently `get_active_alerts`, `get_watch_warning_summary`, `get_weather_briefing`, `get_all_hazards_briefing`, and `get_impact_forecast` each appear to format alerts differently and one of them omits them entirely.
3. **Sanitize sentinel values from upstream APIs.** `-999`, `NaN`, year-0001 dates, and 4388-of-everything need filtering at the adapter layer. (Bugs 5, 11, 4.)
4. **Friendly error wrapper.** Several tools leak raw 400s and raw Zod JSON. A small error-shaping helper that runs over the response would eliminate Bugs 9, 10, 22, 23, 17 in one pass.
5. **Unify the fire-risk taxonomy.** Pick one ladder (LOW / ELEVATED / CRITICAL / EXTREME) and have `get_fire_risk_score`, `get_fire_weather_environment`, and `get_fire_weather_outlook` share it. Currently the score is on 0–10 with labels LOW / LOW-MODERATE / HIGH / EXTREME(?) and the environment uses NORMAL / ELEVATED / EXTREME — they're hard to reconcile.
6. **LP index fix.** Either swap to a working source (e.g. Open-Meteo's `lightning_potential` flag) or compute LP from CAPE × precipitable water + cloud-ice as documented in the tool's help text. The current 0.0 everywhere is worse than not providing the field.
7. **SNOTEL adapter rewrite.** The "4388 found" plus permanent "Data temporarily unavailable" suggests the metadata-list call works but the data-query call fails. Worth a focused fix as snowpack is the only entry point for spring runoff / water-supply / avalanche-context queries.
8. **Out-of-coverage handling.** Tools that depend on US-only sources (NWS, SPC, NHC, US Drought Monitor, US AirNow, SNOTEL) should detect non-US lat/lon (use a CONUS+AK+HI+PR+territories bounding test) and refuse politely instead of silently returning empty / mixed-source output.

---

*End of report.*
