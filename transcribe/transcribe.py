#!/usr/bin/env python3
"""
ENV-A: Local transcription with faster-whisper (CTranslate2) — tuned for RTX 3050 Mobile 6GB 120W + 24GB RAM
Replaces prev-plan.md Colab openai-whisper large-v3 + Tesla T4 paywall with fully local, $0 inference.

Default: large-v3 int8_float16 cuda beam=1 vad_filter=True word_timestamps=True task=translate -> SRT
Perf on 3050M: 1hr ~1m43s-2m24s (large-v3) / 30-45s (turbo) ; 10-min chunk ~17-24s
"""

import argparse
import os
import sys
import time
import gc
from pathlib import Path

# Safe Windows console encoding for Unicode/multilingual text (Kannada/Hindi/English)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODEL_ALIASES = {
    "large": "large-v3",
    "large-v3": "large-v3",
    "large-v3-turbo": "large-v3-turbo",
    "turbo": "large-v3-turbo",
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
    "distil-large-v3": "distil-large-v3",
}

# 6GB-tuned defaults
DEFAULT_MODEL = "large-v3"
DEFAULT_COMPUTE_TURBO = "float16"      # 809M fits 2GB
DEFAULT_COMPUTE_LARGE = "int8_float16" # 1.55B fits 2.5GB vs float16 3.1GB
DEFAULT_BEAM = 1  # beam=5 needs +1GB and +30% time for <0.3% WER gain

def format_srt_time(seconds: float) -> str:
    # robust: total milliseconds to avoid float remainder errors (e.g. 3599.9995)
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3600 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            print(f"[device] torch.cuda available -> {name} {total:.2f} GB -> using cuda")
            return "cuda"
        else:
            print("[device] torch.cuda not available -> using cpu")
            return "cpu"
    except ImportError:
        pass
    # fallback: try ctranslate2 without torch
    try:
        import ctranslate2
        # if ctranslate2 lists cuda devices, assume cuda
        # simplest heuristic: check nvidia-smi exists
        import shutil
        if shutil.which("nvidia-smi"):
            print("[device] nvidia-smi found, torch missing -> trying cuda (fallback)")
            return "cuda"
    except Exception:
        pass
    print("[device] defaulting to cpu")
    return "cpu"

