"""Single-user OpenClaw-style subagent orchestration tools and runtime."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.db import get_db
from app.message_queue import queue_key
from app.reminders import send_notification

logger = logging.getLogger(__name__)

_RUN_TASKS: dict[str, asyncio.Task] = {}
_ALLOWED_CLEANUP = {"keep", "delete"}


def get_subagent_tools_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "agents_list",
                "description": "List available agent ids for sessions_spawn. Asta single-user always returns one default agent.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sessions_spawn",
                "description": (
                    "Spawn a background subagent run in an isolated session. Non-blocking: returns accepted immediately."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "label": {"type": "string"},
                        "runTimeoutSeconds": {"type": "integer", "minimum": 0},
                        "timeoutSeconds": {"type": "integer", "minimum": 0},
                        "cleanup": {"type": "string", "enum": ["keep", "delete"]},
                    },
                    "required": ["task"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sessions_list",
                "description": "List recent subagent runs for the current parent session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sessions_history",
                "description": "Read message history for a subagent run/session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runId": {"type": "string"},
                        "sessionKey": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sessions_send",
                "description": "Send a follow-up message into a running subagent session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runId": {"type": "string"},
                        "sessionKey": {"type": "string"},
                        "message": {"type": "string"},
                        "text": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sessions_stop",
                "description": "Stop a running subagent run.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runId": {"type": "string"},
                        "sessionKey": {"type": "string"},
                    },
                },
            },
        },
    ]


def parse_subagent_tool_args(arguments_str: str | dict) -> dict:
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except Exception:
        data = {}
    out = dict(data)
    if not isinstance(out.get("runId"), str) and isinstance(out.get("run_id"), str):
        out["runId"] = out["run_id"]
    if not isinstance(out.get("sessionKey"), str):
        if isinstance(out.get("childSessionKey"), str):
            out["sessionKey"] = out["childSessionKey"]
        elif isinstance(out.get("session_id"), str):
            out["sessionKey"] = out["session_id"]
    if not isinstance(out.get("message"), str) and isinstance(out.get("text"), str):
        out["message"] = out["text"]
    if "runTimeoutSeconds" not in out and "timeoutSeconds" in out:
        out["runTimeoutSeconds"] = out.get("timeoutSeconds")
    return out


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_timeout(raw: object) -> int:
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return max(0, min(raw, 3600))
    if isinstance(raw, str) and raw.strip().isdigit():
        return max(0, min(int(raw.strip()), 3600))
    return 0


def _render_announce_message(run: dict) -> str:
    label = (run.get("label") or "").strip() or (run.get("task") or "").strip() or "subagent task"
    status = (run.get("status") or "").strip().lower()
    result = (run.get("result_text") or "").strip()
    error = (run.get("error_text") or "").strip()

    if status == "completed":
        if result:
            snippet = result[:1800] + ("…" if len(result) > 1800 else "")
            return f"Subagent \"{label}\" finished.\n\n{snippet}"
        return f"Subagent \"{label}\" finished."
    if status == "timeout":
        return f"Subagent \"{label}\" timed out."
    if status == "stopped":
        return f"Subagent \"{label}\" was stopped."
    if status == "error":
        if error:
            return f"Subagent \"{label}\" failed: {error[:500]}"
        return f"Subagent \"{label}\" failed."
    if status == "interrupted":
        return f"Subagent \"{label}\" was interrupted by restart."
    return f"Subagent \"{label}\" ended with status: {status or 'unknown'}."


async def _run_subagent_turn(
    *,
    user_id: str,
    child_conversation_id: str,
    task: str,
    provider_name: str,
) -> str:
    from app.handler import handle_message

    async with queue_key(f"subagent:{child_conversation_id}"):
        return await handle_message(
            user_id=user_id,
            channel="subagent",
            text=task,
            provider_name=provider_name,
            conversation_id=child_conversation_id,
            channel_target="",
            extra_context={"subagent_mode": True},
        )


async def _announce_subagent_run(run_id: str) -> None:
    db = get_db()
    await db.connect()
    run = await db.get_subagent_run(run_id)
    if not run:
        return
    message = _render_announce_message(run)
    parent_cid = (run.get("parent_conversation_id") or "").strip()
    channel = (run.get("channel") or "").strip().lower()
    target = (run.get("channel_target") or "").strip()

    if parent_cid:
        await db.add_message(parent_cid, "assistant", message, "script")
    if channel in ("telegram", "whatsapp") and target:
        try:
            await send_notification(channel, target, message)
        except Exception as e:
            logger.debug("Subagent announce failed channel=%s target=%s: %s", channel, target, e)


async def _run_subagent_background(
    *,
    run_id: str,
    user_id: str,
    parent_conversation_id: str,
    child_conversation_id: str,
    task: str,
    provider_name: str,
    run_timeout_seconds: int,
    cleanup: str,
) -> None:
    db = get_db()
    await db.connect()
    try:
        if run_timeout_seconds > 0:
            reply = await asyncio.wait_for(
                _run_subagent_turn(
                    user_id=user_id,
                    child_conversation_id=child_conversation_id,
                    task=task,
                    provider_name=provider_name,
                ),
                timeout=run_timeout_seconds,
            )
        else:
            reply = await _run_subagent_turn(
                user_id=user_id,
                child_conversation_id=child_conversation_id,
                task=task,
                provider_name=provider_name,
            )
        await db.update_subagent_run(
            run_id,
            status="completed",
            result_text=(reply or "").strip(),
            ended=True,
        )
    except asyncio.TimeoutError:
        await db.update_subagent_run(
            run_id,
            status="timeout",
            error_text=f"Timed out after {run_timeout_seconds}s.",
            ended=True,
        )
    except asyncio.CancelledError:
        await db.update_subagent_run(
            run_id,
            status="stopped",
            error_text="Stopped by request.",
            ended=True,
        )
        raise
    except Exception as e:
        await db.update_subagent_run(
            run_id,
            status="error",
            error_text=str(e)[:1000],
            ended=True,
        )
    finally:
        await _announce_subagent_run(run_id)
        if cleanup == "delete":
            try:
                await db.delete_conversation(child_conversation_id)
            except Exception:
                pass
        _RUN_TASKS.pop(run_id, None)


async def spawn_subagent_run(
    *,
    user_id: str,
    parent_conversation_id: str,
    task: str,
    label: str | None,
    provider_name: str,
    channel: str,
    channel_target: str,
    cleanup: str = "keep",
    run_timeout_seconds: int = 0,
) -> dict:
    cleaned_task = (task or "").strip()
    if not cleaned_task:
        return {"status": "error", "error": "task is required"}
    if cleanup not in _ALLOWED_CLEANUP:
        cleanup = "keep"

    run_id = f"sub_{uuid4().hex[:10]}"
    child_cid = f"{parent_conversation_id}:subagent:{run_id}"
    db = get_db()
    await db.connect()
    await db.add_subagent_run(
        run_id=run_id,
        user_id=user_id,
        parent_conversation_id=parent_conversation_id,
        child_conversation_id=child_cid,
        task=cleaned_task,
        label=(label or "").strip() or None,
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
        cleanup=cleanup,
        status="running",
    )
    task_obj = asyncio.create_task(
        _run_subagent_background(
            run_id=run_id,
            user_id=user_id,
            parent_conversation_id=parent_conversation_id,
            child_conversation_id=child_cid,
            task=cleaned_task,
            provider_name=provider_name,
            run_timeout_seconds=run_timeout_seconds,
            cleanup=cleanup,
        ),
        name=f"subagent:{run_id}",
    )
    _RUN_TASKS[run_id] = task_obj
    return {
        "status": "accepted",
        "runId": run_id,
        "childSessionKey": child_cid,
        "cleanup": cleanup,
        "runTimeoutSeconds": run_timeout_seconds,
        "createdAt": _now_iso(),
    }


def _match_run(rows: list[dict], run_id: str | None, session_key: str | None) -> dict | None:
    rid = (run_id or "").strip()
    skey = (session_key or "").strip()
    if rid:
        for row in rows:
            if (row.get("run_id") or "").strip() == rid:
                return row
    if skey:
        for row in rows:
            if (row.get("child_conversation_id") or "").strip() == skey:
                return row
    return rows[0] if rows else None


async def stop_subagent_run(run_id: str) -> bool:
    rid = (run_id or "").strip()
    if not rid:
        return False
    task = _RUN_TASKS.get(rid)
    if task and not task.done():
        task.cancel()
        return True
    return False


async def wait_subagent_run(run_id: str, timeout_seconds: float = 20.0) -> bool:
    rid = (run_id or "").strip()
    if not rid:
        return False
    task = _RUN_TASKS.get(rid)
    if not task:
        return True
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=max(0.1, timeout_seconds))
        return True
    except asyncio.CancelledError:
        return True
    except Exception:
        return False


async def recover_subagent_runs_on_startup() -> int:
    db = get_db()
    await db.connect()
    fixed = await db.mark_running_subagent_runs_interrupted()
    if fixed:
        logger.info("Marked %d running subagent run(s) as interrupted after restart.", fixed)
    return fixed


async def run_subagent_tool(
    *,
    tool_name: str,
    params: dict,
    user_id: str,
    parent_conversation_id: str,
    provider_name: str,
    channel: str,
    channel_target: str,
) -> str:
    db = get_db()
    await db.connect()
    name = (tool_name or "").strip()
    if name == "agents_list":
        return _json({"agents": [{"id": "main", "label": "Asta (single-user)"}], "count": 1})

    if name == "sessions_spawn":
        payload = await spawn_subagent_run(
            user_id=user_id,
            parent_conversation_id=parent_conversation_id,
            task=(params.get("task") or "").strip(),
            label=(params.get("label") or "").strip() or None,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
            cleanup=(params.get("cleanup") or "keep").strip().lower(),
            run_timeout_seconds=_normalize_timeout(params.get("runTimeoutSeconds")),
        )
        return _json(payload)

    if name == "sessions_list":
        limit = _normalize_timeout(params.get("limit")) or 20
        rows = await db.list_subagent_runs(parent_conversation_id, limit=limit)
        runs = []
        for row in rows:
            runs.append(
                {
                    "runId": row.get("run_id"),
                    "status": row.get("status"),
                    "label": row.get("label") or row.get("task") or "",
                    "childSessionKey": row.get("child_conversation_id"),
                    "createdAt": row.get("created_at"),
                    "startedAt": row.get("started_at"),
                    "endedAt": row.get("ended_at"),
                }
            )
        return _json({"runs": runs, "count": len(runs)})

    if name == "sessions_history":
        run_id = (params.get("runId") or "").strip()
        session_key = (params.get("sessionKey") or "").strip()
        rows = await db.list_subagent_runs(parent_conversation_id, limit=200)
        row = _match_run(rows, run_id, session_key)
        if not row:
            return _json({"error": "Subagent run not found for this session."})
        limit = _normalize_timeout(params.get("limit")) or 40
        messages = await db.get_recent_messages(row["child_conversation_id"], limit=limit)
        return _json(
            {
                "runId": row.get("run_id"),
                "status": row.get("status"),
                "childSessionKey": row.get("child_conversation_id"),
                "messages": messages,
            }
        )

    if name == "sessions_send":
        run_id = (params.get("runId") or "").strip()
        session_key = (params.get("sessionKey") or "").strip()
        message = (params.get("message") or "").strip()
        if not message:
            return _json({"error": "message is required"})
        rows = await db.list_subagent_runs(parent_conversation_id, limit=200)
        row = _match_run(rows, run_id, session_key)
        if not row:
            return _json({"error": "Subagent run not found for this session."})
        if (row.get("status") or "").strip().lower() != "running":
            return _json({"error": "Subagent is not running.", "status": row.get("status")})

        async def _send() -> None:
            await _run_subagent_turn(
                user_id=user_id,
                child_conversation_id=row["child_conversation_id"],
                task=message,
                provider_name=(row.get("provider_name") or provider_name or "default"),
            )

        asyncio.create_task(_send(), name=f"subagent-send:{row['run_id']}")
        return _json(
            {
                "status": "accepted",
                "runId": row.get("run_id"),
                "childSessionKey": row.get("child_conversation_id"),
            }
        )

    if name == "sessions_stop":
        run_id = (params.get("runId") or "").strip()
        session_key = (params.get("sessionKey") or "").strip()
        rows = await db.list_subagent_runs(parent_conversation_id, limit=200)
        row = _match_run(rows, run_id, session_key)
        if not row:
            return _json({"error": "Subagent run not found for this session."})
        stopped = await stop_subagent_run(str(row.get("run_id") or ""))
        if not stopped and (row.get("status") or "").strip().lower() == "running":
            await db.update_subagent_run(
                str(row.get("run_id") or ""),
                status="interrupted",
                error_text="Asta could not stop this run cleanly.",
                ended=True,
            )
        return _json(
            {
                "status": "stopped" if stopped else "already-ended",
                "runId": row.get("run_id"),
                "childSessionKey": row.get("child_conversation_id"),
            }
        )

    return _json({"error": f"Unsupported subagent tool: {name}"})
