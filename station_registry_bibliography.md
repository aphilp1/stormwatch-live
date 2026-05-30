# Station Registry & Source Bibliography — Camp / Tubbs / Kincade

Companion to `hindcast_event_library.md`. Pins RAWS station identities,
data-access routes, and peer-reviewed citations with verified wind values
usable as validation targets. All values attributed to a paper are that
paper's published numbers.

---

## DATA-ACCESS ROUTES (serve 2017-2019 hourly RAWS)

| Route | Notes |
|---|---|
| **Synoptic Timeseries API** | api.synopticdata.com/v2/stations/timeseries. Research token removes free-tier lookback cap. Best programmatic path. |
| **IEM archive** | mesonet.agron.iastate.edu. No 30-day gate. Fastest for Nov 2018. |
| **MesoWest (browse)** | mesowest.utah.edu. Confirm station existed on a date before scripting. |
| **WRCC / RAWS USA** | raws.dri.edu. Full archive; >30-day gated via email to wrcc@dri.edu. |
| **MADIS** | madis.ncep.noaa.gov. NOAA authoritative; heavier to use. |

Always pull BOTH sustained and gust -- sustained settles the gust-factor convention.

---

## EVENT 1 -- CAMP FIRE (2018-11-08)

### Station network (Brewer & Clements 2020; Mass et al. 2021 BAMS)
Five RAWS + two PG&E stations. Concow/Paradise/Pulga had NO dedicated RAWS in 2018.

| Station | Type | Role | Key data |
|---|---|---|---|
| Jarbo Gap | CAL FIRE RAWS 041214 | Primary anchor | Coords: 39.735944, -121.488944, 2535 ft, ridge SE aspect. Observed 8 Nov: sustained ~32 mph, gust 52 mph, peak ~4 AM PST. Gust factor = 52/32 = 1.625 |
| Colby Mountain | RAWS | Held-out target A | Literature: peak gust >=26 m/s (~58 mph), late-morning 8th |
| Saddleback | RAWS | Held-out target B | Literature: peak gust >=26 m/s (~58 mph) |
| Humbug Summit | RAWS | Held-out target C | Similar downslope conditions |
| Openshaw | RAWS | Network | In Mass et al. 2021 station set |
| Stirling City | PG&E wx | Network | Non-RAWS |
| Red Hill Lookout | PG&E wx | Network | Non-RAWS |

CRITICAL -- gust factor resolved from literature:
Jarbo sustained ~32 mph, gust 52 mph. Gust factor = 1.625.
The prior "within 4%" comparison (WN 49.7 vs gust 52) was WN-sustained vs
observed-GUST -- wrong convention. On sustained-to-sustained: WN 49.7 vs
observed 32 = 55% overshoot with the 35 mph BC. Requires re-run with
corrected coordinates (39.735944, -121.488944) before any ratio is trusted.

Sweep design (revised):
- Sweep A (BC label): Jarbo + Openshaw -> BC for outer trainer
- Sweep B (held-out): Jarbo only -> check Colby Mtn + Saddleback (never saw BC)

### Camp Fire citations
1. Mass et al. (2021) BAMS 102(1) -- "Gusts 10-20 kt sheltered to 50-60 kt exposed."
   Operational models forecast synoptic winds skillfully. 444-m WRF delayed wind
   decline (timing-bust in peer-reviewed record). Directly validates program thesis.
2. Brewer & Clements (2020) Atmosphere 11(1):47 -- 5-RAWS + 2-PG&E network.
   Jarbo sustained >12 m/s NE through the night. Doppler lidar deployed.
3. IBHS (2019) -- Fig. 1 has full Jarbo Gap gust+sustained curve,
   00 UTC 8 Nov to 12 UTC 9 Nov. Pull to validate RAWS fetch.

---

## EVENT 2 -- TUBBS FIRE (2017-10-08/09)

### Station network (Mass & Ovens 2019 BAMS)
| Station | Record | Key data |
|---|---|---|
| Hawkeye | Since ~1993, 24 yr | Max gust 79 mph (69 kt) -- strongest NE on record. ~45 km NW Santa Rosa. |
| Santa Rosa | Since 1991, 26 yr | Peak gust 68 mph (59 kt), 2nd-strongest NE on record. 11z 9 Oct: T 32.8C, RH 7%, gust 27.3 m/s |
| Atlas Peak | 6 yr | REJECTED -- tall trees shelter N/E, undersamples strong winds. Warning for own station selection. |

Hawkeye is a shared anchor across Tubbs AND Kincade. One station ID unlocks two hindcasts.

### Tubbs citations
1. Mass & Ovens (2019) BAMS 100(2) -- definitive paper. Hawkeye 79 mph / Santa Rosa 68 mph.
2. Nauslar, Abatzoglou & Marsh (2018) Fire 1(1):18 -- Atlas Peak rejection rationale.
3. Smith, Hatchett et al. (2018) Fire 1(2):25 -- Diablo-wind climatology. Foundational.

---

## EVENT 3 -- KINCADE FIRE (2019-10-23 to 10-27)

### Mechanism wrinkle: TWO wind regimes
Kincade ignited under NW winds (not classic NE Diablo) near John Kincade Rd /
Burned Mountain Rd at The Geysers. Then stronger NE Diablo drove the 27 Oct big run.
BC direction differs from Camp/Tubbs even though mechanism is SYNOPTIC_TERRAIN.

| Station | Key data |
|---|---|
| Pine Flat Road | 102 mph gust, 27 Oct -- confirm if long-record RAWS or PSPS-era sensor |
| Healdsburg Hills | 93 mph gust, 27 Oct -- same caveat |
| Hawkeye | Shared anchor; reliable long-record |
| NWS peak | 76 mph early run, 24 Oct |

### Kincade citations
1. CIMSS/SSEC blog 2019 -- Pine Flat 102 mph / Healdsburg Hills 93 mph
2. NASA Earth Observatory 2019 -- 96 mph gusts, GEOS-5 animation
3. Thinner peer-reviewed record than Camp/Tubbs

---

## CROSS-EVENT NOTES

- Both BAMS papers confirm synoptic winds were forecast skillfully. The gap is
  sub-3km terrain amplification. This IS the program thesis, confirmed in literature.
- Exposed ridge vs sheltered valley split is in every paper -- your amplification
  ratio quantifies what the literature keeps describing qualitatively.
- All headline validation numbers are GUSTS. WN outputs sustained. Pin gust factor
  before comparing. Jarbo = 1.625. Physical range 1.3-1.7 confirmed.
- Tree-sheltering corrupts labels (Atlas Peak rejection) -- same failure mode as
  wrong coordinates. Both errors produce low readings that misrepresent terrain signal.
