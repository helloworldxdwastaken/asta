"""RAG: learn topic, ask about topic, list what was learned."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.service import get_rag, check_rag_status, check_ollama_at_url

router = APIRouter()


@router.get("/rag/status")
async def rag_status():
    """Check if RAG is working (ChromaDB + at least one embedding provider)."""
    return await check_rag_status()


@router.get("/rag/check-ollama")
async def rag_check_ollama(url: str):
    """Check if Ollama is reachable at the given URL (no ChromaDB). For UI 'Check connection'."""
    import asyncio
    return await asyncio.to_thread(check_ollama_at_url, url)


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
    """Ingest text under a topic for later RAG. Uses Ollama (nomic-embed-text) for embeddings."""
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


@router.delete("/rag/topic/{topic}")
async def rag_delete_topic(topic: str):
    """Delete all chunks for a given topic."""
    rag = get_rag()
    deleted = rag.delete_topic(topic)
    return {"ok": True, "topic": topic, "deleted_chunks": deleted}


@router.get("/rag/topic/{topic}")
async def rag_get_topic(topic: str):
    """Get all content for a topic."""
    rag = get_rag()
    content = rag.get_topic_content(topic)
    return {"topic": topic, "content": content}


class UpdateTopicIn(BaseModel):
    content: str


@router.put("/rag/topic/{topic}")
async def rag_update_topic(topic: str, body: UpdateTopicIn):
    """Update/replace all content for a topic."""
    rag = get_rag()
    await rag.update_topic(topic, body.content)
    return {"ok": True, "topic": topic}
