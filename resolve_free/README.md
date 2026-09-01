# ENV-B — DaVinci Resolve FREE Injection

Two injection paths. Both work on **Resolve FREE** (no Studio, no external API). Script runs **inside** Resolve: `Fusion Page -> Workspace -> Console -> Py3` or `Workspace -> Scripts -> Utility`.

## Prerequisites (once)

1. Resolve installed from `blackmagicdesign.com` (not Microsoft Store). Check: `Workspace -> Console -> Py3 -> import sys; print(sys.version)` must show `3.10.x` or `3.11.x` (same Python that will run scripts).
2. Template: `Fusion Page -> Effects Library -> Titles -> Text+` drag to `Media Pool -> Master`. Right-click -> `Change Clip Name` -> `TEMPLATE_Subtitle`. This is the `templatePattern` (`TEMPLATE`).
3. Place scripts: copy `resolve_free/srt_to_textplus.py` + `resolve_free/check_timeline.py` + `resolve_free/config.json` to:
   ```
   %appdata%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\
   ```
   (Create folders if missing. `C:\ProgramData\...` also works. Restart Resolve, then check `Workspace -> Scripts -> Utility -> srt_to_textplus`.)

## Path A — Subtitle Track (0 code, recommended first)

1. ENV-A: `python transcribe/transcribe.py --input "exports/audio.wav" --model large-v3` → `exports/audio-ENGLISH.srt`
2. `python transcribe/verify_srt.py --input "exports/audio-ENGLISH.srt"` → `[OK]`
3. Resolve: `File -> Import -> Subtitle` select `audio-ENGLISH.srt` **or** drag SRT from `Media Pool` onto timeline `Subtitle Track` (`Subtitles` lane above video).
4. Dialog: `Insert Selected Subtitles to Timeline Using Timecode` -> `OK`.
   * If timeline starts at `01:00:00:00` (default Resolve) and SRT at `00:00:00,000`, Resolve auto-adds `01:00:00:00` offset — verify first cue at `01:00:01`. If mismatch, right-click subtitle clip -> `Change Clip Timecode` or re-export SRT with offset (add `3600s`).
5. `Inspector -> Caption` to style (font, size, background, line width 42). `Deliver -> Subtitle Settings -> Export as Separate file (SRT)` or `Burn into video`.

Pros: Native subtitle lane, editable, exportable. Cons: Limited styling vs Text+.

## Path B — Text+ Overlay (coded, `srt_to_textplus.py`)

For styled karaoke/burned text not dependent on subtitle track.

### Config

Copy `config.example.json` → `config.json` next to `srt_to_textplus.py` (same `Utility` folder):

```json
{
  "srt_path": "C:/Users/YourUsername/UGA-SUB-DR/exports/generated-ENGLISH.srt",
  "targetTrack": 2,
  "templatePattern": "TEMPLATE",
  "fps": null,
  "clipColor": "Orange"
}
```

* `srt_path`: **absolute, forward slashes** (Windows `C:/...` not `C:\...`). Relative paths resolve against `config.json` dir.
* `targetTrack`: `2` = `V2` (keeps `V1` for video). Use `1` if no video on `V2`.
* `templatePattern`: substring to find template clip in Media Pool (`TEMPLATE` matches `TEMPLATE_Subtitle`).
* `fps`: `null` = auto-detect `timeline.GetSetting("timelineFrameRate")` as `float` (never `int(29.97)` → `29`). Set manually e.g. `23.976` if auto fails.
* `clipColor`: `Teal/Orange` for timeline visibility.

### Run

1. In Resolve: open timeline, select `Edit` or `Fusion` page (either works, Fusion required for Text+ Fusion comps).
2. `Workspace -> Console -> Py3` then:
   ```python
    exec(open(r"%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\srt_to_textplus.py", encoding="utf-8").read())
   ```
   Or `Workspace -> Scripts -> Utility -> srt_to_textplus`.
3. Console output:
   ```
   [srt] 123 cues ...
   [template] found 'TEMPLATE_Subtitle'
   [lock] locked all video tracks except 2
   [inject] done injected=123 failed=0
   [text] updated 123/123 Text+ items
   [done] 123 Text+ clips on V2
   ```

### Troubleshooting

* `DaVinciResolveScript not importable` → you ran from external PowerShell/PyCharm. Run inside Resolve Console only.
* `TEMPLATE not found` → run `check_timeline.py` (`exec(open(..., "check_timeline.py").read())`) to list Media Pool clips. Ensure template is in `Master` not in a subfolder that is closed, or adjust `templatePattern`.
* `AppendToTimeline failed` → check `targetTrack` exists (`timeline.GetTrackCount("video")`). Create `V2` by dragging video to `V2` or `Timeline -> Add Video Track`.
* Overlapping cues or `recordFrame` collision → script trims `duration_frames = next_record - record_frame -1`. If still fails, increase gap in SRT or set `useTrackLock:false` in `config.json`.
* Text shows as empty/default → Fusion comp tool name mismatch. `check_timeline.py` shows Fusion app; open one Text+ clip -> `Fusion Page` -> check tool name in `Tools` (should be `Template` or `TextPlus`). Script tries both `StyledText` and `Text` inputs; if still fails, open `Fusion` and manually set `StyledText` to test.
* Frame rate drift (`29.97 → 29`) → script uses `float(fps)` and `round(start*fps)`. Verify with `check_timeline.py` `fps=29.97` not `29`. If wrong, set `fps: 29.97` explicitly in `config.json`.
* `SetTrackLock failed` → older Resolve FREE may not expose `SetTrackLock`; script falls back to `useTrackLock:false` automatically.

## Verification

After injection, scrub to `00:01 / 05:00 / end` and check `Inspector > Title > Text` matches SRT `verify_srt.py` first/mid/last cue. `verify_srt.py:37` catches `00:00:00.000` dot, BPM boxes before import.

## Deliver

* Subtitle Track: `Deliver -> Video -> Export Video [x] Export Audio [x] -> Subtitle Settings -> Export as Separate file / Burn into video`
* Text+: Already burned as `Text+` video clips — `Deliver -> Video` exports with text baked in (no separate SRT).
