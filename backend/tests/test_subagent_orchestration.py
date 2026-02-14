from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from app.db import get_db
from app.subagent_orchestrator import (
    recover_subagent_runs_on_startup,
    run_subagent_tool,
    spawn_subagent_run,
    wait_subagent_run,
)


@pytest.mark.asyncio
async def test_subagent_spawn_completes_and_announces(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    async def _fake_turn(*, user_id: str, child_conversation_id: str, task: str, provider_name: str) -> str:
        return f"done: {task}"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _fake_turn)

    accepted = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="check logs",
        label="logs",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
    )
    assert accepted["status"] == "accepted"
    run_id = accepted["runId"]
    assert await wait_subagent_run(run_id, timeout_seconds=2.0) is True

    row = await db.get_subagent_run(run_id)
    assert row is not None
    assert (row.get("status") or "").lower() == "completed"
    assert "done: check logs" in (row.get("result_text") or "")

    messages = await db.get_recent_messages(cid, limit=20)
    assert any("Subagent" in (m.get("content") or "") for m in messages)
    assert any("done: check logs" in (m.get("content") or "") for m in messages)


@pytest.mark.asyncio
async def test_sessions_list_and_history_tools():
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-tools-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    child_cid = f"{cid}:subagent:manual"

    await db.add_message(child_cid, "assistant", "child output")
    await db.add_subagent_run(
        run_id=f"sub_manual_{uuid.uuid4().hex[:6]}",
        user_id=user_id,
        parent_conversation_id=cid,
        child_conversation_id=child_cid,
        task="manual task",
        label="manual",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
        status="completed",
    )
    rows = await db.list_subagent_runs(cid, limit=5)
    run_id = rows[0]["run_id"]

    listed_raw = await run_subagent_tool(
        tool_name="sessions_list",
        params={"limit": 5},
        user_id=user_id,
        parent_conversation_id=cid,
        provider_name="openai",
        channel="web",
        channel_target="web",
    )
    listed = json.loads(listed_raw)
    assert listed["count"] >= 1
    assert any(r.get("runId") == run_id for r in listed["runs"])

    history_raw = await run_subagent_tool(
        tool_name="sessions_history",
        params={"runId": run_id, "limit": 10},
        user_id=user_id,
        parent_conversation_id=cid,
        provider_name="openai",
        channel="web",
        channel_target="web",
    )
    history = json.loads(history_raw)
    assert history.get("runId") == run_id
    assert any((m.get("content") or "") == "child output" for m in history.get("messages", []))


@pytest.mark.asyncio
async def test_sessions_stop_cancels_running_subagent(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-stop-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    async def _slow_turn(*, user_id: str, child_conversation_id: str, task: str, provider_name: str) -> str:
        await asyncio.sleep(10)
        return "late"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _slow_turn)

    accepted = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="long task",
        label="long",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
    )
    run_id = accepted["runId"]

    stop_raw = await run_subagent_tool(
        tool_name="sessions_stop",
        params={"runId": run_id},
        user_id=user_id,
        parent_conversation_id=cid,
        provider_name="openai",
        channel="web",
        channel_target="web",
    )
    stop_payload = json.loads(stop_raw)
    assert stop_payload["runId"] == run_id

    assert await wait_subagent_run(run_id, timeout_seconds=2.0) is True
    row = await db.get_subagent_run(run_id)
    assert row is not None
    assert (row.get("status") or "").lower() in {"stopped", "interrupted", "already-ended", "completed"}


@pytest.mark.asyncio
async def test_recovery_marks_running_subagents_interrupted():
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-recover-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    run_id = f"sub_recover_{uuid.uuid4().hex[:8]}"
    child_cid = f"{cid}:subagent:recover"
    await db.add_subagent_run(
        run_id=run_id,
        user_id=user_id,
        parent_conversation_id=cid,
        child_conversation_id=child_cid,
        task="recover me",
        label="recover",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
        status="running",
    )
    fixed = await recover_subagent_runs_on_startup()
    assert fixed >= 1
    row = await db.get_subagent_run(run_id)
    assert row is not None
    assert (row.get("status") or "").lower() == "interrupted"
