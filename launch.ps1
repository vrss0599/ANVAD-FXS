# launch.ps1 — Foolproof GUI launcher (always uses venv python, avoids yellow badge)
# Handles: ExecutionPolicy Restricted, spaces in path, missing venv hint.
# Usage:  double-click launch.bat (always works) OR powershell -ExecutionPolicy Bypass -File .\launch.ps1

$ErrorActionPreference = "Continue"

# Try to relax policy for this user (foolproof for next launches)
try {
    $pol = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
    if ($pol -eq "Restricted" -or $pol -eq "AllSigned") {
        try { Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force -ErrorAction SilentlyContinue } catch { }
    }
} catch { }

$proj = $PSScriptRoot
if (-not $proj) { $proj = $PWD.Path }
$venvPy = Join-Path $proj "venv\Scripts\python.exe"
$mainPy = Join-Path $proj "app\main.py"

if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "venv not found at $venvPy" -ForegroundColor Red
    Write-Host "Run install first:  double-click install.bat  or  powershell -ExecutionPolicy Bypass -File .\install.ps1" -ForegroundColor Yellow
    Write-Host "Press Enter to close..."; Read-Host | Out-Null
    exit 1
}
if (-not (Test-Path -LiteralPath $mainPy)) {
    Write-Host "app/main.py not found at $mainPy" -ForegroundColor Red
    pause; exit 1
}
Write-Host "Launching UGA-SUB via venv: $venvPy" -ForegroundColor Green
Write-Host "  Tip: if GPU badge is yellow, run:  `"$venvPy`" tools/check_cuda.py" -ForegroundColor DarkGray
# Quote both paths (spaces in "Sanika manjunath")
& "$venvPy" "$mainPy"
$ec = $LASTEXITCODE
if ($ec -ne 0) {
    Write-Host "GUI exited with code $ec" -ForegroundColor Yellow
    Write-Host "Try:  `"$venvPy`" tools/check_cuda.py" -ForegroundColor Yellow
    Write-Host "Press Enter to close..."; Read-Host | Out-Null
}
