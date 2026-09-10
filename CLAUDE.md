# StormWatch — Rules for Claude Code

## Do unapproved work on the `wip` branch, never on `master`

All new work that Alex hasn't explicitly approved to go live happens on the local `wip`
branch (`git checkout wip`, create it if it doesn't exist), never directly on `master`.
Only merge `wip` into `master` and push when Alex explicitly says to (e.g. "update
StormWatch git", "push it", "merge it in"). This applies even after I've verified a fix
myself and it looks clean — my own local verification is not sufficient grounds to
merge/push on its own.

**Why this is a branch rule, not just a "don't push" promise:** 2026-09-09 — first
pushed a GOES-animation fix right after verifying it myself, before Alex had tested it;
corrected directly ("You pushed too early... don't push in the future, unless you
confirm with me"). Committed to never pushing without confirmation going forward — but
later the same session, something else on this machine (a scheduled bot task's own
commit+push cycle for Alert Monitor/Health-check-in snapshot files, most likely, though
never conclusively identified — `Get-ScheduledTask` was blocked by sandbox permissions
when checked) ran its own `git pull`/rebase/`push` in this same repo and swept my
still-`master`-resident, not-yet-approved commits out to `origin/master` and the live
public site along with its own commit. A verbal "I won't push" only constrains what I
do; it does nothing about another process with push access to the same branch. Keeping
unapproved work on a separate branch is an actual technical barrier: whatever that other
process does to `master`, it has no reason to touch `wip`.

## Verify JS syntax immediately after every edit to weather-alerts.html

Alex frequently re-tests `weather-alerts.html` against the same local server
(`localhost:8001`) while I'm actively editing it. Run a syntax check right after every
Edit/Write to that file — before moving on to further edits or my own browser
testing — not deferred to a final check at the end of a session:

```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('weather-alerts.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
scripts.forEach((s,i) => { try { new Function(s); console.log(i,'OK'); } catch(e) { console.log(i,'SYNTAX ERROR:', e.message); } });
"
```

**Why:** 2026-09-09 — an Edit call dropped a function's closing brace, which broke the
page's *entire* inline script (one syntax error kills every function, not just the one
being edited — checkboxes and buttons all went dead). Alex was independently re-testing
the same server at that moment and very plausibly hit that exact broken window, which
read as a much bigger regression than it was. A syntax error is the cheapest possible
thing to catch and the most catastrophic to leave live even briefly.
