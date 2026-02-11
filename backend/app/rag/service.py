"""RAG: ingest text, embed (Ollama, then OpenAI, then Google), store in Chroma; query for context."""
from __future__ import annotations
import asyncio
import logging
import os
import httpx
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

COLLECTION = "asta_rag"
CHROMA_PATH = os.environ.get("ASTA_CHROMA_PATH", str(Path(__file__).resolve().parent.parent.parent / "chroma_db"))
EMBED_DIM = 768  # nomic-embed-text; OpenAI/Google normalized to this for compatibility


def _embed_ollama(text: str, base_url: str) -> list[float]:
    """Ollama embed endpoint. Returns 768-dim list or []."""
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{base_url.rstrip('/')}/api/embed",
                json={"model": "nomic-embed-text", "input": text},
            )
            if r.status_code != 200:
                return []
            data = r.json()
            emb = data.get("embeddings", [data.get("embedding", [])])[0] if data else []
            return emb if isinstance(emb, list) and len(emb) == EMBED_DIM else []
    except Exception as e:
        logger.debug("Ollama embed failed: %s", e)
        return []


def _embed_openai(text: str, api_key: str) -> list[float]:
    """OpenAI embeddings (text-embedding-3-small, 768 dims). Returns [] on failure."""
    if not (api_key or "").strip():
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key.strip())
        r = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8191],
            dimensions=EMBED_DIM,
        )
        if r.data and len(r.data) > 0:
            emb = r.data[0].embedding
            return emb[:EMBED_DIM] if len(emb) >= EMBED_DIM else emb + [0.0] * (EMBED_DIM - len(emb))
        return []
    except Exception as e:
        logger.debug("OpenAI embed failed: %s", e)
        return []


def _embed_google(text: str, api_key: str) -> list[float]:
    """Google Gemini embedding (models/embedding-001). Normalized to EMBED_DIM."""
    if not (api_key or "").strip():
        return []
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key.strip())
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        emb = result.get("embedding", getattr(result, "embedding", None)) or []
        if not emb or not isinstance(emb, list):
            return []
        # embedding-001 is 768 dims; if larger, truncate; if smaller, pad
        if len(emb) >= EMBED_DIM:
            return emb[:EMBED_DIM]
        return emb + [0.0] * (EMBED_DIM - len(emb))
    except Exception as e:
        logger.debug("Google embed failed: %s", e)
        return []


async def _get_embedding_any(text: str) -> list[float]:
    """Try Ollama first, then OpenAI, then Google. Returns 768-dim list or []."""
    from app.config import get_settings
    from app.keys import get_api_key
    settings = get_settings()
    base_url = (settings.ollama_base_url or "").strip() or "http://localhost:11434"

    # 1) Ollama (sync, run in thread)
    emb = await asyncio.to_thread(_embed_ollama, text, base_url)
    if emb:
        return emb

    # 2) OpenAI (if key set)
    openai_key = await get_api_key("openai_api_key")
    if openai_key:
        emb = await asyncio.to_thread(_embed_openai, text, openai_key)
        if emb:
            return emb

    # 3) Google (Gemini or Google AI key)
    for key_name in ("gemini_api_key", "google_ai_key"):
        key = await get_api_key(key_name)
        if key:
            emb = await asyncio.to_thread(_embed_google, text, key)
            if emb:
                return emb

    return []


class RAGService:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._coll = self._client.get_or_create_collection(
            COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    async def add(
        self,
        topic: str,
        text: str,
        doc_id: str | None = None,
    ) -> None:
        """Chunk and add text under a topic. Uses Ollama, then OpenAI, then Google for embeddings."""
        # Normalize topic to lowercase for case-insensitive matching
        topic = topic.lower()
        chunks = [text[i : i + 500] for i in range(0, len(text), 500)] if len(text) > 500 else [text]
        if not chunks:
            return
        ids = [f"{doc_id or topic}_{i}" for i in range(len(chunks))]
        embeddings: list[list[float]] = []
        for c in chunks:
            emb = await _get_embedding_any(c)
            if emb:
                embeddings.append(emb)
            else:
                embeddings.append([0.0] * EMBED_DIM)
        if embeddings:
            self._coll.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=[{"topic": topic}] * len(ids),
            )

    def list_topics(self) -> list[dict]:
        """Return list of learned topics with chunk counts. Empty if nothing learned."""
        try:
            n = self._coll.count()
            if n == 0:
                return []
            result = self._coll.get(include=["metadatas"], limit=max(n, 1))
            raw = result.get("metadatas") or []
            metadatas: list[dict] = []
            for m in raw:
                if isinstance(m, list):
                    metadatas.extend(m)
                elif m is not None:
                    metadatas.append(m)
            by_topic: dict[str, int] = {}
            for m in metadatas:
                if not isinstance(m, dict):
                    continue
                t = (m.get("topic") or "").strip() or "unknown"
                by_topic[t] = by_topic.get(t, 0) + 1
            return [{"topic": k, "chunks_count": v} for k, v in sorted(by_topic.items())]
        except Exception:
            return []

    async def query(self, question: str, topic: str | None = None, k: int = 5) -> str:
        """Return top-k relevant chunks as a single summary string for context."""
        emb = await _get_embedding_any(question)
        if not emb:
            return ""
        # Normalize topic to lowercase for case-insensitive matching
        where = {"topic": topic.lower()} if topic else None
        try:
            n = self._coll.count()
            if n == 0:
                return ""
            results = self._coll.query(
                query_embeddings=[emb],
                n_results=min(k, n),
                where=where,
            )
        except Exception:
            return ""
        if not results or not results.get("documents") or not results["documents"][0]:
            return ""
        return "\n".join(results["documents"][0])

    def delete_topic(self, topic: str) -> int:
        """Delete all chunks for a given topic. Returns number of chunks deleted."""
        # Normalize topic to lowercase for case-insensitive matching
        topic = topic.lower()
        try:
            n = self._coll.count()
            if n == 0:
                return 0
            # Get all IDs for this topic
            result = self._coll.get(where={"topic": topic}, include=["metadatas"])
            ids = result.get("ids") or []
            if ids:
                self._coll.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def get_topic_content(self, topic: str) -> str:
        """Get all content for a topic as a single text string."""
        # Normalize topic to lowercase for case-insensitive matching
        topic = topic.lower()
        try:
            result = self._coll.get(where={"topic": topic}, include=["documents"])
            docs = result.get("documents") or []
            return "\n\n".join(docs) if docs else ""
        except Exception:
            return ""

    async def update_topic(self, topic: str, new_content: str):
        """Replace all content for a topic with new content."""
        # Normalize topic to lowercase for case-insensitive matching
        topic = topic.lower()
        # Delete old content
        self.delete_topic(topic)
        # Add new content
        if new_content.strip():
            await self.add(topic, new_content)



_rag: RAGService | None = None


def get_rag() -> RAGService:
    global _rag
    if _rag is None:
        _rag = RAGService()
    return _rag
