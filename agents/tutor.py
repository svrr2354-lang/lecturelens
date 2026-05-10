import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_study_materials(transcript_data: dict, language: str = "English") -> dict:
    """Agent 2 - Tutor: Generate study materials from transcript"""
    
    if not transcript_data.get("success"):
        return {"success": False, "error": "No valid transcript provided"}
    
    full_text = transcript_data["full_text"]
    chunks = transcript_data["chunks"]
    
    # Build a timestamped transcript for context
    # For long videos, sample evenly across entire lecture
    timestamped = ""
    
    if len(chunks) > 300:
        step = len(chunks) // 300
        sampled_chunks = chunks[::step][:300]
    else:
        sampled_chunks = chunks
    
    for chunk in sampled_chunks:
        minutes = int(chunk["start"] // 60)
        seconds = int(chunk["start"] % 60)
        timestamped += f"[{minutes:02d}:{seconds:02d}] {chunk['text']}\n"

    # Build sampled full text for flashcards
    sampled_full_text = " ".join([c["text"] for c in sampled_chunks])

    # ── CONTENT VALIDATION ──
    try:
        validation_response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"""Look at this transcript excerpt and answer with ONLY "yes" or "no".
Is this educational content like a lecture, tutorial, course, documentary, or talk?

Transcript excerpt:
{full_text[:1000]}

Answer with only yes or no:"""
            }]
        )
        
        is_educational = validation_response.content[0].text.strip().lower()
        
        if "no" in is_educational:
            return {
                "success": False,
                "error": "This doesn't appear to be a lecture or educational video. LectureLens works best with lectures, tutorials, courses, and educational talks."
            }
    except:
        pass  # If validation fails, continue anyway

    # ── GENERATE STUDY MATERIALS ──
    try:
        # Generate outline + summaries
        outline_response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": f"""You are an expert tutor analyzing a lecture transcript.

Here is the timestamped transcript:
{timestamped[:30000]}

Please provide:
1. A structured outline with 5-8 main topics, each with a timestamp reference (MM:SS format)
2. A 90-second summary (around 150 words) - the absolute essentials only
3. A 5-minute summary (around 500 words) - key concepts with some detail

Format your response exactly like this:

OUTLINE:
- [MM:SS] Topic 1
  - Subtopic
- [MM:SS] Topic 2
  - Subtopic

SUMMARY_90:
(your 90 second summary here)

SUMMARY_5MIN:
(your 5 minute summary here)

Generate all content in {language}."""
            }]
        )
        
        outline_text = outline_response.content[0].text
        
        # Generate flashcards
        flashcard_response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"""You are an expert tutor creating flashcards from a lecture transcript.

Here is the transcript:
{sampled_full_text[:20000]}

Create exactly 8 flashcards covering the most important concepts.
Format exactly like this:

FLASHCARD_1:
FRONT: (question or term)
BACK: (answer or definition)
TIMESTAMP: MM:SS

FLASHCARD_2:
FRONT: (question or term)
BACK: (answer or definition)
TIMESTAMP: MM:SS

(continue for all 8 flashcards)

Generate all flashcards in {language}."""
            }]
        )
        
        flashcard_text = flashcard_response.content[0].text
        
        # Parse the responses
        outline, summary_90, summary_5min = parse_outline_response(outline_text)
        flashcards = parse_flashcards(flashcard_text)
        
        return {
            "success": True,
            "outline": outline,
            "summary_90": summary_90,
            "summary_5min": summary_5min,
            "flashcards": flashcards
        }
        
    except Exception as e:
        return {"success": False, "error": f"Tutor agent failed: {str(e)}"}


def parse_outline_response(text: str) -> tuple:
    """Parse Claude's response into outline, 90s summary, and 5min summary"""
    outline = ""
    summary_90 = ""
    summary_5min = ""
    
    if "OUTLINE:" in text:
        parts = text.split("OUTLINE:")[1]
        if "SUMMARY_90:" in parts:
            outline = parts.split("SUMMARY_90:")[0].strip()
            rest = parts.split("SUMMARY_90:")[1]
            if "SUMMARY_5MIN:" in rest:
                summary_90 = rest.split("SUMMARY_5MIN:")[0].strip()
                summary_5min = rest.split("SUMMARY_5MIN:")[1].strip()
    
    return outline, summary_90, summary_5min


def parse_flashcards(text: str) -> list:
    """Parse Claude's response into a list of flashcard dicts"""
    flashcards = []
    cards = text.split("FLASHCARD_")[1:]
    
    for card in cards:
        lines = card.strip().split("\n")
        front = ""
        back = ""
        timestamp = ""
        
        for line in lines:
            if line.startswith("FRONT:"):
                front = line.replace("FRONT:", "").strip()
            elif line.startswith("BACK:"):
                back = line.replace("BACK:", "").strip()
            elif line.startswith("TIMESTAMP:"):
                timestamp = line.replace("TIMESTAMP:", "").strip()
        
        if front and back:
            flashcards.append({
                "front": front,
                "back": back,
                "timestamp": timestamp
            })
    
    return flashcards