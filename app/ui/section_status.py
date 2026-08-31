"""
Section 1 — System Status: readiness badges with retry + fix suggestions.

UX-first: red badges show a ↻ retry icon + clickable fix hint.
Green badges show ✓. Orange shows ⚠ with hint.
"""

import customtkinter as ctk
import threading
from typing import Callable, Optional

from app.ui.theme import COLORS, FONTS, PAD, DIM, ICONS


class StatusBadge(ctk.CTkFrame):
    """A single status badge with icon, label, retry button, and fix tooltip."""

    def __init__(self, master, key: str, on_retry: Optional[Callable] = None, **kwargs):
        super().__init__(master, corner_radius=DIM["badge_corner"], **kwargs)
        self.key = key
        self.on_retry = on_retry
        self._fix_popup = None

        # Layout: [icon_label] [text_label] [retry_btn]
        self.grid_columnconfigure(1, weight=1)

        self.icon_label = ctk.CTkLabel(
            self, text="", width=20,
            font=ctk.CTkFont(family=FONTS["badge"][0], size=FONTS["badge"][1]),
        )
        self.icon_label.grid(row=0, column=0, padx=(8, 2), pady=4)

        self.text_label = ctk.CTkLabel(
            self, text="Checking...",
            font=ctk.CTkFont(family=FONTS["badge"][0], size=FONTS["badge"][1], weight=FONTS["badge"][2]),
        )
        self.text_label.grid(row=0, column=1, padx=(2, 4), pady=4, sticky="w")

        self.retry_btn = ctk.CTkButton(
            self, text=ICONS["retry"], width=28, height=24,
            font=ctk.CTkFont(size=14),
            corner_radius=4,
            fg_color="transparent",
            hover_color=COLORS["accent"],
            command=self._on_retry_click,
        )
        # Hidden by default — shown when status is bad
        self.retry_btn.grid(row=0, column=2, padx=(0, 4), pady=2)
        self.retry_btn.grid_remove()

        # Fix hint row (hidden by default)
        self.fix_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.fix_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 4))
        self.fix_frame.grid_remove()

        self.fix_label = ctk.CTkLabel(
            self.fix_frame, text="",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
            wraplength=200, justify="left",
        )
        self.fix_label.pack(side="left", padx=2)

        self.fix_copy_btn = ctk.CTkButton(
            self.fix_frame, text=ICONS["copy"], width=24, height=20,
            font=ctk.CTkFont(size=11),
            corner_radius=3,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._copy_fix_cmd,
        )
        self.fix_copy_btn.pack(side="right", padx=2)
        self.fix_copy_btn.pack_forget()  # Hidden until there's a copyable command

        self._fix_cmd: Optional[str] = None

    def set_status(self, data: dict):
        """Update badge appearance from a readiness check result.

        data: {"ok": bool, "label": str, "detail": str, "fix_hint": str|None, "fix_cmd": str|None}
        """
        ok = data.get("ok", False)
        label = data.get("label", self.key)
        detail = data.get("detail", "")
        fix_hint = data.get("fix_hint")
        self._fix_cmd = data.get("fix_cmd")

        if ok:
            self.icon_label.configure(text=ICONS["check"])
            self.text_label.configure(text=label)
            self.configure(fg_color=COLORS["badge_ok_bg"])
            self.icon_label.configure(text_color=COLORS["badge_ok_fg"])
            self.text_label.configure(text_color=COLORS["badge_ok_fg"])
            self.retry_btn.grid_remove()
            self.fix_frame.grid_remove()
        else:
            # Determine if it's a warning (partial) or error (missing)
            is_warning = data.get("warning", False)
            if is_warning:
                bg = COLORS["badge_warn_bg"]
                fg = COLORS["badge_warn_fg"]
                icon = ICONS["warning"]
            else:
                bg = COLORS["badge_err_bg"]
                fg = COLORS["badge_err_fg"]
                icon = ICONS["cross"]

            self.icon_label.configure(text=icon, text_color=fg)
            self.text_label.configure(text=label, text_color=fg)
            self.configure(fg_color=bg)

            # Show retry button
            if self.on_retry:
                self.retry_btn.grid()
                self.retry_btn.configure(text_color=fg)

            # Show fix hint
            if fix_hint:
                self.fix_label.configure(text=fix_hint)
                self.fix_frame.grid()
                if self._fix_cmd:
                    self.fix_copy_btn.pack(side="right", padx=2)
                else:
                    self.fix_copy_btn.pack_forget()
            else:
                self.fix_frame.grid_remove()

    def set_checking(self):
        """Show a 'checking...' spinner state."""
        self.icon_label.configure(text="⟳", text_color=COLORS["accent"])
        self.text_label.configure(text=f"{self.key}: checking...", text_color=COLORS["text_dim"])
        self.configure(fg_color=COLORS["badge_na_bg"])
        self.retry_btn.grid_remove()
        self.fix_frame.grid_remove()

    def _on_retry_click(self):
        if self.on_retry:
            self.set_checking()
            self.on_retry(self.key)

    def _copy_fix_cmd(self):
        if self._fix_cmd:
            self.clipboard_clear()
            self.clipboard_append(self._fix_cmd)
            # Flash the button text to confirm
            original = self.fix_copy_btn.cget("text")
            self.fix_copy_btn.configure(text="✓")
            self.after(1200, lambda: self.fix_copy_btn.configure(text=original))


