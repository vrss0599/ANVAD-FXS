"""
Readiness checker for UGA-SUB desktop app.

Each check returns:
  {"ok": bool, "label": str, "detail": str, "fix_hint": str|None, "fix_cmd": str|None}

UX: Every check is wrapped in try/except so one failure never blocks others.
"""

import sys
import shutil
from pathlib import Path


def _is_in_venv() -> bool:
    """Detect if Python is running inside a virtual environment."""
    # Standard detection: sys.prefix differs from sys.base_prefix inside a venv
    return sys.prefix != sys.base_prefix


def _find_project_root() -> Path:
    """Find the project root (contains transcribe/ and resolve_free/)."""
    # From app/core/readiness.py -> go up 2 levels to project root
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "transcribe").is_dir():
        return candidate
    # Fallback: walk up from cwd
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
    # Also check if we're already in a venv
    if _is_in_venv():
        return sys.executable
    return sys.executable


def check_single(name: str) -> dict:
    """Run a single readiness check by name."""

    if name == "python":
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return {
            "ok": True,
            "label": f"Python {ver}",
            "detail": sys.executable,
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
                # Running inside a venv — that's what we want
                return {
                    "ok": True,
                    "label": "Virtual Environment",
                    "detail": f"Active: {sys.prefix}",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            elif venv_exists:
                # venv folder exists but not activated
                return {
                    "ok": False,
                    "warning": True,
                    "label": "Virtual Environment",
                    "detail": "venv exists but not activated",
                    "fix_hint": "Activate before launching: .\\venv\\Scripts\\activate",
                    "fix_cmd": ".\\venv\\Scripts\\Activate.ps1",
                }
            else:
                return {
                    "ok": False,
                    "label": "Virtual Environment",
                    "detail": "No venv found",
                    "fix_hint": "Create virtual environment",
                    "fix_cmd": "python -m venv venv && .\\venv\\Scripts\\activate && pip install -r transcribe/requirements.txt",
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
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram = f"{props.total_memory / 1024**3:.1f}GB"
                return {
                    "ok": True,
                    "label": f"GPU: {device_name}",
                    "detail": f"{device_name} ({vram})",
                    "fix_hint": None,
                    "fix_cmd": None,
                }
            else:
                # torch is installed but CUDA not available.
                # Check if this is a CPU-only torch on a machine WITH an NVIDIA GPU.
                torch_cuda_built = hasattr(torch.version, "cuda") and torch.version.cuda is not None
                has_nvidia_driver = shutil.which("nvidia-smi") is not None

                if not has_nvidia_driver:
                    # Also check Windows DriverStore for nvidia-smi
                    import glob
                    nvsmi_candidates = glob.glob(r"C:\Windows\System32\DriverStore\FileRepository\nv*\nvidia-smi.exe")
                    has_nvidia_driver = len(nvsmi_candidates) > 0

                if has_nvidia_driver and not torch_cuda_built:
                    # GPU exists but torch is CPU-only build — most common mistake
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (wrong PyTorch)",
                        "detail": f"NVIDIA GPU detected but PyTorch {torch.__version__} is CPU-only build",
                        "fix_hint": "Reinstall PyTorch with CUDA support",
                        "fix_cmd": "pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121",
                    }
                elif has_nvidia_driver and torch_cuda_built:
                    # GPU + CUDA torch but still not available — driver mismatch?
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU (driver issue)",
                        "detail": f"PyTorch has CUDA {torch.version.cuda} but torch.cuda.is_available()=False",
                        "fix_hint": "Update NVIDIA driver to latest from nvidia.com/drivers",
                        "fix_cmd": None,
                    }
                else:
                    # No GPU at all
                    return {
                        "ok": False,
                        "label": "GPU Acceleration",
                        "detail": "No NVIDIA GPU detected — will use CPU (slower but works)",
                        "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                        "fix_cmd": None,
                    }
        except ImportError:
            # torch not installed — check nvidia-smi as fallback
            try:
                nvsmi = shutil.which("nvidia-smi")
                if nvsmi:
                    return {
                        "ok": False,
                        "warning": True,
                        "label": "GPU Acceleration",
                        "detail": "NVIDIA driver found but PyTorch not installed with CUDA",
                        "fix_hint": "Install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu121",
                        "fix_cmd": "pip install torch --index-url https://download.pytorch.org/whl/cu121",
                    }
            except Exception:
                pass
            return {
                "ok": False,
                "label": "GPU Acceleration",
                "detail": "No NVIDIA GPU detected — will use CPU",
                "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                "fix_cmd": None,
            }
        except Exception as e:
            return {"ok": False, "label": "GPU Acceleration", "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}

    elif name == "faster_whisper":
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
            return {
                "ok": False,
                "label": "faster-whisper",
                "detail": "Module not found",
                "fix_hint": "Install faster-whisper in venv",
                "fix_cmd": "pip install faster-whisper>=1.2.0",
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
