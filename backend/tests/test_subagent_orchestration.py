from __future__ import annotations

import asyncio
import json
import re
import uuid
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from app.db import get_db
from app.handler import handle_message
from app.providers.base import ProviderResponse
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

    async def _fake_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
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

    async def _slow_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
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


@pytest.mark.asyncio
async def test_sessions_spawn_respects_max_concurrency(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-cap-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    async def _slow_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
        await asyncio.sleep(2.0)
        return "ok"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _slow_turn)
    monkeypatch.setattr(
        "app.subagent_orchestrator.get_settings",
        lambda: SimpleNamespace(asta_subagents_max_concurrent=1, asta_subagents_archive_after_minutes=60),
    )

    first = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="one",
        label="one",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
    )
    assert first["status"] == "accepted"

    second = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="two",
        label="two",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
    )
    assert second["status"] == "busy"
    assert second["maxConcurrent"] == 1

    await wait_subagent_run(first["runId"], timeout_seconds=4.0)


@pytest.mark.asyncio
async def test_sessions_spawn_passes_model_and_thinking_overrides(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-overrides-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    observed: dict[str, str | None] = {"model": None, "thinking": None}

    async def _fake_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
        observed["model"] = model_override
        observed["thinking"] = thinking_override
        return "ok"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _fake_turn)

    accepted = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="check",
        label="check",
        provider_name="openai",
        channel="web",
        channel_target="web",
        model_override="gpt-4.1-mini",
        thinking_override="low",
        cleanup="keep",
    )
    assert accepted["status"] == "accepted"
    await wait_subagent_run(accepted["runId"], timeout_seconds=2.0)
    assert observed["model"] == "gpt-4.1-mini"
    assert observed["thinking"] == "low"

    row = await db.get_subagent_run(accepted["runId"])
    assert row is not None
    assert (row.get("model_override") or "") == "gpt-4.1-mini"
    assert (row.get("thinking_override") or "") == "low"


@pytest.mark.asyncio
async def test_subagent_auto_archive_removes_child_conversation(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-archive-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")
    monkeypatch.setenv("ASTA_SUBAGENTS_ARCHIVE_AFTER_SECONDS", "1")

    async def _fake_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
        # Ensure child conversation exists so archive has something to delete.
        await db.add_message(child_conversation_id, "assistant", f"child:{task}")
        return "done"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _fake_turn)

    accepted = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=cid,
        task="archive me",
        label="archive",
        provider_name="openai",
        channel="web",
        channel_target="web",
        cleanup="keep",
    )
    assert accepted["status"] == "accepted"
    run_id = accepted["runId"]
    child_key = accepted["childSessionKey"]
    await wait_subagent_run(run_id, timeout_seconds=2.0)
    await asyncio.sleep(1.4)

    child_messages = await db.get_recent_messages(child_key, limit=5)
    assert child_messages == []
    row = await db.get_subagent_run(run_id)
    assert row is not None
    assert row.get("archived_at")


@pytest.mark.asyncio
async def test_subagents_slash_help_and_list_are_deterministic():
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-slash-help-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    help_reply = await handle_message(
        user_id=user_id,
        channel="web",
        text="/subagents",
        provider_name="openai",
        conversation_id=cid,
    )
    assert "Subagents commands:" in help_reply

    list_reply = await handle_message(
        user_id=user_id,
        channel="web",
        text="/subagents list",
        provider_name="openai",
        conversation_id=cid,
    )
    assert "No subagent runs yet" in list_reply


@pytest.mark.asyncio
async def test_subagents_slash_spawn_list_and_stop(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-slash-spawn-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    async def _fake_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
        await db.add_message(child_conversation_id, "assistant", f"done: {task}")
        return f"done: {task}"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _fake_turn)

    spawn_reply = await handle_message(
        user_id=user_id,
        channel="web",
        text="/subagents spawn check desktop files",
        provider_name="openai",
        conversation_id=cid,
    )
    m = re.search(r"Spawned subagent \[([^\]]+)\]", spawn_reply)
    assert m is not None
    run_id = m.group(1).strip()
    assert run_id

    assert await wait_subagent_run(run_id, timeout_seconds=2.0) is True

    list_reply = await handle_message(
        user_id=user_id,
        channel="web",
        text="/subagents list",
        provider_name="openai",
        conversation_id=cid,
    )
    assert run_id in list_reply

    stop_reply = await handle_message(
        user_id=user_id,
        channel="web",
        text=f"/subagents stop {run_id}",
        provider_name="openai",
        conversation_id=cid,
    )
    assert "Subagent" in stop_reply
    assert "stopped" in stop_reply or "already-ended" in stop_reply


@pytest.mark.asyncio
async def test_auto_subagent_spawn_for_explicit_background_request(monkeypatch):
    db = get_db()
    await db.connect()
    user_id = f"test-subagent-auto-bg-{uuid.uuid4().hex[:8]}"
    cid = await db.get_or_create_conversation(user_id, "web")

    async def _fake_turn(
        *,
        user_id: str,
        child_conversation_id: str,
        task: str,
        provider_name: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
    ) -> str:
        await db.add_message(child_conversation_id, "assistant", "background completed")
        return "background completed"

    monkeypatch.setattr("app.subagent_orchestrator._run_subagent_turn", _fake_turn)

    reply = await handle_message(
        user_id=user_id,
        channel="web",
        text=(
            "Please run this in background: research my competitor positioning, compare pricing pages, "
            "and prepare a rollout plan with risks and mitigations."
        ),
        provider_name="openai",
        conversation_id=cid,
    )
    assert "background subagent" in reply.lower()
    m = re.search(r"\[([^\]]+)\]", reply)
    assert m is not None
    run_id = m.group(1).strip()
    assert run_id
    assert await wait_subagent_run(run_id, timeout_seconds=2.0) is True

    rows = await db.list_subagent_runs(cid, limit=20)
    assert any((r.get("run_id") or "") == run_id for r in rows)


@pytest.mark.asyncio
async def test_auto_subagent_not_used_for_simple_short_request():
    class _DummyProvider:
        name = "openai"

    async def _fake_compact(messages, provider, context=None, max_tokens=None):
        return messages

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(content="Short direct answer."), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=f"test-subagent-auto-no-{uuid.uuid4().hex[:8]}",
            channel="web",
            text="check my desktop",
            provider_name="openai",
        )

    assert "background subagent" not in reply.lower()
