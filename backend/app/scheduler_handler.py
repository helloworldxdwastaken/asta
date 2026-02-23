"""Scheduler handler - extracted from handler.py for better maintainability.

Handles reminder and cron job intents, parsing, and responses.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Regex patterns for intent detection
_REMINDER_SET_KEYWORDS = (
    "remind me", "set reminder", "set a reminder", "alarm at", "alarm for",
    "set alarm", "set an alarm", "wake me up", "set timer", "timer for",
)
_REMINDER_LIST_KEYWORDS = (
    "what reminders", "list reminders", "show reminders", "do i have any reminders",
    "do i have reminders", "pending reminders", "what reminder", "tasks", "task", "tast",
)
_CRON_LIST_KEYWORDS = ("what", "list", "show", "have", "status", "jobs", "tasks")
_SCHEDULE_KEYWORDS = (
    "what tasks do i have", "what task do i have", "do i have any task",
    "do i have any tasks", "any pending task", "any pending tasks",
    "do i have any pending task", "do i have any pending tasks",
    "what reminders and cron", "what reminders or cron",
)
_REMINDER_EXCLUSIONS = (
    "do i have reminder", "do i have any reminder", "what reminders", "list reminders",
    "show reminders", "pending reminders", "any reminders",
)


def _looks_like_reminder_set_request(text: str) -> bool:
    """Check if text looks like a request to set a reminder."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # List/status questions should not schedule.
    if any(q in t for q in _REMINDER_EXCLUSIONS):
        return False
    return any(k in t for k in _REMINDER_SET_KEYWORDS)


def _looks_like_reminder_list_request(text: str) -> bool:
    """Check if text looks like a request to list reminders."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # Natural "task" wording and common typo ("tast") should still list reminders.
    if any(k in t for k in ("tasks", "task", "tast")) and any(k in t for k in ("reminder", "alarm")):
        return True
    return any(k in t for k in _REMINDER_LIST_KEYWORDS)


def _looks_like_cron_list_request(text: str) -> bool:
    """Check if text looks like a request to list cron jobs."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if "cron" in t:
        return any(k in t for k in _CRON_LIST_KEYWORDS)
    return False


def _looks_like_schedule_overview_request(text: str) -> bool:
    """Check if text looks like a request for a schedule overview."""
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
    return any(k in t for k in _SCHEDULE_KEYWORDS)


