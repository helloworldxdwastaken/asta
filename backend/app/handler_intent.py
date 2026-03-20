"""Intent-detection helpers and associated constants extracted from handler.py."""

import json
import re
import logging
from pathlib import Path

from app.handler_thinking import _STRICT_FINAL_UNSUPPORTED_PROVIDERS

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
