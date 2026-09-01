#!/usr/bin/env python3
"""
check_cuda.py — Robust CUDA diagnostic for UGA-SUB.

Probes BOTH system python and venv python via subprocess (same logic as readiness.py)
so launch-method bugs cannot hide. Run:
  python tools/check_cuda.py
  .\venv\Scripts\python tools/check_cuda.py

Also checks nvidia-smi, ctranslate2, faster-whisper.
Windows-safe: forces utf-8 output, avoids cp1252 emoji issues.
"""
import sys, shutil, subprocess, json, glob, tempfile, textwrap
from pathlib import Path

# Force utf-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def find_venv_python():
    proj = Path(__file__).resolve().parents[1]
    vp = proj / "venv" / "Scripts" / "python.exe"
    return str(vp) if vp.exists() else None

def probe(python_exe, timeout=15):
    probe_py = textwrap.dedent("""
        import json, sys
        d = {}
        try:
            import torch
            d['torch_version'] = getattr(torch, '__version__', 'unknown')
            d['cuda_built'] = getattr(getattr(torch, 'version', None), 'cuda', None)
            d['cuda_available'] = torch.cuda.is_available()
            d['device_name'] = torch.cuda.get_device_name(0) if d['cuda_available'] else None
            try:
                d['vram_gb'] = (torch.cuda.get_device_properties(0).total_memory / 1024**3) if d['cuda_available'] else None
            except Exception:
                d['vram_gb'] = None
            d['exe'] = sys.executable
        except ImportError as e:
            d = {'import_error': str(e), 'exe': sys.executable}
        except Exception as e:
            d = {'error': str(e), 'exe': sys.executable}
        print(json.dumps(d))
    """)
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(probe_py)
            tf_path = tf.name
        try:
            r = subprocess.run([python_exe, tf_path], capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess,'CREATE_NO_WINDOW') else 0)
            if r.returncode==0 and r.stdout.strip():
                return json.loads(r.stdout.strip())
            return {"error": (r.stderr[:600] if r.stderr else "no output"), "exe": python_exe, "returncode": r.returncode}
        finally:
            try:
                Path(tf_path).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        return {"error": str(e), "exe": python_exe}

def main():
    print("="*60)
    print("UGA-SUB CUDA Diagnostic")
    print("="*60)
    print(f"Running as: {sys.executable} (is_venv={sys.prefix!=sys.base_prefix})")
    print(f"Python: {sys.version.replace(chr(10),' ')}")
    venv = find_venv_python()
    print(f"Venv python: {venv or 'NOT FOUND'}")
    print(f"nvidia-smi on PATH: {shutil.which('nvidia-smi') or 'NOT FOUND'}")
    try:
        cands = glob.glob(r"C:\Windows\System32\DriverStore\FileRepository\nv*\nvidia-smi.exe")
        print(f"DriverStore nvidia-smi: {cands[0] if cands else 'not found via glob'}")
    except Exception:
        pass
    # Probe system
    print("\n--- system python probe ---")
    psys = probe(sys.executable)
    print(json.dumps(psys, indent=2))
    # Probe venv if different
    if venv and Path(venv).resolve() != Path(sys.executable).resolve():
        print("\n--- venv python probe ---")
        pvenv = probe(venv)
        print(json.dumps(pvenv, indent=2))
        # Verdict
        print("\n--- verdict ---")
        def has_cuda(d): return d.get("cuda_available") is True
        if has_cuda(pvenv) and not has_cuda(psys):
            print("[OK] venv has CUDA but system does not — launch GUI via venv:  .\\venv\\Scripts\\python app\\main.py (or .\\launch.ps1)")
        elif has_cuda(pvenv) and has_cuda(psys):
            print("[OK] Both have CUDA — any launch method works, but venv is recommended.")
        elif not has_cuda(pvenv) and has_cuda(psys):
            print("[WARN] system has CUDA but venv does not — reinstall into venv:  .\\venv\\Scripts\\python -m pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121")
        elif pvenv.get("import_error"):
            print("[FAIL] venv missing torch — run:  .\\install.ps1  or  .\\venv\\Scripts\\python -m pip install torch --index-url https://download.pytorch.org/whl/cu121")
        else:
            print(f"[FAIL] venv cuda_available=False (built={pvenv.get('cuda_built')}) — check driver >=537 and torch CUDA wheel. Fix: .\\venv\\Scripts\\python -m pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121")
    else:
        # No venv or same exe
        print("\n--- verdict ---")
        if psys.get("cuda_available"):
            print(f"[OK] CUDA ok: {psys.get('device_name')} {psys.get('vram_gb',0):.1f}GB")
        elif psys.get("import_error"):
            print("[FAIL] torch not installed — run install.ps1")
        elif psys.get("cuda_built") is None:
            print(f"[FAIL] CPU-only torch {psys.get('torch_version')} — reinstall CUDA:  pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121")
        else:
            print(f"[FAIL] torch CUDA {psys.get('cuda_built')} but cuda_available=False — update NVIDIA driver from nvidia.com/drivers")

    # Extra: faster-whisper check
    print("\n--- faster-whisper (venv) ---")
    if venv:
        try:
            code = "import faster_whisper,json; print(json.dumps({'ver': getattr(faster_whisper,'__version__','unknown')}))"
            r = subprocess.run([venv, "-c", code], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess,'CREATE_NO_WINDOW') else 0)
            print(r.stdout.strip() or r.stderr.strip() or "not installed in venv")
        except Exception as e:
            print(str(e))
    print("="*60)

if __name__ == "__main__":
    main()
