from unittest.mock import patch

import pytest

from app.handler import handle_message
from app.providers.base import ProviderResponse
from app.db import get_db


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None, **kwargs):
    return messages


@pytest.mark.asyncio
async def test_bracket_cron_protocol_is_executed_and_not_leaked():
    db = get_db()
    await db.connect()
    user_id = "test-bracket-cron-protocol"

    for job in await db.get_cron_jobs(user_id):
        await db.delete_cron_job(int(job["id"]))

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(
            content=(
                "I'll set that up.\n\n"
                '[cron: action=add, name="Wake up for work", cron_expr=30 7 * * 0-4, '
                'message="Time to get up for work", tz=Asia/Jerusalem]'
            )
        ), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="Make a reminder every day at 7:30 except Friday and Saturday",
            provider_name="openai",
        )

    assert "[cron:" not in reply.lower()
    assert "cron (add)" in reply.lower() or "scheduled cron job" in reply.lower()

    jobs = await db.get_cron_jobs(user_id)
    assert len(jobs) == 1
    assert (jobs[0].get("name") or "") == "Wake up for work"
    assert (jobs[0].get("cron_expr") or "") == "30 7 * * 0-4"

    for job in jobs:
        await db.delete_cron_job(int(job["id"]))


@pytest.mark.asyncio
async def test_shell_command_line_is_not_leaked_when_not_requested():
    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(
            content=(
                "You're on the latest local build.\n"
                "cd asta && git describe --tags --always 2>/dev/null || echo no git tags"
            )
        ), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id="test-shell-leak-filter",
            channel="web",
            text="what version of asta is this?",
            provider_name="openai",
        )

    low = reply.lower()
    assert "git describe" not in low
    assert "/dev/null" not in low
    assert "latest local build" in low

