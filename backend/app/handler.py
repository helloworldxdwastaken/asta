"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import asyncio
import logging
import io
import json
import re
import html
import shlex
from pathlib import Path
from inspect import isawaitable
from typing import Any
from PIL import Image
from app.context import build_context
from app.db import get_db
from app.providers.registry import get_provider
from app.providers.base import ProviderResponse, ProviderError
from app.reminders import send_skill_status, send_notification
from app.time_weather import geocode, parse_location_from_message

# Scheduler handler (extracted from handler.py)
from app.scheduler_handler import (
    handle_scheduler_intents as _handle_scheduler_intents,
    _looks_like_reminder_set_request,
    _looks_like_reminder_list_request,
    _looks_like_cron_list_request,
    _looks_like_schedule_overview_request,
    _looks_like_remove_request,
    _looks_like_update_request,
)

# Services
from app.services.reminder_service import ReminderService
from app.services.learning_service import LearningService
from app.services.giphy_service import GiphyService
from app.stream_state_machine import AssistantStreamStateMachine
from app.thinking_capabilities import supports_xhigh_thinking

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
_APPLE_NOTES_EXPLICIT_HINTS = (
    "apple notes",
    "notes.app",
    "icloud notes",
    "memo",
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
_NOTE_CAPTURE_HINTS = (
    "take a note",
    "note that",
    "add a note",
    "create a note",
    "quick note",
    "save this",
    "write that down",
    "remember this",
    "add to my notes",
    "save a note",
)
_WORKSPACE_NOTES_LIST_HINTS = (
    "what notes",
    "my notes",
    "list notes",
    "show notes",
    "notes i have",
    "do i have notes",
    "which notes",
)
_IMAGE_GEN_REQUEST_VERBS = (
    "make",
    "create",
    "generate",
    "draw",
    "render",
    "illustrate",
    "design",
    "paint",
    "build",
)
_IMAGE_GEN_REQUEST_OBJECTS = (
    "image",
    "picture",
    "photo",
    "art",
    "poster",
    "banner",
    "wallpaper",
    "avatar",
    "logo",
    "mockup",
    "thumbnail",
    "cover",
    "ad",
)

# Providers that can participate in tool/fallback guardrails.
# Ollama is included because Asta uses text tool-call protocols with it.
_TOOL_CAPABLE_PROVIDERS = frozenset({"openai", "groq", "openrouter", "claude", "google", "ollama"})
_VISION_PREPROCESSOR_PROVIDERS = frozenset({"openrouter", "ollama"})
_VISION_PROVIDER_KEY = {
    "openrouter": "openrouter_api_key",
}
_VISION_PROVIDER_ORDER_DEFAULT = ("openrouter", "ollama")  # Nemotron first, Minimax fallback
_VISION_OPENROUTER_MODEL_DEFAULT = "nvidia/nemotron-nano-12b-v2-vl:free"
_VISION_OLLAMA_MODEL_DEFAULT = "minimax-m2.5:cloud"
_VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE = (
    "Image received, but the dedicated vision preprocessor is unavailable. "
    "Asta expects OpenRouter Nemotron first and Ollama Minimax as fallback."
)
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
_FILES_CHECK_QUESTION_HINTS = (
    "what",
    "do i have",
    "any",
)
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
_THINK_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh")
_REASONING_MODES = ("off", "on", "stream")
_FINAL_MODES = ("off", "strict")
# OpenClaw-style: Ollama should not require strict <final> tags.
_STRICT_FINAL_UNSUPPORTED_PROVIDERS = frozenset({"ollama"})
_THINK_DIRECTIVE_PATTERN = re.compile(
    r"(?:^|\s)/(?:thinking|think|t)(?=$|\s|:)",
    re.IGNORECASE,
)
_REASONING_DIRECTIVE_PATTERN = re.compile(
    r"(?:^|\s)/(?:reasoning|reason)(?=$|\s|:)",
    re.IGNORECASE,
)
_REASONING_QUICK_TAG_RE = re.compile(
    r"<\s*/?\s*(?:think(?:ing)?|thought|antthinking|final)\b",
    re.IGNORECASE,
)
_REASONING_FINAL_TAG_RE = re.compile(
    r"<\s*/?\s*final\b[^<>]*>",
    re.IGNORECASE,
)
_REASONING_THINK_TAG_RE = re.compile(
    r"<\s*(/?)\s*(?:think(?:ing)?|thought|antthinking)\b[^<>]*>",
    re.IGNORECASE,
)
_STATUS_PREFIX = "[[ASTA_STATUS]]"
_SENSITIVE_DB_KEY_NAMES = (
    "notion_api_key",
    "giphy_api_key",
    "openai_api_key",
    "openrouter_api_key",
    "anthropic_api_key",
    "groq_api_key",
    "gemini_api_key",
    "google_ai_key",
    "huggingface_api_key",
    "spotify_client_secret",
    "telegram_bot_token",
)
_REDACTED_SECRET = "[REDACTED_SECRET]"
_REDACTED_NOTION_TOKEN = "[REDACTED_NOTION_TOKEN]"
_NOTION_TOKEN_RE = re.compile(r"\bntn_[A-Za-z0-9_-]{8,}\b")
_BEARER_HEADER_RE = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s\"'`]+)")

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


async def _emit_live_stream_event(
    callback,
    payload: dict[str, Any],
) -> None:
    """Best-effort stream event emitter for web SSE/live callbacks."""
    if not callable(callback):
        return
    try:
        maybe = callback(payload)
        if isawaitable(maybe):
            await maybe
    except Exception as e:
        logger.debug("Live stream event callback failed: %s", e)


async def _emit_tool_event(
    *,
    phase: str,          # "start" or "end"
    name: str,
    label: str,
    channel: str,
    channel_target: str,
    stream_event_callback=None,
) -> None:
    """Emit an infrastructure-level tool event (OpenClaw style).
    - web: SSE event with type=tool_start or tool_end
    - telegram: send status message on start only (no noise on end)
    """
    event_type = "tool_start" if phase == "start" else "tool_end"
    if callable(stream_event_callback):
        await _emit_live_stream_event(
            stream_event_callback,
            {"type": event_type, "name": name, "label": label},
        )
    ch = (channel or "").strip().lower()
    if ch == "telegram" and channel_target and phase == "start":
        from app.reminders import send_notification
        try:
            await send_notification(ch, channel_target, f"🔧 {label}…")
        except Exception as e:
            logger.debug("Could not send tool status to telegram: %s", e)


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from text (case-insensitive, greedy)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()


async def _generate_conversation_title(
    cid: str,
    user_text: str,
    assistant_reply: str,
    provider_name: str,
) -> None:
    """Generate an AI title for a new conversation and persist it.
    Fires as a background task after the first exchange completes.
    """
    try:
        db = get_db()
        # Guard: skip if title already set (e.g. parallel request)
        existing = await db.get_conversation_title(cid)
        if existing:
            return
        provider = get_provider(provider_name)
        # Strip <think> blocks from the reply before using as context, and disable
        # thinking for this call so the response itself won't contain reasoning blocks.
        clean_reply = _strip_think_blocks(assistant_reply)
        snippet = (user_text[:300] + "\n\n" + clean_reply[:300]).strip()
        messages = [
            {
                "role": "user",
                "content": (
                    "Give this conversation a short title (3–6 words, sentence case, "
                    "no punctuation at the end). Reply with ONLY the title, nothing else.\n\n"
                    + snippet
                ),
            }
        ]
        response = await provider.chat(messages, thinking_level="off", reasoning_mode="off")
        if response.error:
            logger.debug("Auto-title provider error: %s", response.error_message or response.error)
            return
        raw = _strip_think_blocks(response.content or "")
        title = raw.strip().strip('"').strip("'")
        if len(title) > 80:
            title = title[:80]
        # Fallback: if model only generated thinking with no output (e.g. Ollama/DeepSeek),
        # derive a title from the user's message instead.
        if not title:
            words = user_text.strip().split()
            title = " ".join(words[:7])
            if len(user_text.split()) > 7:
                title += "…"
            title = title[:80]
        if title:
            await db.set_conversation_title(cid, title)
            logger.debug("Auto-titled conversation %s → %r", cid, title)
    except Exception as e:
        logger.debug("Could not auto-title conversation %s: %s", cid, e)


def _longest_common_prefix_size(left: str, right: str) -> int:
    max_len = min(len(left), len(right))
    idx = 0
    while idx < max_len and left[idx] == right[idx]:
        idx += 1
    return idx


def _largest_suffix_prefix_overlap(left: str, right: str, *, max_scan: int = 2048) -> int:
    """Return overlap size where suffix(left) == prefix(right)."""
    if not left or not right:
        return 0
    cap = min(len(left), len(right), max_scan)
    for size in range(cap, 0, -1):
        if left.endswith(right[:size]):
            return size
    return 0


def _merge_stream_source_text(current: str, incoming: str) -> str:
    """Merge provider stream text while tolerating duplicated or full-content chunks.

    Providers should send text deltas, but some fallbacks can emit snapshots. This keeps
    the accumulated source text monotonic and avoids duplicate appends.
    """
    cur = current or ""
    inc = incoming or ""
    if not inc:
        return cur
    if not cur:
        return inc

    # Incoming is full snapshot that already includes current content.
    if inc.startswith(cur):
        return inc
    # Incoming is duplicate/older subset.
    if cur.startswith(inc) or inc in cur:
        return cur

    overlap = _largest_suffix_prefix_overlap(cur, inc)
    if overlap > 0:
        return cur + inc[overlap:]

    # Snapshot style fallback that still contains current text somewhere.
    if cur in inc and len(inc) >= len(cur):
        return inc

    return cur + inc


def _compute_incremental_delta(previous: str, current: str) -> str:
    prev = previous or ""
    cur = current or ""
    if not cur:
        return ""
    if cur.startswith(prev):
        return cur[len(prev):]
    common = _longest_common_prefix_size(prev, cur)
    if common > 0:
        return cur[common:]
    return cur


def _plan_stream_text_update(
    *,
    previous: str,
    current: str,
    allow_rewrite: bool = False,
) -> tuple[bool, str, bool]:
    """Plan a streaming text update.

    Returns (should_emit, delta, rewrote_non_prefix).
    """
    prev = previous or ""
    # Only strip leading whitespace — trailing newlines are part of content
    cur = (current or "").lstrip()
    if not cur or cur == prev:
        return False, "", False
    if prev and not cur.startswith(prev):
        if not allow_rewrite:
            return False, "", False
        return True, cur, True
    delta = _compute_incremental_delta(prev, cur)
    if not delta and cur == prev:
        return False, "", False
    return True, delta or cur, False


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


def _is_explicit_apple_notes_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(hint in t for hint in _APPLE_NOTES_EXPLICIT_HINTS)


def _is_note_capture_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # Apple Notes / memo CLI intents are separate from local markdown note capture.
    if _is_explicit_apple_notes_request(t):
        return False
    return any(hint in t for hint in _NOTE_CAPTURE_HINTS)


def _is_workspace_notes_list_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if _is_explicit_apple_notes_request(t):
        return False
    if _is_note_capture_request(t):
        return False
    if "notes" not in t and "note" not in t:
        return False
    if t in {"notes", "note", "my notes"}:
        return True
    return any(hint in t for hint in _WORKSPACE_NOTES_LIST_HINTS)


