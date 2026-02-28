"""Main AI provider flow policy (OpenClaw-style failover classification)."""

from __future__ import annotations

from app.providers.base import ProviderError

# Fixed provider chain for single-user Asta flow.
MAIN_PROVIDER_CHAIN: tuple[str, ...] = ("claude", "google", "openrouter", "ollama")
DEFAULT_MAIN_PROVIDER = MAIN_PROVIDER_CHAIN[0]

_BILLING_ERROR_HINTS: tuple[str, ...] = (
    "credit balance",
    "insufficient credit",
    "insufficient credits",
    "insufficient quota",
    "quota exceeded",
    "billing hard limit",
    "billing",
    "payment required",
    "out of credits",
    "plan",
)

_AUTH_ERROR_HINTS: tuple[str, ...] = (
    "api key invalid",
    "invalid api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "token expired",
    "key expired",
    "revoked",
)


def normalize_main_provider(provider_name: str | None) -> str:
    candidate = (provider_name or "").strip().lower()
    if candidate in MAIN_PROVIDER_CHAIN:
        return candidate
    return DEFAULT_MAIN_PROVIDER


def resolve_main_provider_order(primary_provider: str | None) -> list[str]:
    primary = normalize_main_provider(primary_provider)
    return [primary, *[p for p in MAIN_PROVIDER_CHAIN if p != primary]]


def _error_text(error_message: str | None) -> str:
    return (error_message or "").strip().lower()


def is_billing_or_quota_error(error_message: str | None) -> bool:
    text = _error_text(error_message)
    if not text:
        return False
    if "402" in text:
        return True
    return any(hint in text for hint in _BILLING_ERROR_HINTS)


def is_auth_error_text(error_message: str | None) -> bool:
    text = _error_text(error_message)
    if not text:
        return False
    if "401" in text or "403" in text:
        return True
    return any(hint in text for hint in _AUTH_ERROR_HINTS)


def classify_provider_disable_reason(
    *,
    provider_error: ProviderError | None,
    error_message: str | None,
) -> str | None:
    """Return disable reason when a provider should be auto-disabled."""
    if is_billing_or_quota_error(error_message):
        return "billing"
    if provider_error == ProviderError.AUTH and is_auth_error_text(error_message):
        return "auth"
    return None
