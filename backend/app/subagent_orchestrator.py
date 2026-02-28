"""Single-user OpenClaw-style subagent orchestration tools and runtime."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from app.config import get_settings
from app.db import get_db
from app.message_queue import queue_key
from app.reminders import send_notification

logger = logging.getLogger(__name__)

_RUN_TASKS: dict[str, asyncio.Task] = {}
_ARCHIVE_TASKS: dict[str, asyncio.Task] = {}
_TASKS_LOCK = asyncio.Lock()  # Guards _RUN_TASKS and _ARCHIVE_TASKS access
# Track depth for each session: session_key -> depth level
_SESSION_DEPTHS: dict[str, int] = {}
_DEPTHS_LOCK = asyncio.Lock()
_ALLOWED_CLEANUP = {"keep", "delete"}
_ALLOWED_THINKING = {"off", "minimal", "low", "medium", "high", "xhigh"}


async def _get_session_depth(session_key: str) -> int:
    """Get the current depth level for a session key.
    
    Depth is determined by counting ':subagent:' occurrences in the session key.
    Main session = depth 0
    First-level subagent = depth 1
    Second-level subagent = depth 2, etc.
    """
    return session_key.count(":subagent:")


async def _get_children_count(parent_session_key: str) -> int:
    """Count active child subagents for a given parent session."""
    async with _TASKS_LOCK:
        count = 0
        for run_id, task in _RUN_TASKS.items():
            if task is None or task.done():
                continue
            # Check if this task is a direct child of the parent
            if f"{parent_session_key}:subagent:" in run_id:
                count += 1
        return count


def get_subagent_tools_openai_def() -> list[dict]:
    settings = get_settings()
    max_depth = max(1, int(getattr(settings, "asta_subagents_max_depth", 1) or 1))
    max_children = max(1, int(getattr(settings, "asta_subagents_max_children", 5) or 5))
    
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
                    f"Spawn a background subagent run in an isolated session. "
                    f"Non-blocking: returns accepted immediately. "
                    f"Max nesting depth: {max_depth}, max concurrent children: {max_children}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "label": {"type": "string"},
                        "model": {"type": "string", "description": "Optional model override for this subagent run."},
                        "thinking": {
                            "type": "string",
                            "enum": ["off", "minimal", "low", "medium", "high", "xhigh"],
                            "description": "Optional thinking override for this subagent run.",
                        },
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
                "description": "Send a follow-up message into a running subagent session. Optional timeoutSeconds waits for a reply.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runId": {"type": "string"},
                        "sessionKey": {"type": "string"},
                        "message": {"type": "string"},
                        "text": {"type": "string"},
                        "timeoutSeconds": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Optional wait timeout. If >0, wait for subagent reply up to N seconds.",
                        },
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
    if "timeoutSeconds" not in out and "waitSeconds" in out:
        out["timeoutSeconds"] = out.get("waitSeconds")
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


def _normalize_thinking(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if not value:
        return None
    if value not in _ALLOWED_THINKING:
        return "__invalid__"
    return value


async def _active_in_memory_count() -> int:
    """Count active tasks - MUST be called under _TASKS_LOCK.

    This function does NOT acquire the lock itself because it's only
    called from sections that already hold _TASKS_LOCK. Acquiring the
    lock here would cause a deadlock.
    """
    return sum(1 for t in _RUN_TASKS.values() if not t.done())


def _archive_after_seconds() -> int | None:
    # Testing override: allow short timers without changing minutes config.
    raw_seconds = (os.environ.get("ASTA_SUBAGENTS_ARCHIVE_AFTER_SECONDS") or "").strip()
    if raw_seconds.isdigit():
        sec = int(raw_seconds)
        return sec if sec > 0 else None
    minutes = int(getattr(get_settings(), "asta_subagents_archive_after_minutes", 60) or 0)
    if minutes <= 0:
        return None
    return minutes * 60


def _render_announce_message(run: dict) -> str:
    label = (run.get("label") or "").strip() or (run.get("task") or "").strip() or "subagent task"
    status = (run.get("status") or "").strip().lower()
    result = (run.get("result_text") or "").strip()
    error = (run.get("error_text") or "").strip()

    if status == "completed":
        if result:
            snippet = result[:1800] + ("..." if len(result) > 1800 else "")
            return f'Subagent "{label}" finished.\n\n{snippet}'
        return f'Subagent "{label}" finished.'
    if status == "timeout":
        return f'Subagent "{label}" timed out.'
    if status == "stopped":
        return f'Subagent "{label}" was stopped.'
    if status == "error":
        if error:
            return f'Subagent "{label}" failed: {error[:500]}'
        return f'Subagent "{label}" failed.'
    if status == "interrupted":
        return f'Subagent "{label}" was interrupted by restart.'
    return f'Subagent "{label}" ended with status: {status or "unknown"}.'


async def _run_subagent_turn(
    *,
    user_id: str,
    child_conversation_id: str,
    task: str,
    provider_name: str,
    model_override: str | None = None,
    thinking_override: str | None = None,
) -> str:
    from app.handler import handle_message

    extra = {"subagent_mode": True}
    if model_override:
        extra["subagent_model_override"] = model_override
    if thinking_override:
        extra["subagent_thinking_override"] = thinking_override

    async with queue_key(f"subagent:{child_conversation_id}"):
        return await handle_message(
            user_id=user_id,
            channel="subagent",
            text=task,
            provider_name=provider_name,
            conversation_id=child_conversation_id,
            channel_target="",
            extra_context=extra,
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
    if channel == "telegram" and target:
        try:
            await send_notification(channel, target, message)
        except Exception as e:
            logger.debug("Subagent announce failed channel=%s target=%s: %s", channel, target, e)


async def _archive_child_session_after_delay(run_id: str, child_conversation_id: str, delay_seconds: int) -> None:
    try:
        await asyncio.sleep(max(1, int(delay_seconds)))
        db = get_db()
        await db.connect()
        run = await db.get_subagent_run(run_id)
        if not run:
            return
        status = (run.get("status") or "").strip().lower()
        if status == "running":
            return
        if run.get("archived_at"):
            return
        await db.delete_conversation(child_conversation_id)
        await db.update_subagent_run(run_id, archived=True)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.debug("Subagent archive timer failed run=%s: %s", run_id, e)
    finally:
        # Clean up task reference under lock
        async with _TASKS_LOCK:
            _ARCHIVE_TASKS.pop(run_id, None)


async def _schedule_archive_timer(run_id: str, child_conversation_id: str) -> None:
    """Schedule archive with proper lock protection."""
    delay = _archive_after_seconds()
    if delay is None:
        return
    async with _TASKS_LOCK:
        existing = _ARCHIVE_TASKS.get(run_id)
        if existing and not existing.done():
            existing.cancel()
        _ARCHIVE_TASKS[run_id] = asyncio.create_task(
            _archive_child_session_after_delay(run_id, child_conversation_id, delay),
            name=f"subagent-archive:{run_id}",
    )


async def _run_subagent_background(
    *,
    run_id: str,
    user_id: str,
    child_conversation_id: str,
    task: str,
    provider_name: str,
    model_override: str | None,
    thinking_override: str | None,
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
                    model_override=model_override,
                    thinking_override=thinking_override,
                ),
                timeout=run_timeout_seconds,
            )
        else:
            reply = await _run_subagent_turn(
                user_id=user_id,
                child_conversation_id=child_conversation_id,
                task=task,
                provider_name=provider_name,
                model_override=model_override,
                thinking_override=thinking_override,
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

        # Determine cleanup action under lock, execute outside lock to avoid deadlock
        should_archive = False
        async with _TASKS_LOCK:
            if cleanup == "delete":
                try:
                    # Update DB state first (safer order)
                    await db.update_subagent_run(run_id, archived=True)
                    # Then delete conversation
                    await db.delete_conversation(child_conversation_id)
                except Exception as e:
                    logger.warning("Failed to cleanup subagent %s: %s", run_id, e)
            else:
                should_archive = True

            # Clean up task reference
            _RUN_TASKS.pop(run_id, None)

        # Schedule archive timer outside lock to avoid deadlock
        if should_archive:
            await _schedule_archive_timer(run_id, child_conversation_id)


async def spawn_subagent_run(
    *,
    user_id: str,
    parent_conversation_id: str,
    task: str,
    label: str | None,
    provider_name: str,
    channel: str,
    channel_target: str,
    model_override: str | None = None,
    thinking_override: str | None = None,
    cleanup: str = "keep",
    run_timeout_seconds: int = 0,
) -> dict:
    cleaned_task = (task or "").strip()
    if not cleaned_task:
        return {"status": "error", "error": "task is required"}
    if cleanup not in _ALLOWED_CLEANUP:
        cleanup = "keep"
    thinking_norm = _normalize_thinking(thinking_override)
    if thinking_norm == "__invalid__":
        return {"status": "error", "error": "thinking must be one of: off, minimal, low, medium, high, xhigh"}
    thinking_override = thinking_norm or None

    # Get depth and children limits from settings
    settings = get_settings()
    max_depth = max(1, int(getattr(settings, "asta_subagents_max_depth", 1) or 1))
    max_children = max(1, int(getattr(settings, "asta_subagents_max_children", 5) or 5))
    
    # Check current depth level of parent session
    current_depth = await _get_session_depth(parent_conversation_id)
    if current_depth >= max_depth:
        return {
            "status": "error",
            "error": f"Max subagent depth reached ({max_depth}). Cannot spawn subagent at depth {current_depth + 1}.",
            "maxDepth": max_depth,
            "currentDepth": current_depth,
        }
    
    # Check children count for this parent
    children_count = await _get_children_count(parent_conversation_id)
    if children_count >= max_children:
        return {
            "status": "error",
            "error": f"Max concurrent children reached ({max_children}). Cannot spawn more subagents.",
            "maxChildren": max_children,
            "currentChildren": children_count,
        }

    db = get_db()
    await db.connect()
    max_concurrent = max(1, int(getattr(settings, "asta_subagents_max_concurrent", 3) or 3))

    # Protect concurrency check and task creation with lock.
    # Single-user runtime truth is in-memory tasks; DB "running" rows can become stale
    # after crashes/restarts or test interruptions.
    async with _TASKS_LOCK:
        running_rows = await db.get_subagent_runs_by_status(["running"], limit=5000)
        active_run_ids = {
            rid for rid, task in _RUN_TASKS.items() if rid and task is not None and not task.done()
        }
        stale_running_ids: list[str] = []
        for row in running_rows:
            rid = str(row.get("run_id") or "").strip()
            if rid and rid not in active_run_ids:
                stale_running_ids.append(rid)
        for rid in stale_running_ids:
            await db.update_subagent_run(
                rid,
                status="interrupted",
                error_text="Recovered stale running state.",
                ended=True,
            )

        running_count = len(active_run_ids)
        if running_count >= max_concurrent:
            return {
                "status": "busy",
                "error": f"Max concurrent subagents reached ({max_concurrent}).",
                "maxConcurrent": max_concurrent,
                "running": running_count,
            }

        run_id = f"sub_{uuid4().hex[:10]}"
        child_cid = f"{parent_conversation_id}:subagent:{run_id}"
        await db.add_subagent_run(
            run_id=run_id,
            user_id=user_id,
            parent_conversation_id=parent_conversation_id,
            child_conversation_id=child_cid,
            task=cleaned_task,
            label=(label or "").strip() or None,
            provider_name=provider_name,
            model_override=(model_override or "").strip() or None,
            thinking_override=thinking_override,
            run_timeout_seconds=run_timeout_seconds,
            channel=channel,
            channel_target=channel_target,
            cleanup=cleanup,
            status="running",
        )
        task_obj = asyncio.create_task(
            _run_subagent_background(
                run_id=run_id,
                user_id=user_id,
                child_conversation_id=child_cid,
                task=cleaned_task,
                provider_name=provider_name,
                model_override=(model_override or "").strip() or None,
                thinking_override=thinking_override,
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
        "maxConcurrent": max_concurrent,
        "model": (model_override or "").strip() or None,
        "thinking": thinking_override,
        "createdAt": _now_iso(),
        "note": "auto-announces on completion — do not poll or wait. Reply to the user immediately; the result will be delivered as an assistant message when the agent finishes.",
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
    """Stop a running subagent by canceling its task.

    Returns True if task was canceled, False if not found or already done.
    """
    rid = (run_id or "").strip()
    if not rid:
        return False

    # Get task reference under lock
    async with _TASKS_LOCK:
        task = _RUN_TASKS.get(rid)

    # Cancel task if running (outside lock to avoid blocking)
    if task and not task.done():
        task.cancel()
        return True
    return False


async def wait_subagent_run(run_id: str, timeout_seconds: float = 20.0) -> bool:
    """Wait for a subagent run to complete.

    Returns True if completed or not found, False on timeout.
    """
    rid = (run_id or "").strip()
    if not rid:
        return False

    # Get task reference under lock to avoid race condition
    async with _TASKS_LOCK:
        task = _RUN_TASKS.get(rid)

    # If no task found, assume already completed
    if not task:
        return True

    # Wait for task to complete (outside lock to avoid blocking other operations)
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
    # Best effort: schedule archive timers for completed non-archived runs.
    try:
        done_rows = await db.get_subagent_runs_by_status(
            ["completed", "timeout", "error", "stopped", "interrupted"],
            limit=1000,
        )
        for row in done_rows:
            if row.get("archived_at"):
                continue
            if (row.get("cleanup") or "").strip().lower() == "delete":
                continue
            child_key = (row.get("child_conversation_id") or "").strip()
            run_id = (row.get("run_id") or "").strip()
            if run_id and child_key:
                await _schedule_archive_timer(run_id, child_key)
    except Exception as e:
        logger.debug("Subagent archive timer restore skipped: %s", e)
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
        settings = get_settings()
        max_concurrent = max(1, int(getattr(settings, "asta_subagents_max_concurrent", 3) or 3))
        max_depth = max(1, int(getattr(settings, "asta_subagents_max_depth", 1) or 1))
        max_children = max(1, int(getattr(settings, "asta_subagents_max_children", 5) or 5))
        return _json(
            {
                "agents": [{"id": "main", "label": "Asta (single-user)"}],
                "count": 1,
                "maxConcurrent": max_concurrent,
                "maxDepth": max_depth,
                "maxChildren": max_children,
            }
        )

    if name == "sessions_spawn":
        payload = await spawn_subagent_run(
            user_id=user_id,
            parent_conversation_id=parent_conversation_id,
            task=(params.get("task") or "").strip(),
            label=(params.get("label") or "").strip() or None,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
            model_override=(params.get("model") or "").strip() or None,
            thinking_override=params.get("thinking"),
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
                    "archivedAt": row.get("archived_at"),
                    "model": row.get("model_override"),
                    "thinking": row.get("thinking_override"),
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
                "label": row.get("label") or row.get("task") or "",
                "model": row.get("model_override"),
                "thinking": row.get("thinking_override"),
                "childSessionKey": row.get("child_conversation_id"),
                "createdAt": row.get("created_at"),
                "startedAt": row.get("started_at"),
                "endedAt": row.get("ended_at"),
                "archivedAt": row.get("archived_at"),
                "messages": messages,
            }
        )

    if name == "sessions_send":
        run_id = (params.get("runId") or "").strip()
        session_key = (params.get("sessionKey") or "").strip()
        message = (params.get("message") or "").strip()
        # Default to 30s like OpenClaw — LLM waits briefly then moves on; agent continues in background
        raw_timeout = params.get("timeoutSeconds")
        timeout_seconds = _normalize_timeout(raw_timeout) if raw_timeout is not None else 30
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
                model_override=(row.get("model_override") or "").strip() or None,
                thinking_override=(row.get("thinking_override") or "").strip() or None,
            )

        send_task = asyncio.create_task(_send(), name=f"subagent-send:{row['run_id']}")
        if timeout_seconds > 0:
            try:
                await asyncio.wait_for(asyncio.shield(send_task), timeout=timeout_seconds)
                # Best-effort: return the latest assistant content from child session.
                messages = await db.get_recent_messages(row["child_conversation_id"], limit=20)
                reply = ""
                for m in reversed(messages):
                    if (m.get("role") or "").strip().lower() != "assistant":
                        continue
                    content = (m.get("content") or "").strip()
                    if content:
                        reply = content
                        break
                return _json(
                    {
                        "status": "completed",
                        "runId": row.get("run_id"),
                        "childSessionKey": row.get("child_conversation_id"),
                        "reply": reply,
                        "waitedSeconds": timeout_seconds,
                    }
                )
            except asyncio.TimeoutError:
                return _json(
                    {
                        "status": "timeout",
                        "runId": row.get("run_id"),
                        "childSessionKey": row.get("child_conversation_id"),
                        "waitedSeconds": timeout_seconds,
                    }
                )
            except Exception as e:
                return _json(
                    {
                        "status": "error",
                        "runId": row.get("run_id"),
                        "childSessionKey": row.get("child_conversation_id"),
                        "error": str(e)[:500],
                    }
                )

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
