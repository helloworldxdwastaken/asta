"""Provider model policy helpers.

OpenRouter tool mode is intentionally restricted to Kimi/Trinity model families.
This keeps tool-calling behavior deterministic and avoids weak tool support.
"""

from __future__ import annotations

# Default chain used when no model is specified by the user.
OPENROUTER_DEFAULT_MODEL_CHAIN = "arcee-ai/trinity-large-preview:free"

OPENROUTER_RECOMMENDED_MODELS: tuple[str, ...] = (
    "moonshotai/kimi-k2.5",
    "moonshotai/kimi-k2-thinking",
    "arcee-ai/trinity-large-preview:free",
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


def _canonical_openrouter_model(model: str) -> str:
    canonical = (model or "").strip()
    if canonical.lower().startswith("openrouter/"):
        canonical = canonical.split("/", 1)[1].strip()
    return canonical


def classify_openrouter_model_csv(raw: str | None) -> tuple[list[str], list[str]]:
    """Return (allowed, rejected) model lists for OpenRouter tool mode."""
    values = split_model_csv(raw)
    allowed: list[str] = []
    rejected: list[str] = []
    for model in values:
        canonical = _canonical_openrouter_model(model)
        if not canonical:
            continue
        if is_openrouter_tool_model(canonical):
            allowed.append(canonical)
        else:
            rejected.append(canonical)
    return _dedupe_preserve_order(allowed), _dedupe_preserve_order(rejected)


def is_openrouter_tool_model(model: str) -> bool:
    """True only for OpenRouter model IDs from Kimi/Trinity families."""
    canonical = _canonical_openrouter_model(model).lower()
    if not canonical:
        return False
    return (
        canonical.startswith("moonshotai/kimi")
        or canonical.startswith("arcee-ai/trinity")
        or canonical.startswith("kimi")
        or canonical.startswith("trinity")
        or "/kimi" in canonical
        or "/trinity" in canonical
    )


def coerce_openrouter_model_csv(raw: str | None) -> tuple[str, list[str]]:
    allowed, rejected = classify_openrouter_model_csv(raw)
    if not allowed:
        allowed = split_model_csv(OPENROUTER_DEFAULT_MODEL_CHAIN)
    return ",".join(allowed), rejected
