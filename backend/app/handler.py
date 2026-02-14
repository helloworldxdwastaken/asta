"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import logging
import io
import json
import re
import html
from PIL import Image
from app.context import build_context
from app.db import get_db
from app.providers.registry import get_provider
from app.providers.base import ProviderResponse, ProviderError
from app.reminders import send_skill_status, send_notification
from app.time_weather import geocode, parse_location_from_message

# Services
from app.services.spotify_service import SpotifyService
from app.services.reminder_service import ReminderService
from app.services.learning_service import LearningService
from app.services.giphy_service import GiphyService

logger = logging.getLogger(__name__)

# Short acknowledgments: when user sends only this, we nudge the model to reply with one phrase
_SHORT_ACK_PHRASES = frozenset({
    "ok", "okay", "thanks", "thank you", "thx", "bye", "got it", "no", "sure", "yep", "yes",
    "cool", "nice", "np", "alright", "k", "kk", "done", "good", "great", "perfect",
})

_EXEC_INTENT_HINTS = (
    "apple notes",
    "memo",
    "things",
    "things app",
    "things inbox",
)
_EXEC_CHECK_VERBS = (
    "check",
    "see",
    "show",
    "list",
    "find",
    "read",
    "open",
    "what",
    "do i have",
)

_TOOL_CAPABLE_PROVIDERS = frozenset({"openai", "groq", "openrouter", "claude", "google"})
_GIF_COOLDOWN_SECONDS = 30 * 60
_SILENT_REPLY_TOKEN = "NO_REPLY"
_FILES_LOCATION_HINTS = {
    "desktop": "~/Desktop",
    "documents": "~/Documents",
    "downloads": "~/Downloads",
}
_FILES_CHECK_VERBS = (
    "check",
    "look",
    "find",
    "see",
    "list",
    "show",
    "search",
    "scan",
)
_STATUS_PREFIX = "[[ASTA_STATUS]]"

_TOOL_TRACE_GROUP = {
    "exec": "Terminal",
    "bash": "Terminal",
    "process": "Process",
    "list_directory": "Files",
    "read_file": "Files",
    "write_file": "Files",
    "allow_path": "Files",
    "delete_file": "Files",
    "delete_matching_files": "Files",
    "read": "Files",
    "write": "Files",
    "edit": "Files",
    "apply_patch": "Files",
    "web_search": "Web",
    "web_fetch": "Web",
    "memory_search": "Memory",
    "memory_get": "Memory",
    "message": "Message",
    "reminders": "Reminders",
    "cron": "Cron",
}

_TOOL_TRACE_DEFAULT_ACTION = {
    "list_directory": "list",
    "read_file": "read",
    "write_file": "write",
    "allow_path": "allow",
    "delete_file": "delete",
    "delete_matching_files": "delete-many",
    "read": "read",
    "write": "write",
    "edit": "edit",
    "apply_patch": "patch",
    "web_search": "search",
    "web_fetch": "fetch",
    "memory_search": "search",
    "memory_get": "get",
}


def _is_short_acknowledgment(text: str) -> bool:
    """True if the message is only a short acknowledgment (ok, thanks, etc.)."""
    t = (text or "").strip().lower()
    if len(t) > 25:
        return False
    # Exact match or single word/phrase from list
    if t in _SHORT_ACK_PHRASES:
        return True
    # "thanks!" or "ok." etc.
    base = t.rstrip(".!")
    if base in _SHORT_ACK_PHRASES:
        return True
    return False


def _is_exec_intent(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(k in t for k in _EXEC_INTENT_HINTS)


def _is_exec_check_request(text: str) -> bool:
    t = (text or "").strip().lower()
    return _is_exec_intent(t) and any(v in t for v in _EXEC_CHECK_VERBS)


def _provider_supports_tools(provider_name: str) -> bool:
    return (provider_name or "").strip().lower() in _TOOL_CAPABLE_PROVIDERS


def _thinking_instruction(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv == "off":
        return ""
    if lv == "low":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: low. Spend a bit more effort before answering. "
            "Double-check tool outputs and avoid assumptions."
        )
    if lv == "medium":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: medium. Plan briefly before answering, validate tool output, "
            "and prefer factual, verified replies over quick guesses."
        )
    if lv == "high":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: high. Do deeper internal planning and verification. "
            "For external-state claims (files, reminders, notes, statuses), rely on real tool results only."
        )
    return ""


def _reasoning_instruction(mode: str) -> str:
    rm = (mode or "off").strip().lower()
    if rm not in ("on", "stream"):
        return ""
    return (
        "\n\n[REASONING]\n"
        "Before your final answer, you MUST include exactly one brief rationale block inside "
        "<think>...</think>. Do not skip it in this mode. "
        "Keep it short (1-3 lines), factual, and directly tied to tool results when tools are used."
    )


def _extract_reasoning_blocks(text: str) -> tuple[str, str]:
    raw = (text or "")
    if not raw:
        return "", ""
    blocks = re.findall(r"(?is)<(?:think|thinking)>\s*(.*?)\s*</(?:think|thinking)>", raw)
    final_text = re.sub(r"(?is)<(?:think|thinking)>\s*.*?\s*</(?:think|thinking)>", "", raw).strip()
    parts: list[str] = []
    for block in blocks:
        b = (block or "").strip()
        if b:
            parts.append(b)
    return final_text, "\n\n".join(parts).strip()


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


def _looks_like_files_check_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if any(k in t for k in ("write", "create", "save", "delete", "remove", "rename", "move", "edit")):
        return False
    has_verb = any(v in t for v in _FILES_CHECK_VERBS)
    has_target = any(
        k in t
        for k in (
            "desktop",
            "documents",
            "downloads",
            "folder",
            "directory",
            "file",
            "files",
            "on my mac",
        )
    )
    return has_verb and has_target


