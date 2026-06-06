# Stormwatch — DART & External Resources to Track

**Created 2026-06-01.** A dedicated, self-contained list of external methods, people, code,
and baselines worth pursuing — pulled out of `da_ideas_integration_note.md` so it's easy to
find later. NONE of this gates current work; it's the "go look at this when you reach the
output/confidence stage, or when positioning the project" list. The build (PHASE A
observations task → dataset → row counts) comes first; see `STORMWATCH_GOAL_AND_DATASET.md`.

---

## 1. DART / QCEFF / BNRH — the bounded-distribution methods source

**What it is:** DART (Data Assimilation Research Testbed), NCAR/UCAR's community ensemble-DA
system, maintained by the Data Assimilation Research Section (DAReS). For Stormwatch, DART is
the **output-distribution methods source** — how to represent honest, bounded, non-Gaussian
uncertainty for the wind-speed channel. It is NOT a framework to run our pipeline inside (it
supports GCMs like CAM/WRF/MPAS and the Lorenz toy models, not a terrain-scale diagnostic
wind tool).

**The method we want (when we build the confidence/output stage):**
- **BNRH — Bounded Normal Rank Histogram** with quantile regression, part of the **QCEFF**
  framework (Jeff Anderson). Demonstrated properties that are exactly what the wind-speed
  channel needs:
  - unbiased,
  - can go to all zeros,
  - produces NO negative values (respects the physical lower bound at calm),
  - beats traditional Gaussian filters on RMSE especially in the low/near-zero regime
    (the analog of near-calm wind).
- Use a BNRH-style bounded representation for the speed-channel output distribution so
  confidence intervals are asymmetric near calm and never spill below zero. The dangerous
  tail for fire is the upside, so honest asymmetric uncertainty matters.
- It's REAL CODE with tutorials, not just papers — DART is downloadable and laptop-runnable
  (no-MPI build for conceptual models).

**Why it fits the project philosophy:** QCEFF is about moving PAST the Gaussian assumption —
the same reason Stormwatch uses a feature-based predictor rather than a covariance. See the
SIAM piece "Removing Kalman from Ensemble Kalman Filtering."

**Links:**
- DART home: https://dart.ucar.edu  (docs, tutorials, source)
- Get DART: https://dart.ucar.edu/software
- Docs: https://docs.dart.ucar.edu
- Tutorials: https://dart.ucar.edu/tutorials
- MOST RELEVANT PAGE — non-Gaussian algorithm development:
  https://dart.ucar.edu/research/non-gaussian-algorithm-development
  (exactly the bounded / non-Gaussian problem domain)

**Reference paper:** Anderson et al., *Mon. Wea. Rev.* 152, 2111–2127 (mixed distributions;
variables with a zero-spike + continuous part — precip, tracers, fire sources).

---

## 2. People to track

- **Jeff Anderson (NCAR / UCAR; DART, QCEFF).** The closest match in the DA world to our
  output problem: honest non-Gaussian / bounded uncertainty for geophysical variables.
  2022 AGU Fellow. Items: QCEFF filters, BNRH + quantile regression, mixed distributions.
- **Ian Grooms.** Novel non-Gaussian algorithm development, featured on the DART
  non-Gaussian page above. Track alongside Anderson.

---

## 3. Radar-retrieved PBL depth — the Stouffer / Penn State CBL program

**Added 2026-06-05** after the CADRE-EPIC DA workshop (Braedon Stouffer presenting). A direct
**physical retrieval** of a lower-atmosphere observable — NOT a learned prior, NOT the
falsified BC correction. It estimates daytime convective boundary layer (CBL) depth from
dual-pol WSR-88D Z_DR (Bragg-scatter minimum at CBL top), every 5–10 min, network-wide.

**Why it's on this list:** a candidate "better-chosen observation" (lever b) for the
better-WindNinja-starting-point work — but with a sharp scope. **It is a Great Plains tool,
not a complex-terrain one.** The dividing line maps almost exactly onto our regime split:

