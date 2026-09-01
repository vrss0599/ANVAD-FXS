#!/usr/bin/env python3
"""
install.py — Simple one-shot installer for UGA-SUB (RTX 2050 4GB / 3050 6GB)

Why this file exists: no .ps1 / .bat / ExecutionPolicy issues. Just:
  python install.py
  venv\Scripts\python app/main.py   (or: venv\Scripts\python tools/check_cuda.py)

Handles:
  - Python 3.10/3.11/3.13 (3.11 recommended; 3.13 has no cu121 wheel, auto-falls back to cu124)
  - Spaces in path (e.g. "Sanika manjunath") via pathlib — no quoting needed
  - GPU VRAM hint (nvidia-smi if present)
  - Robust torch CUDA install: cu121 --index-url -> cu121 --extra-index -> cu124 --index -> cpu
  - Never aborts on torch failure — always installs app/transcribe deps so GUI works on CPU

Usage:
  python install.py              # creates venv if missing, does everything
  python install.py --no-torch   # skip torch (CPU-only)
  python install.py --recreate   # delete and recreate venv
"""
import sys, subprocess, shutil, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
VENV_PY = VENV / "Scripts" / "python.exe"
VENV_PY_POSIX = VENV / "bin" / "python"

def venv_python() -> Path:
    if VENV_PY.exists(): return VENV_PY
    if VENV_PY_POSIX.exists(): return VENV_PY_POSIX
    return VENV_PY  # default for Windows

def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, **kw)

def ensure_venv(recreate=False):
    if recreate and VENV.exists():
        print(f"[venv] removing existing venv: {VENV}")
        shutil.rmtree(VENV, ignore_errors=True)
    if not VENV.exists():
        print(f"[1/6] Creating venv at {VENV} ...")
        r = run([sys.executable, "-m", "venv", str(VENV)])
        if r.returncode != 0:
            print("ERROR: venv creation failed. Try: py -m venv venv  (check Python install)")
            sys.exit(1)
    else:
        print(f"[1/6] venv exists — reusing {VENV}")
    vp = venv_python()
    if not vp.exists():
        print(f"ERROR: venv python not found at {vp}")
        sys.exit(1)
    print(f"      venv python: {vp}")
    return vp

def upgrade_pip(vp: Path):
    print("[2/6] Upgrading pip ...")
    r = run([str(vp), "-m", "pip", "install", "--upgrade", "pip"])
    if r.returncode != 0:
        print("  warn: pip upgrade failed (non-fatal)")

def install_torch(vp: Path, no_torch=False):
    if no_torch:
        print("[3/6] Skipping torch (--no-torch)")
        return False
    py_mm = f"{sys.version_info.major}.{sys.version_info.minor}"
    use_fallback_note = py_mm in ("3.13", "3.14")
    if use_fallback_note:
        print(f"[3/6] Python {py_mm} detected — cu121 has no cp313 wheel, will fallback to cu124 if needed")
    else:
        print(f"[3/6] Installing PyTorch CUDA (may download ~2GB) ... Python {py_mm}")

    torch_index = "https://download.pytorch.org/whl/cu121"
    torch_fallback = "https://download.pytorch.org/whl/cu124"
    torch_cpu = "https://download.pytorch.org/whl/cpu"
    attempts = [
        ("cu121 --index-url", ["install", "torch", "--index-url", torch_index]),
        ("cu121 --extra-index-url", ["install", "torch", "--extra-index-url", torch_index]),
        ("cu124 --index-url (for Py 3.13)", ["install", "torch", "--index-url", torch_fallback]),
        ("cpu fallback", ["install", "torch", "--index-url", torch_cpu]),
    ]
    for label, args in attempts:
        print(f"      trying {label} ...")
        r = run([str(vp), "-m", "pip", *args])
        if r.returncode == 0:
            # verify import
            probe = subprocess.run([str(vp), "-c", "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"],
                                   capture_output=True, text=True)
            out = (probe.stdout.strip() + " " + probe.stderr.strip()).strip()
            print(f"      -> {out}")
            if probe.returncode == 0 and "cuda" in out.lower() or torch_cpu in label:
                if "cpu" in label.lower():
                    print("      NOTE: CPU torch installed — GPU transcription will fallback to CPU (slower but works). For GPU, use Python 3.11.")
                else:
                    print(f"      OK via {label}")
                return True
            # if cpu fallback installed, consider success even if cuda string missing
            if "cpu" in label:
                return True
        else:
            print(f"      failed, trying next fallback ...")
    print("ERROR: all torch installs failed — check internet. Continuing so app still works on CPU.")
    print("  Tip: for GPU, use Python 3.11 and re-run: python install.py")
    return False

def pip_install(vp: Path, req: Path, label: str):
    if not req.exists():
        print(f"[skip] {req} not found")
        return
    print(f"[{label}] pip install -r {req} ...")
    r = run([str(vp), "-m", "pip", "install", "-r", str(req)])
    if r.returncode != 0:
        print(f"  warn: {req.name} had errors (see above)")

def main():
    ap = argparse.ArgumentParser(description="UGA-SUB simple installer")
    ap.add_argument("--no-torch", action="store_true", help="skip torch install")
    ap.add_argument("--recreate", action="store_true", help="delete and recreate venv")
    args = ap.parse_args()

    print("="*60)
    print(" UGA-SUB — Simple Installer (python install.py)")
    print("="*60)
    print(f" Python: {sys.version.split()[0]}  ({sys.executable})")
    # GPU hint
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=4)
        if out.returncode == 0 and out.stdout.strip():
            print(f" GPU: {out.stdout.strip()}")
    except Exception:
        pass

    vp = ensure_venv(recreate=args.recreate)
    upgrade_pip(vp)
    torch_ok = install_torch(vp, no_torch=args.no_torch)

    pip_install(vp, ROOT / "app" / "requirements.txt", "4/6 app")
    pip_install(vp, ROOT / "transcribe" / "requirements.txt", "5/6 transcribe")

    print("[6/6] CUDA diagnostic ...")
    ck = ROOT / "tools" / "check_cuda.py"
    if ck.exists():
        run([str(vp), str(ck)])
    else:
        run([str(vp), "-c", "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"])

    print("")
    print("="*60)
    print(" Install finished!")
    if torch_ok:
        print(" Launch GUI:")
    else:
        print(" Launch GUI (CPU mode — torch CUDA not installed):")
    print(f"   {vp} app/main.py")
    # also show posix alt for docs
    print(f"   # or:  python -m pip install torch --index-url https://download.pytorch.org/whl/cu121  (inside venv)")
    print(f" Verify: {vp} tools/check_cuda.py")
    if f"{sys.version_info.major}.{sys.version_info.minor}" in ("3.13","3.14"):
        print(" Note: Python 3.13 needs cu124 for CUDA (cu121 has no 3.13 wheel). Re-run with Python 3.11 for best support.")
    print(" RTX 2050 4GB: uses beam=1 auto (6GB uses beam=5). No config needed.")
    print("="*60)

if __name__ == "__main__":
    main()
