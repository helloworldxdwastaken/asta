import pytest
from fastapi import HTTPException

import app.routers.settings as settings_router
from app.routers.settings import VisionSettingsIn, get_vision_settings, set_vision_settings


@pytest.mark.asyncio
async def test_get_vision_settings_reads_current_config(monkeypatch):
    class _S:
        asta_vision_preprocess = False
        asta_vision_provider_order = "openrouter,ollama"
        asta_vision_openrouter_model = "openrouter/demo-vision"

    monkeypatch.setattr(settings_router, "get_settings", lambda: _S())
    out = await get_vision_settings()
    assert out["preprocess"] is False
    assert out["provider_order"] == "openrouter,ollama"
    assert out["openrouter_model"] == "openrouter/demo-vision"


@pytest.mark.asyncio
async def test_set_vision_settings_persists_env(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_set_env(key: str, value: str, *, allow_empty: bool = False):
        captured[key] = value

    monkeypatch.setattr(settings_router, "set_env_value", _fake_set_env)
    out = await set_vision_settings(
        VisionSettingsIn(
            preprocess=False,
            provider_order="openrouter,ollama",
            openrouter_model="openrouter/demo-vision",
        )
    )
    assert out["preprocess"] is False
    assert out["provider_order"] == "openrouter,ollama"
    assert out["openrouter_model"] == "openrouter/demo-vision"
    assert captured["ASTA_VISION_PREPROCESS"] == "false"
    assert captured["ASTA_VISION_PROVIDER_ORDER"] == "openrouter,ollama"
    assert captured["ASTA_VISION_OPENROUTER_MODEL"] == "openrouter/demo-vision"


@pytest.mark.asyncio
async def test_set_vision_settings_rejects_invalid_provider_name():
    with pytest.raises(HTTPException) as exc:
        await set_vision_settings(
            VisionSettingsIn(
                preprocess=True,
                provider_order="openrouter,not-a-provider",
                openrouter_model="model",
            )
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_vision_settings_uses_defaults_for_blank_fields(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_set_env(key: str, value: str, *, allow_empty: bool = False):
        captured[key] = value

    monkeypatch.setattr(settings_router, "set_env_value", _fake_set_env)
    out = await set_vision_settings(
        VisionSettingsIn(
            preprocess=True,
            provider_order="",
            openrouter_model="",
        )
    )
    assert out["provider_order"] == "openrouter,ollama"
    assert out["openrouter_model"] == "nvidia/nemotron-nano-12b-v2-vl:free"
    assert captured["ASTA_VISION_PROVIDER_ORDER"] == "openrouter,ollama"
    assert captured["ASTA_VISION_OPENROUTER_MODEL"] == "nvidia/nemotron-nano-12b-v2-vl:free"
