from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

import app.routers.settings as settings_router
from app.routers.settings import (
    DefaultAiIn,
    ProviderEnabledIn,
    get_provider_flow,
    set_default_ai,
    set_provider_enabled,
)


@dataclass
class _DummyDB:
    default_provider: str = "claude"
    runtime: dict[str, dict] = field(
        default_factory=lambda: {
            "claude": {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
            "ollama": {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
            "openrouter": {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
        }
    )
    models: dict[str, str] = field(default_factory=lambda: {"claude": "claude-3-5-sonnet-20241022"})
    keys: dict[str, str] = field(default_factory=lambda: {"anthropic_api_key": "x", "openrouter_api_key": "y"})

    async def connect(self) -> None:
        return None

    async def get_user_default_ai(self, user_id: str) -> str:
        return self.default_provider

    async def set_user_default_ai(self, user_id: str, provider: str) -> None:
        self.default_provider = provider

    async def set_provider_runtime_enabled(self, user_id: str, provider: str, enabled: bool) -> None:
        current = self.runtime.get(provider) or {"enabled": True, "auto_disabled": False, "disabled_reason": ""}
        current["enabled"] = bool(enabled)
        if enabled:
            current["auto_disabled"] = False
            current["disabled_reason"] = ""
        self.runtime[provider] = current

    async def get_provider_runtime_states(self, user_id: str, providers):
        out = {}
        for provider in providers:
            out[provider] = self.runtime.get(
                provider,
                {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
            )
        return out

    async def get_all_provider_models(self, user_id: str) -> dict[str, str]:
        return dict(self.models)

    async def get_stored_api_key(self, key_name: str) -> str | None:
        return self.keys.get(key_name)


@pytest.mark.asyncio
async def test_set_default_ai_rejects_non_main_provider(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    out = await set_default_ai(DefaultAiIn(provider="openai"), user_id="u")
    assert "error" in out


@pytest.mark.asyncio
async def test_get_provider_flow_returns_fixed_priority(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)

    async def _ollama_up():
        return True

    monkeypatch.setattr(settings_router, "_ollama_reachable", _ollama_up)
    out = await get_provider_flow(user_id="u")

    assert out["order"] == list(settings_router.MAIN_PROVIDER_CHAIN)
    assert out["default_provider"] == "claude"
    assert [row["position"] for row in out["providers"]] == list(range(1, len(settings_router.MAIN_PROVIDER_CHAIN) + 1))
    assert all("active" in row for row in out["providers"])


@pytest.mark.asyncio
async def test_set_provider_enabled_updates_runtime_state(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    out = await set_provider_enabled(ProviderEnabledIn(provider="claude", enabled=False), user_id="u")
    assert out["provider"] == "claude"
    assert out["enabled"] is False


@pytest.mark.asyncio
async def test_set_provider_enabled_rejects_unknown_provider(monkeypatch):
    db = _DummyDB()
    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    with pytest.raises(HTTPException):
        await set_provider_enabled(ProviderEnabledIn(provider="openai", enabled=True), user_id="u")
