import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.cron_tool import parse_cron_tool_args, run_cron_tool
from app.db import get_db


async def _cleanup_cron_user(db, user_id: str) -> None:
    jobs = await db.get_cron_jobs(user_id)
    for row in jobs:
        await db.delete_cron_job(int(row["id"]))
    if db._conn is not None:
        await db._conn.execute("DELETE FROM cron_job_runs WHERE user_id = ?", (user_id,))
        await db._conn.commit()


def test_parse_cron_tool_args_recovers_flattened_add():
    raw = json.dumps(
        {
            "action": "add",
            "name": "Wake up reminder",
            "cron_expr": "30 7 * * 1,2,3,4,5",
            "message": "wake up",
            "tz": "America/Los_Angeles",
        }
    )
    parsed = parse_cron_tool_args(raw)
    assert parsed["action"] == "add"
    assert parsed["name"] == "Wake up reminder"
    assert parsed["cron_expr"] == "30 7 * * 1,2,3,4,5"
    assert parsed["message"] == "wake up"
    assert parsed["tz"] == "America/Los_Angeles"


def test_parse_cron_tool_args_recovers_nested_job_add_shape():
    parsed = parse_cron_tool_args(
        {
            "action": "add",
            "job": {
                "name": "Daily update",
                "schedule": {"kind": "cron", "expr": "0 4 * * *", "tz": "UTC"},
                "payload": {"kind": "systemEvent", "text": "run updates"},
            },
        }
    )
    assert parsed["action"] == "add"
    assert parsed["name"] == "Daily update"
    assert parsed["cron_expr"] == "0 4 * * *"
    assert parsed["tz"] == "UTC"
    assert parsed["message"] == "run updates"


@pytest.mark.asyncio
async def test_cron_run_action_force_uses_manual_runner(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = "test-cron-run-force"
    await _cleanup_cron_user(db, user_id)
    job_id = await db.add_cron_job(
        user_id,
        "Daily update",
        "0 4 * * *",
        "run updates",
        channel="web",
        channel_target="",
    )

    async def _fake_manual_run(target_job_id: int, *, run_mode: str = "force"):
        return {
            "ok": True,
            "id": int(target_job_id),
            "status": "ok",
            "trigger": "manual",
            "run_mode": run_mode,
            "output": "done",
        }

    monkeypatch.setattr("app.cron_tool.run_cron_job_now", _fake_manual_run)
    out = await run_cron_tool(
        {"action": "run", "id": job_id, "runMode": "force"},
        user_id=user_id,
        channel="web",
        channel_target="web",
        db=db,
    )
    payload = json.loads(out)
    assert payload["ok"] is True
    assert int(payload["id"]) == int(job_id)
    assert payload["status"] == "ok"
    assert payload["run_mode"] == "force"
    await _cleanup_cron_user(db, user_id)


@pytest.mark.asyncio
async def test_cron_run_action_due_skips_when_not_due(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = "test-cron-run-due-skip"
    await _cleanup_cron_user(db, user_id)
    job_id = await db.add_cron_job(
        user_id,
        "Weekday wake",
        "30 7 * * 1,2,3,4,5",
        "wake up",
        channel="web",
        channel_target="",
    )

    class _FakeScheduler:
        running = True

        def get_jobs(self):
            return []

        def get_job(self, _job_id: str):
            return SimpleNamespace(next_run_time=datetime.now(timezone.utc) + timedelta(hours=2))

    monkeypatch.setattr("app.cron_tool.get_scheduler", lambda: _FakeScheduler())
    out = await run_cron_tool(
        {"action": "run", "id": job_id, "runMode": "due"},
        user_id=user_id,
        channel="web",
        channel_target="web",
        db=db,
    )
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["status"] == "skipped_not_due"
    runs = await db.get_cron_job_runs(user_id=user_id, cron_job_id=job_id, limit=5)
    assert runs and runs[0]["status"] == "skipped_not_due"
    await _cleanup_cron_user(db, user_id)


@pytest.mark.asyncio
async def test_cron_runs_action_returns_persisted_run_history():
    db = get_db()
    await db.connect()
    user_id = "test-cron-runs-history"
    await _cleanup_cron_user(db, user_id)
    job_id = await db.add_cron_job(
        user_id,
        "History job",
        "0 9 * * *",
        "history",
        channel="web",
        channel_target="",
    )
    await db.add_cron_job_run(
        cron_job_id=job_id,
        user_id=user_id,
        trigger="schedule",
        run_mode="due",
        status="ok",
        output="first",
    )
    await db.add_cron_job_run(
        cron_job_id=job_id,
        user_id=user_id,
        trigger="manual",
        run_mode="force",
        status="error",
        error="boom",
    )

    out = await run_cron_tool(
        {"action": "runs", "id": job_id, "limit": 10},
        user_id=user_id,
        channel="web",
        channel_target="web",
        db=db,
    )
    payload = json.loads(out)
    assert int(payload["job_id"]) == int(job_id)
    assert len(payload["runs"]) == 2
    assert payload["runs"][0]["status"] in ("error", "ok")
    await _cleanup_cron_user(db, user_id)


@pytest.mark.asyncio
async def test_cron_wake_action_now_reloads_scheduler(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = "test-cron-wake-now"
    await _cleanup_cron_user(db, user_id)
    reload_called = {"ok": False}

    async def _fake_reload():
        reload_called["ok"] = True

    class _FakeScheduler:
        running = True

        def get_jobs(self):
            return [SimpleNamespace(id="cron_1"), SimpleNamespace(id="other_1"), SimpleNamespace(id="cron_2")]

        def get_job(self, _job_id: str):
            return None

    monkeypatch.setattr("app.cron_tool.reload_cron_jobs", _fake_reload)
    monkeypatch.setattr("app.cron_tool.get_scheduler", lambda: _FakeScheduler())
    out = await run_cron_tool(
        {"action": "wake", "mode": "now", "text": "wake scheduler"},
        user_id=user_id,
        channel="web",
        channel_target="web",
        db=db,
    )
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["mode"] == "now"
    assert payload["scheduled_cron_jobs"] == 2
    assert reload_called["ok"] is True
