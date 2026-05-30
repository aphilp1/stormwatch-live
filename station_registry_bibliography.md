# Station Registry & Source Bibliography — Camp / Tubbs / Kincade

Companion to `hindcast_event_library.md`. This pins the **RAWS station identities**
(with the literature's own station selections), the **data-access routes** that
actually serve 2017–2019, and the **peer-reviewed citations** with verified wind
values you can use as validation targets. Everything here is sourced; values
attributed to a paper are that paper's published numbers, not estimates.

> **A note on the original request framing.** No one — human or AI — can hand you a
> WRCC "access code"; those are issued by the data provider to a named researcher.
> The 30-day wall is a property of WRCC's *public web UI* and Synoptic's *free tier*,
> not of the data. The real unlocks are below (research-tier Synoptic token; IEM
> archive; a genuine email to wrcc@dri.edu). Frame outreach as a research-data
> request, not a code request.

---

## DATA-ACCESS ROUTES (serve 2017–2019 hourly RAWS)

| Route | URL | Serves these years? | Notes |
|---|---|---|---|
| **Synoptic Timeseries API** | api.synopticdata.com/v2/stations/timeseries | YES with research token | Your `dec17_final.py` already calls this. Free tier caps lookback; **apply for a free academic/research token** to remove it. Best programmatic path. |
| **IEM archive** | mesonet.agron.iastate.edu | YES | Already used in your code for ASOS. No 30-day gate. Likely fastest for Nov 2018. |
| **MesoWest (browse)** | mesowest.utah.edu | YES | Same data, browsable — use to confirm a station existed on a given date before scripting. |
| **WRCC / RAWS USA** | raws.dri.edu | YES (full archive) | >30-day instant download gated; email **wrcc@dri.edu** describing the research to get past it. |
| **MADIS** | madis.ncep.noaa.gov | YES | NOAA archive; heavier to use but authoritative. |

**Pull BOTH sustained and gust** for every station — sustained settles the
gust-factor convention; gust feeds the amplification-ratio test. Pulling gust-only
forces a second fetch.

---

## EVENT 1 — CAMP FIRE (2018-11-08)

### Station network — what the literature actually used
Cao & Wang / Brewer & Clements (Atmosphere 2020) and Mass et al. (BAMS 2021) used
**five RAWS + two PG&E stations**. This is a bigger, better network than the 4-station
set in the current pipeline — several are independent ridge sites usable as
**held-out amplification targets**.

| Station | Type | Role | Notes for the audit |
|---|---|---|---|
| **Jarbo Gap** | CAL FIRE RAWS **041214** | Primary / anchor | NIFC coords 39.735944, -121.488944, ~2535 ft, ridge, SE aspect. Observed 8 Nov: sustained ~32 mph, gust 52 mph, peak ~4 AM PST. **BURNOVER WARNING:** clip data before ~14:00 UTC Nov 9 (06:00 PST) — paper Fig 7A marks as "questionable" after that point (soil temps >40C, station likely burned ~08:00 PST Nov 9). |
| **Colby Mountain** | RAWS | **Held-out A** | Confirmed: gusts **≥26 m/s (~58 mph)**, sustained **≥10 m/s (~22 mph)**. Strong ridge amplification target. Coords: pull from paper Table 1 PDF. |
| **Saddleback** | RAWS | **Held-out B** | Confirmed: gusts **≥26 m/s (~58 mph)**, sustained **≥10 m/s (~22 mph)**. Strong ridge amplification target. Coords: pull from paper Table 1 PDF. |
| **Humbug Mountain** | RAWS | **Low-end control** | Paper name: "Humbug Mountain" (also "Humbug Summit" in text — ambiguous). **WEAK site:** gusts ~14 m/s (~31 mph), sustained ~5 m/s (~11 mph). Useful as low-amplification control, NOT a strong target. |
| **Openshaw** | RAWS | Network | In paper network. Large direction error in WRF validation (Openshaw was the worst direction site, 54°→35° when dropped). Verify coords before using. |
| **Stirling City** | PG&E wx | **UNRELIABLE** | Paper documents erratic behavior — two periods of weak SE flow, possibly under a rotor. DROP from validation. Same class as Atlas Peak (Tubbs). |
| **Red Hill Lookout** | PG&E wx | Network | Non-RAWS; PG&E mesonet. |

**Concow / Paradise / Pulga reality check:** these *towns* likely had **no dedicated
RAWS** in 2018 — Jarbo Gap is the RAWS that *covers* the Concow/Yankee Hill area.
So the "held-out stations near Concow/Paradise/Pulga" most likely resolve to
**Colby Mountain, Saddleback, Humbug, Openshaw**, not stations at those town names.
This matters: the Concow +92% can't be validated at a Concow station that doesn't
exist — validate the *ridge-amplification physics* at Colby/Saddleback instead,
which the literature already measured at ~58 mph.

### Camp Fire citations
1. **Mass, Ovens, et al. (2021)** — "The Synoptic and Mesoscale Evolution Accompanying
   the 2018 Camp Fire of Northern California," *BAMS* 102(1).
   journals.ametsoc.org/view/journals/bams/102/1/BAMS-D-20-0124.1.xml
   - Key result: downslope NE winds descended the W. Sierra slopes, peaked ~sunrise 8 Nov.
     **Gusts 10–20 kt at sheltered sites to 50–60 kt at exposed mid/upper-slope sites.**
     Winds were *not* climatologically exceptional; low-level temps cooler than normal.
   - **Directly relevant to your speed-bias finding:** "both the synoptic evolution and
     low-level winds skillfully forecast by operational models" — and the 444-m WRF nest
     gave the best NE-wind forecast but *delayed the wind decline*. A timing-bust signature.
2. **Brewer & Clements (2020)** — "The 2018 Camp Fire: Meteorological Analysis Using
   In Situ Observations and Numerical Simulations," *Atmosphere* 11(1):47.
   mdpi.com/2073-4433/11/1/47  (open access; PDF: /pdf, XML: /xml)
   - The 5-RAWS + 2-PG&E network above; mobile Doppler lidar deployed 8 Nov.
   - Jarbo Gap sustained >12 m/s NE through the night; gap-flow mechanism confirmed.
     WRF cross-sections: subcritical → supercritical down the lee, hydraulic jumps.
     Strongest winds near the crest; 10-20 m/s just above surface near Concow/Paradise.
   - **Model bias:** WRF had a HIGH bias vs observations (over-predicted), especially
     at low wind speeds -- most points above 1:1 line. RMSE 3.34 m/s speed, 54° direction.
     After dropping Stirling City: 2.78 m/s. After dropping Openshaw: 35° direction.
     Sign of bias is station- and speed-dependent -- not a domain constant.
   - **Table 1** has verified station coords + elevations -- NOT readable from HTML.
     Use PDF or XML version to get coordinates. Apply elevation cross-check on each.
3. **IBHS (2019)** — "Post-Event Investigation: California Wildfires of 2017 and 2018."
   ibhs.org/wp-content/uploads/member_docs/camp-fire-report_ibhs-1.pdf
   - Has the **Jarbo Gap hourly gust+sustained time series, 00 UTC 8 Nov – 12 UTC 9 Nov**
     (their Fig. 1) — a published curve to validate your RAWS pull against.
4. **Cliff Mass blog (2018-11-20)** — Jarbo climatology context (NE ≥30 mph occurred
   508× in 15 yr). Useful for the "not exceptional" framing; not peer-reviewed.

---

## EVENT 2 — TUBBS FIRE (2017-10-08/09)  [North Bay "Wine Country" firestorm]

### Station network — the two the literature standardized on
| Station | Type | Role | Verified observations |
|---|---|---|---|
| **Hawkeye** | RAWS (record from ~1993, 24-yr) | Primary ridge | **Max gust 79 mph (69 kt)** 8–9 Oct — strongest NE gusts on record AND strongest from any direction (Mass & Ovens). ~45 km NW of Santa Rosa. |
| **Santa Rosa** | RAWS (record from 1991, 26-yr) | Valley/lee | **Peak gust 68 mph (59 kt)**, 2nd-strongest NE-quadrant on record. At 11 UTC 9 Oct: T 32.8 °C, RH 7%, gust 27.3 m/s, FFWI 78. |
| **Atlas Peak** | RAWS | **REJECTED by lit** | Tall trees shelter N/E → undersamples strong winds; only 6-yr record. **A direct warning for your own station selection.** |

> Mass & Ovens chose Hawkeye + Santa Rosa for proximity to the Tubbs/Nuns/Pocket
> fires, lee-slope position for NE downslope flow, and long records. Use the same two.

### Tubbs citations
1. **Mass & Ovens (2019)** — "The Northern California Wildfires of 8–9 October 2017:
   The Role of a Major Downslope Wind Event," *BAMS* 100(2).
   journals.ametsoc.org/view/journals/bams/100/2/bams-d-18-0037.1.xml
   - The definitive synoptic/mesoscale paper. Hawkeye 79 mph / Santa Rosa 68 mph above.
     Classic offshore "Diablo" pattern: building SLP over the Intermountain West + coastal trough.
2. **Nauslar, Abatzoglou & Marsh (2018)** — "The 2017 North Bay and Southern California
   Fires: A Case Study," *Fire* 1(1):18. mdpi.com/2571-6255/1/1/18
   - Station-selection rationale (incl. Atlas Peak rejection), FFWI/FM10 values,
     downslope standing-wave structure from high-res mesoscale model.
3. **Smith, Hatchett, et al. (2018)** — "A Surface Observation Based Climatology of
   Diablo-Like Winds in California's Wine Country and Western Sierra Nevada,"
   *Fire* 1(2):25. mdpi.com/2571-6255/1/2/25
   - **The Diablo-wind climatology paper** — defines the phenomenon, Hawkeye 22 m/s
     (50 mph) with RH<15% at midnight. Foundational for the mechanism definition.
4. **SFSU thesis (Geosciences)** — tornado.sfsu.edu/.../Thesis_Final.html
   - Hawkeye 35 m/s (78 mph) 11pm 8 Oct; hydraulic-jump schematic; links to the
     1964/1970 Hanly Fire Diablo analog (Monteverdi 1973).

---

## EVENT 3 — KINCADE FIRE (2019-10-23 to 10-27)

### Station network & the mechanism wrinkle
**Important:** Kincade ignited under **NW** winds, not the classic NE Diablo — the BC
direction differs from Camp/Tubbs. Then a stronger NE Diablo event drove the big
27 Oct run. Two distinct wind regimes in one fire.

| Station / sensor | Role | Verified observations |
|---|---|---|
| **Pine Flat Road** (PSPS/mesonet sensor) | Peak-wind site | **102 mph gust, 27 Oct** (CIMSS/SSEC). The headline number. |
| **Healdsburg Hills** | Peak-wind site | **93 mph gust, 27 Oct.** |
| **Hawkeye** | RAWS | Shared anchor with Tubbs; elevated gusts during event (SSEC). |
| NWS-recorded peak | — | **76 mph** (early run, 24 Oct, Press Democrat/CNN). |

> "Pine Flat Road" and "Healdsburg Hills" may be PG&E/PSPS-era mesonet sensors rather
> than long-record RAWS — confirm station type/coords in MesoWest before treating them
> as RAWS. Hawkeye is the reliable long-record RAWS anchor here.

### Kincade citations
- Kincade has **less formal peer-reviewed meteorology** than Camp/Tubbs (more recent,
  PSPS-dominated). Primary sources are agency/satellite analyses:
1. **CIMSS Satellite Blog / SSEC (2019)** — cimss.ssec.wisc.edu/satellite-blog/page/481
   - Pine Flat 102 mph / Healdsburg Hills 93 mph, 27 Oct; GOES-17 1-min imagery of the
     ~10-mi SW run toward Hwy 101 as Diablo winds increased overnight.
2. **NASA Earth Observatory (2019)** — earthobservatory.nasa.gov/images/145793
   - 96 mph gusts 27 Oct; GEOS-5 wind animation; Diablo mechanism (Great Basin origin,
     compression/heating down the ranges).
3. **Press Democrat day-by-day** — pressdemocrat.com (NWS 76 mph; NW 60 mph at ignition).
4. (Check for newer journal treatments — Kincade sometimes appears in PSPS/utility and
   multi-event Diablo studies rather than a dedicated case-study paper.)

---

## FOUNDATIONAL / CROSS-CUTTING LITERATURE (the Diablo/downslope mechanism)

These define the SYNOPTIC_TERRAIN mechanism your whole approach targets — cite for
the *why*, not a specific event:

1. **Smith, Hatchett et al. (2018)** *Fire* 1(2):25 — Diablo-wind climatology (above).
2. **Mass & Ovens (2019)** *BAMS* — downslope-windstorm dynamics for North Bay (above).
3. **Mass et al. (2021)** *BAMS* — Camp Fire downslope/gap-wind dynamics (above).
4. **Monteverdi (1973)** — early Diablo-wind synoptic analysis (1970 Hanly Fire pattern);
   historical anchor, cited by the SFSU thesis.
5. **Brewer & Clements (2020)** *Atmosphere* — in-situ + WRF downslope analysis (above).
6. (For mountain-wave/downslope theory generally: Durran's downslope-windstorm work and
   the hydraulic-jump framework referenced in the Tubbs sources — pull these for the
   physical mechanism section of any writeup.)

---

## CROSS-EVENT NOTES FOR THE PIPELINE

- **Hawkeye RAWS is a shared anchor** across Tubbs AND Kincade — same station, two
  events, long record. High-value: one station identity unlocks two hindcasts.
- **The "exposed ridge vs sheltered valley" split is in every paper.** Camp (10–20 kt
  sheltered vs 50–60 kt exposed), Tubbs (Atlas Peak rejected for sheltering), Kincade
  (Pine Flat ridge 102 mph). Your amplification ratio is the *quantified* version of
  this qualitative split the literature keeps describing — that's the contribution.
- **Operational models already forecast the synoptic winds "skillfully" (both BAMS
  papers say so).** That sharpens your thesis: the gap is NOT synoptic-scale wind —
  it's the **3km→sub-1km terrain amplification** HRRR can't resolve. The literature
  supports exactly the niche the BC→WindNinja pipeline fills.
- **Validation targets you now have, with citations:** Camp Colby/Saddleback ~58 mph;
  Camp Jarbo 52 mph gust; Tubbs Hawkeye 79 mph / Santa Rosa 68 mph; Kincade Pine Flat
  102 mph / Healdsburg Hills 93 mph. These are published numbers to score WindNinja
  against — independent of any BC you fit.
- **Gust-factor caution recurs:** every headline number above is a GUST. WindNinja
  outputs sustained. Pin the gust factor consistently before comparing, per the audit.
  **RESOLVED for Jarbo Gap (2026-05-30):** Brewer & Clements / IBHS confirm sustained
  ~32 mph, gust 52 mph on 8 Nov → gust factor = **1.625**. The prior "within 4%"
  comparison (WN 49.7 vs 52 mph) was WN-sustained vs observed-GUST — wrong convention.
  Correct sustained-to-sustained: WN 49.7 vs 32 mph = 55% overshoot. Set
  `GUST_FACTOR = 1.625` in bc_label_generator.py. Re-run WindNinja at corrected
  Jarbo coords (39.735944, -121.488944) before trusting any amplification ratio.
