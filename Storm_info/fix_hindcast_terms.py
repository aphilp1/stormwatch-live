"""Fix 'Forecast' terminology back to 'Hindcast' throughout weather-alerts.html"""

HTML = r'C:\Users\aphil\Documents\Stormwatch\weather-alerts.html'

with open(HTML, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('Corrected Forecast KNOWN_FAIL',   'Corrected Hindcast KNOWN_FAIL'),
    ('Corrected Forecast (corrected BC', 'Corrected Hindcast (corrected BC'),
    ('Corrected Forecast (two-level corrected BC)', 'Corrected Hindcast (two-level corrected BC)'),
    ('Corrected Forecast: do-no-harm',  'Corrected Hindcast: do-no-harm'),
    ('Corrected Forecast',              'Corrected Hindcast'),
    ('Forecast (raw BC)',               'Hindcast (raw BC)'),
    ('Forecast (raw): WN',              'Hindcast (raw): WN'),
    ('Forecast vs. Truth',              'Hindcast vs. Truth'),
    ('Forecast (raw) --',               'Hindcast (raw) --'),
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

print(f'\nDone. {count_total} replacements.')
