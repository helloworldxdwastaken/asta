import asyncio
import json
import os

import pytest

from app.process_tool import parse_process_tool_args, run_exec_with_process_support, run_process_tool


async def _cleanup_sessions() -> None:
    listed = json.loads(await run_process_tool({"action": "list"}))
    for section in ("running", "finished"):
        for s in listed.get(section, []):
            sid = s.get("session_id")
            if sid:
                await run_process_tool({"action": "remove", "session_id": sid})


@pytest.mark.asyncio
async def test_exec_yield_completes_fast_command():
    await _cleanup_sessions()
    res = await run_exec_with_process_support(
        "echo hello",
        allowed_bins={"echo"},
        yield_ms=500,
    )
    assert res["status"] in ("completed", "failed")
    if res["status"] == "completed":
        assert "hello" in (res.get("stdout") or "")


@pytest.mark.asyncio
async def test_exec_yield_background_then_poll():
    await _cleanup_sessions()
    res = await run_exec_with_process_support(
        "sleep 1",
        allowed_bins={"sleep"},
        yield_ms=10,
    )
    assert res["status"] == "running"
    sid = res["session_id"]
    assert res["sessionId"] == sid
    assert isinstance(res.get("startedAt"), int)

    listed = json.loads(await run_process_tool({"action": "list"}))
    assert any(s["session_id"] == sid and s["sessionId"] == sid for s in listed.get("running", []))

    await asyncio.sleep(1.2)
    polled = json.loads(await run_process_tool({"action": "poll", "session_id": sid}))
    assert polled["session_id"] == sid
    assert polled["sessionId"] == sid
    assert polled["status"] in ("completed", "failed")


@pytest.mark.asyncio
async def test_process_log_write_kill_remove_actions():
    await _cleanup_sessions()
    res = await run_exec_with_process_support(
        "cat",
        allowed_bins={"cat"},
        background=True,
    )
    assert res["status"] == "running"
    sid = res["session_id"]

    wrote = json.loads(
        await run_process_tool(
            {"action": "write", "session_id": sid, "data": "hello from test\n"},
        )
    )
    assert wrote["ok"] is True

    await asyncio.sleep(0.1)
    logged = json.loads(await run_process_tool({"action": "log", "session_id": sid}))
    assert logged["session_id"] == sid
    assert logged["sessionId"] == sid
    assert logged["totalLines"] == logged["total_lines"]
    assert "hello from test" in (logged.get("log") or "")

    killed = json.loads(await run_process_tool({"action": "kill", "session_id": sid}))
    assert killed["status"] == "killed"

    removed = json.loads(await run_process_tool({"action": "remove", "session_id": sid}))
    assert removed["status"] == "removed"


@pytest.mark.asyncio
async def test_process_clear_finished_session():
    await _cleanup_sessions()
    res = await run_exec_with_process_support(
        "sleep 1",
        allowed_bins={"sleep"},
        yield_ms=10,
    )
    assert res["status"] == "running"
    sid = res["session_id"]

    await asyncio.sleep(1.2)
    polled = json.loads(await run_process_tool({"action": "poll", "session_id": sid}))
    assert polled["status"] in ("completed", "failed")

    cleared = json.loads(await run_process_tool({"action": "clear", "session_id": sid}))
    assert cleared["status"] == "cleared"


def test_parse_process_tool_args_normalizes_session_alias():
    parsed = parse_process_tool_args({"action": "send_keys", "sessionId": "p_123", "limit": "25"})
    assert parsed["session_id"] == "p_123"
    assert parsed["action"] == "send-keys"
    assert parsed["limit"] == 25


@pytest.mark.asyncio
async def test_process_openclaw_compat_actions():
    await _cleanup_sessions()
    res = await run_exec_with_process_support(
        "cat",
        allowed_bins={"cat"},
        background=True,
    )
    assert res["status"] == "running"
    sid = res["session_id"]

    pasted = json.loads(
        await run_process_tool(
            {"action": "paste", "sessionId": sid, "text": "hello compat\n", "bracketed": False},
        )
    )
    assert pasted["ok"] is True

    sent = json.loads(
        await run_process_tool(
            {"action": "send-keys", "sessionId": sid, "keys": ["w", "o", "r", "l", "d", "Enter"]},
        )
    )
    assert sent["ok"] is True

    submitted = json.loads(await run_process_tool({"action": "submit", "sessionId": sid}))
    assert submitted["ok"] is True

    await asyncio.sleep(0.1)
    logged = json.loads(await run_process_tool({"action": "log", "sessionId": sid}))
    text = logged.get("log") or ""
    assert "hello compat" in text
    assert "world" in text

    await run_process_tool({"action": "remove", "session_id": sid})


@pytest.mark.asyncio
async def test_exec_pty_flag_changes_tty_detection():
    if os.name == "nt":
        pytest.skip("PTY test is POSIX-only")
    await _cleanup_sessions()
    cmd = "sh -c 'if [ -t 1 ]; then echo tty; else echo notty; fi'"
    nonpty = await run_exec_with_process_support(
        cmd,
        allowed_bins={"sh"},
        yield_ms=1500,
        pty=False,
    )
    assert nonpty["status"] in ("completed", "failed")
    if nonpty["status"] == "completed":
        assert "notty" in (nonpty.get("stdout") or "")

    pty = await run_exec_with_process_support(
        cmd,
        allowed_bins={"sh"},
        yield_ms=1500,
        pty=True,
    )
    assert pty["status"] in ("completed", "failed")
    assert pty.get("pty") is True
    if pty["status"] == "completed":
        out = (pty.get("stdout") or "").lower()
        assert "tty" in out
