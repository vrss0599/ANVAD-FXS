#!/usr/bin/env python3
"""
verify_srt.py — Validates SRT for DaVinci Resolve FREE import.
Blocks common rejects: bad numbering, comma vs dot, UTF-8 BOM, overlap, empty cues, long lines.

Usage:
  python transcribe/verify_srt.py --input exports/audio-ENGLISH.srt
  python transcribe/verify_srt.py --input subs.srt --fix  # auto-fixes numbering/line endings
  python transcribe/verify_srt.py --input out.srt --strict  # fail on warnings

Exit 0 = OK (or fixed), 1 = errors, 2 = warnings (if --strict)
"""

import argparse
import re
import sys
from pathlib import Path

# Safe Windows console encoding for Unicode/multilingual text
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TIMESTAMP_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)
TIMESTAMP_DOT_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}")

def srt_time_to_ms(h, m, s, ms):
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

def parse_args():
    p = argparse.ArgumentParser(description="Validate SRT for DaVinci Resolve FREE")
    p.add_argument("--input", "-i", required=True, help="SRT file to verify")
    p.add_argument("--fix", action="store_true", help="Auto-fix numbering, CRLF->LF, trailing spaces, dot->comma")
    p.add_argument("--max_line_len", type=int, default=42, help="Warn if line exceeds this (Resolve wraps but 42 is safe)")
    p.add_argument("--max_lines_per_cue", type=int, default=2, help="Warn if cue has more than N lines")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    p.add_argument("--encoding", default="utf-8", help="Expected encoding (default utf-8)")
    return p.parse_args()

