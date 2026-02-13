"""RAG: ingest text, embed via Ollama (nomic-embed-text), store in Chroma; query for context.

Hybrid search: combines vector similarity (ChromaDB) with keyword search (SQLite FTS5)
for better retrieval. Inspired by OpenClaw's hybrid memory search.
"""
from __future__ import annotations
import asyncio
import logging
import os
import sqlite3
import hashlib
import httpx
from pathlib import Path

logger = logging.getLogger(__name__)

COLLECTION = "asta_rag"
CHROMA_PATH = os.environ.get("ASTA_CHROMA_PATH", str(Path(__file__).resolve().parent.parent.parent / "chroma_db"))
FTS_DB_PATH = os.environ.get("ASTA_FTS_PATH", str(Path(__file__).resolve().parent.parent.parent / "rag_fts.db"))
EMBED_DIM = 768  # nomic-embed-text


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


def _ollama_embed_error(base_url: str) -> str:
    """Try Ollama embed and return a human-readable error string, or empty if OK."""
    _, detail = _ollama_diagnose(base_url)
    return detail or ""


def _ollama_diagnose(base_url: str) -> tuple[str, str]:
    """Try Ollama embed. Returns (reason, detail). reason: ok | not_running | model_missing | wrong_config | unknown."""
    base_url = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=10) as c:
            r = c.post(
                f"{base_url}/api/embed",
                json={"model": "nomic-embed-text", "input": "test"},
            )
            if r.status_code == 200:
                data = r.json()
                emb = data.get("embeddings", [data.get("embedding", [])])[0] if data else []
                if isinstance(emb, list) and len(emb) == EMBED_DIM:
                    return "ok", ""
                return "wrong_config", "Ollama returned invalid embedding (wrong size). Pull the embed model and ensure Ollama is running."
            if r.status_code == 404:
                return "model_missing", "Model not found. Run: ollama pull nomic-embed-text"
            try:
                body = r.json()
                err = body.get("error", r.text[:200]) or r.text[:200]
            except Exception:
                err = r.text[:200] if r.text else f"HTTP {r.status_code}"
            if "model" in err.lower() and ("not found" in err.lower() or "404" in err):
                return "model_missing", err
            return "unknown", f"Ollama error ({r.status_code}): {err}"
    except httpx.ConnectError:
        return "not_running", f"Cannot reach Ollama at {base_url}. Ollama may not be installed, or it may not be running."
    except httpx.TimeoutException:
        return "not_running", f"Ollama at {base_url} timed out. Is it running?"
    except Exception as e:
        return "unknown", str(e) or "Ollama request failed"


async def _get_embedding_any(text: str) -> list[float]:
    """Embed via Ollama (nomic-embed-text). Returns 768-dim list or []."""
    from app.config import get_settings
    settings = get_settings()
    base_url = (settings.ollama_base_url or "").strip() or "http://localhost:11434"
    return await asyncio.to_thread(_embed_ollama, text, base_url)


