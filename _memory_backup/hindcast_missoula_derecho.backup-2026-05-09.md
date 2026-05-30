---
name: Missoula derecho hindcast — July 24, 2024
description: WindNinja hindcast validation setup for Missoula derecho event, including real sounding data, station locations, and analysis workflow
type: project
originSessionId: c9f7fb6e-f1f7-461c-9a34-24f4e7e7eca6
---
# Missoula Derecho Hindcast — July 24, 2024

## Event
- **Event 1: July 24, 2024 Missoula derecho, 21:00 MDT**
- UTC equivalent: 03:00 UTC July 25, 2024

## Analysis script
`C:\Users\aphil\Documents\Stormwatch\hrrr_missoula_20240724.py`
- Uses IEM RAOB API for real radiosonde soundings (no ecCodes needed)
- Uses Open-Meteo ERA5 archive for 10m surface context
- Run with: `cd C:\Users\aphil\Documents\Stormwatch && python hrrr_missoula_20240724.py`

## Real 700 hPa data (OTX radiosonde, 00 UTC July 25 = 18:00 MDT July 24)
- **Speed: 26 kt (29.9 mph)**
- **Direction: 234° (from SW)**
- Height of 700 hPa surface: 3112 m (~10,210 ft MSL)
- Temperature at 700 hPa: 3.5°C
- Source: OTX (Spokane) NWS upper-air station via IEM RAOB API

## TFX (Great Falls) 700 hPa for comparison
- 26 kt, 234° — identical to OTX
- Confirms: synoptic flow was coherent across the region; no cross-barrier contrast

## ERA5 10m surface winds (synoptic context only, NOT terrain-resolved)
- Point Six: 5.6 mph from 220° (SW)
- Blue Mountain: 5.1 mph from 229° (SW)
- Lolo Portable: 5.7 mph from 219° (SW)
- Missoula ref: 5.6 mph from 220° (SW)
- Note: ERA5 is 31 km resolution — cannot resolve terrain jets. WindNinja does that work.

## HRRR 10m winds
- NOT obtained — ecCodes C library incompatible with Python 3.14 on Windows
- cfgrib/herbie installed but cannot load
- ERA5 10m used as synoptic substitute (adequate for context, not for terrain validation)

## WindNinja initialization (use these values)
- wind_speed = 30 mph
- wind_direction = 234° (FROM SW)
- Location: Missoula, MT (~46.87°N, 114.09°W)

## RAWS validation targets — data access status
- Point Six (MPOI):  46.876°N, -114.082°W, ~6300 ft MSL
- Blue Mountain (BLMM8): 46.832°N, -114.216°W, ~3400 ft MSL
- Lolo Portable (TS897): 46.749°N, -114.066°W, ~3200 ft MSL
- **WRCC**: blocks data older than 30 days without access code — user emailing wrcc@dri.edu to request
- **Synoptic Data free tier**: zero historical access (API key `Kun2M9j4GiyoIKzzLfqyRZa7smE8sdiC3cJA3ZR6ef`, token generated via `/v2/auth`)
- **KMSO ASOS (IEM)**: 10-hour gap 20:50 MDT Jul 24 – 06:55 MDT Jul 25; station went offline as storm hit

## NWS Local Storm Reports — best available validation data
Source: IEM GeoJSON LSR API, WFO=TFX, window 21:00 UTC Jul 24 – 06:00 UTC Jul 25  
All times MDT (UTC−6). Type G = measured gust, N = non-thunderstorm wind.

| MDT Time | Gust | Location (lat,lon) | Source |
|----------|------|--------------------|--------|
| 20:35 | 72 mph | 5 SW Lolo (46.72,−114.16) | CWOP MOMM8 |
| 20:55 | 90–100 mph | 1 SSW Missoula (46.86,−114.01) | NWS employee damage estimate |
| 21:00 | 90 mph | 1 SSW Missoula (46.85,−114.01) | Toppled 70-yr maple tree |
| 21:01 | 81 mph | 6 NW Missoula (46.92,−114.09) | Personal WX station |
| 21:03 | 66 mph | 2 ENE Stevensville (46.53,−114.05) | CWOP AV610 |
| 21:04 | 65 mph | 1 ENE East Missoula (46.88,−113.92) | WU KMTMILLT2 |
| 21:05 | 109 mph | 2 SSW East Missoula (46.85,−113.96) | WU station Mt. Sentinel 5026 ft |
| 21:05 | 80 mph | 3 ESE Frenchtown (47.00,−114.18) | Power outage report |

## Proximity: closest LSR obs to each RAWS station
**Point Six (MPOI)** — 6300 ft, 46.876N, 114.082W:
  - 3.1 mi: 81 mph (6 NW Missoula, 21:01 MDT)
  - 3.6 mi: 90–100 mph (NWS estimate, 20:55 MDT)
  - 6.0 mi: 109 mph (Mt. Sentinel 5026 ft, 21:05 MDT) — lower elevation, opposite side of valley

