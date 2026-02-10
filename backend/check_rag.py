#!/usr/bin/env python3
"""Check what's in the RAG (Chroma) store. Run from backend/: python check_rag.py
Uses same path and .env as the app so we're not looking at a different DB."""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
# Load backend/.env so ASTA_CHROMA_PATH matches the running server
_env = BACKEND_DIR / ".env"
if _env.is_file():
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

# Same formula as app/rag/service.py (default: backend/chroma_db)
_default = str(BACKEND_DIR / "chroma_db")
_raw = os.environ.get("ASTA_CHROMA_PATH", _default)
p = Path(_raw)
CHROMA_PATH = p.resolve() if p.is_absolute() else (BACKEND_DIR / _raw).resolve()
COLLECTION = "asta_rag"


def main():
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
    except ImportError:
        print("chromadb not installed. Run: pip install chromadb")
        sys.exit(1)

    print(f"RAG DB path: {CHROMA_PATH}")
    if not CHROMA_PATH.exists():
        print(f"Chroma DB path does not exist: {CHROMA_PATH}")
        print("RAG has not stored anything yet (no chroma_db folder).")
        print("(If the server runs from another dir with ASTA_CHROMA_PATH=./chroma_db, that DB is elsewhere.)")
        sys.exit(0)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH), settings=ChromaSettings(anonymized_telemetry=False))
    try:
        coll = client.get_collection(COLLECTION)
    except Exception as e:
        print(f"Collection {COLLECTION!r} not found or error: {e}")
        sys.exit(0)

    n = coll.count()
    print(f"Total chunks in RAG: {n}")
    if n == 0:
        print("RAG is empty. Nothing learned yet.")
        sys.exit(0)

    result = coll.get(include=["metadatas"], limit=n)
    raw = result.get("metadatas") or []
    metadatas = []
    for m in raw:
        if isinstance(m, list):
            metadatas.extend(m)
        elif m is not None:
            metadatas.append(m)

    by_topic = {}
    for m in metadatas:
        if not isinstance(m, dict):
            continue
        t = (m.get("topic") or "").strip() or "unknown"
        by_topic[t] = by_topic.get(t, 0) + 1

    print("\nTopics actually in RAG (topic -> chunk count):")
    for topic, count in sorted(by_topic.items()):
        print(f"  - {topic!r}: {count} chunks")
    print(f"\nUnique topics: {len(by_topic)}")
    if by_topic:
        print("So the AI should only claim it learned about the topics listed above.")

if __name__ == "__main__":
    main()
