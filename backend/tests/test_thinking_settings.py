from unittest.mock import patch, AsyncMock

import pytest
import uuid
from fastapi import HTTPException

from app.db import get_db
from app.handler import _extract_reasoning_blocks, handle_message
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
    await db.set_user_thinking_level(user_id, "minimal")
    level3 = await db.get_user_thinking_level(user_id)
    assert level3 == "minimal"
    await db.set_user_thinking_level(user_id, "xhigh")
    level4 = await db.get_user_thinking_level(user_id)
    assert level4 == "xhigh"

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

    async def _fake_chat_with_fallback_stream(primary, messages, fallback_names, on_text_delta=None, **kwargs):
        return ProviderResponse(content="<think>Checked file tool output.</think>\nFinal answer"), primary

    emit_mock = AsyncMock()
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback_stream", side_effect=_fake_chat_with_fallback_stream),
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

    async def _fake_chat_with_fallback_stream(primary, messages, fallback_names, on_text_delta=None, **kwargs):
        return ProviderResponse(content="<think>internal only</think>"), primary

    emit_mock = AsyncMock()
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback_stream", side_effect=_fake_chat_with_fallback_stream),
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


def test_extract_reasoning_blocks_keeps_tags_in_inline_code():
    final_text, reasoning = _extract_reasoning_blocks(
        "Use `<thinking>literal</thinking>` and <think>internal note</think> final answer."
    )

    assert "`<thinking>literal</thinking>`" in final_text
    assert "<think>" not in final_text.lower()
    assert reasoning == "internal note"


def test_extract_reasoning_blocks_keeps_tags_in_fenced_code():
    final_text, reasoning = _extract_reasoning_blocks(
        "```txt\n<thinking>code sample</thinking>\n```\n<think>hidden</think>\nDone."
    )

    assert "<thinking>code sample</thinking>" in final_text
    assert "Done." in final_text
    assert reasoning == "hidden"


def test_extract_reasoning_blocks_supports_thought_and_antthinking_tags():
    final_text, reasoning = _extract_reasoning_blocks(
        "<thought>first</thought> output <antthinking>second</antthinking> done"
    )

    assert final_text == "output  done"
    assert reasoning == "first\n\nsecond"


def test_extract_reasoning_blocks_strips_final_tags_outside_code_only():
    final_text, reasoning = _extract_reasoning_blocks(
        "<final>Final answer</final> and `<final>literal</final>`"
    )

    assert final_text == "Final answer and `<final>literal</final>`"
    assert reasoning == ""


def test_extract_reasoning_blocks_unclosed_think_stays_hidden_from_final():
    final_text, reasoning = _extract_reasoning_blocks(
        "Visible start <thinking>internal unfinished section"
    )

    assert final_text == "Visible start"
    assert "internal unfinished section" in reasoning


@pytest.mark.asyncio
async def test_set_thinking_invalid_value_returns_http_400():
    with pytest.raises(HTTPException) as exc:
        await set_thinking(ThinkingIn(thinking_level="invalid"), user_id="default")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_thinking_accepts_xhigh():
    out = await set_thinking(ThinkingIn(thinking_level="xhigh"), user_id="default")
    assert out["thinking_level"] == "xhigh"


@pytest.mark.asyncio
async def test_set_reasoning_invalid_value_returns_http_400():
    with pytest.raises(HTTPException) as exc:
        await set_reasoning(ReasoningIn(reasoning_mode="invalid"), user_id="default")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_inline_think_directive_sets_level_only():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-only"
    await db.set_user_thinking_level(user_id, "off")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/thinking high",
            provider_name="openai",
        )

    assert "Thinking level set to high." in reply
    assert await db.get_user_thinking_level(user_id) == "high"


@pytest.mark.asyncio
async def test_inline_think_directive_sets_level_and_continues():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-continue"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"thinking_level": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/t minimal say hello",
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["thinking_level"] == "minimal"
    assert observed["last_user"] == "say hello"


@pytest.mark.asyncio
async def test_inline_think_directive_mixed_text_sets_level_and_continues():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-mixed"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"thinking_level": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="please /think:high run diagnostics",
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["thinking_level"] == "high"
    assert observed["last_user"] == "please run diagnostics"
    assert await db.get_user_thinking_level(user_id) == "high"


@pytest.mark.asyncio
async def test_inline_think_directive_normalizes_on_to_low():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-on"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"thinking_level": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/thinking on say hello",
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["thinking_level"] == "low"
    assert observed["last_user"] == "say hello"
    assert await db.get_user_thinking_level(user_id) == "low"


@pytest.mark.asyncio
async def test_inline_think_directive_without_argument_shows_current_and_options():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-options"
    await db.set_user_thinking_level(user_id, "medium")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/think:",
            provider_name="openai",
        )

    assert "Current thinking level: medium." in reply
    assert "Options: off, minimal, low, medium, high." in reply


@pytest.mark.asyncio
async def test_inline_think_directive_does_not_match_thinkstuff():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-thinkstuff"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"thinking_level": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/thinkstuff",
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["thinking_level"] == "off"
    assert observed["last_user"] == "/thinkstuff"
    assert await db.get_user_thinking_level(user_id) == "off"