def _looks_like_remove_request(text: str) -> bool:
    """Check if text looks like a request to remove something."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in ("remove", "delete", "cancel"):
        return True
    if any(t.startswith(prefix) for prefix in ("remove this", "delete this", "cancel this", "remove that", "delete that", "cancel that")):
        return True
    if re.search(r"\b(?:remove|delete|cancel)\b", t):
        return True
    return any(t.startswith(prefix) for prefix in ("remove ", "delete ", "cancel "))


def _looks_like_update_request(text: str) -> bool:
    """Check if text looks like a request to update something."""
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
    """Extract new name from update request."""
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
    """Extract inline cron expression from text."""
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


def _extract_target_id(text: str) -> int | None:
    """Extract numeric ID from text."""
    t = (text or "").strip().lower()
    if not t:
        return None
    m = re.search(r"(?:id|#)\s*(\d+)\b", t)
    if m:
        return int(m.group(1))
    # Avoid treating times like "9am" / "18:30" as ids.
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", t):
        return None
    if re.search(r"\b\d{1,2}:\d{2}\b", t):
        return None
    nums = re.findall(r"\b\d+\b", t)
    # Implicit numeric id only for short commands like "remove 2".
    if len(nums) == 1 and len(t.split()) <= 4:
        return int(nums[0])
    return None


def _match_cron_id_by_name(text: str, cron_rows: list[dict]) -> int | None:
    """Match cron job ID by name in text."""
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
    """Extract update text from request."""
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"\bto\s+(.+)$", raw, flags=re.IGNORECASE)
    if not m:
        return None
    candidate = (m.group(1) or "").strip().strip("\"'`").strip(" .?!,")
    return candidate or None


async def _get_pending_reminder_rows(db, user_id: str) -> list[dict]:
    """Get pending reminders from database."""
    rows = await db.get_notifications(user_id, limit=50)
    return [r for r in rows if (r.get("status") or "").lower() == "pending"]


def _render_reminders_list_text(pending_rows: list[dict]) -> str:
    """Render pending reminders as human-readable text."""
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
    """Render cron jobs as human-readable text."""
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
    """Infer whether user wants to remove a reminder or cron job based on recent messages."""
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


async def handle_scheduler_intents(
    *,
    db,
    user_id: str,
    conversation_id: str,
    text: str,
    channel: str,
    channel_target: str,
    reminders_enabled: bool,
) -> tuple[str, str] | None:
    """Main handler for scheduler (reminder/cron) intents.
    
    Returns tuple of (reply_text, tool_trace_label) or None if not handled.
    """
    from app.reminders_tool import run_reminders_tool
    from app.cron_tool import run_cron_tool
    
    t = (text or "").strip().lower()
    if not t:
        return None

    # Schedule overview - show both reminders and cron jobs
    if _looks_like_schedule_overview_request(t):
        pending = await _get_pending_reminder_rows(db, user_id) if reminders_enabled else []
        cron_rows = await db.get_cron_jobs(user_id)
        parts = []
        if reminders_enabled:
            parts.append(_render_reminders_list_text(pending))
        parts.append(_render_cron_list_text(cron_rows))
        return "\n\n".join(parts), "scheduler (overview/fallback)"

    # Reminder list request
    if reminders_enabled and _looks_like_reminder_list_request(t):
        if any(k in t for k in ("task", "tasks", "tast", "cron", "schedule")):
            pending = await _get_pending_reminder_rows(db, user_id)
            cron_rows = await db.get_cron_jobs(user_id)
            return (
                _render_reminders_list_text(pending) + "\n\n" + _render_cron_list_text(cron_rows),
                "scheduler (overview/fallback)",
            )
        pending = await _get_pending_reminder_rows(db, user_id)
        return _render_reminders_list_text(pending), "reminders (list/fallback)"

    # Cron list request
    if _looks_like_cron_list_request(t):
        cron_rows = await db.get_cron_jobs(user_id)
        return _render_cron_list_text(cron_rows), "cron (list/fallback)"

    # Get current state
    pending = await _get_pending_reminder_rows(db, user_id) if reminders_enabled else []
    cron_rows = await db.get_cron_jobs(user_id)
    inferred_target = await _infer_remove_target_from_recent(db, conversation_id, text)
    has_scheduler_terms = any(k in t for k in ("reminder", "alarm", "timer", "cron", "schedule", "task"))

    # Determine target (reminder vs cron)
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

    # Extract target ID
    target_id = _extract_target_id(t)
    if target is None and target_id is not None:
        if reminders_enabled and any(int(r.get("id") or 0) == int(target_id) for r in pending):
            target = "reminder"
        elif any(int(r.get("id") or 0) == int(target_id) for r in cron_rows):
            target = "cron"

    # Try to match by name
    named_cron_id = _match_cron_id_by_name(text, cron_rows)
    if named_cron_id is not None and target_id is None:
        target_id = named_cron_id
        if target in (None, "cron") or (target == "reminder" and not pending):
            target = "cron"

    is_update = _looks_like_update_request(t)
    is_remove = _looks_like_remove_request(t)

    # Handle update requests
    if is_update:
        # Let model/tool loop handle compound requests
        if any(k in t for k in (" and add ", "add reminder", "set reminder", "set a reminder")):
            return None
        if not has_scheduler_terms and not inferred_target and target is None:
            return None

        if target == "reminder" and reminders_enabled:
            if target_id is None:
                if len(pending) == 1:
                    target_id = int(pending[0]["id"])
                elif len(pending) > 1:
                    return (
                        "I found multiple reminders. Tell me which one to edit by id "
                        "(e.g. 'edit reminder 2 to tomorrow 8am').\n\n"
                        + _render_reminders_list_text(pending)
                    ), "reminders (update/fallback)"
                else:
                    if named_cron_id is not None:
                        target = "cron"
                        target_id = named_cron_id
                    else:
                        return "You have no pending reminders to edit.", "reminders (update/fallback)"

            if target == "reminder" and target_id is not None:
                update_text = _extract_update_payload_text(text)
                if not update_text:
                    return (
                        "Tell me what to change, for example: "
                        "'edit reminder 2 to remind me tomorrow at 7am to wake up'."
                    ), "reminders (update/fallback)"
                
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
                        return out.strip(), "reminders (update/fallback)"
                    return "I could not update that reminder right now.", "reminders (update/fallback)"
                
                if data.get("ok"):
                    when = (data.get("run_at") or "").strip()
                    msg = (data.get("message") or "").strip()
                    suffix = f" ({msg})" if msg else ""
                    return (
                        f"Updated reminder #{int(target_id)} for {when}{suffix}."
                        if when
                        else f"Updated reminder #{int(target_id)}{suffix}."
                    ), "reminders (update/fallback)"
                return f"No pending reminder found with id {int(target_id)}.", "reminders (update/fallback)"

        if target == "cron":
            if target_id is None:
                if len(cron_rows) == 1:
                    target_id = int(cron_rows[0]["id"])
                elif len(cron_rows) > 1:
                    return (
                        "I found multiple cron jobs. Tell me which one to edit by id "
                        "(e.g. 'edit cron 2 to 30 7 * * 1,2,3,4,5').\n\n"
                        + _render_cron_list_text(cron_rows)
                    ), "cron (update/fallback)"
                else:
                    return "You have no cron jobs to edit.", "cron (update/fallback)"

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
                ), "cron (update/fallback)"
            
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
                    return out.strip(), "cron (update/fallback)"
                return "I could not update that cron job right now.", "cron (update/fallback)"
            
            if data.get("ok"):
                job = data.get("job") if isinstance(data.get("job"), dict) else {}
                name = (job.get("name") or "").strip()
                expr = (job.get("cron_expr") or "").strip()
                summary = f"Updated cron job #{int(target_id)}."
                if name:
                    summary += f" Name: {name}."
                if expr:
                    summary += f" Schedule: {expr}."
                return summary, "cron (update/fallback)"
            return f"No cron job found with id {int(target_id)}.", "cron (update/fallback)"

        return None

    # Handle remove requests
    if not is_remove:
        return None
    
    is_bare_remove = t in ("remove", "delete", "cancel")
    # Allow contextual deletes like "delete this" after reminder listing.
    if not is_bare_remove and not has_scheduler_terms and not inferred_target:
        return None
    # Let model/tool loop handle compound requests
    if any(k in t for k in (" and add ", "add reminder", "set reminder", "set a reminder")):
        return None

    if target == "reminder" and reminders_enabled:
        if target_id is None:
            if len(pending) == 1:
                target_id = int(pending[0]["id"])
            elif len(pending) > 1:
                return (
                    "I found multiple reminders. Tell me which one to remove by id "
                    "(e.g. 'remove reminder 2').\n\n" + _render_reminders_list_text(pending)
                ), "reminders (remove/fallback)"
            else:
                return "You have no pending reminders to remove.", "reminders (remove/fallback)"

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
            return "I could not remove that reminder right now.", "reminders (remove/fallback)"
        if data.get("ok"):
            return f"Removed reminder #{int(target_id)}.", "reminders (remove/fallback)"
        return f"No pending reminder found with id {int(target_id)}.", "reminders (remove/fallback)"

    if target == "cron":
        if target_id is None:
            if len(cron_rows) == 1:
                target_id = int(cron_rows[0]["id"])
            elif len(cron_rows) > 1:
                return (
                    "I found multiple cron jobs. Tell me which one to remove by id "
                    "(e.g. 'remove cron 2').\n\n" + _render_cron_list_text(cron_rows)
                ), "cron (remove/fallback)"
            else:
                return "You have no cron jobs to remove.", "cron (remove/fallback)"

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
            return "I could not remove that cron job right now.", "cron (remove/fallback)"
        if data.get("ok"):
            return f"Removed cron job #{int(target_id)}.", "cron (remove/fallback)"
        return f"No cron job found with id {int(target_id)}.", "cron (remove/fallback)"

    return None


# Need json for parsing tool outputs
import json
