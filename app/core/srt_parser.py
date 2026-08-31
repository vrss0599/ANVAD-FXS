import re
from pathlib import Path
from typing import List, Dict, Any

def parse_srt_file(path: str) -> List[Dict[str, Any]]:
    """Parse SRT file and return list of cue dicts.
    Each dict: {"index": int, "start": str, "end": str, "text": str}
    """
    cues = []
    try:
        p = Path(path)
        if not p.exists():
            return []
            
        with open(p, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        blocks = re.split(r'\n\n+', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                try:
                    index = int(lines[0].strip())
                    times = lines[1].strip()
                    text = '\n'.join(lines[2:]).strip()
                    
                    if '-->' in times:
                        start, end = times.split('-->', 1)
                        cues.append({
                            "index": index,
                            "start": start.strip(),
                            "end": end.strip(),
                            "text": text
                        })
                except ValueError:
                    continue
    except Exception:
        pass
        
    return cues

def get_srt_summary(path: str) -> Dict[str, Any]:
    """Returns {"cue_count": int, "duration_fmt": str, "first_cue": str, "last_cue": str, "file_size_kb": float}"""
    summary = {
        "cue_count": 0,
        "duration_fmt": "00:00:00",
        "first_cue": "",
        "last_cue": "",
        "file_size_kb": 0.0
    }
    
    try:
        p = Path(path)
        if p.exists():
            summary["file_size_kb"] = round(p.stat().st_size / 1024, 2)
            
        cues = parse_srt_file(path)
        if cues:
            summary["cue_count"] = len(cues)
            summary["first_cue"] = cues[0]["start"]
            summary["last_cue"] = cues[-1]["end"]
            summary["duration_fmt"] = summary["last_cue"].split(',')[0]
    except Exception:
        pass
        
    return summary