@pytest.mark.asyncio
async def test_inline_think_directive_does_not_match_url_path():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-url"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"thinking_level": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["thinking_level"] = kwargs.get("thinking_level")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    message = "see https://example.com/path/thinkstuff"
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text=message,
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["thinking_level"] == "off"
    assert observed["last_user"] == message
    assert await db.get_user_thinking_level(user_id) == "off"


@pytest.mark.asyncio
async def test_inline_reasoning_directive_sets_mode_only():
    db = get_db()
    await db.connect()
    user_id = "test-inline-reasoning-only"
    await db.set_user_reasoning_mode(user_id, "off")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/reasoning stream",
            provider_name="openai",
        )

    assert "Reasoning mode set to stream." in reply
    assert await db.get_user_reasoning_mode(user_id) == "stream"


@pytest.mark.asyncio
async def test_inline_reasoning_directive_sets_mode_and_continues():
    db = get_db()
    await db.connect()
    user_id = "test-inline-reasoning-continue"
    await db.set_user_reasoning_mode(user_id, "off")

    observed = {"reasoning_mode": None, "last_user": ""}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["reasoning_mode"] = kwargs.get("reasoning_mode")
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if users:
            observed["last_user"] = str(users[-1].get("content") or "")
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="please /reasoning:on run checks",
            provider_name="openai",
        )

    assert reply.startswith("ok")
    assert observed["reasoning_mode"] == "on"
    assert observed["last_user"] == "please run checks"
    assert await db.get_user_reasoning_mode(user_id) == "on"


@pytest.mark.asyncio
async def test_inline_reasoning_directive_without_argument_shows_current_and_options():
    db = get_db()
    await db.connect()
    user_id = "test-inline-reasoning-options"
    await db.set_user_reasoning_mode(user_id, "on")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/reasoning:",
            provider_name="openai",
        )

    assert "Current reasoning mode: on." in reply
    assert "Options: off, on, stream." in reply


@pytest.mark.asyncio
async def test_inline_reasoning_directive_rejects_invalid_mode():
    db = get_db()
    await db.connect()
    user_id = "test-inline-reasoning-invalid"
    await db.set_user_reasoning_mode(user_id, "off")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/reasoning maybe",
            provider_name="openai",
        )

    assert 'Unrecognized reasoning mode "maybe".' in reply
    assert await db.get_user_reasoning_mode(user_id) == "off"


@pytest.mark.asyncio
async def test_inline_directive_does_not_send_raw_and_cleaned_user_message():
    db = get_db()
    await db.connect()
    user_id = f"test-inline-no-raw-dup-{uuid.uuid4().hex[:8]}"
    await db.set_user_thinking_level(user_id, "off")

    observed = {"users": []}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        observed["users"] = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        return ProviderResponse(content="ok"), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        await handle_message(
            user_id=user_id,
            channel="web",
            text="/think high hello",
            provider_name="openai",
        )

    assert len(observed["users"]) == 1
    assert observed["users"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_inline_think_xhigh_rejected_for_unsupported_model():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-xhigh-unsupported"
    await db.set_user_default_ai(user_id, "openai")
    await db.set_user_provider_model(user_id, "openai", "gpt-4o-mini")
    await db.set_user_thinking_level(user_id, "off")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/thinking xhigh",
            provider_name="default",
        )

    assert "xhigh" in reply.lower()
    assert "not supported" in reply.lower()
    assert await db.get_user_thinking_level(user_id) == "off"


@pytest.mark.asyncio
async def test_inline_think_xhigh_allowed_for_supported_model():
    db = get_db()
    await db.connect()
    user_id = "test-inline-think-xhigh-supported"
    await db.set_user_default_ai(user_id, "openai")
    await db.set_user_provider_model(user_id, "openai", "gpt-5.2")
    await db.set_user_thinking_level(user_id, "off")

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="/thinking xhigh",
            provider_name="default",
        )

    assert "Thinking level set to xhigh." in reply
    assert await db.get_user_thinking_level(user_id) == "xhigh"


@pytest.mark.asyncio
async def test_reasoning_mode_stream_emits_incremental_status_updates():
    db = get_db()
    await db.connect()
    user_id = "test-reasoning-stream-incremental"
    await db.set_user_reasoning_mode(user_id, "stream")

    async def _fake_chat_with_fallback_stream(primary, messages, fallback_names, on_text_delta=None, **kwargs):
        if on_text_delta:
            await on_text_delta("<think>step one\n")
            await on_text_delta("step two\n")
            await on_text_delta("step three</think>\nFinal answer")
        return ProviderResponse(content="<think>step one\nstep two\nstep three</think>\nFinal answer"), primary

    emit_mock = AsyncMock()
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback_stream", side_effect=_fake_chat_with_fallback_stream),
        patch("app.handler._emit_stream_status", emit_mock),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="hello",
            provider_name="openai",
        )

    assert "Final answer" in reply
    reasoning_calls = [
        call for call in emit_mock.await_args_list
        if str(call.kwargs.get("text") or "").startswith("Reasoning:\n")
    ]
    assert len(reasoning_calls) == 3
    first_text = reasoning_calls[0].kwargs.get("text") or ""
    last_text = reasoning_calls[-1].kwargs.get("text") or ""
    assert "step one" in first_text
    assert "step three" in last_text
