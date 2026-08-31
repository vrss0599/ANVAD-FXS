# ENV-A — Transcription Core (RTX 3050 6GB)

Local `faster-whisper` `CTranslate2` transcription. Replaces `prev-plan.md` Colab `openai-whisper` + `Tesla T4` paywall.
Two-env design: ENV-A outside Resolve (this folder, 6GB CTranslate2) + ENV-B inside Resolve FREE (Console/Scripts).

## Quick Start (Windows)

```powershell
# 0. Prereqs: Python 3.10.11 x64 PATH + ffmpeg on PATH
python --version  # ideally 3.10.x for Resolve Console parity (you have 3.11 — works but re-install 3.10.11 recommended)
ffmpeg -version   # if missing: winget install Gyan.FFmpeg

# 1. ENV-A setup (once)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r transcribe\requirements.txt  # --extra-index-url https://download.pytorch.org/whl/cu121 already included

# 2a. Audio extraction (fallback if not using Resolve Deliver)
python transcribe\extract_audio.py --input "C:\Videos\talk.mp4" --out "exports\talk.wav"  # 16kHz mono PCM
# MVP for FREE: DaVinci Resolve > Deliver > Audio Only > WAV 16kHz mono > Start Render -> exports\audio.wav

# 2b. Transcribe — Kannada+Hindi+English -> English SRT (your case, prev-plan.md:1)
python transcribe\transcribe.py --input "exports\talk.wav" --model large-v3
# -> exports\talk-ENGLISH.srt  (or same folder as input)
# Perf on RTX 3050 Mobile 6GB 120W:
#   large-v3 int8_float16 beam=1 : 1hr ~110s (10-min chunk ~18s)  VRAM 2.5GB
#   turbo float16 (English-only): 1hr ~40s                         VRAM 2.0GB
#   fallback CPU int8            : 1hr ~6min  (24GB RAM)

# 2c. Verify SRT before Resolve import
python transcribe\verify_srt.py --input "exports\talk-ENGLISH.srt"
python transcribe\verify_srt.py --input "exports\talk-ENGLISH.srt" --fix  # auto-fix numbering/CRLF/dot

# 3. Import to DaVinci Resolve FREE (ENV-B, no external API)
# DaVinci > File > Import > Subtitle  or drag SRT onto Media Pool -> Insert Selected Subtitles Using Timecode
# If timeline starts at 01:00:00:00 but SRT at 00:00:00,000, Resolve auto-offsets; verify first cue at 00:01.

# Options
python transcribe\transcribe.py --input "C:\Videos\talk.mp4" --model turbo --task transcribe --language en --beam_size 1
python transcribe\transcribe.py --input "audio.wav" --out "subs\out.srt" --exports_dir "exports"
python transcribe\transcribe.py --input "audio.wav" --stable  # requires pip install stable-ts[fw]
python transcribe\verify_srt.py --input out.srt --strict --max_line_len 42
python transcribe\extract_audio.py --input in.mp4 --sample_rate 16000 --overwrite
```

## Phase Map

* Phase 0: `Python 3.10.11 + ffmpeg + venv` — Foundations
* Phase 1: `transcribe/transcribe.py:39` `format_srt_time()` + CTranslate2 `int8_float16` — Core (done)
* Phase 2: `transcribe/extract_audio.py:40` FFmpeg 16k mono + `transcribe/verify_srt.py:37` BOM/CRLF/dot/overlap checks — Audio & Post (done)
* Phase 3: ENV-B Subtitle Track (File > Import) — 0 code path
* Phase 4: ENV-B Text+ `resolve_free/srt_to_textplus.py` via Console/Utility — coded overlay

## Why This vs prev-plan.md

* `prev-plan.md:45` `whisper.load_model("large-v3", device="cuda")` needs T4 16GB + Colab Pro $ — this uses `WhisperModel("large-v3", device="cuda", compute_type="int8_float16")` 2.5GB on your 3050.
* `vad_filter=True` + `logprob/compression` filters match `prev-plan.md:96-105` thresholds but add Silero VAD and word_timestamps.
* 6GB tuning: `int8_float16`, `beam=1` (saves 1GB vs 5), auto OOM fallback to `int8` then `cpu`.
* Post: `verify_srt.py` catches DaVinci rejects (BOM, CRLF, `00:00:00.000` dot, `□` boxes, overlap <300ms/>10s) before import — prev-plan had no verifier.

## Verify

```powershell
python transcribe\transcribe.py --help
python transcribe\verify_srt.py --help
python transcribe\extract_audio.py --help
python -m py_compile transcribe\transcribe.py transcribe\verify_srt.py transcribe\extract_audio.py
```
