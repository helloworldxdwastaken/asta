from datetime import datetime, timedelta, timezone

import pytest

from app.db import (
    ONE_SHOT_REMINDER_ID_OFFSET,
    decode_one_shot_reminder_id,
    get_db,
)


async def _cleanup_user_scheduler_data(db, user_id: str) -> None:
    for row in await db.get_notifications(user_id, limit=200):
        if (row.get("status") or "").lower() == "pending":
            await db.delete_reminder(int(row["id"]), user_id)
    for job in await db.get_cron_jobs(user_id):
        await db.delete_cron_job(int(job["id"]))


@pytest.mark.asyncio
async def test_one_shot_reminder_is_stored_in_cron_but_listed_in_notifications():
    db = get_db()
    await db.connect()
    user_id = "test-reminder-cron-one-shot"
    await _cleanup_user_scheduler_data(db, user_id)

    run_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_id = await db.add_reminder(user_id, "web", "", "drink water", run_at)

    assert reminder_id >= ONE_SHOT_REMINDER_ID_OFFSET
    assert decode_one_shot_reminder_id(reminder_id) is not None

    notifications = await db.get_notifications(user_id, limit=50)
    pending = [r for r in notifications if (r.get("status") or "").lower() == "pending"]
    assert any(int(r["id"]) == reminder_id for r in pending)

    # Recurring cron list should not include one-shot reminders.
    assert await db.get_cron_jobs(user_id) == []

    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_mark_one_shot_reminder_sent_moves_history_and_removes_pending_cron():
    db = get_db()
    await db.connect()
    user_id = "test-reminder-cron-mark-sent"
    await _cleanup_user_scheduler_data(db, user_id)

    run_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_id = await db.add_reminder(user_id, "web", "", "stretch", run_at)
    await db.mark_reminder_sent(reminder_id)

    notifications = await db.get_notifications(user_id, limit=50)
    pending = [r for r in notifications if (r.get("status") or "").lower() == "pending"]
    sent = [r for r in notifications if (r.get("status") or "").lower() == "sent"]

    assert pending == []
    assert any((r.get("message") or "").lower() == "stretch" for r in sent)

    await _cleanup_user_scheduler_data(db, user_id)


@pytest.mark.asyncio
async def test_legacy_pending_reminders_are_migrated_to_one_shot_cron():
    db = get_db()
    await db.connect()
    user_id = "test-reminder-cron-migration"
    await _cleanup_user_scheduler_data(db, user_id)

    assert db._conn is not None
    await db._conn.execute(
        """INSERT INTO reminders (user_id, channel, channel_target, message, run_at, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))""",
        (
            user_id,
            "web",
            "",
            "legacy pending reminder",
            (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    await db._conn.commit()

    moved = await db.migrate_legacy_pending_reminders_to_one_shot()
    assert moved >= 1

    pending = await db.get_pending_reminders_for_user(user_id, limit=20)
    assert any("legacy pending reminder" in (r.get("message") or "") for r in pending)

    cursor = await db._conn.execute(
        "SELECT COUNT(*) as cnt FROM reminders WHERE user_id = ? AND status = 'pending'",
        (user_id,),
    )
    row = await cursor.fetchone()
    assert int(row["cnt"]) == 0

    await _cleanup_user_scheduler_data(db, user_id)
