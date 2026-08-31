#!/usr/bin/env python3
"""
UGA-SUB Desktop — Free DaVinci Auto-Subtitles

Launch:  python app/main.py
         python -m app.main

Wraps the CLI transcription pipeline (transcribe.py, extract_audio.py, verify_srt.py)
into an intuitive desktop GUI. No terminal commands needed.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so 'from app.core...' imports work
# when launched as: python app/main.py  (cwd = project root)
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    try:
        import customtkinter as ctk
    except ImportError:
        print("=" * 60)
        print("ERROR: customtkinter is not installed.")
        print("")
        print("Install it with:")
        print("  pip install customtkinter>=5.2.0 pillow>=10.0.0")
        print("")
        print("Or install all app dependencies:")
        print("  pip install -r app/requirements.txt")
        print("=" * 60)
        sys.exit(1)

    # Configure appearance before creating window
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from app.ui.app_window import AppWindow
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
