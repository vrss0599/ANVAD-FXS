import sys
import shutil
from pathlib import Path

def get_venv_python() -> str:
    venv_py = Path(__file__).resolve().parents[2] / 'venv' / 'Scripts' / 'python.exe'
    if venv_py.exists():
        return str(venv_py)
    return sys.executable

def check_single(name: str) -> dict:
    if name == 'python':
        return {
            "ok": True,
            "label": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "detail": sys.executable,
            "fix_hint": None,
            "fix_cmd": None
        }
    elif name == 'venv':
        try:
            venv_py = Path(__file__).resolve().parents[1] / 'venv' / 'Scripts' / 'python.exe'
            ok = venv_py.exists()
            return {
                "ok": ok,
                "label": "Virtual Environment",
                "detail": "venv found" if ok else "venv missing",
                "fix_hint": "Create virtual environment" if not ok else None,
                "fix_cmd": "python -m venv venv && .\\venv\\Scripts\\activate && pip install -r transcribe/requirements.txt" if not ok else None
            }
        except Exception as e:
            return {"ok": False, "label": "Virtual Environment", "detail": str(e), "fix_hint": None, "fix_cmd": None}
    elif name == 'ffmpeg':
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            ok = ffmpeg_path is not None
            return {
                "ok": ok,
                "label": "FFmpeg",
                "detail": "FFmpeg found" if ok else "FFmpeg missing",
                "fix_hint": "Install FFmpeg for audio extraction" if not ok else None,
                "fix_cmd": "winget install Gyan.FFmpeg" if not ok else None
            }
        except Exception as e:
            return {"ok": False, "label": "FFmpeg", "detail": str(e), "fix_hint": None, "fix_cmd": None}
    elif name == 'gpu':
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram = f"{props.total_memory / 1024**3:.1f}GB"
                return {
                    "ok": True,
                    "label": "GPU Acceleration",
                    "detail": f"{device_name} ({vram})",
                    "fix_hint": None,
                    "fix_cmd": None
                }
            else:
                return {
                    "ok": False,
                    "label": "GPU Acceleration",
                    "detail": "CUDA not available",
                    "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                    "fix_cmd": None
                }
        except ImportError:
            try:
                import subprocess
                res = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
                if res.returncode == 0:
                    return {
                        "ok": True,
                        "label": "GPU Acceleration",
                        "detail": "NVIDIA driver found, PyTorch missing",
                        "fix_hint": "Install PyTorch with CUDA support",
                        "fix_cmd": None
                    }
                else:
                    raise Exception()
            except Exception:
                return {
                    "ok": False,
                    "label": "GPU Acceleration",
                    "detail": "PyTorch and nvidia-smi not found",
                    "fix_hint": "Install NVIDIA drivers or use CPU mode (slower)",
                    "fix_cmd": None
                }
        except Exception as e:
            return {"ok": False, "label": "GPU Acceleration", "detail": str(e), "fix_hint": None, "fix_cmd": None}
    elif name == 'faster_whisper':
        try:
            import faster_whisper
            return {
                "ok": True,
                "label": "faster-whisper",
                "detail": f"Version {faster_whisper.__version__}",
                "fix_hint": None,
                "fix_cmd": None
            }
        except ImportError:
            return {
                "ok": False,
                "label": "faster-whisper",
                "detail": "Module not found",
                "fix_hint": "Install faster-whisper in venv",
                "fix_cmd": "pip install faster-whisper>=1.2.0"
            }
        except Exception as e:
            return {"ok": False, "label": "faster-whisper", "detail": str(e), "fix_hint": None, "fix_cmd": None}
    elif name == 'model_cache':
        try:
            hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub'
            if hf_cache.exists():
                models = [d.name for d in hf_cache.iterdir() if d.is_dir() and 'whisper' in d.name.lower()]
                return {
                    "ok": True,
                    "label": "Model Cache",
                    "detail": f"{len(models)} models found: {', '.join(models)}" if models else "No models cached",
                    "fix_hint": "Models download automatically on first transcription run" if not models else None,
                    "fix_cmd": None
                }
            else:
                return {
                    "ok": True,
                    "label": "Model Cache",
                    "detail": "Cache directory not found",
                    "fix_hint": "Models download automatically on first transcription run",
                    "fix_cmd": None
                }
        except Exception as e:
            return {
                "ok": False,
                "label": "Model Cache",
                "detail": str(e),
                "fix_hint": None,
                "fix_cmd": None
            }
    return {}

def check_all() -> dict[str, dict]:
    checks = ['python', 'venv', 'ffmpeg', 'gpu', 'faster_whisper', 'model_cache']
    results = {}
    for check in checks:
        try:
            results[check] = check_single(check)
        except Exception as e:
            results[check] = {
                "ok": False,
                "label": check,
                "detail": f"Error: {str(e)}",
                "fix_hint": None,
                "fix_cmd": None
            }
    return results
