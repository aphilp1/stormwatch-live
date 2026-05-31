# Stormwatch — Pending Human Actions

**These items cannot be automated. Each one unblocks specific downstream work.**
Last updated: 2026-05-30.

---

## 1. Fix Synoptic API (URGENT — blocking RAWS obs fetch)

**What:** The Synoptic Data API is returning 403 on all endpoints, including
timeseries. The token generates fine but the API rejects it. This blocks
fetching historical RAWS obs for any station (BLMM8, JBGC1, Hawkeye, etc.).

**Why it matters:** The single most important test in the project — BC-corrected
WindNinja vs raw HRRR at held-out RAWS — requires historical RAWS data. Synoptic
is one of two routes to it (WRCC is the other).

**Action:**
1. Go to: https://synopticdata.com → log in → Customer Console
2. Find your API key (starts with `KuBZVMIo...`)
3. Check: is the key active? Are terms of service accepted?
4. Look for any "account issue" or "access settings" warning — the error message
   says "Review your account access settings in the customer console"
5. Once fixed, run: `python -c "from synoptic_config import SYNOPTIC_TOKEN as t; import requests; r=requests.get('https://api.synopticdata.com/v2/stations/timeseries',params={'stid':'BLMM8','recent':'60','vars':'wind_speed','units':'english','token':t},timeout=15); print(r.status_code, r.json().get('SUMMARY',{}))"` to verify

**Research tier:** Also apply for the research/academic tier (free) at the same
console — it removes the 7-day lookback limit and unlocks 2017-2019 historical
obs for Camp Fire, Tubbs, Kincade. This is the primary RAWS access path.

---

## 2. Register for Copernicus CDS — ERA5 pressure levels (HIGH VALUE)

**What:** The ERA5 archive (European Centre for Medium-Range Weather Forecasts
reanalysis) provides full 3D atmospheric structure at 28km, hourly, back to 1940.
This gives 700 hPa pressure-level winds (the BC reference level) as a
reanalysis-quality alternative to HRRR forecasts — no forecast truncation, no
spin-up artifacts. Open-Meteo's free tier returns NULL for pressure levels;
Copernicus CDS is the clean free alternative.

**Why it matters:**
- Provides independent 700 hPa BC cross-check for every event
- ERA5 vs sounding fidelity check (does ERA5 agree with Wyoming radiosonde?)
- Timing re-test without HRRR truncation artifacts
- `era5_pull.py` is written and corrected — it just needs the cdsapi credentials

**Action:**
1. Go to: https://climate.copernicus.eu → Register (free, ~5 minutes)
2. After registration, go to: https://cds.climate.copernicus.eu/user/login
3. Click your username (top right) → "API key" → copy your UID and API key
4. Create file `C:\Users\aphil\.cdsapirc` with contents:
   ```
   url: https://cds.climate.copernicus.eu/api/v2
   key: YOUR-UID:YOUR-API-KEY
   ```
5. In PowerShell: `pip install cdsapi` (or in hrrr311 conda env)
6. Tell Claude Code — it will update `era5_pull.py` to use cdsapi and run it

---

## 3. Register for NCAR RDA — ERA5 ds633.0 (ALTERNATIVE ERA5 PATH)

**What:** The NCAR Research Data Archive hosts ERA5 ds633.0 with full vertical
structure, accessible via OPeNDAP (no large downloads). Alternative to Copernicus
CDS for the same ERA5 data.

**Why it matters:** Same as #2 above — full-resolution ERA5 for BC cross-checks.
Pick either Copernicus CDS (#2) or NCAR RDA (#3); you don't need both.
Copernicus CDS is recommended (simpler API, Python `cdsapi` package).

**Action:**
1. Go to: https://rda.ucar.edu → "Create Account" (free, research/non-commercial)
2. Once registered, tell Claude Code — it will build the OPeNDAP pull script

---

## 4. WRCC — Historical RAWS (AWAITING REPLY)

**What:** Western Regional Climate Center holds historical RAWS data beyond the
7-day free window. Required for PNTM8 (Point Six, Missoula) historical obs and
potentially Camp Fire / Tubbs era stations.

**Why it matters:** PNTM8 at 7897 ft is the key above-inversion validation station
for Missoula. WindNinja predicts 40.6 mph NW flow there (40% terrain amplification).
If PNTM8 obs confirm this, it's the first terrain-amplification validation we have
with real obs at the right elevation. This is a major finding waiting to happen.

**Status:** Email sent to wrcc@dri.edu. Awaiting reply.

**Action:** Follow up if no reply within 1-2 weeks. Describe the research context
(hindcasting Missoula wind events for fire-weather forecasting) and request
hourly data for PNTM8 (WIMS 42010? — verify) for December 17, 2025.

---

## 5. SJSU/CSU-MAPS Lidar (DEFERRED — LOW URGENCY)

**What:** CSU-MAPS mobile Doppler lidar has scanning wind profiles from fire-weather
events. Provides vertical wind structure that surface RAWS can't give.

**Why it matters:** Would directly show the coupling between 700 hPa flow and
surface terrain response — the physical chain the whole pipeline is trying to model.

**Action:** Email SJSU (contact from `next_gen_engine_spec.md`) describing research
context. Not urgent until RAWS validation is cleared first.

---

## Summary table

| Action | Urgency | Blocks |
|--------|---------|--------|
| Fix Synoptic console (403) | HIGH | All historical RAWS obs fetch |
| Register Copernicus CDS | HIGH | ERA5 700hPa for all events |
| Register NCAR RDA | MEDIUM | Alternative ERA5 path (pick one) |
| WRCC follow-up | MEDIUM | PNTM8 obs; Missoula terrain validation |
| SJSU lidar | LOW | Vertical profile; defer until RAWS done |

**The critical path:** Synoptic fix → historical RAWS → BC sweep → held-out validation.
Everything else (ERA5, lidar) improves the science but doesn't change the critical path.
