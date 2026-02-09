"""RAG: ingest text, embed (Ollama), store in Chroma; query for context."""
from __future__ import annotations
import os
import httpx
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings

COLLECTION = "asta_rag"
CHROMA_PATH = os.environ.get("ASTA_CHROMA_PATH", str(Path(__file__).resolve().parent.parent.parent / "chroma_db"))


def _get_embedding(text: str, base_url: str) -> list[float]:
    """Ollama embed endpoint."""
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{base_url.rstrip('/')}/api/embed", json={"model": "nomic-embed-text", "input": text})
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("embeddings", [data.get("embedding", [])])[0] if data else []


class RAGService:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=CHROMA_PATH, settings=ChromaSettings(anonymized_telemetry=False))
        self._coll = self._client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    def add(self, topic: str, text: str, doc_id: str | None = None, base_url: str = "http://localhost:11434") -> None:
        """Chunk and add text under a topic."""
        chunks = [text[i : i + 500] for i in range(0, len(text), 500)] if len(text) > 500 else [text]
        if not chunks:
            return
        from app.config import get_settings
        base_url = get_settings().ollama_base_url
        ids = [f"{doc_id or topic}_{i}" for i in range(len(chunks))]
        embeddings = []
        for c in chunks:
            emb = _get_embedding(c, base_url)
            if emb:
                embeddings.append(emb)
            else:
                embeddings.append([0.0] * 768)  # fallback dimension
        if embeddings:
            self._coll.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=[{"topic": topic}] * len(ids))

    def query(self, question: str, topic: str | None = None, k: int = 5, base_url: str = "http://localhost:11434") -> str:
        """Return top-k relevant chunks as a single summary string for context."""
        from app.config import get_settings
        base_url = get_settings().ollama_base_url
        emb = _get_embedding(question, base_url)
        if not emb:
            return ""
        where = {"topic": topic} if topic else None
        try:
            n = self._coll.count()
            if n == 0:
                return ""
            results = self._coll.query(query_embeddings=[emb], n_results=min(k, n), where=where)
        except Exception:
            return ""
        if not results or not results.get("documents") or not results["documents"][0]:
            return ""
        return "\n".join(results["documents"][0])


_rag: RAGService | None = None


def get_rag() -> RAGService:
    global _rag
    if _rag is None:
        _rag = RAGService()
    return _rag
