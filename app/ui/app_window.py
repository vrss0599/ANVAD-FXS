"""
UGA-SUB main application window.

Single scrollable window with 5 stacked sections:
1. System Status (readiness badges with retry + fix)
2. Audio Input (file picker + metadata)
3. Settings (model/task/language)
4. Transcription (start + progress + log)
5. Output (SRT result + DaVinci steps)
"""

import customtkinter as ctk
import sys
from pathlib import Path

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS
from app.ui.section_status import SectionStatus
from app.ui.section_input import SectionInput
from app.ui.section_settings import SectionSettings
from app.ui.section_transcribe import SectionTranscribe
from app.ui.section_output import SectionOutput


class AppWindow(ctk.CTk):
    """Main UGA-SUB desktop application window."""

    APP_TITLE = "UGA-SUB — Free Auto Subtitles"
    APP_ID = "ugasub.davinci.autosubtitles.v1"

    def __init__(self):
        # Set Windows taskbar icon grouping before CTk init
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.APP_ID)
        except Exception:
            pass

        super().__init__()

        self.title(self.APP_TITLE)
        self.geometry(f"{DIM['window_width']}x{DIM['window_height']}")
        self.minsize(DIM["window_min_width"], DIM["window_min_height"])
        self.configure(fg_color=COLORS["bg"])

        # Center on screen
        self._center_window(DIM["window_width"], DIM["window_height"])

        # ── Title bar ──
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], 0))

        ctk.CTkLabel(
            title_frame, text=self.APP_TITLE,
            font=ctk.CTkFont(family=FONTS["title"][0], size=FONTS["title"][1], weight=FONTS["title"][2]),
            text_color=COLORS["text"],
        ).pack(side="left")

        # Theme toggle
        self.theme_btn = ctk.CTkButton(
            title_frame, text="☀", width=32, height=32,
            font=ctk.CTkFont(size=16), corner_radius=16,
            fg_color="transparent", hover_color=COLORS["badge_na_bg"],
            text_color=COLORS["text_dim"],
            command=self._toggle_theme,
        )
        self.theme_btn.pack(side="right")

        # Accent bar
        ctk.CTkFrame(
            self, height=3, corner_radius=2,
            fg_color=COLORS["accent"],
        ).pack(fill="x", padx=PAD["card_outer_x"], pady=(4, 0))

        # ── Scrollable content ──
        self.content = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            corner_radius=0,
        )
        self.content.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Section 1: System Status ──
        self.sec_status = SectionStatus(self.content)
        self.sec_status.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], 0))

        # ── Section 2: Audio Input ──
        self.sec_input = SectionInput(self.content, on_file_selected=self._on_file_selected)
        self.sec_input.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], 0))

        # ── Section 3: Settings ──
        self.sec_settings = SectionSettings(self.content)
        self.sec_settings.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], 0))

        # ── Section 4: Transcription ──
        self.sec_transcribe = SectionTranscribe(self.content, on_complete=self._on_transcribe_complete)
        self.sec_transcribe.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], 0))

        # Wire up data sources for the transcribe section
        self.sec_transcribe.bind_data_sources(
            get_file_path=lambda: self.sec_input.get_selected_path(),
            get_settings=lambda: self.sec_settings.get_settings(),
            get_audio_info=lambda: self.sec_input.get_audio_info(),
        )

        # ── Section 5: Output ──
        self.sec_output = SectionOutput(self.content)
        self.sec_output.pack(fill="x", padx=PAD["card_outer_x"], pady=(PAD["section"], PAD["section"]))

        # ── Footer ──
        footer = ctk.CTkFrame(self, fg_color="transparent", height=30)
        footer.pack(fill="x", padx=PAD["card_outer_x"], pady=(0, 8))

        ctk.CTkLabel(
            footer,
            text="UGA-SUB · Free DaVinci Auto-Subtitles · RTX 3050 6GB Optimized · ₹0 · Offline",
            font=ctk.CTkFont(family=FONTS["small"][0], size=9),
            text_color=COLORS["muted"],
        ).pack(side="left")

        version_text = f"Python {sys.version_info.major}.{sys.version_info.minor}"
        ctk.CTkLabel(
            footer, text=version_text,
            font=ctk.CTkFont(family=FONTS["small"][0], size=9),
            text_color=COLORS["muted"],
        ).pack(side="right")

        # ── Initial actions ──
        # Run system checks on startup (after window is shown)
        self.after(300, self.sec_status.run_all_checks)
        # Start with transcribe button disabled
        self.sec_transcribe.set_ready(False)

    def _center_window(self, width: int, height: int):
        self.update_idletasks()
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scaling = 1.0
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = int((screen_w / 2) - (width * scaling / 2))
        pos_y = int((screen_h / 2) - (height * scaling / 2))
        self.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="🌙")
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="☀")

    def _on_file_selected(self, path: str, info: dict):
        """Called when user selects a file in Section 2."""
        # Enable/disable transcribe based on file + deps
        has_file = path is not None
        # Check if minimum deps are available
        status_results = self.sec_status.get_results()
        has_deps = status_results.get("faster_whisper", {}).get("ok", False)

        if has_file and has_deps:
            self.sec_transcribe.set_ready(True)
        elif has_file:
            # File selected but deps missing — still enable (runner will show error)
            self.sec_transcribe.set_ready(True)

        # Reset output section
        self.sec_output.reset()

    def _on_transcribe_complete(self, srt_path: str):
        """Called when transcription + verification completes."""
        self.sec_output.set_srt_result(srt_path)

        # Scroll to output section
        try:
            self.content._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
