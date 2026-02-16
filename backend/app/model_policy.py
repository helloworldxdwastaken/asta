"""Provider model policy helpers (OpenClaw-style capability guardrails)."""

from __future__ import annotations

OPENROUTER_ALLOWED_MODEL_PREFIXES: tuple[str, ...] = (
    "moonshotai/kimi-k2",
    "arcee-ai/trinity",
)

OPENROUTER_RECOMMENDED_MODELS: tuple[str, ...] = (
    "moonshotai/kimi-k2.5",
    "moonshotai/kimi-k2-thinking",
    "arcee-ai/trinity-large-preview:free",
)

OPENROUTER_DEFAULT_MODEL_CHAIN = "moonshotai/kimi-k2.5,arcee-ai/trinity-large-preview:free"


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


def is_openrouter_tool_model(model: str) -> bool:
    key = (model or "").strip().lower()
    if key.startswith("openrouter/"):
        key = key.split("/", 1)[1]
    if not key:
        return False
    return any(key.startswith(prefix) for prefix in OPENROUTER_ALLOWED_MODEL_PREFIXES)


def classify_openrouter_model_csv(raw: str | None) -> tuple[list[str], list[str]]:
    values = split_model_csv(raw)
    allowed: list[str] = []
    rejected: list[str] = []
    for model in values:
        canonical = model.strip()
        if canonical.lower().startswith("openrouter/"):
            canonical = canonical.split("/", 1)[1].strip()
        if is_openrouter_tool_model(canonical):
            allowed.append(canonical)
        else:
            rejected.append(model)
    return _dedupe_preserve_order(allowed), _dedupe_preserve_order(rejected)


def coerce_openrouter_model_csv(raw: str | None) -> tuple[str, list[str]]:
    allowed, rejected = classify_openrouter_model_csv(raw)
    if not allowed:
        allowed = split_model_csv(OPENROUTER_DEFAULT_MODEL_CHAIN)
    return ",".join(allowed), rejected