class SectionStatus(ctk.CTkFrame):
    """Section 1: System Status — horizontal row of badges with retry + fix hints."""

    BADGE_KEYS = ["python", "venv", "ffmpeg", "gpu", "faster_whisper", "model_cache"]

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=DIM["card_corner"], **kwargs)
        self.configure(fg_color=COLORS["card"], border_color=COLORS["card_border"], border_width=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PAD["card_inner"], pady=(PAD["card_inner"], PAD["small"]))

        ctk.CTkLabel(
            header, text=f"1. System Status",
            font=ctk.CTkFont(family=FONTS["heading"][0], size=FONTS["heading"][1], weight=FONTS["heading"][2]),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.recheck_btn = ctk.CTkButton(
            header, text=f"{ICONS['retry']} Recheck All", width=110, height=28,
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            corner_radius=DIM["button_corner"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.run_all_checks,
        )
        self.recheck_btn.pack(side="right")

        # Summary label
        self.summary_label = ctk.CTkLabel(
            self, text="Checking system readiness...",
            font=ctk.CTkFont(family=FONTS["small"][0], size=FONTS["small"][1]),
            text_color=COLORS["text_dim"],
        )
        self.summary_label.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["small"]))

        # Badges container — wrapping grid
        self.badges_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.badges_frame.pack(fill="x", padx=PAD["card_inner"], pady=(0, PAD["card_inner"]))

        self.badges: dict[str, StatusBadge] = {}
        for i, key in enumerate(self.BADGE_KEYS):
            badge = StatusBadge(self.badges_frame, key=key, on_retry=self._retry_single)
            badge.grid(row=i // 3, column=i % 3, padx=PAD["small"], pady=PAD["small"], sticky="ew")
            self.badges[key] = badge

        # Make columns expand evenly
        for col in range(3):
            self.badges_frame.grid_columnconfigure(col, weight=1)

        self._check_results: dict = {}

    def run_all_checks(self):
        """Run all readiness checks in a background thread."""
        self.recheck_btn.configure(state="disabled", text=f"⟳ Checking...")
        self.summary_label.configure(text="Running system checks...", text_color=COLORS["accent"])
        for badge in self.badges.values():
            badge.set_checking()

        def worker():
            try:
                from app.core.readiness import check_all
                results = check_all()
            except Exception as e:
                results = {k: {"ok": False, "label": k, "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None} for k in self.BADGE_KEYS}
            self._check_results = results
            # Schedule UI update on main thread
            self.after(0, lambda: self._apply_results(results))

        threading.Thread(target=worker, daemon=True).start()

    def _retry_single(self, key: str):
        """Re-run a single check (called when user clicks retry on a badge)."""
        def worker():
            try:
                from app.core.readiness import check_single
                result = check_single(key)
            except Exception as e:
                result = {"ok": False, "label": key, "detail": str(e), "fix_hint": "Internal error", "fix_cmd": None}
            self._check_results[key] = result
            self.after(0, lambda: self._apply_single(key, result))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_results(self, results: dict):
        """Apply all check results to badges (must be called on main thread)."""
        for key, badge in self.badges.items():
            data = results.get(key, {"ok": False, "label": key, "detail": "Not checked", "fix_hint": None, "fix_cmd": None})
            badge.set_status(data)

        self._update_summary(results)
        self.recheck_btn.configure(state="normal", text=f"{ICONS['retry']} Recheck All")

    def _apply_single(self, key: str, result: dict):
        """Apply a single check result."""
        if key in self.badges:
            self.badges[key].set_status(result)
        self._update_summary(self._check_results)

    def _update_summary(self, results: dict):
        """Update the summary label based on all results."""
        ok_count = sum(1 for r in results.values() if r.get("ok"))
        total = len(results)
        if ok_count == total:
            self.summary_label.configure(
                text=f"All {total} checks passed — ready to transcribe!",
                text_color=COLORS["success"],
            )
        else:
            failed = total - ok_count
            self.summary_label.configure(
                text=f"{ok_count}/{total} passed · {failed} need attention (click {ICONS['retry']} to retry or see fix below)",
                text_color=COLORS["warning"],
            )

    def get_results(self) -> dict:
        return self._check_results

    def is_ready_to_transcribe(self) -> bool:
        """Minimum requirements: python + faster_whisper installed."""
        r = self._check_results
        return r.get("python", {}).get("ok", False) and r.get("faster_whisper", {}).get("ok", False)
