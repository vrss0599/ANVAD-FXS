#!/usr/bin/env python3
r"""
check_timeline.py — Run inside DaVinci Resolve FREE: Fusion Page -> Workspace -> Console -> Py3

Prints timeline FPS, start timecode, track counts, and template detection.
Use to verify before running srt_to_textplus.py.

Inside Console, run:
  exec(open(r"C:/Users/YourUsername/UGA-SUB-DR/resolve_free/check_timeline.py", encoding="utf-8").read())

Or place in Utility and run via Workspace -> Scripts -> Utility -> check_timeline
"""

def main():
    try:
        import DaVinciResolveScript as bmd
    except ImportError as e:
        print("[error] DaVinciResolveScript not found — run INSIDE Resolve Console/Scripts, not external terminal")
        print(f"  {e}")
        return

    resolve = bmd.scriptapp("Resolve")
    if not resolve:
        print("[error] bmd.scriptapp('Resolve') returned None — is Resolve running?")
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

    print("=" * 60)
    print("TIMELINE CHECK")
    print("=" * 60)

    # FPS — must use float, not int(29.97) -> 29 bug
    fps = None
    try:
        fps_str = timeline.GetSetting("timelineFrameRate")
        if fps_str:
            fps = float(fps_str)
            print(f"[fps] timeline.GetSetting('timelineFrameRate') = {fps_str} -> {fps}")
    except Exception as e:
        print(f"[fps] timeline.GetSetting failed: {e}")
    if fps is None:
        try:
            fps_str = project.GetSetting("timelineFrameRate")
            if fps_str:
                fps = float(fps_str)
                print(f"[fps] project.GetSetting('timelineFrameRate') = {fps_str} -> {fps}")
        except Exception as e:
            print(f"[fps] project fallback failed: {e}")
    if fps is None:
        fps = 24.0
        print(f"[fps] fallback to {fps}")

    try:
        start_frame = timeline.GetStartFrame()
        print(f"[start] timeline.GetStartFrame() = {start_frame}")
        # also print timecode
        try:
            tc = timeline.GetStartTimecode()
            print(f"[start] timeline.GetStartTimecode() = {tc}")
        except Exception:
            pass
        # 01:00:00:00 vs 00:00:00:00 offset
        offset_sec = start_frame / fps if fps else 0
        print(f"[start] offset = {offset_sec:.3f}s ({start_frame} frames / {fps} fps)")
        if start_frame == 86400 and abs(fps - 24) < 0.1:
            print("  -> 01:00:00:00 at 24fps detected (broadcast start)")
        # common offsets
        if abs(fps - 23.976) < 0.01 and start_frame == 86382:
            print("  -> 01:00:00:00 at 23.976")
    except Exception as e:
        print(f"[start] failed: {e}")

    # track counts
    for ttype in ["video", "audio", "subtitle"]:
        try:
            n = timeline.GetTrackCount(ttype)
            print(f"[tracks] {ttype} = {n}")
        except Exception as e:
            print(f"[tracks] {ttype} failed: {e}")

    # media pool template search
    try:
        mp = project.GetMediaPool()
        root = mp.GetRootFolder()
        def find_recursive(folder, pattern, depth=0):
            hits = []
            try:
                clips = folder.GetClipList() or []
                for c in clips:
                    try:
                        name = c.GetClipProperty("Clip Name") or c.GetName() or ""
                    except Exception:
                        name = ""
                    if pattern.lower() in name.lower():
                        hits.append((name, folder.GetName()))
            except Exception:
                pass
            try:
                subs = folder.GetSubFolderList() or []
                for sub in subs:
                    hits.extend(find_recursive(sub, pattern, depth+1))
            except Exception:
                pass
            return hits

        for pat in ["TEMPLATE", "Text+", "Subtitle"]:
            hits = find_recursive(root, pat)
            if hits:
                print(f"[template] pattern '{pat}' found {len(hits)}: {hits[:3]}")
            else:
                print(f"[template] pattern '{pat}' not found in Media Pool")
    except Exception as e:
        print(f"[template] search failed: {e}")

    # fusion check
    try:
        # In Console, fusion object may be global 'fusion' or via bmd
        import DaVinciResolveScript as bmd2
        fusion = bmd2.scriptapp("Fusion")
        if fusion:
            print(f"[fusion] Fusion app found: {fusion}")
        else:
            print("[fusion] Fusion app not found (expected inside Fusion page)")
    except Exception as e:
        print(f"[fusion] check failed: {e}")

    print("=" * 60)
    print("If FPS/start_frame look wrong, fix config.json fps/timelineStartFrame manually")
    print("=" * 60)

if __name__ == "__main__":
    main()
else:
    import os
    if os.environ.get("UGA_TEST") != "1":
        try:
            main()
        except Exception as e:
            print(f"[error] {e}")
            import traceback
            traceback.print_exc()
