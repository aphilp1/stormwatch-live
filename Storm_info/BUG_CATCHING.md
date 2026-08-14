# Automated bug-catching infra

Two checks run on every push to `master` that touches `weather-alerts.html`
(`.github/workflows/smoke-test.yml`), in order:

1. **`lint_utc_mixing.js`** — static check. Flags any function that mixes
   local-time `Date` setters (`setHours`/`setMinutes`/etc.) with UTC getters
   or UTC-serialized output (`getUTC*`, `toISOString`). Would have caught the
   2026-08-01 NAQFC timezone bug (`getNaqfcTimeStr`, fixed in `c5d79b1`), which
   only reproduced on a machine set to a non-UTC timezone. Heuristic brace-
   counting, not a real parser — see the file header for known false-
   positive/negative cases.

2. **`smoketest_layers.js`** — Playwright browser check. Loads the app in a
   fixed-UTC-6 context (`America/Regina`, no DST — deterministic year-round),
   cycles every top-level tab, then clicks every `lyr-*` layer toggle on and
   off. Fails on any real JS console error or uncaught exception; a filter
   strips the generic "Failed to load resource" noise every map app generates
   from ordinary things (missing ocean-edge tiles, a momentarily-down third-
   party feed) so the test stays green on network flakiness and red on actual
   code bugs. Verified against a real regression before being wired into CI:
   an intentionally-injected `TypeError` inside a toggle handler was caught
   and correctly failed the run; reverting the bug made it pass again.

**What this catches:** JS-crash-class regressions — a toggle that throws, a
null-reference on missing data, the exact shape of the 2026-07-08 Montana
Mesonet null-sensor crash.

**What this does NOT catch:** silent-wrong-output bugs, where the code runs
without error but produces the wrong result (wrong color, wrong timestamp,
wrong location) — like the NAQFC timezone bug's actual symptom (blank tiles,
no exception) or the 2026-08-01 wind-flow contrast bug (a real color, just
too washed-out to see). Those need a human visual check or a value-level
assertion, not this script.

**Running locally:**

```bash
cd Storm_info
npm ci
npx playwright install chromium   # first run only
node lint_utc_mixing.js ../weather-alerts.html
python3 -m http.server 8123 &     # from the repo root, in another terminal
node smoketest_layers.js http://localhost:8123/weather-alerts.html
```

A 2026-08-01 session claimed this infra was "done." It wasn't — the workflow
file, this doc, and the smoke test script didn't survive past that session
(only the lint script did, and it was never committed). Rebuilt and verified
2026-08-14.
