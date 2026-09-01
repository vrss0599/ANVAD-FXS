# launch.ps1 — Robust GUI launcher (always uses venv python, avoids yellow badge)
# Usage:  powershell -ExecutionPolicy Bypass -File .\launch.ps1   or double-click

$ErrorActionPreference = "Stop"
$proj = $PSScriptRoot
$venvPy = Join-Path $proj "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "venv not found at $venvPy" -ForegroundColor Red
    Write-Host "Run install first:  .\install.ps1" -ForegroundColor Yellow
    pause; exit 1
}
Write-Host "Launching UGA-SUB via venv: $venvPy" -ForegroundColor Green
& $venvPy (Join-Path $proj "app\main.py")
