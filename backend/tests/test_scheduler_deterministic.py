import pytest
from unittest.mock import patch

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
    # Simulate tool-capable provider that skipped tool calls and hallucinated text.
    return ProviderResponse(content="No scheduled items found."), primary


async def _fake_chat_with_fallback_tool_call(primary, messages, fallback_names, **kwargs):
    return ProviderResponse(
        content="",
        tool_calls=[
            {
                "id": "tc_1",
                "type": "function",
                "function": {
                    "name": "cron",
                    "arguments": "{\"action\":\"list\"}",
                },
            }
        ],
    ), primary


async def _cleanup_user_scheduler_data(db, user_id: str) -> None:
    for row in await db.get_notifications(user_id, limit=200):
        if (row.get("status") or "").lower() == "pending":
            await db.delete_reminder(int(row["id"]), user_id)
    for job in await db.get_cron_jobs(user_id):
        await db.delete_cron_job(int(job["id"]))


@pytest.mark.asyncio
async def test_cron_list_is_deterministic_from_db():
    db = get_db()
    await db.connect()
    user_id = "test-cron-list-deterministic"
    await _cleanup_user_scheduler_data(db, user_id)

    await db.add_cron_job(
        user_id,
        "Daily Auto-Update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )
    await db.add_cron_job(
        user_id,
        "Work Wake-Up",
        "30 7 * * 1,2,3,4,5",
        "wake up",
        channel="telegram",
        channel_target="6168747695",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="What cron jobs I have?",
            provider_name="openai",
        )

    assert "You have 2 cron job(s):" in reply
    assert "Daily Auto-Update" in reply
    assert "Work Wake-Up" in reply

    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_pending_tasks_phrase_triggers_schedule_overview_fallback():
    db = get_db()
    await db.connect()
    user_id = "test-pending-tasks-overview"
    await _cleanup_user_scheduler_data(db, user_id)
    await db.set_skill_enabled(user_id, "reminders", True)

    reminder_id = await db.add_reminder(
        user_id,
        "web",
        "",
        "drink water",
        "2099-01-01T09:00:00Z",
    )
    await db.add_cron_job(
        user_id,
        "Daily Auto-Update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="Do I have any pending tasks?",
            provider_name="openai",
        )

    assert "pending reminder" in reply.lower()
    assert f"[id {reminder_id}]" in reply
    assert "cron job(s)" in reply
    assert "didn't get a reply back" not in reply.lower()

    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_plain_remove_after_reminder_context_removes_pending_reminder():
    db = get_db()
    await db.connect()
    user_id = "test-remove-reminder-context"
    await _cleanup_user_scheduler_data(db, user_id)
    await db.set_skill_enabled(user_id, "reminders", True)

    reminder_id = await db.add_reminder(
        user_id,
        "telegram",
        "6168747695",
        "drink water",
        "2099-01-01T09:00:00Z",
    )
    await db.add_cron_job(
        user_id,
        "Daily Auto-Update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        list_reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="Do I have any tast or reminders ?",
            provider_name="openai",
        )
    assert f"[id {reminder_id}]" in list_reply
    assert "cron job(s)" in list_reply

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        remove_reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="Can you delete this of drink water 9am",
            provider_name="openai",
        )
    assert f"Removed reminder #{reminder_id}." in remove_reply
    pending = await db.get_pending_reminders_for_user(user_id, limit=20)
    assert pending == []
    cron_jobs = await db.get_cron_jobs(user_id)
    assert len(cron_jobs) == 1
    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_update_cron_name_fallback_is_deterministic():
    db = get_db()
    await db.connect()
    user_id = "test-update-cron-name-fallback"
    await _cleanup_user_scheduler_data(db, user_id)

    cron_id = await db.add_cron_job(
        user_id,
        "daily water reminder",
        "30 7 * * 1,2,3,4,5",
        "drink water",
        channel="telegram",
        channel_target="6168747695",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="can u esit the daily water reminder ? should be called Wake up reminder",
            provider_name="openai",
        )

    assert f"Updated cron job #{cron_id}." in reply
    cron_rows = await db.get_cron_jobs(user_id)
    assert any((r.get("name") or "") == "Wake up reminder" for r in cron_rows)
    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_update_reminder_fallback_updates_pending_reminder():
    db = get_db()
    await db.connect()
    user_id = "test-update-reminder-fallback"
    await _cleanup_user_scheduler_data(db, user_id)
    await db.set_skill_enabled(user_id, "reminders", True)

    reminder_id = await db.add_reminder(
        user_id,
        "web",
        "",
        "drink water",
        "2099-01-01T09:00:00Z",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text=f"edit reminder {reminder_id} to remind me in 10 min to stretch",
            provider_name="openai",
        )

    assert f"Updated reminder #{reminder_id}" in reply
    pending = await db.get_pending_reminders_for_user(user_id, limit=20)
    row = next((r for r in pending if int(r.get("id") or 0) == int(reminder_id)), None)
    assert row is not None
    assert "stretch" in (row.get("message") or "").lower()
    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_tool_trace_shows_friendly_tool_names_when_enabled(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = "test-tool-trace-friendly"
    await _cleanup_user_scheduler_data(db, user_id)

    await db.add_cron_job(
        user_id,
        "Daily Auto-Update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )

    class _TraceSettings:
        asta_show_tool_trace = True

        @property
        def tool_trace_channels(self):
            return {"web", "telegram"}

    monkeypatch.setattr("app.handler._get_trace_settings", lambda: _TraceSettings())

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback_tool_call),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="what cron jobs do I have?",
            provider_name="openai",
        )

    assert "Tools used: Cron (list)" in reply
    await _cleanup_user_scheduler_data(db, user_id)
    await db.set_skill_enabled(user_id, "reminders", True)

    reminder_id = await db.add_reminder(
        user_id,
        "telegram",
        "6168747695",
        "drink water",
        "2099-01-01T09:00:00Z",
    )
    await db.add_cron_job(
        user_id,
        "Daily Auto-Update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )
    await db.add_cron_job(
        user_id,
        "Work Wake-Up",
        "30 7 * * 1,2,3,4,5",
        "wake up",
        channel="telegram",
        channel_target="6168747695",
    )

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        list_reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="Hey dude what reminders I have set?",
            provider_name="openai",
        )
    assert f"[id {reminder_id}]" in list_reply

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        remove_reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="Remove",
            provider_name="openai",
        )
    assert f"Removed reminder #{reminder_id}." in remove_reply

    pending = await db.get_pending_reminders_for_user(user_id, limit=20)
    assert pending == []

    cron_jobs = await db.get_cron_jobs(user_id)
    assert len(cron_jobs) == 2

    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_tool_trace_footer_is_suppressed_on_telegram_even_when_enabled(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = "test-tool-trace-telegram-suppressed"
    await _cleanup_user_scheduler_data(db, user_id)
    await db.set_skill_enabled(user_id, "reminders", True)

    class _TraceSettings:
        asta_show_tool_trace = True

        @property
        def tool_trace_channels(self):
            return {"web", "telegram"}

    monkeypatch.setattr("app.handler._get_trace_settings", lambda: _TraceSettings())

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="telegram",
            channel_target="6168747695",
            text="what reminders do I have?",
            provider_name="openai",
        )

    assert "Tools used:" not in reply
