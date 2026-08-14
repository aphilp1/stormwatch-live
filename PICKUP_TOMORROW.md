# StormWatch — Resume Anchor

**Active again 2026-07-28.** Cue to restart: Alex types
**"resume stormwatch"** → read this file. Master overview = `STORMWATCH_PROJECT_MAP.md`.
Full ledger for 2026-07-28 session in `Storm_info/STORMWATCH_MASTER_STATUS.md` top entry
(lightning/fire-weather layers shipped, 2 real bugs found+fixed via stress test, gaps
below still open).

## 🗒 BACKLOG (not started, no urgency, pick up when asked)
- **48-Hour Fire Forecast tab** — parked on branch `fire48-wip` (pushed, never merged to
  master, not on the public site). Alex: "needs work." Not scoped yet — ask what's wrong
  with it / what "done" looks like before touching it.

## ▶ 2026-08-01 session — 2 live bugs found by Alex, fixed + pushed; smoke-test infra added
Alex reported Smoke Forecast (NAQFC) broken and Animated Wind Flow arrows invisible on the
**public site** (not localhost). Both were real, live, already-shipped bugs from the
2026-07-28 session, sitting undetected for days:
1. `getNaqfcTimeStr()` mixed local-time setters (`setHours`/`setMinutes`) with a UTC hour
   value and UTC serialization — on Alex's UTC-6 machine this requested a WMS TIME ~6h in
   the future that NOAA hadn't published yet → blank tiles. Fixed: `setUTCHours`/
   `setUTCMinutes`. Only reproduces off-UTC, which is why it shipped unnoticed.
2. Animated Wind Flow's calm-wind color (`#7d93ab`) was a washed-out slate blue nearly
   invisible against the light basemap at leaflet-velocity's low per-frame trail alpha —
   invisible specifically when winds are light, i.e. most of the country most of the time.
   Fixed: more saturated blue + thicker lineWidth (1.9→2.6).
Both commits: `c5d79b1`, verified in-browser on localhost (exact HEAD + fix, confirmed no
other diff) before push. Live now — remind Alex to hard-refresh.

**New: automated bug-catching infra** (Alex asked "figure out a way to catch bugs" after
this session) — see `Storm_info/BUG_CATCHING.md` for full design. Summary: (a) a static
lint (`Storm_info/lint_utc_mixing.js`) that fails CI if new code mixes local-time Date
setters with UTC getters/output — would have caught bug #1 above; (b) a Playwright smoke
test (`Storm_info/smoketest_layers.js`) that loads the app in a UTC-6 browser context,
clicks every layer toggle, and fails on any console error — catches JS-crash-class
regressions (e.g. the 2026-07-08 Montana Mesonet null-sensor crash) but does NOT catch
silent-wrong-output bugs like #1/#2 above (no exception was thrown by either — the lint
rule is what catches #1; #2's contrast issue isn't caught by either, it needs a human/
visual check — noted as a known gap). Wired into `.github/workflows/smoke-test.yml`,
runs on every push to master that touches `weather-alerts.html`.

## ▶ 2026-07-30 session — "click on alert layer does nothing" — NOT a code bug, verified fine

Alex reported: on the live public site, Layers tab, with an alert layer (e.g.
Other/Advisory) toggled on, clicking a lit-up polygon did nothing — cursor just panned
like a hand-drag, no info card. Investigated on the live site (HEAD `c51fb58`, no code
changes made this session):
- Reproduced Alex's exact toggle state (master alerts off, Other/Advisory on, same
  "~250 active" count, same MT polygon) — click opened the full alert detail panel
  correctly every time (3 repeats, fresh page load, no console errors).
- Root cause of what Alex saw: his screenshot showed a **"Claude started debugging
  this browser"** banner — a stray Chrome DevTools (CDP) debugging session attached to
  that tab, which can swallow/alter real mouse-click dispatch so a click behaves like a
  drag-start. Alex clicked Cancel on that banner + hard-refreshed → confirmed working
  on his end too.
- **No fix was needed, nothing was changed or pushed.** `addAlertPolygon`'s click
  handler (`weather-alerts.html` ~line 3111-3134, calls `selectAlert`→`showDetail`) is
  intact and correct. If this "clicks just pan" report recurs, check for a stray
  debugger-attached banner on the tab FIRST before assuming a code regression.
