# StormWatch — Rules for Claude Code

## Never push without explicit confirmation

Commit locally whenever it makes sense, but do **not** run `git push` on this repo
until Alex explicitly says to (e.g. "update StormWatch git", "push it", "go ahead and
push"). This applies even after I've verified a fix myself and it looks clean — my own
local verification is not sufficient grounds to push on its own.

**Why:** 2026-09-09 — pushed a GOES-animation fix right after verifying it myself,
before Alex had tested it. That specific bug went through three "verified" rounds that
didn't hold up in his hands, on top of the push. He corrected it directly: "You pushed
too early... don't push in the future, unless you confirm with me."

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
