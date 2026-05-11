import os
import re
import subprocess
import json
from dotenv import load_dotenv

load_dotenv()

def extract_video_id(url: str) -> str:
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_transcript(url: str) -> dict:
    """Agent 1 - Librarian: Fetch transcript using yt-dlp"""

    video_id = extract_video_id(url)

    if not video_id:
        return {"success": False, "error": "Could not extract video ID from URL."}

    if 'shorts' in url.lower():
        return {"success": False, "error": "YouTube Shorts are not supported. Please use a regular lecture video."}

    try:
        proxy = os.getenv("PROXY_URL", "")

        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--sub-format", "json3",
            "--output", f"/tmp/{video_id}",
            f"https://www.youtube.com/watch?v={video_id}"
        ]

        if proxy:
            cmd.insert(-1, "--proxy")
            cmd.insert(-1, proxy)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        import glob
        sub_files = glob.glob(f"/tmp/{video_id}*.json3")

        if not sub_files:
            cmd_vtt = [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--skip-download",
                "--sub-format", "vtt",
                "--output", f"/tmp/{video_id}",
                f"https://www.youtube.com/watch?v={video_id}"
            ]
            if proxy:
                cmd_vtt.insert(-1, "--proxy")
                cmd_vtt.insert(-1, proxy)

            result = subprocess.run(cmd_vtt, capture_output=True, text=True, timeout=60)
            sub_files = glob.glob(f"/tmp/{video_id}*.vtt")

            if not sub_files:
                return {"success": False, "error": "No captions available for this video."}

            chunks = parse_vtt(sub_files[0])
        else:
            chunks = parse_json3(sub_files[0])

        if not chunks:
            return {"success": False, "error": "Could not parse transcript."}

        full_text = " ".join([c["text"] for c in chunks])

        punctuation_count = sum(1 for c in full_text if c in '.!?,;:')
        auto_generated = punctuation_count < 3

        return {
            "success": True,
            "video_id": video_id,
            "chunks": chunks,
            "full_text": full_text,
            "total_chunks": len(chunks),
            "auto_generated_captions": auto_generated
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Request timed out. Please try again."}
    except Exception as e:
        return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}


def parse_json3(filepath: str) -> list:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        chunks = []
        for event in data.get("events", []):
            if "segs" not in event:
                continue
            text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
            if text and text != "\n":
                start = event.get("tStartMs", 0) / 1000
                duration = event.get("dDurationMs", 0) / 1000
                chunks.append({"text": text, "start": start, "duration": duration})
        return chunks
    except:
        return []


def parse_vtt(filepath: str) -> list:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        chunks = []
        blocks = content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue

            ts_line = None
            text_lines = []
            for line in lines:
                if '-->' in line:
                    ts_line = line
                elif ts_line and line.strip() and not line.strip().isdigit():
                    text_lines.append(line.strip())

            if ts_line and text_lines:
                start_str = ts_line.split('-->')[0].strip()
                start = parse_timestamp(start_str)
                text = ' '.join(text_lines)
                text = re.sub(r'<[^>]+>', '', text).strip()
                if text:
                    chunks.append({"text": text, "start": start, "duration": 5})

        return chunks
    except:
        return []


def parse_timestamp(ts: str) -> float:
    try:
        ts = ts.split('.')[0]
        parts = ts.split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0