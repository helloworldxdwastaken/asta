from __future__ import annotations

import pytest

import app.routers.settings as settings_router
from app.routers.settings import ApiKeysIn, get_api_keys_status, set_api_keys


class _DummyDB:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.status = {"huggingface_api_key": True}

    async def connect(self) -> None:
        return None

    async def get_api_keys_status(self) -> dict[str, bool]:
        return dict(self.status)

    async def set_stored_api_key(self, key_name: str, value: str) -> None:
        self.saved.append((key_name, value))


@pytest.mark.asyncio
async def test_get_api_keys_status_includes_huggingface(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    out = await get_api_keys_status()
    assert "huggingface_api_key" in out
    assert out["huggingface_api_key"] is True


@pytest.mark.asyncio
async def test_set_api_keys_persists_huggingface(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    await set_api_keys(ApiKeysIn(huggingface_api_key="hf_123"))
    assert ("huggingface_api_key", "hf_123") in db.saved


@pytest.mark.asyncio
async def test_test_api_key_huggingface_reports_missing_key(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    async def _fake_get_api_key(name: str):
        return None

    monkeypatch.setattr("app.keys.get_api_key", _fake_get_api_key)
    out = await settings_router.test_api_key(provider="huggingface", user_id="u")

    assert out["ok"] is False
    assert "No Hugging Face API key set" in (out["error"] or "")
