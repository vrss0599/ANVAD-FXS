# install.ps1 — Robust one-shot installer for UGA-SUB (RTX 3050 6GB)
# Fixes yellow CUDA badge by forcing CUDA torch via --index-url BEFORE other deps.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Or:  .\install.ps1

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " UGA-SUB — Robust Installer (RTX 3050 6GB)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. Find python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Host "ERROR: python not found on PATH. Install Python 3.10/3.11 x64 with Add to PATH checked." -ForegroundColor Red; exit 1 }
Write-Host "[1/6] Python: $($py.Source)  $((& python --version) 2>&1)" -ForegroundColor Green

# 2. Create venv if missing
if (-not (Test-Path -LiteralPath "venv\Scripts\python.exe")) {
    Write-Host "[2/6] Creating venv ..." -ForegroundColor Yellow
    & python -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Host "venv creation failed" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "[2/6] venv already exists — reusing" -ForegroundColor Green
}

$venvPy = (Resolve-Path "venv\Scripts\python.exe").Path
Write-Host "      Venv python: $venvPy" -ForegroundColor DarkGray

# 3. Upgrade pip in venv (use venv python explicitly — robust to non-activated shell)
Write-Host "[3/6] Upgrading pip in venv ..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-Host "pip upgrade failed" -ForegroundColor Red; exit 1 }

# 4. Force CUDA torch FIRST (deterministic — fixes C1: --extra-index-url fallback picking CPU wheel)
Write-Host "[4/6] Installing PyTorch CUDA 12.1 (this may take 1-2 min, ~2GB download) ..." -ForegroundColor Yellow
Write-Host "      Command: $venvPy -m pip install torch --index-url https://download.pytorch.org/whl/cu121" -ForegroundColor DarkGray
& $venvPy -m pip install torch --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) { Write-Host "torch CUDA install failed — check internet" -ForegroundColor Red; exit 1 }
Write-Host "      Verifying torch CUDA ..." -ForegroundColor DarkGray
& $venvPy -c "import torch; print(f'torch {torch.__version__} cuda_built={torch.version.cuda} cuda_available={torch.cuda.is_available()}')"
if ($LASTEXITCODE -ne 0) { Write-Host "torch verification failed" -ForegroundColor Yellow }

# 5. Install app + transcribe deps (now torch already CUDA, so resolver won't downgrade to CPU)
Write-Host "[5/6] Installing app deps (customtkinter, pillow) ..." -ForegroundColor Yellow
& $venvPy -m pip install -r app/requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "app requirements failed" -ForegroundColor Red; exit 1 }

Write-Host "[5/6] Installing transcribe deps (faster-whisper, soundfile, av, cudnn) ..." -ForegroundColor Yellow
& $venvPy -m pip install -r transcribe/requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "transcribe requirements failed" -ForegroundColor Red; exit 1 }

# 6. Verify
Write-Host "[6/6] Running CUDA diagnostic ..." -ForegroundColor Yellow
& $venvPy tools/check_cuda.py

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Install complete!" -ForegroundColor Green
Write-Host " Launch GUI via VENV (robust, avoids yellow badge):" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\python app\main.py" -ForegroundColor White
Write-Host " Or double-click launch.ps1 / launch.bat" -ForegroundColor White
Write-Host " If badge still yellow, click Recheck or run:  .\venv\Scripts\python tools/check_cuda.py" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Green
