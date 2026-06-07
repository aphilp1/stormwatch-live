# run_merge_gate.ps1
# Merge DEM features into departure database and run Phase B gate checks.
# Uses conda hrrr311 env (needs numpy; no py3dep/rasterio required).

$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\hrrr311"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"

$SCRIPT = "$PSScriptRoot\merge_dem_and_gate.py"
& "$CONDA_ENV\python.exe" $SCRIPT @args