- Separately noted but NOT touched (per Alex's explicit instruction — public-site bug
  only, not dev work): there is still ~930 lines of **uncommitted, unpushed** local-only
  work in `weather-alerts.html` (a "48-Hour Fire Forecast" tab, `tab-fire48`,
  `activate48FireMode()`), last touched 2026-07-29, not logged anywhere before this
  session. It does NOT affect the live site (live site = HEAD `c51fb58`, this diff was
  never committed). On next resume, ask Alex what this is / whether to finish, discard,
  or keep parked before touching it.

## ▶ 2026-07-28 session — Lightning/fire-weather layers + public-site stress test

**Shipped (pushed, verify HEAD matches):** loading-overlay fix (overlay no longer blocks
map for 2-3 min on high-alert days), Lightning Strike Density (observed, NOAA real-time),
Dry Thunderstorm Outlook (SPC Day 1-8, real), Critical Fire Weather/Wind-RH Outlook (SPC
Day 3-8, real), Base Map crash fix (bringToFront bug, all 6 base maps). All moved into
Wildland Fire group per Alex's request.

**✅ VERIFIED on the LIVE public site 2026-07-29** (HEAD `c51fb58`, real click-through,
not localhost):
1. Lightning Strike Density — real colored strike-density blobs rendered (yellow/orange
   dots across CONUS + Gulf), sidebar showed live UTC window "00:45Z–01:00Z". ✅
2. Dry Thunderstorm Outlook + Critical Fire Weather — cycled D1/D4/D6 (dry t-storm) and
   D3/D7 (critical fire wx); consistently "none issued" (plausible, no active outlook
   that hour) with zero console errors either layer/day. ✅
3. Base Map — clicked through Dark/Satellite/Topo/USGS Hillshade (+Light/USGS Topo-3DEP
   present but not individually clicked); all rendered correctly, zero console errors on
   any switch. Reset to Light after. ✅
4. Loading spinner — page fully loaded (alerts + map) within 6s of navigation, no stuck
   overlay. ✅

All 4 resume-checklist items closed. Gaps below still open, nothing else blocking.

**Gaps flagged during stress test, NOT yet covered — pick up next:**
- Mobile/responsive layout at narrow widths (untested this round).
- Dark mode / contrast re-check (last session's 491-instance bug wasn't re-verified here).
- Accessibility (keyboard nav, screen reader).
- Fire Winds hindcast library — only 2 of 12 event cards were opened.
- WindNinja Terrain Wind probe's real click-to-probe behavior (needs local MCP backend).
- Cross-browser (only tested in Chrome).
- Extended-session/memory-leak behavior; GitHub Pages deploy quirks (.nojekyll/cache).

---

## Earlier session (2026-07-27, kept for history)

**Active again 2026-07-27** (was parked 2026-07-19). State at 2026-07-27 close: HEAD
`4766902` + bot commits, all pushed, site LIVE and verified (screenshot-confirmed on the
actual public URL, not just localhost).

