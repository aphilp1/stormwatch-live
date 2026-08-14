#!/usr/bin/env node
// Catches the exact bug class found 2026-08-01: a function that mixes local-time
// Date setters (setHours/setMinutes/setSeconds/setDate/setMonth/setFullYear) with
// UTC getters (getUTC*) or UTC-serialized output (toISOString, which is always UTC).
// Every WMS/NOAA TIME-parameter builder in this app is UTC-only — mixing local and
// UTC Date methods silently shifts the timestamp by the machine's timezone offset,
// only reproducing off-UTC (see getNaqfcTimeStr, fixed in commit c5d79b1).
//
// Heuristic, not a real parser: extracts each top-level `function name(...) { ... }`
// body via brace counting, then checks for both patterns inside the SAME function.
// False positives are possible for a function that intentionally reports local wall
// time; false negatives are possible for arrow functions or nested helpers. Good
// enough as a fast pre-push/CI gate — not a substitute for review.

const fs = require('fs');
const path = process.argv[2] || 'weather-alerts.html';
const src = fs.readFileSync(path, 'utf8');

// Functions that genuinely mean local wall-clock time — reviewed and confirmed safe.
const ALLOW = new Set([]);

const LOCAL_SETTERS = /\.set(Hours|Minutes|Seconds|Date|Month|FullYear)\s*\(/;
const UTC_MARKERS = /getUTC\w+\s*\(|toISOString\s*\(/;

const fnRe = /function\s+(\w+)\s*\([^)]*\)\s*\{/g;
let m;
const findings = [];

while ((m = fnRe.exec(src))) {
  const name = m[1];
  const bodyStart = m.index + m[0].length;
  let depth = 1, i = bodyStart;
  while (depth > 0 && i < src.length) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') depth--;
    i++;
  }
  const body = src.slice(bodyStart, i);
  if (!ALLOW.has(name) && LOCAL_SETTERS.test(body) && UTC_MARKERS.test(body)) {
    const line = src.slice(0, m.index).split('\n').length;
    findings.push({ name, line });
  }
}

if (findings.length) {
  console.error('lint_utc_mixing: found local/UTC Date-method mixing:');
  for (const f of findings) {
    console.error(`  ${path}:${f.line}  function ${f.name}()`);
  }
  console.error('\nIf this is intentional (function really means local wall-clock time),');
  console.error('add it to the ALLOW list at the top of Storm_info/lint_utc_mixing.js.');
  process.exit(1);
} else {
  console.log('lint_utc_mixing: clean, no local/UTC Date-method mixing found.');
  process.exit(0);
}
