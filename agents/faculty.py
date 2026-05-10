import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def audit_lecture(transcript_data: dict, language: str = "English") -> dict:
    """Agent 5 - Faculty Auditor: Audit lecture across 4 dimensions"""
    
    if not transcript_data.get("success"):
        return {"success": False, "error": "No valid transcript provided"}
    
    full_text = transcript_data["full_text"]
    chunks = transcript_data["chunks"]
    
    # Build timestamped transcript (same sampling logic as tutor)
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

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": f"""You are an expert pedagogical consultant reviewing a lecture transcript for a faculty member who wants to improve their teaching. This report is private and only for the faculty member.

Here is the timestamped lecture transcript:
{timestamped[:30000]}

Audit this lecture across these 4 dimensions and provide specific, actionable feedback:

1. PEDAGOGICAL QUALITY — Structure, learning objectives, examples, pacing
2. ACCESSIBILITY — Language complexity, jargon, assumptions about prior knowledge
3. EQUITY & INCLUSION — Inclusive language, diverse examples, cultural sensitivity
4. CLARITY — Explanation quality, confusing sections, transitions

Format your response EXACTLY like this:

OVERALL_SCORE:
(Give an overall letter grade A/B/C/D and one sentence explaining it)

TOP_PRIORITY:
(The single most important thing to fix — be specific and direct)

PEDAGOGICAL:
SCORE: (A/B/C/D)
STRENGTHS: (2-3 specific strengths with timestamps)
ISSUES: (2-3 specific issues with timestamps)
SUGGESTION: (One specific rewrite suggestion with timestamp)

ACCESSIBILITY:
SCORE: (A/B/C/D)
STRENGTHS: (2-3 specific strengths with timestamps)
ISSUES: (2-3 specific issues with timestamps)
SUGGESTION: (One specific rewrite suggestion with timestamp)

EQUITY:
SCORE: (A/B/C/D)
STRENGTHS: (2-3 specific strengths with timestamps)
ISSUES: (2-3 specific issues with timestamps)
SUGGESTION: (One specific rewrite suggestion with timestamp)

CLARITY:
SCORE: (A/B/C/D)
STRENGTHS: (2-3 specific strengths with timestamps)
ISSUES: (2-3 specific issues with timestamps)
SUGGESTION: (One specific rewrite suggestion with timestamp)

REWRITE_EXAMPLES:
(Provide 2-3 specific timestamped sections that could be improved, with exact suggested rewrites)
Example format:
[MM:SS] ORIGINAL: "..."
REWRITE: "..."
REASON: (Why this is better)"""
            }]
        )
        
        audit_text = response.content[0].text
        parsed = parse_audit_response(audit_text)
        
        return {
            "success": True,
            "raw": audit_text,
            **parsed
        }
        
    except Exception as e:
        return {"success": False, "error": f"Faculty audit failed: {str(e)}"}


def parse_audit_response(text: str) -> dict:
    """Parse Claude's audit response into structured data"""
    
    result = {
        "overall_score": "",
        "top_priority": "",
        "pedagogical": {"score": "", "strengths": "", "issues": "", "suggestion": ""},
        "accessibility": {"score": "", "strengths": "", "issues": "", "suggestion": ""},
        "equity": {"score": "", "strengths": "", "issues": "", "suggestion": ""},
        "clarity": {"score": "", "strengths": "", "issues": "", "suggestion": ""},
        "rewrite_examples": ""
    }
    
    try:
        if "OVERALL_SCORE:" in text:
            result["overall_score"] = text.split("OVERALL_SCORE:")[1].split("TOP_PRIORITY:")[0].strip()
        
        if "TOP_PRIORITY:" in text:
            result["top_priority"] = text.split("TOP_PRIORITY:")[1].split("PEDAGOGICAL:")[0].strip()
        
        for dimension in ["pedagogical", "accessibility", "equity", "clarity"]:
            key = dimension.upper() + ":"
            next_keys = {
                "pedagogical": "ACCESSIBILITY:",
                "accessibility": "EQUITY:",
                "equity": "CLARITY:",
                "clarity": "REWRITE_EXAMPLES:"
            }
            
            if key in text:
                section = text.split(key)[1].split(next_keys[dimension])[0]
                
                if "SCORE:" in section:
                    result[dimension]["score"] = section.split("SCORE:")[1].split("STRENGTHS:")[0].strip()
                if "STRENGTHS:" in section:
                    result[dimension]["strengths"] = section.split("STRENGTHS:")[1].split("ISSUES:")[0].strip()
                if "ISSUES:" in section:
                    result[dimension]["issues"] = section.split("ISSUES:")[1].split("SUGGESTION:")[0].strip()
                if "SUGGESTION:" in section:
                    result[dimension]["suggestion"] = section.split("SUGGESTION:")[1].strip()
        
        if "REWRITE_EXAMPLES:" in text:
            result["rewrite_examples"] = text.split("REWRITE_EXAMPLES:")[1].strip()
    
    except:
        pass
    
    return result