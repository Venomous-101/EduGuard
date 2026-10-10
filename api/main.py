"""EduGuard UAE - FastAPI backend.

Endpoints:
  POST /evaluate   {lesson_plan: str, context: str} -> verdict JSON
  GET  /health     -> KB chunk count, LLM availability
  GET  /sources    -> KB source documents with URLs
  GET  /           -> demo UI

Run:
  uvicorn api.main:app --reload --port 8000   (from the eduguard/ directory)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents.pipeline import EduGuardPipeline  # noqa: E402
from agents.llm import LLMBackend  # noqa: E402
from kb.store import PolicyKB  # noqa: E402

app = FastAPI(
    title="EduGuard UAE",
    description="Evidence-anchored AI compliance agent for UAE schools (ITU AI for Good Hackathon UAE).",
    version="0.1.0",
)

_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = EduGuardPipeline()
    return _pipeline


class EvaluateRequest(BaseModel):
    lesson_plan: str = Field(..., min_length=10, max_length=20000, description="The lesson plan or classroom AI use case to evaluate.")
    context: str = Field(default="", max_length=2000, description="Optional context: grade level, school, emirate, etc.")


@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    try:
        report = get_pipeline().evaluate(req.lesson_plan, req.context)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"evaluation failed: {e}")


@app.get("/health")
def health():
    kb = PolicyKB()
    llm = LLMBackend()
    return {
        "status": "ok",
        "kb_chunks": kb.count(),
        "kb_sources": len(kb.list_sources()),
        "llm_backend": llm.backend,
        "llm_available": llm.available,
        "notice": "SIMULATION ONLY - synthetic test data. No real student data is processed.",
    }


@app.get("/sources")
def sources():
    return {"sources": PolicyKB().list_sources()}


@app.get("/")
def demo():
    here = os.path.dirname(os.path.abspath(__file__))
    return FileResponse(os.path.join(here, "demo.html"))
