#!/usr/bin/env python3
r"""
extract_audio.py — ENV-A audio extraction fallback (16kHz mono WAV) for faster-whisper.
DaVinci FREE MVP is manual: Deliver -> Audio Only -> WAV. This script is for CLI fallback when you have
the source video/audio file directly (bypasses Resolve). Produced WAV is identical to Deliver export.

Usage:
  python transcribe/extract_audio.py --input "C:\Videos\talk.mp4" --out "exports\talk.wav"
  python transcribe/extract_audio.py --input in.mp4  # -> in_16000.wav next to input
  python transcribe/extract_audio.py --input in.mp3 --out exports/audio.wav --sample_rate 16000

Requires: ffmpeg on PATH (https://ffmpeg.org), in project root/venv, or via pip install imageio-ffmpeg
Verifies: output is 16k mono PCM, duration check, no BWF time_reference drift (reports if present)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

# Safe Windows console encoding for Unicode/multilingual text
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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
    # 1. Direct path
    if Path(arg_path).exists():
        return str(Path(arg_path).resolve())
    
    # 2. System PATH
    found = shutil.which(arg_path) or shutil.which(name)
    if found:
        return found

    # 3. Check local project root & venv folders
    proj_root = Path(__file__).resolve().parent.parent
    candidates = [
        proj_root / "venv" / "Scripts" / f"{name}.exe",
        proj_root / f"{name}.exe",
        proj_root / "bin" / f"{name}.exe",
        proj_root / "ffmpeg" / "bin" / f"{name}.exe",
        proj_root / "ffmpeg" / f"{name}.exe",
        proj_root / "tools" / f"{name}.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())

    # 4. Check imageio_ffmpeg
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).is_file():
                return str(Path(exe).resolve())
        except Exception:
            pass

    print(f"[error] {name} not found: '{arg_path}' not on PATH or in project folder. Install from https://ffmpeg.org", file=sys.stderr)
    print(f"  Windows: winget install Gyan.FFmpeg  or  pip install imageio-ffmpeg", file=sys.stderr)
    print(f"  Then reopen terminal and run: ffmpeg -version", file=sys.stderr)
    sys.exit(3)


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

    print(f"[ffmpeg] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        print(f"[error] failed to run ffmpeg: {e}", file=sys.stderr)
        sys.exit(3)

    if result.returncode != 0:
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
            return dur
    except wave.Error as e:
        print(f"[error] not a valid WAV: {e}", file=sys.stderr)
        sys.exit(1)


def check_time_reference(ffprobe: str, path: Path):
    if not shutil.which(ffprobe) and not Path(ffprobe).exists():
        return
    cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        tags = fmt.get("tags", {})
        tr = tags.get("time_reference") or tags.get("TIME_REFERENCE")
        if tr and tr != "0":
            print(f"[warn] WAV has BWF time_reference={tr} (non-zero) — may offset by {int(tr)/fmt.get('sample_rate', 16000):.3f}s in some NLEs.")
        else:
            print(f"[verify] no BWF time_reference (clean)")
    except Exception:
        pass


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
    print(f"[OK] WAV ready for transcribe.py")
    print(f"  python transcribe/transcribe.py --input \"{out}\" --model large-v3")
    print("=" * 60)


if __name__ == "__main__":
    main()