def resolve_compute_type(model: str, device: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if device == "cpu":
        return "int8"  # cpu only supports int8/float32, int8 fastest
    # cuda
    if model == "large-v3-turbo":
        return DEFAULT_COMPUTE_TURBO
    return DEFAULT_COMPUTE_LARGE

def load_model_with_fallback(model_name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    attempts = []
    if compute_type == "int8_float16":
        attempts = [compute_type, "int8", "float16"]
    elif compute_type == "float16":
        attempts = [compute_type, "int8_float16", "int8"]
    elif compute_type == "int8":
        attempts = [compute_type, "int8_float16"]
    else:
        attempts = [compute_type]

    # dedup
    seen = []
    for c in attempts:
        if c not in seen:
            seen.append(c)
    attempts = seen

    # on OOM also try cpu
    last_exc = None
    for ct in attempts:
        try:
            print(f"[model] loading '{model_name}' device={device} compute_type={ct} ...")
            t0 = time.time()
            model = WhisperModel(model_name, device=device, compute_type=ct)
            dt = time.time() - t0
            print(f"[model] loaded in {dt:.1f}s")
            try:
                import torch
                if device == "cuda" and torch.cuda.is_available():
                    used = torch.cuda.memory_allocated() / (1024 ** 3)
                    print(f"[model] VRAM allocated: {used:.2f} GB")
            except Exception:
                pass
            return model, ct
        except Exception as e:
            msg = str(e).lower()
            print(f"[model] failed {ct}: {e}")
            last_exc = e
            is_oom = "out of memory" in msg or "cublas" in msg or "cuda" in msg and "memory" in msg
            if not is_oom and "unsupported" not in msg and "compute" not in msg:
                # for non-OOM, don't keep retrying compute types unless it's a compute issue
                if ct == attempts[0] and len(attempts) > 1:
                    continue
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            continue

    # final fallback: cpu int8
    if device == "cuda":
        print("[model] all cuda attempts failed -> falling back to cpu int8 (slower but works on 24GB RAM)")
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            return model, "int8 (cpu)"
        except Exception as e:
            last_exc = e

    raise RuntimeError(f"Failed to load model '{model_name}' after {attempts}: {last_exc}")

def parse_args():
    p = argparse.ArgumentParser(
        description="Local faster-whisper transcribe for RTX 3050 6GB (FREE, no Colab). Kannada+Hindi+English -> English SRT by default.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", "-i", required=True, help="Input audio/video file (wav/mp3/mp4/m4a/mov/mkv etc). Use 16kHz mono WAV from DaVinci Deliver for best speed.")
    p.add_argument("--out", "-o", default=None, help="Output SRT path. Default: <input>-ENGLISH.srt next to input or in exports/")
    p.add_argument("--model", "-m", default=DEFAULT_MODEL, choices=list(MODEL_ALIASES.keys()) + list(set(MODEL_ALIASES.values())), help="Whisper model. large-v3 for kn/hi->en, turbo for English-only 2x faster.")
    p.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="Device. auto -> cuda if torch.cuda available else cpu")
    p.add_argument("--compute_type", default="auto", choices=["auto", "int8_float16", "float16", "int8", "float32"], help="CTranslate2 compute type. auto tuned for 6GB: large-v3->int8_float16, turbo->float16, cpu->int8")
    p.add_argument("--task", default="translate", choices=["translate", "transcribe"], help="translate=kn/hi->en (default), transcribe=keep original language")
    p.add_argument("--language", default=None, help="Force language code (e.g., kn, hi, en) or auto-detect if omitted")
    p.add_argument("--beam_size", type=int, default=DEFAULT_BEAM, help="Beam size. 1=fast/low VRAM (3050 default), 5=more accurate +1GB/+30%% time")
    p.add_argument("--vad_filter", action=argparse.BooleanOptionalAction, default=True, help="Enable Silero VAD to skip silence (recommended, improves timestamps)")
    p.add_argument("--vad_min_silence_ms", type=int, default=500, help="VAD min silence duration ms")
    p.add_argument("--word_timestamps", action=argparse.BooleanOptionalAction, default=True, help="Generate word-level timestamps (needed for stable-ts polish)")
    p.add_argument("--condition_on_previous_text", action=argparse.BooleanOptionalAction, default=False, help="Condition on previous text (False reduces hallucination loops)")
    p.add_argument("--no_speech_threshold", type=float, default=0.6, help="Drop segments with no_speech_prob above this")
    p.add_argument("--log_prob_threshold", type=float, default=-0.8, help="Drop segments with avg_logprob below this (hallucination filter)")
    p.add_argument("--compression_ratio_threshold", type=float, default=2.0, help="Drop segments with compression_ratio above this")
    p.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    p.add_argument("--initial_prompt", default=None, help="Optional initial prompt to bias vocabulary")
    p.add_argument("--stable", action="store_true", help="Use stable-ts (if installed) for VAD+regroup polish +15-25%% time. Otherwise native faster-whisper word_timestamps.")
    p.add_argument("--exports_dir", default=None, help="If --out not set, write SRT into this dir (default: same dir as input). Example: exports/")
    return p.parse_args()

def transcribe_with_faster_whisper(model, args, audio_path: str):
    print("=" * 60)
    print(f"{args.task.upper()}: {Path(audio_path).name} -> English SRT" if args.task == "translate" else f"TRANSCRIBE: {Path(audio_path).name}")
    print("=" * 60)
    print(f"[transcribe] task={args.task} language={args.language or 'auto'} beam={args.beam_size} vad_filter={args.vad_filter} word_timestamps={args.word_timestamps}")

    vad_params = dict(min_silence_duration_ms=args.vad_min_silence_ms) if args.vad_filter else None

    t0 = time.time()
    segments, info = model.transcribe(
        audio_path,
        language=args.language,
        task=args.task,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
        vad_parameters=vad_params,
        word_timestamps=args.word_timestamps,
        condition_on_previous_text=args.condition_on_previous_text,
        temperature=args.temperature,
        compression_ratio_threshold=args.compression_ratio_threshold,
        log_prob_threshold=args.log_prob_threshold,
        no_speech_threshold=args.no_speech_threshold,
        initial_prompt=args.initial_prompt,
    )

    # info contains language detection, duration
    print(f"[info] detected language: {info.language} prob {info.language_probability:.2f}")
    print(f"[info] duration after VAD: {info.duration_after_vad:.1f}s (original ~{info.duration:.1f}s)")

    collected = []
    for seg in segments:
        # faster_whisper segment fields: id, seek, start, end, text, tokens, temperature, avg_logprob, compression_ratio, no_speech_prob, words
        text = seg.text.strip()
        if not text:
            continue
        # filters already applied via thresholds, but extra hallucination guard
        if seg.no_speech_prob is not None and seg.no_speech_prob > args.no_speech_threshold:
            continue
        if seg.avg_logprob is not None and seg.avg_logprob < args.log_prob_threshold:
            # allow slightly below threshold if text is short? keep strict as prev-plan
            continue
        if seg.compression_ratio is not None and seg.compression_ratio > args.compression_ratio_threshold:
            continue
        collected.append(seg)
        # progress echo like prev-plan CELL 7
        print(f"[{seg.start:07.2f} -> {seg.end:07.2f}] {text} (logprob={seg.avg_logprob:.2f} no_speech={seg.no_speech_prob:.2f})")

    dt = time.time() - t0
    rtf = (info.duration / dt) if dt > 0 else 0
    print(f"[done] segments={len(collected)} time={dt:.1f}s RTF={rtf:.1f}x (audio {info.duration:.1f}s / processing {dt:.1f}s)")
    if rtf > 0:
        # estimate for 1hr
        est_1hr = 3600 / rtf
        print(f"[perf] est for 1hr audio: {est_1hr:.0f}s (~{est_1hr/60:.1f} min) at RTF {rtf:.1f}x on this device")
    return collected, info, dt

def transcribe_with_stable_ts(model_path: str, device: str, compute_type: str, args, audio_path: str):
    # stable-ts wraps faster-whisper with regrouping
    import stable_whisper
    print(f"[stable-ts] loading with stable_whisper.load_faster_whisper('{model_path}') vad={args.vad_filter}")
    model = stable_whisper.load_faster_whisper(model_path, device=device, compute_type=compute_type)
    # stable-ts transcribe returns result dict with segments
    result = model.transcribe(
        audio_path,
        language=args.language,
        task=args.task,
        vad=args.vad_filter,
        suppress_silence=True,
        regroup=True,
        vad_threshold=0.5,
        min_word_dur=0.1,
    )
    # convert to objects compatible with rest of pipeline
    # result['segments'] is list of dicts with start/end/text
    class Seg:
        def __init__(self, d):
            self.start = d["start"]
            self.end = d["end"]
            self.text = d["text"]
            self.avg_logprob = -0.5
            self.no_speech_prob = 0.0
            self.compression_ratio = 1.5
            self.words = d.get("words")
    segs = [Seg(s) for s in result["segments"]]
    class Info:
        def __init__(self):
            self.language = result.get("language", args.language or "auto")
            self.language_probability = 0.9
            self.duration = result.get("duration", 0)
            self.duration_after_vad = self.duration
    return segs, Info(), 0

def clean_segments(segments):
    clean = []
    for seg in segments:
        text = seg.text.strip() if hasattr(seg, "text") else str(seg).strip()
        if not text:
            continue
        if clean:
            prev = clean[-1].text.strip()
            # same as prev-plan CELL 8: drop exact repeat within 3s
            if text.lower() == prev.lower() and (seg.start - clean[-1].end) < 3.0:
                print(f"[filter] drop repeat '{text}' at {seg.start:.2f}")
                continue
        clean.append(seg)
    print(f"[filter] original {len(segments)} -> clean {len(clean)}")
    return clean

def write_srt(segments, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for idx, seg in enumerate(segments, start=1):
            f.write(f"{idx}\n")
            f.write(f"{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n")
            txt = seg.text.strip()
            # optional: rudimentary line break at 42 chars without breaking words
            # keep simple for now — DaVinci wraps, but we can split very long cues
            if len(txt) > 84:
                # split into 2 lines at nearest space near 42
                mid = len(txt) // 2
                # find space near mid
                split_at = txt.rfind(" ", 0, 48)
                if split_at == -1:
                    split_at = txt.find(" ", 48)
                if split_at != -1:
                    txt = txt[:split_at] + "\n" + txt[split_at+1:].strip()
            f.write(txt + "\n\n")
    size_kb = out_path.stat().st_size / 1024
    print(f"[srt] wrote {len(segments)} cues -> {out_path} ({size_kb:.1f} KB) UTF-8 LF")
    return out_path

def main():
    args = parse_args()

    audio_path = Path(args.input)
    if not audio_path.exists():
        print(f"[error] input not found: {audio_path}", file=sys.stderr)
        sys.exit(2)
    if audio_path.stat().st_size == 0:
        print(f"[error] input is empty: {audio_path}", file=sys.stderr)
        sys.exit(2)

    model_key = MODEL_ALIASES.get(args.model, args.model)
    device = detect_device(args.device)
    compute_type = resolve_compute_type(model_key, device, args.compute_type)
    print(f"[config] model={model_key} (alias '{args.model}') device={device} compute_type={compute_type} task={args.task}")
    print(f"[config] 3050M 6GB tip: int8_float16 ~2.5GB VRAM for large-v3, float16 ~2GB for turbo, beam=1 saves ~1GB vs 5")

    # stable-ts path
    if args.stable:
        try:
            import stable_whisper  # noqa
            segs, info, _ = transcribe_with_stable_ts(model_key, device, compute_type, args, str(audio_path))
            cleaned = clean_segments(segs)
            # resolve output path
            if args.out:
                out_path = Path(args.out)
            elif args.exports_dir:
                out_path = Path(args.exports_dir) / (audio_path.stem + "-ENGLISH.srt")
            else:
                out_path = audio_path.with_name(audio_path.stem + "-ENGLISH.srt")
                # prefer exports/ if it exists and input is video-like
                exports = Path("exports")
                if exports.is_dir() and audio_path.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi"]:
                    out_path = exports / out_path.name
            write_srt(cleaned, out_path)
            print("=" * 60)
            print("[OK] ENGLISH SRT CREATED (stable-ts)")
            print("=" * 60)
            print(str(out_path))
            return
        except ImportError:
            print("[stable-ts] not installed (pip install stable-ts[fw]) -> falling back to native faster-whisper", file=sys.stderr)
        except Exception as e:
            print(f"[stable-ts] failed {e} -> falling back to native faster-whisper", file=sys.stderr)

    # native faster-whisper path
    try:
        from faster_whisper import WhisperModel  # noqa
    except ImportError:
        print("[error] faster-whisper not installed. Run: pip install -r transcribe/requirements.txt", file=sys.stderr)
        print("  pip install faster-whisper soundfile", file=sys.stderr)
        sys.exit(3)

    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    model, used_ct = load_model_with_fallback(model_key, device, compute_type)
    try:
        segments, info, dt = transcribe_with_faster_whisper(model, args, str(audio_path))
    except Exception as e:
        msg = str(e).lower()
        if "out of memory" in msg or "memory" in msg and "cuda" in msg:
            print(f"[error] OOM with {used_ct}: {e}", file=sys.stderr)
            print("[hint] retry with --compute_type int8 --beam_size 1 or --device cpu", file=sys.stderr)
        raise
    finally:
        # free model VRAM for subsequent runs
        del model
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    cleaned = clean_segments(segments)

    if args.out:
        out_path = Path(args.out)
    elif args.exports_dir:
        out_path = Path(args.exports_dir) / (audio_path.stem + "-ENGLISH.srt")
    else:
        out_path = audio_path.with_name(audio_path.stem + "-ENGLISH.srt")
        # if input is absolute video path and exports/ exists, mirror there for Resolve Import convenience
        try:
            exports = Path(__file__).resolve().parent.parent / "exports"
            if exports.is_dir() and audio_path.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi", ".wav", ".mp3", ".m4a", ".flac"]:
                alt = exports / out_path.name
                # prefer exports if caller didn't specify --out
                out_path = alt
        except Exception:
            pass
        # fallback to input dir if exports not found
        if not out_path.parent.exists():
            out_path = audio_path.with_name(audio_path.stem + "-ENGLISH.srt")

    write_srt(cleaned, out_path)

    print()
    print("=" * 60)
    print("[OK] ENGLISH SRT CREATED")
    print("=" * 60)
    print(str(out_path))
    print(f"Segments: {len(cleaned)}")
    try:
        dur = info.duration
        print(f"Audio duration: {dur:.1f}s")
    except Exception:
        pass

if __name__ == "__main__":
    main()
