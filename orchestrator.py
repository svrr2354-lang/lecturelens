from agents.librarian import fetch_transcript
from agents.tutor import generate_study_materials
from agents.search import index_transcript, search_transcript
from agents.translator import translate_content
from agents.faculty import audit_lecture
import json

def process_video_stream(url: str, language: str = "English"):
    """
    Streaming orchestrator - yields progress events as each agent completes
    """
    
    # Step 1 - Agent 1: Fetch transcript
    yield f"data: {json.dumps({'event': 'agent_start', 'agent': 1, 'message': 'Fetching transcript...'})}\n\n"
    
    transcript_data = fetch_transcript(url)
    
    if not transcript_data["success"]:
        yield f"data: {json.dumps({'event': 'error', 'error': transcript_data['error']})}\n\n"
        return

    # Fix 5 — Short video detection
    if transcript_data["total_chunks"] < 20:
        yield f"data: {json.dumps({'event': 'error', 'error': 'This video is too short to generate meaningful study materials. Please try a longer lecture.'})}\n\n"
        return

    chunks_count = transcript_data['total_chunks']
    yield f"data: {json.dumps({'event': 'agent_done', 'agent': 1, 'message': f'{chunks_count} chunks fetched'})}\n\n"

    # Fix 2 — Auto-generated captions warning
    if transcript_data.get("auto_generated_captions"):
        yield f"data: {json.dumps({'event': 'warning', 'message': 'Auto-generated captions detected. Study material quality may vary.'})}\n\n"

    # Step 2 - Agent 2: Generate study materials
    yield f"data: {json.dumps({'event': 'agent_start', 'agent': 2, 'message': 'Generating study materials...'})}\n\n"
    
    study_materials = generate_study_materials(transcript_data, language)
    
    if not study_materials["success"]:
        yield f"data: {json.dumps({'event': 'error', 'error': study_materials['error']})}\n\n"
        return
    
    yield f"data: {json.dumps({'event': 'agent_done', 'agent': 2, 'message': 'Outline, summaries & flashcards ready'})}\n\n"

    # Step 3 - Agent 3: Index transcript
    yield f"data: {json.dumps({'event': 'agent_start', 'agent': 3, 'message': 'Indexing for semantic search...'})}\n\n"
    
    index_result = index_transcript(transcript_data, transcript_data["video_id"])
    
    if not index_result["success"]:
        yield f"data: {json.dumps({'event': 'error', 'error': index_result['error']})}\n\n"
        return
    
    segments_count = index_result['segments_indexed']
    yield f"data: {json.dumps({'event': 'agent_done', 'agent': 3, 'message': f'{segments_count} segments indexed'})}\n\n"

    # All done - send final result
    result = {
        "event": "complete",
        "video_id": transcript_data["video_id"],
        "outline": study_materials["outline"],
        "summary_90": study_materials["summary_90"],
        "summary_5min": study_materials["summary_5min"],
        "flashcards": study_materials["flashcards"],
        "total_chunks": transcript_data["total_chunks"]
    }
    
    yield f"data: {json.dumps(result)}\n\n"


def answer_question(question: str, video_id: str, language: str = "English") -> dict:
    print(f"[Orchestrator] Question received: {question}")
    result = search_transcript(question, video_id, language)
    return result


def translate_materials(study_materials: dict, language: str) -> dict:
    print(f"[Orchestrator] Translation requested: {language}")
    result = translate_content(study_materials, language)
    return result

def process_faculty_stream(url: str):
    """
    Faculty orchestrator - fetches transcript then runs faculty audit
    """

    # Step 1 - Agent 1: Fetch transcript
    yield f"data: {json.dumps({'event': 'agent_start', 'agent': 1, 'message': 'Fetching transcript...'})}\n\n"

    transcript_data = fetch_transcript(url)

    if not transcript_data["success"]:
        yield f"data: {json.dumps({'event': 'error', 'error': transcript_data['error']})}\n\n"
        return

    if transcript_data["total_chunks"] < 20:
        yield f"data: {json.dumps({'event': 'error', 'error': 'This video is too short to audit. Please try a longer lecture.'})}\n\n"
        return

    chunks_count = transcript_data['total_chunks']
    yield f"data: {json.dumps({'event': 'agent_done', 'agent': 1, 'message': f'{chunks_count} chunks fetched'})}\n\n"

    # Step 2 - Faculty Agent: Audit lecture
    yield f"data: {json.dumps({'event': 'agent_start', 'agent': 'faculty', 'message': 'Auditing lecture...'})}\n\n"

    audit_result = audit_lecture(transcript_data)

    if not audit_result["success"]:
        yield f"data: {json.dumps({'event': 'error', 'error': audit_result['error']})}\n\n"
        return

    yield f"data: {json.dumps({'event': 'agent_done', 'agent': 'faculty', 'message': 'Audit complete'})}\n\n"

    # Send final result
    result = {
        "event": "faculty_complete",
        "overall_score": audit_result["overall_score"],
        "top_priority": audit_result["top_priority"],
        "pedagogical": audit_result["pedagogical"],
        "accessibility": audit_result["accessibility"],
        "equity": audit_result["equity"],
        "clarity": audit_result["clarity"],
        "rewrite_examples": audit_result["rewrite_examples"],
        "total_chunks": transcript_data["total_chunks"]
    }

    yield f"data: {json.dumps(result)}\n\n"