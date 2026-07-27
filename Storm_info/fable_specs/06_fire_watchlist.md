# Spec 06 — National Fire Watchlist (trigger × fuels × exposure)

*Written 2026-07-27. Goal set by Alex: predict WHERE interesting wildland fire events
will occur, where "interesting" = **high risk to property and human life**.*

## The idea

A dangerous fire event needs three things at once: a **weather trigger** (wind + dryness),
**receptive fuels** (dry vegetation), and **exposure** (people and structures in the path).
Each ingredient already has an authoritative public source. Nothing combines them.

The watchlist is a daily bot that finds the **convergence**: it sweeps every populated
place in CONUS, keeps the ones sitting inside official fire-weather/fire-potential areas,
scores fuels and wind mechanism there, and publishes a ranked list — *"the places most
likely to produce a dangerous fire event in the next 1–7 days, and exactly why."*

**Transparency rule (per Alex's standing "no homemade score" rule):** the ranking is our
synthesis, but every ingredient shown is an authoritative product quoted as-is (Red Flag
status, SPC category, PSP potential, USGS fire-danger probabilities, Census population).
The combination formula is documented here and in the JSON. No opaque "risk = 87/100".

## Candidate space: census places, not counties

Exposure is scored at the **incorporated-place level** (Census gazetteer, ~32k places
with centroid + ACS population). Rationale: "risk to property and life" is about
communities — county-level density drowns a Paradise (26k people) inside a huge rural
county, and big western counties (San Bernardino, LA) would dominate spuriously.

- Nearby-place dedupe: within a 0.25° grid cell keep the highest-population place
  (prevents 20 suburbs of one metro filling the list).
- v1 limitation (documented in output): unincorporated WUI sprawl between places is not
  separately scored; the nearest place usually catches the signal. CDPs (census
  designated places) ARE included in the gazetteer "places" file, which covers most
  named WUI communities (Paradise itself is a town; Concow is a CDP).

## Pipeline (daily, ~13:30 UTC after SPC 13z fire-wx issuance)

1. **Trigger polygons (3 pulls):**
   - SPC Fire Weather Outlook D1 + D2 categorical (dn 5/8/10) + dry-lightning polygons
     (`mapservices.weather.noaa.gov … SPC_firewx` layers 1/2/4/5, geojson).
   - Predictive Services 7-Day Significant Fire Potential, Days 1–7
     (`fsapps.nwcg.gov/psp/... outlooks_forecast` layers 0–6): keep `type` CRITICAL /
     IGNITION-risk polygons (the actual risk areas, not the dryness base fill).
   - Active NWS Red Flag Warnings + Fire Weather Watches (`api.weather.gov/alerts/active`,
     `event=Red Flag Warning,Fire Weather Watch`) — polygon geometry when present; for
     zone-based alerts (geometry null) fetch the zone geometry from
     `api.weather.gov/zones/fire/{id}` (cached across the run).
2. **Candidate filter:** point-in-polygon test of all place centroids against the union
   of trigger polygons (pure-python ray casting; no geo deps). A place qualifies if it is
   inside ANY trigger polygon. Cap: top 60 candidates by population after dedupe.
3. **Fuels at candidates (USGS fire danger, same feeds as the app's Fire Risk probe):**
   WMS GetFeatureInfo point queries for WFPI (fire potential index), WLFP (large-fire
   probability, %) and WFSP (spread probability, %). Query the place centroid plus a
   ~9 km ring (4 offset points) and keep the **max** — town centers can sit on the
   urban/water mask while the surrounding wildland is primed. Water/nodata mask: codes
   ≥248 are invalid (WLFP values are ×10; WFPI and WFSP are ×1 — see spec 05 finding).
4. **Wind mechanism at the top ~30** (after fuels): reuse `live_forecast.forecast_site()`
   (Open-Meteo → `mechanism_classifier`): threat level (CRITICAL/ELEVATED/BENIGN), peak
   gust/RH, headline mechanism, WindNinja applicability, bust axis. This is the piece
   nobody else has — it says *what kind* of wind event and how forecast models are
   likely to miss it.
5. **Score + rank** (documented formula, v1):

   ```
   trigger_pts = redflag(2|1|0) + spc(dn5→1, dn8→2, dn10→3, +0.5 dry-ltg)
               + psp(Day1 hit→1.5, Day2–3→1.0, Day4–7→0.5, summed, cap 3)
               + wind(threat CRITICAL→2, ELEVATED→1, BENIGN→0)
   fuels_pct   = max(WLFP%, WFSP%)          # authoritative probabilities, 0–100
   exposure    = log10(population)
   risk_index  = trigger_pts × (1 + fuels_pct/25) × exposure
   ```

   Product form = convergence: a ghost town or a no-trigger day zeroes out. Entries
   keep every raw ingredient so the index is auditable. `fuels_pct` missing (mask) →
   fall back to scaled WFPI (WFPI/150×20, flagged `fuels_source:"wfpi"`).
6. **Output top 15:**
   - `data/fire_watchlist.json` — generated_utc, method_version, entries with all raw
     components + human "why" strings.
   - `FIRE_WATCHLIST.md` — ranked digest for reading on GitHub.
   - Committed by `fire-watchlist.yml` Action (pattern = daily-fire-wind.yml).

## App layer (public site, same-origin JSON)

- New Fire-section toggle **"🎯 Fire Watchlist"**: numbered rank badges (1–15) at place
  coords, size/color by risk_index tier.
- Click card: place + state, population, then the three ingredient blocks —
  **Trigger** (Red Flag status, SPC category, PSP days hit, peak gust/RH + mechanism +
  WN applicability), **Fuels** (WLFP/WFSP/WFPI values), **Exposure** (population,
  housing units) — each labeled with its source agency, plus the risk_index and a
  one-line formula reminder. Freshness stamp from generated_utc ("as of 6:31 AM PDT").
- Layer note shows entry count + data date; stale (>36 h) → "outdated" warning.

## Coverage + honesty

- **CONUS-only v1** (USGS fire danger + SPC firewx don't cover AK/HI). Stated in the MD
  footer. AK/HI extension = future work (PSP covers AK; fuels source needed).
- Every value shown is fetched live from the named agency on generation day; if a feed
  fails, its component is omitted and flagged, never guessed (standing no-fake-data rule).
- The watchlist predicts *conditions for a dangerous event*, not ignitions. An ignition
  source (lightning, powerline, human) still has to happen — phrased that way in the UI.

## Static input built once (kept in repo)

`data/place_exposure.json` — from Census 2023 Gazetteer (places: GEOID, name, state,
INTPTLAT/LONG) joined to ACS 2023 5-yr B01003_001E population + B25001_001E housing
units. ~32k places, filtered to pop ≥ 1,000 (keeps file ~1 MB). Rebuild yearly.

## Future upgrades (explicitly out of v1)

- SILVIS WUI housing-in-WUI fraction per place (sharper exposure than raw population).
- ERC / dead-fuel-moisture percentile from WFAS gridded NFDRS (deeper fuels term).
- Lightning + new-starts (`WFIGS_Incident_Locations_Last24h`) as ignition-likelihood.
- Route the top-5 through the full HRRR → WindNinja pipeline for terrain-resolved wind.
- AK/HI coverage.
