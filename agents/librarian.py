import os
import re
import json
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
    """Agent 1 - Librarian: Fetch transcript using requests + proxy"""

    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Could not extract video ID from URL."}
    if 'shorts' in url.lower():
        return {"success": False, "error": "YouTube Shorts are not supported. Please use a regular lecture video."}

    try:
        proxy = os.getenv("PROXY_URL", "")
        proxies = {"http": proxy, "https": proxy} if proxy else None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        # Fetch video page
        page_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(
            page_url,
            headers=headers,
            proxies=proxies,
            verify=False,
            timeout=30
        )

        print(f"Page status: {response.status_code}")
        print(f"Proxy used: {proxy[:50] if proxy else 'none'}")

        if response.status_code != 200:
            return {"success": False, "error": f"Could not access video page. Status: {response.status_code}"}

        page_text = response.text

        if "Video unavailable" in page_text or '"playabilityStatus":{"status":"ERROR"' in page_text:
            return {"success": False, "error": "Video is private or unavailable."}

        if '"isLive":true' in page_text or '"isLiveBroadcast":true' in page_text:
            return {"success": False, "error": "Live streams are not supported."}

        # Extract caption tracks
        caption_match = re.search(r'"captionTracks":(\[.*?\])', page_text)
        if not caption_match:
            print("No captionTracks found in page")
            return {"success": False, "error": "No captions available for this video."}

        tracks = json.loads(caption_match.group(1))
        print(f"Found {len(tracks)} caption tracks")

        caption_url = None
        auto_generated = False

        # Prefer manual English captions
        for track in tracks:
            if track.get("languageCode") == "en" and track.get("kind") != "asr":
                caption_url = track.get("baseUrl")
                auto_generated = False
                break

        # Fall back to auto-generated English
        if not caption_url:
            for track in tracks:
                if track.get("languageCode") == "en":
                    caption_url = track.get("baseUrl")
                    auto_generated = True
                    break

        # Fall back to any language
        if not caption_url and tracks:
            caption_url = tracks[0].get("baseUrl")
            auto_generated = True

        if not caption_url:
            return {"success": False, "error": "No captions available for this video."}

        # Fetch captions
        caption_url += "&fmt=json3"
        cap_response = requests.get(
            caption_url,
            headers=headers,
            proxies=proxies,
            verify=False,
            timeout=30
        )

        print(f"Caption status: {cap_response.status_code}")

        if cap_response.status_code != 200:
            return {"success": False, "error": "Could not fetch captions."}

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
        punctuation_count = sum(1 for c in full_text if c in '.!?,;:')
        auto_generated = auto_generated or punctuation_count < 3

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
        print(f"Exception: {str(e)}")
        return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}