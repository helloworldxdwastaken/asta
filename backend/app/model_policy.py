"""Provider model policy helpers.

Single-user Asta — OpenRouter supports ANY model the user selects.
We still keep a default chain for when no model is specified.
"""

from __future__ import annotations

# Default chain used when no model is specified by the user.
# Primary: Kimi K2.5 (strong tool use), fallback: Trinity (free tier).
OPENROUTER_DEFAULT_MODEL_CHAIN = "moonshotai/kimi-k2.5,arcee-ai/trinity-large-preview:free"

OPENROUTER_RECOMMENDED_MODELS: tuple[str, ...] = (
    "moonshotai/kimi-k2.5",
    "moonshotai/kimi-k2-thinking",
    "arcee-ai/trinity-large-preview:free",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4-5",
    "google/gemini-2.0-flash-001",
)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def split_model_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return _dedupe_preserve_order([chunk.strip() for chunk in str(raw).split(",") if chunk.strip()])


def classify_openrouter_model_csv(raw: str | None) -> tuple[list[str], list[str]]:
    """Return (allowed, rejected) model lists.

    All user-specified models are allowed. We only strip the 'openrouter/' prefix
    if present (since OpenRouter's own API doesn't want it in the model field).
    Nothing is rejected by policy — the user knows what they want.
    """
    values = split_model_csv(raw)
    allowed: list[str] = []
    for model in values:
        canonical = model.strip()
        # Strip redundant 'openrouter/' prefix if present
        if canonical.lower().startswith("openrouter/"):
            canonical = canonical.split("/", 1)[1].strip()
        if canonical:
            allowed.append(canonical)
    return _dedupe_preserve_order(allowed), []  # nothing rejected


def is_openrouter_tool_model(model: str) -> bool:
    """Legacy helper kept for compatibility — always returns True now."""
    return bool((model or "").strip())


def coerce_openrouter_model_csv(raw: str | None) -> tuple[str, list[str]]:
    allowed, rejected = classify_openrouter_model_csv(raw)
    if not allowed:
        allowed = split_model_csv(OPENROUTER_DEFAULT_MODEL_CHAIN)
    return ",".join(allowed), rejected
