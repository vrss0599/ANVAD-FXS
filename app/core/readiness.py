"""
Readiness checker for UGA-SUB desktop app.

Each check returns:
  {"ok": bool, "label": str, "detail": str, "fix_hint": str|None, "fix_cmd": str|None}

Robust GPU check: probes BOTH system python (sys.executable) and venv python
via subprocess so launch method (activated vs double-click) and stale import
cache cannot cause a false yellow. Slightly slower (~0.5-1s) but 100% accurate.
"""

import sys
import shutil
import subprocess
import json
from pathlib import Path


def _is_in_venv() -> bool:
    """Detect if Python is running inside a virtual environment."""
    return sys.prefix != sys.base_prefix


def _find_project_root() -> Path:
    """Find the project root (contains transcribe/ and resolve_free/)."""
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "transcribe").is_dir():
        return candidate
    cwd = Path.cwd()
    if (cwd / "transcribe").is_dir():
        return cwd
    return candidate


def get_venv_python() -> str:
    """Returns path to venv python.exe if it exists, else sys.executable."""
    root = _find_project_root()
    venv_py = root / "venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    if _is_in_venv():
        return sys.executable
    return sys.executable


def _probe_torch_via_subprocess(python_exe: str, timeout: float = 15.0) -> dict | None:
    """Probe python_exe for torch/CUDA via a temp script (avoids -c quoting/try issues on Windows)."""
    import tempfile, textwrap
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
            r = subprocess.run(
                [python_exe, tf_path],
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if r.returncode != 0 or not r.stdout.strip():
                return None
            return json.loads(r.stdout.strip())
        finally:
            try:
                Path(tf_path).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        return None


def _has_nvidia_driver() -> bool:
    if shutil.which("nvidia-smi"):
        return True
    try:
        import glob
        cands = glob.glob(r"C:\Windows\System32\DriverStore\FileRepository\nv*\nvidia-smi.exe")
        if cands:
            return True
    except Exception:
        pass
    return False


def check_single(name: str) -> dict:
    """Run a single readiness check by name."""

    if name == "python":
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        venv_py = get_venv_python()
        launched_in_venv = Path(sys.executable).resolve() == Path(venv_py).resolve() if Path(venv_py).exists() else _is_in_venv()
        detail = sys.executable
        if not launched_in_venv and Path(venv_py).exists():
            detail += f" (system) | venv: {venv_py}"
        return {
            "ok": True,
            "label": f"Python {ver}",
            "detail": detail,
            "fix_hint": None,
            "fix_cmd": None,
        }

    elif name == "venv":
        try:
            in_venv = _is_in_venv()
            root = _find_project_root()
            venv_dir = root / "venv"
            venv_exists = venv_dir.is_dir()

            if in_venv:
                return {
                    "ok": True,
                    "label": "Virtual Environment",
                    "detail": f"Active: {sys.prefix}",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            elif venv_exists:
                # venv exists but GUI not launched from it — show warning with correct launch cmd
                venv_py = get_venv_python()
                return {
                    "ok": False,
                    "warning": True,
                    "label": "Virtual Environment",
                    "detail": f"venv exists but not activated (GUI launched via system python: {Path(sys.executable).name})",
                    "fix_hint": "Relaunch via venv python for correct CUDA detection",
                    "fix_cmd": f"{venv_py} app\\main.py",
                }
            else:
                return {
                    "ok": False,
                    "label": "Virtual Environment",
                    "detail": "No venv found",
                    "fix_hint": "Create virtual environment",
                    "fix_cmd": "python -m venv venv && .\\venv\\Scripts\\activate && .\\install.ps1",
                }
        except Exception as e:
            return {"ok": False, "label": "Virtual Environment", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    elif name == "ffmpeg":
        try:
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                return {
                    "ok": True,
                    "label": "FFmpeg",
                    "detail": f"Found: {ffmpeg_path}",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            else:
                return {
                    "ok": False,
                    "label": "FFmpeg",
                    "detail": "Not found on PATH",
                    "fix_hint": "Install FFmpeg for audio extraction (optional for WAV files)",
                    "fix_cmd": "winget install Gyan.FFmpeg",
                }
        except Exception as e:
            return {"ok": False, "label": "FFmpeg", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    elif name == "gpu":
        # --- Robust: probe venv python + system python via subprocess (slightly slower, 100% accurate) ---
        venv_py = get_venv_python()
        venv_exists = Path(venv_py).exists()
        launched_in_venv = Path(sys.executable).resolve() == Path(venv_py).resolve() if venv_exists else _is_in_venv()

        # Probe venv first (authoritative for transcription), then system if different
        results = {}
        if venv_exists:
            r = _probe_torch_via_subprocess(venv_py)
            if r is not None:
                results["venv"] = r
        # Only probe system if not same exe (avoid double subprocess)
        if not launched_in_venv or Path(sys.executable).resolve() != Path(venv_py).resolve():
            r2 = _probe_torch_via_subprocess(sys.executable)
            if r2 is not None:
                results["system"] = r2

        # Pick authoritative: venv if exists, else system
        primary_key = "venv" if "venv" in results else "system"
        primary = results.get(primary_key)
        has_driver = _has_nvidia_driver()

        # If we got a valid probe, decide based on it
        if primary is not None:
            # Check for import_error / generic error
            if "import_error" in primary or "error" in primary:
                # torch not installed in primary — but maybe other env has it
                other_key = "system" if primary_key == "venv" else "venv"
                other = results.get(other_key)
                if other and other.get("cuda_available"):
                    # Other env has CUDA — tell user they launched wrong python
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (venv mismatch)",
                        "detail": f"venv torch missing ({primary.get('import_error', primary.get('error','no torch'))}) but {other_key} has CUDA {other.get('torch_version')} — relaunch via venv",
                        "fix_hint": "GUI launched outside venv — relaunch via venv python",
                        "fix_cmd": f"{venv_py} app\\main.py",
                    }
                if has_driver:
                    venv_cmd = f"{venv_py} -m pip install torch --index-url https://download.pytorch.org/whl/cu121"
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU Acceleration",
                        "detail": f"NVIDIA driver found but PyTorch not installed in {primary_key} ({primary.get('import_error','no torch')})",
                        "fix_hint": "Install PyTorch with CUDA into venv",
                        "fix_cmd": venv_cmd,
                    }
                return {
                    "ok": False,
                    "label": "GPU Acceleration",
                    "detail": "No NVIDIA GPU detected — will use CPU (also no torch)",
                    "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                    "fix_cmd": None,
                }

            # torch is installed — check cuda_available
            if primary.get("cuda_available"):
                name_ = primary.get("device_name") or "GPU"
                vram = primary.get("vram_gb")
                vram_s = f"{vram:.1f}GB" if vram else ""
                # If launched outside venv but venv also has CUDA, note it
                extra = ""
                if not launched_in_venv and "venv" in results and results["venv"].get("cuda_available"):
                    extra = " (venv CUDA ok)"
                elif not launched_in_venv and venv_exists:
                    extra = " (system CUDA ok — consider launching via venv)"
                return {
                    "ok": True,
                    "label": f"GPU: {name_}",
                    "detail": f"{name_} ({vram_s}){extra}",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            else:
                # torch installed but cuda not available
                cuda_built = primary.get("cuda_built")
                ver = primary.get("torch_version", "unknown")
                other = results.get("system" if primary_key == "venv" else "venv")
                # If other env HAS cuda, user launched wrong python — surface mismatch
                if other and other.get("cuda_available"):
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (venv mismatch)",
                        "detail": f"{primary_key} torch {ver} cuda_available=False but {('system' if primary_key=='venv' else 'venv')} has CUDA {other.get('device_name')} — relaunch via venv",
                        "fix_hint": "Relaunch GUI via venv python for CUDA",
                        "fix_cmd": f"{venv_py} app\\main.py",
                    }
                # CPU-only torch but driver exists
                if has_driver and not cuda_built:
                    venv_cmd = f"{venv_py} -m pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121"
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (wrong PyTorch)",
                        "detail": f"NVIDIA GPU detected but {primary_key} PyTorch {ver} is CPU-only (cuda_built={cuda_built})",
                        "fix_hint": "Reinstall PyTorch with CUDA into venv (yellow → green after reinstall)",
                        "fix_cmd": venv_cmd,
                    }
                elif has_driver and cuda_built:
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (driver issue)",
                        "detail": f"{primary_key} PyTorch CUDA {cuda_built} but cuda_available=False (driver {ver})",
                        "fix_hint": "Update NVIDIA driver to latest from nvidia.com/drivers, then restart",
                        "fix_cmd": None,
                    }
                else:
                    return {
                        "ok": False,
                        "label": "GPU Acceleration",
                        "detail": "No NVIDIA GPU detected — will use CPU (slower but works)",
                        "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                        "fix_cmd": None,
                    }

        # Subprocess probe failed entirely — fallback to in-process import for resilience
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram = f"{props.total_memory / 1024**3:.1f}GB"
                return {
                    "ok": True,
                    "label": f"GPU: {device_name}",
                    "detail": f"{device_name} ({vram}) [fallback probe]",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            else:
                torch_cuda_built = hasattr(torch.version, "cuda") and torch.version.cuda is not None
                has_nvidia_driver = _has_nvidia_driver()
                if has_nvidia_driver and not torch_cuda_built:
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (wrong PyTorch)",
                        "detail": f"NVIDIA GPU detected but PyTorch {torch.__version__} is CPU-only",
                        "fix_hint": "Reinstall PyTorch with CUDA (run install.ps1 again)",
                        "fix_cmd": f"{venv_py} -m pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121",
                    }
                elif has_nvidia_driver and torch_cuda_built:
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (driver issue)",
                        "detail": f"PyTorch CUDA {torch.version.cuda} but cuda_available=False",
                        "fix_hint": "Update NVIDIA driver",
                        "fix_cmd": None,
                    }
                else:
                    return {
                        "ok": False,
                        "label": "GPU Acceleration",
                        "detail": "No NVIDIA GPU — will use CPU",
                        "fix_hint": "Install NVIDIA drivers or use CPU mode",
                        "fix_cmd": None,
                    }
        except ImportError:
            if _has_nvidia_driver():
                return {
                    "ok": False,
                    "warning": True,
                    "label": "GPU Acceleration",
                    "detail": "NVIDIA driver found but PyTorch not installed",
                    "fix_hint": "Run install.ps1 to install CUDA PyTorch into venv",
                    "fix_cmd": f"{venv_py} -m pip install torch --index-url https://download.pytorch.org/whl/cu121",
                }
            return {
                "ok": False,
                "label": "GPU Acceleration",
                "detail": "No NVIDIA GPU — will use CPU",
                "fix_hint": "Install NVIDIA drivers or use CPU mode",
                "fix_cmd": None,
            }
        except Exception as e:
            return {"ok": False, "label": "GPU Acceleration", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    elif name == "faster_whisper":
        # Also probe venv first if GUI not in venv — slightly slower but robust
        venv_py = get_venv_python()
        if Path(venv_py).exists() and Path(sys.executable).resolve() != Path(venv_py).resolve():
            r = _probe_torch_via_subprocess(venv_py)  # warm cache, but actually probe faster_whisper separately
            # Quick subprocess check for faster_whisper in venv
            try:
                code = "import faster_whisper,json; print(json.dumps({'ver': getattr(faster_whisper,'__version__','unknown')}))"
                pr = subprocess.run([venv_py, "-c", code], capture_output=True, text=True, timeout=4.0,
                                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                if pr.returncode == 0 and pr.stdout.strip():
                    j = json.loads(pr.stdout.strip())
                    return {"ok": True, "label": f"faster-whisper {j.get('ver','unknown')} (venv)", "detail": f"Version {j.get('ver')} in venv", "fix_hint": None, "fix_cmd": None}
            except Exception:
                pass
        try:
            import faster_whisper
            ver = getattr(faster_whisper, "__version__", "unknown")
            return {
                "ok": True,
                "label": f"faster-whisper {ver}",
                "detail": f"Version {ver}",
                "fix_hint": None,
                "fix_cmd": None,
            }
        except ImportError:
            venv_py2 = get_venv_python()
            return {
                "ok": False,
                "label": "faster-whisper",
                "detail": "Module not found in this python (try venv)",
                "fix_hint": "Install into venv",
                "fix_cmd": f"{venv_py2} -m pip install faster-whisper>=1.2.0",
            }
        except Exception as e:
            return {"ok": False, "label": "faster-whisper", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    elif name == "model_cache":
        try:
            hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
            if hf_cache.exists():
                models = [d.name for d in hf_cache.iterdir() if d.is_dir() and "whisper" in d.name.lower()]
                if models:
                    short = [m.replace("models--", "").replace("Systran--faster-", "") for m in models]
                    return {
                        "ok": True,
                        "label": f"Model Cache ({len(models)})",
                        "detail": ", ".join(short),
                        "fix_hint": None,
                        "fix_cmd": None,
                    }
                else:
                    return {
                        "ok": True,
                        "label": "Model Cache",
                        "detail": "No Whisper models cached yet",
                        "fix_hint": "Models download automatically on first transcription (~2.9GB for large-v3)",
                        "fix_cmd": None,
                    }
            else:
                return {
                    "ok": True,
                    "label": "Model Cache",
                    "detail": "HuggingFace cache directory will be created on first run",
                    "fix_hint": "Models download automatically on first transcription (~2.9GB for large-v3)",
                    "fix_cmd": None,
                }
        except Exception as e:
            return {"ok": False, "label": "Model Cache", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    return {"ok": False, "label": name, "detail": "Unknown check", "fix_hint": None, "fix_cmd": None}


def check_all() -> dict[str, dict]:
    """Run all readiness checks. Each check is isolated — one failure doesn't block others."""
    checks = ["python", "venv", "ffmpeg", "gpu", "faster_whisper", "model_cache"]
    results = {}
    for check_name in checks:
        try:
            results[check_name] = check_single(check_name)
        except Exception as e:
            results[check_name] = {
                "ok": False,
                "label": check_name,
                "detail": f"Error: {e}",
                "fix_hint": "Internal error running check",
                "fix_cmd": None,
            }
    return results
