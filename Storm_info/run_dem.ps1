# run_dem.ps1 — Launcher for build_dem_features.py
# Uses conda dem env (has py3dep, rasterio, rioxarray).

$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\dem"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"
$env:GDAL_DATA = "$CONDA_ENV\Library\share\gdal"
$env:PROJ_DATA = "$CONDA_ENV\Library\share\proj"

$SCRIPT = "$PSScriptRoot\build_dem_features.py"
& "$CONDA_ENV\python.exe" $SCRIPT @args
