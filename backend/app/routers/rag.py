"""RAG: learn topic, ask about topic."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.service import get_rag

router = APIRouter()


class LearnIn(BaseModel):
    topic: str
    text: str
    doc_id: str | None = None


@router.post("/rag/learn")
async def rag_learn(body: LearnIn):
    """Ingest text under a topic for later RAG."""
    rag = get_rag()
    rag.add(body.topic, body.text, doc_id=body.doc_id)
    return {"ok": True, "topic": body.topic}


class AskIn(BaseModel):
    question: str
    topic: str | None = None
    k: int = 5


@router.post("/rag/ask")
async def rag_ask(body: AskIn):
    """Get RAG context for a question (used internally by chat; can call for preview)."""
    rag = get_rag()
    summary = rag.query(body.question, topic=body.topic, k=body.k)
    return {"summary": summary}