**⚠️ Read on resume: user called this session "horrible."** Full honest ledger in
`Storm_info/STORMWATCH_MASTER_STATUS.md` top entry and memory
`feedback-verify-against-real-target-not-proxy`. Short version: good feature work
(New Ignitions, real WindNinja routing, National Threat widened to 8 families, a
real severe contrast bug found+fixed — 491 near-invisible alert-list entries) was
undercut by a tab-alignment fix that took 6 attempts because I kept verifying a
proxy for the actual thing (button box, not glyph position; window size, not the
actual fixed sidebar width; my own screenshot, not the user's real browser) instead
of the thing itself. No open trust-rebuilding action needed — just don't repeat it:
next time a visual fix doesn't land the first time, stop and ask for their
screenshot/exact measurement before a second attempt, don't iterate blind.

**⚠️ Alex flagged additional errors from this session he has NOT yet detailed** —
his words: "There are other errors you created and left behind. Will clean them up
tomorrow." Do NOT assume the app is clean beyond what's logged above. On resume,
ASK what he found before doing anything else — don't re-audit blind and don't
assume the contrast/alignment work was the only casualty.

## ▶ 2026-07-27 session — National Fire Watchlist + fire-layer bug fixes

User goal: predict WHERE dangerous wildland fire events will occur (risk to property
and life), not just where fire weather is generically bad. Full detail in memory
`project_fire_watchlist` and `Storm_info/STORMWATCH_MASTER_STATUS.md` top entry.

**Shipped:**
- Three live bugs fixed (`4e6c991`): Fire/Fresh Perimeters "NIFC busy" → Esri mirror
  fallback; HMS Smoke Plumes moved off localhost to public NESDIS feed; SPC Fire Wx
  D1/D2 dn:0 placeholder no longer inflates the zone count.
- National Fire Watchlist (`bdce457`): daily bot ranks CONUS places where fire-weather
  trigger × USGS fuels × Census population converge; "🎯 Fire Watchlist" map layer,
  ranked 1-15 markers with detail cards. Spec: `Storm_info/fable_specs/06_fire_watchlist.md`.
  Daily Action `fire-watchlist.yml` runs 13:45 UTC — first automated run not yet observed;
  worth checking `data/fire_watchlist.json`'s `generated_utc` on next resume.

**On resume, pick from (future work, not started, ask before building):**
- AK/HI coverage for the watchlist (USGS fire-danger + SPC firewx are CONUS-only).
- ERC / dead-fuel-moisture (WFAS gridded NFDRS) as a deeper fuels term than WFPI alone.
- Lightning + new-starts feed (`WFIGS_Incident_Locations_Last24h`) as ignition signal.
- SILVIS WUI housing-fraction per place (sharper exposure than raw population).
- Route the watchlist's top 5 through the full HRRR→WindNinja pipeline for
  terrain-resolved wind (currently Open-Meteo via the same classifier as the old
  7-site daily-fire-wind bot).

---

## Earlier park state (2026-07-19, kept for history)

## ▶ TO-DO LIST ON RESUME (in priority order)

**Alex's own quick actions (remind about these first):**
1. **Restart Claude Desktop** (if not done while parked) — loads the bug-fixed MCP
   server (all 24 QA-sweep bugs closed 2026-07-19, commit `5b0aeb0`).
2. **Phone-test the 📸 Snapshot Share button** on https://aphilp1.github.io/stormwatch-live/
   (still untested on mobile).
3. **Set the `NTFY_TOPIC` repo secret** on GitHub + subscribe in the ntfy app —
   unlocks push notifications from BOTH monitors (alert anomalies + health down/recover).

**Build work (each needs Alex's go-ahead where noted):**
4. **Wire public site → cloud Worker** (https://stormwatch.stormwatch-live.workers.dev)
   — APPROVED-PENDING, Alex said "hold as a plan" (2026-07-18) then "later" (2026-07-19).
   ASK before starting. Plan: Fire agent first — cloud-first fetch, graceful fallback to
   MCP_LOCAL, localhost-test before push; then Flood/Nowcast/Combined same pattern.
5. **Commit mcp-server README/.env.example/claude_desktop_config.example.json +
   start-stormwatch.ps1 + RECOVERY.md** — written 2026-07-05, still untracked, needs
   Alex's OK to push (public repo).
6. **Hosting migration** (Cloudflare Pages+R2+Workers) — plan READY at
   Documents\RapidWatch\HOSTING_MIGRATION_PLAN.md, DON'T execute until Alex says go.

**Research side (Fire Winds science, no user action needed — pick up if asked):**
7. labor_day 5 outlier stations still unvalued (C5507/OD110/OD140/ODT50 out of domain,
   TCFO3 nodata).
8. SLEC1 bespoke-DEM hunt (see memory slec1-dem-hunt).
9. Tubbs direction caveat open (4 valley stations 25–66° more northerly than BC).
10. Rebuild broken `hrrr311` conda env (use SYSTEM python or `dem` env meanwhile).

## ✅ DONE 2026-07-19 session (all verified + pushed)
- **"WN niche" badge scrub** (`7697325`): camp_2018 → "WN Corrects", kincade_ign_2019 →
  "WN edge" — last open item from the 2026-06-22 niche re-quote directive; browser-verified.
- **MCP bug backlog CLOSED** (`5b0aeb0`): all remaining QA-sweep bugs fixed
  (007/012–024 + 006 labels). Highlights: US-coverage gate on briefing tools; geocoder
  honors country suffixes ("London UK" no longer hijacked to Ohio), matches PR/VI/GU
  territories, fails honestly on wrong-state ("Pikes Peak Colorado" → clear error);
  marine inland guard; friendly validation (no raw Zod). Verified 17/17 bug repros +
  8/8 geocoder regressions over stdio. Backup: `backup-index-2026-07-19-pre-bugfix2.js`.
  Cloud Worker unaffected (no geocoder copy).

## Previous session state (2026-07-18 close, for context)
Spec-05 Fire Risk probe + draggable card redesign; Cloudflare backend deployed;
diagnostics.html + health_monitor.py + 6-hourly health-monitor Action all live.

## ⚡ LATEST (2026-07-08 evening session, HEAD `5ceb542`+, live)
- **Snapshot REBUILT after user feedback** ("expect a lot more"; wants layer info + basic
  cartographic info): screenshot libs ditched (one wrong, one 90 s) → custom `snapComposite()`
  compositor (tiles/canvas/SVG drawn natively, **0.5 s**); scale bar + north arrow + attribution
  ON the image; carto block (center/scale/extent/view-width/projection/UTC); Active Layers w/
  live notes; Map Keys = all enabled layers' legends. Verified via the real generated .html.
- ⚠️ LESSON (memory `feedback-fix-first-dont-argue`): when user reports bad output — fix
  first, verify the real deliverable yourself, never analyze his screenshot's provenance.
- ~~**RESUME ORDER: (1) apply `Storm_info/fable_specs/05_fire_risk_part2.md`**~~ ✅ **DONE
  2026-07-18** (commit `877a539`, pushed + live): Fire Risk at a Point applied per spec,
  full checklist browser-verified incl. live Red Flag Warning probe (OR, NW06) + real
  alert-card regression. One spec bug found+fixed: WFSP water mask serves ×1 codes (254),
  not ×10 like WLFP — mask guard is `<248` for both probability rows.
- **✅ (3) DONE 2026-07-18 — Cloudflare backend LIVE**: account created (aphilp1@gmail.com),
  subdomain `stormwatch-live`, Worker deployed → https://stormwatch.stormwatch-live.workers.dev
  (/health + /fire-agent verified = local :3456). **Site NOT yet wired to it — user said HOLD
  as a plan** (wire with graceful fallback when he approves).
- **✅ NEW 2026-07-18 — diagnostics stack** (user request "always check everything"):
  `diagnostics.html` (33 live checks) + `health_monitor.py` + `health-monitor.yml` Action
  every 6 h → commits `data/health_status.json`; ntfy on down/recover if NTFY_TOPIC set.
- **✅ Fire Risk probe card redesigned** (user feedback): draggable dark card top-right,
  clear of zoom control, sharper text, ring marker at point (`acbcf80`).
- **REMAINING: (2) remind user: phone test of 📸 Share button; (+) wire site → cloud Worker when user OKs.**

## ✅ DONE 2026-07-08 session (all pushed + live, HEAD `ba91573`+)
- Spec 01 applied: **7-Day Fire Potential** (D1–D7; risk polygons must bypass isvalid filter —
  live data flags all risk isvalid=0) + **Fresh Perimeters (72 h)** (age-colored, card-clickable).
- Spec 04 applied: **📸 Snapshot / Clip·Zip·Ship flagship** — offline .html + .pdf situation
  card + Web Share. Works locally; ~30–60 s capture on national views; **phone share untested**.
- **Montana Mesonet fixed** (user-reported): null-sensor `.toFixed` crash killed the layer;
  card was dark-on-dark AND nuked #det-body (shared card) — now #det-custom + .dl/.dv;
  ensureDetStandard restores det-zoom defaults.
- Wind-flow pace tuned (velocityScale 0.005, particleAge 110).
- **Spec 05 WRITTEN, NOT applied**: `Storm_info/fable_specs/05_fire_risk_part2.md` —
  click-anywhere fire risk (USGS WFPI GetFeatureInfo + NIFC PSP point query, live-verified,
  additive, explicit probe toggle). → APPLY THIS FIRST ON RESUME.
- Still blocked: MCP cloud publish (needs user's free Cloudflare account).
- Backup bundle 2026-07-08 in Documents + Desktop (local only).

## Status at previous pause (2026-07-07)
- Public site LIVE (https://aphilp1.github.io/stormwatch-live/), HEAD `2d6c9d7`, git **in sync (0/0)**.
- Local app `:8001` up; MCP `:3456` comes up with Claude Desktop.
- Deploys fast/reliable (`.nojekyll` in place). **Always tell user to hard-refresh (Ctrl+Shift+R) after any push.**
- Fire experience overhauled & live: incidents, perimeters (clickable, full report), VIIRS (AK+HI), observed winds, animated wind flow (readout + legend).

## ▶ ON RESUME — GO AGGRESSIVE WITH FABLE
User directive (2026-07-07): *"use Fable to get very aggressive here."* Plan = launch
**Fable (model: fable) subagents, in parallel**, to build out the roadmap fast; I
verify each in-browser + push (one hard-refresh reminder per push). Method that works:
edit `weather-alerts.html`, test on `:8001`, verify with DOM-dispatch clicks + screenshots
(pixel clicks mis-scale — window 1920 vs screenshot 1568), then commit + push + poll deploy.

**⚡ PRE-BUILT BY FABLE (launched 2026-07-07 at pause):** Fable agents produced
ready-to-integrate specs in `Storm_info/fable_specs/` — `01_fire_potential_and_fresh_perimeters.md`,
`02_fire_danger_wms.md` (✅ done — USGS WFPI/WLFP/WFSP WMS, D1-7, verified), `03_inciweb_imsr_airnow.md`
(✅ done), and `04_clip_zip_ship.md` (⭐ NEW FLAGSHIP FEATURE — see below). Each has
drop-in code + exact insertion anchors + verified endpoints. ON RESUME: read those,
apply one at a time to weather-alerts.html, browser-verify, commit/push (hard-refresh reminder).

**⭐ FLAGSHIP FEATURE — "Clip · Zip · Ship" (StormWatch Snapshot), approved 2026-07-07:**
one point-and-click button on the main screen captures the current view (map + active
layers + open card + wind readout) → packages a BEAUTIFUL, self-contained, mobile-friendly
**.html** (works offline) AND **.pdf** → ships via Web Share API (one-tap email/msg on
phone) or download fallback. A branded "situation card", not a bare screenshot. Fable
speccing capture lib (leaflet-image/html2canvas + tile-CORS handling), self-contained
packaging, PDF path, share UX, and the card design → `04_clip_zip_ship.md`.

**Attack list (each is a self-contained Leaflet layer; endpoints already verified in `FIRE_DATA_CATALOG.md`):**
1. **Fable Top-6 fire additions** — 7-Day Significant Fire Potential (fsapps.nwcg.gov),
   fresher IR-flight perimeters (WFIGS_Daily_Perimeters), InciWeb links (rss.xml),
   USGS fire-danger WMS, IMSR sitrep points, AirNow PM2.5. Fan these out to Fable.
2. **Wind-flow animation speed** — quick: lower `velocityScale` ~0.0075→0.005 + shorter
   trails; then non-linear map if needed (see `stormwatch-fire-section` memory).
3. **Fire Risk — Part 2** — click-anywhere → risk from AUTHORITATIVE gov data
   (USGS WFPI + NIFC 7-day potential), NOT a homemade score (hard user rule).
4. **MCP publish** — deploy `stormwatch-cloud/` Fire-agent Worker (needs user's free
   Cloudflare account) so public site's agents work. WindNinja stays local.

## Guardrails
- Verify in-browser BEFORE claiming done (user was burned by "claimed it worked").
- Contrast: detail card `#detail` is DARK → light text; chips need light accents (see `feedback-stormwatch-contrast`).
- No real email / secrets in commits. Don't push without it being clearly wanted (this session user is fine with push→hard-refresh loop).
- Full plan + memory index: `STORMWATCH_PROJECT_MAP.md` §Roadmap + memories `stormwatch-project-map`, `stormwatch-fire-section`, `stormwatch-mcp-servers-plan`, `stormwatch-cloud-backend`, `stormwatch-pages-nojekyll`.
