"""Replace 'Reality A/B' terminology with 'Forecast/Corrected Forecast' in weather-alerts.html"""

HTML = r'C:\Users\aphil\Documents\Stormwatch\weather-alerts.html'

with open(HTML, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('Reality B KNOWN_FAIL',          'Corrected Forecast KNOWN_FAIL'),
    ('Reality B (corrected BC',       'Corrected Forecast (corrected BC'),
    ('Reality B (two-level corrected BC)', 'Corrected Forecast (two-level corrected BC)'),
    ('Reality B: do-no-harm',         'Corrected Forecast: do-no-harm'),
    ('Reality B',                     'Corrected Forecast'),
    ('Reality A with raw BC',         'Forecast (raw BC)'),
    ('Reality A: WN raw',             'Forecast (raw): WN'),
    ('Reality A',                     'Forecast (raw)'),
    ('Two Realities',                 'Forecast vs. Truth'),
]

count_total = 0
for old, new in replacements:
    n = content.count(old)
    if n:
        content = content.replace(old, new)
        print(f'  {n}x  "{old}"  ->  "{new}"')
        count_total += n

with open(HTML, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nDone. {count_total} replacements total.')
