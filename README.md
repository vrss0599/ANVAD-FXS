# UGA-SUB — Free DaVinci Auto-Subtitles

> **$0, 100% Offline Local AI Subtitling & Translation for DaVinci Resolve FREE**  
> Tuned specifically for **NVIDIA RTX 3050 Mobile 6GB VRAM (120W) + 24GB RAM** with automatic CPU fallback.

---

## Overview

**UGA-SUB** is an end-to-end subtitle generation and timeline injection system designed to bypass paywalls (like Google Colab Pro, Tesla T4 cloud instances, or Resolve Studio's $295 license). It translates mixed **Kannada, Hindi, and English speech directly into clean English SRT subtitles** locally on consumer hardware.

### Two Execution Environments Architecture
* **ENV-A (Outside DaVinci Resolve):** Local ML inference using `faster-whisper` (CTranslate2 engine) + modern CustomTkinter desktop UI. Handles 100% of GPU compute and audio processing.
* **ENV-B (Inside DaVinci Resolve FREE):** Subtitle track import or coded Fusion `Text+` title injection via Resolve's internal Py3 Console and Utility Scripts menu (`%appdata%`). Completely avoids Studio-only restrictions (no `UIManager`, no external `DaVinciResolveScript`).

---

## Hardware Benchmarks (RTX 3050 Mobile 6GB 120W)

| Model | Precision / Compute | VRAM Used | Speed (1hr Audio) | Primary Use Case |
| :--- | :--- | :---: | :---: | :--- |
| **`large-v3`** | `int8_float16` (beam=1) | **~2.5 GB** | **1m 43s – 2m 24s** | Kannada / Hindi / Multilingual $\to$ English |
| **`turbo`** | `float16` | **~2.0 GB** | **30s – 45s** | English-only (2× speed) |
| **CPU Fallback** | `int8` (24GB System RAM) | **0 GB VRAM** | **~6 min** | Any machine without NVIDIA GPU |

---

## Requirements & Prerequisites

1. **Operating System:** Windows 10 / 11 (64-bit)
2. **Python:** Python `3.10.x` or `3.11.x` 64-bit installed with **Add Python to PATH** checked.
3. **GPU & Drivers:** NVIDIA GPU (RTX 3050 6GB recommended) with Driver version $\ge$ 537. *(Runs in CPU mode if no NVIDIA GPU is present)*.
4. **FFmpeg:** Required for audio extraction from video containers.
5. **DaVinci Resolve:** DaVinci Resolve FREE 18.x / 19.x (installed from [blackmagicdesign.com](https://www.blackmagicdesign.com/products/davinciresolve), not the Microsoft Store).

---

## Step 1: Fork, Clone & Environment Setup

### 1. Fork and Clone Repository
```powershell
# Clone your fork or the repository
git clone https://github.com/vrss0599/ANVAD-FXS.git UGA-SUB-DR
cd UGA-SUB-DR
```

### 2. Install FFmpeg (System-wide)
If you don't already have FFmpeg on your PATH:
```powershell
winget install Gyan.FFmpeg
# Restart your terminal/PowerShell and verify:
ffmpeg -version
```

### 3. Create Virtual Environment & Install Dependencies
```powershell
# Create venv in project root
python -m venv venv

# Activate venv
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install desktop UI dependencies
pip install -r app/requirements.txt

# Install ML transcription core (faster-whisper, PyTorch cu121, cuDNN wheels)
pip install -r transcribe/requirements.txt
```

> **Note on CUDA:** `transcribe/requirements.txt` includes `--extra-index-url https://download.pytorch.org/whl/cu121` and standalone `nvidia-cudnn-cu12` wheels. You do **not** need a manual CUDA Toolkit installation if your NVIDIA drivers are up to date.

---

## Step 2: Launch the Desktop UI

Launch the modern 5-step wizard desktop application:

```powershell
.\venv\Scripts\activate
python app/main.py
```

### Desktop UI Features (UX-First Design)
1. **System Status Panel:** Real-time badges checking Python, Virtual Environment, FFmpeg, GPU CUDA, faster-whisper, and HuggingFace cache.
   - Any failing dependency turns **Red** with a **↻ Retry button** and an actionable **Copy Command** fix hint.
2. **Audio/Video Input:** Drag-and-drop / file browser supporting `.wav`, `.mp3`, `.m4a`, `.mp4`, `.mov`, `.mkv`. Inspects duration, sample rate, channels, and flags non-16kHz audio.
3. **Settings:** Dropdowns for Model (`large-v3`, `turbo`, `medium`, `small`, `base`, `tiny`), Task (`Translate to English` vs `Transcribe`), and Language. Includes an expandable **Advanced Settings** menu for beam size, Silero VAD toggle, and device overrides.
4. **Transcription Engine:** One-click automated pipeline (Extract audio $\to$ Transcribe $\to$ Auto-fix SRT). Features a live progress bar, estimated time remaining (ETA), real-time factor (RTF), and streaming console logs.
5. **Output & Resolve Integration:** Live SRT preview, 1-click Save SRT file, Copy Path, and integrated DaVinci Resolve import instructions.

---

## Step 3: CLI Alternative Workflow

If you prefer running via command line instead of the desktop UI:

### 1. Audio Extraction (FFmpeg fallback)
Extract 16kHz mono PCM 16-bit WAV (matches Resolve Deliver page output):
```powershell
python transcribe/extract_audio.py --input "C:\Videos\interview.mp4" --out "exports\audio.wav"
```

### 2. Local AI Transcription
Translate Kannada/Hindi/English audio to English SRT:
```powershell
python transcribe/transcribe.py --input "exports\audio.wav" --model large-v3 --task translate
```
*Outputs to `exports/audio-ENGLISH.srt`.*

### 3. Validate & Fix SRT
Verify syntax, strip UTF-8 BOM, fix comma/dot timestamp delimiters, and split cues >42 chars:
```powershell
python transcribe/verify_srt.py --input "exports\audio-ENGLISH.srt" --fix
```

---

## Step 4: DaVinci Resolve FREE Injection (ENV-B)

### Path A — Subtitle Track Lane (Recommended, 0 Code)

1. Open your project timeline in **DaVinci Resolve**.
2. Go to **File $\to$ Import $\to$ Subtitle** and select `exports/audio-ENGLISH.srt` (or drag the SRT directly from the Media Pool onto the timeline).
3. In the popup dialog, choose: **Insert Selected Subtitles to Timeline Using Timecode** $\to$ Click **OK**.
4. **Timeline Offset Note:** If your timeline starts at `01:00:00:00` (DaVinci default) and your SRT starts at `00:00:00,000`, Resolve automatically adds the 1-hour offset. Verify your first cue aligns with speech.
5. Select subtitle clips on the timeline and use **Inspector $\to$ Caption** to adjust font, size, line wrap, and background.
6. On the **Deliver** page $\to$ **Subtitle Settings** $\to$ Choose **Burn into video** or **Export as separate file**.

---

### Path B — Coded Text+ Title Overlay (`srt_to_textplus.py`)

For styled Fusion Text+ titles with individual motion graphic/font styling:

#### 1. Setup Fusion Text+ Template in Resolve (One-time)
1. Open DaVinci Resolve $\to$ go to the **Fusion** or **Edit** page.
2. In **Effects Library $\to$ Titles $\to$ Text+**, drag a Text+ title into your **Media Pool $\to$ Master** folder.
3. Right-click the clip in Media Pool $\to$ **Change Clip Name** $\to$ rename to: `TEMPLATE_Subtitle`.
4. Style this template clip (font, color, stroke, drop shadow, position) to your liking.

#### 2. Install Scripts to Resolve Utility Folder
Copy the scripts from `resolve_free/` into DaVinci Resolve's application scripts directory:
```powershell
# Copy scripts to Resolve AppData
$resolveDir = "$env:APPDATA\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
New-Item -ItemType Directory -Force -Path $resolveDir
Copy-Item "resolve_free\srt_to_textplus.py" "$resolveDir\"
Copy-Item "resolve_free\check_timeline.py" "$resolveDir\"
Copy-Item "resolve_free\config.json" "$resolveDir\"
```

#### 3. Configure `config.json`
Edit `$resolveDir\config.json` (or `resolve_free/config.json`) with forward slashes:
```json
{
  "srt_path": "C:/Users/Shreyas Shetty/UGA-SUB-DR/exports/audio-ENGLISH.srt",
  "targetTrack": 2,
  "templatePattern": "TEMPLATE",
  "fps": null,
  "clipColor": "Orange",
  "useTrackLock": true
}
```

#### 4. Execute Script Inside Resolve
1. Inside Resolve, open your project timeline. Ensure Video Track 2 (`V2`) is empty or ready for subtitles.
2. Open **Workspace $\to$ Console $\to$ Py3 tab**.
3. Run the following command:
```python
exec(open(r"C:\Users\Shreyas Shetty\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\srt_to_textplus.py", encoding="utf-8").read())
```
*Or navigate to **Workspace $\to$ Scripts $\to$ Utility $\to$ srt_to_textplus**.*

The script will:
- Lock track `V1` to prevent timeline ripple.
- Append template Text+ items to track `V2` matching exact start/end frames.
- Inject the subtitle text into each clip's Fusion composition (`StyledText`).
- Restore your track lock settings.

---

## Debugging & Troubleshooting Guide

### 1. `nvidia-smi` Not Found / GPU Shows "None"
- **Cause:** NVIDIA graphic drivers are not installed, or your laptop is running on integrated graphics (Intel Iris Xe / AMD Radeon).
- **Fix:** Download the latest Game Ready or Studio Driver from [nvidia.com/drivers](https://www.nvidia.com/download/index.aspx). If on a laptop, verify discrete GPU is enabled in BIOS / Windows Graphics Settings.
- **Workaround:** The application will automatically fall back to CPU `int8` mode.

### 2. CUDA Out of Memory (OOM) on 6GB VRAM
- **Symptom:** `torch.cuda.OutOfMemoryError` or CTranslate2 memory allocation crash.
- **Fix:**
  1. Set **Beam Size = 1** (default). Beam size 5 adds ~1GB VRAM for negligible accuracy improvement.
  2. Use **`compute_type="int8_float16"`** for `large-v3` (~2.5GB VRAM).
  3. Switch to the **`turbo`** model (`float16`, ~2.0GB VRAM) for English speech.
  4. In desktop UI Advanced Settings, select **Device: CPU**.

### 3. FFmpeg Missing Error
- **Symptom:** `[error] ffmpeg not found: 'ffmpeg' not on PATH`.
- **Fix:** Install via `winget install Gyan.FFmpeg`, then close and reopen your terminal / desktop app.

### 4. Timestamp Drift / Frame Rate Rounding (e.g., 29.97 fps)
- **Symptom:** Subtitle sync gradually drifts away from audio across a 30+ minute video.
- **Cause:** Using integer frame rates (`29` or `30`) instead of float (`29.97` or `23.976`).
- **Fix:** `srt_to_textplus.py` queries `timeline.GetSetting("timelineFrameRate")` as `float`. If your timeline uses non-standard drop-frame rates, explicitly set `"fps": 29.97` in `config.json`.

### 5. `DaVinciResolveScript not importable`
- **Cause:** You attempted to run `srt_to_textplus.py` from external Windows PowerShell or an IDE.
- **Fix:** DaVinci Resolve FREE disables external API socket connections. You **must** execute `srt_to_textplus.py` from **inside** DaVinci Resolve (`Workspace -> Console -> Py3` or `Workspace -> Scripts`).

### 6. Subtitles Appear as Boxes (`□□□`) or Reject Import
- **Cause:** UTF-8 BOM (`\xef\xbb\xbf`), CRLF line endings, or dot delimiters (`00:00:00.000`).
- **Fix:** Run `python transcribe/verify_srt.py --input <file.srt> --fix` to strip BOM and standardize timecodes.

### 7. Run Pre-flight Timeline Diagnostics
To inspect your timeline frame rate, start frame, and track configuration before injection, run inside Resolve Py3 Console:
```python
exec(open(r"C:\Users\Shreyas Shetty\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\check_timeline.py", encoding="utf-8").read())
```

---

## Repository Structure

```
UGA-SUB-DR/
├── app/                              # CustomTkinter Modern Desktop App
│   ├── main.py                       # App entry point
│   ├── requirements.txt              # App GUI dependencies (customtkinter, pillow)
│   ├── core/                         # Pure backend business logic
│   │   ├── readiness.py              # System & hardware readiness validator
│   │   ├── audio_info.py             # Audio/video container metadata parser
│   │   ├── runner.py                 # Threaded subprocess execution & streaming
│   │   └── srt_parser.py             # SRT parser and summarizer
│   └── ui/                           # UI Components
│       ├── theme.py                  # Design tokens, color palette, typography
│       ├── app_window.py             # Main application scrollable container
│       ├── section_status.py         # Section 1: System Status & ↻ Retry Badges
│       ├── section_input.py          # Section 2: File Picker & Audio Metadata
│       ├── section_settings.py       # Section 3: Model, Task & Advanced Settings
│       ├── section_transcribe.py     # Section 4: Transcription Engine & Live Logs
│       └── section_output.py         # Section 5: SRT Result & Resolve Instructions
├── transcribe/                       # Core Transcription & Audio Modules (ENV-A)
│   ├── transcribe.py                 # faster-whisper CTranslate2 STT engine
│   ├── extract_audio.py              # FFmpeg 16kHz mono WAV extraction
│   ├── verify_srt.py                 # Resolve-safe SRT syntax checker & auto-fixer
│   ├── config.example.json           # Model configuration preset
│   └── requirements.txt              # ML dependencies (faster-whisper, torch cu121)
├── resolve_free/                     # DaVinci Resolve FREE Integration (ENV-B)
│   ├── srt_to_textplus.py            # Automated Fusion Text+ title generator
│   ├── check_timeline.py             # Timeline pre-flight diagnostic script
│   ├── config.json                   # Injection track & template configuration
│   └── config.example.json           # Example injection config
├── exports/                          # Destination for generated WAV & SRT files
│   └── generated-ENGLISH.srt         # Demo test subtitle
├── final-plan.md                     # Hardware architectural plan
└── README.md                         # Project documentation
```

---

## License & Attribution
Free and open-source under the MIT License. Built with `faster-whisper` (Systran / OpenAI Whisper), `CustomTkinter` (Tom Schimansky), and DaVinci Resolve scripting API.
