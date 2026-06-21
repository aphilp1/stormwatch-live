"""
Verify SLEC1 WN/obs ratio on original 12mi UTM DEM (the domain used to lock ratio=1.128).
Domain: dem_39.6_-120.9_12mi_utm.tif, center (39.6,-120.9), offset=5.1km to SLEC1.
BC: 34@81 (same as runner used).  obs=35.0 mph.
"""
import subprocess, glob, os, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WN_CLI = r'C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe'
CACHE  = r'C:\temp\windninja_cache'
DEM    = os.path.join(CACHE, 'dem_39.6_-120.9_12mi_utm.tif')
LAT, LON = 39.636140, -120.863990
OBS = 35.0
SPD_INT, DIR_INT = 34, 81

dem_stem = os.path.splitext(os.path.basename(DEM))[0]
cached_vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{DIR_INT}_{SPD_INT}_*_vel-4326.asc'))

if not cached_vel:
    print(f'Running WN on {dem_stem}...')
    args = [WN_CLI, '--num_threads', '4',
            '--elevation_file', DEM,
            '--initialization_method', 'domainAverageInitialization',
            '--input_speed', str(SPD_INT), '--input_speed_units', 'mph',
            '--input_direction', str(DIR_INT),
            '--input_wind_height', '10', '--units_input_wind_height', 'm',
            '--uni_air_temp', '50', '--air_temp_units', 'F',
            '--uni_cloud_cover', '0.1', '--cloud_cover_units', 'fraction',
            '--vegetation', 'trees', '--mesh_choice', 'coarse',
            '--output_wind_height', '10', '--units_output_wind_height', 'm',
            '--output_speed_units', 'mph', '--output_path', CACHE,
            '--write_ascii_output', 'true', '--ascii_out_json', '0', '--ascii_out_4326', '1']
    res = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        print('ERROR:', res.stderr[-400:])
        sys.exit(1)
    cached_vel = glob.glob(os.path.join(CACHE, f'{dem_stem}_{DIR_INT}_{SPD_INT}_*_vel-4326.asc'))

if not cached_vel:
    print('No vel ASC found after run.')
    sys.exit(1)

vel = cached_vel[0]
print(f'ASC: {os.path.basename(vel)}')

hdr, data = {}, []
with open(vel) as f:
    for line in f:
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) == 2 and not parts[0].replace('.','').replace('-','').isdigit():
            hdr[parts[0].lower()] = float(parts[1])
        else:
            try:
                data.append([float(v) for v in parts])
            except:
                pass
arr = np.array(data)
nrows = int(hdr['nrows']); ncols = int(hdr['ncols'])
xll = hdr['xllcorner']; yll = hdr['yllcorner']; cell = hdr['cellsize']
nodata = hdr.get('nodata_value', -9999)

col_f = (LON - xll) / cell
row_f = (nrows - 1) - (LAT - yll) / cell
print(f'Grid: {nrows}x{ncols}  cell={cell:.6f}°  col_f={col_f:.2f}  row_f={row_f:.2f}')
in_bounds = (0.0 <= col_f <= ncols - 1 and 0.0 <= row_f <= nrows - 1)
print(f'In bounds: {in_bounds}')

if in_bounds:
    ci, ri = int(col_f), int(row_f)
    cr, rr = col_f - ci, row_f - ri
    ci = max(0, min(ci, ncols - 2))
    ri = max(0, min(ri, nrows - 2))
    val = (arr[ri,ci]*(1-rr)*(1-cr) + arr[ri,ci+1]*(1-rr)*cr +
           arr[ri+1,ci]*rr*(1-cr) + arr[ri+1,ci+1]*rr*cr)
    wn_spd = float(val) if abs(val - nodata) > 1 else None
    if wn_spd is not None:
        ratio = wn_spd / OBS
        print(f'\nSLEC1 on 12mi_utm DEM (5.1km offset):')
        print(f'  WN_spd = {wn_spd:.2f} mph')
        print(f'  obs    = {OBS:.1f} mph')
        print(f'  ratio  = {ratio:.3f}  (locked = 1.128)')
        print(f'  WN_err = {wn_spd-OBS:+.2f} mph')
        print(f'  Delta from locked: {ratio - 1.128:+.3f}  ({abs(ratio/1.128 - 1)*100:.1f}% swing)')
    else:
        print('Nodata at SLEC1 lat/lon')
else:
    print(f'OUTSIDE grid bounds — needs larger domain or different center')
