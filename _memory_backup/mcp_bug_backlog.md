---
name: mcp-bug-backlog
description: "StormWatch MCP server bug backlog from 2026-05-28 QA sweep — 24 issues, prioritized fix order"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4554217c-598d-4df8-9ee6-f90d75430f79
---

# MCP Bug Backlog — QA Sweep 2026-05-28

Source file: `C:\Users\aphil\Documents\Stormwatch\stormwatch_bug_report_2026-05-28.md`

## Fix Priority Order

### 1. BUG-001 — Geocoder resolves US places to wrong countries/states (CRITICAL)
Affects ALL location-based tools. "Pikes Peak Colorado" → Dry Branch, Georgia. "San Juan PR" → Mexico.
- **Fix:** State-code-aware tiebreaker in geocode() — if input contains state abbreviation or name, filter results to that state. Add "ambiguous match" warning.
- **File:** `mcp-server/index.js` — geocode() helper function

### 2. BUG-003 — `get_lightning_potential` LP index stuck at 0.0 everywhere (CRITICAL)
Even Miami with CAPE 2180 J/kg returns LP 0.0. Likely wrong Open-Meteo variable name or unit mismatch.
- **Fix:** Check Open-Meteo `lightning_potential` field name; may need to compute from CAPE × PW or use different variable

### 3. BUG-004 — `get_snowpack_conditions` returns 4388 stations + permanent "unavailable" (CRITICAL)
4388 count is global not filtered by radius. AWDB REST data call failing universally.
- **Fix:** Rewrite SNOTEL adapter — fix radius filtering on metadata, fix data query call

### 4. BUG-002 — `get_impact_forecast` misses active NWS alerts (CRITICAL, safety)
Phoenix Red Flag Warning appears in get_active_alerts and get_all_hazards_briefing but NOT in get_impact_forecast.
- **Fix:** Shared alert-aggregation function used by all briefing tools

### 5. BUG-011 — `get_nearest_gauge` shows -999 sentinel values and year-0001 dates (HIGH)
Filter upstream sentinels before display: -999 stage, impossible dates.
- **Fix:** Guard clause in gauge formatter — omit forecast row if stage == -999 or year < 1900

### 6. BUG-005 — `get_space_weather` Kp returns NaN (HIGH)
Parser hitting missing field or divide-by-zero.
- **Fix:** Add null check on Kp source field before arithmetic

### 7. BUG-008 — Fire risk score label doesn't match fire environment rating (HIGH)
Phoenix: score says HIGH but environment says EXTREME. Mismatched taxonomy.
- **Fix:** Unify ladder: LOW / ELEVATED / CRITICAL / EXTREME across all three fire tools

### 8. BUG-009 / BUG-010 — Raw 400 errors leaking from get_active_alerts and get_historical_weather (HIGH)
- **Fix:** Friendly error wrapper; validate state codes against known list; validate date range 1940–today

### 9. BUG-007 — Briefing tools silently run for non-US locations (HIGH)
London returns NWS briefing with "No active alerts" — misleading.
- **Fix:** CONUS+AK+HI+PR bounding box check; refuse politely if outside US coverage

### 10. BUG-016 / BUG-021 — Alert formatting inconsistencies in get_all_hazards_briefing (MEDIUM)
Truncated area names, inconsistent severity labels, duplicate alert section.
- **Fix:** Normalize to same severity taxonomy as get_active_alerts; remove duplicate section

### Lower priority (MEDIUM/LOW/COSMETIC)
- BUG-006: Temperature disagreement between get_point_forecast and get_weather_briefing (label source)
- BUG-012: get_marine_weather accepts inland locations
- BUG-013: get_air_quality accepts remote ocean points
- BUG-014: get_climate_context labels 10-yr range as "Record range"
- BUG-015: AirNow vs Open-Meteo AQI disagreement in get_smoke_situation
- BUG-017: get_drought_conditions empty result for non-US
- BUG-018: get_river_summary drowning in Unknown-status gauges
- BUG-019: "today day" grammar in get_fire_weather_environment
- BUG-020: "Honolulu County County" duplicate word
- BUG-022: get_storm_reports accepts invalid state codes
- BUG-023: Raw Zod JSON errors
- BUG-024: Lowercase state code not documented

## Key Cross-Cutting Fixes (do these once, fix many bugs)
1. **Geocoder state tiebreaker** → fixes BUG-001 (all tools)
2. **Shared alert function** → fixes BUG-002, BUG-016, BUG-021
3. **Sentinel sanitizer** → fixes BUG-004 (4388/NaN), BUG-005 (Kp NaN), BUG-011 (-999)
4. **Friendly error wrapper** → fixes BUG-009, BUG-010, BUG-017, BUG-022, BUG-023
5. **US coverage boundary check** → fixes BUG-007, BUG-012, BUG-013, BUG-017

## How to apply
When user asks to fix MCP bugs, work top to bottom on this list. BUG-001 (geocoder) is the highest leverage — it corrupts every single location-based tool. Fix that first.
