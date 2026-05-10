import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats"""
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
    """Agent 1 - Librarian: Fetch transcript using YouTube Data API"""
    
    video_id = extract_video_id(url)
    
    if not video_id:
        return {"success": False, "error": "Could not extract video ID from URL."}

    # Check for Shorts and Live
    if 'shorts' in url.lower():
        return {"success": False, "error": "YouTube Shorts are not supported. Please use a regular lecture video."}

    try:
        # Step 1: Get video details to check if it's valid and get caption info
        video_url = "https://www.googleapis.com/youtube/v3/videos"
        video_params = {
            "id": video_id,
            "part": "snippet,contentDetails,status",
            "key": YOUTUBE_API_KEY
        }
        video_response = requests.get(video_url, params=video_params)
        video_data = video_response.json()

        if not video_data.get("items"):
            return {"success": False, "error": "Video not found or is private."}

        video_item = video_data["items"][0]
        
        # Check if live
        if video_item["snippet"].get("liveBroadcastContent") in ["live", "upcoming"]:
            return {"success": False, "error": "Live streams are not supported. Please use a recorded lecture."}

        # Step 2: Get available captions
        captions_url = "https://www.googleapis.com/youtube/v3/captions"
        captions_params = {
            "videoId": video_id,
            "part": "snippet",
            "key": YOUTUBE_API_KEY
        }
        captions_response = requests.get(captions_url, params=captions_params)
        captions_data = captions_response.json()

        # Step 3: Fall back to youtube-transcript-api for actual transcript content
        # (YouTube Data API requires OAuth to download caption content)
        from youtube_transcript_api import YouTubeTranscriptApi
        
        try:
            transcript_list = YouTubeTranscriptApi().fetch(video_id)
            chunks = [{"text": t.text, "start": t.start, "duration": t.duration} 
                     for t in transcript_list]
        except Exception as e:
            return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}

        if not chunks:
            return {"success": False, "error": "No transcript available for this video."}

        full_text = " ".join([c["text"] for c in chunks])
        
        # Detect auto-generated captions
        auto_generated = False
        if captions_data.get("items"):
            for caption in captions_data["items"]:
                if caption["snippet"].get("trackKind") == "asr":
                    auto_generated = True
                    break
        else:
            # Fallback detection
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

    except Exception as e:
        return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}