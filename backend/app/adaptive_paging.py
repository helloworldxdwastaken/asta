"""OpenClaw-style adaptive paging: cap tool output to 20% of model context window.

Reference: openclaw/src/agents/pi-tools.read.ts → resolveAdaptiveReadMaxBytes
"""
from __future__ import annotations

# Minimum page size: 50 KB (matches OpenClaw DEFAULT_READ_PAGE_MAX_BYTES)
DEFAULT_PAGE_CHARS = 50_000
# Hard ceiling: 512 KB
MAX_PAGE_CHARS = 512_000
# Share of context window dedicated to a single tool output
CONTEXT_SHARE = 0.20
# Conservative chars-per-token estimate (OpenClaw uses 4)
CHARS_PER_TOKEN = 4

# Known model context windows (tokens).
# Keyed on substrings that appear in the model name/id (matched in order, first wins).
_MODEL_CONTEXT_TOKENS: list[tuple[str, int]] = [
    # Groq / small Ollama — the primary problematic tier
    ("llama-3.1-8b",      8_192),
    ("llama-3.2-1b",      8_192),
    ("llama-3.2-3b",      8_192),
    ("llama3.2:1b",       8_192),
    ("llama3.2:3b",       8_192),
    ("gemma:2b",          8_192),
    ("gemma2:2b",         8_192),
    ("phi3:mini",         4_096),
    ("phi3.5:mini",       4_096),
    ("llama-3.1-70b",    32_768),
    ("llama-3.3-70b",    32_768),
    ("mixtral",          32_768),
    ("mistral-nemo",     32_768),
    # Mid-tier
    ("qwen2.5:7b",       32_768),
    ("qwen2.5:14b",      32_768),
    ("llama3.1:8b",      16_384),
    ("llama3.3:70b",     32_768),
    # High context
    ("gemma3",          128_000),
    ("llama3.1",         16_384),   # generic llama 3.1 fallback
    ("deepseek",        128_000),
    ("claude",          200_000),
    ("gemini-1.5",    1_000_000),
    ("gemini-2",      1_048_576),
    ("gpt-4o",          128_000),
    ("gpt-4-turbo",     128_000),
    ("gpt-4",             8_192),
    ("gpt-3.5",           4_096),
    ("o1",              200_000),
    ("o3",              200_000),
]

# Groq-specific model → context window overrides
_GROQ_CONTEXT: dict[str, int] = {
    "llama-3.1-8b-instant":       8_192,
    "llama-3.3-70b-versatile":   32_768,
    "llama-3.3-70b-specdec":     32_768,
    "llama-3.1-70b-versatile":   32_768,
    "mixtral-8x7b-32768":        32_768,
    "gemma2-9b-it":               8_192,
    "whisper-large-v3":            None,  # audio-only, not relevant
}


def _lookup_context_tokens(model: str | None, provider: str | None) -> int | None:
    """Return best-guess context window size in tokens for the given model."""
    if not model:
        return None
    m = model.strip().lower()

    # Groq-specific exact matches first
    if (provider or "").strip().lower() == "groq":
        for key, tokens in _GROQ_CONTEXT.items():
            if m == key.lower():
                return tokens

    # Substring match against known models
    for substring, tokens in _MODEL_CONTEXT_TOKENS:
        if substring.lower() in m:
            return tokens

    return None


def compute_page_chars(
    model: str | None = None,
    provider: str | None = None,
    context_tokens: int | None = None,
) -> int:
    """Return adaptive page size in chars for tool output.

    Priority: explicit context_tokens > model/provider lookup > DEFAULT_PAGE_CHARS.

    Math (mirrors OpenClaw):
        page_chars = clamp(context_tokens * CHARS_PER_TOKEN * CONTEXT_SHARE,
                           DEFAULT_PAGE_CHARS, MAX_PAGE_CHARS)
    """
    tokens = context_tokens
    if tokens is None or tokens <= 0:
        tokens = _lookup_context_tokens(model, provider)
    if tokens is None or tokens <= 0:
        return DEFAULT_PAGE_CHARS

    raw = int(tokens * CHARS_PER_TOKEN * CONTEXT_SHARE)
    return max(DEFAULT_PAGE_CHARS, min(raw, MAX_PAGE_CHARS))


def truncate_with_offset_hint(
    content: str,
    *,
    max_chars: int,
    offset: int = 0,
    unit: str = "chars",
) -> str:
    """Return content[:max_chars] with a continuation hint if truncated.

    Args:
        content:   Full text to page.
        max_chars: Maximum output characters for this page.
        offset:    Character offset where this page starts (used in hint).
        unit:      Label for the offset unit shown in the hint (default "chars").

    Returns:
        Possibly-truncated text, with a hint appended when truncation occurred.
    """
    if len(content) <= max_chars:
        return content
    next_offset = offset + max_chars
    return (
        content[:max_chars]
        + f"\n\n[Read output capped at {max_chars} {unit}."
        + f" Use offset={next_offset} to continue.]"
    )
