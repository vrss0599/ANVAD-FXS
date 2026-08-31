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
        "large-v3": "Best for Kannada/Hindi → English (2.9GB, ~1m43s/hr on 3050)",
        "turbo": "English-only, 2× faster (809MB, ~30-45s/hr on 3050)",
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
        self.model_hint.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["element"]))

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
        self.beam_var = ctk.IntVar(value=1)
        self.beam_slider = ctk.CTkSlider(beam_frame, from_=1, to=5, number_of_steps=4, variable=self.beam_var, width=120)
        self.beam_slider.pack(anchor="w", pady=(2, 0))
        self.beam_label = ctk.CTkLabel(beam_frame, text="1 (low VRAM)", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"])
        self.beam_label.pack(anchor="w")
        self.beam_slider.configure(command=self._on_beam_change)

        # VAD filter
        vad_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        vad_frame.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(vad_frame, text="VAD Filter", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor="w")
        self.vad_var = ctk.BooleanVar(value=True)
        self.vad_switch = ctk.CTkSwitch(vad_frame, text="Silero VAD", variable=self.vad_var, font=ctk.CTkFont(size=11))
        self.vad_switch.pack(anchor="w", pady=(4, 0))

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
        labels = {1: "1 (low VRAM)", 2: "2", 3: "3", 4: "4", 5: "5 (more accurate, +1GB)"}
        self.beam_label.configure(text=labels.get(v, str(v)))

    def _toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
            self.advanced_toggle.configure(text=f"{ICONS['gear']} Advanced Settings ▾")
        else:
            self.advanced_frame.pack_forget()
            self.advanced_toggle.configure(text=f"{ICONS['gear']} Advanced Settings ▸")

    def get_settings(self) -> dict:
        """Return current settings as a dict for the runner."""
        return {
            "model": self.model_var.get(),
            "task": self.TASKS.get(self.task_var.get(), "translate"),
            "language": self.LANGUAGES.get(self.lang_var.get()),
            "beam_size": int(round(self.beam_var.get())),
            "vad_filter": self.vad_var.get(),
            "device": self.DEVICES.get(self.device_var.get(), "auto"),
        }
