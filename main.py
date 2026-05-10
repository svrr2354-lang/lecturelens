from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from orchestrator import process_video_stream, answer_question, translate_materials, process_faculty_stream
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class QuestionRequest(BaseModel):
    question: str
    video_id: str
    language: str = "English"

class TranslateRequest(BaseModel):
    study_materials: dict
    language: str

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/process")
async def process(url: str, language: str = "English"):
    """Streaming endpoint - sends progress as each agent completes"""
    return StreamingResponse(
        process_video_stream(url, language),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/faculty")
async def faculty(url: str):
    """Streaming endpoint for faculty audit"""
    return StreamingResponse(
        process_faculty_stream(url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/search")
async def search(request: QuestionRequest):
    result = answer_question(request.question, request.video_id, request.language)
    return result

@app.post("/api/translate")
async def translate(request: TranslateRequest):
    result = translate_materials(request.study_materials, request.language)
    return result