import asyncio
import json

import pytest

from app.process_tool import run_exec_with_process_support, run_process_tool


@pytest.mark.asyncio
async def test_exec_yield_completes_fast_command():
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
    res = await run_exec_with_process_support(
        "sleep 1",
        allowed_bins={"sleep"},
        yield_ms=10,
    )
    assert res["status"] == "running"
    sid = res["session_id"]

    listed = json.loads(await run_process_tool({"action": "list"}))
    assert any(s["session_id"] == sid for s in listed.get("running", []))

    await asyncio.sleep(1.2)
    polled = json.loads(await run_process_tool({"action": "poll", "session_id": sid}))
    assert polled["session_id"] == sid
    assert polled["status"] in ("completed", "failed")
