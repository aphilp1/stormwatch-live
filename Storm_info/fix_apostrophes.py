"""
Fix unescaped apostrophes inside JS single-quoted note/narrative strings.
The rewrite_all_narratives.py script wrote raw Python string values into JS
single-quoted strings, leaving contractions like HRRR's / don't unescaped,
which breaks the JS parser for the entire script block.
"""

import re

HTML = r'C:\Users\aphil\Documents\Stormwatch\weather-alerts.html'

with open(HTML, 'r', encoding='utf-8') as f:
    content = f.read()

def fix_note_narrative(m):
    prefix = m.group(1)  # "    note: '" or "    narrative: '"
    body   = m.group(2)  # content between opening and closing '
    suffix = m.group(3)  # closing ' plus optional comma
    # Escape any apostrophe NOT already preceded by backslash
    body_fixed = re.sub(r"(?<!\\)'", r"\\'", body)
    return prefix + body_fixed + suffix

# Match single-line note/narrative values
# Group 1: prefix up to and including opening '
# Group 2: body (greedy, stays within line)
# Group 3: closing ' and trailing comma/whitespace
pattern = re.compile(
    r"^(\s+(?:note|narrative): ')(.*)('(?:,?)\s*)$",
    re.MULTILINE
)

content_fixed, n = re.subn(pattern, fix_note_narrative, content)
print(f"Processed {n} note/narrative lines")

# Verify no double-escaping (should not happen due to lookbehind)
doubles = len(re.findall(r"\\\\'", content_fixed))
if doubles:
    print(f"WARNING: {doubles} possible double-escapes found — check manually")
else:
    print("No double-escapes detected")

with open(HTML, 'w', encoding='utf-8') as f:
    f.write(content_fixed)

print("Done.")
