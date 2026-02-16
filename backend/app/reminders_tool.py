"""Structured reminders tool (OpenClaw-style action API)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.reminders import parse_reminder, schedule_reminder
from app.services.reminder_service import _get_effective_location, _is_absolute_time_reminder
from app.time_weather import get_timezone_for_coords

if TYPE_CHECKING:
    from app.db import Db


def get_reminders_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "reminders",
                "description": (
                    "Manage one-time reminders. "
                    "Actions: status, list, add, update, remove. "
                    "Use add with `text` for natural language (e.g. 'remind me in 30 min to call mom')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["status", "list", "add", "update", "remove"],
                        },
                        "text": {
                            "type": "string",
                            "description": "Natural language reminder text for add action.",
                        },
                        "message": {
                            "type": "string",
                            "description": "Reminder message when using explicit run_at.",
                        },
                        "run_at": {
                            "type": "string",
                            "description": "ISO-8601 timestamp for explicit scheduling, e.g. 2026-02-14T20:00:00Z.",
                        },
                        "id": {
                            "type": "integer",
                            "description": "Reminder id for update/remove actions.",
                        },
                    },
                    "required": ["action"],
                },
            },
        }
    ]


def parse_reminders_tool_args(arguments_str: str | dict) -> dict:
    if isinstance(arguments_str, dict):
        return arguments_str
    try:
        data = json.loads(arguments_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_iso_utc(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


async def run_reminders_tool(
    params: dict,
    *,
    user_id: str,
    channel: str,
    channel_target: str,
    db: "Db",
) -> str:
    action = (params.get("action") or "").strip().lower()
    await db.connect()

    if action == "status":
        pending = await db.get_pending_reminders_for_user(user_id, limit=50)
        location = await db.get_user_location(user_id)
        payload = {
            "pending_count": len(pending),
            "next_reminder": pending[0] if pending else None,
            "location": (location or {}).get("location_name") if isinstance(location, dict) else None,
        }
        return json.dumps(payload, indent=0)

    if action == "list":
        rows = await db.get_notifications(user_id, limit=50)
        pending = [r for r in rows if (r.get("status") or "").lower() == "pending"]
        return json.dumps({"pending": pending}, indent=0)

    if action == "remove":
        reminder_id = params.get("id")
        if not isinstance(reminder_id, int) or reminder_id <= 0:
            return "Error: remove action requires integer `id`."
        deleted = await db.delete_reminder(reminder_id, user_id)
        try:
            from app.db import decode_one_shot_reminder_id
            from app.tasks.scheduler import get_scheduler

            sch = get_scheduler()
            # Legacy reminder jobs (pre-migration).
            legacy_job_id = f"rem_{reminder_id}"
            if sch.get_job(legacy_job_id):
                sch.remove_job(legacy_job_id)
            # One-shot cron-backed reminders.
            one_shot_id = decode_one_shot_reminder_id(reminder_id)
            if one_shot_id is not None:
                cron_job_id = f"cron_{one_shot_id}"
                if sch.get_job(cron_job_id):
                    sch.remove_job(cron_job_id)
        except Exception:
            pass
        return json.dumps({"ok": bool(deleted), "removed_id": reminder_id}, indent=0)

    if action == "update":
        reminder_id = params.get("id")
        if not isinstance(reminder_id, int) or reminder_id <= 0:
            return "Error: update action requires integer `id`."

        text = (params.get("text") or "").strip()
        message = (params.get("message") or "").strip()
        run_at_raw = (params.get("run_at") or "").strip()
        if not text and not message and not run_at_raw:
            return "Error: update action requires at least one of `text`, `message`, or `run_at`."

        resolved_message: str | None = None
        resolved_run_at_iso: str | None = None
        display_time: str | None = None

        if text:
            tz_str: str | None = None
            loc = await _get_effective_location(user_id)
            if loc:
                tz_str = await get_timezone_for_coords(
                    loc["latitude"], loc["longitude"], loc.get("location_name")
                )
            if not tz_str and _is_absolute_time_reminder(text):
                return (
                    "Error: absolute-time reminder requires location/timezone. "
                    "Ask the user for their location first."
                )
            parsed = parse_reminder(text, tz_str=tz_str)
            if not parsed:
                return (
                    "Error: could not parse reminder text for update. "
                    "Try formats like 'remind me in 30 min to call mom' or "
                    "'wake me up tomorrow at 7am'."
                )
            resolved_message = parsed.get("message", "Reminder")
            resolved_run_at_iso = parsed["run_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            display_time = parsed.get("display_time")

        if run_at_raw:
            run_at = _parse_iso_utc(run_at_raw)
            if run_at is None:
                return "Error: invalid `run_at` timestamp. Use ISO-8601 format, e.g. 2026-02-14T20:00:00Z."
            if run_at <= datetime.now(timezone.utc):
                return "Error: run_at must be in the future."
            resolved_run_at_iso = run_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if message:
            resolved_message = message

        ok = await db.update_reminder(
            reminder_id,
            user_id,
            message=resolved_message,
            run_at=resolved_run_at_iso,
        )
        if not ok:
            return f"Error: reminder id {reminder_id} not found (or update failed)."

        # Keep scheduler in sync after DB update.
        try:
            from app.cron_runner import add_cron_job_to_scheduler
            from app.db import decode_one_shot_reminder_id, run_at_to_one_shot_cron_expr
            from app.tasks.scheduler import get_scheduler

            sch = get_scheduler()
            one_shot_id = decode_one_shot_reminder_id(reminder_id)
            legacy_job_id = f"rem_{reminder_id}"
            if sch.get_job(legacy_job_id):
                sch.remove_job(legacy_job_id)

            if one_shot_id is not None:
                cron_job_id = f"cron_{one_shot_id}"
                if sch.get_job(cron_job_id):
                    sch.remove_job(cron_job_id)
                pending = await db.get_pending_reminders_for_user(user_id, limit=200)
                updated = next(
                    (r for r in pending if int(r.get("id") or 0) == reminder_id),
                    None,
                )
                if updated and updated.get("run_at"):
                    add_cron_job_to_scheduler(
                        sch,
                        one_shot_id,
                        run_at_to_one_shot_cron_expr(str(updated["run_at"])),
                        None,
                    )
        except Exception:
            pass

        pending = await db.get_pending_reminders_for_user(user_id, limit=200)
        updated = next((r for r in pending if int(r.get("id") or 0) == reminder_id), None)
        payload = {
            "ok": True,
            "id": reminder_id,
            "message": (updated or {}).get("message") or resolved_message or "Reminder",
            "run_at": (updated or {}).get("run_at") or resolved_run_at_iso,
        }
        if display_time:
            payload["display_time"] = display_time
        return json.dumps(payload, indent=0)

    if action == "add":
        text = (params.get("text") or "").strip()
        message = (params.get("message") or "").strip()
        run_at_raw = (params.get("run_at") or "").strip()

        if run_at_raw:
            run_at = _parse_iso_utc(run_at_raw)
            if run_at is None:
                return "Error: invalid `run_at` timestamp. Use ISO-8601 format, e.g. 2026-02-14T20:00:00Z."
            if run_at <= datetime.now(timezone.utc):
                return "Error: run_at must be in the future."
            reminder_message = message or "Reminder"
            target = channel_target or "web"
            reminder_id = await schedule_reminder(user_id, channel, target, reminder_message, run_at)
            return json.dumps(
                {
                    "ok": True,
                    "id": reminder_id,
                    "message": reminder_message,
                    "run_at": run_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                indent=0,
            )

        if not text:
            return "Error: add action requires either `text` or (`message` + `run_at`)."

        tz_str: str | None = None
        loc = await _get_effective_location(user_id)
        if loc:
            tz_str = await get_timezone_for_coords(
                loc["latitude"], loc["longitude"], loc.get("location_name")
            )
        if not tz_str and _is_absolute_time_reminder(text):
            return (
                "Error: absolute-time reminder requires location/timezone. "
                "Ask the user for their location first."
            )

        parsed = parse_reminder(text, tz_str=tz_str)
        if not parsed:
            return (
                "Error: could not parse reminder text. "
                "Try formats like 'remind me in 30 min to call mom' or "
                "'wake me up tomorrow at 7am'."
            )

        run_at = parsed["run_at"]
        reminder_message = parsed.get("message", "Reminder")
        target = channel_target or "web"
        reminder_id = await schedule_reminder(user_id, channel, target, reminder_message, run_at)
        return json.dumps(
            {
                "ok": True,
                "id": reminder_id,
                "message": reminder_message,
                "run_at": run_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "display_time": parsed.get("display_time"),
            },
            indent=0,
        )

    return "Error: unknown action. Use one of: status, list, add, update, remove."