def _extract_path_hint(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    m = re.search(r"(?P<path>~\/[^\s,;]+|\/[^\s,;]+)", t)
    if not m:
        return None
    return m.group("path").strip()


def _infer_files_directory(text: str) -> str:
    path_hint = _extract_path_hint(text)
    if path_hint:
        return path_hint
    t = (text or "").strip().lower()
    for key, path in _FILES_LOCATION_HINTS.items():
        if key in t:
            return path
    return "~/Desktop"


def _extract_files_search_term(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    for pat in (
        r"\bfor\s+(.+)$",
        r"\bnamed\s+(.+)$",
        r"\bcalled\s+(.+)$",
    ):
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            q = m.group(1).strip().strip("\"'`").strip(" .?!,")
            q = re.sub(r"^(the|a|an)\s+", "", q, flags=re.IGNORECASE).strip()
            if q and len(q) <= 120:
                return q
    return ""


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _name_matches_query(name: str, query: str) -> bool:
    nn = _normalize_match_text(name)
    nq = _normalize_match_text(query)
    if not nn or not nq:
        return False
    return nq in nn


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


def _build_tool_trace_label(tool_name: str, action: str | None = None) -> str:
    group = _TOOL_TRACE_GROUP.get(tool_name, tool_name)
    act = (action or _TOOL_TRACE_DEFAULT_ACTION.get(tool_name) or "").strip().lower()
    if "/" in act:
        act = act.split("/", 1)[0].strip()
    if act:
        return f"{group} ({act})"
    return group


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        k = item.strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def _render_tool_trace(labels: list[str]) -> str:
    uniq = _dedupe_keep_order(labels)
    if not uniq:
        return "Tools used: none (AI-only reply; skill routing may still run in background)"
    return "Tools used: " + ", ".join(uniq)


def _make_status_message(text: str) -> str:
    return f"{_STATUS_PREFIX}{(text or '').strip()}"


async def _emit_stream_status(
    *,
    db,
    conversation_id: str,
    channel: str,
    channel_target: str,
    text: str,
) -> None:
    msg = (text or "").strip()
    if not msg:
        return
    ch = (channel or "").strip().lower()
    if ch in ("telegram", "whatsapp") and channel_target:
        try:
            await send_notification(ch, channel_target, msg)
        except Exception as e:
            logger.debug("Could not send stream status to channel=%s: %s", ch, e)
    if ch == "web":
        try:
            await db.add_message(conversation_id, "assistant", _make_status_message(msg), "script")
        except Exception as e:
            logger.debug("Could not persist stream status to web conversation: %s", e)


def _sanitize_silent_reply_markers(text: str) -> tuple[str, bool]:
    """Strip NO_REPLY control marker and tell whether this should be a silent/no-output reply."""
    raw = (text or "")
    if not raw.strip():
        return "", False

    # Exact control token means "do not emit assistant text".
    if re.fullmatch(r"(?is)\s*NO_REPLY\s*", raw):
        return "", True

    # Remove standalone NO_REPLY lines and trailing token leakage.
    cleaned = re.sub(r"(?im)^\s*NO_REPLY\s*$", "", raw)
    cleaned = re.sub(r"(?i)\s*NO_REPLY\s*$", "", cleaned)
    cleaned = re.sub(r"(?i)^\s*NO_REPLY\s*", "", cleaned)
    cleaned = cleaned.strip()

    # If stripping markers left no user-facing text, keep it silent.
    if not cleaned:
        return "", True
    return cleaned, False


def _tool_names_from_defs(tools: list[dict] | None) -> set[str]:
    names: set[str] = set()
    for t in (tools or []):
        if not isinstance(t, dict):
            continue
        fn = t.get("function")
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _extract_textual_tool_calls(
    text: str,
    allowed_names: set[str],
) -> tuple[list[dict] | None, str]:
    raw = text or ""
    if not raw.strip():
        return None, raw

    # Existing fallback protocol used in provider prompts.
    m = re.search(r"\[ASTA_TOOL_CALL\]\s*(\{.*?\})\s*\[/ASTA_TOOL_CALL\]", raw, re.DOTALL)
    if m:
        payload_raw = m.group(1).strip()
        try:
            payload = json.loads(payload_raw)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            name = str(payload.get("name") or "").strip()
            if name and (not allowed_names or name in allowed_names):
                args = payload.get("arguments")
                if not isinstance(args, dict):
                    args = {}
                tool_calls = [
                    {
                        "id": "text_tool_call_1",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                ]
                cleaned = (raw[: m.start()] + raw[m.end() :]).strip()
                return tool_calls, cleaned

    # OpenClaw/Claude-style text tool calls:
    # <function_calls><invoke name="read"><parameter name="path">...</parameter></invoke></function_calls>
    block_match = re.search(r"(?is)<function_calls>\s*(.*?)\s*</function_calls>", raw)
    if block_match:
        body = block_match.group(1) or ""
        invocations = re.finditer(
            r'(?is)<invoke\s+name\s*=\s*"([^"]+)"\s*>(.*?)</invoke>',
            body,
        )
        tool_calls: list[dict] = []
        for idx, inv in enumerate(invocations, start=1):
            name = (inv.group(1) or "").strip()
            if not name:
                continue
            if allowed_names and name not in allowed_names:
                continue
            params_body = inv.group(2) or ""
            args: dict[str, str] = {}
            for p in re.finditer(
                r'(?is)<parameter\s+name\s*=\s*"([^"]+)"\s*>(.*?)</parameter>',
                params_body,
            ):
                p_name = (p.group(1) or "").strip()
                if not p_name:
                    continue
                p_value = html.unescape((p.group(2) or "").strip())
                args[p_name] = p_value
            tool_calls.append(
                {
                    "id": f"text_tool_call_{idx}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
        if tool_calls:
            cleaned = re.sub(r"(?is)<function_calls>\s*.*?\s*</function_calls>", "", raw).strip()
            return tool_calls, cleaned
    return None, raw


def _has_tool_call_markup(text: str) -> bool:
    raw = text or ""
    if not raw:
        return False
    if re.search(r"\[ASTA_TOOL_CALL\].*?\[/ASTA_TOOL_CALL\]", raw, re.DOTALL):
        return True
    if re.search(r"(?is)<function_calls>\s*.*?\s*</function_calls>", raw):
        return True
    return False


def _strip_tool_call_markup(text: str) -> str:
    raw = text or ""
    if not raw:
        return ""
    cleaned = re.sub(r"\[ASTA_TOOL_CALL\]\s*\{.*?\}\s*\[/ASTA_TOOL_CALL\]", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"(?is)<function_calls>\s*.*?\s*</function_calls>", "", cleaned)
    return cleaned.strip()


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

    if not _looks_like_remove_request(t):
        return None
    is_bare_remove = t in ("remove", "delete", "cancel")
    has_scheduler_terms = any(k in t for k in ("reminder", "alarm", "timer", "cron", "schedule", "task"))
    pending = await _get_pending_reminder_rows(db, user_id) if reminders_enabled else []
    cron_rows = await db.get_cron_jobs(user_id)
    inferred_target = await _infer_remove_target_from_recent(db, conversation_id, text)
    # Allow contextual deletes like "delete this" after reminder listing.
    if not is_bare_remove and not has_scheduler_terms and not inferred_target:
        return None
    # Let the model/tool loop handle compound requests like "delete this reminder and add..."
    if any(k in t for k in (" and add ", "add reminder", "set reminder", "set a reminder")):
        return None

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


async def _handle_files_check_fallback(
    *,
    db,
    user_id: str,
    text: str,
) -> tuple[str, str] | None:
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


async def handle_message(
    user_id: str,
    channel: str,
    text: str,
    provider_name: str = "default",
    conversation_id: str | None = None,
    extra_context: dict | None = None,
    channel_target: str = "",
    mood: str | None = None,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> str:
    """Process one user message: context + AI + save. Schedules reminders when requested. Returns assistant reply.
    Asta is the agent; it uses whichever AI provider you set (Groq, Gemini, Claude, Ollama)."""
    db = get_db()
    await db.connect()

    # Image optimization: compress/resize to speed up API
    if image_bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Max dimension 1024px
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size))
            
            # Convert to RGB if necessary (e.g. RGBA/PNG to JPEG)
            if img.mode != "RGB":
                img = img.convert("RGB")
                
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=70, optimize=True)
            image_bytes = out_buf.getvalue()
            image_mime = "image/jpeg"
            logger.info("Image compressed: %d bytes", len(image_bytes))
        except Exception as e:
            logger.warning("Image compression failed: %s", e)

    cid = conversation_id or await db.get_or_create_conversation(user_id, channel)
    # Persist user message early so Telegram (and web) thread shows it even if handler or provider fails later
    user_content = f" [Image: {image_mime or 'image/jpeg'}] {text}" if image_bytes else text
    await db.add_message(cid, "user", user_content)
    extra = extra_context or {}
    if mood is None:
        mood = await db.get_user_mood(user_id)
    extra["mood"] = mood
    thinking_level = await db.get_user_thinking_level(user_id)
    extra["thinking_level"] = thinking_level
    reasoning_mode = await db.get_user_reasoning_mode(user_id)
    extra["reasoning_mode"] = reasoning_mode
    if provider_name == "default":
        provider_name = await db.get_user_default_ai(user_id)

    # If user is setting their location (for time/weather skill), save it now
    # 1. Explicit syntax "I'm in Paris"
    location_place = parse_location_from_message(text)
    
    # 2. Check if we *asked* for location recently (pending request)
    if not location_place:
        if await db.get_pending_location_request(user_id):
            # Treat the entire text as a potential location (e.g. "Holon, Israel")
            # But skip if it's too long or looks like a command
            clean_text = text.strip()
            if len(clean_text) < 100 and " " in clean_text: # Simple heuristic: cities usually have short names, maybe allow single words too?
                 # Actually single word cities exist "London". Let's allow anything short enough.
                 location_place = clean_text
            elif len(clean_text) < 50:
                 location_place = clean_text
    
    if location_place:
        result = await geocode(location_place)
        if result:
            lat, lon, name = result
            await db.set_user_location(user_id, name, lat, lon)
            await db.clear_pending_location_request(user_id) # Clear flag
            extra["location_just_set"] = name
            # If we just set location, we might want to ACK it here or let the context know
        else:
            # If we were pending and failed to geocode, maybe we shouldn't clear?
            # Or maybe we should to avoid getting stuck. Let's clear if it was an explicit "I'm in X"
            # but if it was pending, maybe they said "No thanks".
            # For now, let's just log and move on.
            if await db.get_pending_location_request(user_id):
                 await db.clear_pending_location_request(user_id) # Assume they replied something else

    # Build enabled skills early so we can gate service calls by toggle (built-in + workspace skills)
    from app.skills.registry import get_all_skills as _get_all_skills
    enabled = set()
    for skill in _get_all_skills():
        if await db.get_skill_enabled(user_id, skill.name):
            enabled.add(skill.name)

    # --- SERVICE CALLS (only when skill is enabled) ---

    # 1. Reminders
    # OpenClaw-style flow uses tool calls for capable providers; keep this as a fallback for providers without tools.
    if "reminders" in enabled and not _provider_supports_tools(provider_name):
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)

    # 2. Learning
    if "learn" in enabled:
        learning_result = await LearningService.process_learning(user_id, text, channel, channel_target)
        if learning_result:
            extra.update(learning_result)

    # 3. Spotify
    if "spotify" in enabled:
        spotify_reply = await SpotifyService.handle_message(user_id, text, extra)
        if spotify_reply:
            await db.add_message(cid, "assistant", spotify_reply, "script")
            return spotify_reply

    # --- END SERVICE CALLS ---

    # Intent-based skill selection: only run and show skills relevant to this message (saves tokens)
    from app.skill_router import get_skills_to_use, SKILL_STATUS_LABELS
    
    skills_to_use = get_skills_to_use(text, enabled)
    
    # When user says "yeah do that" / "yes" after AI offered to save to a file, include files skill
    if "files" in enabled and "files" not in skills_to_use:
        short_affirmation = text.strip().lower() in (
            "yeah", "yes", "do that", "ok", "sure", "go ahead", "please", "do it", "yep", "okay",
        ) or (len(text.strip()) < 25 and any(w in text.lower() for w in ("do it", "go ahead", "yes", "yeah", "ok", "sure")))
        if short_affirmation:
            recent = await db.get_recent_messages(cid, limit=3)
            if recent and recent[-1].get("role") == "assistant":
                last_content = (recent[-1].get("content") or "").lower()
                if any(k in last_content for k in ("save", "file", "write", "create a file", "save it to")):
                    skills_to_use = skills_to_use | {"files"}
                    logger.info("Including files skill for affirmation after save offer")
    
    # Force include skills if services triggered them
    if extra.get("is_reminder"):
        skills_to_use = skills_to_use | {"reminders"}
    if extra.get("is_learning"):
        skills_to_use = skills_to_use | {"learn"}
    if extra.get("location_just_set"):
        skills_to_use = skills_to_use | {"time", "weather"}

    # If user asks for time/weather but no location (DB or User.md), ask for their location
    # REMOVED: fast-fail check. We now let it fall through to build_context, which has instructions
    # to ask for location if missing. This allows combined intents (e.g. "check notes and time")
    # to succeed on the "notes" part even if location is invalid.


    # Status: only the skills we're actually using, with emojis (workspace skills get generic label)
    skill_labels = [SKILL_STATUS_LABELS.get(s, f"📄 Using {s}…") for s in skills_to_use]
    if skill_labels and channel in ("telegram", "whatsapp") and channel_target:
        await send_skill_status(channel, channel_target, skill_labels)
    if skill_labels and (reasoning_mode or "").lower() == "stream":
        await _emit_stream_status(
            db=db,
            conversation_id=cid,
            channel=channel,
            channel_target=channel_target,
            text=" • ".join(skill_labels),
        )

    # Execute skills to gather data (populate `extra`)
    from app.skills.registry import get_skill_by_name, get_all_skills

    # Sort skills: RAG before Google Search (Search sees RAG content); then registry order for stability
    priority_order = ["rag", "google_search"]
    skill_names = list(get_all_skills())
    name_to_idx = {s.name: i for i, s in enumerate(skill_names)}

    def _skill_sort_key(name: str) -> tuple[int, int]:
        prio = priority_order.index(name) if name in priority_order else 999
        idx = name_to_idx.get(name, 999)
        return (prio, idx)

    sorted_skills = sorted(skills_to_use, key=_skill_sort_key)
    logger.info("Executing skills: %s (Original: %s)", sorted_skills, skills_to_use)

    # OpenClaw-style: Apple Notes (and other exec) work only via the exec tool. Model calls exec(command);
    # we run it and return the result — no proactive run or context injection.

    for skill_name in sorted_skills:
        skill = get_skill_by_name(skill_name)
        if skill:
            try:
                logger.info("Skill %s executing...", skill_name)
                skill_result = await skill.execute(user_id, text, extra)
                if skill_result:
                    logger.info("Skill %s returned data: %s", skill_name, list(skill_result.keys()))
                    extra.update(skill_result)
                else:
                    logger.debug("Skill %s returned None", skill_name)
            except Exception as e:
                logger.error("Skill %s execution failed: %s", skill_name, e, exc_info=True)

    # 4. Build Context (Prompt Engineering)
    # Built-in skills are intent-routed; workspace skills are selected by the model via <available_skills> + read tool.
    context = await build_context(db, user_id, cid, extra=extra, skills_in_use=skills_to_use)
    
    # Silly GIF skill: Proactive instruction (not intent-based)
    if "silly_gif" in enabled:
        context += (
            "\n\n[SKILL: SILLY GIF ENABLED]\n"
            "You can occasionally (10-20% chance) send a relevant GIF by adding `[gif: search term]` at the end of your message. "
            "Only do this when the mood is friendly or fun. Example: 'That's awesome! [gif: happy dance]'"
        )

    # Short acknowledgment: force a one-phrase reply (model often ignores SOUL otherwise)
    if _is_short_acknowledgment(text):
        context += (
            "\n\n[IMPORTANT] The user just sent a very short acknowledgment (e.g. ok, thanks). "
            "Reply with ONE short phrase only (e.g. 'Got it!', 'Anytime!', 'Take care!'). "
            "Do not add extra sentences like 'Let me know if you need anything.'"
        )
    context += _thinking_instruction(thinking_level)
    context += _reasoning_instruction(reasoning_mode)

    # Load recent messages; skip old assistant error messages so the model doesn't repeat "check your API key"
    recent = await db.get_recent_messages(cid, limit=20)

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in recent
        # Simple heuristic for old string-based errors in DB, plus new structured ones if we saved them
        if not (
            m["role"] == "assistant"
            and (
                m["content"].startswith("Error:")
                or m["content"].startswith("No AI provider")
                or m["content"].startswith(_STATUS_PREFIX)
            )
        )
    ]
    messages.append({"role": "user", "content": text})


    # Context compaction: summarize older messages if history is too long
    from app.compaction import compact_history
    provider_for_compact = get_provider(provider_name)
    if provider_for_compact:
        messages = await compact_history(messages, provider_for_compact, context=context)

    provider = get_provider(provider_name)
    if not provider:
        return f"No AI provider found for '{provider_name}'. Check your provider settings."
    user_model = await db.get_user_provider_model(user_id, provider.name)

    # Exec tool (Claw-style): expose based on exec security policy.
    from app.exec_tool import (
        get_effective_exec_bins,
        get_bash_tool_openai_def,
        get_exec_tool_openai_def,
        run_allowlisted_command,
        parse_exec_arguments,
    )
    from app.config import get_settings
    effective_bins = await get_effective_exec_bins(db, user_id)
    # OpenClaw-style: expose exec based on security policy.
    # - deny: hidden
    # - allowlist: shown when allowlist has bins
    # - full: always shown
    exec_mode = get_settings().exec_security
    offer_exec = exec_mode != "deny" and (exec_mode == "full" or bool(effective_bins))
    tools = list(get_exec_tool_openai_def(effective_bins, security_mode=exec_mode)) if offer_exec else []
    if offer_exec:
        tools = tools + get_bash_tool_openai_def(effective_bins, security_mode=exec_mode)
    if offer_exec:
        logger.info("Exec allowlist: %s; passing tools to provider=%s", sorted(effective_bins), provider.name)
    elif "notes" in text.lower() or "memo" in text.lower():
        logger.warning("User asked for notes/memo but exec allowlist is empty (enable Apple Notes skill or set ASTA_EXEC_ALLOWED_BINS)")
    # Process tool companion for long-running exec sessions (OpenClaw-style).
    if offer_exec:
        from app.process_tool import get_process_tool_openai_def
        tools = tools + get_process_tool_openai_def()

    # Coding compatibility tools (OpenClaw-style): read/write/edit with alias normalization.
    # Enabled for workspace skills and for files workflows.
    from app.workspace import discover_workspace_skills
    workspace_skill_names = {s.name for s in discover_workspace_skills()}
    has_enabled_workspace_skills = any(name in enabled for name in workspace_skill_names)
    offer_coding_compat = has_enabled_workspace_skills or ("files" in enabled)
    if offer_coding_compat:
        from app.coding_compat_tool import get_coding_compat_tools_openai_def
        from app.apply_patch_compat_tool import get_apply_patch_compat_tool_openai_def
        tools = tools + get_coding_compat_tools_openai_def()
        tools = tools + get_apply_patch_compat_tool_openai_def()
    # High-value OpenClaw compat tools for imported skills.
    if has_enabled_workspace_skills:
        from app.openclaw_compat_tools import get_openclaw_web_memory_tools_openai_def
        from app.message_compat_tool import get_message_compat_tool_openai_def
        tools = tools + get_openclaw_web_memory_tools_openai_def()
        tools = tools + get_message_compat_tool_openai_def()

    # Files tool: list_directory/read_file/write_file/allow_path/delete* for filesystem workflows.
    if "files" in enabled:
        from app.files_tool import get_files_tools_openai_def
        tools = tools + get_files_tools_openai_def()
    # Reminders tool: status/list/add/remove (one-shot reminders)
    if "reminders" in enabled:
        from app.reminders_tool import get_reminders_tool_openai_def
        tools = tools + get_reminders_tool_openai_def()
    # Cron tool: status/list/add/update/remove for recurring jobs
    from app.cron_tool import get_cron_tool_openai_def
    tools = tools + get_cron_tool_openai_def()
    tools = tools if tools else None

    from app.providers.fallback import chat_with_fallback, get_available_fallback_providers
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model

    chat_kwargs = dict(
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
        image_bytes=image_bytes,
        image_mime=image_mime,
        thinking_level=thinking_level,
        reasoning_mode=reasoning_mode,
    )
    if tools:
        chat_kwargs["tools"] = tools
    allowed_tool_names = _tool_names_from_defs(tools)

    response, provider_used = await chat_with_fallback(
        provider, messages, fallback_names, **chat_kwargs
    )
    if tools and not response.tool_calls:
        parsed_calls, cleaned = _extract_textual_tool_calls(response.content or "", allowed_tool_names)
        if parsed_calls:
            response.tool_calls = parsed_calls
            response.content = cleaned
            logger.info(
                "Parsed textual tool-call fallback from provider=%s (count=%s)",
                provider_used.name if provider_used else provider.name,
                len(parsed_calls),
            )
    if tools and provider_used:
        has_tc = bool(response.tool_calls)
        logger.info("Provider %s returned tool_calls=%s (count=%s)", provider_used.name, has_tc, len(response.tool_calls or []))

    # Tool-call loop: if model requested exec (or other tools), run and re-call same provider until done
    MAX_TOOL_ROUNDS = 3
    current_messages = list(messages)
    ran_exec_tool = False
    ran_files_tool = False
    ran_reminders_tool = False
    ran_cron_tool = False
    used_tool_labels: list[str] = []
    reminder_tool_scheduled = False
    last_exec_stdout: str = ""
    for _ in range(MAX_TOOL_ROUNDS):
        if tools and not response.tool_calls:
            parsed_calls, cleaned = _extract_textual_tool_calls(response.content or "", allowed_tool_names)
            if parsed_calls:
                response.tool_calls = parsed_calls
                response.content = cleaned
                logger.info(
                    "Parsed textual tool-call fallback mid-round from provider=%s (count=%s)",
                    provider_used.name if provider_used else provider.name,
                    len(parsed_calls),
                )
        if not response.tool_calls or not provider_used:
            break
        # Append assistant message (with content + tool_calls) and run each exec call
        asst_content = response.content or ""
        asst_tool_calls = response.tool_calls
        current_messages.append({
            "role": "assistant",
            "content": asst_content,
            "tool_calls": asst_tool_calls,
        })
        for tc in asst_tool_calls:
            fn = (tc.get("function") or {}) if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("function", {}).get("name")
            args_str = fn.get("arguments") or "{}"
            if name and (reasoning_mode or "").lower() == "stream":
                await _emit_stream_status(
                    db=db,
                    conversation_id=cid,
                    channel=channel,
                    channel_target=channel_target,
                    text=f"Running {_build_tool_trace_label(name)}…",
                )
            if name in ("exec", "bash"):
                params = parse_exec_arguments(args_str)
                cmd = (params.get("command") or "").strip()
                timeout_sec = params.get("timeout_sec")
                yield_ms = params.get("yield_ms")
                background = bool(params.get("background"))
                pty = bool(params.get("pty"))
                workdir = params.get("workdir") if isinstance(params.get("workdir"), str) else None
                logger.info("Exec tool called: command=%r", cmd)
                if background or isinstance(yield_ms, int) or pty:
                    from app.process_tool import run_exec_with_process_support

                    exec_result = await run_exec_with_process_support(
                        cmd,
                        allowed_bins=effective_bins,
                        timeout_seconds=timeout_sec if isinstance(timeout_sec, int) else None,
                        workdir=workdir,
                        background=background,
                        yield_ms=yield_ms if isinstance(yield_ms, int) else None,
                        pty=pty,
                    )
                    status = (exec_result.get("status") or "").strip().lower()
                    if status == "running":
                        ok = True
                        stdout = json.dumps(exec_result, indent=0)
                        stderr = ""
                    elif status in ("completed", "failed"):
                        stdout = (exec_result.get("stdout") or "").strip()
                        stderr = (exec_result.get("stderr") or "").strip()
                        ok = bool(exec_result.get("ok")) if "ok" in exec_result else (status == "completed")
                    else:
                        stdout = ""
                        stderr = (exec_result.get("error") or "Exec failed").strip()
                        ok = False
                else:
                    stdout, stderr, ok = await run_allowlisted_command(
                        cmd,
                        allowed_bins=effective_bins,
                        timeout_seconds=timeout_sec if isinstance(timeout_sec, int) else None,
                        workdir=workdir,
                    )
                ran_exec_tool = True
                used_tool_labels.append(_build_tool_trace_label(name))
                last_exec_stdout = stdout
                logger.info("Exec result: ok=%s stdout_len=%s stderr_len=%s", ok, len(stdout), len(stderr))
                if ok or stdout or stderr:
                    out = f"stdout:\n{stdout}\n" + (f"stderr:\n{stderr}\n" if stderr else "")
                else:
                    out = f"error: {stderr or 'Command not allowed or failed.'}"
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "process":
                from app.process_tool import parse_process_tool_args, run_process_tool

                params = parse_process_tool_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("process", str(params.get("action") or "")))
                out = await run_process_tool(params)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "list_directory":
                from app.files_tool import list_directory as list_dir, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await list_dir(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("list_directory"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "read_file":
                from app.files_tool import read_file_content as read_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await read_file_fn(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("read_file"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "write_file":
                from app.files_tool import write_file as write_file_fn, parse_files_tool_args as parse_files_args

                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                content = params.get("content")
                out = await write_file_fn(path, content if isinstance(content, str) else "", user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("write_file"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "allow_path":
                from app.files_tool import allow_path as allow_path_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await allow_path_fn(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("allow_path"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "delete_file":
                from app.files_tool import delete_file as delete_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_file_fn(path, user_id, db, permanently=permanently)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("delete_file"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "delete_matching_files":
                from app.files_tool import (
                    delete_matching_files as delete_matching_files_fn,
                    parse_files_tool_args as parse_files_args,
                )
                params = parse_files_args(args_str)
                directory = (params.get("directory") or "").strip()
                glob_pattern = (params.get("glob_pattern") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_matching_files_fn(
                    directory,
                    glob_pattern,
                    user_id,
                    db,
                    permanently=permanently,
                )
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("delete_matching_files"))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name in ("read", "write", "edit"):
                from app.coding_compat_tool import (
                    parse_coding_compat_args,
                    run_read_compat,
                    run_write_compat,
                    run_edit_compat,
                )

                params = parse_coding_compat_args(args_str)
                if name == "read":
                    out = await run_read_compat(params, user_id, db)
                elif name == "write":
                    out = await run_write_compat(params, user_id, db)
                else:
                    out = await run_edit_compat(params, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label(name))
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "web_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("web_search"))
                out = await run_web_search_compat(params)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "web_fetch":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_fetch_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("web_fetch"))
                out = await run_web_fetch_compat(params)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "memory_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_search"))
                out = await run_memory_search_compat(params, user_id=user_id)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "memory_get":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_get_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_get"))
                out = await run_memory_get_compat(params)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "apply_patch":
                from app.apply_patch_compat_tool import parse_apply_patch_compat_args, run_apply_patch_compat

                params = parse_apply_patch_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("apply_patch"))
                out = await run_apply_patch_compat(params)
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "message":
                from app.message_compat_tool import parse_message_compat_args, run_message_compat

                params = parse_message_compat_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("message", str(params.get("action") or "send"))
                )
                out = await run_message_compat(
                    params,
                    current_channel=channel,
                    current_target=channel_target,
                )
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "reminders":
                from app.reminders_tool import run_reminders_tool, parse_reminders_tool_args
                params = parse_reminders_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("reminders", str(params.get("action") or ""))
                )
                out = await run_reminders_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                ran_reminders_tool = True
                if (params.get("action") or "").strip().lower() == "add":
                    try:
                        parsed = json.loads(out)
                        if isinstance(parsed, dict) and parsed.get("ok") is True:
                            reminder_tool_scheduled = True
                            extra["reminder_scheduled"] = True
                            extra["reminder_at"] = (
                                parsed.get("display_time")
                                or parsed.get("run_at")
                                or ""
                            )
                    except Exception:
                        pass
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "cron":
                from app.cron_tool import run_cron_tool, parse_cron_tool_args
                params = parse_cron_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("cron", str(params.get("action") or ""))
                )
                out = await run_cron_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                ran_cron_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            else:
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": "Unknown tool."})
        # Re-call same provider with updated messages (no fallback switch); use that provider's model
        tool_kwargs = {**chat_kwargs}
        if provider_used.name == provider.name:
            tool_kwargs["model"] = user_model or None
        else:
            tool_kwargs["model"] = fallback_models.get(provider_used.name)
        # Give the model more time when it has to summarize large tool output (e.g. memo notes)
        if provider_used.name == "openrouter":
            tool_kwargs["timeout"] = 90
        response = await provider_used.chat(current_messages, **tool_kwargs)
        if response.error:
            break

    raw_reply = (response.content or "").strip()
    had_tool_markup = _has_tool_call_markup(raw_reply)
    reply = _strip_tool_call_markup(raw_reply)
    if not reply and had_tool_markup and not response.error:
        reply = "I couldn't execute that tool call format. Ask again and I'll retry with tools."
    reply, suppress_user_reply = _sanitize_silent_reply_markers(reply)

    # If there was a fatal error (Auth/RateLimit) and no content, show the error message to the user
    if not reply and response.error:
        reply = f"Error: {response.error_message or 'Unknown provider error'}"

    # OpenClaw-style preference: scheduler actions should be executed via tools.
    # If a tool-capable model skipped reminders/cron tool calls, apply deterministic fallback
    # from tool logic so we don't hallucinate list/remove outcomes.
    if (
        _provider_supports_tools(provider_name)
        and not ran_reminders_tool
        and not ran_cron_tool
    ):
        scheduler_fallback = await _handle_scheduler_intents(
            db=db,
            user_id=user_id,
            conversation_id=cid,
            text=text,
            channel=channel,
            channel_target=channel_target,
            reminders_enabled=("reminders" in enabled),
        )
        if scheduler_fallback:
            fallback_reply, fallback_label = scheduler_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)

    # OpenClaw-style guardrail: if model skipped files tool calls on a clear files-check request,
    # run deterministic listing fallback (or return a factual access error) instead of pretending.
    if (
        _provider_supports_tools(provider_name)
        and "files" in enabled
        and not ran_files_tool
    ):
        files_fallback = await _handle_files_check_fallback(
            db=db,
            user_id=user_id,
            text=text,
        )
        if files_fallback:
            fallback_reply, fallback_label = files_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)

    # Strict no-fake-check rule for exec-backed checks (Apple Notes/Things): if no exec tool ran,
    # do not allow unverified "I checked..." claims.
    if (
        _provider_supports_tools(provider_name)
        and _is_exec_check_request(text)
        and not ran_exec_tool
    ):
        reply = (
            "I couldn't verify that yet because no Terminal tool call was executed. "
            "Ask again and I'll run the check with tools."
        )
        used_tool_labels.append(_build_tool_trace_label("exec", "required"))

    # Reasoning visibility mode (OpenClaw-like):
    # - off: hide extracted <think> blocks
    # - on/stream: show extracted reasoning above final answer
    final_text, extracted_reasoning = _extract_reasoning_blocks(reply)
    reasoning_mode_norm = (reasoning_mode or "").lower()
    if reasoning_mode_norm == "off":
        # Never leak raw <think> blocks to user output.
        reply = final_text
    elif extracted_reasoning:
        if reasoning_mode_norm == "stream":
            await _emit_stream_status(
                db=db,
                conversation_id=cid,
                channel=channel,
                channel_target=channel_target,
                text=f"Reasoning:\n{extracted_reasoning}",
            )
            # Stream mode emits reasoning as status; final user reply should stay clean.
            reply = final_text
        else:
            reply = f"Reasoning:\n{extracted_reasoning}\n\n{final_text}".strip()
    else:
        reply = final_text

    # OpenClaw-style: generic fallback when we ran exec but got no reply (no skill-specific hints)
    if not reply and ran_exec_tool:
        if last_exec_stdout:
            reply = "I ran the command and got output, but the model didn't return a reply. **Command output:**\n\n```\n"
            max_show = 2000
            excerpt = last_exec_stdout.strip()[:max_show] + ("…" if len(last_exec_stdout) > max_show else "")
            reply += excerpt + "\n```"
        else:
            reply = "I ran the command but didn't get a reply back. Try again or rephrase."

    
    # Expand GIF tags
    if "[gif:" in reply:
        match = re.search(r"\[gif:\s*(.+?)\]", reply, re.IGNORECASE)
        if match:
            from app.cooldowns import is_cooldown_ready, mark_cooldown_now

            query = match.group(1).strip()
            can_send_gif = await is_cooldown_ready(
                db,
                user_id,
                "gif_reply",
                _GIF_COOLDOWN_SECONDS,
            )
            if can_send_gif:
                gif_markdown = await GiphyService.get_gif(query)
                if gif_markdown:
                    reply = reply.replace(match.group(0), "\n" + gif_markdown)
                    await mark_cooldown_now(db, user_id, "gif_reply")
                else:
                    reply = reply.replace(match.group(0), "")
            else:
                reply = reply.replace(match.group(0), "")

    # Extract and apply memories from [SAVE: key: value] in reply
    from app.memories import parse_save_instructions, strip_save_instructions, add_memory
    for k, v in parse_save_instructions(reply):
        add_memory(user_id, k, v)
    reply = strip_save_instructions(reply)

    # Claw-like exec: run allowlisted commands from [ASTA_EXEC: cmd][/ASTA_EXEC], then re-call model with output
    exec_pattern = re.compile(r"\[ASTA_EXEC:\s*([^\]]+)\]\s*\[/ASTA_EXEC\]", re.IGNORECASE)
    exec_matches = list(exec_pattern.finditer(reply))
    exec_outputs: list[str] = []
    if exec_matches:
        # Safety: only honor legacy [ASTA_EXEC] fallback when current user message is clearly exec-intent.
        # Prevents unrelated requests (e.g. reminders/lists) from accidentally running stale exec commands.
        if _is_exec_intent(text):
            from app.exec_tool import get_effective_exec_bins, run_allowlisted_command
            effective_bins = await get_effective_exec_bins(db, user_id)
            for m in exec_matches:
                cmd = m.group(1).strip()
                stdout, stderr, ok = await run_allowlisted_command(cmd, allowed_bins=effective_bins)
                if ok or stdout or stderr:
                    exec_outputs.append(f"Command: {cmd}\nOutput:\n{stdout}\n" + (f"Stderr:\n{stderr}\n" if stderr else ""))
                else:
                    exec_outputs.append(f"Command: {cmd}\nError: {stderr or 'Command not allowed or failed.'}")
            if exec_outputs:
                exec_message = "[Command output from Asta]\n\n" + "\n---\n\n".join(exec_outputs)
                exec_message += "\n\nReply to the user based on this output. Do not use [ASTA_EXEC] in your reply."
                messages_plus = list(messages) + [{"role": "assistant", "content": reply}] + [{"role": "user", "content": exec_message}]
                response2, _ = await chat_with_fallback(
                    provider, messages_plus, fallback_names,
                    context=context, model=user_model or None,
                    _fallback_models=fallback_models,
                )
                if response2.content and not response2.error:
                    reply = response2.content
        # Always strip raw block from user-visible reply.
        reply = exec_pattern.sub("", reply).strip() or reply

    # Create file when AI outputs [ASTA_WRITE_FILE: path]...[/ASTA_WRITE_FILE]
    write_match = re.search(
        r"\[ASTA_WRITE_FILE:\s*([^\]]+)\]\s*\n?(.*?)\[/ASTA_WRITE_FILE\]",
        reply,
        re.DOTALL | re.IGNORECASE,
    )
    if write_match:
        file_path = write_match.group(1).strip()
        file_content = write_match.group(2).strip()
        try:
            from app.routers.files import write_to_allowed_path
            written = await write_to_allowed_path(user_id, file_path, file_content)
            reply = reply.replace(write_match.group(0), f"I've saved that to `{written}`.")
            logger.info("Created file via ASTA_WRITE_FILE: %s", written)
        except Exception as e:
            reply = reply.replace(write_match.group(0), f"I couldn't create that file: {e}.")
            logger.warning("ASTA_WRITE_FILE failed: %s", e)

    # Claw-style cron: [ASTA_CRON_ADD: name|cron_expr|tz|message][/ASTA_CRON_ADD] and [ASTA_CRON_REMOVE: name][/ASTA_CRON_REMOVE]
    cron_add_pattern = re.compile(r"\[ASTA_CRON_ADD:\s*([^\]]+)\]\s*\[/ASTA_CRON_ADD\]", re.IGNORECASE)
    for m in list(cron_add_pattern.finditer(reply)):
        raw = m.group(1).strip()
        parts = [p.strip() for p in raw.split("|", 3)]
        if len(parts) >= 3:
            name, cron_expr = parts[0], parts[1]
            tz = (parts[2] if len(parts) == 4 else None) or None
            message = parts[3] if len(parts) == 4 else parts[2]
            if name and cron_expr and message:
                try:
                    from app.cron_runner import add_cron_job_to_scheduler
                    from app.tasks.scheduler import get_scheduler
                    job_id = await db.add_cron_job(user_id, name, cron_expr, message, tz=tz, channel=channel, channel_target=channel_target)
                    add_cron_job_to_scheduler(get_scheduler(), job_id, cron_expr, tz)
                    reply = reply.replace(m.group(0), f"I've scheduled cron job \"{name}\" ({cron_expr}).")
                except Exception as e:
                    reply = reply.replace(m.group(0), f"I couldn't schedule the cron job: {e}.")
            else:
                reply = reply.replace(m.group(0), "I couldn't parse the cron job (need name|cron_expr|tz|message).")
        else:
            reply = reply.replace(m.group(0), "I couldn't parse the cron job (use name|cron_expr|tz|message).")
    cron_remove_pattern = re.compile(r"\[ASTA_CRON_REMOVE:\s*([^\]]+)\]\s*\[/ASTA_CRON_REMOVE\]", re.IGNORECASE)
    for m in list(cron_remove_pattern.finditer(reply)):
        name = m.group(1).strip()
        if name:
            try:
                from app.cron_runner import reload_cron_jobs
                deleted = await db.delete_cron_job_by_name(user_id, name)
                if deleted:
                    await reload_cron_jobs()
                    reply = reply.replace(m.group(0), f"I've removed the cron job \"{name}\".")
                else:
                    reply = reply.replace(m.group(0), f"No cron job named \"{name}\" found.")
            except Exception as e:
                reply = reply.replace(m.group(0), f"I couldn't remove the cron job: {e}.")
        else:
            reply = reply.replace(m.group(0), "I couldn't parse the cron job name.")

    # Reliability fallback: for tool-capable providers that skipped reminder tool calls,
    # schedule directly from parser so clear reminder intents still work.
    if (
        "reminders" in enabled
        and _provider_supports_tools(provider_name)
        and _looks_like_reminder_set_request(text)
        and not extra.get("reminder_scheduled")
        and not reminder_tool_scheduled
    ):
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)
            if reminder_result.get("reminder_scheduled"):
                when = (reminder_result.get("reminder_at") or "").strip()
                reply = f"Done. I set your reminder{f' for {when}' if when else ''}."
            elif reminder_result.get("reminder_needs_location"):
                reply = "I can set that, but I need your location/timezone first. Tell me your city and country."

    # Post-reply validation: AI claimed it set a reminder but we didn't
    if "reminders" in skills_to_use and not extra.get("reminder_scheduled"):
        lower = reply.lower()
        if any(p in lower for p in ("i've set a reminder", "i set a reminder", "reminder set", "i'll remind you", "i'll send you a message at")):
            reply += "\n\n_I couldn't parse that reminder. Try: \"remind me in 5 min to X\" or \"alarm in 5 min to take a shower\"_"

    # Re-sanitize in case post-processing introduced marker leakage.
    reply, suppress_now = _sanitize_silent_reply_markers(reply)
    suppress_user_reply = suppress_user_reply or suppress_now

    # OpenClaw-style: single generic fallback when reply is empty (no skill-specific hints)
    if (not suppress_user_reply) and (not reply or not reply.strip()):
        reply = "I didn't get a reply back. Try again or rephrase."

    # Optional trace: show tool activity in Telegram/Web replies for debugging.
    trace_settings = _get_trace_settings()
    channel_norm = (channel or "").strip().lower()
    # Telegram already gets proactive "skill status" pings; avoid noisy duplicate footer there.
    allow_trace_for_channel = channel_norm != "telegram"
    if (
        (not suppress_user_reply)
        and trace_settings.asta_show_tool_trace
        and allow_trace_for_channel
        and channel_norm in trace_settings.tool_trace_channels
    ):
        trace_line = _render_tool_trace(used_tool_labels)
        if reply:
            reply = f"{reply}\n\n{trace_line}"
        else:
            reply = trace_line

    # Silent control-path: no assistant message emitted/persisted.
    if suppress_user_reply and not reply.strip():
        return ""

    # Always persist assistant reply (including errors) so web UI matches what user saw on Telegram
    await db.add_message(cid, "assistant", reply, provider.name if not reply.strip().startswith("Error:") and not reply.strip().startswith("No AI provider") else None)
    return reply
