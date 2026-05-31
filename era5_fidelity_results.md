# ERA5 fidelity check vs independent Wyoming soundings (2026-05-30)

**SOLID — ERA5 is a trusted synoptic BC source (NorCal + SoCal Diablo/Santa Ana).**
Validated ERA5 700 hPa wind against Wyoming wsgi soundings (src=FM35) at exact UTC
launch times, vec_avg, m/s->mph:
- Tubbs / OAK, 8 Oct (pre-ignition launches): 00z ERA5 20.2@297 vs obs 23.0@300
  (-2.8 mph / 3deg); 12z 27.1@332 vs 24.2@320 (+3.0 / 12deg). Grid 3 km from station.
- Thomas / VBG, 4 Dec (box extended S=34N to cover VBG): 00z 34.4@305 vs 33.3@310
  (+1.1 / 5deg); 12z 24.2@321 vs 27.7@310 (-3.5 / 11deg). Grid 6 km from station.
Direction (the high-leverage BC variable) agrees within ~12deg in all four. ERA5
earns "trusted BC source" for these synoptic cases.

**SOLID — BC-level finding: 700 hPa is above the inversion for sub-inversion gap
flow.** Camp / REV (real Wyoming pull), both launch times: 700 hPa (~3100 m) sits
ABOVE the Reno inversion base (2307 m at 00z, 1516 m at 12z) -> samples
free-atmosphere flow, NOT the NE gap flow. 850 hPa agreement is tight (12z: 1deg
direction). Operational rule (refines protocol §2.4): for sub-inversion gap-flow
events, the BC level must be 850 hPa / sub-lid, NOT 700 hPa.

**WITHDRAWN (method catch).** The earlier "ERA5 direction reversed at REV 12z, 202deg
off" was caused by a HAND-TRANSCRIBED IEM observed value, not ERA5. With the verified
Wyoming sounding, ERA5 and obs AGREE at 700 hPa 12z (~63 vs ~60deg, 3deg apart).
Lesson: observed values must be READ from wyoming_soundings.json, never typed in.
Convention added: no hand-entered obs in any comparison.

**Noted, not a finding.** Camp 12z 700 hPa speed +6.7 mph (direction agrees within
3deg) — soft-threshold trip from a 28 km grid cell vs point sonde; not a divergence.

**Open.** Kincade fidelity not run — only valid sounding (OAK 27 Oct) is outside the
23-25 Oct ERA5 window. Next: pull Kincade 26-28 Oct ERA5 window, then check vs OAK 27 Oct.