def _sanitize_note_path_component(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.replace("\\", "/")
    cleaned = cleaned.strip("/.")
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_.")
    return cleaned


def _canonicalize_note_write_path(path: str) -> str:
    """Normalize note writes into workspace-relative memos/* markdown files."""
    raw = (path or "").strip().replace("\\", "/")
    if not raw:
        return "memos/note.md"

    candidate = raw
    while candidate.startswith("./"):
        candidate = candidate[2:]
    if candidate.startswith("~/workspace/"):
        candidate = candidate[len("~/workspace/") :]
    elif candidate.startswith("~/"):
        # For note capture intents, keep notes in workspace/notes even if model emits home paths.
        candidate = candidate[2:]
    if Path(candidate).is_absolute():
        # For note capture intents, keep notes in workspace/notes even if model emits absolute paths.
        candidate = Path(candidate).as_posix().lstrip("/")
    while candidate.lower().startswith("workspace/"):
        candidate = candidate[len("workspace/") :]
    if candidate.startswith("~/"):
        candidate = candidate[2:]

    parts = [p for p in candidate.split("/") if p and p not in (".", "..")]
    lower_parts = [p.lower() for p in parts]

    note_tail: list[str]
    if "notes" in lower_parts:
        idx = lower_parts.index("notes")
        note_tail = parts[idx + 1 :]
    else:
        note_tail = [parts[-1]] if parts else []

    sanitized_parts = [_sanitize_note_path_component(part) for part in note_tail]
    sanitized_parts = [part for part in sanitized_parts if part]
    if not sanitized_parts:
        sanitized_parts = ["note.md"]

    filename = sanitized_parts[-1]
    if "." in filename:
        stem = filename.rsplit(".", 1)[0]
        filename = f"{stem}.md" if stem else "note.md"
    else:
        filename = f"{filename}.md"
    sanitized_parts[-1] = filename

    return "notes/" + "/".join(sanitized_parts)


def _provider_supports_tools(provider_name: str) -> bool:
    return (provider_name or "").strip().lower() in _TOOL_CAPABLE_PROVIDERS


def _provider_supports_strict_final(provider_name: str) -> bool:
    normalized = (provider_name or "").strip().lower()
    if not normalized:
        return True
    return normalized not in _STRICT_FINAL_UNSUPPORTED_PROVIDERS


async def _run_vision_preprocessor(
    *,
    text: str,
    image_bytes: bytes,
    image_mime: str | None,
) -> tuple[str, str, str | None] | None:
    from app.config import get_settings
    from app.keys import get_api_key

    settings = get_settings()
    if not bool(getattr(settings, "asta_vision_preprocess", True)):
        return None

    raw_order = str(getattr(settings, "asta_vision_provider_order", "") or "").strip().lower()
    provider_order = [
        p.strip()
        for p in raw_order.split(",")
        if p.strip() and p.strip() in _VISION_PREPROCESSOR_PROVIDERS
    ]
    if not provider_order:
        provider_order = list(_VISION_PROVIDER_ORDER_DEFAULT)
    else:
        for fallback_provider in _VISION_PROVIDER_ORDER_DEFAULT:
            if fallback_provider not in provider_order:
                provider_order.append(fallback_provider)

    openrouter_model = (
        str(getattr(settings, "asta_vision_openrouter_model", _VISION_OPENROUTER_MODEL_DEFAULT) or "").strip()
        or _VISION_OPENROUTER_MODEL_DEFAULT
    )
    image_prompt = (text or "").strip() or "Describe this image."
    vision_context = (
        "You are Asta's vision preprocessor. Analyze the image and return concise factual notes.\n"
        "Output plain text only (no code fences). Include:\n"
        "- scene summary\n"
        "- visible text (OCR)\n"
        "- important objects/entities\n"
        "- uncertainty notes if relevant"
    )

    for candidate in provider_order:
        provider = get_provider(candidate)
        if not provider:
            continue
        chat_kwargs: dict = {
            "context": vision_context,
            "image_bytes": image_bytes,
            "image_mime": image_mime or "image/jpeg",
            "thinking_level": "off",
        }
        if candidate == "openrouter":
            key_name = _VISION_PROVIDER_KEY.get(candidate)
            if not key_name:
                continue
            api_key = await get_api_key(key_name)
            if not api_key:
                continue
            if openrouter_model:
                chat_kwargs["model"] = openrouter_model
            chat_kwargs["skip_model_policy"] = True
        elif candidate == "ollama":
            chat_kwargs["model"] = _VISION_OLLAMA_MODEL_DEFAULT
        try:
            resp = await provider.chat(
                [{"role": "user", "content": image_prompt}],
                **chat_kwargs,
            )
        except Exception as e:
            logger.warning("Vision preprocessor provider=%s failed: %s", candidate, e)
            continue
        if resp.error:
            logger.warning(
                "Vision preprocessor provider=%s returned error=%s",
                candidate,
                (resp.error_message or str(resp.error)),
            )
            continue
        analysis = (resp.content or "").strip()
        if not analysis:
            continue
        model_used = str(chat_kwargs.get("model") or "").strip() or None
        return analysis[:5000], candidate, model_used
    return None


def _thinking_instruction(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv == "off":
        return ""
    if lv == "minimal":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: minimal. Keep reasoning very brief, but still verify critical facts "
            "and tool outputs before answering."
        )
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
    if lv == "xhigh":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: xhigh. Use maximum deliberate planning and strict verification. "
            "For any external-state claim, require concrete tool evidence before asserting results."
        )
    return ""


def _normalize_thinking_level(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    collapsed = re.sub(r"[\s_-]+", "", key)
    if collapsed in ("xhigh", "extrahigh"):
        return "xhigh"
    if key in ("off",):
        return "off"
    if key in ("on", "enable", "enabled"):
        return "low"
    if key in ("min", "minimal"):
        return "minimal"
    if key in ("low", "thinkhard", "think-hard", "think_hard"):
        return "low"
    if key in ("mid", "med", "medium", "thinkharder", "think-harder", "harder"):
        return "medium"
    if key in ("high", "ultra", "ultrathink", "thinkhardest", "highest", "max"):
        return "high"
    if key in ("think",):
        return "minimal"
    return None


def _normalize_reasoning_mode(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in ("off", "false", "no", "0", "hide", "hidden", "disable", "disabled"):
        return "off"
    if key in ("on", "true", "yes", "1", "show", "visible", "enable", "enabled"):
        return "on"
    if key in ("stream", "streaming", "draft", "live"):
        return "stream"
    return None


def _parse_inline_thinking_directive(text: str) -> tuple[bool, str | None, str | None, str]:
    """Parse OpenClaw-style inline thinking directive in mixed text.

    Returns (matched, normalized_level_or_none, raw_level_or_none, cleaned_text).
    """
    raw = (text or "")
    m = _THINK_DIRECTIVE_PATTERN.search(raw)
    if not m:
        return False, None, None, raw
    start, end = m.span()
    i = end
    length = len(raw)
    while i < length and raw[i].isspace():
        i += 1
    if i < length and raw[i] == ":":
        i += 1
        while i < length and raw[i].isspace():
            i += 1
    arg_start = i
    while i < length and (raw[i].isalpha() or raw[i] in "-_"):
        i += 1
    raw_level = (raw[arg_start:i] or "").strip().lower() or None
    level = _normalize_thinking_level(raw_level)
    cleaned = (raw[:start] + " " + raw[i:]).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return True, level, raw_level, cleaned


def _parse_inline_reasoning_directive(text: str) -> tuple[bool, str | None, str | None, str]:
    """Parse OpenClaw-style inline reasoning directive in mixed text.

    Returns (matched, normalized_mode_or_none, raw_mode_or_none, cleaned_text).
    """
    raw = (text or "")
    m = _REASONING_DIRECTIVE_PATTERN.search(raw)
    if not m:
        return False, None, None, raw
    start, end = m.span()
    i = end
    length = len(raw)
    while i < length and raw[i].isspace():
        i += 1
    if i < length and raw[i] == ":":
        i += 1
        while i < length and raw[i].isspace():
            i += 1
    arg_start = i
    while i < length and (raw[i].isalpha() or raw[i] in "-_"):
        i += 1
    raw_mode = (raw[arg_start:i] or "").strip().lower() or None
    mode = _normalize_reasoning_mode(raw_mode)
    cleaned = (raw[:start] + " " + raw[i:]).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return True, mode, raw_mode, cleaned


def _supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    return supports_xhigh_thinking(provider, model)


def _format_thinking_options(provider: str | None, model: str | None) -> str:
    options = ["off", "minimal", "low", "medium", "high"]
    if _supports_xhigh_thinking(provider, model):
        options.append("xhigh")
    return ", ".join(options)


async def _emit_reasoning_stream_progressively(
    *,
    db,
    conversation_id: str,
    channel: str,
    channel_target: str,
    reasoning: str,
) -> None:
    lines = [line.strip() for line in (reasoning or "").splitlines() if line.strip()]
    if not lines:
        return
    built: list[str] = []
    for line in lines:
        built.append(line)
        formatted = _format_reasoning_message("\n".join(built))
        if not formatted:
            continue
        await _emit_stream_status(
            db=db,
            conversation_id=conversation_id,
            channel=channel,
            channel_target=channel_target,
            text=formatted,
        )


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


def _final_tag_instruction(mode: str) -> str:
    fm = (mode or "off").strip().lower()
    if fm != "strict":
        return ""
    return (
        "\n\n[FINAL]\n"
        "You MUST wrap user-visible output in exactly one <final>...</final> block. "
        "Text outside <final> may be hidden."
    )


def _parse_fenced_code_regions(text: str) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    open_region: tuple[int, str, int] | None = None
    offset = 0
    line_pattern = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
    length = len(text)

    while offset <= length:
        next_newline = text.find("\n", offset)
        line_end = length if next_newline == -1 else next_newline
        line = text[offset:line_end]
        match = line_pattern.match(line)
        if match:
            marker = match.group(2)
            marker_char = marker[0]
            marker_len = len(marker)
            if open_region is None:
                open_region = (offset, marker_char, marker_len)
            elif open_region[1] == marker_char and marker_len >= open_region[2]:
                regions.append((open_region[0], line_end))
                open_region = None
        if next_newline == -1:
            break
        offset = next_newline + 1

    if open_region is not None:
        regions.append((open_region[0], length))

    regions.sort(key=lambda region: region[0])
    return regions


def _is_inside_code_region(index: int, regions: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in regions)


def _parse_inline_code_regions(text: str, fenced_regions: list[tuple[int, int]]) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    open_ticks = 0
    open_start = -1
    i = 0
    fenced_index = 0
    length = len(text)

    while i < length:
        while fenced_index < len(fenced_regions) and i >= fenced_regions[fenced_index][1]:
            fenced_index += 1
        if fenced_index < len(fenced_regions):
            fenced_start, fenced_end = fenced_regions[fenced_index]
            if fenced_start <= i < fenced_end:
                i = fenced_end
                continue
        if text[i] != "`":
            i += 1
            continue

        run_start = i
        run_length = 0
        while i < length and text[i] == "`":
            run_length += 1
            i += 1

        if open_ticks == 0:
            open_ticks = run_length
            open_start = run_start
        elif run_length == open_ticks:
            regions.append((open_start, i))
            open_ticks = 0
            open_start = -1

    if open_ticks > 0 and open_start >= 0:
        regions.append((open_start, length))

    regions.sort(key=lambda region: region[0])
    return regions


def _build_code_regions(text: str) -> list[tuple[int, int]]:
    fenced = _parse_fenced_code_regions(text)
    inline = _parse_inline_code_regions(text, fenced)
    regions = fenced + inline
    regions.sort(key=lambda region: region[0])
    return regions


def _strip_pattern_outside_code(
    text: str,
    pattern: re.Pattern[str],
    code_regions: list[tuple[int, int]],
) -> str:
    if not text:
        return text
    output: list[str] = []
    last_index = 0
    for match in pattern.finditer(text):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        output.append(text[last_index:index])
        last_index = match.end()
    output.append(text[last_index:])
    return "".join(output)


def _apply_reasoning_trim(value: str, mode: str = "both") -> str:
    trim_mode = (mode or "both").strip().lower()
    if trim_mode == "none":
        return value
    if trim_mode == "start":
        return value.lstrip()
    return value.strip()


def _extract_final_tag_content(text: str) -> tuple[str, bool]:
    """Return content inside <final> blocks (code-safe), plus whether a real final tag was seen."""
    raw = (text or "")
    if not raw:
        return "", False
    code_regions = _build_code_regions(raw)
    in_final = False
    saw_final = False
    last_index = 0
    out_parts: list[str] = []

    for match in _REASONING_FINAL_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        tag_text = match.group(0) or ""
        is_close = bool(re.match(r"<\s*/", tag_text))
        if not in_final and not is_close:
            in_final = True
            saw_final = True
            last_index = match.end()
            continue
        if in_final and is_close:
            out_parts.append(raw[last_index:index])
            in_final = False
            last_index = match.end()

    if in_final:
        out_parts.append(raw[last_index:])

    return "".join(out_parts), saw_final


def _strip_reasoning_tags_from_text(
    text: str,
    *,
    mode: str = "strict",  # strict | preserve
    trim: str = "both",    # none | start | both
    strict_final: bool = False,
) -> str:
    """OpenClaw-style thinking/final tag stripping with code-span safety."""
    raw = (text or "")
    if not raw:
        return raw
    if not _REASONING_QUICK_TAG_RE.search(raw):
        if strict_final:
            return ""
        return _apply_reasoning_trim(raw, trim)

    cleaned = raw
    code_regions = _build_code_regions(cleaned)

    result_parts: list[str] = []
    in_thinking = False
    last_index = 0

    for match in _REASONING_THINK_TAG_RE.finditer(cleaned):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))

        if not in_thinking:
            result_parts.append(cleaned[last_index:index])
            if not is_close:
                in_thinking = True
        elif is_close:
            in_thinking = False

        last_index = match.end()

    mode_norm = (mode or "strict").strip().lower()
    if (not in_thinking) or mode_norm == "preserve":
        result_parts.append(cleaned[last_index:])

    without_thinking = "".join(result_parts)

    if strict_final:
        final_only, saw_final = _extract_final_tag_content(without_thinking)
        if not saw_final:
            return ""
        final_code_regions = _build_code_regions(final_only)
        final_only = _strip_pattern_outside_code(final_only, _REASONING_FINAL_TAG_RE, final_code_regions)
        return _apply_reasoning_trim(final_only, trim)

    pre_code_regions = _build_code_regions(without_thinking)
    without_final_tags = _strip_pattern_outside_code(
        without_thinking,
        _REASONING_FINAL_TAG_RE,
        pre_code_regions,
    )
    return _apply_reasoning_trim(without_final_tags, trim)


