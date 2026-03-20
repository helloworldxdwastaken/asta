import re
import json
import shlex
import logging

logger = logging.getLogger(__name__)

_AUTO_SUBAGENT_EXPLICIT_HINTS = (
    "use subagent",
    "spawn subagent",
    "run this in background",
    "do this in background",
    "background task",
    "in parallel",
    "parallelize",
)
_AUTO_SUBAGENT_BLOCKLIST_HINTS = (
    "what time",
    "weather",
    "remind me",
    "set reminder",
    "cron",
    "lyrics",
    "spotify",
    "check my desktop",
    "list files",
    "apple notes",
    "things app",
    "server status",
)
_AUTO_SUBAGENT_COMPLEXITY_VERBS = (
    "research",
    "investigate",
    "analyze",
    "compare",
    "implement",
    "refactor",
    "review",
    "audit",
    "migrate",
    "plan",
    "document",
    "test",
    "fix",
)


def _looks_like_auto_subagent_request(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    t = raw.lower()
    if t.startswith("/"):
        return False

    # Messages with embedded document context (e.g. from Mac app file attachments)
    # are NOT complex multi-step tasks — skip auto-delegation.
    if "<document " in t or "<document>" in t:
        return False

    if any(h in t for h in _AUTO_SUBAGENT_EXPLICIT_HINTS):
        return True

    # Avoid auto-delegation for short utility/assistant tasks.
    if any(h in t for h in _AUTO_SUBAGENT_BLOCKLIST_HINTS):
        return False

    words = re.findall(r"\b\w+\b", t)
    word_count = len(words)
    if word_count < 45:
        return False

    verb_hits = sum(1 for v in _AUTO_SUBAGENT_COMPLEXITY_VERBS if v in t)
    step_markers = sum(
        1
        for marker in (" then ", " and ", " also ", " plus ", " after ", " finally ", "\n- ", "\n1.")
        if marker in t
    )

    if word_count >= 80:
        return True
    return verb_hits >= 2 and step_markers >= 2


def _subagent_auto_label(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", (text or "").strip())
    if not words:
        return "background task"
    return " ".join(words[:6])[:80]


async def _maybe_auto_spawn_subagent(
    *,
    user_id: str,
    conversation_id: str,
    text: str,
    provider_name: str,
    channel: str,
    channel_target: str,
) -> str | None:
    if channel == "subagent":
        return None
    from app.config import get_settings
    if not bool(get_settings().asta_subagents_auto_spawn):
        return None
    if not _looks_like_auto_subagent_request(text):
        return None

    from app.subagent_orchestrator import spawn_subagent_run

    payload = await spawn_subagent_run(
        user_id=user_id,
        parent_conversation_id=conversation_id,
        task=text.strip(),
        label=_subagent_auto_label(text),
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
        cleanup="keep",
    )
    status = str(payload.get("status") or "").strip().lower()
    if status == "accepted":
        run_id = str(payload.get("runId") or "").strip()
        return (
            f"I started a background subagent for this task [{run_id}]. "
            "I'll post the result here when it finishes."
        )
    if status == "busy":
        running = payload.get("running")
        max_c = payload.get("maxConcurrent")
        return (
            f"I couldn't start a background subagent right now "
            f"(running {running}/{max_c}). Try again in a moment."
        )
    err = str(payload.get("error") or "").strip()
    if err:
        return f"I couldn't start a background subagent: {err}"
    return None


def _parse_subagents_command(text: str) -> tuple[str, list[str]] | None:
    raw = (text or "").strip()
    if not raw.lower().startswith("/subagents"):
        return None
    rest = raw[len("/subagents"):].strip()
    if not rest:
        return "help", []
    try:
        tokens = shlex.split(rest)
    except Exception:
        tokens = rest.split()
    if not tokens:
        return "help", []
    action = (tokens[0] or "").strip().lower()
    return action, [t for t in tokens[1:] if isinstance(t, str)]


def _format_subagents_list(payload: dict) -> str:
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or not runs:
        return "No subagent runs yet. Use /subagents spawn <task>."

    def _status_rank(value: str) -> int:
        s = (value or "").strip().lower()
        if s == "running":
            return 0
        if s in ("timeout", "error", "interrupted"):
            return 1
        if s in ("completed", "stopped"):
            return 2
        return 3

    valid_rows = [r for r in runs if isinstance(r, dict)]
    ordered = sorted(
        valid_rows,
        key=lambda row: (
            _status_rank(str(row.get("status") or "")),
            str(row.get("createdAt") or ""),
        ),
        reverse=False,
    )
    running_count = sum(
        1 for row in ordered if str(row.get("status") or "").strip().lower() == "running"
    )

    lines = [f"Subagents: {len(ordered)} total ({running_count} running)"]
    for i, row in enumerate(ordered, 1):
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("runId") or "").strip() or "unknown"
        status = str(row.get("status") or "unknown").strip().lower()
        label = str(row.get("label") or "").strip() or "task"
        model = str(row.get("model") or "").strip()
        thinking = str(row.get("thinking") or "").strip()
        created = str(row.get("createdAt") or "").strip()
        suffix = []
        if model:
            suffix.append(f"model={model}")
        if thinking:
            suffix.append(f"thinking={thinking}")
        if created:
            suffix.append(f"created={created}")
        extra = f" ({', '.join(suffix)})" if suffix else ""
        lines.append(f"{i}. [{run_id}] {status} - {label}{extra}")
    return "\n".join(lines)


def _format_subagents_history(payload: dict, limit: int) -> str:
    if not isinstance(payload, dict):
        return "Could not read subagent history."
    if payload.get("error"):
        return str(payload.get("error"))
    run_id = str(payload.get("runId") or "unknown")
    status = str(payload.get("status") or "unknown")
    label = str(payload.get("label") or "").strip()
    model = str(payload.get("model") or "").strip()
    thinking = str(payload.get("thinking") or "").strip()
    created = str(payload.get("createdAt") or "").strip()
    ended = str(payload.get("endedAt") or "").strip()
    archived = str(payload.get("archivedAt") or "").strip()
    msgs = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    lines = [f"Subagent [{run_id}] status: {status}"]
    meta: list[str] = []
    if label:
        meta.append(f"label={label}")
    if model:
        meta.append(f"model={model}")
    if thinking:
        meta.append(f"thinking={thinking}")
    if created:
        meta.append(f"created={created}")
    if ended:
        meta.append(f"ended={ended}")
    if archived:
        meta.append(f"archived={archived}")
    if meta:
        lines.append("Meta: " + ", ".join(meta))
    if not msgs:
        lines.append("No history messages.")
        return "\n".join(lines)
    shown = 0
    for msg in reversed(msgs):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip().lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role not in ("assistant", "user"):
            continue
        excerpt = content[:220] + ("..." if len(content) > 220 else "")
        lines.append(f"- {role}: {excerpt}")
        shown += 1
        if shown >= max(1, min(limit, 5)):
            break
    if shown == 0:
        lines.append("No readable user/assistant messages.")
    return "\n".join(lines)


def _extract_wait_timeout_from_args(args: list[str]) -> tuple[int, list[str]]:
    wait_seconds = 0
    out: list[str] = []
    i = 0
    while i < len(args):
        tok = str(args[i] or "").strip()
        low = tok.lower()
        if low == "--wait":
            if i + 1 < len(args):
                nxt = str(args[i + 1] or "").strip()
                if nxt.isdigit():
                    wait_seconds = max(0, min(int(nxt), 300))
                    i += 2
                    continue
            i += 1
            continue
        if low.startswith("--wait="):
            val = low.split("=", 1)[1].strip()
            if val.isdigit():
                wait_seconds = max(0, min(int(val), 300))
            i += 1
            continue
        out.append(tok)
        i += 1
    return wait_seconds, out


def _subagents_help_text() -> str:
    return (
        "Subagents commands:\n"
        "- /subagents list [limit]\n"
        "- /subagents spawn <task>\n"
        "- /subagents info <runId> [limit]\n"
        "- /subagents send <runId> <message> [--wait <seconds>]\n"
        "- /subagents stop <runId>\n"
        "- /subagents help"
    )


async def _handle_subagents_command(
    *,
    text: str,
    user_id: str,
    conversation_id: str,
    provider_name: str,
    channel: str,
    channel_target: str,
) -> str | None:
    parsed = _parse_subagents_command(text)
    if not parsed:
        return None
    action, args = parsed
    from app.subagent_orchestrator import run_subagent_tool

    if action in ("help", "h", "?"):
        return _subagents_help_text()

    if action in ("list", "ls"):
        limit = 20
        if args and args[0].isdigit():
            limit = max(1, min(int(args[0]), 100))
        raw = await run_subagent_tool(
            tool_name="sessions_list",
            params={"limit": limit},
            user_id=user_id,
            parent_conversation_id=conversation_id,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
        )
        try:
            payload = json.loads(raw)
        except Exception:
            return "Could not list subagents right now."
        return _format_subagents_list(payload)

    if action in ("spawn", "run", "start"):
        task = " ".join(args).strip()
        if not task:
            return "Usage: /subagents spawn <task>"
        raw = await run_subagent_tool(
            tool_name="sessions_spawn",
            params={"task": task},
            user_id=user_id,
            parent_conversation_id=conversation_id,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
        )
        try:
            payload = json.loads(raw)
        except Exception:
            return "Could not spawn subagent right now."
        if payload.get("status") == "accepted":
            run_id = str(payload.get("runId") or "").strip()
            return f"Spawned subagent [{run_id}] for: {task}"
        return str(payload.get("error") or "Could not spawn subagent.")

    if action in ("info", "history", "log"):
        if not args:
            return "Usage: /subagents info <runId> [limit]"
        run_id = args[0].strip()
        limit = 20
        if len(args) > 1 and args[1].isdigit():
            limit = max(1, min(int(args[1]), 200))
        raw = await run_subagent_tool(
            tool_name="sessions_history",
            params={"runId": run_id, "limit": limit},
            user_id=user_id,
            parent_conversation_id=conversation_id,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
        )
        try:
            payload = json.loads(raw)
        except Exception:
            return "Could not read subagent history right now."
        return _format_subagents_history(payload, limit)

    if action in ("send", "steer", "tell"):
        wait_seconds, clean_args = _extract_wait_timeout_from_args(args)
        if len(clean_args) < 2:
            return "Usage: /subagents send <runId> <message> [--wait <seconds>]"
        run_id = clean_args[0].strip()
        message = " ".join(clean_args[1:]).strip()
        raw = await run_subagent_tool(
            tool_name="sessions_send",
            params={
                "runId": run_id,
                "message": message,
                "timeoutSeconds": wait_seconds,
            },
            user_id=user_id,
            parent_conversation_id=conversation_id,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
        )
        try:
            payload = json.loads(raw)
        except Exception:
            return "Could not send to subagent right now."
        if payload.get("status") == "accepted":
            return f"Sent to subagent [{run_id}]."
        if payload.get("status") == "completed":
            reply = str(payload.get("reply") or "").strip()
            if reply:
                excerpt = reply[:800] + ("..." if len(reply) > 800 else "")
                return f"Subagent [{run_id}] replied:\n{excerpt}"
            return f"Subagent [{run_id}] completed."
        if payload.get("status") == "timeout":
            waited = int(payload.get("waitedSeconds") or 0)
            return (
                f"Sent to subagent [{run_id}] and waited {waited}s, "
                "but it is still running."
            )
        return str(payload.get("error") or "Could not send to subagent.")

    if action in ("stop", "kill"):
        if not args:
            return "Usage: /subagents stop <runId>"
        run_id = args[0].strip()
        raw = await run_subagent_tool(
            tool_name="sessions_stop",
            params={"runId": run_id},
            user_id=user_id,
            parent_conversation_id=conversation_id,
            provider_name=provider_name,
            channel=channel,
            channel_target=channel_target,
        )
        try:
            payload = json.loads(raw)
        except Exception:
            return "Could not stop subagent right now."
        status = str(payload.get("status") or "").strip()
        if status in ("stopped", "already-ended"):
            return f"Subagent [{run_id}] {status}."
        return str(payload.get("error") or "Could not stop subagent.")

    return _subagents_help_text()