def verify(path: Path, fix: bool = False, max_line_len: int = 42, max_lines_per_cue: int = 2):
    errors = []
    warnings = []
    cues = []

    raw = path.read_bytes()
    # checks before decode
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("BOM detected (UTF-8 with BOM) -- DaVinci may show boxes. Save as UTF-8 without BOM.")
        if fix:
            raw = raw[3:]
    if b"\r\n" in raw:
        warnings.append("CRLF line endings found -- will normalize to LF (DaVinci accepts both but LF is canonical).")
        if fix:
            raw = raw.replace(b"\r\n", b"\n")
    if b"\r" in raw and b"\n" not in raw.replace(b"\r\n", b""):
        warnings.append("Old Mac CR line endings found.")
        if fix:
            raw = raw.replace(b"\r", b"\n")

    # dot instead of comma
    if TIMESTAMP_DOT_RE.search(raw.decode("utf-8", errors="ignore")):
        # check if any timestamp uses dot
        dot_count = len(re.findall(r"\d{2}:\d{2}:\d{2}\.\d{3}", raw.decode("utf-8", errors="ignore")))
        errors.append(f"Timestamp uses '.' instead of ',' ({dot_count} occurrences) -- SRT requires ','. Example: 00:00:01,000 --> 00:00:02,000")
        if fix:
            # fix only timestamps
            text = raw.decode("utf-8", errors="ignore")
            text = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", text)
            raw = text.encode("utf-8")

    try:
        # use utf-8-sig to strip BOM for parsing (error already reported)
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        errors.append(f"Not valid UTF-8: {e}. Re-save as UTF-8.")
        return errors, warnings, cues, raw

    # check for boxes: non-UTF-8 decodable? Already done. Also check for replacement char
    if "\ufffd" in text:
        warnings.append("Text contains U+FFFD replacement char -- possible encoding corruption.")

    # split into blocks by blank line (2+ newlines)
    # Keep trailing newline handling
    blocks = re.split(r"\n{2,}", text.strip())
    if not blocks or blocks == [""]:
        errors.append("Empty SRT or no cues found.")
        return errors, warnings, cues, raw

    prev_end_ms = -1
    expected_num = 1
    for idx, block in enumerate(blocks, start=1):
        lines = block.strip().split("\n")
        lines = [l.rstrip() for l in lines]  # trim trailing spaces if fix, then check
        if fix:
            # remove trailing spaces already done via rstrip
            pass
        else:
            # warn on trailing spaces
            for l in block.split("\n"):
                if l != l.rstrip():
                    warnings.append(f"Cue {idx}: trailing spaces on line '{l[:40]}'")

        if len(lines) < 2:
            errors.append(f"Cue block {idx}: expected at least 2 lines (number + timestamp), got {len(lines)}: {block[:80]!r}")
            continue

        # number line
        num_line = lines[0].strip()
        try:
            num = int(num_line)
        except ValueError:
            errors.append(f"Cue block {idx}: first line not an integer cue number: '{num_line}'")
            num = expected_num

        if num != expected_num:
            warnings.append(f"Cue {idx}: numbering {num} != expected {expected_num} (may still import but will be renumbered)")
            if fix:
                num = expected_num

        # timestamp line
        ts_line = lines[1].strip()
        m = TIMESTAMP_RE.match(ts_line)
        if not m:
            # try to give helpful error
            if "-->" not in ts_line:
                errors.append(f"Cue {num}: missing '-->' in timestamp line: '{ts_line}'")
            elif "," not in ts_line:
                errors.append(f"Cue {num}: timestamp missing comma (found dot?): '{ts_line}'")
            else:
                errors.append(f"Cue {num}: malformed timestamp: '{ts_line}' expected HH:MM:SS,mmm --> HH:MM:SS,mmm")
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = m.groups()
        try:
            start_ms = srt_time_to_ms(h1, m1, s1, ms1)
            end_ms = srt_time_to_ms(h2, m2, s2, ms2)
        except ValueError as e:
            errors.append(f"Cue {num}: invalid time values: {e}")
            continue

        # range checks
        for v, label in [(int(h1), "start hours"), (int(h2), "end hours"), (int(m1), "start minutes"), (int(m2), "end minutes"), (int(s1), "start seconds"), (int(s2), "end seconds")]:
            if label.endswith("hours") and v > 99:
                warnings.append(f"Cue {num}: {label} {v} >99 (allowed but unusual)")
            if "minutes" in label and v > 59:
                errors.append(f"Cue {num}: {label} {v} >59")
            if "seconds" in label and v > 59:
                errors.append(f"Cue {num}: {label} {v} >59")
        if int(ms1) > 999 or int(ms2) > 999:
            errors.append(f"Cue {num}: milliseconds >999")

        if end_ms <= start_ms:
            errors.append(f"Cue {num}: end {ts_line.split('-->')[1].strip()} <= start {ts_line.split('-->')[0].strip()} (zero/negative duration)")
        if start_ms < 0:
            errors.append(f"Cue {num}: negative start time")

        # overlap check (Resolve allows but warns)
        if prev_end_ms != -1 and start_ms < prev_end_ms:
            overlap = prev_end_ms - start_ms
            warnings.append(f"Cue {num}: overlaps previous by {overlap}ms (prev end {prev_end_ms}ms, this start {start_ms}ms)")
        prev_end_ms = max(prev_end_ms, end_ms)

        # text lines
        text_lines = lines[2:]
        if not text_lines or all(not l.strip() for l in text_lines):
            errors.append(f"Cue {num}: empty text (no subtitle content)")
            continue

        # length checks
        if len(text_lines) > max_lines_per_cue:
            warnings.append(f"Cue {num}: {len(text_lines)} lines > max {max_lines_per_cue} -- DaVinci wraps but may overflow safe area")
        for l in text_lines:
            if len(l) > max_line_len:
                warnings.append(f"Cue {num}: line >{max_line_len} chars ({len(l)}): '{l[:50]}...'")
            if len(l) > 80:
                warnings.append(f"Cue {num}: very long line {len(l)} chars may exceed Resolve safe area")
            # box char check: common mojibake
            if "□" in l or "�" in l:
                warnings.append(f"Cue {num}: contains box/replacement char -- possible font/encoding issue")

        dur = end_ms - start_ms
        if dur < 300:
            warnings.append(f"Cue {num}: very short duration {dur}ms (<300ms) may flash")
        if dur > 10000:
            warnings.append(f"Cue {num}: very long duration {dur}ms (>10s) -- consider splitting")

        cues.append((num, start_ms, end_ms, text_lines))

        expected_num += 1
        # if fix, we would rewrite block with correct number — handled at write stage

    # global checks
    if cues:
        total_dur = cues[-1][2] - cues[0][1]
        if total_dur <= 0:
            warnings.append("Total SRT duration <=0 (all cues at same time?)")
        # check for huge gap at start (SRT starts at 00:00:00,000 but timeline may be 01:00:00:00)
        if cues[0][1] > 3600 * 1000:
            warnings.append(f"First cue starts at {cues[0][1]/1000:.1f}s (>1hr) -- if DaVinci timeline starts at 01:00:00:00, this is expected; else check offset")

    # prepare fixed raw if needed
    fixed_raw = None
    if fix and (errors or warnings):
        # rebuild file with corrected numbering and normalized line endings
        out_lines = []
        for i, (num, start_ms, end_ms, _) in enumerate(cues, start=1):
            # re-extract block's timestamp and text from original cues parsing? For simplicity rebuild from parsed cues
            # Need original ts strings — fallback to formatted from ms
            h1, rem = divmod(start_ms, 3600000)
            m1, rem = divmod(rem, 60000)
            s1, ms1 = divmod(rem, 1000)
            h2, rem = divmod(end_ms, 3600000)
            m2, rem = divmod(rem, 60000)
            s2, ms2 = divmod(rem, 1000)
            ts = f"{h1:02d}:{m1:02d}:{s1:02d},{ms1:03d} --> {h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}"
            text_lines = cues[i-1][3]
            out_lines.append(str(i))
            out_lines.append(ts)
            out_lines.extend(text_lines)
            out_lines.append("")  # blank line
        fixed_raw = "\n".join(out_lines).encode("utf-8")

    return errors, warnings, cues, fixed_raw if fixed_raw else raw

