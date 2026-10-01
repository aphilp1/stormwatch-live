# Automated bug-catching infra

Three automated checks, two of them on a schedule so the live site is exercised
around the clock, not only when code changes.

## 1. On every push to `master` that touches `weather-alerts.html`
(`.github/workflows/smoke-test.yml`), in order:

1. **`lint_utc_mixing.js`** — static check. Flags any function that mixes
   local-time `Date` setters (`setHours`/`setMinutes`/etc.) with UTC getters
   or UTC-serialized output (`getUTC*`, `toISOString`). Would have caught the
   2026-08-01 NAQFC timezone bug (`getNaqfcTimeStr`, fixed in `c5d79b1`), which
   only reproduced on a machine set to a non-UTC timezone. Heuristic brace-
   counting, not a real parser — see the file header for known false-
   positive/negative cases.

2. **`smoketest_layers.js`** — Playwright functional layer test against a local
   copy of the page (see below for what it checks).

## 2. Every 6 hours against the LIVE public site
(`.github/workflows/layer-test.yml`, cron `41 */6 * * *`): runs the same
`smoketest_layers.js` against `aphilp1.github.io/stormwatch-live`, writes the
result to `data/layer_test.json` (shown at the top of `diagnostics.html` as
"Last automated layer test"), and pushes an ntfy notification (the existing
`NTFY_TOPIC` secret) listing which layers failed.

## 3. Every 6 hours, server-side service pings
(`health_monitor.py` via `.github/workflows/health-monitor.yml`): one tiny real
request to every upstream service, including (since 2026-09-30) the Overpass
API that the Stream Network layer depends on.

## What `smoketest_layers.js` checks (rebuilt 2026-09-30)

Loads the app in a fixed-UTC-6 context (`America/Regina`, no DST —
deterministic year-round), cycles every top-level tab, then switches every
`lyr-*` layer toggle on, **waits for that layer's own status note to settle**,
and records what it said:

- `ok` — the note shows real content ("12 frames", "293 fires", "241 waterways").
- `fail` — the note is an error state ("load error", "unavailable", "err",
  "stream servers busy"). **This is the check that was missing before**: the
  old script only failed on JS exceptions, so a feed that quietly returned
  "load error" passed.
- `timeout` — still "loading…" after 20 s (120 s when it is working through
  fallback mirrors).
- `zoom-gated` — the note asked for a closer zoom ("zoom in (9+) to load",
  "zoom 14+ to see zones"). These layers are re-tested in a later pass zoomed
  in to Missoula at the zoom level the note asked for, so zoom-gated feeds
  such as Stream Network (Overpass) and FEMA flood zones are really exercised
  instead of skipped.
- `no-note` — the layer has no status note (a plain tile overlay); only the
  console-error check applies to it.

Any real JS console error or uncaught exception during the run is a **code
failure**; any `fail`/`timeout` layer is a **data failure**; either one fails
the run. The generic "Failed to load resource" console noise every map app
generates (ocean-edge tiles, a CORS-blocked third party) is filtered out so
the test stays green on ordinary network flakiness.

Verified against a real outage before being wired in: on 2026-09-30 the
Overpass servers were returning HTTP 504 for several minutes; the local run
correctly reported `lyr-nhd` as the one failing layer and every other layer
(44 of 50 with status notes) as loaded.

**What this does NOT catch:** silent-wrong-output bugs, where the code runs,
the note looks normal, but the drawn result is wrong (wrong colour, wrong
timestamp, wrong location) — like the NAQFC timezone bug's actual symptom
(blank tiles, no exception) or the 2026-08-01 wind-flow contrast bug (a real
colour, just too washed-out to see). Those need a human visual check or a
value-level assertion, not this script.

## Running locally

```bash
cd Storm_info
npm ci
npx playwright install chromium   # first run only
node lint_utc_mixing.js ../weather-alerts.html
python3 -m http.server 8123 &     # from the repo root, in another terminal
node smoketest_layers.js http://localhost:8123/weather-alerts.html
# or against the live site, writing the same JSON the Action writes:
node smoketest_layers.js https://aphilp1.github.io/stormwatch-live/weather-alerts.html --out ../data/layer_test.json
```

A full local run takes about 2 minutes (50 toggles).

A 2026-08-01 session claimed this infra was "done." It wasn't — the workflow
file, this doc, and the smoke test script didn't survive past that session
(only the lint script did, and it was never committed). Rebuilt and verified
2026-08-14; upgraded from crash-only to data-level checks plus the scheduled
live run 2026-09-30.
