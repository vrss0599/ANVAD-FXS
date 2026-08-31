import os
import wave
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

def get_audio_info(path: str) -> Dict[str, Any]:
    p = Path(path)
    result = {
        "name": p.name,
        "size_bytes": 0,
        "size_mb": "0.0",
        "duration_s": 0.0,
        "duration_fmt": "00:00:00",
        "sample_rate": 0,
        "channels": 0,
        "format": "Unknown",
        "is_video": False,
        "needs_extraction": False,
        "warnings": [],
    }
    
    try:
        if not p.exists():
            return {"name": p.name, "size_bytes": 0, "size_mb": "0.0"}
            
        size = p.stat().st_size
        result["size_bytes"] = size
        result["size_mb"] = f"{size / (1024 * 1024):.1f}"
        
        ext = p.suffix.lower()
        video_exts = {'.mp4', '.mov', '.mkv', '.avi'}
        audio_exts = {'.mp3', '.m4a', '.flac', '.ogg', '.aac'}
        
        if ext in video_exts:
            result["is_video"] = True
            result["needs_extraction"] = True
        elif ext in audio_exts:
            result["needs_extraction"] = True
            
        if ext == '.wav':
            with wave.open(str(p), 'rb') as w:
                channels = w.getnchannels()
                sample_rate = w.getframerate()
                sample_width = w.getsampwidth()
                nframes = w.getnframes()
                
                result["channels"] = channels
                result["sample_rate"] = sample_rate
                result["format"] = f"WAV PCM {sample_width * 8}-bit"
                if sample_rate > 0:
                    result["duration_s"] = nframes / sample_rate
                    
                if sample_rate != 16000:
                    result["warnings"].append("Not 16kHz — transcription will be slower")
                if channels != 1:
                    result["warnings"].append("Not mono channel — might affect transcription")
                    
        elif result["needs_extraction"] or result["is_video"]:
            try:
                cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(p)]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    fmt = data.get("format", {})
                    if "duration" in fmt:
                        result["duration_s"] = float(fmt["duration"])
                    
                    streams = data.get("streams", [])
                    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
                    if audio_stream:
                        if "sample_rate" in audio_stream:
                            result["sample_rate"] = int(audio_stream["sample_rate"])
                        if "channels" in audio_stream:
                            result["channels"] = int(audio_stream["channels"])
                            
                    result["format"] = fmt.get("format_name", ext[1:].upper())
            except Exception:
                pass
                
        # Format duration
        if result["duration_s"] > 0:
            h = int(result["duration_s"] // 3600)
            m = int((result["duration_s"] % 3600) // 60)
            s = int(result["duration_s"] % 60)
            result["duration_fmt"] = f"{h:02d}:{m:02d}:{s:02d}"
            
    except Exception:
        # Minimal dict on error
        return {
            "name": p.name,
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "size_mb": f"{(p.stat().st_size / (1024*1024)):.1f}" if p.exists() else "0.0"
        }
        
    return result
