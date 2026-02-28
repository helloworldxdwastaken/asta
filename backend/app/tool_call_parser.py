"""Tool-call format parsing and tool-utility helpers extracted from handler.py.

All functions here are pure (no DB, no async I/O) and can be imported by
any module without circular-import risk.

Supported tool-call wire formats:
  1. [ASTA_TOOL_CALL]{...}[/ASTA_TOOL_CALL]   — legacy Asta protocol
  2. <tool_call>{...}</tool_call>              — Qwen / Trinity XML
  3. <function_calls><invoke name="...">...</invoke></function_calls>  — OpenClaw / Claude XML
  4. [tool_name: key="value"]                 — bracket shorthand
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Tool trace grouping (name → display group)
# ---------------------------------------------------------------------------

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
    "agents_list": "Subagents",
    "sessions_spawn": "Subagents",
    "sessions_list": "Subagents",
    "sessions_history": "Subagents",
    "sessions_send": "Subagents",
    "sessions_stop": "Subagents",
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
    "agents_list": "agents",
    "sessions_spawn": "spawn",
    "sessions_list": "list",
    "sessions_history": "history",
    "sessions_send": "send",
    "sessions_stop": "stop",
}

_MUTATING_TOOL_NAMES = frozenset(
    {
        "exec",
        "bash",
        "write_file",
        "allow_path",
        "delete_file",
        "delete_matching_files",
        "write",
        "edit",
        "apply_patch",
        "sessions_spawn",
        "sessions_send",
        "sessions_stop",
    }
)
_MUTATING_ACTION_NAMES = frozenset(
    {
        "add",
        "create",
        "set",
        "update",
        "edit",
        "remove",
        "delete",
        "cancel",
        "clear",
        "send",
        "spawn",
        "stop",
        "run",
        "enable",
        "disable",
        "pause",
        "resume",
    }
)
_RECOVERABLE_TOOL_ERROR_KEYWORDS = (
    "required",
    "missing",
    "invalid",
    "must be",
    "must have",
    "needs",
    "requires",
)

# ---------------------------------------------------------------------------
# Tool trace rendering
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tool error classification
# ---------------------------------------------------------------------------

def _extract_tool_error_message(tool_output: str) -> str:
    text = (tool_output or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("error:"):
        return text.split(":", 1)[1].strip() or text
    if lower.startswith("approval-needed:"):
        return text
    if lower.startswith("failed:") or lower.startswith("failed "):
        return text

    parsed: Any
    try:
        parsed = json.loads(text)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""

    if parsed.get("ok") is False or parsed.get("success") is False:
        for key in ("error", "message", "reason", "detail"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Tool reported failure."

    status = parsed.get("status")
    if isinstance(status, str) and status.strip().lower() in {"failed", "error"}:
        for key in ("error", "message", "reason", "detail"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return f"Tool reported status={status.strip()}."

    return ""


def _is_recoverable_tool_error(error_text: str) -> bool:
    low = (error_text or "").strip().lower()
    if not low:
        return False
    return any(keyword in low for keyword in _RECOVERABLE_TOOL_ERROR_KEYWORDS)


def _is_likely_mutating_tool_call(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    name = (tool_name or "").strip().lower()
    if name in _MUTATING_TOOL_NAMES:
        return True
    action = (args or {}).get("action")
    action_norm = action.strip().lower() if isinstance(action, str) else ""
    if name in {"reminders", "cron", "message"}:
        return action_norm in _MUTATING_ACTION_NAMES
    if name == "spotify":
        # Read-only: search, now_playing, list_playlists, list_devices
        # Mutating: play, control, volume, create_playlist, add_to_playlist
        return action_norm not in {"search", "now_playing", "list_playlists", "list_devices"}
    return False


def _build_tool_action_fingerprint(tool_name: str, args: dict[str, Any] | None = None) -> str:
    name = (tool_name or "").strip().lower()
    payload: dict[str, Any] = {}
    data = args if isinstance(args, dict) else {}
    for key in (
        "action",
        "path",
        "file_path",
        "directory",
        "glob_pattern",
        "command",
        "id",
        "job_id",
        "reminder_id",
        "session_id",
        "name",
        "channel",
        "channel_id",
        "thread_id",
    ):
        value = data.get(key)
        if isinstance(value, (str, int, float, bool)):
            if isinstance(value, str) and not value.strip():
                continue
            payload[key] = value
    if not payload:
        return name
    try:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        encoded = str(payload)
    return f"{name}:{encoded}"


# ---------------------------------------------------------------------------
# Tool definition helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tool-call wire format parsing
# ---------------------------------------------------------------------------

def _parse_inline_tool_args(raw: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for m in re.finditer(
        r"""([A-Za-z_][\w\-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^,\]]+))""",
        raw or "",
    ):
        key = (m.group(1) or "").strip()
        if not key:
            continue
        value = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        args[key] = html.unescape(value)
    return args


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

    # Qwen/Trinity-style: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    tc_match = re.search(r"(?is)<tool_call>\s*(\{.*?\})\s*</tool_call>", raw)
    if tc_match:
        try:
            payload = json.loads(tc_match.group(1).strip())
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
                        "id": "text_tool_call_qwen",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                ]
                cleaned = (raw[: tc_match.start()] + raw[tc_match.end() :]).strip()
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

    # Bracket protocol fallback:
    # [allow_path: path="~/Desktop"]
    # [list_directory: path="~/Desktop"]
    bracket_matches = list(
        re.finditer(r"(?is)\[\s*([a-zA-Z_][\w\-]*)\s*:\s*([^\]]*?)\]", raw)
    )
    if bracket_matches:
        tool_calls: list[dict] = []
        remove_spans: list[tuple[int, int]] = []
        for idx, m in enumerate(bracket_matches, start=1):
            name = (m.group(1) or "").strip()
            if not name:
                continue
            # Keep bracket cron payloads in text for dedicated cron protocol handling later.
            if name.lower() == "cron":
                continue
            if allowed_names and name not in allowed_names:
                continue
            body = (m.group(2) or "").strip()
            args = _parse_inline_tool_args(body) if body else {}
            # Treat this as protocol only when it looks like tool arguments.
            if body and ("=" in body) and not args:
                continue
            tool_calls.append(
                {
                    "id": f"text_tool_call_bracket_{idx}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
            remove_spans.append((m.start(), m.end()))
        if tool_calls:
            chunks: list[str] = []
            cursor = 0
            for start, end in remove_spans:
                chunks.append(raw[cursor:start])
                cursor = end
            chunks.append(raw[cursor:])
            cleaned = "".join(chunks).strip()
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
    # Qwen/Trinity-style tool call XML
    if re.search(r"(?is)<tool_call>\s*\{.*?\}\s*</tool_call>", raw):
        return True
    return False


def _strip_tool_call_markup(text: str) -> str:
    raw = text or ""
    if not raw:
        return ""
    cleaned = re.sub(r"\[ASTA_TOOL_CALL\]\s*\{.*?\}\s*\[/ASTA_TOOL_CALL\]", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"(?is)<function_calls>\s*.*?\s*</function_calls>", "", cleaned)
    # Qwen/Trinity-style tool call XML (emitted as text alongside structured tool_calls)
    cleaned = re.sub(r"(?is)<tool_call>\s*\{.*?\}\s*</tool_call>", "", cleaned)
    return cleaned.strip()


def _strip_bracket_tool_protocol(text: str) -> str:
    raw = text or ""
    if not raw:
        return ""
    # Keep [cron: ...] payloads for dedicated cron protocol parsing later in the pipeline.
    tool_names = [n for n in sorted(_TOOL_TRACE_GROUP.keys(), key=len, reverse=True) if n != "cron"]
    if not tool_names:
        return raw.strip()
    names_pat = "|".join(re.escape(n) for n in tool_names)
    pat = rf"(?is)\[\s*(?:{names_pat})\s*:\s*[^\]]*=\s*[^\]]*\]"
    cleaned = re.sub(pat, "", raw)
    return cleaned.strip()