def main():
    args = parse_args()
    p = Path(args.input)
    if not p.exists():
        print(f"[error] not found: {p}", file=sys.stderr)
        sys.exit(2)
    if p.stat().st_size == 0:
        print(f"[error] empty file: {p}", file=sys.stderr)
        sys.exit(2)

    errors, warnings, cues, fixed = verify(p, fix=args.fix, max_line_len=args.max_line_len, max_lines_per_cue=args.max_lines_per_cue)

    print("=" * 60)
    print(f"VERIFY: {p}  cues={len(cues)}")
    print("=" * 60)

    if not errors and not warnings:
        print("[OK] SRT OK -- ready for DaVinci Resolve FREE import")
        print("   Import: DaVinci > File > Import > Subtitle  or drag SRT onto Media Pool -> Insert Selected Subtitles Using Timecode")
        sys.exit(0)

    if errors:
        print(f"[error] {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print(f"[warn] {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if args.fix and fixed is not None:
        # overwrite original (backup)
        backup = p.with_suffix(p.suffix + ".bak")
        if not backup.exists():
            p.rename(backup)
            print(f"[fix] backup -> {backup}")
            Path(p).write_bytes(fixed)
        else:
            Path(p).write_bytes(fixed)
        print(f"[fix] fixed file written -> {p} ({len(fixed)} bytes, UTF-8 LF)")
        # re-verify
        errors2, warnings2, cues2, _ = verify(p, fix=False, max_line_len=args.max_line_len, max_lines_per_cue=args.max_lines_per_cue)
        if not errors2:
            print("[OK] Fixed SRT now OK")
            sys.exit(0)
        else:
            print(f"[fix] still {len(errors2)} error(s) after fix")
            sys.exit(1)

    if errors:
        print("[FAIL] SRT has errors -- DaVinci will reject or show missing cues. Fix with --fix or edit manually.")
        sys.exit(1)
    if warnings and args.strict:
        print("[FAIL] --strict: warnings treated as errors")
        sys.exit(2)
    print("[WARN] SRT has warnings but should import. Review warnings above (Resolve will wrap long lines).")
    sys.exit(0)

if __name__ == "__main__":
    main()
