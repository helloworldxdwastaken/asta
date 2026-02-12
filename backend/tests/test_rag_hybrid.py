"""Tests for hybrid RAG search (FTS5 keyword + vector merge)."""
import sqlite3
import hashlib
import pytest
import tempfile
import os


class TestHybridMerge:
    """Test the static merge function in isolation."""

    def test_merge_deduplicate(self):
        from app.rag.service import RAGService

        vector = [
            {"text": "Python is a programming language", "score": 0.9, "source": "vector"},
            {"text": "JavaScript is also popular", "score": 0.7, "source": "vector"},
        ]
        keyword = [
            {"text": "Python is a programming language", "score": 0.8, "source": "keyword"},
            {"text": "Python was created by Guido", "score": 0.6, "source": "keyword"},
        ]
        merged = RAGService._merge_hybrid(vector, keyword)
        assert len(merged) == 3  # 3 unique texts
        # "Python is a programming language" should be first (highest combined score)
        assert merged[0] == "Python is a programming language"

    def test_merge_empty(self):
        from app.rag.service import RAGService
        merged = RAGService._merge_hybrid([], [])
        assert merged == []

    def test_merge_vector_only(self):
        from app.rag.service import RAGService
        vector = [{"text": "hello", "score": 0.9, "source": "vector"}]
        merged = RAGService._merge_hybrid(vector, [])
        assert merged == ["hello"]

    def test_merge_keyword_only(self):
        from app.rag.service import RAGService
        keyword = [{"text": "world", "score": 0.5, "source": "keyword"}]
        merged = RAGService._merge_hybrid([], keyword)
        assert merged == ["world"]


class TestFTS5Table:
    """Test FTS5 keyword search using a temporary SQLite DB."""

    def setup_method(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(doc_id, topic, chunk_text)"
        )
        # Insert test data
        self.conn.execute(
            "INSERT INTO rag_fts VALUES (?, ?, ?)",
            ("doc1_0", "python", "Python is a high-level programming language created by Guido van Rossum"),
        )
        self.conn.execute(
            "INSERT INTO rag_fts VALUES (?, ?, ?)",
            ("doc1_1", "python", "Python supports multiple programming paradigms including object-oriented"),
        )
        self.conn.execute(
            "INSERT INTO rag_fts VALUES (?, ?, ?)",
            ("doc2_0", "javascript", "JavaScript is the language of the web browser"),
        )
        self.conn.commit()

    def teardown_method(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_keyword_match(self):
        rows = self.conn.execute(
            "SELECT chunk_text FROM rag_fts WHERE rag_fts MATCH ?", ('"Guido"',)
        ).fetchall()
        assert len(rows) == 1
        assert "Guido" in rows[0][0]

    def test_keyword_match_topic_filter(self):
        rows = self.conn.execute(
            "SELECT chunk_text FROM rag_fts WHERE rag_fts MATCH ? AND topic = ?",
            ('"programming"', "python"),
        ).fetchall()
        assert len(rows) == 2

    def test_no_match(self):
        rows = self.conn.execute(
            "SELECT chunk_text FROM rag_fts WHERE rag_fts MATCH ?", ('"nonexistentword"',)
        ).fetchall()
        assert len(rows) == 0
