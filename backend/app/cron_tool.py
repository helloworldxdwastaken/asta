"""Structured cron tool (OpenClaw-style action API, simplified)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.cron_runner import (
    CRON_JOB_PREFIX,
    add_cron_job_to_scheduler,
    reload_cron_jobs,
    run_cron_job_now,
)
from app.tasks.scheduler import get_scheduler

if TYPE_CHECKING:
    from app.db import Db


_CRON_ACTIONS = ("status", "list", "add", "update", "remove", "run", "runs", "wake")
_CRON_WAKE_MODES = ("now", "next-heartbeat")
_CRON_RUN_MODES = ("due", "force")


def get_cron_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "cron",
                "description": (
                    "Manage recurring cron jobs. "
                    "Actions: status, list, add, update, remove, run, runs, wake. "
                    "Use for recurring schedules like daily/weekly reminders."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": list(_CRON_ACTIONS),
                        },
                        "id": {"type": "integer", "description": "Cron job id (update/remove/run/runs)."},
                        "jobId": {"type": "integer", "description": "Alias for id (run/runs/update/remove)."},
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
                        "job": {
                            "type": "object",
                            "description": "Optional nested job object (flattened add recovery).",
                        },
                        "patch": {
                            "type": "object",
                            "description": "Optional nested patch object (update recovery).",
                        },
                        "runMode": {
                            "type": "string",
                            "enum": list(_CRON_RUN_MODES),
                            "description": "Run mode for action=run: due or force (default force).",
                        },
                        "mode": {
                            "type": "string",
                            "enum": list(_CRON_WAKE_MODES),
                            "description": "Wake mode for action=wake: now or next-heartbeat.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Optional wake text metadata.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max run history rows for action=runs (1-100, default 20).",
                        },
                        "channel": {
                            "type": "string",
                            "enum": ["web", "telegram"],
                            "description": "Notification channel (default web).",
                        },
                        "channel_target": {
                            "type": "string",
                            "description": "Target ID for channel (chat_id for telegram). Optional if only 1 allowed user.",
                        },
                        "tlg_call": {
                            "type": "boolean",
                            "description": "Whether to trigger a voice call (Pingram) for this job. Defaults to true if a phone number is set in settings.",
                        },
                    },
                    "required": ["action"],
                },
            },
        }
    ]


def _parse_inline_args(raw: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for m in re.finditer(
        r"""([A-Za-z_][\w\-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^,\]]+))""",
        raw or "",
    ):
        key = (m.group(1) or "").strip()
        if not key:
            continue
        args[key] = (m.group(2) or m.group(3) or m.group(4) or "").strip()
    return args


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and float(value).is_integer():
        return int(value)
    if isinstance(value, str):
        v = value.strip()
        if v.isdigit():
            return int(v)
    return None


def _pick_first(record: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in record and record.get(key) is not None:
            return record.get(key)
    return None


def _to_str(value) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_add_from_job(job_obj: dict) -> dict:
    out: dict[str, object] = {}
    name = _to_str(_pick_first(job_obj, ("name", "job_name", "jobName", "title")))
    if name:
        out["name"] = name
    cron_expr = _to_str(_pick_first(job_obj, ("cron_expr", "cron", "expr", "cronExpr")))
    tz = _to_str(_pick_first(job_obj, ("tz", "timezone")))
    message = _to_str(_pick_first(job_obj, ("message", "msg", "text")))

    schedule = job_obj.get("schedule")
    if isinstance(schedule, dict):
        schedule_kind = _to_str(schedule.get("kind")).lower()
        if schedule_kind == "cron":
            cron_expr = _to_str(_pick_first(schedule, ("expr", "cron_expr", "cron", "cronExpr"))) or cron_expr
            tz = _to_str(_pick_first(schedule, ("tz", "timezone"))) or tz
        elif schedule_kind:
            out["schedule_kind"] = schedule_kind

    payload = job_obj.get("payload")
    if isinstance(payload, dict):
        payload_kind = _to_str(payload.get("kind")).lower()
        if payload_kind == "systemevent":
            message = _to_str(_pick_first(payload, ("text", "message"))) or message
        elif payload_kind == "agentturn":
            message = _to_str(_pick_first(payload, ("message", "text"))) or message
        elif payload_kind:
            out["payload_kind"] = payload_kind

    if cron_expr:
        out["cron_expr"] = cron_expr
    if tz:
        out["tz"] = tz
    if message:
        out["message"] = message
    return out


def _normalize_cron_params(raw: dict) -> dict:
    params = dict(raw or {})
    action = _to_str(params.get("action")).lower()
    if action not in _CRON_ACTIONS:
        return params
    out: dict[str, object] = {"action": action}

    if action == "add":
        job_obj = params.get("job")
        if isinstance(job_obj, dict):
            out.update(_normalize_add_from_job(job_obj))

        name = _to_str(_pick_first(params, ("name", "jobName", "job_name", "title")))
        cron_expr = _to_str(_pick_first(params, ("cron_expr", "cron", "expr", "cronExpr")))
        tz = _to_str(_pick_first(params, ("tz", "timezone")))
        message = _to_str(_pick_first(params, ("message", "msg", "text")))

        if name:
            out["name"] = name
        if cron_expr:
            out["cron_expr"] = cron_expr
        if tz:
            out["tz"] = tz
        if message:
            out["message"] = message
            
        channel = _to_str(_pick_first(params, ("channel", "chn")))
        target = _to_str(_pick_first(params, ("channel_target", "target", "chat_id")))
        if channel:
            out["channel"] = channel
        if target:
            out["channel_target"] = target
            
        payload_kind = _to_str(_pick_first(params, ("payload_kind", "payloadKind", "kind")))
        if payload_kind:
            out["payload_kind"] = payload_kind.lower()
            
        tlg_call = _pick_first(params, ("tlg_call", "tlgCall", "call"))
        if tlg_call is not None:
            if isinstance(tlg_call, str):
                v = tlg_call.strip().lower()
                out["tlg_call"] = 1 if v in ("1", "true", "on", "yes") else 0
            else:
                out["tlg_call"] = 1 if tlg_call else 0

        return out

    if action == "update":
        job_id = _as_int(_pick_first(params, ("id", "jobId")))
        if job_id is not None:
            out["id"] = job_id
        patch = params.get("patch")
        if isinstance(patch, dict):
            patch_norm = _normalize_add_from_job(patch)
            for key in ("name", "cron_expr", "tz", "message"):
                v = patch_norm.get(key)
                if isinstance(v, str) and v.strip():
                    out[key] = v.strip()
        for key_group, target_key in (
            (("name", "jobName", "job_name", "title"), "name"),
            (("cron_expr", "cron", "expr", "cronExpr"), "cron_expr"),
            (("tz", "timezone"), "tz"),
            (("message", "msg", "text"), "message"),
            (("channel", "chn"), "channel"),
            (("channel_target", "target", "chat_id"), "channel_target"),
            (("payload_kind", "payloadKind", "kind"), "payload_kind"),
        ):
            value = _to_str(_pick_first(params, key_group))
            if value:
                out[target_key] = value
        
        enabled = params.get("enabled")
        if enabled is not None:
            if isinstance(enabled, str):
                v = enabled.strip().lower()
                out["enabled"] = 1 if v in ("1", "true", "on", "yes") else 0
            else:
                out["enabled"] = 1 if enabled else 0

        tlg_call = params.get("tlg_call")
        if tlg_call is not None:
            if isinstance(tlg_call, str):
                v = tlg_call.strip().lower()
                out["tlg_call"] = 1 if v in ("1", "true", "on", "yes") else 0
            else:
                out["tlg_call"] = 1 if tlg_call else 0
        return out

    if action == "remove":
        job_id = _as_int(_pick_first(params, ("id", "jobId")))
        if job_id is not None:
            out["id"] = job_id
        name = _to_str(params.get("name"))
        if name:
            out["name"] = name
        return out

    if action == "run":
        job_id = _as_int(_pick_first(params, ("id", "jobId")))
        if job_id is not None:
            out["id"] = job_id
        run_mode = _to_str(_pick_first(params, ("runMode", "run_mode", "mode"))).lower()
        if run_mode in _CRON_RUN_MODES:
            out["run_mode"] = run_mode
        return out

    if action == "runs":
        job_id = _as_int(_pick_first(params, ("id", "jobId")))
        if job_id is not None:
            out["id"] = job_id
        limit = _as_int(params.get("limit"))
        if limit is not None:
            out["limit"] = max(1, min(limit, 100))
        return out

    if action == "wake":
        mode = _to_str(params.get("mode")).lower()
        if mode in _CRON_WAKE_MODES:
            out["mode"] = mode
        text = _to_str(params.get("text"))
        if text:
            out["text"] = text
        return out

    return out


def parse_cron_tool_args(arguments_str: str | dict) -> dict:
    if isinstance(arguments_str, dict):
        return _normalize_cron_params(arguments_str)
    try:
        data = json.loads(arguments_str)
        if isinstance(data, dict):
            return _normalize_cron_params(data)
    except (json.JSONDecodeError, TypeError):
        pass

    if isinstance(arguments_str, str):
        inline = _parse_inline_args(arguments_str)
        if inline:
            return _normalize_cron_params(inline)
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
    params = _normalize_cron_params(params)
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
        schedule_kind = (params.get("schedule_kind") or "").strip().lower()
        payload_kind = (params.get("payload_kind") or "").strip().lower()
        if schedule_kind and schedule_kind != "cron":
            return "Error: add only supports cron schedule.kind='cron' in Asta."
        if payload_kind and payload_kind not in ("systemevent", "agentturn"):
            return f"Error: unsupported payload kind '{payload_kind}' for cron add."
        if not name or not cron_expr or not message:
            return "Error: add requires `name`, `cron_expr`, and `message`."

        # Validate cron expression before adding
        from app.db import validate_cron_expression
        is_valid, error_msg = validate_cron_expression(cron_expr, tz)
        if not is_valid:
            return f"Error: Invalid cron expression: {error_msg}"

        # Resolve channel/target
        req_channel = (params.get("channel") or "").strip().lower() or channel
        req_target = (params.get("channel_target") or "").strip() or channel_target
        
        if req_channel == "telegram" and not req_target:
            from app.config import get_settings
            settings = get_settings()
            allowed = list(settings.telegram_allowed_ids)
            if len(allowed) == 1:
                req_target = allowed[0]

        from app.config import get_settings
        s = get_settings()
        owner_phone = getattr(s, "asta_owner_phone_number", None)
        
        # Default tlg_call to True if phone number is set
        default_call = bool(owner_phone)
        tlg_call = params.get("tlg_call")
        if tlg_call is None:
            tlg_call = default_call
            
        # If call is requested but no number in target, use owner_phone
        if tlg_call and owner_phone and not (req_target and (str(req_target).startswith("+") or str(req_target).isdigit())):
            req_target = owner_phone

        job_id = await db.add_cron_job(
            user_id,
            name,
            cron_expr,
            message,
            tz=tz,
            channel=req_channel,
            channel_target=req_target,
            payload_kind=payload_kind or "agentturn",
            tlg_call=bool(tlg_call),
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
                "channel": req_channel,
                "channel_target": req_target,
            },
            indent=0,
        )

    if action == "update":
        job_id = _as_int(params.get("id"))
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

        new_channel = params.get("channel")
        new_target = params.get("channel_target")
        new_payload_kind = params.get("payload_kind")
        new_enabled = params.get("enabled")
        new_tlg_call = params.get("tlg_call")
        
        # If switching to telegram without target, try to infer it
        if new_channel == "telegram" and not new_target:
             from app.config import get_settings
             settings = get_settings()
             allowed = list(settings.telegram_allowed_ids)
             if len(allowed) == 1:
                 new_target = allowed[0]

        ok = await db.update_cron_job(
            job_id,
            name=name,
            cron_expr=cron_expr,
            tz=tz,
            message=message,
            channel=new_channel,
            channel_target=new_target,
            payload_kind=new_payload_kind,
            enabled=new_enabled,
            tlg_call=new_tlg_call
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
        job_id = _as_int(params.get("id"))
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

    if action == "run":
        job_id = _as_int(params.get("id"))
        if not isinstance(job_id, int) or job_id <= 0:
            return "Error: run requires integer `id`."
        row = await db.get_cron_job(job_id)
        if not row or (row.get("user_id") or "") != user_id:
            return f"Error: cron job id {job_id} not found."
        run_mode = (params.get("run_mode") or "force").strip().lower()
        if run_mode not in _CRON_RUN_MODES:
            run_mode = "force"
        if run_mode == "due":
            sched_id = f"{CRON_JOB_PREFIX}{job_id}"
            sched_job = sch.get_job(sched_id)
            next_run_at = getattr(sched_job, "next_run_time", None) if sched_job else None
            now_utc = datetime.now(timezone.utc)
            if next_run_at is None or next_run_at > now_utc:
                await db.add_cron_job_run(
                    cron_job_id=job_id,
                    user_id=user_id,
                    trigger="manual",
                    run_mode="due",
                    status="skipped_not_due",
                    output="Cron run skipped because next run is not due yet.",
                )
                return json.dumps(
                    {
                        "ok": False,
                        "id": job_id,
                        "status": "skipped_not_due",
                        "run_mode": "due",
                        "next_run_at": next_run_at.isoformat() if next_run_at else None,
                    },
                    indent=0,
                )
        result = await run_cron_job_now(job_id, run_mode=run_mode)
        return json.dumps(result, indent=0)

    if action == "runs":
        job_id = _as_int(params.get("id"))
        if not isinstance(job_id, int) or job_id <= 0:
            return "Error: runs requires integer `id`."
        row = await db.get_cron_job(job_id)
        if not row or (row.get("user_id") or "") != user_id:
            return f"Error: cron job id {job_id} not found."
        limit = _as_int(params.get("limit")) or 20
        runs = await db.get_cron_job_runs(user_id=user_id, cron_job_id=job_id, limit=limit)
        return json.dumps({"job_id": job_id, "runs": runs}, indent=0)

    if action == "wake":
        mode = (params.get("mode") or "next-heartbeat").strip().lower()
        if mode not in _CRON_WAKE_MODES:
            mode = "next-heartbeat"
        text = (params.get("text") or "").strip()
        if mode == "now":
            await reload_cron_jobs()
        cron_jobs = [j for j in sch.get_jobs() if (j.id or "").startswith(CRON_JOB_PREFIX)]
        return json.dumps(
            {
                "ok": True,
                "mode": mode,
                "scheduler_running": bool(getattr(sch, "running", False)),
                "scheduled_cron_jobs": len(cron_jobs),
                "text": text or None,
            },
            indent=0,
        )

    return "Error: unknown action. Use one of: status, list, add, update, remove, run, runs, wake."
