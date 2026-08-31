#!/usr/bin/env python3
r"""
srt_to_textplus.py — DaVinci Resolve FREE Text+ injector (Fusion Console / Utility)
Implements injection path B for RTX 3050 / 24GB system with 2-env design.

Place:
  %appdata%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\srt_to_textplus.py
  + config.json next to it  (copy from config.example.json)
  Template: Fusion Page -> Effects -> Titles -> Text+ -> drag to Media Pool -> rename to TEMPLATE_Subtitle

Run:
  Fusion Page -> Workspace -> Console -> Py3 -> exec(open(r"<path>/srt_to_textplus.py", encoding="utf-8").read())
  OR Workspace -> Scripts -> Utility -> srt_to_textplus  (if placed in Utility)
  (Do NOT run from external PowerShell/PyCharm — bmd.scriptapp only works inside Resolve)

Tuned for 6GB: beam=1, int8_float16 already done in ENV-A. This script never loads ML models.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# SRT parsing (mirrors transcribe/verify_srt but minimal)
# ---------------------------------------------------------------------------

SRT_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})")

def srt_time_to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def parse_srt(srt_path: Path):
    text = srt_path.read_text(encoding="utf-8-sig")  # strip BOM if present
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", text.strip())
    cues = []
    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip() != ""]
        if len(lines) < 3:
            # allow 2 lines if text empty? skip
            if len(lines) < 2:
                continue
            # number + timestamp + at least one text line
            if len(lines) == 2:
                continue
        # first line is number, second is timestamp
        try:
            int(lines[0])
        except ValueError:
            # malformed block, skip
            continue
        m = SRT_TS_RE.match(lines[1])
        if not m:
            print(f"[warn] skip malformed timestamp block: {lines[1][:80]}")
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = m.groups()
        start = srt_time_to_seconds(h1, m1, s1, ms1)
        end = srt_time_to_seconds(h2, m2, s2, ms2)
        if end <= start:
            print(f"[warn] skip cue {lines[0]} end<=start {start}->{end}")
            continue
        # remaining lines are text (may contain \n already joined)
        txt = "\n".join(lines[2:]).strip()
        if not txt:
            continue
        cues.append((start, end, txt))
    cues.sort(key=lambda x: x[0])
    return cues

def load_config(script_path: Path):
    # config.json next to script, or next to srt_to_textplus.py in repo for testing outside Resolve
    candidates = [
        script_path.with_name("config.json"),
        Path(__file__).with_name("config.json"),
        Path.cwd() / "resolve_free" / "config.json",
    ]
    # also allow config.example.json as fallback for testing
    for p in candidates:
        if p.exists():
            try:
                cfg = json.loads(p.read_text(encoding="utf-8"))
                print(f"[config] loaded {p}")
                return cfg, p
            except Exception as e:
                print(f"[warn] failed to parse {p}: {e}")
    # interactive fallback inside Resolve (no UIManager)
    print("[config] config.json not found next to script")
    try:
        # In Console, input() works and prints to console
        raw = input("Enter absolute SRT path (e.g. C:/Users/.../exports/generated-ENGLISH.srt): ").strip().strip('"')
        if raw:
            cfg = {"srt_path": raw, "targetTrack": 2, "templatePattern": "TEMPLATE", "fps": None, "clipColor": "Orange", "useTrackLock": True}
            return cfg, None
    except Exception:
        pass
    return None, None

# ---------------------------------------------------------------------------
# Resolve helpers
# ---------------------------------------------------------------------------

def find_template_clip(media_pool, pattern: str):
    root = media_pool.GetRootFolder()
    found = []

    def recurse(folder):
        try:
            clips = folder.GetClipList()
            if clips:
                for c in clips:
                    try:
                        name = c.GetClipProperty("Clip Name")
                        if not name:
                            name = c.GetName() if hasattr(c, "GetName") else ""
                    except Exception:
                        try:
                            name = c.GetName()
                        except Exception:
                            name = ""
                    if pattern.lower() in (name or "").lower():
                        found.append(c)
        except Exception:
            pass
        try:
            subs = folder.GetSubFolderList()
            if subs:
                for sub in subs:
                    recurse(sub)
        except Exception:
            pass

    recurse(root)
    return found[0] if found else None

def get_fps(project, timeline):
    # must use float, not int(29.97)
    for src, obj in [("timeline", timeline), ("project", project)]:
        try:
            v = obj.GetSetting("timelineFrameRate")
            if v not in (None, ""):
                f = float(v)
                print(f"[fps] {src}.GetSetting('timelineFrameRate')={v} -> {f}")
                return f
        except Exception as e:
            print(f"[fps] {src} GetSetting failed: {e}")
    print("[fps] fallback 24.0")
    return 24.0

def get_start_frame(timeline):
    try:
        sf = timeline.GetStartFrame()
        print(f"[timeline] GetStartFrame()={sf}")
        try:
            tc = timeline.GetStartTimecode()
            print(f"[timeline] GetStartTimecode()={tc}")
        except Exception:
            pass
        return int(sf)
    except Exception as e:
        print(f"[timeline] GetStartFrame failed: {e} -> assume 0")
        return 0

def get_track_lock_state(timeline, track_type="video"):
    # not all versions expose GetTrackLock, so probe
    state = {}
    try:
        n = timeline.GetTrackCount(track_type)
        for i in range(1, n + 1):
            try:
                # GetTrackLock may not exist on some builds
                locked = timeline.GetTrackLock(track_type, i)
                state[i] = bool(locked)
            except Exception:
                state[i] = False
    except Exception as e:
        print(f"[lock] GetTrackCount failed: {e}")
    return state

def set_track_locks(timeline, target_track, lock_others=True):
    original = get_track_lock_state(timeline, "video")
    if not original:
        return original
    try:
        for idx in original:
            should_lock = (idx != target_track) if lock_others else False
            # only change if needed
            if original[idx] != should_lock:
                try:
                    timeline.SetTrackLock("video", idx, should_lock)
                except Exception as e:
                    print(f"[lock] SetTrackLock video {idx} -> {should_lock} failed: {e}")
        print(f"[lock] locked all video tracks except {target_track} (original {original})")
    except Exception as e:
        print(f"[lock] failed: {e}")
    return original

def restore_track_locks(timeline, original):
    if not original:
        return
    for idx, was_locked in original.items():
        try:
            timeline.SetTrackLock("video", idx, was_locked)
        except Exception:
            pass
    print(f"[lock] restored {original}")

# ---------------------------------------------------------------------------
# Main injection
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("SRT -> Text+ injector (FREE, 6GB tuned, no external API)")
    print("=" * 60)

    # locate script path for config
    try:
        script_path = Path(__file__).resolve()
    except NameError:
        # when exec(open(...).read()) __file__ may not exist, use cwd
        script_path = Path.cwd() / "resolve_free" / "srt_to_textplus.py"

    cfg, cfg_path = load_config(script_path)
    if not cfg:
        print("[error] config.json not found. Create resolve_free/config.json from config.example.json")
        print("  Example: {\"srt_path\": \"C:/.../exports/generated-ENGLISH.srt\", \"targetTrack\": 2}")
        return

    srt_path = Path(cfg.get("srt_path", "")).expanduser()
    if not srt_path.is_absolute():
        # if relative, resolve against config dir
        if cfg_path:
            srt_path = (cfg_path.parent / srt_path).resolve()
        else:
            srt_path = (Path.cwd() / srt_path).resolve()

    target_track = int(cfg.get("targetTrack", 2))
    template_pat = cfg.get("templatePattern", "TEMPLATE")
    clip_color = cfg.get("clipColor", "Orange")
    use_lock = bool(cfg.get("useTrackLock", True))
    fps_override = cfg.get("fps")
    start_override = cfg.get("timelineStartFrame")

    if not srt_path.exists():
        print(f"[error] srt_path not found: {srt_path}")
        print(f"  Edit {cfg_path or 'config.json'}  srt_path")
        try:
            raw = input(f"Enter correct SRT path or press Enter to abort: ").strip().strip('"')
            if raw:
                srt_path = Path(raw)
            else:
                return
        except Exception:
            return
        if not srt_path.exists():
            print(f"[error] still not found: {srt_path}")
            return

    cues = parse_srt(srt_path)
    if not cues:
        print(f"[error] no cues parsed from {srt_path}")
        return
    print(f"[srt] {len(cues)} cues from {srt_path.name}  first={cues[0][0]:.2f}s text='{cues[0][2][:40]}'")

    # Resolve objects — must run inside Resolve
    try:
        import DaVinciResolveScript as bmd
    except ImportError as e:
        print("[error] DaVinciResolveScript not importable — run INSIDE Resolve Console/Scripts")
        print(f"  {e}")
        print("  Fusion Page -> Workspace -> Console -> Py3 -> exec(open(r\"%s\", encoding=\"utf-8\").read())" % script_path)
        return

    resolve = bmd.scriptapp("Resolve")
    if not resolve:
        print("[error] bmd.scriptapp('Resolve') returned None")
        return
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        print("[error] No project open")
        return
    timeline = project.GetCurrentTimeline()
    if not timeline:
        print("[error] No timeline open — open a timeline first")
        return
    media_pool = project.GetMediaPool()
    if not media_pool:
        print("[error] No media pool")
        return

    fps = float(fps_override) if fps_override not in (None, "") else get_fps(project, timeline)
    start_frame = int(start_override) if start_override not in (None, "") else get_start_frame(timeline)

    # find template
    template_item = find_template_clip(media_pool, template_pat)
    if not template_item:
        print(f"[error] TEMPLATE not found with pattern '{template_pat}' in Media Pool")
        print("  Fix: Fusion Page -> Effects Library -> Titles -> Text+ -> drag to Media Pool -> rename to TEMPLATE_Subtitle")
        print("  Then retry. Current Media Pool clips:")
        try:
            root = media_pool.GetRootFolder()
            clips = root.GetClipList() or []
            for c in clips[:10]:
                try:
                    print("   -", c.GetClipProperty("Clip Name"))
                except Exception:
                    pass
        except Exception:
            pass
        return
    try:
        tname = template_item.GetClipProperty("Clip Name")
    except Exception:
        tname = str(template_item)
    print(f"[template] found '{tname}' pattern='{template_pat}'")

    # lock tracks
    original_locks = {}
    if use_lock:
        original_locks = set_track_locks(timeline, target_track, True)

    # snapshot before count
    try:
        before = timeline.GetItemListInTrack("video", target_track)
        before_count = len(before) if before else 0
    except Exception:
        before_count = 0

    # inject
    injected = 0
    failed = 0
    for idx, (start, end, text) in enumerate(cues, start=1):
        record_frame = start_frame + int(round(start * fps))
        duration_frames = max(1, int(round((end - start) * fps)))
        # ensure tiny gaps don't collapse
        if idx < len(cues):
            next_start = cues[idx][0]  # cues idx is next (0-based)
            next_record = start_frame + int(round(next_start * fps))
            if record_frame + duration_frames > next_record:
                # trim to avoid overlap by 1 frame
                duration_frames = max(1, next_record - record_frame - 1)

        clip_info = {
            "mediaPoolItem": template_item,
            "startFrame": 0,
            "endFrame": duration_frames,
            "trackIndex": target_track,
            "recordFrame": record_frame,
        }
        # some Resolve versions require mediaType
        # keep minimal; AppendToTimeline tolerates extra keys
        try:
            result = media_pool.AppendToTimeline([clip_info])
            if not result:
                # try with mediaType
                clip_info["mediaType"] = 1  # 1=video
                result = media_pool.AppendToTimeline([clip_info])
            if result:
                injected += 1
                if injected % 50 == 0:
                    print(f"[inject] {injected}/{len(cues)} at {record_frame} dur {duration_frames} '{text[:30]}'")
            else:
                print(f"[warn] AppendToTimeline failed cue {idx} at {record_frame}")
                failed += 1
        except Exception as e:
            print(f"[error] AppendToTimeline cue {idx} failed: {e}")
            failed += 1
            # try fallback without lock
            if "track" in str(e).lower() and use_lock:
                print("  retry without track lock...")
                restore_track_locks(timeline, original_locks)
                use_lock = False
                try:
                    result = media_pool.AppendToTimeline([clip_info])
                    if result:
                        injected += 1
                        failed -= 1
                except Exception as e2:
                    print(f"  retry failed: {e2}")

    print(f"[inject] done injected={injected} failed={failed} total={len(cues)}")

    # restore locks before text pass (so second pass can read)
    if use_lock and original_locks:
        restore_track_locks(timeline, original_locks)

    # second pass: set text
    try:
        items = timeline.GetItemListInTrack("video", target_track)
        if not items:
            print(f"[warn] GetItemListInTrack video {target_track} returned empty")
            return
        # items are TimelineItem objects sorted by timeline position
        # isolate newly injected: last `injected` items if before_count known, else match by start time
        if before_count and len(items) >= injected:
            new_items = items[-injected:]
            # ensure sorted by start
            try:
                new_items = sorted(new_items, key=lambda it: it.GetStart() if hasattr(it, "GetStart") else 0)
            except Exception:
                pass
        else:
            # fallback: sort all by start and take cues-length window; assume injected items are contiguous
            try:
                items_sorted = sorted(items, key=lambda it: it.GetStart())
                # find window closest to cues start times if possible
                new_items = items_sorted[-len(cues):]
            except Exception:
                new_items = items

        if len(new_items) != len(cues):
            print(f"[warn] item count {len(new_items)} != cues {len(cues)} — will map by order, verify timeline")

        updated = 0
        for item, (start, end, text) in zip(new_items, cues):
            try:
                comp = None
                # Try multiple accessors for Fusion comp
                for accessor in ["GetFusionCompByIndex", "GetFusionCompByName"]:
                    try:
                        if accessor == "GetFusionCompByIndex":
                            comp = item.GetFusionCompByIndex(1)
                        else:
                            comp = item.GetFusionCompByName("Fusion Composition")
                        if comp:
                            break
                    except Exception:
                        continue
                if not comp:
                    print(f"[warn] no FusionComp for item at {start:.2f} — is Text+ template Fusion-based?")
                    continue
                # Find Text+ tool: common names "Template", "TextPlus", "Text+"
                tool = None
                for name in ["Template", "TextPlus", "Text+", "Title"]:
                    try:
                        tool = comp.FindTool(name)
                        if tool:
                            break
                    except Exception:
                        continue
                if not tool:
                    # fallback: first TextPlus tool in comp
                    try:
                        tool_list = comp.GetToolList(False, "TextPlus")
                        if tool_list and len(tool_list) > 0:
                            tool = list(tool_list.values())[0] if isinstance(tool_list, dict) else tool_list[0]
                    except Exception:
                        pass
                if not tool:
                    print(f"[warn] no TextPlus tool in FusionComp at {start:.2f}")
                    continue
                # StyledText is rich text; for Text+ also "StyledText"
                try:
                    tool.SetInput("StyledText", text)
                except Exception:
                    # fallback for TextPlus vs Text+
                    try:
                        tool.SetInput("Text", text)
                    except Exception as e2:
                        print(f"[warn] SetInput failed for '{text[:20]}': {e2}")
                        continue
                # optional color for visibility
                try:
                    item.SetClipColor(clip_color)
                except Exception:
                    pass
                updated += 1
            except Exception as e:
                print(f"[warn] failed to set text for cue at {start:.2f}: {e}")
        print(f"[text] updated {updated}/{len(cues)} Text+ items with StyledText, color {clip_color}")
    except Exception as e:
        print(f"[error] second pass (SetInput) failed: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)
    print(f"[done] {injected} Text+ clips on V{target_track} from {srt_path.name}")
    print(f"  Verify: scrub 00:01 / 05:00 / end, check Inspector > Title > Text")
    print(f"  Deliver: Burn into video or keep as Text+ for styling")
    print("=" * 60)

if __name__ == "__main__":
    main()
else:
    # when exec() in Console, still run — skip when testing (UGA_TEST=1)
    import os
    if os.environ.get("UGA_TEST") != "1":
        try:
            main()
        except SystemExit:
            pass
        except Exception as e:
            print(f"[fatal] {e}")
            import traceback
            traceback.print_exc()