- STRONG where: daytime, dry, flat, big growing CBL → **Great Plains dry-windy fire weather.**
  Validation/demo radars that work cleanly are continental Plains (KAMA Amarillo, KGRK Fort
  Worth, plus KLRX Elko, KYUX Yuma). RMSE ~148 m vs Windsondes (below wind-profiler range,
  near expert agreement). Authors name wildfire behavior as a target application.
- WEAK / fails where: (1) **complex terrain** — the paper explicitly states mountains
  interrupt the beam, creating missing azimuths that complicate CBL-top ID; (2) **nocturnal /
  stable BL** — the method tracks the sunrise-to-sunset *growing* CBL, so terrain-driven
  nocturnal downslope events have no target; (3) **rain** — raindrops kill the Z_DR signal
  (25% of their QVPs dropped for rain).
- => For our **mountain-West nocturnal terrain-wind niche** (Camp/Kincade), it degrades on all
  three counts at once. It does NOT compete with the terrain niche; it complements it in a
  different region. **Caveat for the project: our 12-event database currently has NO Great
  Plains regime in it, so it can't yet test where this observable is strongest.** If radar-PBLH
  is ever to matter here, a Plains dry-windy fire-wind event would need to enter the set.

**The papers (Penn State / Comer, Stouffer, Stensrud, Zhang, Kumjian):**
- **Method (FREE full text):** Comer, Stouffer, Stensrud, Zhang & Kumjian, 2024, "An Automated
  Approach to Estimating Convective Boundary Layer Depth from Dual-Polarization WSR-88D Radar
  Observations," *J. Atmos. Oceanic Technol.* 41, 767–780, doi:10.1175/JTECH-D-23-0166.1.
  Free at https://par.nsf.gov/servlets/purl/10565166 . Introduces the **DVar** variable (Z_DR
  combined with azimuthal variance) for morning CBL-top ID; two trackers (DVar minimum +
  continuous wavelet transform on Z_DR) combined by inverse-variance weighting.
- **Predecessor:** Banghoff, Stensrud & Kumjian, 2018, "Convective Boundary Layer Depth
  Estimation from S-Band Dual-Polarization Radar," *JTECH* 35, 1723–1733. (Manual estimate,
  central OK, r=0.90, RMSE 254 m vs rawinsondes.)
- **Climatology:** Stensrud, Comer, Stouffer et al., "Synoptic and Mesoscale Variability in
  Convective Boundary Layer Depth Observations from Dual-Polarization WSR-88D Radars." 48
  radars, 2014 & 2022; CONUS mean monthly CBL 632 m (Dec) → 1606 m (Jun). Plus companion
  Stouffer & Stensrud, "Estimates of Entrainment Zone Depth Across the United States…"
- **Model-evaluation (closest to our departure-study design):** Stouffer & Stensrud,
  "Evaluating Planetary Boundary Layer and Land Surface Models via Dual-Polarization WSR-88D
  and Flux Tower Observations." MYNN-EDMF PBL-depth forecasts vs WSR-88D, 2022, via RAP/WRF-ARW.
  This is literally "diagnose where the model's PBL depth departs from a radar-retrieved truth."
- **Assimilation (parents of the derecho talk):** Stensrud, Comer, Stouffer et al.,
  "Assimilating Novel Boundary Layer Observations from Dual-Polarization Radars to Improve
  Lower-Tropospheric Moisture and Torrential Rainfall Forecasts" (first comprehensive PBLH-DA
  study; E. Kentucky 27–28 Jul 2022 flash flood). And Eure, Y. Zhang, Stensrud, F. Zhang,
  Greybush et al., 2023, "Simultaneous Assimilation of PBL Observations from Radar and All-Sky
  Satellite… for Convection Initiation," *MWR* 151(3), MWR-D-22-0188.1.

**Open question for Braedon (if contact continues):** has the DVar retrieval been validated in
high-relief, dry-slope fire-weather terrain, or is it fundamentally a Plains-and-East
capability? The paper concedes the beam-blockage mechanism; what's unknown is whether a
workaround is in progress.

---

## 4. Fire-wind landscape — where Stormwatch sits