def _extract_thinking_from_tagged_text(text: str) -> str:
    """Extract text inside closed <think>/<thinking>/<thought>/<antthinking> blocks."""
    raw = (text or "")
    if not raw:
        return ""
    if not _REASONING_QUICK_TAG_RE.search(raw):
        return ""

    code_regions = _build_code_regions(raw)
    reasoning_parts: list[str] = []
    in_thinking = False
    reasoning_start = 0

    for match in _REASONING_THINK_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))

        if not in_thinking and not is_close:
            in_thinking = True
            reasoning_start = match.end()
            continue

        if in_thinking and is_close:
            chunk = raw[reasoning_start:index].strip()
            if chunk:
                reasoning_parts.append(chunk)
            in_thinking = False

    return "\n\n".join(reasoning_parts).strip()


def _extract_thinking_from_tagged_stream(text: str) -> str:
    """Streaming-friendly extraction: closed blocks first, otherwise last open block tail."""
    raw = (text or "")
    if not raw:
        return ""
    if not _REASONING_QUICK_TAG_RE.search(raw):
        return ""

    closed = _extract_thinking_from_tagged_text(raw)
    if closed:
        return closed

    code_regions = _build_code_regions(raw)
    last_open_start: int | None = None
    last_open_end: int | None = None
    last_close_start: int | None = None

    for match in _REASONING_THINK_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))
        if is_close:
            last_close_start = index
        else:
            last_open_start = index
            last_open_end = match.end()

    if last_open_start is None or last_open_end is None:
        return ""
    if last_close_start is not None and last_close_start > last_open_start:
        return closed

    return raw[last_open_end:].strip()


def _format_reasoning_message(text: str) -> str:
    trimmed = (text or "").strip()
    if not trimmed:
        return ""
    return f"Reasoning:\n{trimmed}"


def _extract_reasoning_blocks(text: str, *, strict_final: bool = False) -> tuple[str, str]:
    raw = (text or "")
    if not raw:
        return "", ""
    final_text = _strip_reasoning_tags_from_text(
        raw,
        mode="strict",
        trim="both",
        strict_final=strict_final,
    )
    reasoning_text = _extract_thinking_from_tagged_text(raw)
    if not reasoning_text:
        reasoning_text = _extract_thinking_from_tagged_stream(raw)
    return final_text, reasoning_text


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
    has_question_hint = any(v in t for v in _FILES_CHECK_QUESTION_HINTS)
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
    return (has_verb or has_question_hint) and has_target


def _looks_like_image_generation_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t.startswith("/imagine") or t.startswith("imagine "):
        return True
    # Pure capability questions should not trigger image generation fallback.
    if any(
        k in t
        for k in (
            "do you have access",
            "have access to image",
            "image generation tool",
            "which model",
            "what model",
            "best model",
            "api key",
            "rate limit",
            "how many steps",
        )
    ):
        return False
    has_request_verb = any(re.search(rf"\b{re.escape(v)}\b", t) for v in _IMAGE_GEN_REQUEST_VERBS)
    has_image_object = any(re.search(rf"\b{re.escape(v)}\b", t) for v in _IMAGE_GEN_REQUEST_OBJECTS)
    return has_request_verb and has_image_object


def _reply_claims_image_tool_unavailable(reply: str) -> bool:
    t = (reply or "").strip().lower()
    if not t:
        return False
    denies_access = any(
        k in t
        for k in (
            "don't have access",
            "do not have access",
            "isn't available",
            "is not available",
            "can't generate images",
            "cannot generate images",
            "image generation service is currently unavailable",
            "image generation service unavailable",
        )
    )
    image_context = any(
        k in t
        for k in (
            "image_gen",
            "image generation",
            "generate images",
            "generate an image",
            "picture",
        )
    )
    return denies_access and image_context


