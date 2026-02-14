"""OpenClaw-style process companion tool for long-running exec sessions."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.exec_tool import (
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    prepare_allowlisted_command,
    resolve_safe_workdir,
)

logger = logging.getLogger(__name__)

DEFAULT_YIELD_MS = 10_000
DEFAULT_TIMEOUT_SECONDS = 30 * 60
DEFAULT_FINISHED_TTL_SECONDS = 30 * 60
MAX_FINISHED_TTL_SECONDS = 3 * 60 * 60
MIN_FINISHED_TTL_SECONDS = 60
DEFAULT_TAIL_CHARS = 2000


def _finished_ttl_seconds() -> int:
    raw = (os.environ.get("ASTA_PROCESS_TTL_SECONDS") or "").strip()
    try:
        val = int(raw)
    except Exception:
        return DEFAULT_FINISHED_TTL_SECONDS
    return max(MIN_FINISHED_TTL_SECONDS, min(MAX_FINISHED_TTL_SECONDS, val))


def _new_session_id() -> str:
    return f"p_{uuid.uuid4().hex[:10]}"


def _safe_decode(chunk: bytes) -> str:
    return (chunk or b"").decode("utf-8", errors="replace")


def _slice_log_lines(text: str, offset: int | None, limit: int | None) -> tuple[str, int]:
    lines = (text or "").splitlines()
    total = len(lines)
    if total == 0:
        return "", 0
    lim = int(limit) if isinstance(limit, int) and limit > 0 else 200
    if isinstance(offset, int) and offset >= 0:
        start = min(offset, total)
    else:
        start = max(0, total - lim)
    end = min(total, start + lim)
    return "\n".join(lines[start:end]), total


@dataclass
class ProcessSession:
    id: str
    command: str
    process: asyncio.subprocess.Process
    started_at: float
    cwd: str | None = None
    backgrounded: bool = False
    exited: bool = False
    exit_code: int | None = None
    exit_signal: int | None = None
    aggregated: str = ""
    pending_stdout: list[str] = field(default_factory=list)
    pending_stderr: list[str] = field(default_factory=list)
    tail: str = ""
    truncated: bool = False
    timeout_task: asyncio.Task | None = None

    @property
    def pid(self) -> int | None:
        return self.process.pid


@dataclass
class FinishedSession:
    id: str
    command: str
    started_at: float
    ended_at: float
    status: str
    cwd: str | None = None
    exit_code: int | None = None
    exit_signal: int | None = None
    aggregated: str = ""
    tail: str = ""
    truncated: bool = False


_running_sessions: dict[str, ProcessSession] = {}
_finished_sessions: dict[str, FinishedSession] = {}


def _cleanup_finished() -> None:
    cutoff = time.time() - _finished_ttl_seconds()
    for sid, s in list(_finished_sessions.items()):
        if s.ended_at < cutoff:
            _finished_sessions.pop(sid, None)


def _append_output(s: ProcessSession, text: str, stream: str) -> None:
    if not text:
        return
    if stream == "stderr":
        s.pending_stderr.append(text)
    else:
        s.pending_stdout.append(text)
    merged = s.aggregated + text
    if len(merged) > MAX_OUTPUT_BYTES:
        s.truncated = True
        merged = merged[-MAX_OUTPUT_BYTES:]
    s.aggregated = merged
    s.tail = merged[-DEFAULT_TAIL_CHARS:] if len(merged) > DEFAULT_TAIL_CHARS else merged


def _drain_pending(s: ProcessSession) -> tuple[str, str]:
    out = "".join(s.pending_stdout)
    err = "".join(s.pending_stderr)
    s.pending_stdout.clear()
    s.pending_stderr.clear()
    return out, err


def _finalize_session(s: ProcessSession, status: str) -> None:
    _running_sessions.pop(s.id, None)
    if not s.backgrounded:
        return
    _finished_sessions[s.id] = FinishedSession(
        id=s.id,
        command=s.command,
        started_at=s.started_at,
        ended_at=time.time(),
        status=status,
        cwd=s.cwd,
        exit_code=s.exit_code,
        exit_signal=s.exit_signal,
        aggregated=s.aggregated,
        tail=s.tail,
        truncated=s.truncated,
    )


async def _read_stream(s: ProcessSession, which: str) -> None:
    stream = s.process.stderr if which == "stderr" else s.process.stdout
    if stream is None:
        return
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        _append_output(s, _safe_decode(chunk), which)


async def _watch_exit(s: ProcessSession) -> None:
    rc = await s.process.wait()
    s.exited = True
    s.exit_code = rc
    status = "completed" if rc == 0 else "failed"
    _finalize_session(s, status)


async def _enforce_timeout(s: ProcessSession, timeout_seconds: int) -> None:
    try:
        await asyncio.sleep(timeout_seconds)
        if s.exited:
            return
        s.process.terminate()
        try:
            await asyncio.wait_for(s.process.wait(), timeout=3)
        except asyncio.TimeoutError:
            s.process.kill()
            await s.process.wait()
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.warning("Process timeout watcher failed for %s: %s", s.id, e)


async def _spawn_session(
    parts: list[str],
    *,
    command: str,
    cwd: Path | None,
    timeout_seconds: int,
    backgrounded: bool,
) -> ProcessSession:
    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    s = ProcessSession(
        id=_new_session_id(),
        command=command,
        process=proc,
        started_at=time.time(),
        cwd=str(cwd) if cwd else None,
        backgrounded=backgrounded,
    )
    _running_sessions[s.id] = s
    asyncio.create_task(_read_stream(s, "stdout"))
    asyncio.create_task(_read_stream(s, "stderr"))
    asyncio.create_task(_watch_exit(s))
    s.timeout_task = asyncio.create_task(_enforce_timeout(s, timeout_seconds))
    return s


async def run_exec_with_process_support(
    command: str,
    *,
    allowed_bins: set[str],
    timeout_seconds: int | None = None,
    workdir: str | None = None,
    background: bool = False,
    yield_ms: int | None = None,
) -> dict:
    """Run an allowlisted command with optional OpenClaw-style background behavior."""
    parts, err = prepare_allowlisted_command(command, allowed_bins=allowed_bins)
    if err:
        return {"status": "failed", "error": err}
    assert parts is not None
    cwd = resolve_safe_workdir(workdir)
    if workdir and cwd is None:
        return {"status": "failed", "error": "Invalid workdir. Use a directory under your home or workspace."}

    timeout = DEFAULT_TIMEOUT_SECONDS
    if isinstance(timeout_seconds, int):
        timeout = max(1, min(timeout_seconds, MAX_TIMEOUT_SECONDS))
    y_ms = DEFAULT_YIELD_MS if yield_ms is None else max(10, min(int(yield_ms), 120_000))

    s = await _spawn_session(
        parts,
        command=command,
        cwd=cwd,
        timeout_seconds=timeout,
        backgrounded=bool(background),
    )
    if background:
        return {
            "status": "running",
            "session_id": s.id,
            "pid": s.pid,
            "started_at": int(s.started_at),
            "cwd": s.cwd,
            "tail": s.tail,
        }

    try:
        await asyncio.wait_for(s.process.wait(), timeout=y_ms / 1000.0)
        await asyncio.sleep(0)
        stdout, stderr = _drain_pending(s)
        if s.timeout_task:
            s.timeout_task.cancel()
        _running_sessions.pop(s.id, None)
        ok = (s.exit_code or 0) == 0
        return {
            "status": "completed" if ok else "failed",
            "ok": ok,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": s.exit_code,
        }
    except asyncio.TimeoutError:
        s.backgrounded = True
        return {
            "status": "running",
            "session_id": s.id,
            "pid": s.pid,
            "started_at": int(s.started_at),
            "cwd": s.cwd,
            "tail": s.tail,
            "note": f"Process is still running after {y_ms}ms; use process tool to poll/log/kill.",
        }


def get_process_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "process",
                "description": (
                    "Manage background exec sessions. Actions: list, poll, log, write, kill, clear, remove. "
                    "Use after exec returns status=running with a session_id."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["list", "poll", "log", "write", "kill", "clear", "remove"],
                        },
                        "session_id": {"type": "string"},
                        "data": {"type": "string", "description": "stdin data for write action"},
                        "eof": {"type": "boolean", "description": "close stdin after write"},
                        "offset": {"type": "integer", "description": "line offset for log"},
                        "limit": {"type": "integer", "description": "line limit for log"},
                    },
                    "required": ["action"],
                },
            },
        }
    ]


def parse_process_tool_args(arguments_str: str | dict) -> dict:
    if isinstance(arguments_str, dict):
        return arguments_str
    try:
        data = json.loads(arguments_str)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def run_process_tool(params: dict) -> str:
    _cleanup_finished()
    action = (params.get("action") or "").strip().lower()

    if action == "list":
        running = []
        for s in list(_running_sessions.values()):
            if s.backgrounded:
                running.append(
                    {
                        "session_id": s.id,
                        "status": "running",
                        "pid": s.pid,
                        "started_at": int(s.started_at),
                        "runtime_sec": int(time.time() - s.started_at),
                        "cwd": s.cwd,
                        "command": s.command,
                        "tail": s.tail,
                        "truncated": s.truncated,
                    }
                )
        finished = [
            {
                "session_id": s.id,
                "status": s.status,
                "started_at": int(s.started_at),
                "ended_at": int(s.ended_at),
                "runtime_sec": int(max(0, s.ended_at - s.started_at)),
                "cwd": s.cwd,
                "command": s.command,
                "tail": s.tail,
                "truncated": s.truncated,
                "exit_code": s.exit_code,
                "exit_signal": s.exit_signal,
            }
            for s in list(_finished_sessions.values())
        ]
        payload = {"running": running, "finished": finished}
        return json.dumps(payload, indent=0)

    sid = (params.get("session_id") or "").strip()
    if not sid:
        return "Error: session_id is required for this action."

    s = _running_sessions.get(sid)
    f = _finished_sessions.get(sid)

    if action == "poll":
        if s:
            stdout, stderr = _drain_pending(s)
            payload = {
                "session_id": sid,
                "status": "running",
                "stdout": stdout,
                "stderr": stderr,
                "tail": s.tail,
            }
            return json.dumps(payload, indent=0)
        if f:
            payload = {
                "session_id": sid,
                "status": f.status,
                "tail": f.tail,
                "exit_code": f.exit_code,
                "exit_signal": f.exit_signal,
            }
            return json.dumps(payload, indent=0)
        return f"Error: No session found for {sid}."

    if action == "log":
        text = s.aggregated if s else (f.aggregated if f else "")
        if not s and not f:
            return f"Error: No session found for {sid}."
        slice_text, total_lines = _slice_log_lines(
            text,
            params.get("offset") if isinstance(params.get("offset"), int) else None,
            params.get("limit") if isinstance(params.get("limit"), int) else None,
        )
        payload = {
            "session_id": sid,
            "status": "running" if s else f.status,
            "total_lines": total_lines,
            "log": slice_text,
            "truncated": s.truncated if s else f.truncated,
        }
        return json.dumps(payload, indent=0)

    if action == "write":
        if not s:
            return f"Error: No active session found for {sid}."
        data = params.get("data")
        if not isinstance(data, str):
            return "Error: write action requires string `data`."
        try:
            if s.process.stdin is None:
                return f"Error: stdin is not available for {sid}."
            s.process.stdin.write(data.encode("utf-8", errors="replace"))
            await s.process.stdin.drain()
            if bool(params.get("eof")):
                with contextlib.suppress(Exception):
                    s.process.stdin.write_eof()
        except Exception as e:
            return f"Error writing to session {sid}: {e}"
        return json.dumps({"ok": True, "session_id": sid}, indent=0)

    if action == "kill":
        if not s:
            return f"Error: No active session found for {sid}."
        try:
            s.process.terminate()
            try:
                await asyncio.wait_for(s.process.wait(), timeout=3)
            except asyncio.TimeoutError:
                s.process.kill()
                await s.process.wait()
        except Exception as e:
            return f"Error killing session {sid}: {e}"
        return json.dumps({"ok": True, "session_id": sid, "status": "killed"}, indent=0)

    if action == "clear":
        if sid in _finished_sessions:
            _finished_sessions.pop(sid, None)
            return json.dumps({"ok": True, "session_id": sid, "status": "cleared"}, indent=0)
        if sid in _running_sessions:
            return f"Error: session {sid} is still running. Use kill or remove."
        return f"Error: No session found for {sid}."

    if action == "remove":
        if sid in _running_sessions:
            s = _running_sessions[sid]
            try:
                s.process.terminate()
                try:
                    await asyncio.wait_for(s.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    s.process.kill()
                    await s.process.wait()
            except Exception:
                pass
            _running_sessions.pop(sid, None)
            _finished_sessions.pop(sid, None)
            return json.dumps({"ok": True, "session_id": sid, "status": "removed"}, indent=0)
        if sid in _finished_sessions:
            _finished_sessions.pop(sid, None)
            return json.dumps({"ok": True, "session_id": sid, "status": "removed"}, indent=0)
        return f"Error: No session found for {sid}."

    return "Error: unknown action. Use one of: list, poll, log, write, kill, clear, remove."
