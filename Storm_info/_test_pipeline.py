import sys
sys.stdout.reconfigure(encoding='utf-8')

print('=== Pipeline dependency check ===')

# herbie
try:
    from herbie import Herbie
    print('herbie:   OK')
except Exception as e:
    print(f'herbie:   FAIL  {e}')

# HRRR metadata fetch for Camp Fire date
try:
    H = Herbie('2018-11-08 06:00', model='hrrr', product='sfc', fxx=0)
    print(f'HRRR meta: OK  grib={H.grib}')
    can_fetch = True
except Exception as e:
    print(f'HRRR meta: FAIL  {e}')
    can_fetch = False

# cfgrib
try:
    import cfgrib
    print('cfgrib:   OK')
except Exception as e:
    print(f'cfgrib:   FAIL  {e}')

# xarray, numpy
for lib in ['numpy','xarray','netCDF4','cdsapi']:
    try:
        __import__(lib)
        print(f'{lib}: OK')
    except Exception as e:
        print(f'{lib}: FAIL  {e}')

# Try a small HRRR data fetch if metadata worked
if can_fetch:
    try:
        ds = H.xarray('TMP:2 m')
        print(f'HRRR data fetch: OK  shape={dict(ds.dims)}')
    except Exception as e:
        print(f'HRRR data fetch: FAIL  {e}')

# Check WindNinja terrain files / cache
import os
from pathlib import Path
wn_cache = Path(r'C:\temp\windninja_cache')
print(f'\nWindNinja cache exists: {wn_cache.exists()}')
if wn_cache.exists():
    dems = list(wn_cache.glob('*.tif')) + list(wn_cache.glob('**/*.tif'))
    print(f'  DEMs found: {len(dems)}')
    for d in dems[:5]:
        print(f'    {d.name}  {d.stat().st_size//1024}KB')

# Check for existing WN output files
wn_dirs = list(Path(r'C:\temp').glob('*')) if Path(r'C:\temp').exists() else []
print(f'\nC:\\temp contents (top-level): {[d.name for d in wn_dirs[:15]]}')
