"""
Section 4 — Transcription: start/cancel button, progress bar, live log console.

UX-first:
- Start disabled until file selected + deps installed
- Progress bar: indeterminate during model load, determinate during transcription
- Live log: auto-scrolling monospace console showing real-time output
- Cancel button replaces Start during transcription
- Error state shows red banner with retry button + suggestions
"""

import customtkinter as ctk
import queue
import time
from pathlib import Path
from typing import Callable, Optional

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS


class SectionTranscribe(ctk.CTkFrame):
    """Section 4: Transcription — start + progress + log."""

    def __init__(self, master, on_complete: Optional[Callable] = None, **kwargs):
        super().__init__(master, corner_radius=DIM["card_corner"], **kwargs)
        self.configure(fg_color=COLORS["card"], border_color=COLORS["card_border"], border_width=1)
        self.on_complete = on_complete
        self._runner = None
        self._msg_queue = queue.Queue()
        self._is_running = False
        self._start_time: Optional[float] = None
        self._srt_path: Optional[str] = None
        self._pipeline_step = 0  # 0=idle, 1=extracting, 2=transcribing, 3=verifying

        # Header
        ctk.CTkLabel(
            self, text="4. Transcription",
            font=ctk.CTkFont(family=FONTS["heading"][0], size=FONTS["heading"][1], weight=FONTS["heading"][2]),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=PAD["card_inner"], pady=(PAD["card_inner"], PAD["small"]))

        # Action button row
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))

        self.start_btn = ctk.CTkButton(
            btn_row, text=f"{ICONS['play']}  Start Transcription",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1], weight="bold"),
            height=40, corner_radius=DIM["button_corner"],
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._on_start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True)

        self.cancel_btn = ctk.CTkButton(
            btn_row, text=f"{ICONS['stop']}  Cancel",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1], weight="bold"),
            height=40, corner_radius=DIM["button_corner"],
            fg_color=COLORS["error"], hover_color="#a02030",
            command=self._on_cancel,
        )
        self.cancel_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn.pack_forget()  # Hidden initially

        # Status label
        self.status_label = ctk.CTkLabel(
            self, text="Ready — select a file and click Start",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            text_color=COLORS["text_dim"],
        )
        self.status_label.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["small"]))

        # Progress bar
        self.progress = ctk.CTkProgressBar(
            self, height=DIM["progress_height"],
            corner_radius=6,
            progress_color=COLORS["accent"],
        )
        self.progress.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))
        self.progress.set(0)

        # Time info row
        self.time_row = ctk.CTkFrame(self, fg_color="transparent")
        self.time_row.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))

        self.elapsed_label = ctk.CTkLabel(
            self.time_row, text="",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        )
        self.elapsed_label.pack(side="left")

        self.rtf_label = ctk.CTkLabel(
            self.time_row, text="",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        )
        self.rtf_label.pack(side="right")

        # Live log console
        self.log_box = ctk.CTkTextbox(
            self, height=DIM["log_height"],
            font=ctk.CTkFont(family=FONTS["mono"][0], size=FONTS["mono"][1]),
            fg_color=COLORS["log_bg"],
            text_color=COLORS["log_fg"],
            corner_radius=8,
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=PAD["card_inner"], pady=(0, PAD["element"]))

        # Error banner (hidden)
        self.error_frame = ctk.CTkFrame(self, fg_color=COLORS["badge_err_bg"], corner_radius=8)
        self.error_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
        self.error_frame.pack_forget()

        self.error_icon = ctk.CTkLabel(
            self.error_frame, text=ICONS["cross"],
            font=ctk.CTkFont(size=16), text_color=COLORS["error"],
        )
        self.error_icon.grid(row=0, column=0, padx=(12, 4), pady=8)

        self.error_label = ctk.CTkLabel(
            self.error_frame, text="",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            text_color=COLORS["badge_err_fg"], wraplength=500, justify="left",
        )
        self.error_label.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=8)

        self.error_retry_btn = ctk.CTkButton(
            self.error_frame, text=f"{ICONS['retry']} Retry", width=70, height=28,
            font=ctk.CTkFont(size=11), corner_radius=4,
            fg_color=COLORS["error"], hover_color="#a02030",
            command=self._on_start,
        )
        self.error_retry_btn.grid(row=0, column=2, padx=(0, 12), pady=8)

        self.error_hint = ctk.CTkLabel(
            self.error_frame, text="",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"], wraplength=500, justify="left",
        )
        self.error_hint.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8))

        self.error_frame.grid_columnconfigure(1, weight=1)

        # Bottom spacer
        ctk.CTkFrame(self, fg_color="transparent", height=4).pack()

        # Internal state
        self._get_settings = None  # Set by parent: callable returning settings dict
        self._get_file_path = None  # Set by parent: callable returning selected file path
        self._get_audio_info = None  # Set by parent: callable returning audio info dict

    def bind_data_sources(self, get_file_path, get_settings, get_audio_info):
        """Called by the parent window to wire up data sources."""
        self._get_file_path = get_file_path
        self._get_settings = get_settings
        self._get_audio_info = get_audio_info

    def set_ready(self, ready: bool):
        """Enable/disable start button based on readiness."""
        self.start_btn.configure(state="normal" if ready else "disabled")

    def _on_start(self):
        if self._is_running:
            return

        # Validate
        file_path = self._get_file_path() if self._get_file_path else None
        if not file_path:
            self._show_error("No file selected", "Select an audio or video file in Section 2 above.")
            return

        settings = self._get_settings() if self._get_settings else {}
        audio_info = self._get_audio_info() if self._get_audio_info else {}

        # Clear previous state
        self.error_frame.pack_forget()
        self._clear_log()
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._start_time = time.time()

        # Switch to cancel button
        self.start_btn.pack_forget()
        self.cancel_btn.pack(side="left", fill="x", expand=True)
        self._is_running = True

        # Import runner
        from app.core.runner import ScriptRunner
        self._runner = ScriptRunner()
        self._msg_queue = queue.Queue()

        # Determine pipeline
        needs_extraction = audio_info.get("needs_extraction", False)
        if needs_extraction:
            self._pipeline_step = 1
            self.status_label.configure(text="Extracting audio from video...", text_color=COLORS["accent"])
            self._log("Pipeline: extract audio → transcribe → verify SRT")

            exports_dir = Path(file_path).parent
            try:
                from app.core.readiness import get_venv_python
                project_root = Path(__file__).resolve().parents[2]
                exports_dir = project_root / "exports"
                exports_dir.mkdir(exist_ok=True)
            except Exception:
                pass

            wav_out = str(exports_dir / (Path(file_path).stem + ".wav"))
            self._wav_path = wav_out
            self._runner.run_extract(file_path, wav_out, self._msg_queue)
        else:
            self._pipeline_step = 2
            self._wav_path = file_path
            self.status_label.configure(text="Loading model...", text_color=COLORS["accent"])
            self._log("Pipeline: transcribe → verify SRT")
            self._start_transcribe(file_path, settings)

        # Start polling
        self._poll()

    def _start_transcribe(self, audio_path: str, settings: dict):
        self._pipeline_step = 2
        self.status_label.configure(text=f"Transcribing with {settings.get('model', 'large-v3')}...", text_color=COLORS["accent"])
        self._runner.run_transcribe(
            input_path=audio_path,
            model=settings.get("model", "large-v3"),
            task=settings.get("task", "translate"),
            msg_queue=self._msg_queue,
            language=settings.get("language"),
            beam_size=settings.get("beam_size", 1),
            device=settings.get("device", "auto"),
        )

    def _start_verify(self, srt_path: str):
        self._pipeline_step = 3
        self.status_label.configure(text="Verifying SRT...", text_color=COLORS["accent"])
        self._runner.run_verify(srt_path, self._msg_queue, fix=True)

    def _poll(self):
        """Poll the message queue for updates from the background runner."""
        if not self._is_running:
            return

        try:
            while True:
                msg = self._msg_queue.get_nowait()
                msg_type = msg.get("type", "")

                if msg_type == "log":
                    text = msg.get("text", "")
                    self._log(text)

                    # Parse progress clues from transcribe.py output
                    if text.startswith("[model] loaded"):
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress.set(0.05)
                        self.status_label.configure(text="Model loaded — transcribing...")

                    elif text.startswith("[") and "->" in text and "logprob=" in text:
                        # Segment line — estimate progress from timestamps
                        try:
                            ts = text.split("]")[0].lstrip("[").strip()
                            end_ts = float(ts.split("->")[1].strip().split("]")[0].strip())
                            audio_info = self._get_audio_info() if self._get_audio_info else {}
                            total_dur = audio_info.get("duration_s", 0)
                            if total_dur > 0:
                                pct = min(0.95, end_ts / total_dur)
                                self.progress.set(pct)
                                self.status_label.configure(
                                    text=f"Transcribing... {int(pct*100)}%",
                                    text_color=COLORS["accent"],
                                )
                        except (ValueError, IndexError):
                            pass

                    elif text.startswith("[done]"):
                        self.progress.set(0.95)

                    elif text.startswith("[srt]"):
                        # SRT written — extract path
                        try:
                            # "[srt] wrote 42 cues -> path/to/file.srt (1.2 KB) UTF-8 LF"
                            parts = text.split("->")
                            if len(parts) > 1:
                                srt_part = parts[1].strip().split("(")[0].strip()
                                self._srt_path = srt_part
                        except Exception:
                            pass

                    elif "[OK]" in text:
                        self.progress.set(1.0)

                elif msg_type == "progress":
                    val = msg.get("value", 0)
                    try:
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                    except Exception:
                        pass
                    self.progress.set(val)

                elif msg_type == "done":
                    if self._pipeline_step == 1:
                        # Extraction done → start transcription
                        self._log("Audio extraction complete.")
                        settings = self._get_settings() if self._get_settings else {}
                        self._msg_queue = queue.Queue()
                        from app.core.runner import ScriptRunner
                        self._runner = ScriptRunner()
                        self._start_transcribe(self._wav_path, settings)
                        self.after(100, self._poll)
                        return

                    elif self._pipeline_step == 2:
                        # Transcription done → verify
                        self._log("Transcription complete — verifying SRT...")
                        if self._srt_path:
                            self._msg_queue = queue.Queue()
                            from app.core.runner import ScriptRunner
                            self._runner = ScriptRunner()
                            self._start_verify(self._srt_path)
                            self.after(100, self._poll)
                            return
                        else:
                            # Try to find SRT in exports/
                            self._finish_success()
                            return

                    elif self._pipeline_step == 3:
                        # Verify done → complete!
                        self._finish_success()
                        return

                elif msg_type == "error":
                    err_text = msg.get("text", "Unknown error")
                    self._finish_error(err_text)
                    return

                elif msg_type == "started":
                    self._log(f"$ {msg.get('cmd', '')}")

        except queue.Empty:
            pass

        # Update elapsed time
        if self._start_time:
            elapsed = time.time() - self._start_time
            mins, secs = divmod(int(elapsed), 60)
            self.elapsed_label.configure(text=f"Elapsed: {mins}:{secs:02d}")

        self.after(100, self._poll)

    def _finish_success(self):
        self._is_running = False
        self._pipeline_step = 0
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate")
        except Exception:
            pass
        self.progress.set(1.0)

        elapsed = time.time() - self._start_time if self._start_time else 0
        mins, secs = divmod(int(elapsed), 60)
        self.elapsed_label.configure(text=f"Total: {mins}:{secs:02d}")

        self.status_label.configure(
            text=f"{ICONS['check']} Complete — SRT ready!",
            text_color=COLORS["success"],
        )
        self.cancel_btn.pack_forget()
        self.start_btn.configure(text=f"{ICONS['play']}  Re-run Transcription")
        self.start_btn.pack(side="left", fill="x", expand=True)

        if self.on_complete and self._srt_path:
            self.on_complete(self._srt_path)

    def _finish_error(self, error_text: str):
        self._is_running = False
        self._pipeline_step = 0
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate")
        except Exception:
            pass
        self.progress.set(0)

        self.status_label.configure(text="Failed", text_color=COLORS["error"])
        self.cancel_btn.pack_forget()
        self.start_btn.configure(text=f"{ICONS['play']}  Start Transcription")
        self.start_btn.pack(side="left", fill="x", expand=True)

        # Show error banner with retry
        self.error_label.configure(text=error_text)

        # Generate fix hint based on error
        hint = self._suggest_fix(error_text)
        if hint:
            self.error_hint.configure(text=f"{ICONS['info']} {hint}")
            self.error_hint.grid()
        else:
            self.error_hint.grid_remove()

        self.error_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))

    def _suggest_fix(self, error_text: str) -> Optional[str]:
        """Generate actionable fix suggestions from error text."""
        err = error_text.lower()
        if "faster-whisper" in err or "faster_whisper" in err or "no module named" in err:
            return "faster-whisper is not installed. Run: pip install faster-whisper>=1.2.0 (or activate your venv first)"
        elif "out of memory" in err or "oom" in err or "cuda" in err and "memory" in err:
            return "GPU ran out of memory. Try: smaller model (turbo/medium), beam_size=1, or switch to CPU in Advanced Settings"
        elif "ffmpeg" in err or "ffprobe" in err:
            return "FFmpeg not found. Install with: winget install Gyan.FFmpeg — then restart the app"
        elif "not found" in err and "input" in err:
            return "Input file not found. Check the file path and try again."
        elif "python" in err and "not found" in err:
            return "Python not found. Make sure venv is set up: python -m venv venv && .\\venv\\Scripts\\activate"
        elif "permission" in err or "access" in err:
            return "Permission denied. Close the file if it's open in another app, or run as administrator."
        elif "model" in err and ("download" in err or "network" in err or "connection" in err):
            return "Model download failed. Check your internet connection — the model will be cached after first download (~2.9GB for large-v3)."
        return "Check the log above for details. Click Retry to try again."

    def _on_cancel(self):
        if self._runner:
            self._runner.cancel()
        self._is_running = False
        self._pipeline_step = 0
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate")
        except Exception:
            pass
        self.progress.set(0)
        self.status_label.configure(text="Cancelled", text_color=COLORS["warning"])
        self.cancel_btn.pack_forget()
        self.start_btn.configure(text=f"{ICONS['play']}  Start Transcription")
        self.start_btn.pack(side="left", fill="x", expand=True)
        self._log("Cancelled by user.")

    def _log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def get_srt_path(self) -> Optional[str]:
        return self._srt_path
