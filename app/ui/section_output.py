"""
Section 5 — Output: SRT result, preview, save, and DaVinci Resolve instructions.

UX: Success banner, SRT preview, save button, copy path, and a full DaVinci
instruction panel with copy buttons for each step.
"""

import customtkinter as ctk
from tkinter import filedialog
import shutil
from pathlib import Path
from typing import Optional

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS


class SectionOutput(ctk.CTkFrame):
    """Section 5: Output — SRT result + save + DaVinci Resolve instructions."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=DIM["card_corner"], **kwargs)
        self.configure(fg_color=COLORS["card"], border_color=COLORS["card_border"], border_width=1)
        self._srt_path: Optional[str] = None

        # Header
        ctk.CTkLabel(
            self, text="5. Output",
            font=ctk.CTkFont(family=FONTS["heading"][0], size=FONTS["heading"][1], weight=FONTS["heading"][2]),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=PAD["card_inner"], pady=(PAD["card_inner"], PAD["small"]))

        # Placeholder (shown before transcription)
        self.placeholder = ctk.CTkLabel(
            self, text="SRT output will appear here after transcription",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            text_color=COLORS["text_dim"], height=50,
        )
        self.placeholder.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))

        # ── Result area (hidden until SRT ready) ──

        self.result_container = ctk.CTkFrame(self, fg_color="transparent")
        self.result_container.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
        self.result_container.pack_forget()

        # Success banner
        self.banner = ctk.CTkFrame(self.result_container, fg_color=COLORS["badge_ok_bg"], corner_radius=8)
        self.banner.pack(fill="x", pady=(0, PAD["element"]))

        self.banner_icon = ctk.CTkLabel(
            self.banner, text=ICONS["check"],
            font=ctk.CTkFont(size=18), text_color=COLORS["success"],
        )
        self.banner_icon.pack(side="left", padx=(12, 4), pady=8)

        self.banner_text = ctk.CTkLabel(
            self.banner, text="SRT Ready",
            font=ctk.CTkFont(family=FONTS["subheading"][0], size=FONTS["subheading"][1], weight="bold"),
            text_color=COLORS["badge_ok_fg"],
        )
        self.banner_text.pack(side="left", padx=(0, 12), pady=8)

        # SRT preview
        self.preview_label = ctk.CTkLabel(
            self.result_container, text="Preview:",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        )
        self.preview_label.pack(anchor="w", pady=(0, 2))

        self.preview_box = ctk.CTkTextbox(
            self.result_container, height=100,
            font=ctk.CTkFont(family=FONTS["mono"][0], size=FONTS["mono_small"][1]),
            fg_color=COLORS["log_bg"], text_color=COLORS["log_fg"],
            corner_radius=6, state="disabled",
        )
        self.preview_box.pack(fill="x", pady=(0, PAD["element"]))

        # Action buttons row
        btn_row = ctk.CTkFrame(self.result_container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, PAD["element"]))

        self.save_btn = ctk.CTkButton(
            btn_row, text=f"{ICONS['save']}  Save SRT File",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1], weight="bold"),
            height=36, corner_radius=DIM["button_corner"],
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._save_srt,
        )
        self.save_btn.pack(side="left", padx=(0, PAD["element"]))

        self.copy_path_btn = ctk.CTkButton(
            btn_row, text=f"{ICONS['copy']}  Copy Path",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            height=36, corner_radius=DIM["button_corner"],
            fg_color=COLORS["badge_na_bg"], hover_color=COLORS["muted"],
            text_color=COLORS["text"],
            command=self._copy_path,
        )
        self.copy_path_btn.pack(side="left", padx=(0, PAD["element"]))

        self.resolve_btn = ctk.CTkButton(
            btn_row, text=f"{ICONS['resolve']}  DaVinci Resolve Steps →",
            font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
            height=36, corner_radius=DIM["button_corner"],
            fg_color="transparent", hover_color=COLORS["badge_na_bg"],
            text_color=COLORS["accent"],
            border_width=2, border_color=COLORS["accent"],
            command=self._toggle_resolve_steps,
        )
        self.resolve_btn.pack(side="left")

        # ── DaVinci Resolve Instructions Panel ──

        self.resolve_panel = ctk.CTkFrame(
            self.result_container,
            fg_color=COLORS["badge_na_bg"], corner_radius=8,
        )
        self.resolve_panel.pack(fill="x", pady=(0, PAD["element"]))
        self.resolve_panel.pack_forget()  # Hidden by default

        self._build_resolve_instructions()

    def _build_resolve_instructions(self):
        """Build the DaVinci Resolve step-by-step instructions panel."""
        panel = self.resolve_panel
        inner = ctk.CTkFrame(panel, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        # ── Path A: Subtitle Track ──
        ctk.CTkLabel(
            inner, text="Path A — Subtitle Track (Recommended, Easiest)",
            font=ctk.CTkFont(family=FONTS["subheading"][0], size=FONTS["subheading"][1], weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(0, 6))

        steps_a = [
            ("1", "Open DaVinci Resolve → your project timeline"),
            ("2", "File → Import → Subtitle"),
            ("3", "Select the SRT file:"),
            ("4", 'Choose "Insert Selected Subtitles to Timeline Using Timecode" → OK'),
            ("5", "Inspector → Caption tab to style (font, size, outline)"),
            ("6", "Deliver → Subtitle Settings → Burn into video or Export as separate file"),
        ]

        for num, text in steps_a:
            step_row = ctk.CTkFrame(inner, fg_color="transparent")
            step_row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                step_row, text=f"  {num}.",
                font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1], weight="bold"),
                text_color=COLORS["accent"], width=28,
            ).pack(side="left")
            ctk.CTkLabel(
                step_row, text=text,
                font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
                text_color=COLORS["text"], anchor="w", wraplength=500,
            ).pack(side="left", fill="x")

        # SRT path display with copy button
        self.srt_path_frame = ctk.CTkFrame(inner, fg_color=COLORS["log_bg"], corner_radius=6)
        self.srt_path_frame.pack(fill="x", padx=28, pady=(2, 6))

        self.srt_path_label = ctk.CTkLabel(
            self.srt_path_frame, text="",
            font=ctk.CTkFont(family=FONTS["mono_small"][0], size=FONTS["mono_small"][1]),
            text_color=COLORS["log_fg"], anchor="w",
        )
        self.srt_path_label.pack(side="left", padx=8, pady=4, fill="x", expand=True)

        ctk.CTkButton(
            self.srt_path_frame, text=ICONS["copy"], width=28, height=22,
            font=ctk.CTkFont(size=12), corner_radius=3,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._copy_path,
        ).pack(side="right", padx=4, pady=4)

        # Offset note
        note_frame = ctk.CTkFrame(inner, fg_color=COLORS["badge_warn_bg"], corner_radius=6)
        note_frame.pack(fill="x", padx=28, pady=(0, 10))
        ctk.CTkLabel(
            note_frame,
            text=f"{ICONS['warning']}  Timeline starts at 01:00:00:00? Resolve auto-adds the offset. Verify first subtitle cue position.",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["badge_warn_fg"], wraplength=480, justify="left",
        ).pack(padx=8, pady=6)

        # Separator
        ctk.CTkFrame(inner, fg_color=COLORS["card_border"], height=1).pack(fill="x", pady=8)

        # ── Path B: Text+ Overlay ──
        ctk.CTkLabel(
            inner, text="Path B — Text+ Overlay (Advanced, More Styling)",
            font=ctk.CTkFont(family=FONTS["subheading"][0], size=FONTS["subheading"][1], weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(0, 6))

        steps_b = [
            ("1", "Copy scripts to the Resolve Utility folder:"),
            ("2", "Open Resolve → Workspace → Console → Py3 tab"),
            ("3", "Run the injection command below:"),
        ]

        for num, text in steps_b:
            step_row = ctk.CTkFrame(inner, fg_color="transparent")
            step_row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                step_row, text=f"  {num}.",
                font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1], weight="bold"),
                text_color=COLORS["accent"], width=28,
            ).pack(side="left")
            ctk.CTkLabel(
                step_row, text=text,
                font=ctk.CTkFont(family=FONTS["body"][0], size=FONTS["body"][1]),
                text_color=COLORS["text"], anchor="w", wraplength=500,
            ).pack(side="left", fill="x")

        # Utility path with copy
        utility_path = r"%appdata%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
        util_row = ctk.CTkFrame(inner, fg_color=COLORS["log_bg"], corner_radius=6)
        util_row.pack(fill="x", padx=28, pady=(2, 4))
        ctk.CTkLabel(
            util_row, text=utility_path,
            font=ctk.CTkFont(family=FONTS["mono_small"][0], size=FONTS["mono_small"][1]),
            text_color=COLORS["log_fg"], anchor="w",
        ).pack(side="left", padx=8, pady=4, fill="x", expand=True)
        ctk.CTkButton(
            util_row, text=ICONS["copy"], width=28, height=22,
            font=ctk.CTkFont(size=12), corner_radius=3,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=lambda: self._copy_text(utility_path),
        ).pack(side="right", padx=4, pady=4)

        # Exec command with copy
        self.exec_cmd_label_text = ""
        exec_row = ctk.CTkFrame(inner, fg_color=COLORS["log_bg"], corner_radius=6)
        exec_row.pack(fill="x", padx=28, pady=(2, 6))
        self.exec_cmd_label = ctk.CTkLabel(
            exec_row, text="exec(open(r\"...\").read())",
            font=ctk.CTkFont(family=FONTS["mono_small"][0], size=FONTS["mono_small"][1]),
            text_color=COLORS["log_fg"], anchor="w",
        )
        self.exec_cmd_label.pack(side="left", padx=8, pady=4, fill="x", expand=True)
        ctk.CTkButton(
            exec_row, text=ICONS["copy"], width=28, height=22,
            font=ctk.CTkFont(size=12), corner_radius=3,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=lambda: self._copy_text(self.exec_cmd_label_text),
        ).pack(side="right", padx=4, pady=4)

    def set_srt_result(self, srt_path: str):
        """Called when transcription completes — show results."""
        self._srt_path = srt_path
        self.placeholder.pack_forget()
        self.result_container.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))

        # Load SRT summary
        try:
            from app.core.srt_parser import get_srt_summary, parse_srt_file
            summary = get_srt_summary(srt_path)
            cues = parse_srt_file(srt_path)

            cue_count = summary.get("cue_count", 0)
            duration = summary.get("duration_fmt", "?")
            size_kb = summary.get("file_size_kb", 0)
            self.banner_text.configure(
                text=f"SRT Ready — {cue_count} cues · {duration} · {size_kb:.1f} KB"
            )

            # Preview: first 3 + last 2 cues
            preview_lines = []
            show_cues = cues[:3] + ([{"text": "..."}] if len(cues) > 5 else []) + cues[-2:] if len(cues) > 5 else cues[:5]
            for c in show_cues:
                if c.get("start"):
                    preview_lines.append(f"[{c['start']} → {c['end']}] {c['text']}")
                else:
                    preview_lines.append(c.get("text", "..."))

            self.preview_box.configure(state="normal")
            self.preview_box.delete("1.0", "end")
            self.preview_box.insert("end", "\n".join(preview_lines))
            self.preview_box.configure(state="disabled")

        except Exception as e:
            self.banner_text.configure(text=f"SRT Ready — {Path(srt_path).name}")
            self.preview_box.configure(state="normal")
            self.preview_box.delete("1.0", "end")
            self.preview_box.insert("end", f"Could not preview: {e}")
            self.preview_box.configure(state="disabled")

        # Update resolve instructions paths
        self.srt_path_label.configure(text=srt_path)

        # Build exec command
        try:
            project_root = Path(__file__).resolve().parents[2]
            script = project_root / "resolve_free" / "srt_to_textplus.py"
            self.exec_cmd_label_text = f'exec(open(r"{script}", encoding="utf-8").read())'
            self.exec_cmd_label.configure(text=self.exec_cmd_label_text)
        except Exception:
            self.exec_cmd_label_text = 'exec(open(r"path/to/srt_to_textplus.py").read())'

    def _save_srt(self):
        if not self._srt_path:
            return
        dest = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Save SRT Subtitle File",
            defaultextension=".srt",
            initialfile=Path(self._srt_path).name if self._srt_path else "subtitles.srt",
            filetypes=[("SRT Subtitle", "*.srt"), ("All files", "*.*")],
        )
        if dest:
            try:
                shutil.copy2(self._srt_path, dest)
                self.save_btn.configure(text=f"{ICONS['check']} Saved!")
                self.after(2000, lambda: self.save_btn.configure(text=f"{ICONS['save']}  Save SRT File"))
            except Exception as e:
                self.save_btn.configure(text=f"{ICONS['cross']} Error")
                self.after(2000, lambda: self.save_btn.configure(text=f"{ICONS['save']}  Save SRT File"))

    def _copy_path(self):
        if self._srt_path:
            self.clipboard_clear()
            self.clipboard_append(self._srt_path)
            self.copy_path_btn.configure(text=f"{ICONS['check']} Copied!")
            self.after(1500, lambda: self.copy_path_btn.configure(text=f"{ICONS['copy']}  Copy Path"))

    def _copy_text(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _toggle_resolve_steps(self):
        if self.resolve_panel.winfo_ismapped():
            self.resolve_panel.pack_forget()
            self.resolve_btn.configure(text=f"{ICONS['resolve']}  DaVinci Resolve Steps →")
        else:
            self.resolve_panel.pack(fill="x", pady=(0, PAD["element"]))
            self.resolve_btn.configure(text=f"{ICONS['resolve']}  DaVinci Resolve Steps ▾")

    def reset(self):
        """Reset to initial state."""
        self._srt_path = None
        self.result_container.pack_forget()
        self.resolve_panel.pack_forget()
        self.placeholder.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))
