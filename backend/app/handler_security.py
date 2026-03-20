import re
import logging

logger = logging.getLogger(__name__)

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