def _extract_image_markdown_from_tool_output(tool_output: str) -> tuple[str | None, str | None]:
    raw = (tool_output or "").strip()
    if not raw:
        return None, "Image generation returned empty output."
    if raw.startswith("!["):
        return raw, None
    try:
        payload = json.loads(raw)
    except Exception:
        return None, raw[:500]
    if isinstance(payload, dict):
        md = (payload.get("image_markdown") or "").strip()
        if md:
            return md, None
        err = (payload.get("error") or "").strip()
        if err:
            return None, err
    return None, raw[:500]


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

    def _clean_candidate(value: str) -> str:
        q = (value or "").strip().strip("\"'`").strip(" .?!,")
        q = re.sub(r"^(any|some|all|the|a|an)\s+", "", q, flags=re.IGNORECASE).strip()
        generic = {"files", "file", "folders", "folder", "items", "stuff"}
        if q.lower() in generic:
            return ""
        if q and len(q) <= 120:
            return q
        return ""

    for pat in (
        r"\bfor\s+(.+)$",
        r"\bnamed\s+(.+)$",
        r"\bcalled\s+(.+)$",
    ):
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            q = _clean_candidate(m.group(1))
            if q:
                return q

    # Natural phrasing support:
    # - "any screenshots on my desktop?"
    # - "find notes in my documents"
    m = re.search(
        r"\b(?:any|some|all|find|search(?: for)?|look(?:ing)? for|check(?: for)?)\s+(.+?)\s+"
        r"(?:on|in)\s+(?:my|the)\s+(?:desktop|documents|downloads)\b",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        q = _clean_candidate(m.group(1))
        if q:
            return q
    return ""


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _name_matches_query(name: str, query: str) -> bool:
    nn = _normalize_match_text(name)
    nq = _normalize_match_text(query)
    if not nn or not nq:
        return False
    if nq in nn:
        return True
    # Handle simple plural phrasing ("screenshots" -> "screenshot").
    if nq.endswith("s") and len(nq) > 3:
        return nq[:-1] in nn
    return False


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


def _make_status_message(text: str) -> str:
    return f"{_STATUS_PREFIX}{(text or '').strip()}"


async def _emit_stream_status(
    *,
    db,
    conversation_id: str,
    channel: str,
    channel_target: str,
    text: str,
    stream_event_callback=None,
    stream_event_type: str = "status",
) -> None:
    msg = (text or "").strip()
    if not msg:
        return
    if callable(stream_event_callback):
        await _emit_live_stream_event(
            stream_event_callback,
            {
                "type": stream_event_type,
                "text": msg,
            },
        )
    ch = (channel or "").strip().lower()
    if ch == "telegram" and channel_target:
        try:
            await send_notification(ch, channel_target, msg)
        except Exception as e:
            logger.debug("Could not send stream status to channel=%s: %s", ch, e)
    # For live-stream web requests, status is delivered over SSE and should stay ephemeral.
    if ch == "web" and not callable(stream_event_callback):
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


def _looks_like_command_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(
        k in t
        for k in (
            "command",
            "commands",
            "terminal",
            "shell",
            "bash",
            "zsh",
            "cli",
            "script",
            "run this",
            "how to run",
            "install",
        )
    )


def _strip_shell_command_leakage(reply: str) -> tuple[str, bool]:
    raw = (reply or "")
    if not raw.strip():
        return "", False
    out_lines: list[str] = []
    removed = False
    cmd_line = re.compile(
        r"(?is)^\s*(?:cd|git|npm|pnpm|yarn|bun|python|python3|node|uv|pip|brew|docker|kubectl|ls|cat|grep|rg|find|curl|wget)\b"
    )
    for line in raw.splitlines():
        ln = line.strip()
        if not ln:
            out_lines.append(line)
            continue
        if cmd_line.search(ln) or ">/dev/null" in ln or "2>/dev/null" in ln or "&&" in ln or "||" in ln:
            removed = True
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip(), removed


def _redact_local_paths(text: str) -> str:
    raw = text or ""
    if not raw:
        return ""
    out = raw
    path_patterns = (
        r"/Users/[^\s\"'`]+",
        r"/home/[^\s\"'`]+",
        r"~/(?:[^\s\"'`]+)",
        r"[A-Za-z]:\\[^\s\"'`]+",
    )
    for pat in path_patterns:
        out = re.sub(pat, "[path]", out)
    return out


def _dedupe_secret_values(values: list[str]) -> list[str]:
    uniq = {
        v.strip()
        for v in values
        if isinstance(v, str) and v.strip() and len(v.strip()) >= 6
    }
    return sorted(uniq, key=len, reverse=True)


async def _load_sensitive_key_values(db) -> list[str]:
    values: list[str] = []
    for key_name in _SENSITIVE_DB_KEY_NAMES:
        try:
            val = await db.get_stored_api_key(key_name)
        except Exception:
            continue
        if isinstance(val, str) and val.strip():
            values.append(val.strip())
    return _dedupe_secret_values(values)


async def _redact_sensitive_reply_content(reply: str, db) -> tuple[str, bool]:
    out = reply or ""
    if not out:
        return "", False

    changed = False
    for secret in await _load_sensitive_key_values(db):
        if secret in out:
            out = out.replace(secret, _REDACTED_SECRET)
            changed = True

    out, notion_hits = _NOTION_TOKEN_RE.subn(_REDACTED_NOTION_TOKEN, out)
    if notion_hits:
        changed = True

    out, bearer_hits = _BEARER_HEADER_RE.subn(r"\1[REDACTED_SECRET]", out)
    if bearer_hits:
        changed = True

    return out, changed


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


def _learn_help_text() -> str:
    return (
        "Learn commands:\n"
        "- /learn <topic> - Save information about a topic to memory\n"
        "- /learn list - Show saved topics\n"
        "- /learn delete <topic> - Delete a saved topic\n"
        "- /learn help - Show this help"
    )


def _parse_learn_command(text: str) -> tuple[str, list[str]] | None:
    """Parse /learn command. Returns (action, args) or None if not a learn command."""
    raw = (text or "").strip()
    if not raw.lower().startswith("/learn"):
        return None
    rest = raw[len("/learn"):].strip()
    if not rest:
        return "help", []
    try:
        tokens = shlex.split(rest)
    except Exception:
        tokens = rest.split()
    if not tokens:
        return "help", []
    first = (tokens[0] or "").strip().lower()
    if first in ("help", "h", "?", "list", "ls", "delete", "remove", "rm"):
        return first, [t for t in tokens[1:] if isinstance(t, str)]
    # Default path: /learn <topic...>
    return "learn", [t for t in tokens if isinstance(t, str)]


async def _handle_learn_command(
    *,
    user_id: str,
    text: str,
    channel: str,
    channel_target: str,
) -> str | None:
    """Handle /learn command - save information to memory/RAG."""
    parsed = _parse_learn_command(text)
    if not parsed:
        return None
    action, args = parsed

    if action in ("help", "h", "?"):
        return _learn_help_text()

    if action in ("list", "ls"):
        from app.rag.service import get_rag
        try:
            topics = get_rag().list_topics()
            if not topics:
                return "You haven't saved any topics yet. Use /learn <topic> to save information."
            lines = [f"You have {len(topics)} saved topic(s):"]
            for i, topic in enumerate(topics[:20], 1):
                if isinstance(topic, dict):
                    name = topic.get("topic", "Unknown")
                    lines.append(f"{i}. {name}")
                else:
                    lines.append(f"{i}. {topic}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Could not list learned topics: %s", e)
            return "Could not list saved topics."

    if action in ("delete", "remove", "rm"):
        # Delete a saved topic
        if not args:
            return "Usage: /learn delete <topic_name>"
        topic_name = " ".join(args).strip()
        if not topic_name:
            return "Please specify a topic to delete."
        from app.rag.service import get_rag
        try:
            deleted = int(get_rag().delete_topic(topic_name))
            if deleted > 0:
                return f"Deleted topic: {topic_name}"
            return f"Could not delete topic '{topic_name}'. It may not exist."
        except Exception as e:
            logger.warning("Could not delete learned topic: %s", e)
            return f"Could not delete topic '{topic_name}'."

    # Default: learn/save a topic - use LearningService
    topic_text = " ".join(args).strip()
    if not topic_text:
        return _learn_help_text()
    
    # Process via LearningService to save to RAG
    try:
        from app.services.learning_service import LearningService
        result = await LearningService.process_learning(
            user_id=user_id,
            text=f"learn about {topic_text}",
            channel=channel,
            channel_target=channel_target,
        )
        if result and result.get("is_learning"):
            return f"Saved to memory: '{topic_text}'. I'll remember this."
    except Exception as e:
        logger.warning("Could not learn topic: %s", e)
    
    # Fallback response
    return f"Saved to memory: '{topic_text}'. I'll remember this."


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


async def _handle_workspace_notes_list_fallback(
    *,
    text: str,
    limit: int = 20,
) -> tuple[str, str] | None:
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


def _append_selected_agent_context(context: str, extra: dict) -> str:
    selected = extra.get("selected_agent") if isinstance(extra, dict) else None
    if not isinstance(selected, dict):
        return context

    aid = str(selected.get("id") or "").strip()
    name = str(selected.get("name") or "").strip() or aid or "agent"
    desc = str(selected.get("description") or "").strip()
    agent_prompt = str(selected.get("system_prompt") or "").strip()

    sections: list[str] = []
    sections.append("[SELECTED AGENT]")
    sections.append(f"You are currently routed to agent '{name}' (id: {aid or 'unknown'}).")
    if desc:
        sections.append(f"Agent description: {desc}")
    skills = selected.get("skills")
    if isinstance(skills, list):
        normalized = [str(s).strip() for s in skills if str(s).strip()]
        if normalized:
            sections.append(f"Allowed skills for this agent: {', '.join(normalized)}")
        else:
            sections.append("Allowed skills for this agent: (none)")
    sections.append(
        "Follow this agent's intent and style for this turn, while still obeying higher-priority safety/policy instructions."
    )
    if agent_prompt:
        sections.append("")
        sections.append("[AGENT PROMPT]")
        sections.append(agent_prompt)

    # Reliability boost: if this agent is constrained to exactly one workspace
    # skill, preload that SKILL.md so the model does not skip/forget to read it.
    # This is especially important for API-heavy skills (e.g. Notion) where small
    # command mistakes lead to false negatives.
    skills_for_agent = selected.get("skills")
    if isinstance(skills_for_agent, list):
        normalized_skill_ids: list[str] = []
        seen_skill_ids: set[str] = set()
        for item in skills_for_agent:
            sid = str(item).strip().lower()
            if not sid or sid in seen_skill_ids:
                continue
            seen_skill_ids.add(sid)
            normalized_skill_ids.append(sid)
        if len(normalized_skill_ids) == 1:
            try:
                from app.workspace import discover_workspace_skills

                target_skill_id = normalized_skill_ids[0]
                resolved = next(
                    (s for s in discover_workspace_skills() if str(s.name).strip().lower() == target_skill_id),
                    None,
                )
                if resolved and resolved.file_path.is_file():
                    raw_skill = resolved.file_path.read_text(encoding="utf-8", errors="replace").strip()
                    if raw_skill:
                        # Safety cap to avoid unbounded prompt growth from unusually large skill files.
                        max_chars = 12000
                        if len(raw_skill) > max_chars:
                            raw_skill = raw_skill[:max_chars].rstrip() + "\n\n[TRUNCATED FOR CONTEXT SIZE]"
                        sections.append("")
                        sections.append("[AGENT SKILL DIRECTIVES]")
                        sections.append(
                            f"Preloaded allowed skill '{target_skill_id}' from {resolved.file_path}. "
                            "Follow these instructions exactly for this turn."
                        )
                        sections.append("")
                        sections.append(raw_skill)
            except Exception as e:
                logger.warning("Could not preload selected agent skill context: %s", e)

    snippets = extra.get("agent_knowledge_snippets") if isinstance(extra, dict) else None
    if isinstance(snippets, list) and snippets:
        sections.append("")
        sections.append("[AGENT KNOWLEDGE SNIPPETS]")
        sections.append(
            "These were retrieved from the agent's local knowledge folder. Prefer them when relevant."
        )
        for idx, item in enumerate(snippets[:6], start=1):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "unknown")
            line_start = int(item.get("line_start") or 0)
            line_end = int(item.get("line_end") or 0)
            excerpt = str(item.get("snippet") or "").strip()
            if not excerpt:
                continue
            sections.append(f"{idx}. Source: {source}:{line_start}-{line_end}")
            sections.append(excerpt)
            sections.append("")

    payload = "\n".join(sections).strip()
    if not payload:
        return context
    return context + "\n\n" + payload