**Blue Mountain (BLMM8)** — 3400 ft, 46.832N, 114.216W:
  - 8.2 mi: 72 mph (CWOP MOMM8, 20:35 MDT) — closest, storm onset
  - 8.5 mi: 81 mph (6 NW Missoula, 21:01 MDT)
  - No LSR within 8 miles — bracketed by 72–81 mph at 8+ mi

**Lolo Portable (TS897)** — 3200 ft, 46.749N, 114.066W:
  - 4.9 mi: 72 mph (CWOP MOMM8 at 5 SW Lolo, 20:35 MDT) — storm onset, closest obs
  - 7.5 mi: 90 mph (1 SSW Missoula, 21:00 MDT)

## Critical interpretation
These LSR gusts (65–109 mph) are **convective downdraft winds** from the derecho, not terrain-amplified synoptic flow. WindNinja models terrain effects on ambient flow — initialized at 30 mph / 234° it will produce 20–50 mph outputs. The 90–109 mph values are storm-generated; the comparison is qualitative, not direct.

The right WindNinja validation question: "Given 30 mph SW flow, which stations show terrain amplification relative to others, and does the terrain-driven spatial pattern match?" Not: "Did WindNinja predict 100 mph?"

## Scripts
- `C:\Users\aphil\Documents\Stormwatch\hrrr_missoula_20240724.py` — sounding + ERA5 surface winds
- `C:\Users\aphil\Documents\Stormwatch\raws_fetch.py` — Synoptic API attempt (blocked); LSR pull logic

## Previous session proxy (now superseded)
- 35 mph WSW was used as stand-in — 17% too fast, 6° off direction

## December 17, 2025 NW-flow event (WindNinja validation case 2)

### 700 hPa sounding (OTX + TFX, 12z — both identical)
- Speed: 25 kt (28.8 mph) | Direction: 315° (NW) | Height: 3166 m | Temp: 9.0°C | Dewpt: -10.0°C
- WindNinja init: wind_speed=29 mph, wind_direction=315°

### Key finding: valley cold pool decoupling
At 12z (05 MST) the surface is COMPLETELY decoupled from 700 hPa:
- KMSO airport: 130-150° SE at 12-21 mph (opposite of 315° aloft)
- BLMM8 (3412 ft): 157-182° S at 1.7-4.3 mph — also decoupled, calm
- ERA5 surface: 111-174° SE-S, 6-13 mph at all three RAWS locations

By 18-21z (11-14 MST), daytime mixing couples the flow to the surface:
- KMSO: shifts to 270-280° W at 18-22 mph (now consistent with 700 hPa NW)
- BLMM8: stays light and variable (E/SE/N, 1.7-5.2 mph) — may be sheltered or mislocated
- ERA5: shifts to 258-274° W at 13-19 mph sustained

**BLMM8 coordinate discrepancy**: Synoptic returns 46.8207°N, -114.1009°W — but memory/WRCC says 46.832°N, -114.216°W. The Synoptic coordinates place BLMM8 near East Missoula, not Blue Mountain Recreation Area SW of the city. Treat BLMM8 location as uncertain until WRCC data confirms.

### WindNinja validation interpretation for Dec 17
- At 12z: Surface-atmosphere decoupling means WindNinja (315°) vs. observed is not apples-to-apples. Model would predict NW flow; surface was SE cold pool. Elevated stations (Point Six 6300 ft) may have been in NW flow already — MPOI obs unavailable.
- At 18-21z: Coupling achieved at KMSO (W 18-22 mph); this is the right window for WindNinja comparison.
- BLMM8 not responding to coupling even in Window 2 — possible terrain shelter or coordinates wrong.

### Data sources for Dec 17 2025
- OTX/TFX sounding: IEM RAOB API (same as July event)
- KMSO: IEM ASOS (full day, 272 records)
- BLMM8: Synoptic Data API (12 hourly obs, 10-22z)
- MPOI / TS897: Not in Synoptic free-tier network — need WRCC access code
- ERA5: Open-Meteo archive, hourly 31km

## Key technical notes
- IEM RAOB API: `https://mesonet.agron.iastate.edu/json/raob.json?airport=OTX&ts=2024-07-25T00:00:00Z&fmt=json`
- IEM LSR GeoJSON: `https://mesonet.agron.iastate.edu/geojson/lsr.php?wfo=TFX&sts=...&ets=...`
- 700 hPa mandatory level: `pres == 700.0`, fields: `sknt` (knots), `drct` (degrees), `hght` (m), `tmpc` (°C)
- Convert knots to mph: multiply by 1.15078
