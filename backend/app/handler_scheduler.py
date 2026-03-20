"""Scheduler / reminder helper functions extracted from handler.py."""

import re
import json
import logging
from typing import Any

from app.tool_call_parser import _build_tool_trace_label

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent detection helpers
# ---------------------------------------------------------------------------

def _looks_like_reminder_set_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # List/status questions should not schedule.
    if any(
        q in t for q in (
            "do i have reminder",
            "do i have any reminder",
            "what reminders",
            "list reminders",
            "show reminders",
            "pending reminders",
            "any reminders",
        )
    ):
        return False
    return any(
        k in t for k in (
            "remind me",
            "set reminder",
            "set a reminder",
            "alarm at",
            "alarm for",
            "set alarm",
            "set an alarm",
            "wake me up",
            "set timer",
            "timer for",
        )
    )


def _looks_like_reminder_list_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # Natural "task" wording and common typo ("tast") should still list reminders.
    if any(k in t for k in ("tasks", "task", "tast")) and any(k in t for k in ("reminder", "alarm")):
        return True
    return any(
        k in t
        for k in (
            "what reminders",
            "list reminders",
            "show reminders",
            "do i have any reminders",
            "do i have reminders",
            "pending reminders",
            "what reminder",
        )
    )


def _looks_like_cron_list_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if "cron" in t:
        return any(
            k in t
            for k in (
                "what",
                "list",
                "show",
                "have",
                "status",
                "jobs",
                "tasks",
            )
        )
    return False


def _looks_like_schedule_overview_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if "schedule" in t and any(k in t for k in ("what", "have", "list", "show")):
        return True
    if "pending" in t and any(k in t for k in ("task", "tasks", "tast")) and any(
        k in t for k in ("what", "have", "list", "show", "do i have", "any")
    ):
        return True
    if "reminder" in t and "cron" in t and any(k in t for k in ("what", "have", "list", "show", "do i have")):
        return True
    if any(k in t for k in ("task", "tasks", "tast")) and "reminder" in t and any(
        k in t for k in ("what", "have", "list", "show", "do i have")
    ):
        return True
    return any(
        k in t
        for k in (
            "what tasks do i have",
            "what task do i have",
            "do i have any task",
            "do i have any tasks",
            "any pending task",
            "any pending tasks",
            "do i have any pending task",
            "do i have any pending tasks",
            "what reminders and cron",
            "what reminders or cron",
        )
    )


def _looks_like_remove_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in ("remove", "delete", "cancel"):
        return True
    if any(t.startswith(prefix) for prefix in ("remove this", "delete this", "cancel this", "remove that", "delete that", "cancel that")):
        return True
    if re.search(r"\b(?:remove|delete|cancel)\b", t):
        return True
    return any(
        t.startswith(prefix)
        for prefix in (
            "remove ",
            "delete ",
            "cancel ",
        )
    )


def _looks_like_update_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if re.search(r"\b(?:update|edit|change|rename|reschedule|move)\b", t):
        return True
    # Common typo ("esit" for "edit").
    if "esit" in t:
        return True
    return False


