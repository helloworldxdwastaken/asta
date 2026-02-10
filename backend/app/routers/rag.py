"""RAG: learn topic, ask about topic, list what was learned."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.service import get_rag

router = APIRouter()


@router.get("/rag/learned")
async def rag_learned():
    """Return whether the AI has learned anything and what topics (with chunk counts)."""
    rag = get_rag()
    topics = rag.list_topics()
    return {"has_learned": len(topics) > 0, "topics": topics}


class LearnIn(BaseModel):
    topic: str
    text: str
    doc_id: str | None = None


@router.post("/rag/learn")
async def rag_learn(body: LearnIn):
    """Ingest text under a topic for later RAG. Uses Ollama, then OpenAI, then Google for embeddings."""
    rag = get_rag()
    await rag.add(body.topic, body.text, doc_id=body.doc_id)
    return {"ok": True, "topic": body.topic}


class AskIn(BaseModel):
    question: str
    topic: str | None = None
    k: int = 5


@router.post("/rag/ask")
async def rag_ask(body: AskIn):
    """Get RAG context for a question (used internally by chat; can call for preview)."""
    rag = get_rag()
    summary = await rag.query(body.question, topic=body.topic, k=body.k)
    return {"summary": summary}
