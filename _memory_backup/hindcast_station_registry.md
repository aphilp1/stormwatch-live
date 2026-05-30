---
name: hindcast-station-registry
description: "NIFC-authoritative RAWS station IDs, coordinates, and literature validation targets for Camp Fire, Tubbs, and Kincade hindcast cases"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2ee07a89-8f8b-4d9c-a701-6f15f45f66fd
---

# Hindcast Station Registry
Source: Opus literature search 2026-05-30 (Brewer & Clements 2020; Mass et al. 2021 BAMS; Mass & Ovens BAMS)

## Camp Fire — November 8 2018

**Papers:** Brewer & Clements 2020; Mass et al. 2021 (BAMS)

| Station | ID | Lat | Lon | Elev | Notes |
|---------|-----|-----|-----|------|-------|
| Jarbo Gap | JBGC1 | 39.735944 | -121.488944 | 2535 ft | CAL FIRE 041214; ridge SE aspect; anchor station |
| Openshaw | TBD | TBD | TBD | TBD | In Mass et al. 2021 station set |
| Colby Mountain | TBD | TBD | TBD | TBD | Literature: >=58 mph (26 m/s) peak gust -- HELD-OUT target A |
| Saddleback | TBD | TBD | TBD | TBD | Literature: >=58 mph (26 m/s) peak gust -- HELD-OUT target B |
| Humbug | TBD | TBD | TBD | TBD | In Mass et al. 2021 station set |
| Stirling City | TBD | TBD | TBD | TBD | PG&E station (not RAWS) |
| Red Hill Lookout | TBD | TBD | TBD | TBD | PG&E station (not RAWS) |

**Concow/Paradise/Pulga**: NO dedicated RAWS in 2018. Jarbo Gap covers the Concow district.
The +92% Concow WN prediction cannot be validated at a Concow station. Use Colby Mountain
and Saddleback as held-out targets instead -- literature already measured ~58 mph there.

**Gust factor question**: IBHS report Fig 1 has full gust+sustained curve for Jarbo Gap
(00z Nov 8 -- 12z Nov 9). Pull this to resolve whether 52 mph was gust or sustained
before running the BC sweep. This is the pre-registered convention question.

**Audit sweep design (revised):**
- Sweep A (BC label): Jarbo Gap + Openshaw -> consistent BC for outer trainer
- Sweep B (held-out amplification): Jarbo Gap only -> check Colby Mountain + Saddleback

**Key literature findings:**
- Both BAMS papers confirm operational models forecast SYNOPTIC winds skillfully
  -> Gap is sub-3km terrain amplification. DIRECTLY validates the program thesis.
- Mass 2021: 444m WRF nest delayed wind decline = timing-bust in peer-reviewed record
- NE/ENE winds at ridge sites throughout late morning Nov 8

## Tubbs Fire — October 8-9 2017

**Paper:** Mass & Ovens BAMS

| Station | ID | Lat | Lon | Notes |
|---------|-----|-----|-----|-------|
| Hawkeye RAWS | TBD | ~45km NW Santa Rosa | TBD | Peak gusts 79 mph (69 kt) -- strongest NE gusts on record to 1993 |
| Santa Rosa RAWS | TBD | Santa Rosa area | TBD | Peak 68 mph (59 kt), 2nd strongest NE on record |

**Rejected station:** Atlas Peak -- tree-sheltering undersamples strong winds.
WARNING: same class of error as wrong coordinates. Sheltered stations corrupt labels.

**SHARED ANCHOR:** Hawkeye RAWS appears in BOTH Tubbs and Kincade. One station ID unlocks two hindcasts.

## Kincade Fire — October 23-27 2019

**Important mechanism note:** Kincade ignited under NORTHWEST winds (not classic NE Diablo).
Near John Kincade Road / Burned Mountain Road at The Geysers, Sonoma/Lake County line.
BC direction differs from Camp Fire / Tubbs even though all three are SYNOPTIC_TERRAIN.
Tests whether the BC method handles a different approach angle.

| Station | ID | Notes |
|---------|-----|-------|
| Hawkeye RAWS | TBD | Shared with Tubbs -- reliable long-record anchor |
| Pine Flat Road | TBD | 102 mph gust -- verify if RAWS or PSPS-era mesonet |
| Healdsburg Hills | TBD | 93 mph -- verify if RAWS or PSPS-era mesonet |

**Data quality note:** Pine Flat 102 mph and Healdsburg Hills 93 mph well-documented
but confirm in MesoWest whether these are long-record RAWS or PSPS-era sensors.
Kincade has thinner peer-reviewed meteorology than Camp or Tubbs.

## How to apply
- Always verify station IDs in MesoWest before scripting a fetch
- Tree-sheltering and wrong coordinates are the two known label-corruption failure modes
- Use literature validation targets (Colby Mtn, Saddleback, Hawkeye) as held-out stations
  the BC was never fit to -- these are the clean amplification tests
