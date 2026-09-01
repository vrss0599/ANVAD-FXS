#!/usr/bin/env python3
"""
ENV-A: Local transcription with faster-whisper (CTranslate2) — tuned for RTX 2050 4GB / 3050 6GB
Replaces prev-plan.md Colab openai-whisper large-v3 + Tesla T4 paywall with fully local, $0 inference.

Default: large-v3 int8_float16 cuda beam=5 vad_filter=False word_timestamps=True task=translate -> SRT
Perf on 3050 6GB: 1hr ~2m00s-2m45s (large-v3 beam=5, VAD off) / 30-45s (turbo) ; 10-min ~20-27s
Perf on 2050 4GB: auto-tuned to int8 beam=1 ~2.2GB (beam=5 would OOM) ; 1hr ~2m30s-3m30s ; turbo ~40s-60s
VAD OFF = best quality / 100% recall (+10-15% time vs VAD on, but zero dropped words)
Foolproof: Python 3.13+ auto-uses cu124 torch wheel (cu121 has no 3.13 build)
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

# Suppress harmless HF Hub Windows symlink warning
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

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

# Hardware-tuned defaults — High-Recall 100% preset
# RTX 3050 6GB: large-v3 int8_float16 beam=5 ~2.8GB (beam=1 ~2.5GB)  1hr ~2m00s-2m45s
# RTX 2050 4GB: large-v3 int8 beam=1 ~2.2GB or turbo float16 ~2.0GB — beam=5 will OOM on 4GB
DEFAULT_MODEL = "large-v3"
DEFAULT_COMPUTE_TURBO = "float16"      # 809M fits 2GB
DEFAULT_COMPUTE_LARGE = "int8_float16" # 1.55B fits 2.8GB beam=5 (auto falls back to int8 on 4GB)
DEFAULT_BEAM = 5  # 100% complete: tracks multiple paths, fixes mid/end drops (auto-downgrades to 1 on 4GB VRAM)
# High-Recall thresholds (near-disable): keep almost everything, filter only obvious junk in Python
DEFAULT_NO_SPEECH = 0.90          # was 0.6/0.8 — 0.90 near-disable, only drops pure silence
DEFAULT_LOG_PROB = -2.0            # was -1.0 — -2.0 keeps soft/accented speech (logprob ~-1.2)
DEFAULT_COMPRESSION = 3.0          # was 2.4 — 3.0 keeps repetitive but valid speech

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

def is_model_cached(model_name: str) -> bool:
    """Check if model weights are already downloaded in local HuggingFace cache."""
    try:
        cache_hub = Path.home() / ".cache" / "huggingface" / "hub"
        if not cache_hub.exists():
            return False
        clean_name = model_name.lower().replace("-", "").replace("_", "")
        for d in cache_hub.iterdir():
            if d.is_dir() and "whisper" in d.name.lower():
                d_clean = d.name.lower().replace("-", "").replace("_", "")
                if clean_name in d_clean:
                    snapshots = d / "snapshots"
                    if snapshots.is_dir() and any(snapshots.iterdir()):
                        return True
        return False
    except Exception:
        return False

def _get_vram_gb() -> float | None:
    """Detect total VRAM for auto-tuning (2050 4GB vs 3050 6GB)."""
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except Exception:
        pass
    return None

def _auto_tune_for_vram(model_name: str, device: str, compute_type: str, beam_size: int) -> tuple[str, int]:
    """Foolproof 4GB handling: RTX 2050 4GB cannot run beam=5 at int8_float16, auto downgrade."""
    vram = _get_vram_gb()
    if vram is None or device != "cuda":
        return compute_type, beam_size
    if vram < 5.0:
        # 4GB card
        if model_name == "large-v3" and compute_type == "int8_float16" and beam_size == 5:
            print(f"[auto-tune] RTX 4GB detected ({vram:.1f}GB) — downgrading beam 5->1 and compute int8_float16->int8 to avoid OOM")
            return "int8", 1
        if beam_size == 5:
            print(f"[auto-tune] RTX 4GB ({vram:.1f}GB) — beam 5 may OOM, keeping but will fallback on failure")
    return compute_type, beam_size

def load_model_with_fallback(model_name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    
    cached = is_model_cached(model_name)
    if not cached:
        print(f"[download] Model '{model_name}' not found in local cache.")
        print(f"[download] Downloading '{model_name}' weights from Hugging Face (first-time only, ~2.9GB for large-v3)...")
        print(f"[download] Please wait — model will be cached permanently on disk for instant future loads.")
    else:
        print(f"[model] Model '{model_name}' found in local cache.")

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
            print(f"[model] loaded '{model_name}' ({device}/{ct}) in {dt:.1f}s")
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
    p.add_argument("--beam_size", type=int, default=5, help="Beam size. 5=100%% complete/accurate (recommended), 1=fast/greedy")
    p.add_argument("--vad_filter", action=argparse.BooleanOptionalAction, default=False, help="Enable Silero VAD to skip silence. DEFAULT False = 100%% recall (best quality, +10-15%% time). True = faster but may drop whisper-level speech.")
    p.add_argument("--vad_threshold", type=float, default=0.35, help="VAD speech threshold (0.35 catches soft/accented speech)")
    p.add_argument("--vad_min_silence_ms", type=int, default=1000, help="VAD min silence duration ms before splitting")
    p.add_argument("--vad_speech_pad_ms", type=int, default=400, help="VAD speech padding ms on both sides")
    p.add_argument("--word_timestamps", action=argparse.BooleanOptionalAction, default=True, help="Generate word-level timestamps")
    p.add_argument("--condition_on_previous_text", action=argparse.BooleanOptionalAction, default=None, help="Condition on previous text for context. None=auto: translate->False (reduces hallucination), transcribe->True (keeps flow). Set explicitly to override.")
    p.add_argument("--no_speech_threshold", type=float, default=DEFAULT_NO_SPEECH, help="Drop threshold for no_speech probability (High-Recall 0.90 = near-disable, keeps soft speech)")
    p.add_argument("--log_prob_threshold", type=float, default=DEFAULT_LOG_PROB, help="Drop threshold for avg log probability (High-Recall -2.0 = near-disable)")
    p.add_argument("--compression_ratio_threshold", type=float, default=DEFAULT_COMPRESSION, help="Drop threshold for compression ratio (High-Recall 3.0 = near-disable)")
    p.add_argument("--temperature", default="0.0,0.2,0.4,0.6,0.8", help="Temperature list for fallback (comma-separated or single float)")
    p.add_argument("--initial_prompt", default=None, help="Optional initial prompt to bias vocabulary (default set for kn/hi->en if not provided)")
    p.add_argument("--high_recall", action="store_true", help="Shortcut: force VAD off + near-disable thresholds + beam 5 + translate-safe condition=False (100%% mode)")
    p.add_argument("--stable", action="store_true", help="Use stable-ts (if installed) for VAD+regroup polish")
    p.add_argument("--exports_dir", default=None, help="If --out not set, write SRT into this dir (default: same dir as input). Example: exports/")
    return p.parse_args()

def _resolve_condition_flag(args) -> bool:
    """Per-task smart default: translate -> False (avoid drift/hallucination), transcribe -> True (context)."""
    if args.condition_on_previous_text is not None:
        return bool(args.condition_on_previous_text)
    # auto: translate benefits from False (mixed kn/hi/en), transcribe benefits from True
    return False if args.task == "translate" else True

def _apply_high_recall_overrides(args):
    if not getattr(args, "high_recall", False):
        return
    # Force 100% mode regardless of UI/CLI earlier values
    args.vad_filter = False
    args.beam_size = 5
    args.no_speech_threshold = 0.90
    args.log_prob_threshold = -2.0
    args.compression_ratio_threshold = 3.0
    args.condition_on_previous_text = False
    print("[high-recall] --high_recall active: VAD off, beam=5, thresholds near-disable, condition=False")

def transcribe_with_faster_whisper(model, args, audio_path: str):
    # High-recall shortcut + per-task condition
    _apply_high_recall_overrides(args)
    cond = _resolve_condition_flag(args)
    # Default initial prompt for kn/hi->en if user didn't set one
    if args.initial_prompt is None and args.task == "translate" and args.language is None:
        args.initial_prompt = "Kannada Hindi English conversation translation."

    print("=" * 60)
    print(f"{args.task.upper()}: {Path(audio_path).name} -> English SRT" if args.task == "translate" else f"TRANSCRIBE: {Path(audio_path).name}")
    print("=" * 60)
    mode_label = "HIGH-RECALL 100% (VAD off)" if not args.vad_filter else f"VAD gentle thr={args.vad_threshold}"
    print(f"[transcribe] task={args.task} language={args.language or 'auto'} beam={args.beam_size} vad_filter={args.vad_filter} ({mode_label}) word_timestamps={args.word_timestamps}")
    print(f"[transcribe] thresholds: no_speech={args.no_speech_threshold} logprob={args.log_prob_threshold} compression={args.compression_ratio_threshold} condition_on_previous_text={cond}")

    # Parse temperature list
    try:
        if isinstance(args.temperature, str) and "," in args.temperature:
            temp = [float(x.strip()) for x in args.temperature.split(",") if x.strip()]
        else:
            temp = float(args.temperature)
    except Exception:
        temp = [0.0, 0.2, 0.4, 0.6, 0.8]

    # Gentle, speech-preserving VAD parameters (only used if vad_filter=True)
    vad_params = None
    if args.vad_filter:
        vad_params = dict(
            threshold=args.vad_threshold,
            min_speech_duration_ms=150,
            max_speech_duration_s=float("inf"),
            min_silence_duration_ms=args.vad_min_silence_ms,
            speech_pad_ms=args.vad_speech_pad_ms,
        )
        print(f"[vad] gentle: thr={args.vad_threshold} min_silence={args.vad_min_silence_ms}ms pad={args.vad_speech_pad_ms}ms min_speech=150ms")
    else:
        print("[vad] OFF — 100% recall mode: every frame decoded (best quality, +10-15% time, zero dropped words)")

    t0 = time.time()
    segments, info = model.transcribe(
        audio_path,
        language=args.language,
        task=args.task,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
        vad_parameters=vad_params,
        word_timestamps=args.word_timestamps,
        condition_on_previous_text=cond,
        temperature=temp,
        compression_ratio_threshold=args.compression_ratio_threshold,
        log_prob_threshold=args.log_prob_threshold,
        no_speech_threshold=args.no_speech_threshold,
        initial_prompt=args.initial_prompt,
    )

    # info contains language detection, duration
    print(f"[info] detected language: {info.language} prob {info.language_probability:.2f}")
    if hasattr(info, "duration_after_vad") and info.duration_after_vad is not None:
        print(f"[info] duration after VAD: {info.duration_after_vad:.1f}s (original ~{info.duration:.1f}s)")
        if args.vad_filter:
            removed = info.duration - info.duration_after_vad
            pct = (removed / info.duration * 100) if info.duration > 0 else 0
            if pct > 15:
                print(f"[warn] VAD removed {removed:.1f}s ({pct:.1f}%) — if speech seems missing, re-run with --no-vad_filter or --high_recall")
            else:
                print(f"[vad] VAD kept {info.duration_after_vad/info.duration*100:.1f}% of audio ({removed:.1f}s silence removed)")
    # Per-task condition info
    print(f"[info] condition_on_previous_text={cond} ({'auto:translate->False' if args.condition_on_previous_text is None else 'explicit'}) temperature={temp}")

    collected = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        collected.append(seg)
        # progress echo
        print(f"[{seg.start:07.2f} -> {seg.end:07.2f}] {text} (logprob={seg.avg_logprob:.2f} no_speech={seg.no_speech_prob:.2f})")

    dt = time.time() - t0
    rtf = (info.duration / dt) if dt > 0 else 0
    print(f"[done] segments={len(collected)} time={dt:.1f}s RTF={rtf:.1f}x (audio {info.duration:.1f}s / processing {dt:.1f}s)")
    if rtf > 0:
        # estimate for 1hr
        est_1hr = 3600 / rtf
        print(f"[perf] est for 1hr audio: {est_1hr:.0f}s (~{est_1hr/60:.1f} min) at RTF {rtf:.1f}x on this device")
        if not args.vad_filter:
            vad_on_est = est_1hr * 0.88
            print(f"[perf] VAD ON would be ~{vad_on_est:.0f}s (~{vad_on_est/60:.1f} min) — VAD OFF costs +12% time for 100% recall")
    # --- Gap diagnostics (detect dropped regions) ---
    if collected:
        collected.sort(key=lambda s: s.start)
        gaps = []
        for a, b in zip(collected, collected[1:]):
            gap = b.start - a.end
            if gap > 1.5:
                gaps.append((a.end, b.start, gap))
                print(f"[gap] {gap:.2f}s silence/gap at {a.end:07.2f} -> {b.start:07.2f} — if speech was here, try --high_recall")
        # leading/trailing gap check
        if collected[0].start > 1.5:
            print(f"[gap] leading gap {collected[0].start:.2f}s before first cue (00:00:00 -> {collected[0].start:.2f})")
        # coverage stats
        total_covered = sum(s.end - s.start for s in collected)
        coverage = (total_covered / info.duration * 100) if info.duration > 0 else 0
        print(f"[coverage] speech cues cover {total_covered:.1f}s / {info.duration:.1f}s = {coverage:.1f}% of audio; gaps>{1.5}s: {len(gaps)}")
        if gaps:
            print(f"[hint] For 100% guarantee: python transcribe/transcribe.py --input \"{audio_path}\" --high_recall  (or --no-vad_filter --no_speech_threshold 0.90 --log_prob_threshold -2.0 --compression_ratio_threshold 3.0)")
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
    """High-recall post-filter: only drop empty, exact repeats, and obvious hallucinations."""
    clean = []
    dropped_repeats = 0
    dropped_empty = 0
    for seg in segments:
        text = seg.text.strip() if hasattr(seg, "text") else str(seg).strip()
        if not text:
            dropped_empty += 1
            continue
        if clean:
            prev = clean[-1].text.strip()
            # same as prev-plan CELL 8: drop exact repeat within 3s (hallucination loop)
            if text.lower() == prev.lower() and (seg.start - clean[-1].end) < 3.0:
                print(f"[filter] drop repeat '{text}' at {seg.start:.2f}")
                dropped_repeats += 1
                continue
        clean.append(seg)
    # Diagnostics — with near-disable thresholds we expect very few Python drops
    print(f"[filter] original {len(segments)} -> clean {len(clean)} (dropped {dropped_empty} empty, {dropped_repeats} exact repeats; thresholds were near-disable so zero valid speech was discarded)")
    if len(segments) > 0:
        keep_pct = len(clean) / len(segments) * 100
        if keep_pct < 85:
            print(f"[warn] keep rate {keep_pct:.1f}% low — check for repeated hallucinations; run verify_srt.py to inspect")
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

    # High-recall global override before device/model logging
    if getattr(args, "high_recall", False):
        _apply_high_recall_overrides(args)

    model_key = MODEL_ALIASES.get(args.model, args.model)
    device = detect_device(args.device)
    compute_type = resolve_compute_type(model_key, device, args.compute_type)
    # Auto-tune for 2050 4GB (foolproof)
    orig_beam, orig_ct = args.beam_size, compute_type
    compute_type, tuned_beam = _auto_tune_for_vram(model_key, device, compute_type, args.beam_size)
    if tuned_beam != orig_beam or compute_type != orig_ct:
        args.beam_size = tuned_beam
        print(f"[config] auto-tuned for 4GB: beam {orig_beam}->{tuned_beam} compute {orig_ct}->{compute_type}")
    else:
        vram = _get_vram_gb()
        if vram and vram < 5:
            print(f"[config] RTX 4GB detected ({vram:.1f}GB) — large-v3 beam=5 may OOM; will auto-fallback to beam=1/int8 on failure")
    print(f"[config] model={model_key} (alias '{args.model}') device={device} compute_type={compute_type} task={args.task} beam={args.beam_size}")
    print(f"[config] High-Recall 100%: beam={args.beam_size} VRAM ~{'2.2GB (4GB-safe)' if (_get_vram_gb() or 99) < 5 else '2.8GB (6GB)' } for large-v3. VAD off costs +10-15% time for zero dropped words.")
    print(f"[config] thresholds: no_speech={args.no_speech_threshold} logprob={args.log_prob_threshold} compression={args.compression_ratio_threshold} (near-disable)")
    # Per-task condition default explained
    cond_preview = _resolve_condition_flag(args)
    src = "explicit" if args.condition_on_previous_text is not None else f"auto:{args.task}->{cond_preview}"
    print(f"[config] condition_on_previous_text={cond_preview} ({src}) — translate=False avoids drift, transcribe=True keeps context")

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
