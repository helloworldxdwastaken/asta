from unittest.mock import patch

import pytest

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


@pytest.mark.asyncio
async def test_reminder_tool_skip_fallback_still_schedules():
    db = get_db()
    await db.connect()
    user_id = "test-reminder-tool-skip-fallback"
    await db.set_skill_enabled(user_id, "reminders", True)

    async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
        return messages

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        # Simulate a tool-capable provider that returned text but skipped tool calls.
        return ProviderResponse(content="Sure, reminder set."), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="remind me in 5 min to stretch",
            provider_name="openai",
        )

    assert "Done. I set your reminder" in reply
    pending = await db.get_pending_reminders_for_user(user_id, limit=20)
    assert any("stretch" in (r.get("message") or "").lower() for r in pending)

    for r in await db.get_notifications(user_id, limit=100):
        if (r.get("status") or "").lower() == "pending":
            await db.delete_reminder(int(r["id"]), user_id)
