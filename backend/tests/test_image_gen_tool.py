from __future__ import annotations

import json

import httpx
import pytest
from huggingface_hub.errors import HfHubHTTPError

import app.image_gen_tool as image_gen_tool


@pytest.mark.asyncio
async def test_run_image_gen_requires_prompt():
    out = await image_gen_tool.run_image_gen(user_id="u", prompt=" ")
    payload = json.loads(out)
    assert payload["error"] == "Prompt is required"


@pytest.mark.asyncio
async def test_run_image_gen_prefers_gemini_when_available(monkeypatch):
    calls = {"hf": 0}

    async def _fake_get_api_key(name: str):
        if name in {"gemini_api_key", "google_ai_key"}:
            return "gem-key"
        if name == "huggingface_api_key":
            return "hf-key"
        return None

    async def _fake_run_gemini(key: str, prompt: str):
        assert key == "gem-key"
        return json.dumps({"ok": True, "provider": "gemini"})

    async def _fake_run_hf(key: str, prompt: str):
        calls["hf"] += 1
        return json.dumps({"ok": True, "provider": "huggingface"})

    monkeypatch.setattr(image_gen_tool, "get_api_key", _fake_get_api_key)
    monkeypatch.setattr(image_gen_tool, "_run_gemini", _fake_run_gemini)
    monkeypatch.setattr(image_gen_tool, "_run_huggingface", _fake_run_hf)

    out = await image_gen_tool.run_image_gen(user_id="u", prompt="test prompt")
    payload = json.loads(out)
    assert payload["provider"] == "gemini"
    assert calls["hf"] == 0


@pytest.mark.asyncio
async def test_run_image_gen_falls_back_to_huggingface_on_gemini_rate_limit(monkeypatch):
    async def _fake_get_api_key(name: str):
        if name in {"gemini_api_key", "google_ai_key"}:
            return "gem-key"
        if name == "huggingface_api_key":
            return "hf-key"
        return None

    async def _fake_run_gemini(key: str, prompt: str):
        return None

    async def _fake_run_hf(key: str, prompt: str):
        assert key == "hf-key"
        return json.dumps({"ok": True, "provider": "huggingface"})

    monkeypatch.setattr(image_gen_tool, "get_api_key", _fake_get_api_key)
    monkeypatch.setattr(image_gen_tool, "_run_gemini", _fake_run_gemini)
    monkeypatch.setattr(image_gen_tool, "_run_huggingface", _fake_run_hf)

    out = await image_gen_tool.run_image_gen(user_id="u", prompt="test prompt")
    payload = json.loads(out)
    assert payload["provider"] == "huggingface"


@pytest.mark.asyncio
async def test_run_image_gen_supports_hf_only(monkeypatch):
    async def _fake_get_api_key(name: str):
        if name == "huggingface_api_key":
            return "hf-key"
        return None

    async def _fake_run_hf(key: str, prompt: str):
        assert key == "hf-key"
        return json.dumps({"ok": True, "provider": "huggingface"})

    monkeypatch.setattr(image_gen_tool, "get_api_key", _fake_get_api_key)
    monkeypatch.setattr(image_gen_tool, "_run_huggingface", _fake_run_hf)

    out = await image_gen_tool.run_image_gen(user_id="u", prompt="test prompt")
    payload = json.loads(out)
    assert payload["provider"] == "huggingface"


@pytest.mark.asyncio
async def test_run_image_gen_returns_clear_error_when_no_keys(monkeypatch):
    async def _fake_get_api_key(name: str):
        return None

    monkeypatch.setattr(image_gen_tool, "get_api_key", _fake_get_api_key)

    out = await image_gen_tool.run_image_gen(user_id="u", prompt="test prompt")
    payload = json.loads(out)
    assert "No image generation provider configured" in payload["error"]


@pytest.mark.asyncio
async def test_run_huggingface_calls_rate_limiter(monkeypatch):
    calls = {"rate_limit": 0, "providers": []}

    async def _fake_acquire():
        calls["rate_limit"] += 1

    async def _fake_provider_order(model: str, token: str):
        assert model == image_gen_tool.HUGGINGFACE_IMAGE_MODEL
        assert token == "hf-token"
        return ["auto"]

    async def _fake_generate(key: str, prompt: str, model: str, provider: str):
        calls["providers"].append(provider)
        assert key == "hf-token"
        assert model == image_gen_tool.HUGGINGFACE_IMAGE_MODEL
        assert prompt == "astronaut riding a horse"
        return b"fake-image-bytes", "image/png"

    monkeypatch.setattr(image_gen_tool, "_acquire_hf_rate_slot", _fake_acquire)
    monkeypatch.setattr(image_gen_tool, "_get_hf_provider_attempt_order", _fake_provider_order)
    monkeypatch.setattr(image_gen_tool, "_hf_generate_image", _fake_generate)

    out = await image_gen_tool._run_huggingface("hf-token", "astronaut riding a horse")
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["provider"] == "huggingface"
    assert calls["rate_limit"] == 1
    assert calls["providers"] == ["auto"]


@pytest.mark.asyncio
async def test_run_huggingface_retries_after_deprecated_provider(monkeypatch):
    calls = {"rate_limit": 0, "providers": []}

    async def _fake_acquire():
        calls["rate_limit"] += 1

    async def _fake_provider_order(model: str, token: str):
        return ["auto", "fal-ai"]

    def _hf_error(status: int, msg: str) -> HfHubHTTPError:
        req = httpx.Request("POST", "https://router.huggingface.co")
        resp = httpx.Response(status_code=status, request=req, text=msg)
        return HfHubHTTPError(msg, response=resp)

    async def _fake_generate(key: str, prompt: str, model: str, provider: str):
        calls["providers"].append(provider)
        if provider == "auto":
            raise _hf_error(410, "model deprecated on hf-inference")
        return b"img", "image/png"

    monkeypatch.setattr(image_gen_tool, "_acquire_hf_rate_slot", _fake_acquire)
    monkeypatch.setattr(image_gen_tool, "_get_hf_provider_attempt_order", _fake_provider_order)
    monkeypatch.setattr(image_gen_tool, "_hf_generate_image", _fake_generate)

    out = await image_gen_tool._run_huggingface("hf-token", "cyberpunk city")
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["hf_provider"] == "fal-ai"
    assert calls["providers"] == ["auto", "fal-ai"]
    assert calls["rate_limit"] == 2


@pytest.mark.asyncio
async def test_run_huggingface_returns_clear_auth_error(monkeypatch):
    async def _fake_provider_order(model: str, token: str):
        return ["auto"]

    async def _fake_acquire():
        return None

    async def _fake_generate(key: str, prompt: str, model: str, provider: str):
        req = httpx.Request("POST", "https://router.huggingface.co")
        resp = httpx.Response(status_code=401, request=req, text="unauthorized")
        raise HfHubHTTPError("unauthorized", response=resp)

    monkeypatch.setattr(image_gen_tool, "_get_hf_provider_attempt_order", _fake_provider_order)
    monkeypatch.setattr(image_gen_tool, "_acquire_hf_rate_slot", _fake_acquire)
    monkeypatch.setattr(image_gen_tool, "_hf_generate_image", _fake_generate)

    out = await image_gen_tool._run_huggingface("bad-key", "test")
    payload = json.loads(out)
    assert "invalid or unauthorized" in payload["error"].lower()