def _selected_agent_skill_filter(extra: dict) -> list[str] | None:
    selected = extra.get("selected_agent") if isinstance(extra, dict) else None
    if not isinstance(selected, dict):
        return None
    raw = selected.get("skills")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        sid = str(item).strip().lower()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        normalized.append(sid)
    return normalized


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
    _out: dict | None = None,
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

    raw_user_text = text
    cid = conversation_id or await db.get_or_create_conversation(user_id, channel)
    # Persist user message early so Telegram (and web) thread shows it even if handler or provider fails later
    user_content = f" [Image: {image_mime or 'image/jpeg'}] {text}" if image_bytes else text
    await db.add_message(cid, "user", user_content)
    extra = extra_context or {}
    try:
        # Named-agent routing syntax from UI: "@Agent Name: message".
        from app.routers.agents import resolve_agent_mention_in_text
        from app.agent_knowledge import (
            ensure_agent_knowledge_layout,
            retrieve_agent_knowledge_snippets,
        )

        selected_agent, cleaned_text = await resolve_agent_mention_in_text(text, user_id=user_id)
        if selected_agent:
            text = (cleaned_text or "").strip() or text
            aid = str(selected_agent.get("id") or "").strip()
            selected_payload = {
                "id": aid,
                "name": str(selected_agent.get("name") or "").strip(),
                "description": str(selected_agent.get("description") or "").strip(),
                "system_prompt": str(selected_agent.get("system_prompt") or "").strip(),
            }
            agent_skills_raw = selected_agent.get("skills")
            if isinstance(agent_skills_raw, list):
                agent_skills = [
                    str(s).strip().lower()
                    for s in agent_skills_raw
                    if str(s).strip()
                ]
                if agent_skills_raw == []:
                    selected_payload["skills"] = []
                elif agent_skills:
                    selected_payload["skills"] = list(dict.fromkeys(agent_skills))
            knowledge_path = ensure_agent_knowledge_layout(aid)
            if knowledge_path:
                selected_payload["knowledge_path"] = str(knowledge_path)
            extra["selected_agent"] = selected_payload

            # Agent-scoped model/thinking defaults (unless subagent overrides are explicit).
            agent_model = str(selected_agent.get("model") or "").strip()
            if agent_model and not extra.get("subagent_model_override"):
                extra["agent_model_override"] = agent_model
            agent_thinking = str(selected_agent.get("thinking") or "").strip().lower()
            if agent_thinking and not extra.get("subagent_thinking_override"):
                extra["agent_thinking_override"] = agent_thinking

            snippets = retrieve_agent_knowledge_snippets(agent_id=aid, query=text)
            if snippets:
                extra["agent_knowledge_snippets"] = snippets
                logger.info(
                    "Agent knowledge: selected=%s snippets=%d query=%r",
                    aid,
                    len(snippets),
                    text[:120],
                )
            logger.info("Agent routing: selected=%s name=%s", aid, selected_payload.get("name") or aid)
    except Exception as e:
        logger.warning("Agent routing/knowledge failed: %s", e)

    stream_event_callback = extra.get("_stream_event_callback")
    if not callable(stream_event_callback):
        stream_event_callback = None
    stream_events_enabled = bool(stream_event_callback) and (channel or "").strip().lower() == "web"
    live_stream_machine: AssistantStreamStateMachine | None = None
    if mood is None:
        mood = await db.get_user_mood(user_id)
    extra["mood"] = mood
    thinking_level = await db.get_user_thinking_level(user_id)
    thinking_override = (
        extra.get("subagent_thinking_override")
        or extra.get("agent_thinking_override")
        or ""
    ).strip().lower()
    if thinking_override in _THINK_LEVELS:
        thinking_level = thinking_override
    extra["thinking_level"] = thinking_level
    reasoning_mode = await db.get_user_reasoning_mode(user_id)
    extra["reasoning_mode"] = reasoning_mode
    reasoning_mode_norm = (reasoning_mode or "").strip().lower()
    final_mode = await db.get_user_final_mode(user_id)
    if final_mode not in _FINAL_MODES:
        final_mode = "off"
    extra["final_mode"] = final_mode
    if provider_name == "default":
        provider_name = await db.get_user_default_ai(user_id)
    strict_final_mode_requested = final_mode == "strict"
    strict_final_mode_enabled = (
        strict_final_mode_requested
        and _provider_supports_strict_final(provider_name)
    )
    if strict_final_mode_requested and not strict_final_mode_enabled:
        logger.info(
            "Strict final mode requested but disabled for provider=%s (OpenClaw-style provider guardrail).",
            provider_name,
        )

    # OpenClaw-style inline directives:
    # - /t <level>, /think:<level>, /thinking <level>
    # - /reasoning <off|on|stream>, /reason <mode>
    # - supports mixed text (e.g. "please /think high run this")
    # - /think (query current level)
    # - /reasoning (query current mode)
    model_override = (
        extra.get("subagent_model_override")
        or extra.get("agent_model_override")
        or ""
    ).strip()
    directive_model = model_override or await db.get_user_provider_model(user_id, provider_name)
    think_options = _format_thinking_options(provider_name, directive_model)

    directive_text = text
    think_matched, think_level, think_raw_level, think_rest = _parse_inline_thinking_directive(directive_text)
    if think_matched:
        directive_text = think_rest
    reasoning_matched, reasoning_level, reasoning_raw_level, reasoning_rest = _parse_inline_reasoning_directive(directive_text)
    if reasoning_matched:
        directive_text = reasoning_rest

    if think_matched:
        if think_raw_level is None:
            reply = (
                f"Current thinking level: {thinking_level}. "
                f"Options: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if think_level not in _THINK_LEVELS:
            reply = (
                f'Unrecognized thinking level "{think_raw_level}". '
                f"Valid levels: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if think_level == "xhigh" and not _supports_xhigh_thinking(provider_name, directive_model):
            reply = (
                'Thinking level "xhigh" is not supported for your current model. '
                f"Valid levels: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        await db.set_user_thinking_level(user_id, think_level)
        thinking_level = await db.get_user_thinking_level(user_id)
        extra["thinking_level"] = thinking_level

    if reasoning_matched:
        if reasoning_raw_level is None:
            reply = (
                f"Current reasoning mode: {reasoning_mode}. "
                "Options: off, on, stream."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if reasoning_level not in _REASONING_MODES:
            reply = (
                f'Unrecognized reasoning mode "{reasoning_raw_level}". '
                "Valid levels: off, on, stream."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        await db.set_user_reasoning_mode(user_id, reasoning_level)
        reasoning_mode = await db.get_user_reasoning_mode(user_id)
        extra["reasoning_mode"] = reasoning_mode
        reasoning_mode_norm = (reasoning_mode or "").strip().lower()

    if think_matched or reasoning_matched:
        text = directive_text
        if not text:
            parts: list[str] = []
            if think_matched and think_raw_level is not None:
                parts.append(f"Thinking level set to {thinking_level}.")
            if reasoning_matched and reasoning_raw_level is not None:
                parts.append(f"Reasoning mode set to {reasoning_mode}.")
            reply = " ".join(parts).strip() or "OK."
            await db.add_message(cid, "assistant", reply, "script")
            return reply

    # OpenClaw-style explicit subagent command UX (single-user):
    # /subagents list|spawn|info|send|stop
    subagents_cmd_reply = await _handle_subagents_command(
        text=text,
        user_id=user_id,
        conversation_id=cid,
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
    )
    if subagents_cmd_reply is not None:
        await db.add_message(cid, "assistant", subagents_cmd_reply, "script")
        return subagents_cmd_reply

    # Learn command - explicit /learn X only (not automatic from conversation)
    learn_cmd_reply = await _handle_learn_command(
        user_id=user_id,
        text=text,
        channel=channel,
        channel_target=channel_target,
    )
    if learn_cmd_reply is not None:
        await db.add_message(cid, "assistant", learn_cmd_reply, "script")
        return learn_cmd_reply

    auto_subagent_reply = await _maybe_auto_spawn_subagent(
        user_id=user_id,
        conversation_id=cid,
        text=text,
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
    )
    if auto_subagent_reply is not None:
        await db.add_message(cid, "assistant", auto_subagent_reply, "script")
        return auto_subagent_reply

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
    agent_skill_filter = _selected_agent_skill_filter(extra)
    if agent_skill_filter is not None:
        enabled &= set(agent_skill_filter)
        logger.info(
            "Applied selected-agent skill filter: allowed=%s enabled_after_filter=%s",
            agent_skill_filter,
            sorted(enabled),
        )

    # --- SERVICE CALLS (only when skill is enabled) ---

    # 1. Reminders
    # OpenClaw-style flow uses tool calls for capable providers; keep this as a fallback for providers without tools.
    if "reminders" in enabled and not _provider_supports_tools(provider_name):
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)

    # 2. Learning - DISABLED: automatic "learn about X" from conversation removed
    # Only /learn command now triggers learning (handled above)
    # if "learn" in enabled:
    #     learning_result = await LearningService.process_learning(user_id, text, channel, channel_target)
    #     if learning_result:
    #         extra.update(learning_result)

    # 3. Spotify: populate connection status in extra so context section can inform the LLM.
    # Actual Spotify actions are handled via the spotify LLM tool (Option B - tool-based).
    if "spotify" in enabled:
        from app.spotify_client import get_user_access_token as _spotify_get_token
        _spotify_token = await _spotify_get_token(user_id)
        if _spotify_token:
            extra["spotify_play_connected"] = True
        else:
            _spotify_row = await db.get_spotify_tokens(user_id)
            if _spotify_row:
                extra["spotify_reconnect_needed"] = True
            else:
                extra["spotify_play_connected"] = False

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
    if skill_labels and channel == "telegram" and channel_target:
        await send_skill_status(channel, channel_target, skill_labels)
    if skill_labels and (reasoning_mode or "").lower() == "stream":
        await _emit_stream_status(
            db=db,
            conversation_id=cid,
            channel=channel,
            channel_target=channel_target,
            text=" • ".join(skill_labels),
            stream_event_callback=stream_event_callback,
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
    context = _append_selected_agent_context(context, extra)
    
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
    if provider_name in ("openrouter", "ollama"):
        context += _reasoning_instruction(reasoning_mode)
    context += _final_tag_instruction("strict" if strict_final_mode_enabled else "off")
    if extra.get("force_web"):
        context += (
            "\n\n[WEB MODE]\n"
            "Prefer using web_search and web_fetch for up-to-date information when the user asks factual/current questions. "
            "After using web tools, synthesize a normal helpful answer (don't dump raw tool output)."
        )
    if channel != "subagent":
        context += (
            "\n\n[SUBAGENTS]\n"
            "For long or parallelizable work, use sessions_spawn to delegate a focused background subagent run. "
            "Use sessions_list/sessions_history to inspect results."
        )

    effective_user_text = text
    if image_bytes:
        vision_result = await _run_vision_preprocessor(
            text=text,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
        if vision_result:
            analysis, vision_provider, vision_model = vision_result
            source = vision_provider + (f"/{vision_model}" if vision_model else "")
            context += (
                "\n\n[VISION PREPROCESSOR]\n"
                "The user shared an image. A separate vision model already analyzed it. "
                "Use the vision analysis block from the user message as the image observation source."
            )
            effective_user_text = (
                f"{text}\n\n"
                f"[VISION_ANALYSIS source={source}]\n"
                f"{analysis}\n"
                f"[/VISION_ANALYSIS]"
            )
            image_bytes = None
            image_mime = None
            logger.info("Vision preprocess complete using %s", source)
        else:
            await db.add_message(cid, "assistant", _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE, "script")
            return _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE

    # Load recent messages; skip old assistant error messages so the model doesn't repeat "check your API key"
    recent = await db.get_recent_messages(cid, limit=20)
    if text != raw_user_text and recent:
        last = recent[-1]
        if isinstance(last, dict) and last.get("role") == "user" and str(last.get("content") or "") == user_content:
            # When inline directives are stripped, avoid sending both raw and cleaned user text.
            recent = recent[:-1]

    messages = [
        {
            "role": m["role"],
            # Strip textual tool-call markup from saved assistant messages before sending to
            # the model — older messages may have <tool_call> / [ASTA_TOOL_CALL] tags stored
            # in the DB. If the model sees these in its own history it will try to re-execute
            # them, causing repeated identical tool calls on every new request.
            "content": _strip_tool_call_markup(m["content"]) if m["role"] == "assistant" else (m["content"] or ""),
        }
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
    messages.append({"role": "user", "content": effective_user_text})


    # Context compaction: summarize older messages if history is too long.
    # Pass model + provider_name so the budget scales with the model's context window.
    # NOTE: user_model is not yet resolved here; use directive_model (same value at this point).
    from app.compaction import compact_history
    provider_for_compact = get_provider(provider_name)
    if provider_for_compact:
        try:
            messages = await compact_history(
                messages,
                provider_for_compact,
                model=directive_model,
                provider_name=provider_name,
                context=context,
            )
        except TypeError as e:
            # Backward-compat for tests/mocks patching compact_history with older signatures.
            err = str(e).lower()
            if "unexpected keyword argument" in err and ("model" in err or "provider_name" in err):
                messages = await compact_history(
                    messages,
                    provider_for_compact,
                    context=context,
                )
            else:
                raise

    provider = get_provider(provider_name)
    if not provider:
        return f"No AI provider found for '{provider_name}'. Check your provider settings."
    if image_bytes:
        await db.add_message(cid, "assistant", _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE, "script")
        return _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE
    user_model = await db.get_user_provider_model(user_id, provider.name)
    model_override = (
        extra.get("subagent_model_override")
        or extra.get("agent_model_override")
        or ""
    ).strip()
    if model_override:
        user_model = model_override
    if thinking_level == "xhigh" and not _supports_xhigh_thinking(provider.name, user_model):
        # Keep stored preference intact, but downgrade unsupported runtime requests.
        thinking_level = "high"
        extra["thinking_level"] = thinking_level

    # Exec tool (Claw-style): expose based on exec security policy.
    from app.exec_tool import (
        get_effective_exec_bins,
        get_bash_tool_openai_def,
        get_exec_tool_openai_def,
        prepare_allowlisted_command,
        run_allowlisted_command,
        parse_exec_arguments,
        truncate_output_tail,
        OUTPUT_EVENT_TAIL_CHARS,
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
    # Also allow web tools on-demand (e.g. UI \"Web\" toggle) even without workspace skills.
    if has_enabled_workspace_skills or extra.get("force_web"):
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
    # Spotify tool: search/play/control/playlists — full LLM-driven integration.
    if "spotify" in enabled:
        from app.spotify_tool import get_spotify_tools_openai_def
        tools = tools + get_spotify_tools_openai_def()
    # Image generation tool — Gemini primary, Hugging Face FLUX.1-dev fallback.
    from app.keys import get_api_key as _get_api_key_img
    _gemini_key = await _get_api_key_img("gemini_api_key") or await _get_api_key_img("google_ai_key")
    _hf_key = await _get_api_key_img("huggingface_api_key")
    if _gemini_key or _hf_key:
        from app.image_gen_tool import get_image_gen_tool_openai_def
        tools = tools + get_image_gen_tool_openai_def()
    # Single-user OpenClaw-style subagent orchestration tools.
    if channel != "subagent":
        from app.subagent_orchestrator import get_subagent_tools_openai_def
        tools = tools + get_subagent_tools_openai_def()
    tools = tools if tools else None

    from app.providers.fallback import (
        chat_with_fallback,
        chat_with_fallback_stream,
        get_available_fallback_providers,
    )
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model

    chat_kwargs = dict(
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
        _runtime_db=db,
        _runtime_user_id=user_id,
        image_bytes=image_bytes,
        image_mime=image_mime,
        thinking_level=thinking_level,
        reasoning_mode=reasoning_mode,
    )
    if tools:
        chat_kwargs["tools"] = tools
    allowed_tool_names = _tool_names_from_defs(tools)

    live_stream_reasoning_enabled = reasoning_mode_norm == "stream"
    # Enable provider streaming for real-time web assistant deltas, even when reasoning mode is off.
    live_model_stream_enabled = live_stream_reasoning_enabled or stream_events_enabled
    live_stream_reasoning_emitted = False

    async def _emit_live_assistant_text(text_value: str, delta: str) -> None:
        if not stream_events_enabled:
            return
        await _emit_live_stream_event(
            stream_event_callback,
            {
                "type": "assistant",
                "text": (text_value or "").lstrip(),
                "delta": delta or "",
            },
        )

    async def _emit_live_reasoning_text(text_value: str, delta: str) -> None:
        next_text = (text_value or "").strip()
        if not next_text:
            return
        if stream_events_enabled:
            await _emit_live_stream_event(
                stream_event_callback,
                {
                    "type": "reasoning",
                    "text": next_text,
                    "delta": delta or "",
                },
            )
            return
        await _emit_stream_status(
            db=db,
            conversation_id=cid,
            channel=channel,
            channel_target=channel_target,
            text=next_text,
            stream_event_callback=stream_event_callback,
            stream_event_type="reasoning",
        )

    def _extract_live_assistant_text(raw_stream_text: str) -> str:
        assistant_live = _strip_reasoning_tags_from_text(
            raw_stream_text,
            mode="strict",
            trim="both",
            strict_final=strict_final_mode_enabled,
        )
        return _strip_bracket_tool_protocol(_strip_tool_call_markup(assistant_live or "")).strip()

    async def _on_model_stream_event(payload: dict[str, Any]) -> None:
        if not live_stream_machine:
            return
        await live_stream_machine.on_event(payload)

    async def _on_model_text_delta(delta_text: str) -> None:
        if not live_stream_machine or not delta_text:
            return
        await live_stream_machine.on_event({"type": "text_delta", "delta": delta_text})

    if live_model_stream_enabled:
        live_stream_machine = AssistantStreamStateMachine(
            merge_source_text=_merge_stream_source_text,
            plan_text_update=_plan_stream_text_update,
            extract_assistant_text=_extract_live_assistant_text,
            extract_reasoning_text=_extract_thinking_from_tagged_stream,
            format_reasoning=_format_reasoning_message,
            emit_assistant=_emit_live_assistant_text,
            emit_reasoning=_emit_live_reasoning_text,
            stream_reasoning=live_stream_reasoning_enabled,
        )

    if live_model_stream_enabled:
        response, provider_used = await chat_with_fallback_stream(
            provider,
            messages,
            fallback_names,
            on_stream_event=_on_model_stream_event,
            **chat_kwargs,
        )
        live_stream_reasoning_emitted = bool(
            live_stream_machine and live_stream_machine.reasoning_emitted
        )
    else:
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
    MAX_TOOL_ROUNDS = 30
    current_messages = list(messages)
    
    # Initialize tool loop detector for this conversation
    from app.tool_loop_detection import get_session_detector, inject_loop_warning
    loop_detector = get_session_detector(cid)
    
    # Track if a critical loop was detected to break the tool execution
    critical_loop_detected = False
    critical_loop_message = ""

    ran_exec_tool = False
    ran_any_tool = False
    exec_tool_call_count = 0   # count exec calls within this request to trigger script nudge
    ran_files_tool = False
    ran_image_gen_tool = False
    ran_reminders_tool = False
    ran_cron_tool = False
    used_tool_labels: list[str] = []
    reminder_tool_scheduled = False
    last_exec_stdout: str = ""
    last_exec_stderr: str = ""
    last_exec_command: str = ""
    last_exec_error: str = ""
    last_tool_output: str = ""
    last_tool_label: str = ""
    last_tool_error: str = ""
    last_tool_error_label: str = ""
    last_tool_error_mutating = False
    last_tool_error_fingerprint: str = ""

    def _record_tool_outcome(
        *,
        tool_name: str,
        tool_output: str,
        tool_args: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> None:
        nonlocal ran_any_tool, last_tool_output, last_tool_label
        nonlocal last_tool_error, last_tool_error_label, last_tool_error_mutating, last_tool_error_fingerprint

        ran_any_tool = True
        label = _build_tool_trace_label(tool_name, action)
        output_text = (tool_output or "").strip()
        last_tool_output = output_text
        last_tool_label = label

        mutating = _is_likely_mutating_tool_call(tool_name, tool_args)
        fingerprint = _build_tool_action_fingerprint(tool_name, tool_args)
        error_text = _extract_tool_error_message(output_text)
        if error_text:
            last_tool_error = error_text
            last_tool_error_label = label
            last_tool_error_mutating = mutating
            last_tool_error_fingerprint = fingerprint
            return

        if not last_tool_error:
            return

        if last_tool_error_mutating:
            if last_tool_error_fingerprint and fingerprint == last_tool_error_fingerprint:
                last_tool_error = ""
                last_tool_error_label = ""
                last_tool_error_mutating = False
                last_tool_error_fingerprint = ""
            return

        # Non-mutating errors are recoverable once any later tool call succeeds.
        last_tool_error = ""
        last_tool_error_label = ""
        last_tool_error_mutating = False
        last_tool_error_fingerprint = ""

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
        # Strip any textual tool-call markup (e.g. <tool_call> XML from Trinity/Qwen models)
        # from the content before storing it in the conversation history. If the model
        # sees its own <tool_call> tags in prior turns it will try to re-execute them,
        # causing identical-command loops.
        asst_content = _strip_tool_call_markup(response.content or "")
        asst_tool_calls = response.tool_calls
        current_messages.append({
            "role": "assistant",
            "content": asst_content,
            "tool_calls": asst_tool_calls,
        })

        # Track seen IDs to prevent duplicates
        seen_ids = set()

        for tc in asst_tool_calls:
            fn = (tc.get("function") or {}) if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("function", {}).get("name")
            args_str = fn.get("arguments") or "{}"
            args_data: dict[str, Any] = {}
            if isinstance(args_str, dict):
                args_data = args_str
            elif isinstance(args_str, str):
                try:
                    parsed_args = json.loads(args_str)
                    if isinstance(parsed_args, dict):
                        args_data = parsed_args
                except Exception:
                    args_data = {}

            # SECURITY: Validate tool name against registry
            if not name:
                logger.warning("Tool call missing name: %s", tc)
                out = "Error: Tool call missing name"
                _record_tool_outcome(tool_name="tool_call", tool_output=out, tool_args=args_data)
                # Truncate extremely large tool output to prevent context overflow/model failure
                MAX_CHARS = 10000
                if len(out) > MAX_CHARS:
                    logger.info("Truncating tool output from %d to %d chars", len(out), MAX_CHARS)
                    out = out[:MAX_CHARS] + f"\n\n[TRUNCATED: original output was {len(out)} chars]"
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
                continue

            # Normalize and validate tool name
            name = name.strip().lower()
            out = None
            if name not in allowed_tool_names:
                logger.warning("Tool '%s' not in allowed tools: %s", name, sorted(allowed_tool_names))
                out = f"Error: Tool '{name}' not available (not in registry)"

            # SECURITY: Validate database availability for tools that need it
            db_required_tools = {
                "list_directory", "read_file", "write_file", "delete_file",
                "delete_matching_files", "allow_path", "reminders", "cron",
                "message", "agents_list", "sessions_spawn", "sessions_list",
                "sessions_history", "sessions_send", "sessions_stop"
            }
            if name in db_required_tools and db is None:
                out = f"Error: Database not available for tool '{name}'"
                logger.error("Tool %s requires database but db is None", name)

            # Validate and normalize tool_call_id
            tool_call_id = tc.get("id", "")
            if not tool_call_id:
                logger.warning("Tool call missing ID, generating fallback: %s", name)
                tool_call_id = f"{name}_{len(current_messages)}"

            # Check for duplicate IDs
            if tool_call_id in seen_ids:
                logger.error("Duplicate tool_call_id: %s", tool_call_id)
                tool_call_id = f"{tool_call_id}_dup_{len(seen_ids)}"
            seen_ids.add(tool_call_id)

            # === TOOL LOOP DETECTION ===
            # Check for loops before executing the tool
            if loop_detector and name:
                loop_result = loop_detector.detect_loop(name, args_data)
                if loop_result.stuck:
                    if loop_result.level == "critical":
                        # Critical - block the tool execution
                        critical_loop_detected = True
                        critical_loop_message = loop_result.message
                        logger.warning(f"Tool loop blocked: {name} - {loop_result.message}")
                        out = f"Error: Tool execution blocked due to loop detection.\n\n{loop_result.message}"
                        current_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": out})
                        continue
                    else:
                        # Warning - inject warning into tool result but allow execution
                        logger.info(f"Tool loop warning: {name} - {loop_result.message}")
                        # Record the call anyway so we can track progress
                        loop_detector.record_tool_call(name, args_data, tool_call_id)
                        # Note: We'll record the outcome after execution
                else:
                    # No loop detected - record the call
                    loop_detector.record_tool_call(name, args_data, tool_call_id)
            # === END TOOL LOOP DETECTION ===

            if name:
                await _emit_tool_event(
                    phase="start",
                    name=name,
                    label=_build_tool_trace_label(name),
                    channel=channel,
                    channel_target=channel_target,
                    stream_event_callback=stream_event_callback,
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
                precheck_argv, precheck_err = prepare_allowlisted_command(
                    cmd,
                    allowed_bins=effective_bins,
                )
                if (
                    precheck_err
                    and exec_mode == "allowlist"
                    and "not in allowlist" in precheck_err.lower()
                ):
                    from app.exec_approvals import create_pending_exec_approval

                    approval_id, requested_bin = await create_pending_exec_approval(
                        db=db,
                        user_id=user_id,
                        channel=channel,
                        channel_target=channel_target,
                        command=cmd,
                        timeout_sec=timeout_sec if isinstance(timeout_sec, int) else None,
                        workdir=workdir,
                        background=background,
                        pty=pty,
                    )
                    out = (
                        f"approval-needed: id={approval_id} binary={requested_bin or 'unknown'} command={cmd}\n"
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny."
                    )
                    ran_exec_tool = True
                    last_exec_command = cmd
                    last_exec_stdout = ""
                    last_exec_stderr = ""
                    last_exec_error = (
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny."
                    )
                    used_tool_labels.append(_build_tool_trace_label(name))
                elif precheck_err and exec_mode != "allowlist":
                    ran_exec_tool = True
                    last_exec_command = cmd
                    last_exec_stdout = ""
                    last_exec_stderr = ""
                    last_exec_error = precheck_err
                    used_tool_labels.append(_build_tool_trace_label(name))
                    out = f"error: {precheck_err}"
                else:
                    # precheck_argv is intentionally not reused; runtime functions re-validate for safety.
                    _ = precheck_argv
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
                    exec_tool_call_count += 1
                    used_tool_labels.append(_build_tool_trace_label(name))
                    last_exec_command = cmd
                    last_exec_stdout = stdout
                    last_exec_stderr = stderr
                    if not ok:
                        last_exec_error = (stderr or stdout or "").strip() or "Command not allowed or failed."
                    else:
                        last_exec_error = ""
                    logger.info("Exec result: ok=%s stdout_len=%s stderr_len=%s", ok, len(stdout), len(stderr))
                    if ok or stdout or stderr:
                        out = f"stdout:\n{stdout}\n" + (f"stderr:\n{stderr}\n" if stderr else "")
                    else:
                        out = f"error: {stderr or 'Command not allowed or failed.'}"
            elif name == "process":
                from app.process_tool import parse_process_tool_args, run_process_tool

                params = parse_process_tool_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("process", str(params.get("action") or "")))
                out = await run_process_tool(params)
                _record_tool_outcome(
                    tool_name="process",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
            elif name == "list_directory":
                from app.files_tool import list_directory as list_dir, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await list_dir(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("list_directory"))
            elif name == "read_file":
                from app.files_tool import read_file_content as read_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                _rf_offset = int(params["offset"]) if isinstance(params.get("offset"), int) and params["offset"] > 0 else 0
                out = await read_file_fn(
                    path, user_id, db,
                    offset=_rf_offset,
                    model=user_model,
                    provider=provider_name,
                )
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("read_file"))
            elif name == "write_file":
                from app.files_tool import write_file as write_file_fn, parse_files_tool_args as parse_files_args

                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                if _is_note_capture_request(text):
                    path = _canonicalize_note_write_path(path)
                    params["path"] = path
                content = params.get("content")
                out = await write_file_fn(path, content if isinstance(content, str) else "", user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("write_file"))
            elif name == "allow_path":
                from app.files_tool import allow_path as allow_path_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await allow_path_fn(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("allow_path"))
            elif name == "delete_file":
                from app.files_tool import delete_file as delete_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_file_fn(path, user_id, db, permanently=permanently)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("delete_file"))
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
            elif name in ("read", "write", "edit"):
                from app.coding_compat_tool import (
                    parse_coding_compat_args,
                    run_read_compat,
                    run_write_compat,
                    run_edit_compat,
                )

                params = parse_coding_compat_args(args_str)
                if name == "read":
                    out = await run_read_compat(params, user_id, db, model=user_model, provider=provider_name)
                elif name == "write":
                    if _is_note_capture_request(text):
                        note_path = _canonicalize_note_write_path(str(params.get("path") or ""))
                        params["path"] = note_path
                    out = await run_write_compat(params, user_id, db)
                else:
                    out = await run_edit_compat(params, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label(name))
            elif name == "web_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("web_search"))
                out = await run_web_search_compat(params)
            elif name == "web_fetch":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_fetch_compat

                params = parse_openclaw_compat_args(args_str)
                # Inject model/provider so web_fetch can compute adaptive page cap.
                params["_model"] = user_model
                params["_provider"] = provider_name
                used_tool_labels.append(_build_tool_trace_label("web_fetch"))
                out = await run_web_fetch_compat(params)
            elif name == "memory_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_search"))
                out = await run_memory_search_compat(params, user_id=user_id)
            elif name == "memory_get":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_get_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_get"))
                out = await run_memory_get_compat(params, model=user_model, provider=provider_name)
                _record_tool_outcome(tool_name="memory_get", tool_output=out, tool_args=params)
            elif name == "apply_patch":
                from app.apply_patch_compat_tool import parse_apply_patch_compat_args, run_apply_patch_compat

                params = parse_apply_patch_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("apply_patch"))
                out = await run_apply_patch_compat(params)
                ran_files_tool = True
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
                _record_tool_outcome(
                    tool_name="reminders",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
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
                _record_tool_outcome(
                    tool_name="cron",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
            elif name in (
                "agents_list",
                "sessions_spawn",
                "sessions_list",
                "sessions_history",
                "sessions_send",
                "sessions_stop",
            ):
                from app.subagent_orchestrator import parse_subagent_tool_args, run_subagent_tool

                params = parse_subagent_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label(name)
                )
                out = await run_subagent_tool(
                    tool_name=name,
                    params=params,
                    user_id=user_id,
                    parent_conversation_id=cid,
                    provider_name=provider_name,
                    channel=channel,
                    channel_target=channel_target,
                )
            elif name == "spotify":
                from app.spotify_tool import parse_spotify_tool_args, run_spotify_tool
                params = parse_spotify_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("spotify", str(params.get("action") or ""))
                )
                out = await run_spotify_tool(params, user_id=user_id)
            elif name == "image_gen":
                from app.image_gen_tool import run_image_gen
                prompt = (args_data.get("prompt") or "").strip() if isinstance(args_data, dict) else ""
                used_tool_labels.append(_build_tool_trace_label("image_gen"))
                out = await run_image_gen(user_id=user_id, prompt=prompt)
                ran_image_gen_tool = True
            else:
                out = "Unknown tool."

            if out is not None:
                # Record if not already handled specifically in branches (like process/reminders/cron)
                # Note: most tools were refactored to use this common block.
                recorded_tools = (
                    "process", "reminders", "cron", "agents_list", "sessions_spawn",
                    "sessions_list", "sessions_history", "sessions_send", "sessions_stop"
                )
                if name not in recorded_tools:
                    _record_tool_outcome(tool_name=name or "unknown", tool_output=out, tool_args=args_data)

                # Truncate tool output to prevent context overflow / provider failure.
                # OpenClaw-style adaptive paging:
                #   - exec/bash: tail truncation (keep last N chars of stdout)
                #   - read/coding tools: already paged at source with offset hint; safety cap here
                #   - pageable non-read tools (memory_get): already paged at source; safety cap only
                #   - non-pageable tools (web_fetch, list_dir, memory_search): hard cap, no offset hint
                if name in ("exec", "bash"):
                    if len(out) > OUTPUT_EVENT_TAIL_CHARS:
                        logger.info("Truncating exec output from %d to last %d chars", len(out), OUTPUT_EVENT_TAIL_CHARS)
                        out = truncate_output_tail(out, OUTPUT_EVENT_TAIL_CHARS)
                else:
                    from app.adaptive_paging import compute_page_chars, truncate_with_offset_hint
                    _tool_page_chars = compute_page_chars(user_model, provider_name)
                    if len(out) > _tool_page_chars:
                        logger.info(
                            "Truncating tool %s output from %d to %d chars (adaptive, model=%s)",
                            name, len(out), _tool_page_chars, user_model or "unknown",
                        )
                        # Tools that support offset-based pagination get a continuation hint.
                        # Non-pageable tools get a plain truncation notice (no offset hint).
                        # Tools that do their own offset-based pagination at the source.
                        # These already append a continuation hint, so we add one here too
                        # (for the rare case where the safety net fires on top of their output).
                        _offset_pageable = name in (
                            "read", "read_file", "read_workspace_file",
                            "memory_get",  # already paged at source with from= hint
                        )
                        if _offset_pageable:
                            out = truncate_with_offset_hint(out, max_chars=_tool_page_chars, offset=0)
                        else:
                            out = out[:_tool_page_chars] + (
                                f"\n\n[Output truncated to {_tool_page_chars} chars."
                                " Use a more specific query or request a smaller range.]"
                            )

                if name:
                    await _emit_tool_event(
                        phase="end",
                        name=name,
                        label=_build_tool_trace_label(name),
                        channel=channel,
                        channel_target=channel_target,
                        stream_event_callback=stream_event_callback,
                    )
                current_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": out})

        # If the model has made 6+ exec calls in a row, nudge it hard to write a script
        SCRIPT_NUDGE_THRESHOLD = 6
        if exec_tool_call_count == SCRIPT_NUDGE_THRESHOLD:
            current_messages.append({
                "role": "user",
                "content": (
                    f"[SYSTEM NOTICE] You have made {exec_tool_call_count} exec calls. "
                    "Stop making individual exec calls now. "
                    "Write a single bash script to workspace/scripts/tmp/ that does ALL remaining steps, "
                    "then run it in one exec call. Use python3 -c to parse JSON and chain IDs. "
                    "Do it now without explaining — just write_file then exec."
                ),
            })
            logger.info("Script nudge injected after %d exec calls", exec_tool_call_count)

        # Re-call same provider with updated messages (no fallback switch); use that provider's model
        tool_kwargs = {**chat_kwargs}
        if provider_used.name == provider.name:
            tool_kwargs["model"] = user_model or None
        else:
            tool_kwargs["model"] = fallback_models.get(provider_used.name)
        # Give the model more time when it has to summarize large tool output (e.g. memo notes)
        if provider_used.name == "openrouter":
            tool_kwargs["timeout"] = 90
        elif provider_used.name == "claude":
            tool_kwargs["timeout"] = 120
        if live_model_stream_enabled and hasattr(provider_used, "chat_stream"):
            if live_stream_machine:
                await live_stream_machine.on_event(
                    {"type": "message_start", "provider": provider_used.name}
                )
            response = await provider_used.chat_stream(
                current_messages,
                on_text_delta=_on_model_text_delta,
                **tool_kwargs,
            )
            if live_stream_machine:
                await live_stream_machine.on_event(
                    {
                        "type": "text_end",
                        "provider": provider_used.name,
                        "content": response.content or "",
                    }
                )
                await live_stream_machine.on_event(
                    {
                        "type": "message_end",
                        "provider": provider_used.name,
                        "content": response.content or "",
                    }
                )
                live_stream_reasoning_emitted = live_stream_machine.reasoning_emitted
        else:
            response = await provider_used.chat(current_messages, **tool_kwargs)
        if response.error:
            break

    # Detect if the tool loop was exhausted (hit MAX_TOOL_ROUNDS) while the model
    # still had pending tool calls — i.e. the task needed more steps than allowed.
    # In this case, tell the user clearly instead of silently dropping the work.
    _tool_rounds_exhausted = ran_any_tool and bool(response.tool_calls)

    raw_reply = (response.content or "").strip()

    if _tool_rounds_exhausted and not response.error:
        exhausted_note = (
            f"\n\n_(I hit my action limit ({MAX_TOOL_ROUNDS} steps) mid-task and couldn't finish. "
            "For large bulk tasks like this, ask me to write a single script that does everything "
            "in one go — I can handle hundreds of operations in one step that way.)_"
        )
        raw_reply = (raw_reply + exhausted_note).strip()
        logger.info("Tool rounds exhausted (%d/%d) — appending user-facing note", MAX_TOOL_ROUNDS, MAX_TOOL_ROUNDS)

    # If the model ran a tool but returned empty content (or content that is *only*
    # tool-call markup, which will be empty after stripping), nudge it to synthesize.
    # This handles Trinity/Qwen models that output <tool_call> XML as their entire
    # response text alongside structured tool_calls — after stripping the XML the
    # effective content is empty, so we need the same synthesis nudge.
    _raw_reply_is_only_markup = (
        bool(raw_reply)
        and _has_tool_call_markup(raw_reply)
        and not _strip_tool_call_markup(raw_reply).strip()
    )
    if (not raw_reply or _raw_reply_is_only_markup) and ran_any_tool and last_tool_output and not response.error and provider_used:
        logger.info("Model returned empty after tool use — injecting synthesis nudge (provider=%s)", provider_used.name)
        # For Anthropic/Claude: do NOT append an extra user message — tool_result messages are
        # already wrapped as user messages in _to_anthropic_messages(), so adding another user
        # message creates consecutive user messages which is invalid and causes a 400 error.
        # Anthropic will naturally synthesize when re-called with tool_results present and no tools.
        # For other providers: append an explicit synthesis request.
        if provider_used.name != "claude":
            current_messages.append({
                "role": "user",
                "content": (
                    "The tool ran successfully. Now write your reply to the user based on the results above. "
                    "Be direct and concrete — do not call any more tools, just respond."
                ),
            })
        try:
            nudge_kwargs = {**chat_kwargs}
            nudge_kwargs.pop("tools", None)  # no more tool calls, just synthesize
            nudge_kwargs.pop("tool_choice", None)
            if provider_used.name == "openrouter":
                nudge_kwargs["timeout"] = 60
            nudge_resp = await provider_used.chat(current_messages, **nudge_kwargs)
            if nudge_resp.content and not nudge_resp.error:
                response = nudge_resp
                raw_reply = nudge_resp.content.strip()
                logger.info("Synthesis nudge succeeded (content_len=%d)", len(raw_reply))
        except Exception as _nudge_err:
            logger.warning("Synthesis nudge failed: %s", _nudge_err)

    had_tool_markup = _has_tool_call_markup(raw_reply)
    reply = _strip_tool_call_markup(raw_reply)
    reply = _strip_bracket_tool_protocol(reply)
    # Only show this error when NO tool was actually executed — if tools ran
    # successfully and the model just returned markup with no surrounding text,
    # the synthesis nudge above already handled producing a real reply.
    if not reply and had_tool_markup and not response.error and not ran_any_tool:
        reply = "I couldn't execute that tool call format. Ask again and I'll retry with tools."
    reply, suppress_user_reply = _sanitize_silent_reply_markers(reply)

    # If there was a fatal error (Auth/RateLimit) and no content, show the error message to the user
    if not reply and response.error:
        reply = f"Error: {response.error_message or 'Unknown provider error'}"

    # OpenClaw-style preference: scheduler actions should be executed via tools.
    # If a tool-capable model skipped reminders/cron tool calls, apply deterministic fallback
    # from tool logic so we don't hallucinate list/remove outcomes.
    scheduler_fallback_used = False
    has_explicit_scheduler_protocol = bool(
        re.search(r"(?is)\[\s*cron\s*:", raw_reply or "")
        or re.search(r"(?is)\[ASTA_CRON_(?:ADD|REMOVE):", raw_reply or "")
        or re.search(r"(?im)^\s*CRON\s+ACTION\s*=\s*(?:add|remove)\b", raw_reply or "")
    )
    if (
        _provider_supports_tools(provider_name)
        and not ran_reminders_tool
        and not ran_cron_tool
        and not has_explicit_scheduler_protocol
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
            scheduler_fallback_used = True

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

    # Generic "notes" requests should use workspace markdown notes, not Apple Notes exec.
    # Apply deterministic fallback so model misrouting (e.g. memo commands) can't hallucinate.
    if (
        _provider_supports_tools(provider_name)
        and "files" in enabled
        and _is_workspace_notes_list_request(text)
    ):
        notes_fallback = await _handle_workspace_notes_list_fallback(text=text)
        if notes_fallback:
            fallback_reply, fallback_label = notes_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)

    # Image generation guardrail: some fallback models occasionally reply with
    # "I don't have access to image tools" even when image_gen is available.
    # If image intent is clear and no image tool call ran, execute deterministic fallback.
    if (
        _provider_supports_tools(provider_name)
        and not ran_image_gen_tool
        and (_looks_like_image_generation_request(text) or _reply_claims_image_tool_unavailable(reply))
    ):
        from app.image_gen_tool import run_image_gen

        image_prompt = (text or "").strip()
        image_tool_output = await run_image_gen(user_id=user_id, prompt=image_prompt)
        _record_tool_outcome(
            tool_name="image_gen",
            tool_output=image_tool_output,
            tool_args={"prompt": image_prompt},
            action="fallback",
        )
        image_markdown, image_error = _extract_image_markdown_from_tool_output(image_tool_output)
        if image_markdown:
            reply = image_markdown
            used_tool_labels.append(_build_tool_trace_label("image_gen", "fallback"))
        elif image_error:
            reply = image_error
            used_tool_labels.append(_build_tool_trace_label("image_gen", "fallback"))

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
    effective_reply_provider = provider_used.name if provider_used else provider_name
    strict_final_for_reply = (
        strict_final_mode_requested
        and _provider_supports_strict_final(effective_reply_provider)
    )
    final_text, extracted_reasoning = _extract_reasoning_blocks(
        reply,
        strict_final=strict_final_for_reply,
    )
    reasoning_mode_norm = (reasoning_mode or "").strip().lower()
    if reasoning_mode_norm == "off":
        # Never leak raw <think> blocks to user output.
        reply = final_text
    elif extracted_reasoning:
        if reasoning_mode_norm == "stream":
            if not live_stream_reasoning_emitted:
                if stream_events_enabled:
                    formatted_reasoning = _format_reasoning_message(extracted_reasoning)
                    if formatted_reasoning:
                        await _emit_live_reasoning_text(formatted_reasoning, formatted_reasoning)
                        live_stream_reasoning_emitted = True
                else:
                    await _emit_reasoning_stream_progressively(
                        db=db,
                        conversation_id=cid,
                        channel=channel,
                        channel_target=channel_target,
                        reasoning=extracted_reasoning,
                    )
            # Stream mode emits reasoning as status; final user reply should stay clean.
            reply = final_text
        elif stream_events_enabled:
            # Streaming web with reasoning "on": emit reasoning as a separate SSE
            # event so the client can display it in the thinking block, and keep
            # the reply text clean (no "Reasoning:\n..." prefix).
            formatted_reasoning = _format_reasoning_message(extracted_reasoning)
            if formatted_reasoning and not live_stream_reasoning_emitted:
                await _emit_live_reasoning_text(formatted_reasoning, formatted_reasoning)
                live_stream_reasoning_emitted = True
            reply = final_text
        else:
            # Non-streaming channels (telegram, etc.): embed reasoning in reply text
            formatted_reasoning = _format_reasoning_message(extracted_reasoning)
            if formatted_reasoning:
                reply = f"{formatted_reasoning}\n\n{final_text}".strip()
            else:
                reply = final_text
    else:
        reply = final_text

    # OpenClaw-style fallback when we ran exec but model returned no user-facing reply:
    # surface the last concrete exec failure first, then raw output excerpt.
    if not reply and ran_exec_tool:
        max_show = 2000
        if last_exec_error:
            safe_cmd = (last_exec_command or "").replace("`", "'")
            if len(safe_cmd) > 140:
                safe_cmd = safe_cmd[:140] + "…"
            excerpt = last_exec_error[:max_show] + ("…" if len(last_exec_error) > max_show else "")
            if safe_cmd:
                reply = f"Exec failed for `{safe_cmd}`: {excerpt}"
            else:
                reply = f"Exec failed: {excerpt}"
        else:
            combined = "\n".join(
                part for part in ((last_exec_stdout or "").strip(), (last_exec_stderr or "").strip()) if part
            ).strip()
            if combined:
                reply = "I ran the command and got output, but the model didn't return a reply. **Command output:**\n\n```\n"
                excerpt = combined[:max_show] + ("…" if len(combined) > max_show else "")
                reply += excerpt + "\n```"
            else:
                reply = "I ran the command but didn't get a reply back. Try again or rephrase."

    # OpenClaw-style fallback for non-exec tools: surface concrete tool failure first.
    if not reply and last_tool_error:
        should_show_tool_error = last_tool_error_mutating or (not _is_recoverable_tool_error(last_tool_error))
        if should_show_tool_error:
            max_show = 2000
            excerpt = last_tool_error[:max_show] + ("…" if len(last_tool_error) > max_show else "")
            label = last_tool_error_label or "Tool"
            reply = f"Warning: {label} failed: {excerpt}"

    # If a tool ran successfully but the model produced no final text, do NOT dump raw tool output
    # to the user (it looks broken/leaky). Log it server-side and return a clean retry message.
    if not reply and ran_any_tool and last_tool_output:
        label = last_tool_label or "a tool"
        try:
            logger.warning(
                "Tool ran but model returned empty reply (label=%s, tool_output_len=%d)",
                label,
                len(last_tool_output or ""),
            )
        except Exception:
            pass
        # Show at least a preview of the tool output to be helpful
        output_preview = _redact_local_paths((last_tool_output or "")[:500])
        if len(last_tool_output or "") > 500:
            output_preview += "..."
        reply = (
            f"I used {label} and got output, but couldn't generate a response. "
            f"Output preview: {output_preview}\n\n"
            "Try rephrasing your request."
        )

    
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
            from app.exec_tool import (
                get_effective_exec_bins,
                prepare_allowlisted_command,
                run_allowlisted_command,
            )
            effective_bins = await get_effective_exec_bins(db, user_id)
            for m in exec_matches:
                cmd = m.group(1).strip()
                precheck_argv, precheck_err = prepare_allowlisted_command(
                    cmd,
                    allowed_bins=effective_bins,
                )
                _ = precheck_argv
                if (
                    precheck_err
                    and exec_mode == "allowlist"
                    and "not in allowlist" in precheck_err.lower()
                ):
                    from app.exec_approvals import create_pending_exec_approval

                    approval_id, requested_bin = await create_pending_exec_approval(
                        db=db,
                        user_id=user_id,
                        channel=channel,
                        channel_target=channel_target,
                        command=cmd,
                    )
                    exec_outputs.append(
                        f"Command: {cmd}\n"
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny.\n"
                        f"Approval id: {approval_id}\n"
                        f"Binary: {requested_bin or 'unknown'}"
                    )
                    continue
                stdout, stderr, ok = await run_allowlisted_command(cmd, allowed_bins=effective_bins)
                if ok or stdout or stderr:
                    exec_outputs.append(f"Command: {cmd}\nOutput:\n{stdout}\n" + (f"Stderr:\n{stderr}\n" if stderr else ""))
                else:
                    exec_outputs.append(f"Command: {cmd}\nError: {stderr or 'Command not allowed or failed.'}")
            if exec_outputs:
                exec_message = "[Command output from Asta]\n\n" + "\n---\n\n".join(exec_outputs)
                exec_message += "\n\nReply to the user based on this output. Do not use [ASTA_EXEC] in your reply."
                from app.exec_tool import truncate_output_tail, OUTPUT_EVENT_TAIL_CHARS
                exec_message = truncate_output_tail(exec_message, OUTPUT_EVENT_TAIL_CHARS)
                messages_plus = list(messages) + [{"role": "assistant", "content": reply}] + [{"role": "user", "content": exec_message}]
                response2, _ = await chat_with_fallback(
                    provider, messages_plus, fallback_names,
                    context=context, model=user_model or None,
                    _fallback_models=fallback_models,
                    _runtime_db=db,
                    _runtime_user_id=user_id,
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
        if _is_note_capture_request(text):
            file_path = _canonicalize_note_write_path(file_path)
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
    textual_cron, reply = _extract_textual_cron_add_protocol(reply)
    if textual_cron:
        try:
            from app.cron_runner import add_cron_job_to_scheduler
            from app.tasks.scheduler import get_scheduler

            job_id = await db.add_cron_job(
                user_id,
                textual_cron["name"],
                textual_cron["cron_expr"],
                textual_cron["message"],
                tz=textual_cron.get("tz") or None,
                channel=channel,
                channel_target=channel_target,
            )
            add_cron_job_to_scheduler(
                get_scheduler(),
                job_id,
                textual_cron["cron_expr"],
                textual_cron.get("tz") or None,
            )
            used_tool_labels.append(_build_tool_trace_label("cron", "add/fallback"))
            if reply:
                reply = reply + "\n\n"
            reply += f"I've scheduled cron job \"{textual_cron['name']}\" ({textual_cron['cron_expr']})."
        except Exception as e:
            if reply:
                reply = reply + "\n\n"
            reply += f"I couldn't schedule the cron job: {e}."

    bracket_cron_adds, reply = _extract_bracket_cron_add_protocols(reply)
    if bracket_cron_adds:
        from app.cron_runner import add_cron_job_to_scheduler
        from app.tasks.scheduler import get_scheduler

        confirmations: list[str] = []
        for item in bracket_cron_adds:
            try:
                job_id = await db.add_cron_job(
                    user_id,
                    item["name"],
                    item["cron_expr"],
                    item["message"],
                    tz=item.get("tz") or None,
                    channel=channel,
                    channel_target=channel_target,
                )
                add_cron_job_to_scheduler(
                    get_scheduler(),
                    job_id,
                    item["cron_expr"],
                    item.get("tz") or None,
                )
                confirmations.append(f"I've scheduled cron job \"{item['name']}\" ({item['cron_expr']}).")
                used_tool_labels.append(_build_tool_trace_label("cron", "add/fallback"))
            except Exception as e:
                confirmations.append(f"I couldn't schedule cron job \"{item['name']}\": {e}.")
        if confirmations:
            if reply:
                reply = reply + "\n\n"
            reply += "\n".join(confirmations)

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
        and not ran_reminders_tool
        and not scheduler_fallback_used
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

    # Avoid leaking internal shell snippets when user didn't ask for commands.
    if not _looks_like_command_request(text):
        stripped_reply, removed_shell = _strip_shell_command_leakage(reply)
        if removed_shell:
            reply = stripped_reply

    reply, removed_secrets = await _redact_sensitive_reply_content(reply, db)
    if removed_secrets:
        logger.warning("Redacted sensitive data from assistant reply before returning to user")

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

    if stream_events_enabled and reply.strip():
        final_visible_reply = reply.strip()
        prior_live_reply = live_stream_machine.assistant_text if live_stream_machine else ""
        if final_visible_reply != prior_live_reply:
            final_delta = _compute_incremental_delta(prior_live_reply, final_visible_reply)
            # Safety: if delta equals the full reply and prior content is non-empty,
            # the strings share no prefix — appending the full delta would duplicate content.
            # Skip the emit; the saved reply is the source of truth.
            skip_delta = prior_live_reply and final_delta == final_visible_reply
            if not skip_delta:
                await _emit_live_stream_event(
                    stream_event_callback,
                    {
                        "type": "assistant",
                        "text": final_visible_reply,
                        "delta": final_delta,
                    },
                )

    # Silent control-path: no assistant message emitted/persisted.
    if suppress_user_reply and not reply.strip():
        if _out is not None:
            _out["provider"] = effective_reply_provider
        return ""

    # Always persist assistant reply (including errors) so history matches what users saw in-chat.
    await db.add_message(cid, "assistant", reply, provider.name if not reply.strip().startswith("Error:") and not reply.strip().startswith("No AI provider") else None)

    # Auto-title: fire background task on first exchange only (no title stored yet)
    if reply.strip() and not reply.strip().startswith("Error:"):
        existing_title = await db.get_conversation_title(cid)
        if not existing_title:
            asyncio.create_task(
                _generate_conversation_title(cid, text, reply, effective_reply_provider),
                name=f"auto-title:{cid}",
            )

    if _out is not None:
        _out["provider"] = effective_reply_provider
    return reply
