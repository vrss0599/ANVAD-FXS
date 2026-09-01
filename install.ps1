# install.ps1 — Foolproof one-shot installer for UGA-SUB (RTX 2050 4GB / 3050 6GB)
# Handles: Python 3.13+ (no cu121 wheel), ExecutionPolicy blocks, spaces in path, offline fallbacks.
# Usage:
#   Double-click install.bat  (recommended, bypasses policy)
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   .\install.ps1  (if policy is RemoteSigned)

$ErrorActionPreference = "Continue"  # foolproof: don't abort on first error, try fallbacks

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " UGA-SUB — Foolproof Installer (RTX 2050 4GB / 3050 6GB)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- 0. Self-elevate ExecutionPolicy for this process (foolproof for launch.ps1 later) ---
try {
    $pol = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
    if ($pol -eq "Restricted" -or $pol -eq "AllSigned" -or $pol -eq "Undefined") {
        Write-Host "[0/6] ExecutionPolicy is $pol — setting CurrentUser RemoteSigned for future launches ..." -ForegroundColor Yellow
        try { Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force -ErrorAction SilentlyContinue; Write-Host "      Policy updated." -ForegroundColor Green } catch { Write-Host "      Could not update policy (non-fatal, use install.bat/launch.bat)" -ForegroundColor Yellow }
    }
} catch { }

# 1. Find python (robust to py launcher)
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "ERROR: python not found on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10 or 3.11 64-bit from python.org with 'Add to PATH' checked." -ForegroundColor Yellow
    Write-Host "Python 3.13 has no PyTorch cu121 wheel — 3.11 is recommended for best CUDA support." -ForegroundColor Yellow
    pause; exit 1
}
$pyVerStr = (& python --version 2>&1 | Out-String).Trim()
if (-not $pyVerStr) { $pyVerStr = (& py --version 2>&1 | Out-String).Trim() }
Write-Host "[1/6] Python: $($py.Source)  $pyVerStr" -ForegroundColor Green

# Parse version for gate
$pyMajorMinor = $null
try {
    $vOut = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    $pyMajorMinor = $vOut.Trim()
} catch { }
Write-Host "      Detected: $pyMajorMinor" -ForegroundColor DarkGray
$torchIndex = "https://download.pytorch.org/whl/cu121"
$torchIndexFallback = "https://download.pytorch.org/whl/cu124"
$useFallback = $false
if ($pyMajorMinor -eq "3.13" -or $pyMajorMinor -eq "3.14") {
    Write-Host "      WARN: Python $pyMajorMinor has NO torch+cu121 wheel (PyTorch cu121 only up to 3.12)." -ForegroundColor Yellow
    Write-Host "      Will try cu121 first, then auto-fallback to cu124 (which has cp313 wheels). For best stability, use Python 3.11." -ForegroundColor Yellow
    $useFallback = $true
}
# Detect GPU VRAM hint (foolproof for 2050 4GB vs 3050 6GB)
try {
    $gpuInfo = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
    if ($gpuInfo) { Write-Host "      GPU: $gpuInfo" -ForegroundColor DarkGray }
} catch { }

# 2. Create venv if missing (handle spaces in path via quoted args)
$venvPy = Join-Path $PWD "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "[2/6] Creating venv ..." -ForegroundColor Yellow
    & python -m venv "venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "venv creation failed (try: py -m venv venv or python3 -m venv venv)" -ForegroundColor Red
        # Try alternative launcher
        try { & py -m venv "venv"; $venvPy = Join-Path $PWD "venv\Scripts\python.exe" } catch { }
        if (-not (Test-Path -LiteralPath $venvPy)) { Write-Host "Still failed — check python install." -ForegroundColor Red; pause; exit 1 }
    }
} else {
    Write-Host "[2/6] venv already exists — reusing" -ForegroundColor Green
}
$venvPy = (Resolve-Path -LiteralPath $venvPy -ErrorAction SilentlyContinue).Path
if (-not $venvPy) { $venvPy = Join-Path $PWD "venv\Scripts\python.exe" }
Write-Host "      Venv python: $venvPy" -ForegroundColor DarkGray

# 3. Upgrade pip in venv (explicit venv python, robust to non-activated shell)
Write-Host "[3/6] Upgrading pip in venv ..." -ForegroundColor Yellow
& "$venvPy" -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-Host "pip upgrade warn (non-fatal)" -ForegroundColor Yellow }

