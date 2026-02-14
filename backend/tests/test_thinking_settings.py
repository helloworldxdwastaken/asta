from unittest.mock import patch, AsyncMock

import pytest
import uuid
from fastapi import HTTPException

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse
from app.routers.settings import set_thinking, set_reasoning, ThinkingIn, ReasoningIn


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


@pytest.mark.asyncio
async def test_db_thinking_level_roundtrip():
    db = get_db()
    await db.connect()
    user_id = f"test-thinking-roundtrip-{uuid.uuid4().hex[:8]}"

    # Default when not set.
    level = await db.get_user_thinking_level(user_id)
    assert level == "off"

    await db.set_user_thinking_level(user_id, "high")
    level2 = await db.get_user_thinking_level(user_id)
    assert level2 == "high"

    mode = await db.get_user_reasoning_mode(user_id)
    assert mode == "off"
    await db.set_user_reasoning_mode(user_id, "on")
    mode2 = await db.get_user_reasoning_mode(user_id)
    assert mode2 == "on"


@pytest.mark.asyncio
async def test_handler_passes_thinking_level_to_provider_kwargs():
    db = get_db()
    await db.connect()
    user_id = "test-thinking-handler-pass"
    await db.set_user_thinking_level(user_id, "medium")

    observed = {"thinking_level": None, "context": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        observed["context"] = kwargs.get("context") or ""
        return ProviderResponse(content="hello"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hi",
            provider_name="openai",
        )

    assert reply
    assert observed["thinking_level"] == "medium"
    assert "[THINKING]" in observed["context"]


@pytest.mark.asyncio
async def test_reasoning_mode_formats_think_blocks():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-format"
    await db.set_user_thinking_level(user_id, "off")
    await db.set_user_reasoning_mode(user_id, "on")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="<think>Checked reminders list first.</think>\nYou have no reminders."), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="say hello",
            provider_name="openai",
        )

    assert "Reasoning:" in reply
    assert "Checked reminders list first." in reply
    assert "You have no pending reminders." in reply or "You have no reminders." in reply


@pytest.mark.asyncio
async def test_reasoning_mode_off_hides_think_blocks():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-off"
    await db.set_user_reasoning_mode(user_id, "off")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="<think>Internal path.</think>\nFinal answer"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hello",
            provider_name="openai",
        )

    assert "Reasoning:" not in reply
    assert "Internal path." not in reply
    assert "Final answer" in reply


@pytest.mark.asyncio
async def test_reasoning_mode_on_hides_reasoning_when_model_skips_think():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-fallback"
    await db.set_user_reasoning_mode(user_id, "on")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="Final answer only"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            text="hello",
            provider_name="openai",
        )

    assert "Reasoning:" not in reply
    assert "Final answer only" in reply


@pytest.mark.asyncio
async def test_reasoning_mode_stream_emits_reasoning_status_separately():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-stream-separate"
    await db.set_user_reasoning_mode(user_id, "stream")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="<think>Checked file tool output.</think>\nFinal answer"), primary

    emit_mock = AsyncMock()
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.handler._emit_stream_status", emit_mock),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hello",
            provider_name="openai",
        )

    assert "Reasoning:" not in reply
    assert "Final answer" in reply
    assert emit_mock.await_count >= 1


@pytest.mark.asyncio
async def test_reasoning_mode_off_never_leaks_think_only_reply():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-off-think-only"
    await db.set_user_reasoning_mode(user_id, "off")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="<think>internal only</think>"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hello",
            provider_name="openai",
        )

    assert "<think>" not in reply.lower()
    assert "internal only" not in reply.lower()
    assert "I didn't get a reply back." in reply


@pytest.mark.asyncio
async def test_reasoning_mode_stream_never_leaks_think_only_reply():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-stream-think-only"
    await db.set_user_reasoning_mode(user_id, "stream")

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="<think>internal only</think>"), primary

    emit_mock = AsyncMock()
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.handler._emit_stream_status", emit_mock),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hello",
            provider_name="openai",
        )

    assert "<think>" not in reply.lower()
    assert "internal only" not in reply.lower()
    assert "I didn't get a reply back." in reply
    assert emit_mock.await_count >= 1


@pytest.mark.asyncio
async def test_set_thinking_invalid_value_returns_http_400():
    with pytest.raises(HTTPException) as exc:
        await set_thinking(ThinkingIn(thinking_level="invalid"), user_id="default")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_reasoning_invalid_value_returns_http_400():
    with pytest.raises(HTTPException) as exc:
        await set_reasoning(ReasoningIn(reasoning_mode="invalid"), user_id="default")
    assert exc.value.status_code == 400
