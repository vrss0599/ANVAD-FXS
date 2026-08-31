import sys
import subprocess
import threading
import queue
from pathlib import Path
from typing import Optional, Callable

class ScriptRunner:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
    
    def _get_python(self) -> str:
        """Find venv python or fall back to sys.executable."""
        # Check relative to this file: app/core/runner.py -> project_root/venv/Scripts/python.exe
        project_root = Path(__file__).resolve().parents[2]
        venv_py = project_root / "venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)
        return sys.executable
    
    def _get_project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]
    
    def run_extract(self, input_path: str, output_path: str, msg_queue: queue.Queue):
        """Run extract_audio.py in background thread."""
        root = self._get_project_root()
        script = root / "transcribe" / "extract_audio.py"
        cmd = [self._get_python(), str(script), "--input", input_path, "--out", output_path, "--overwrite"]
        self._run_cmd(cmd, msg_queue, root)
    
    def run_transcribe(self, input_path: str, model: str, task: str, msg_queue: queue.Queue, language: str = None, beam_size: int = 1, device: str = "auto"):
        """Run transcribe.py in background thread."""
        root = self._get_project_root()
        script = root / "transcribe" / "transcribe.py"
        cmd = [self._get_python(), str(script), "--input", input_path, "--model", model, "--task", task, "--beam_size", str(beam_size), "--device", device, "--exports_dir", str(root / "exports")]
        if language:
            cmd.extend(["--language", language])
        self._run_cmd(cmd, msg_queue, root)
    
    def run_verify(self, srt_path: str, msg_queue: queue.Queue, fix: bool = True):
        """Run verify_srt.py in background thread."""
        root = self._get_project_root()
        script = root / "transcribe" / "verify_srt.py"
        cmd = [self._get_python(), str(script), "--input", srt_path]
        if fix:
            cmd.append("--fix")
        self._run_cmd(cmd, msg_queue, root)
    
    def _run_cmd(self, cmd: list, msg_queue: queue.Queue, cwd: Path):
        """Launch subprocess in a background thread, stream stdout/stderr to msg_queue."""
        def worker():
            self.is_running = True
            msg_queue.put({"type": "started", "cmd": " ".join(cmd)})
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    cwd=str(cwd), bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                for line in self.process.stdout:
                    line = line.rstrip("\n\r")
                    if line:
                        msg_queue.put({"type": "log", "text": line})
                        # Try to parse progress from transcribe.py output
                        # Lines like: [0000.50 -> 0002.30] text (logprob=...)
                        # Lines like: [done] segments=42 time=12.3s RTF=50.2x
                        if line.startswith("[done]"):
                            msg_queue.put({"type": "progress", "value": 1.0})
                        elif line.startswith("[OK]"):
                            pass  # handled by return code
                
                self.process.wait()
                rc = self.process.returncode
                if rc == 0:
                    msg_queue.put({"type": "done", "returncode": 0})
                else:
                    msg_queue.put({"type": "error", "returncode": rc, "text": f"Process exited with code {rc}"})
            except FileNotFoundError as e:
                msg_queue.put({"type": "error", "returncode": -1, "text": f"Python not found: {e}"})
            except Exception as e:
                msg_queue.put({"type": "error", "returncode": -1, "text": str(e)})
            finally:
                self.is_running = False
                self.process = None
        
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
    
    def cancel(self):
        if self.process and self.is_running:
            try:
                self.process.kill()
            except Exception:
                pass
            self.is_running = False
