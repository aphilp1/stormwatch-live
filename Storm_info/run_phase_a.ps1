# run_phase_a.ps1 — Launcher for build_hrrr_error_dataset.py
# Sets conda env paths so eccodes/cfgrib DLLs are found, then runs the build.

$CONDA_ENV = "C:\Users\aphil\miniforge3\envs\hrrr311"
$env:PATH = "$CONDA_ENV;$CONDA_ENV\Library\bin;$CONDA_ENV\Library\mingw-w64\bin;$CONDA_ENV\Library\usr\bin;$CONDA_ENV\Scripts;$env:PATH"

$SCRIPT = "$PSScriptRoot\build_hrrr_error_dataset.py"
& "$CONDA_ENV\python.exe" $SCRIPT @args
