"""
Section 3 — Settings: model, task, and language selection.

Minimal by default, with an expandable "Advanced" panel.
"""

import customtkinter as ctk
from typing import Optional

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS


class SectionSettings(ctk.CTkFrame):
    """Section 3: Settings — model/task/language dropdowns."""

    MODELS = ["large-v3", "turbo", "medium", "small", "base", "tiny"]
    MODEL_HINTS = {
        "large-v3": "Best for Kannada/Hindi → English (2.9GB, ~2m00s/hr VAD off, 100% recall)",
        "turbo": "English-only, 2× faster (809MB, ~30-45s/hr) — use for en-only",
        "medium": "Balanced (1.5GB, decent quality)",
        "small": "Fast, lower quality (462MB)",
        "base": "Very fast, basic quality (141MB)",
        "tiny": "Fastest, lowest quality (73MB) — good for testing",
    }

    TASKS = {
        "Translate to English": "translate",
        "Transcribe (keep language)": "transcribe",
    }

    LANGUAGES = {
        "Auto-detect": None,
        "Kannada (kn)": "kn",
        "Hindi (hi)": "hi",
        "English (en)": "en",
        "Tamil (ta)": "ta",
        "Telugu (te)": "te",
        "Marathi (mr)": "mr",
    }

    DEVICES = {
        "Auto (GPU if available)": "auto",
        "GPU (CUDA)": "cuda",
        "CPU (slower, always works)": "cpu",
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=DIM["card_corner"], **kwargs)
        self.configure(fg_color=COLORS["card"], border_color=COLORS["card_border"], border_width=1)

        # Header
        ctk.CTkLabel(
            self, text="3. Settings",
            font=ctk.CTkFont(family=FONTS["heading"][0], size=FONTS["heading"][1], weight=FONTS["heading"][2]),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=PAD["card_inner"], pady=(PAD["card_inner"], PAD["small"]))

        # Main settings row
        main_row = ctk.CTkFrame(self, fg_color="transparent")
        main_row.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))
        main_row.grid_columnconfigure((0, 1, 2), weight=1)

        # Model dropdown
        model_frame = ctk.CTkFrame(main_row, fg_color="transparent")
        model_frame.grid(row=0, column=0, sticky="ew", padx=(0, PAD["element"]))
        ctk.CTkLabel(
            model_frame, text="Model",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        ).pack(anchor="w")
        self.model_var = ctk.StringVar(value="large-v3")
        self.model_menu = ctk.CTkOptionMenu(
            model_frame, variable=self.model_var, values=self.MODELS,
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            width=160, height=32,
            corner_radius=DIM["button_corner"],
            command=self._on_model_change,
        )
        self.model_menu.pack(anchor="w", pady=(2, 0))

        # Task dropdown
        task_frame = ctk.CTkFrame(main_row, fg_color="transparent")
        task_frame.grid(row=0, column=1, sticky="ew", padx=(0, PAD["element"]))
        ctk.CTkLabel(
            task_frame, text="Task",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        ).pack(anchor="w")
        self.task_var = ctk.StringVar(value="Translate to English")
        self.task_menu = ctk.CTkOptionMenu(
            task_frame, variable=self.task_var, values=list(self.TASKS.keys()),
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            width=180, height=32,
            corner_radius=DIM["button_corner"],
        )
        self.task_menu.pack(anchor="w", pady=(2, 0))

        # Language dropdown
        lang_frame = ctk.CTkFrame(main_row, fg_color="transparent")
        lang_frame.grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(
            lang_frame, text="Language",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        ).pack(anchor="w")
        self.lang_var = ctk.StringVar(value="Auto-detect")
        self.lang_menu = ctk.CTkOptionMenu(
            lang_frame, variable=self.lang_var, values=list(self.LANGUAGES.keys()),
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            width=150, height=32,
            corner_radius=DIM["button_corner"],
        )
        self.lang_menu.pack(anchor="w", pady=(2, 0))

        # Model hint
        self.model_hint = ctk.CTkLabel(
            self, text=self.MODEL_HINTS.get("large-v3", ""),
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.model_hint.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["small"]))

        # ── Preset row: one-click quality modes ──
        preset_frame = ctk.CTkFrame(self, fg_color="transparent")
        preset_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))
        ctk.CTkLabel(
            preset_frame, text="Transcription Quality Preset",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1], weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            preset_frame, text="  VAD off = best quality (recommended for kn/hi→en)",
            font=ctk.CTkFont(family=FONTS["small"][0], size=10),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(6, 0))

        self.preset_var = ctk.StringVar(value="100% Complete (High-Recall) • VAD off • 2m00s/hr")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_frame,
            variable=self.preset_var,
            values=[
                "100% Complete (High-Recall) • VAD off • 2m00s/hr",
                "Balanced • VAD gentle 0.35 • 1m45s/hr",
                "Fast • VAD on • 1m30s/hr",
            ],
            font=ctk.CTkFont(family=FONTS["body"][0], size=11),
            width=340, height=28,
            corner_radius=DIM["button_corner"],
            command=self._on_preset_change,
        )
        self.preset_menu.pack(side="right")

        self.preset_hint = ctk.CTkLabel(
            self,
            text="✓ 100% mode: VAD OFF • near-disable thresholds • beam 5 • every word kept (costs +10-15% time)",
            font=ctk.CTkFont(family=FONTS["small"][0], size=10),
            text_color=COLORS["success"],
            anchor="w",
        )
        self.preset_hint.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))

        # Advanced toggle
        self.advanced_visible = False
        self.advanced_toggle = ctk.CTkButton(
            self, text=f"{ICONS['gear']} Advanced Settings ▸", width=160, height=26,
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            fg_color="transparent", text_color=COLORS["text_dim"],
            hover_color=COLORS["badge_na_bg"],
            anchor="w", corner_radius=4,
            command=self._toggle_advanced,
        )
        self.advanced_toggle.pack(anchor="w", padx=PAD["card_inner"], pady=(0, PAD["small"]))

        # Advanced panel (hidden by default)
        self.advanced_frame = ctk.CTkFrame(self, fg_color=COLORS["badge_na_bg"], corner_radius=8)
        self.advanced_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
        self.advanced_frame.pack_forget()

        adv_inner = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        adv_inner.pack(fill="x", padx=12, pady=10)
        adv_inner.grid_columnconfigure((0, 1, 2), weight=1)

        # Beam size
        beam_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        beam_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(beam_frame, text="Beam Size", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor="w")
        self.beam_var = ctk.IntVar(value=5)
        self.beam_slider = ctk.CTkSlider(beam_frame, from_=1, to=5, number_of_steps=4, variable=self.beam_var, width=120)
        self.beam_slider.pack(anchor="w", pady=(2, 0))
        self.beam_label = ctk.CTkLabel(beam_frame, text="5 (Best quality, 100% complete)", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"])
        self.beam_label.pack(anchor="w")
        self.beam_slider.configure(command=self._on_beam_change)

        # VAD filter
        vad_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        vad_frame.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(vad_frame, text="VAD Filter", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor="w")
        self.vad_var = ctk.BooleanVar(value=False)
        self.vad_switch = ctk.CTkSwitch(vad_frame, text="Silero VAD (off=100%)", variable=self.vad_var, font=ctk.CTkFont(size=11), command=self._on_vad_toggle)
        self.vad_switch.pack(anchor="w", pady=(4, 0))
        self.vad_hint = ctk.CTkLabel(vad_frame, text="OFF = best quality", font=ctk.CTkFont(size=9), text_color=COLORS["success"])
        self.vad_hint.pack(anchor="w")

        # Device
        dev_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        dev_frame.grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(dev_frame, text="Device", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor="w")
        self.device_var = ctk.StringVar(value="Auto (GPU if available)")
        self.device_menu = ctk.CTkOptionMenu(
            dev_frame, variable=self.device_var, values=list(self.DEVICES.keys()),
            font=ctk.CTkFont(size=11), width=160, height=28, corner_radius=4,
        )
        self.device_menu.pack(anchor="w", pady=(2, 0))

        # Bottom spacer
        ctk.CTkFrame(self, fg_color="transparent", height=4).pack()

    def _on_model_change(self, value: str):
        hint = self.MODEL_HINTS.get(value, "")
        self.model_hint.configure(text=hint)

    def _on_beam_change(self, value: float):
        v = int(round(value))
        labels = {1: "1 (fast, low VRAM)", 2: "2", 3: "3 (balanced)", 4: "4", 5: "5 (Best quality, 100% complete)"}
        self.beam_label.configure(text=labels.get(v, str(v)))

    def _on_preset_change(self, value: str):
        """One-click presets — sync VAD switch, beam, and hint."""
        if "100% Complete" in value:
            self.vad_var.set(False)
            self.beam_var.set(5)
            self._on_beam_change(5)
            self.beam_slider.set(5)
            self.preset_hint.configure(text="✓ 100% mode: VAD OFF • near-disable thresholds • beam 5 • every word kept (costs +10-15% time)", text_color=COLORS["success"])
            self.vad_hint.configure(text="OFF = best quality (preset)", text_color=COLORS["success"])
        elif "Balanced" in value:
            self.vad_var.set(True)
            self.beam_var.set(5)
            self._on_beam_change(5)
            self.beam_slider.set(5)
            self.preset_hint.configure(text="Balanced: VAD gentle 0.35 • thresholds 0.90/-2.0/3.0 • beam 5 • good quality, slight speed gain", text_color=COLORS["warning"])
            self.vad_hint.configure(text="ON gentle 0.35", text_color=COLORS["warning"])
        else:  # Fast
            self.vad_var.set(True)
            self.beam_var.set(1)
            self._on_beam_change(1)
            self.beam_slider.set(1)
            self.preset_hint.configure(text="Fast: VAD on • lower accuracy — may drop soft/whisper speech", text_color=COLORS["error"])
            self.vad_hint.configure(text="ON", text_color=COLORS["text_dim"])

    def _on_vad_toggle(self):
        # Keep preset menu in sync when user flips switch manually
        is_on = self.vad_var.get()
        if is_on:
            self.vad_hint.configure(text="ON gentle 0.35", text_color=COLORS["warning"])
            if "100% Complete" in self.preset_var.get():
                self.preset_var.set("Balanced • VAD gentle 0.35 • 1m45s/hr")
                self.preset_hint.configure(text="Balanced: VAD gentle 0.35 • thresholds 0.90/-2.0/3.0 • beam 5 • good quality, slight speed gain", text_color=COLORS["warning"])
        else:
            self.vad_hint.configure(text="OFF = best quality", text_color=COLORS["success"])
            self.preset_var.set("100% Complete (High-Recall) • VAD off • 2m00s/hr")
            self.preset_hint.configure(text="✓ 100% mode: VAD OFF • near-disable thresholds • beam 5 • every word kept (costs +10-15% time)", text_color=COLORS["success"])

    def _toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
            self.advanced_toggle.configure(text=f"{ICONS['gear']} Advanced Settings ▾")
        else:
            self.advanced_frame.pack_forget()
            self.advanced_toggle.configure(text=f"{ICONS['gear']} Advanced Settings ▸")

    def get_settings(self) -> dict:
        """Return current settings as a dict for the runner. Preset determines thresholds."""
        preset = self.preset_var.get() if hasattr(self, "preset_var") else ""
        # High-Recall flag is the cleanest: runner sends --high_recall (single switch) for 100% mode
        high_recall = "100% Complete" in preset
        # Near-disable thresholds for 100%/Balanced; Fast uses original aggressive thresholds
        if high_recall or "Balanced" in preset:
            no_speech = 0.90
            log_prob = -2.0
            compression = 3.0
        else:  # Fast
            no_speech = 0.80
            log_prob = -1.0
            compression = 2.4
        # Per-task condition: translate->False (avoid drift), transcribe->True (context). Runner will send explicit flag.
        task_code = self.TASKS.get(self.task_var.get(), "translate")
        condition = False if task_code == "translate" else True

        return {
            "model": self.model_var.get(),
            "task": task_code,
            "language": self.LANGUAGES.get(self.lang_var.get()),
            "beam_size": int(round(self.beam_var.get())),
            "vad_filter": self.vad_var.get(),
            "device": self.DEVICES.get(self.device_var.get(), "auto"),
            "high_recall": high_recall,
            "no_speech_threshold": no_speech,
            "log_prob_threshold": log_prob,
            "compression_ratio_threshold": compression,
            "vad_threshold": 0.35,
            "vad_min_silence_ms": 1000,
            "vad_speech_pad_ms": 400,
            "word_timestamps": True,
            "condition_on_previous_text": condition,
            "temperature": "0.0,0.2,0.4,0.6,0.8",
        }
