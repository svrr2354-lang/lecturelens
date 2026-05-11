import os
import re
import json
import requests
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
    """Agent 1 - Librarian: Fetch transcript using YouTube timedtext API"""

    video_id = extract_video_id(url)

    if not video_id:
        return {"success": False, "error": "Could not extract video ID from URL."}

    if 'shorts' in url.lower():
        return {"success": False, "error": "YouTube Shorts are not supported. Please use a regular lecture video."}

    try:
        # First get the video page to find caption tracks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        page_url = f"https://www.youtube.com/watch?v={video_id}"
        page_response = requests.get(page_url, headers=headers, timeout=30)
        
        if page_response.status_code != 200:
            return {"success": False, "error": "Could not access video page."}

        page_text = page_response.text

        # Check if video exists
        if "Video unavailable" in page_text or "Private video" in page_text:
            return {"success": False, "error": "Video is private or unavailable."}

        if '"isLiveBroadcast":true' in page_text or '"isLive":true' in page_text:
            return {"success": False, "error": "Live streams are not supported."}

        # Extract caption tracks from page
        caption_url = None
        auto_generated = False

        # Look for captionTracks in page source
        import re as re_module
        caption_match = re_module.search(r'"captionTracks":(\[.*?\])', page_text)
        
        if caption_match:
            try:
                tracks = json.loads(caption_match.group(1))
                # Prefer English manual captions first
                for track in tracks:
                    lang = track.get("languageCode", "")
                    kind = track.get("kind", "")
                    base_url = track.get("baseUrl", "")
                    if lang == "en" and kind != "asr" and base_url:
                        caption_url = base_url
                        auto_generated = False
                        break
                
                # Fall back to auto-generated English
                if not caption_url:
                    for track in tracks:
                        lang = track.get("languageCode", "")
                        base_url = track.get("baseUrl", "")
                        if lang == "en" and base_url:
                            caption_url = base_url
                            auto_generated = True
                            break
                
                # Fall back to any language
                if not caption_url and tracks:
                    caption_url = tracks[0].get("baseUrl", "")
                    auto_generated = True

            except:
                pass

        if not caption_url:
            return {"success": False, "error": "No captions available for this video."}

        # Fetch the captions
        caption_url += "&fmt=json3"
        cap_response = requests.get(caption_url, headers=headers, timeout=30)
        
        if cap_response.status_code != 200:
            return {"success": False, "error": "Could not fetch captions."}

        # Parse json3 format
        cap_data = cap_response.json()
        chunks = []

        for event in cap_data.get("events", []):
            if "segs" not in event:
                continue
            text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
            if text and text != "\n":
                start = event.get("tStartMs", 0) / 1000
                duration = event.get("dDurationMs", 0) / 1000
                chunks.append({"text": text, "start": start, "duration": duration})

        if not chunks:
            return {"success": False, "error": "Could not parse transcript."}

        full_text = " ".join([c["text"] for c in chunks])

        return {
            "success": True,
            "video_id": video_id,
            "chunks": chunks,
            "full_text": full_text,
            "total_chunks": len(chunks),
            "auto_generated_captions": auto_generated
        }

    except requests.Timeout:
        return {"success": False, "error": "Request timed out. Please try again."}
    except Exception as e:
        return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}