**BASELINE TO BEAT — HDW (Hot-Dry-Windy Index), USDA Forest Service**
(Srock, Charney, Potter, Goodrick). The incumbent operational tool for anticipating
erratic/dangerous fire-weather days from temperature, moisture, wind. Works with standard
NWP, any terrain/fuel. USES RAW MODEL WIND — does nothing about terrain-resolution error.
=> The benchmark question for any Stormwatch result is: "does this add skill over HDW?"

**Coupled fire-atmosphere models (CONTEXT — and the OUT-OF-SCOPE boundary)**
- WRF-Fire; Community Fire Behavior Model (CFBM) integrated into NOAA UFS SRW v3.0.0 (2025);
  NSF NCAR 3km→100m downscaling. These resolve winds in complex terrain AND the fire's own
  plume feedback.
- Their 3km→100m downscaling is the same terrain-gap WindNinja targets — but these are the
  PLUME-DRIVEN / coupled path. Stormwatch is WIND-DRIVEN only; plume-driven (fire generating
  its own winds) is EXPLICITLY OUT OF SCOPE.

**NOAA UFS fire-weather** — subseasonal fire metrics; SRW dynamic downscaling improves wind
variability. Same terrain-downscaling theme, different timescale. Context, not a dependency.

**Predictability caveat** (extreme-fire synthesis lit): coupled-model skill drops with lead
time, severely at fine scales — the wall that motivates focusing on WIND and on knowing where
the forecast is unreliable, rather than chasing perfect fine-scale prediction.

---

## 5. Long-term / aspirational (parked, post-signal)

- **Score-based DA / terrain-conditioned learned prior** (Rozet & Louppe 2023/24; Manshausen
  et al. 2024). A terrain-conditioned learned prior over complex topography is unclaimed
  ground; the bust dataset is its foundation. CPU groundwork first (Herbie→Zarr, RAWS
  gridding), validate locally, THEN rent a GPU (host has none; reduced first pass ~tens of
  dollars). NVIDIA PhysicsNeMo `examples/weather/regen/` is a forkable template. Watch-and-
  prototype AFTER the diagnostic signal is found and confirmed.

  **Confirmed specifics (from the paper, 2026-06-05 — arXiv 2406.16947):**
  - Method = **SDA** (score-based data assimilation, Rozet & Louppe 2024); unconditional
    diffusion prior trained via the **EDM framework** (Karras 2022) on ~2.5M HRRR analysis
    snapshots (10 m u/v winds + precip), Oklahoma-sized box, 3 km.
  - Result: 40 stations → ~10% lower RMSE than HRRR on held-out stations — but needed
    ~15-member ensemble; a single member only matched HRRR, and it took ~25 stations before
    one SDA state overtook HRRR.
  - **The caution that matters for us:** authors find the SDA ensembles UNDER-DISPERSIVE and
    state plainly the error reduction "could be simple variance reduction" (possible mode
    collapse in the diffusion prior). This is the regression-to-the-mean-masquerading-as-skill
    artifact our separability gate (rule #0) exists to catch — keep it in the back pocket
    whenever evaluating ANY learned method against the departures.
  - **Provenance for our `hrrr_era` tag:** trained 2018–2021, val 2022, test 2017; authors
    note HRRR methodology updates caused nonstationarities prior to 2018 that affected UPPER
    levels but NOT the surface channels they used. (Our BC work reaches 700/850 hPa, where it
    WOULD bite.)
  - **Unclaimed ground confirmed:** flat Oklahoma, 3 variables, no terrain; authors explicitly
    leave topography to future work. A terrain-conditioned version is the open lane.
  - **Learned-physics proof-of-concept:** leaving out the meridional wind channel entirely,
    the model reconstructs it from the others and recovers gust fronts — evidence a learned
    prior encodes real multivariate physics.
  - **Compute (validates the "tens of dollars" estimate):** training <8 h on 16 A100s; single
    inference 10 s on one RTX 6000 Ada. Code: PhysicsNeMo `examples/weather/regen/`;
    archive Zenodo DOI 10.5281/zenodo.15083507.

---

## Where this is also referenced
These items also live, in context, in `da_ideas_integration_note.md` (future-capability and
People/Work-to-Track sections). This file is the standalone quick-reference; that file has
the surrounding design reasoning.
