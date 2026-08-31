"""
Section 2 — Audio Input: file picker with metadata display.

UX: Browse button + file info bar showing name, size, duration, format.
Warns if file isn't optimal (not 16kHz, not mono, is video needing extraction).
"""

import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
import threading
from typing import Callable, Optional

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS


class SectionInput(ctk.CTkFrame):
    """Section 2: Audio Input — file picker + metadata display."""

    AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")
    VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv")
    ALL_EXTS = AUDIO_EXTS + VIDEO_EXTS

    def __init__(self, master, on_file_selected: Optional[Callable] = None, **kwargs):
        super().__init__(master, corner_radius=DIM["card_corner"], **kwargs)
        self.configure(fg_color=COLORS["card"], border_color=COLORS["card_border"], border_width=1)
        self.on_file_selected = on_file_selected
        self._selected_path: Optional[str] = None
        self._audio_info: Optional[dict] = None

        # Header
        ctk.CTkLabel(
            self, text="2. Audio Input",
            font=ctk.CTkFont(family=FONTS["heading"][0], size=FONTS["heading"][1], weight=FONTS["heading"][2]),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=PAD["card_inner"], pady=(PAD["card_inner"], PAD["small"]))

        # File picker row
        picker_frame = ctk.CTkFrame(self, fg_color="transparent")
        picker_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))

        self.file_entry = ctk.CTkEntry(
            picker_frame,
            placeholder_text="No file selected — click Browse or drop a file path here",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            height=36,
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, PAD["element"]))

        self.browse_btn = ctk.CTkButton(
            picker_frame, text=f"{ICONS['folder']} Browse", width=100, height=36,
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            corner_radius=DIM["button_corner"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._browse,
        )
        self.browse_btn.pack(side="right")

        # Info card (hidden until file selected)
        self.info_frame = ctk.CTkFrame(self, fg_color=COLORS["badge_na_bg"], corner_radius=8)
        self.info_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
        self.info_frame.pack_forget()  # Hidden initially

        self.info_icon = ctk.CTkLabel(
            self.info_frame, text=ICONS["audio"],
            font=ctk.CTkFont(size=24),
        )
        self.info_icon.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8)

        self.info_name = ctk.CTkLabel(
            self.info_frame, text="",
            font=ctk.CTkFont(family=FONTS["subheading"][0], size=FONTS["subheading"][1], weight="bold"),
            text_color=COLORS["text"],
        )
        self.info_name.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(8, 0))

        self.info_details = ctk.CTkLabel(
            self.info_frame, text="",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        )
        self.info_details.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        self.info_frame.grid_columnconfigure(1, weight=1)

        # Warnings area (hidden until needed)
        self.warnings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.warnings_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
        self.warnings_frame.pack_forget()

        # Placeholder message
        self.placeholder = ctk.CTkLabel(
            self, text=f"{ICONS['file']}  Select an audio or video file to begin",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            text_color=COLORS["text_dim"],
            height=40,
        )
        self.placeholder.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))

    def _browse(self):
        filetypes = [
            ("Audio/Video files", " ".join(f"*{e}" for e in self.ALL_EXTS)),
            ("Audio files", " ".join(f"*{e}" for e in self.AUDIO_EXTS)),
            ("Video files", " ".join(f"*{e}" for e in self.VIDEO_EXTS)),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select Audio or Video File",
            filetypes=filetypes,
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._selected_path = path
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, path)

        # Show loading state
        self.placeholder.pack_forget()
        self.info_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))
        self.info_name.configure(text=Path(path).name)
        self.info_details.configure(text="Reading file info...")

        # Get audio info in background
        def worker():
            try:
                from app.core.audio_info import get_audio_info
                info = get_audio_info(path)
            except Exception as e:
                info = {
                    "name": Path(path).name,
                    "size_bytes": Path(path).stat().st_size if Path(path).exists() else 0,
                    "size_mb": f"{Path(path).stat().st_size / (1024*1024):.1f}" if Path(path).exists() else "?",
                    "duration_fmt": "unknown",
                    "format": "unknown",
                    "warnings": [f"Could not read file info: {e}"],
                    "needs_extraction": Path(path).suffix.lower() in self.VIDEO_EXTS,
                }
            self._audio_info = info
            self.after(0, lambda: self._display_info(info))

        threading.Thread(target=worker, daemon=True).start()

    def _display_info(self, info: dict):
        name = info.get("name", "?")
        size = info.get("size_mb", "?")
        duration = info.get("duration_fmt", "?")
        fmt = info.get("format", "?")
        sr = info.get("sample_rate")
        ch = info.get("channels")

        # Build details string
        parts = [f"{size} MB"]
        if sr:
            parts.append(f"{sr // 1000}kHz" if sr >= 1000 else f"{sr}Hz")
        if ch:
            parts.append("mono" if ch == 1 else f"{ch}ch")
        parts.append(duration)
        if fmt and fmt != "unknown":
            parts.append(fmt)

        self.info_name.configure(text=name)
        self.info_details.configure(text=" · ".join(parts))

        if info.get("needs_extraction"):
            self.info_icon.configure(text=ICONS["resolve"])
            self.info_frame.configure(fg_color=COLORS["badge_warn_bg"])
        else:
            self.info_icon.configure(text=ICONS["audio"])
            self.info_frame.configure(fg_color=COLORS["badge_ok_bg"])

        # Show warnings
        warnings = info.get("warnings", [])
        for w in self.warnings_frame.winfo_children():
            w.destroy()

        if warnings:
            self.warnings_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
            for warn_text in warnings:
                lbl = ctk.CTkLabel(
                    self.warnings_frame,
                    text=f"{ICONS['warning']}  {warn_text}",
                    font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
                    text_color=COLORS["warning"],
                    anchor="w",
                )
                lbl.pack(anchor="w", pady=1)
        else:
            self.warnings_frame.pack_forget()

        # Notify parent
        if self.on_file_selected:
            self.on_file_selected(self._selected_path, info)

    def get_selected_path(self) -> Optional[str]:
        return self._selected_path

    def get_audio_info(self) -> Optional[dict]:
        return self._audio_info
