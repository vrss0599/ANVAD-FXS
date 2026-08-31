"""UGA-SUB theme — centralized design tokens."""

# Color palette (dark theme primary, light theme secondary)
COLORS = {
    "bg":           ("#f0f0f0", "#1a1a2e"),       # main background
    "card":         ("#ffffff", "#16213e"),       # section card background
    "card_border":  ("#d0d0d0", "#1f3055"),       # subtle card border
    "accent":       ("#0f97b5", "#0f97b5"),       # teal accent
    "accent_hover": ("#0b7a94", "#12b8d8"),       # accent hover
    "success":      ("#28a745", "#28a745"),       # green
    "error":        ("#dc3545", "#dc3545"),       # red
    "warning":      ("#e6a817", "#ffc107"),       # orange/yellow
    "muted":        ("#868e96", "#6c757d"),       # gray
    "text":         ("#1a1a1a", "#e8e8e8"),       # primary text
    "text_dim":     ("#555555", "#a0a0a0"),       # secondary text
    "badge_ok_bg":  ("#d4edda", "#1e3a2c"),       # green badge bg
    "badge_ok_fg":  ("#155724", "#28a745"),       # green badge text
    "badge_err_bg": ("#f8d7da", "#3a1e1e"),       # red badge bg
    "badge_err_fg": ("#721c24", "#dc3545"),       # red badge text
    "badge_warn_bg":("#fff3cd", "#3a331e"),       # yellow badge bg
    "badge_warn_fg":("#856404", "#ffc107"),       # yellow badge text
    "badge_na_bg":  ("#e2e3e5", "#2a2a3a"),       # gray badge bg
    "badge_na_fg":  ("#383d41", "#6c757d"),       # gray badge text
    "log_bg":       ("#f8f9fa", "#0d1117"),       # console log background
    "log_fg":       ("#212529", "#c9d1d9"),       # console log text
}

# Font definitions (family, size, weight)
FONTS = {
    "title":      ("Segoe UI", 20, "bold"),
    "heading":    ("Segoe UI", 14, "bold"),
    "subheading": ("Segoe UI", 12, "bold"),
    "body":       ("Segoe UI", 12, "normal"),
    "small":      ("Segoe UI", 10, "normal"),
    "mono":       ("Cascadia Code", 11, "normal"),
    "mono_small": ("Cascadia Code", 10, "normal"),
    "badge":      ("Segoe UI", 11, "bold"),
}

# Spacing
PAD = {
    "section": 12,        # between sections
    "card_inner": 16,     # padding inside card
    "card_outer_x": 8,    # horizontal margin of card
    "element": 8,         # between elements within section
    "small": 4,           # small gap
}

# Dimensions
DIM = {
    "window_width": 740,
    "window_height": 880,
    "window_min_width": 600,
    "window_min_height": 700,
    "card_corner": 12,
    "button_corner": 8,
    "badge_corner": 6,
    "progress_height": 12,
    "log_height": 180,
}

# Icons (Unicode symbols used as icon text)
ICONS = {
    "check":    "✓",
    "cross":    "✗",
    "warning":  "⚠",
    "retry":    "↻",
    "folder":   "📁",
    "file":     "📄",
    "play":     "▶",
    "stop":     "⏹",
    "save":     "💾",
    "copy":     "📋",
    "resolve":  "🎬",
    "gear":     "⚙",
    "info":     "ℹ",
    "gpu":      "🖥",
    "model":    "🧠",
    "audio":    "🔊",
}
