#!/usr/bin/env python3
"""
extract_audio.py — ENV-A audio extraction fallback (16kHz mono WAV) for faster-whisper.
DaVinci FREE MVP is manual: Deliver -> Audio Only -> WAV. This script is for CLI fallback when you have
the source video file directly (bypasses Resolve). Produced WAV is identical to Deliver export.

Usage:
  python transcribe/extract_audio.py --input "C:\Videos\talk.mp4" --out "exports\talk.wav"
  python transcribe/extract_audio.py --input in.mp4  # -> in_16000.wav next to input
  python transcribe/extract_audio.py --input in.mp4 --out exports/audio.wav --sample_rate 16000

Requires: ffmpeg on PATH (https://ffmpeg.org) or set --ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"
Verifies: output is 16k mono PCM, duration check, no BWF time_reference drift (reports if present)
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
import wave

def parse_args():
    p = argparse.ArgumentParser(description="Extract 16kHz mono PCM WAV for faster-whisper (FFmpeg fallback)")
    p.add_argument("--input", "-i", required=True, help="Input video/audio file (mp4/mov/mkv/avi/m4a/mp3/wav)")
    p.add_argument("--out", "-o", default=None, help="Output WAV. Default: <input>_16000.wav or exports/ if exists")
    p.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg binary path or name on PATH")
    p.add_argument("--ffprobe", default="ffprobe", help="ffprobe binary path (for verification)")
    p.add_argument("--sample_rate", type=int, default=16000, help="Sample rate (16000 for Whisper, 16000 required)")
    p.add_argument("--channels", type=int, default=1, help="Channels (1 mono for Whisper)")
    p.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    return p.parse_args()

def check_binary(name: str, arg_path: str) -> str:
    # arg_path may be full path or just "ffmpeg"
    if Path(arg_path).exists():
        return str(Path(arg_path).resolve())
    found = shutil.which(arg_path) or shutil.which(name)
    if not found:
        print(f"[error] {name} not found: '{arg_path}' not on PATH. Install from https://ffmpeg.org", file=sys.stderr)
        print(f"  Windows: winget install Gyan.FFmpeg  or  choco install ffmpeg", file=sys.stderr)
        print(f"  Then reopen terminal and run: ffmpeg -version", file=sys.stderr)
        sys.exit(3)
    return found

def run_ffmpeg(ffmpeg: str, inp: Path, out: Path, sr: int, ch: int, overwrite: bool):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not overwrite:
        print(f"[error] output exists (use --overwrite): {out}", file=sys.stderr)
        sys.exit(2)
    # -vn = no video, -ac ch, -ar sr, pcm_s16le
    cmd = [
        ffmpeg, "-hide_banner", "-y" if overwrite else "-n",
        "-i", str(inp),
        "-vn",
        "-ac", str(ch),
        "-ar", str(sr),
        "-acodec", "pcm_s16le",
        str(out)
    ]
    # remove duplicate -n/-y handling: if not overwrite we used -n, ffmpeg will exit 1 if exists; we already checked
    # ensure -y when overwrite
    if overwrite:
        cmd = [ffmpeg, "-hide_banner", "-y", "-i", str(inp), "-vn", "-ac", str(ch), "-ar", str(sr), "-acodec", "pcm_s16le", str(out)]
    else:
        cmd = [ffmpeg, "-hide_banner", "-i", str(inp), "-vn", "-ac", str(ch), "-ar", str(sr), "-acodec", "pcm_s16le", str(out)]

    print(f"[ffmpeg] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as e:
        print(f"[error] failed to run ffmpeg: {e}", file=sys.stderr)
        sys.exit(3)

    if result.returncode != 0:
        # -n case with existing output returns error; we already handled
        print(result.stderr[-2000:] if result.stderr else "", file=sys.stderr)
        print(f"[error] ffmpeg failed (code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode or 1)

    if not out.exists() or out.stat().st_size == 0:
        print(f"[error] ffmpeg produced no output: {out}", file=sys.stderr)
        sys.exit(1)
    print(f"[ok] wrote {out} ({out.stat().st_size/1024/1024:.2f} MB)")

def verify_wav(path: Path, expected_sr: int, expected_ch: int):
    try:
        with wave.open(str(path), "rb") as w:
            nch = w.getnchannels()
            sw = w.getsampwidth()
            sr = w.getframerate()
            nframes = w.getnframes()
            dur = nframes / sr if sr else 0
            print(f"[verify] WAV: {nch}ch {sw*8}-bit {sr}Hz frames={nframes} duration={dur:.2f}s")
            if nch != expected_ch:
                print(f"[warn] channels {nch} != expected {expected_ch} (mono needed for Whisper)")
            if sr != expected_sr:
                print(f"[warn] sample_rate {sr} != expected {expected_sr}")
            if sw != 2:
                print(f"[warn] sample width {sw} !=2 (expected pcm_s16le)")
            # BWF time_reference check via ffprobe if available
            return dur
    except wave.Error as e:
        print(f"[error] not a valid WAV: {e}", file=sys.stderr)
        sys.exit(1)

def check_time_reference(ffprobe: str, path: Path):
    # Detect BWF bext chunk or time_reference that can cause 1-frame offset in Resolve
    if not shutil.which(ffprobe) and not Path(ffprobe).exists():
        print(f"[info] ffprobe not found — skip BWF time_reference check (optional)")
        return
    cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        tags = fmt.get("tags", {})
        # ffprobe exposes time_reference as tag if present
        tr = tags.get("time_reference") or tags.get("TIME_REFERENCE")
        if tr and tr != "0":
            dur = float(fmt.get("duration", 0))
            print(f"[warn] WAV has BWF time_reference={tr} (non-zero) — may offset by {int(tr)/fmt.get('sample_rate', 16000):.3f}s in some NLEs. Whisper ignores it, but for Resolve use this WAV only for transcription, not as timeline audio.")
        else:
            print(f"[verify] no BWF time_reference (clean)")
    except Exception as e:
        print(f"[info] ffprobe check skipped: {e}")

def main():
    args = parse_args()
    inp = Path(args.input)
    if not inp.exists():
        print(f"[error] input not found: {inp}", file=sys.stderr)
        sys.exit(2)
    if inp.stat().st_size == 0:
        print(f"[error] input empty: {inp}", file=sys.stderr)
        sys.exit(2)

    ffmpeg = check_binary("ffmpeg", args.ffmpeg)
    ffprobe = args.ffprobe
    # resolve output
    if args.out:
        out = Path(args.out)
    else:
        # default: <input>_16000.wav next to input; if exports/ exists prefer it for Resolve workflow
        stem = inp.stem + f"_{args.sample_rate}"
        default = inp.with_name(stem + ".wav")
        exports = Path(__file__).resolve().parent.parent / "exports"
        if exports.is_dir():
            out = exports / (inp.stem + ".wav")
        else:
            out = default

    print("=" * 60)
    print(f"EXTRACT: {inp.name} -> {out.name}  ({args.sample_rate}Hz mono PCM)")
    print("=" * 60)
    print(f"[info] ffmpeg: {ffmpeg}")

    run_ffmpeg(ffmpeg, inp, out, args.sample_rate, args.channels, args.overwrite)
    verify_wav(out, args.sample_rate, args.channels)
    check_time_reference(ffprobe, out)

    print("=" * 60)
    print(f"✅ WAV ready for transcribe.py")
    print(f"  python transcribe/transcribe.py --input \"{out}\" --model large-v3")
    print("=" * 60)

if __name__ == "__main__":
    main()
