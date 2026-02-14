from pathlib import Path

import pytest

from app.config import get_settings
from app.memory_health import get_memory_health


@pytest.mark.asyncio
async def test_memory_health_warns_when_rag_unavailable_and_workspace_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTA_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()

    async def _fake_rag_status():
        return {
            "ok": False,
            "message": "Ollama not available.",
            "detail": "Cannot reach Ollama",
            "provider": None,
            "ollama_url": "http://localhost:11434",
            "ollama_reason": "not_running",
        }

    monkeypatch.setattr("app.memory_health.check_rag_status", _fake_rag_status)
    health = await get_memory_health(force=True)
    assert health["status"] == "warn"
    ids = {f["id"] for f in health["findings"]}
    assert "memory.rag.unavailable" in ids
    assert "memory.workspace.empty" in ids
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_memory_health_ok_with_sources_and_rag_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTA_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "USER.md").write_text("Name: Tokyo\n", encoding="utf-8")

    async def _fake_rag_status():
        return {
            "ok": True,
            "message": "RAG ready",
            "detail": None,
            "provider": "Ollama",
            "ollama_url": "http://localhost:11434",
            "ollama_reason": "ok",
        }

    monkeypatch.setattr("app.memory_health.check_rag_status", _fake_rag_status)
    health = await get_memory_health(force=True)
    assert health["status"] == "ok"
    assert health["workspace"]["has_user_md"] is True
    get_settings.cache_clear()