# Helper: try torch install with fallbacks (foolproof)
function Install-Torch {
    param([string]$venvPy)
    Write-Host "[4/6] Installing PyTorch CUDA (may be ~2GB, 1-3 min) ..." -ForegroundColor Yellow

    # Strategy: try cu121 via --index-url, then extra-index fallback, then cu124, then cpu
    $attempts = @(
        @{ Label="cu121 --index-url"; Args=@("install","torch","--index-url",$torchIndex) },
        @{ Label="cu121 --extra-index-url"; Args=@("install","torch","--extra-index-url",$torchIndex) },
        @{ Label="cu124 --index-url (for Py3.13)"; Args=@("install","torch","--index-url",$torchIndexFallback) },
        @{ Label="cpu fallback"; Args=@("install","torch","--index-url","https://download.pytorch.org/whl/cpu") }
    )

    $installed = $false
    $attempt = 0
    foreach ($a in $attempts) {
        $attempt++
        # Skip cu121 index-url on 3.13 first attempt to save time? No — still try, user may have cache
        if ($attempt -eq 1 -and $useFallback) {
            Write-Host "      Attempt $attempt/4 ($($a.Label)) — may fail on 3.13, will fallback ..." -ForegroundColor DarkGray
        } else {
            Write-Host "      Attempt $attempt/4 ($($a.Label)) ..." -ForegroundColor DarkGray
        }
        # Always quote venvPy (spaces in path)
        & "$venvPy" -m pip @($a.Args) 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
        if ($LASTEXITCODE -eq 0) {
            # Verify import
            & "$venvPy" -c "import torch; print(f'torch {torch.__version__} cuda_built={torch.version.cuda} cuda_available={torch.cuda.is_available()}')" 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Green }
            if ($LASTEXITCODE -eq 0) {
                # Check that it's not cpu-only when driver exists
                $probe = & "$venvPy" -c "import torch; print(torch.version.cuda or 'cpu')" 2>&1
                Write-Host "      Installed via $($a.Label): $probe" -ForegroundColor Green
                $installed = $true
                if ($a.Label -like "cpu*") {
                    Write-Host "      NOTE: CPU torch installed — transcription will run on CPU (slower but works)." -ForegroundColor Yellow
                    Write-Host "      For GPU, install Python 3.11 and re-run install.ps1, or ensure internet for CUDA wheel." -ForegroundColor Yellow
                }
                break
            }
        } else {
            Write-Host "      Attempt failed (non-fatal, trying fallback) ..." -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 1
    }

    if (-not $installed) {
        Write-Host "ERROR: All torch install attempts failed. Check internet and Python version." -ForegroundColor Red
        Write-Host "  Recommended: install Python 3.11 64-bit, then:  .\install.ps1" -ForegroundColor Yellow
        Write-Host "  Or manual:  `"$venvPy`" -m pip install torch --extra-index-url https://download.pytorch.org/whl/cu121" -ForegroundColor Yellow
        return $false
    }
    # Final verify
    Write-Host "      Verifying torch CUDA ..." -ForegroundColor DarkGray
    & "$venvPy" -c "import torch; print(f'torch {torch.__version__} cuda_built={torch.version.cuda} cuda_available={torch.cuda.is_available()}'); import sys; print(sys.executable)" 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Green }
    return $true
}

$torchOk = Install-Torch -venvPy $venvPy
if (-not $torchOk) {
    Write-Host "Continuing without CUDA torch — app will use CPU mode. You can retry torch later." -ForegroundColor Yellow
}

# 5. Install app + transcribe deps (torch already present, resolver won't downgrade to CPU if we use --no-deps for torch? pip will respect existing)
Write-Host "[5/6] Installing app deps (customtkinter, pillow) ..." -ForegroundColor Yellow
& "$venvPy" -m pip install -r "app/requirements.txt"
if ($LASTEXITCODE -ne 0) { Write-Host "app requirements: some failed (see above, non-fatal)" -ForegroundColor Yellow }

Write-Host "[5/6] Installing transcribe deps (faster-whisper, soundfile, av, cudnn) ..." -ForegroundColor Yellow
& "$venvPy" -m pip install -r "transcribe/requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "transcribe requirements: some failed — checking if faster-whisper at least present ..." -ForegroundColor Yellow
    & "$venvPy" -c "import faster_whisper; print('faster-whisper', faster_whisper.__version__)" 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
}

# 6. Verify (foolproof: handle missing venv/tool)
Write-Host "[6/6] Running CUDA diagnostic ..." -ForegroundColor Yellow
if (Test-Path -LiteralPath "tools/check_cuda.py") {
    & "$venvPy" "tools/check_cuda.py" 2>&1 | ForEach-Object { Write-Host $_ }
} else {
    & "$venvPy" -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())" 2>&1 | ForEach-Object { Write-Host $_ }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Install finished!" -ForegroundColor Green
if ($torchOk) {
    Write-Host " Launch GUI via VENV (robust, avoids yellow badge):" -ForegroundColor Cyan
} else {
    Write-Host " Launch GUI (CPU mode, torch CUDA not installed):" -ForegroundColor Yellow
}
Write-Host "   .\launch.bat                (double-click, always works)" -ForegroundColor White
Write-Host "   .\venv\Scripts\python app\main.py" -ForegroundColor White
Write-Host "   powershell -ExecutionPolicy Bypass -File .\launch.ps1" -ForegroundColor White
Write-Host " If badge still yellow:  .\venv\Scripts\python tools/check_cuda.py" -ForegroundColor Yellow
if ($pyMajorMinor -eq "3.13" -or $pyMajorMinor -eq "3.14") {
    Write-Host " Python $pyMajorMinor note: for best CUDA, use Python 3.11 (cu121 has no 3.13 wheel, fallback is cu124)." -ForegroundColor Yellow
}
Write-Host " RTX 2050 4GB tip: default beam=1 (low VRAM). Set preset Balanced or use turbo model for 2x speed." -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Green
# Keep window open when double-clicked
if ($Host.Name -match "ConsoleHost") { Write-Host "Press Enter to close..."; Read-Host | Out-Null }
