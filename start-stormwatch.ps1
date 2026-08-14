# start-stormwatch.ps1 — launch the StormWatch Live local app + check the MCP backend.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File "C:\Users\aphil\Documents\Stormwatch\start-stormwatch.ps1"
#   # or, in a PowerShell window sitting in the Stormwatch folder:
#   .\start-stormwatch.ps1
#
# Optional: -Port 8080   (default 8001)
#
# What it does:
#   1. Starts a Python HTTP server in the Stormwatch folder (serves weather-alerts.html).
#   2. Checks whether the MCP HTTP backend on :3456 is alive (that comes from
#      Claude Desktop launching mcp-server\index.js — this script does NOT start it).
#   3. Opens the app in your browser.

param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "StormWatch Live — startup" -ForegroundColor Cyan
Write-Host "Folder: $root"

# --- 1. App server (:$Port) --------------------------------------------------
$portInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "[app] Port $Port already serving — reusing it." -ForegroundColor Yellow
} else {
    Write-Host "[app] Starting: python -m http.server $Port" -ForegroundColor Green
    Start-Process -FilePath "python" -ArgumentList "-m","http.server","$Port" -WorkingDirectory $root -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

# --- 2. MCP backend health (:3456) — informational only ----------------------
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:3456/health" -TimeoutSec 3 -UseBasicParsing
    if ($health.StatusCode -eq 200) {
        Write-Host "[mcp] Backend :3456 healthy (agents + WindNinja available)." -ForegroundColor Green
    }
} catch {
    Write-Host "[mcp] Backend :3456 NOT responding." -ForegroundColor Yellow
    Write-Host "      The 4 agents / WindNinja / HMS smoke / AirNow need it."
    Write-Host "      It is launched by Claude Desktop (mcp-server\index.js) — make sure"
    Write-Host "      Claude Desktop is running, or start it manually:  node mcp-server\index.js"
}

# --- 3. Open the app ---------------------------------------------------------
$url = "http://localhost:$Port/weather-alerts.html"
Write-Host "[app] Opening $url" -ForegroundColor Cyan
Start-Process $url

Write-Host ""
Write-Host "Done. App server runs in a minimized window; close it to stop serving." -ForegroundColor Cyan
