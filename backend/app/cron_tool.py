"""Structured cron tool (OpenClaw-style action API, simplified)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.cron_runner import CRON_JOB_PREFIX, add_cron_job_to_scheduler
from app.tasks.scheduler import get_scheduler

if TYPE_CHECKING:
    from app.db import Db


def get_cron_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "cron",
                "description": (
                    "Manage recurring cron jobs. "
                    "Actions: status, list, add, update, remove. "
                    "Use for recurring schedules like daily/weekly reminders."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["status", "list", "add", "update", "remove"],
                        },
                        "id": {"type": "integer", "description": "Cron job id for update/remove."},
                        "name": {"type": "string", "description": "Cron job name."},
                        "cron_expr": {
                            "type": "string",
                            "description": "5-field cron expression (minute hour day month day_of_week).",
                        },
                        "tz": {
                            "type": "string",
                            "description": "Optional IANA timezone, e.g. America/Los_Angeles.",
                        },
                        "message": {
                            "type": "string",
                            "description": "Message to run when cron triggers.",
                        },
                    },
                    "required": ["action"],
                },
            },
        }
    ]


def parse_cron_tool_args(arguments_str: str | dict) -> dict:
    if isinstance(arguments_str, dict):
        return arguments_str
    try:
        data = json.loads(arguments_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def run_cron_tool(
    params: dict,
    *,
    user_id: str,
    channel: str,
    channel_target: str,
    db: "Db",
) -> str:
    action = (params.get("action") or "").strip().lower()
    await db.connect()
    sch = get_scheduler()

    if action == "status":
        cron_jobs = [j for j in sch.get_jobs() if (j.id or "").startswith(CRON_JOB_PREFIX)]
        return json.dumps(
            {
                "scheduler_running": bool(getattr(sch, "running", False)),
                "scheduled_cron_jobs": len(cron_jobs),
            },
            indent=0,
        )

    if action == "list":
        rows = await db.get_cron_jobs(user_id)
        return json.dumps({"cron_jobs": rows}, indent=0)

    if action == "add":
        name = (params.get("name") or "").strip()
        cron_expr = (params.get("cron_expr") or "").strip()
        message = (params.get("message") or "").strip()
        tz = (params.get("tz") or "").strip() or None
        if not name or not cron_expr or not message:
            return "Error: add requires `name`, `cron_expr`, and `message`."

        # Validate cron expression before adding
        from app.db import validate_cron_expression
        is_valid, error_msg = validate_cron_expression(cron_expr, tz)
        if not is_valid:
            return f"Error: Invalid cron expression: {error_msg}"

        job_id = await db.add_cron_job(
            user_id,
            name,
            cron_expr,
            message,
            tz=tz,
            channel=channel,
            channel_target=channel_target or "",
        )
        add_cron_job_to_scheduler(sch, job_id, cron_expr, tz)
        return json.dumps(
            {
                "ok": True,
                "id": job_id,
                "name": name,
                "cron_expr": cron_expr,
                "tz": tz,
                "message": message,
            },
            indent=0,
        )

    if action == "update":
        job_id = params.get("id")
        if not isinstance(job_id, int) or job_id <= 0:
            return "Error: update requires integer `id`."
        name = (params.get("name") or "").strip() or None
        cron_expr = (params.get("cron_expr") or "").strip() or None
        message = (params.get("message") or "").strip() or None
        tz = (params.get("tz") or "").strip() or None

        if cron_expr is not None:
            from app.db import validate_cron_expression

            is_valid, error_msg = validate_cron_expression(cron_expr, tz)
            if not is_valid:
                return f"Error: Invalid cron expression: {error_msg}"

        ok = await db.update_cron_job(
            job_id,
            name=name,
            cron_expr=cron_expr,
            tz=tz,
            message=message,
        )
        if not ok:
            return (
                f"Error: could not update cron job id {job_id}. "
                "It may not exist, or the new name conflicts with another cron job."
            )
        updated = await db.get_cron_job(job_id)
        if not updated:
            return f"Error: cron job id {job_id} not found."
        sched_id = f"{CRON_JOB_PREFIX}{job_id}"
        if sch.get_job(sched_id):
            sch.remove_job(sched_id)
        expr = (updated.get("cron_expr") or "").strip()
        tz_now = (updated.get("tz") or "").strip() or None
        if expr:
            add_cron_job_to_scheduler(sch, job_id, expr, tz_now)
        return json.dumps({"ok": True, "job": updated}, indent=0)

    if action == "remove":
        job_id = params.get("id")
        name = (params.get("name") or "").strip()
        removed = False
        removed_ids: list[int] = []
        if isinstance(job_id, int) and job_id > 0:
            removed = await db.delete_cron_job(job_id)
            if removed:
                removed_ids.append(job_id)
        elif name:
            jobs = await db.get_cron_jobs(user_id)
            removed_ids = [int(j["id"]) for j in jobs if (j.get("name") or "").strip() == name]
            removed = await db.delete_cron_job_by_name(user_id, name)
        else:
            return "Error: remove requires `id` or `name`."

        for rid in removed_ids:
            sched_id = f"{CRON_JOB_PREFIX}{rid}"
            if sch.get_job(sched_id):
                sch.remove_job(sched_id)
        return json.dumps({"ok": bool(removed), "removed_ids": removed_ids}, indent=0)

    return "Error: unknown action. Use one of: status, list, add, update, remove."
