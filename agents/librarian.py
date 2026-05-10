from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'embed/([a-zA-Z0-9_-]{11})',
        r'live/([a-zA-Z0-9_-]{11})',
        r'shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_transcript(url: str) -> dict:
    """Agent 1 - Librarian: Fetch and chunk transcript from YouTube URL"""
    
    video_id = extract_video_id(url)
    
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL. Please paste a valid YouTube lecture link."}
    
    # Warn about Shorts and live streams
    if 'shorts/' in url:
        return {"success": False, "error": "YouTube Shorts are not supported. Please paste a full lecture URL."}
    
    if 'youtube.com/live' in url:
        return {"success": False, "error": "Live streams are not supported. Please paste a recorded lecture URL."}

    try:
        ytt_api = YouTubeTranscriptApi()
        fetched = ytt_api.fetch(video_id)
        
        # Build chunks with timestamps
        chunks = []
        for entry in fetched:
            chunks.append({
                "text": entry.text,
                "start": round(entry.start, 1),
                "duration": round(entry.duration, 1)
            })
        
        # Build full plain text
        full_text = " ".join([c["text"] for c in chunks])
        
        # Detect auto-generated captions
        sample = " ".join([c["text"] for c in chunks[:20]])
        punctuation_count = sum(1 for c in sample if c in '.!?,;:')
        auto_generated = punctuation_count < 3

        return {
            "success": True,
            "video_id": video_id,
            "chunks": chunks,
            "full_text": full_text,
            "total_chunks": len(chunks),
            "auto_generated_captions": auto_generated
        }
        
    except TranscriptsDisabled:
        return {"success": False, "error": "Transcripts are disabled for this video. Try a different lecture."}
    except NoTranscriptFound:
        return {"success": False, "error": "No transcript found. This video may not have captions available."}
    except Exception as e:
        return {"success": False, "error": f"Could not fetch transcript: {str(e)}"}