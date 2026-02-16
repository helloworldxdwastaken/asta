from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

import app.routers.settings as settings_router
from app.routers.settings import ModelIn, set_model


@dataclass
class _DummyDB:
    saved: tuple[str, str, str] | None = None

    async def connect(self) -> None:
        return None

    async def set_user_provider_model(self, user_id: str, provider: str, model: str) -> None:
        self.saved = (user_id, provider, model)


@pytest.mark.asyncio
async def test_set_model_rejects_openrouter_non_kimi_trinity(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await set_model(
            ModelIn(provider="openrouter", model="openai/gpt-4o-mini"),
            user_id="test-openrouter-reject",
        )

    assert exc.value.status_code == 400
    assert "Kimi/Trinity" in str(exc.value.detail)
    assert db.saved is None


@pytest.mark.asyncio
async def test_set_model_accepts_openrouter_kimi_trinity_csv(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    out = await set_model(
        ModelIn(
            provider="openrouter",
            model="moonshotai/kimi-k2.5, arcee-ai/trinity-large-preview:free, moonshotai/kimi-k2.5",
        ),
        user_id="test-openrouter-accept",
    )

    assert db.saved == (
        "test-openrouter-accept",
        "openrouter",
        "moonshotai/kimi-k2.5,arcee-ai/trinity-large-preview:free",
    )
    assert out["model"] == "moonshotai/kimi-k2.5,arcee-ai/trinity-large-preview:free"


@pytest.mark.asyncio
async def test_set_model_ollama_resolves_prefix_to_tool_model(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    async def _fake_ollama_models():
        return ["qwen2.5-coder:32b", "llama3.3"]

    monkeypatch.setattr(settings_router, "_ollama_list_models", _fake_ollama_models)

    out = await set_model(
        ModelIn(provider="ollama", model="qwen2.5-coder"),
        user_id="test-ollama-resolve",
    )

    assert db.saved == ("test-ollama-resolve", "ollama", "qwen2.5-coder:32b")
    assert out["model"] == "qwen2.5-coder:32b"


@pytest.mark.asyncio
async def test_set_model_ollama_rejects_non_tool_model(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    async def _fake_ollama_models():
        return ["qwen2.5-coder:32b", "llama3.3"]

    monkeypatch.setattr(settings_router, "_ollama_list_models", _fake_ollama_models)

    with pytest.raises(HTTPException) as exc:
        await set_model(
            ModelIn(provider="ollama", model="llama3.2"),
            user_id="test-ollama-reject",
        )

    assert exc.value.status_code == 400
    assert "tool-capable" in str(exc.value.detail)
    assert db.saved is None
