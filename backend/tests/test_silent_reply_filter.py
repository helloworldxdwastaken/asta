from unittest.mock import patch

import pytest

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


@pytest.mark.asyncio
async def test_no_reply_token_is_suppressed_and_not_persisted():
    db = get_db()
    await db.connect()
    user_id = "test-no-reply-token"

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="NO_REPLY"), primary

    class _TraceOff:
        asta_show_tool_trace = False

        @property
        def tool_trace_channels(self):
            return set()

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.handler._get_trace_settings", return_value=_TraceOff()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="Run silent operation",
            provider_name="openai",
        )

    assert reply == ""
    cid = await db.get_or_create_conversation(user_id, "web")
    rows = await db.get_recent_messages(cid, limit=20)
    assistant_rows = [r for r in rows if (r.get("role") or "") == "assistant"]
    assert assistant_rows == []


@pytest.mark.asyncio
async def test_trailing_no_reply_token_is_stripped_from_visible_text():
    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="Done.\nNO_REPLY"), primary

    class _TraceOff:
        asta_show_tool_trace = False

        @property
        def tool_trace_channels(self):
            return set()

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.handler._get_trace_settings", return_value=_TraceOff()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id="test-no-reply-trailing",
            channel="web",
            text="do it",
            provider_name="openai",
        )

    assert reply == "Done."