class RAGService:
    def __init__(self) -> None:
        # Defer chromadb import so backend can start on Python 3.14 (chromadb has pydantic compat issues)
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        self._client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._coll = self._client.get_or_create_collection(
            COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        # Initialize SQLite FTS5 for keyword search
        self._fts_conn = sqlite3.connect(FTS_DB_PATH)
        self._fts_conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(doc_id, topic, chunk_text)"
        )
        self._fts_conn.commit()

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
        # Also add to FTS5 for keyword search
        try:
            for chunk_id, chunk_text in zip(ids, chunks):
                self._fts_conn.execute(
                    "INSERT OR REPLACE INTO rag_fts (doc_id, topic, chunk_text) VALUES (?, ?, ?)",
                    (chunk_id, topic, chunk_text),
                )
            self._fts_conn.commit()
        except Exception as e:
            logger.debug("FTS insert failed: %s", e)

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
        """Hybrid search: vector similarity + keyword match, merged with weights."""
        # 1) Vector search (existing)
        vector_results = await self._query_vector(question, topic, k)
        # 2) Keyword search (new FTS5)
        keyword_results = self._query_keyword(question, topic, k)
        # 3) Merge
        merged = self._merge_hybrid(vector_results, keyword_results)
        return "\n".join(merged[:k]) if merged else ""

    async def _query_vector(self, question: str, topic: str | None, k: int) -> list[dict]:
        """Vector similarity search via ChromaDB. Returns list of {text, score}."""
        emb = await _get_embedding_any(question)
        if not emb:
            return []
        where = {"topic": topic.lower()} if topic else None
        try:
            n = self._coll.count()
            if n == 0:
                return []
            results = self._coll.query(
                query_embeddings=[emb],
                n_results=min(k, n),
                where=where,
            )
        except Exception:
            return []
        if not results or not results.get("documents") or not results["documents"][0]:
            return []
        docs = results["documents"][0]
        distances = results.get("distances", [[]])[0]
        out = []
        for i, doc in enumerate(docs):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite; convert to similarity score
            dist = distances[i] if i < len(distances) else 1.0
            score = max(0.0, 1.0 - dist / 2.0)
            out.append({"text": doc, "score": score, "source": "vector"})
        return out

    def _query_keyword(self, question: str, topic: str | None, k: int) -> list[dict]:
        """Keyword search via SQLite FTS5. Returns list of {text, score}."""
        # Sanitize the query for FTS5 (escape special chars, use OR for terms)
        terms = [w for w in question.split() if len(w) > 2]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in terms[:10])  # Limit to 10 terms
        try:
            if topic:
                rows = self._fts_conn.execute(
                    "SELECT chunk_text, rank FROM rag_fts WHERE rag_fts MATCH ? AND topic = ? ORDER BY rank LIMIT ?",
                    (fts_query, topic.lower(), k),
                ).fetchall()
            else:
                rows = self._fts_conn.execute(
                    "SELECT chunk_text, rank FROM rag_fts WHERE rag_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts_query, k),
                ).fetchall()
        except Exception as e:
            logger.debug("FTS query failed: %s", e)
            return []
        out = []
        for text, rank in rows:
            # FTS5 rank is negative (more negative = more relevant); normalize to 0-1
            score = min(1.0, max(0.0, 1.0 / (1.0 + abs(rank))))
            out.append({"text": text, "score": score, "source": "keyword"})
        return out

    @staticmethod
    def _merge_hybrid(
        vector_results: list[dict],
        keyword_results: list[dict],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[str]:
        """Merge vector and keyword results with weighted scoring. Deduplicate by text hash."""
        scored: dict[str, float] = {}  # text_hash -> weighted_score
        text_map: dict[str, str] = {}  # text_hash -> original text

        for r in vector_results:
            h = hashlib.md5(r["text"].encode()).hexdigest()
            scored[h] = scored.get(h, 0) + r["score"] * vector_weight
            text_map[h] = r["text"]

        for r in keyword_results:
            h = hashlib.md5(r["text"].encode()).hexdigest()
            scored[h] = scored.get(h, 0) + r["score"] * keyword_weight
            text_map[h] = r["text"]

        # Sort by combined score descending
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        return [text_map[h] for h, _ in ranked]

    def delete_topic(self, topic: str) -> int:
        """Delete all chunks for a given topic. Returns number of chunks deleted."""
        topic = topic.lower()
        try:
            n = self._coll.count()
            if n == 0:
                deleted_count = 0
            else:
                result = self._coll.get(where={"topic": topic}, include=["metadatas"])
                ids = result.get("ids") or []
                if ids:
                    self._coll.delete(ids=ids)
                deleted_count = len(ids)
            # Also delete from FTS5
            try:
                self._fts_conn.execute("DELETE FROM rag_fts WHERE topic = ?", (topic,))
                self._fts_conn.commit()
            except Exception as e:
                logger.debug("FTS delete failed: %s", e)
            return deleted_count
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



def check_ollama_at_url(url: str) -> dict:
    """Check Ollama at an arbitrary URL (no ChromaDB). Returns { ok, detail, ollama_url, ollama_reason }."""
    u = (url or "").strip()
    if not u:
        u = "http://localhost:11434"
    if not u.startswith("http://") and not u.startswith("https://"):
        u = "http://" + u
    u = u.rstrip("/")
    reason, detail = _ollama_diagnose(u)
    if reason == "ok":
        return {"ok": True, "detail": None, "ollama_url": u, "ollama_reason": "ok"}
    return {"ok": False, "detail": detail, "ollama_url": u, "ollama_reason": reason}


_rag: RAGService | None = None


def get_rag() -> RAGService:
    global _rag
    if _rag is None:
        _rag = RAGService()
    return _rag


async def check_rag_status() -> dict:
    """Check if RAG is usable: ChromaDB/FTS OK and Ollama embedding works.
    Returns ok, message, provider, detail, ollama_url; when store fails still returns ollama check and ollama_url."""
    from app.config import get_settings
    settings = get_settings()
    base_url = (settings.ollama_base_url or "").strip() or "http://localhost:11434"
    base_url = base_url.rstrip("/")
    store_error: str | None = None
    try:
        get_rag()
    except Exception as e:
        store_error = str(e)
    reason, detail = await asyncio.to_thread(_ollama_diagnose, base_url)
    if store_error:
        return {
            "ok": False,
            "message": f"RAG store failed: {store_error}",
            "provider": None,
            "detail": detail or None,
            "ollama_url": base_url,
            "ollama_reason": reason,
            "ollama_ok": reason == "ok",
            "store_error": True,
        }
    if reason == "ok":
        return {"ok": True, "message": "RAG ready. Learn content below or ask in Chat.", "provider": "Ollama", "detail": None, "ollama_url": base_url, "ollama_reason": "ok", "ollama_ok": True}
    return {
        "ok": False,
        "message": "Ollama not available.",
        "provider": None,
        "detail": detail,
        "ollama_url": base_url,
        "ollama_reason": reason,
        "ollama_ok": False,
    }