def _extract_new_name(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    patterns = (
        r"(?:should\s+be\s+called|be\s+called)\s+(.+)$",
        r"(?:rename(?:\s+it)?\s+to|change\s+name\s+to|name(?:\s+it)?\s+to)\s+(.+)$",
    )
    for pat in patterns:
        m = re.search(pat, raw, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = (m.group(1) or "").strip().strip("\"'`").strip(" .?!,")
        if candidate:
            return candidate[:120]
    return None


def _extract_inline_cron_expr(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(
        r"\b([\d\*/,\-]+\s+[\d\*/,\-]+\s+[\d\*/,\-]+\s+[\d\*/,\-]+\s+[\d\*/,\-]+)\b",
        raw,
    )
    if not m:
        return None
    expr = (m.group(1) or "").strip()
    return expr or None


def _match_cron_id_by_name(text: str, cron_rows: list[dict]) -> int | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    # Prefer longest-name match first to avoid substring collisions.
    rows = sorted(
        [r for r in cron_rows if isinstance(r, dict)],
        key=lambda r: len(str(r.get("name") or "")),
        reverse=True,
    )
    for row in rows:
        name = (row.get("name") or "").strip().lower()
        if not name:
            continue
        if name in t:
            try:
                return int(row.get("id") or 0)
            except Exception:
                return None
    return None


def _extract_update_payload_text(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"\bto\s+(.+)$", raw, flags=re.IGNORECASE)
    if not m:
        return None
    candidate = (m.group(1) or "").strip().strip("\"'`").strip(" .?!,")
    return candidate or None


def _extract_target_id(text: str) -> int | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    m = re.search(r"(?:id|#)\s*(\d+)\b", t)
    if m:
        return int(m.group(1))
    # Avoid treating times like "9am" / "18:30" as ids in phrases like
    # "delete this reminder at 9am".
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", t):
        return None
    if re.search(r"\b\d{1,2}:\d{2}\b", t):
        return None
    nums = re.findall(r"\b\d+\b", t)
    # Implicit numeric id only for short commands like "remove 2".
    if len(nums) == 1 and len(t.split()) <= 4:
        return int(nums[0])
    return None


# ---------------------------------------------------------------------------
# Cron protocol extraction helpers
# ---------------------------------------------------------------------------

def _extract_textual_cron_add_protocol(reply: str) -> tuple[dict[str, str] | None, str]:
    raw = reply or ""
    if not raw.strip():
        return None, raw
    m = re.search(r"(?im)^\s*CRON\s+ACTION\s*=\s*add\b(?P<body>.*)$", raw)
    if not m:
        return None, raw
    body = (m.group("body") or "").strip()
    body = re.sub(r"\s+", " ", body)

    name = ""
    cron_expr = ""
    tz = ""
    message = ""

    m_name = re.search(
        r"(?is)\bname\b\s*[:=]?\s*(.+?)(?=\s+\b(?:cron(?:_expr| expr|expr)|tz|message|msg)\b|$)",
        body,
    )
    if m_name:
        name = (m_name.group(1) or "").strip(" \"'`")

    m_cron = re.search(
        r"(?is)\bcron(?:_expr| expr|expr)?\b\s*[:=]?\s*([^\n]+?)(?=\s+\b(?:tz|message|msg)\b|$)",
        body,
    )
    if m_cron:
        cron_raw = (m_cron.group(1) or "").strip()
        cron_expr = _extract_cron_expr_from_text(cron_raw)

    m_tz = re.search(r"(?is)\btz\b\s*[:=]?\s*([A-Za-z0-9_/\-+]+)", body)
    if m_tz:
        tz = (m_tz.group(1) or "").strip()

    m_msg = re.search(r"(?is)\b(?:message|msg)\b\s*[:=]?\s*(.+)$", body)
    if m_msg:
        message = (m_msg.group(1) or "").strip(" \"'`")

    cleaned = re.sub(r"(?im)^\s*CRON\s+ACTION\s*=\s*add\b.*$", "", raw).strip()
    if not name or not cron_expr:
        return None, cleaned
    return {
        "action": "add",
        "name": name,
        "cron_expr": cron_expr,
        "tz": tz,
        "message": message or "Reminder",
    }, cleaned


def _extract_proto_value(body: str, key: str) -> str:
    pat = re.compile(
        rf"(?is)\b{re.escape(key)}\b\s*[:=]\s*(?:\"([^\"]*)\"|'([^']*)'|([^,\]\n]+))"
    )
    m = pat.search(body or "")
    if not m:
        return ""
    return (m.group(1) or m.group(2) or m.group(3) or "").strip()


def _extract_cron_expr_from_text(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    # Accept common cron tokens including ranges/lists/steps and weekday/month names.
    m = re.search(
        r"(?i)(?<!\S)([0-9a-z*/,\-]+(?:\s+[0-9a-z*/,\-]+){4})(?!\S)",
        raw,
    )
    if not m:
        return ""
    return (m.group(1) or "").strip()


def _extract_bracket_cron_add_protocols(reply: str) -> tuple[list[dict[str, str]], str]:
    raw = reply or ""
    if not raw.strip():
        return [], raw
    pattern = re.compile(r"(?is)\[\s*cron\s*:\s*([^\]]+)\]")
    matches = list(pattern.finditer(raw))
    if not matches:
        return [], raw

    payloads: list[dict[str, str]] = []
    for m in matches:
        body = (m.group(1) or "").strip()
        action = _extract_proto_value(body, "action").lower()
        if action and action != "add":
            continue
        name = _extract_proto_value(body, "name").strip(" \"'`")
        cron_raw = _extract_proto_value(body, "cron_expr") or _extract_proto_value(body, "cron")
        cron_expr = _extract_cron_expr_from_text(cron_raw)
        tz = _extract_proto_value(body, "tz").strip()
        message = _extract_proto_value(body, "message") or _extract_proto_value(body, "msg")
        message = message.strip(" \"'`")
        if name and cron_expr:
            payloads.append(
                {
                    "action": "add",
                    "name": name,
                    "cron_expr": cron_expr,
                    "tz": tz,
                    "message": message or "Reminder",
                }
            )

    cleaned = pattern.sub("", raw).strip()
    return payloads, cleaned


# ---------------------------------------------------------------------------
# Trace / DB helpers
# ---------------------------------------------------------------------------

def _get_trace_settings():
    from app.config import get_settings

    return get_settings()


async def _get_pending_reminder_rows(db, user_id: str) -> list[dict]:
    rows = await db.get_notifications(user_id, limit=50)
    return [r for r in rows if (r.get("status") or "").lower() == "pending"]


def _render_reminders_list_text(pending_rows: list[dict]) -> str:
    if not pending_rows:
        return "You have no pending reminders."
    lines = [f"You have {len(pending_rows)} pending reminder(s):"]
    for i, row in enumerate(pending_rows, 1):
        rid = row.get("id")
        msg = (row.get("message") or "Reminder").strip() or "Reminder"
        run_at = (row.get("run_at") or "").strip()
        lines.append(f"{i}. [id {rid}] {msg} - {run_at}")
    return "\n".join(lines)


def _render_cron_list_text(cron_rows: list[dict]) -> str:
    if not cron_rows:
        return "You have no cron jobs."
    lines = [f"You have {len(cron_rows)} cron job(s):"]
    for i, row in enumerate(cron_rows, 1):
        jid = row.get("id")
        name = (row.get("name") or "").strip() or "Unnamed"
        expr = (row.get("cron_expr") or "").strip()
        message = (row.get("message") or "").strip()
        lines.append(f"{i}. [id {jid}] {name} - {expr} - {message}")
    return "\n".join(lines)


async def _infer_remove_target_from_recent(db, conversation_id: str, current_text: str) -> str | None:
    recent = await db.get_recent_messages(conversation_id, limit=10)
    current_norm = (current_text or "").strip().lower()
    # Prefer previous user message intent.
    for m in reversed(recent):
        if (m.get("role") or "") != "user":
            continue
        c = (m.get("content") or "").strip().lower()
        if not c or c == current_norm:
            continue
        if any(k in c for k in ("reminder", "alarm", "timer")):
            return "reminder"
        if any(k in c for k in ("cron", "schedule", "cron job", "cron task")):
            return "cron"
    # Fallback to assistant wording.
    for m in reversed(recent):
        if (m.get("role") or "") != "assistant":
            continue
        c = (m.get("content") or "").strip().lower()
        if not c:
            continue
        if "pending reminder" in c or "[id " in c and "reminder" in c:
            return "reminder"
        if "cron job" in c:
            return "cron"
    return None


# ---------------------------------------------------------------------------
# Main scheduler intent handler
# ---------------------------------------------------------------------------

async def _handle_scheduler_intents(
    *,
    db,
    user_id: str,
    conversation_id: str,
    text: str,
    channel: str,
    channel_target: str,
    reminders_enabled: bool,
) -> tuple[str, str] | None:
    t = (text or "").strip().lower()
    if not t:
        return None

    if _looks_like_schedule_overview_request(t):
        pending = await _get_pending_reminder_rows(db, user_id) if reminders_enabled else []
        cron_rows = await db.get_cron_jobs(user_id)
        parts = []
        if reminders_enabled:
            parts.append(_render_reminders_list_text(pending))
        parts.append(_render_cron_list_text(cron_rows))
        return "\n\n".join(parts), _build_tool_trace_label("cron", "overview/fallback")

    if reminders_enabled and _looks_like_reminder_list_request(t):
        if any(k in t for k in ("task", "tasks", "tast", "cron", "schedule")):
            pending = await _get_pending_reminder_rows(db, user_id)
            cron_rows = await db.get_cron_jobs(user_id)
            return (
                _render_reminders_list_text(pending) + "\n\n" + _render_cron_list_text(cron_rows),
                _build_tool_trace_label("cron", "overview/fallback"),
            )
        pending = await _get_pending_reminder_rows(db, user_id)
        return _render_reminders_list_text(pending), _build_tool_trace_label("reminders", "list/fallback")

    if _looks_like_cron_list_request(t):
        cron_rows = await db.get_cron_jobs(user_id)
        return _render_cron_list_text(cron_rows), _build_tool_trace_label("cron", "list/fallback")

    pending = await _get_pending_reminder_rows(db, user_id) if reminders_enabled else []
    cron_rows = await db.get_cron_jobs(user_id)
    inferred_target = await _infer_remove_target_from_recent(db, conversation_id, text)
    has_scheduler_terms = any(k in t for k in ("reminder", "alarm", "timer", "cron", "schedule", "task"))

    target: str | None = None
    if any(k in t for k in ("reminder", "alarm", "timer")):
        target = "reminder"
    elif any(k in t for k in ("cron", "schedule", "cron job", "cron task")):
        target = "cron"
    else:
        target = inferred_target
        if not target:
            if reminders_enabled and len(pending) == 1:
                target = "reminder"
            elif len(cron_rows) == 1:
                target = "cron"

    target_id = _extract_target_id(t)
    if target is None and target_id is not None:
        if reminders_enabled and any(int(r.get("id") or 0) == int(target_id) for r in pending):
            target = "reminder"
        elif any(int(r.get("id") or 0) == int(target_id) for r in cron_rows):
            target = "cron"

    named_cron_id = _match_cron_id_by_name(text, cron_rows)
    if named_cron_id is not None and target_id is None:
        target_id = named_cron_id
        if target in (None, "cron") or (target == "reminder" and not pending):
            target = "cron"

    is_update = _looks_like_update_request(t)
    is_remove = _looks_like_remove_request(t)

    if is_update:
        # Let the model/tool loop handle compound requests like "edit and add reminder".
        if any(k in t for k in (" and add ", "add reminder", "set reminder", "set a reminder")):
            return None
        if not has_scheduler_terms and not inferred_target and target is None:
            return None

        if target == "reminder" and reminders_enabled:
            from app.reminders_tool import run_reminders_tool

            if target_id is None:
                if len(pending) == 1:
                    target_id = int(pending[0]["id"])
                elif len(pending) > 1:
                    return (
                        "I found multiple reminders. Tell me which one to edit by id "
                        "(e.g. 'edit reminder 2 to tomorrow 8am').\n\n"
                        + _render_reminders_list_text(pending)
                    ), _build_tool_trace_label("reminders", "update/fallback")
                else:
                    # User may call it "reminder" while referring to cron job by name.
                    if named_cron_id is not None:
                        target = "cron"
                        target_id = named_cron_id
                    else:
                        return "You have no pending reminders to edit.", _build_tool_trace_label("reminders", "update/fallback")

            if target == "reminder" and target_id is not None:
                update_text = _extract_update_payload_text(text)
                if not update_text:
                    return (
                        "Tell me what to change, for example: "
                        "'edit reminder 2 to remind me tomorrow at 7am to wake up'."
                    ), _build_tool_trace_label("reminders", "update/fallback")
                out = await run_reminders_tool(
                    {"action": "update", "id": int(target_id), "text": update_text},
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                try:
                    data = json.loads(out)
                except Exception:
                    if isinstance(out, str) and out.strip().lower().startswith("error:"):
                        return out.strip(), _build_tool_trace_label("reminders", "update/fallback")
                    return "I could not update that reminder right now.", _build_tool_trace_label("reminders", "update/fallback")
                if data.get("ok"):
                    when = (data.get("run_at") or "").strip()
                    msg = (data.get("message") or "").strip()
                    suffix = f" ({msg})" if msg else ""
                    return (
                        f"Updated reminder #{int(target_id)} for {when}{suffix}."
                        if when
                        else f"Updated reminder #{int(target_id)}{suffix}."
                    ), _build_tool_trace_label("reminders", "update/fallback")
                return f"No pending reminder found with id {int(target_id)}.", _build_tool_trace_label("reminders", "update/fallback")

        if target == "cron":
            from app.cron_tool import run_cron_tool

            if target_id is None:
                if len(cron_rows) == 1:
                    target_id = int(cron_rows[0]["id"])
                elif len(cron_rows) > 1:
                    return (
                        "I found multiple cron jobs. Tell me which one to edit by id "
                        "(e.g. 'edit cron 2 to 30 7 * * 1,2,3,4,5').\n\n"
                        + _render_cron_list_text(cron_rows)
                    ), _build_tool_trace_label("cron", "update/fallback")
                else:
                    return "You have no cron jobs to edit.", _build_tool_trace_label("cron", "update/fallback")

            params: dict[str, Any] = {"action": "update", "id": int(target_id)}
            new_name = _extract_new_name(text)
            if new_name:
                params["name"] = new_name
            cron_expr = _extract_inline_cron_expr(text)
            if cron_expr:
                params["cron_expr"] = cron_expr
            tz_match = re.search(
                r"\b(?:tz|timezone)\s*(?:to|=)?\s*([A-Za-z_]+/[A-Za-z0-9_\-+]+)\b",
                text or "",
                flags=re.IGNORECASE,
            )
            if tz_match:
                params["tz"] = (tz_match.group(1) or "").strip()
            msg_match = re.search(
                r"\b(?:message|msg)\s*(?:to|as|=)\s*(.+)$",
                text or "",
                flags=re.IGNORECASE,
            )
            if msg_match:
                msg = (msg_match.group(1) or "").strip().strip("\"'`").strip(" .?!,")
                if msg:
                    params["message"] = msg
            if len(params) == 2:
                return (
                    "Tell me what to change: name, cron expression, timezone, or message. "
                    "Example: 'rename cron 2 to Wake up reminder' or 'edit cron 2 to 30 7 * * 1,2,3,4,5'."
                ), _build_tool_trace_label("cron", "update/fallback")
            out = await run_cron_tool(
                params,
                user_id=user_id,
                channel=channel,
                channel_target=channel_target,
                db=db,
            )
            try:
                data = json.loads(out)
            except Exception:
                if isinstance(out, str) and out.strip().lower().startswith("error:"):
                    return out.strip(), _build_tool_trace_label("cron", "update/fallback")
                return "I could not update that cron job right now.", _build_tool_trace_label("cron", "update/fallback")
            if data.get("ok"):
                job = data.get("job") if isinstance(data.get("job"), dict) else {}
                name = (job.get("name") or "").strip()
                expr = (job.get("cron_expr") or "").strip()
                summary = f"Updated cron job #{int(target_id)}."
                if name:
                    summary += f" Name: {name}."
                if expr:
                    summary += f" Schedule: {expr}."
                return summary, _build_tool_trace_label("cron", "update/fallback")
            return f"No cron job found with id {int(target_id)}.", _build_tool_trace_label("cron", "update/fallback")

        return None

    if not is_remove:
        return None
    is_bare_remove = t in ("remove", "delete", "cancel")
    # Allow contextual deletes like "delete this" after reminder listing.
    if not is_bare_remove and not has_scheduler_terms and not inferred_target:
        return None
    # Let the model/tool loop handle compound requests like "delete this reminder and add..."
    if any(k in t for k in (" and add ", "add reminder", "set reminder", "set a reminder")):
        return None

    if target == "reminder" and reminders_enabled:
        from app.reminders_tool import run_reminders_tool

        if target_id is None:
            if len(pending) == 1:
                target_id = int(pending[0]["id"])
            elif len(pending) > 1:
                return (
                    "I found multiple reminders. Tell me which one to remove by id "
                    "(e.g. 'remove reminder 2').\n\n" + _render_reminders_list_text(pending)
                ), _build_tool_trace_label("reminders", "remove/fallback")
            else:
                return "You have no pending reminders to remove.", _build_tool_trace_label("reminders", "remove/fallback")

        out = await run_reminders_tool(
            {"action": "remove", "id": int(target_id)},
            user_id=user_id,
            channel=channel,
            channel_target=channel_target,
            db=db,
        )
        try:
            data = json.loads(out)
        except Exception:
            return "I could not remove that reminder right now.", _build_tool_trace_label("reminders", "remove/fallback")
        if data.get("ok"):
            return f"Removed reminder #{int(target_id)}.", _build_tool_trace_label("reminders", "remove/fallback")
        return f"No pending reminder found with id {int(target_id)}.", _build_tool_trace_label("reminders", "remove/fallback")

    if target == "cron":
        from app.cron_tool import run_cron_tool

        if target_id is None:
            if len(cron_rows) == 1:
                target_id = int(cron_rows[0]["id"])
            elif len(cron_rows) > 1:
                return (
                    "I found multiple cron jobs. Tell me which one to remove by id "
                    "(e.g. 'remove cron 2').\n\n" + _render_cron_list_text(cron_rows)
                ), _build_tool_trace_label("cron", "remove/fallback")
            else:
                return "You have no cron jobs to remove.", _build_tool_trace_label("cron", "remove/fallback")

        out = await run_cron_tool(
            {"action": "remove", "id": int(target_id)},
            user_id=user_id,
            channel=channel,
            channel_target=channel_target,
            db=db,
        )
        try:
            data = json.loads(out)
        except Exception:
            return "I could not remove that cron job right now.", _build_tool_trace_label("cron", "remove/fallback")
        if data.get("ok"):
            return f"Removed cron job #{int(target_id)}.", _build_tool_trace_label("cron", "remove/fallback")
        return f"No cron job found with id {int(target_id)}.", _build_tool_trace_label("cron", "remove/fallback")

    return None


# ---------------------------------------------------------------------------
# Files / workspace-notes fallback handlers
# ---------------------------------------------------------------------------

async def _handle_files_check_fallback(
    *,
    db,
    user_id: str,
    text: str,
) -> tuple[str, str] | None:
    from app.handler_intent import _looks_like_files_check_request, _infer_files_directory, _extract_files_search_term, _name_matches_query

    if not _looks_like_files_check_request(text):
        return None
    from app.files_tool import list_directory

    path = _infer_files_directory(text)
    out = await list_directory(path, user_id, db)
    trace = _build_tool_trace_label("list_directory", "list/fallback")

    if not out:
        return f"I couldn't check {path} right now.", trace
    if out.startswith("Error:"):
        return f"I couldn't check {path}. {out}", trace
    if "not in the allowed list" in out:
        return f"I can't access {path} yet. {out}", trace

    try:
        payload = json.loads(out)
    except Exception:
        return f"I checked {path}, but got an unreadable result.", trace

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return f"I checked {path}, but got an invalid directory result.", trace

    display_path = str(payload.get("path") or path)
    query = _extract_files_search_term(text)
    valid_entries = [e for e in entries if isinstance(e, dict)]
    if query:
        matches = [e for e in valid_entries if _name_matches_query(str(e.get("name") or ""), query)]
        if matches:
            shown = ", ".join(str(e.get("name") or "") for e in matches[:8])
            more = f" (+{len(matches) - 8} more)" if len(matches) > 8 else ""
            return (
                f"I checked {display_path} and found {len(matches)} match(es) for \"{query}\": {shown}{more}.",
                trace,
            )
        return f"I checked {display_path} and found no items matching \"{query}\".", trace

    file_count = sum(1 for e in valid_entries if (e.get("kind") or "") == "file")
    dir_count = sum(1 for e in valid_entries if (e.get("kind") or "") == "dir")
    preview = ", ".join(str(e.get("name") or "") for e in valid_entries[:10])
    if preview:
        return (
            f"I checked {display_path}: {len(valid_entries)} item(s) "
            f"({dir_count} folder(s), {file_count} file(s)). First items: {preview}.",
            trace,
        )
    return f"I checked {display_path}. It looks empty.", trace


async def _handle_workspace_notes_list_fallback(
    *,
    text: str,
    limit: int = 20,
) -> tuple[str, str] | None:
    from app.handler_intent import _is_workspace_notes_list_request

    if not _is_workspace_notes_list_request(text):
        return None
    from app.routers.settings import get_workspace_notes

    trace = _build_tool_trace_label("read_file", "notes/fallback")
    try:
        payload = await get_workspace_notes(limit=limit)
    except Exception as e:
        logger.warning("Workspace notes fallback failed: %s", e)
        return "I couldn't check workspace notes right now.", trace

    rows = payload.get("notes") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return (
            "You have no workspace notes yet. I can save one for you in notes/ when you say 'take a note ...'.",
            trace,
        )

    lines = [f"You have {len(rows)} workspace note(s):"]
    for idx, row in enumerate(rows[:10], start=1):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "untitled.md")
        rel_path = str(row.get("path") or "")
        modified = str(row.get("modified_at") or "")
        date_short = modified[:10] if modified else ""
        suffix = f" (updated {date_short})" if date_short else ""
        path_part = f" — {rel_path}" if rel_path else ""
        lines.append(f"{idx}. {name}{path_part}{suffix}")
    if len(rows) > 10:
        lines.append(f"... and {len(rows) - 10} more.")
    return "\n".join(lines), trace
