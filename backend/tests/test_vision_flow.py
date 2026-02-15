import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse
from app.providers.claude import ClaudeProvider
from app.providers.openai import OpenAIProvider


def _sample_png_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), (120, 30, 200))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


@pytest.mark.asyncio
async def test_openai_provider_includes_image_content_block():
    calls: list[dict] = []

    class _FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            msg = SimpleNamespace(content="ok", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    with patch("app.providers.openai.get_api_key", new=AsyncMock(return_value="k")), patch(
        "app.providers.openai.AsyncOpenAI", _FakeClient
    ):
        resp = await OpenAIProvider().chat(
            [{"role": "user", "content": "What is in this image?"}],
            image_bytes=b"jpeg-bytes",
            image_mime="image/jpeg",
        )

    assert resp.content == "ok"
    assert calls
    payload = calls[0]["messages"][-1]["content"]
    assert isinstance(payload, list)
    assert payload[0]["type"] == "text"
    assert payload[1]["type"] == "image_url"
    assert payload[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_claude_provider_includes_image_content_block():
    calls: list[dict] = []

    class _FakeMessages:
        async def create(self, **kwargs):
            calls.append(kwargs)
            content = [SimpleNamespace(type="text", text="ok")]
            return SimpleNamespace(content=content)

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

    with patch("app.providers.claude.get_api_key", new=AsyncMock(return_value="k")), patch(
        "app.providers.claude.AsyncAnthropic", _FakeClient
    ):
        resp = await ClaudeProvider().chat(
            [{"role": "user", "content": "Describe this image"}],
            image_bytes=b"abc",
            image_mime="image/jpeg",
        )

    assert resp.content == "ok"
    assert calls
    payload = calls[0]["messages"][-1]["content"]
    assert isinstance(payload, list)
    assert payload[0]["type"] == "text"
    assert payload[1]["type"] == "image"
    assert payload[1]["source"]["type"] == "base64"
    assert payload[1]["source"]["media_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_handle_message_routes_image_to_vision_provider_when_needed():
    db = get_db()
    await db.connect()
    user_id = f"vision-route-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    await db.set_user_default_ai(user_id, "ollama")

    observed: dict[str, str] = {}

    class _Provider:
        def __init__(self, name: str, *, allow_chat: bool = False):
            self.name = name
            self._allow_chat = allow_chat

        async def chat(self, messages, **kwargs):
            if not self._allow_chat:
                raise AssertionError(f"provider.chat should not be called for {self.name}")
            observed["vision_provider"] = self.name
            observed["vision_has_image"] = str(bool(kwargs.get("image_bytes")))
            observed["vision_mime"] = str(kwargs.get("image_mime") or "")
            return ProviderResponse(content="scene: desk and laptop")

    async def _fake_fallback(primary, messages, fallback_names, **kwargs):
        observed["provider"] = primary.name
        observed["mime"] = str(kwargs.get("image_mime") or "")
        observed["has_image"] = str(bool(kwargs.get("image_bytes")))
        observed["user_content"] = str(messages[-1].get("content") or "")
        return ProviderResponse(content="vision ok"), primary

    async def _fake_compact(messages, provider, context=None, max_tokens=None):
        return messages

    def _fake_get_provider(name: str):
        if name == "openrouter":
            return _Provider(name, allow_chat=True)
        if name == "ollama":
            return _Provider(name)
        return None

    async def _fake_get_api_key(key_name: str):
        return "openrouter-key" if key_name == "openrouter_api_key" else None

    with patch("app.handler.get_provider", side_effect=_fake_get_provider), patch(
        "app.providers.fallback.chat_with_fallback", side_effect=_fake_fallback
    ), patch("app.compaction.compact_history", side_effect=_fake_compact), patch(
        "app.keys.get_api_key", side_effect=_fake_get_api_key
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="what is in this image?",
            provider_name="default",
            conversation_id=cid,
            channel_target="web",
            image_bytes=_sample_png_bytes(),
            image_mime="image/png",
        )

    assert "vision ok" in reply
    assert observed["vision_provider"] == "openrouter"
    assert observed["vision_has_image"] == "True"
    assert observed["vision_mime"] == "image/jpeg"
    assert observed["provider"] == "ollama"
    assert observed["has_image"] == "False"
    assert observed["mime"] == ""
    assert "[VISION_ANALYSIS source=openrouter/" in observed["user_content"]


@pytest.mark.asyncio
async def test_handle_message_replies_with_guidance_when_no_vision_provider_available():
    db = get_db()
    await db.connect()
    user_id = f"vision-no-key-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    await db.set_user_default_ai(user_id, "ollama")

    class _Provider:
        def __init__(self, name: str):
            self.name = name

    def _fake_get_provider(name: str):
        if name == "ollama":
            return _Provider(name)
        return None

    async def _fake_compact(messages, provider, context=None, max_tokens=None):
        return messages

    fallback_mock = AsyncMock()

    with patch("app.handler.get_provider", side_effect=_fake_get_provider), patch(
        "app.providers.fallback.chat_with_fallback", fallback_mock
    ), patch("app.compaction.compact_history", side_effect=_fake_compact), patch(
        "app.keys.get_api_key", new=AsyncMock(return_value=None)
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="please describe this picture",
            provider_name="default",
            conversation_id=cid,
            channel_target="web",
            image_bytes=_sample_png_bytes(),
            image_mime="image/png",
        )

    assert "does not support vision" in reply
    assert fallback_mock.await_count == 0
