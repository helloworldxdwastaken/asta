"""Cross-provider model fallback: try primary AI, then fallbacks.
Inspired by OpenClaw's model-fallback.ts — adapted for Asta's Python stack.
"""
from __future__ import annotations
import logging
from enum import Enum
from app.providers.base import BaseProvider, Message

logger = logging.getLogger(__name__)


class ErrorKind(str, Enum):
    """Classify provider errors so we know whether to retry."""
    AUTH = "auth"                # API key invalid — don't retry with same provider
    RATE_LIMIT = "rate_limit"   # Rate limited — try another provider
    MODEL_NOT_FOUND = "model"   # Model doesn't exist — try another provider
    TIMEOUT = "timeout"         # Timed out — try another provider
    TRANSIENT = "transient"     # Unknown/transient error — try another provider
    NONE = "none"               # Not an error


def classify_error(reply: str) -> ErrorKind:
    """Classify an error reply string from a provider. Returns NONE if not an error."""
    if not reply:
        return ErrorKind.NONE
    s = reply.strip()
    if not s.startswith("Error:"):
        return ErrorKind.NONE
    low = s.lower()
    # Auth errors: won't be fixed by retrying with the same key
    if any(k in low for k in ("invalid or expired", "api key not set", "authentication", "401", "key invalid")):
        return ErrorKind.AUTH
    # Rate limit
    if any(k in low for k in ("rate limit", "429", "rate-limited")):
        return ErrorKind.RATE_LIMIT
    # Model not found / decommissioned
    if any(k in low for k in ("not found", "decommissioned", "404", "unknown model")):
        return ErrorKind.MODEL_NOT_FOUND
    # Timeout
    if "timed out" in low or "timeout" in low:
        return ErrorKind.TIMEOUT
    # Any other "Error:" is transient
    return ErrorKind.TRANSIENT


def is_error_reply(reply: str) -> bool:
    """True if the reply is an error message from a provider."""
    return classify_error(reply) != ErrorKind.NONE


async def get_available_fallback_providers(
    db,
    user_id: str,
    exclude_provider: str,
) -> list[str]:
    """Build a list of provider names that have API keys configured, excluding the primary.
    If user has set explicit fallback order, use that (filtered to available ones).
    Otherwise, auto-detect from configured keys.
    """
    # Check user's explicit fallback config
    fallback_csv = await db.get_user_fallback_providers(user_id)
    if fallback_csv:
        explicit = [p.strip() for p in fallback_csv.split(",") if p.strip()]
        # Filter to only providers that have keys set
        available = []
        for p in explicit:
            if p == exclude_provider:
                continue
            if await _provider_has_key(db, p):
                available.append(p)
        return available

    # Auto-detect: check which providers have API keys configured
    key_map = {
        "groq": "groq_api_key",
        "google": "gemini_api_key",
        "claude": "anthropic_api_key",
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
    }
    # Ollama doesn't need a key (local), check if reachable
    available = []
    for provider_name, key_name in key_map.items():
        if provider_name == exclude_provider:
            continue
        val = await db.get_stored_api_key(key_name)
        if val and val.strip():
            available.append(provider_name)
    # Also check google_ai_key as alternative for google
    if "google" not in available and "google" != exclude_provider:
        val = await db.get_stored_api_key("google_ai_key")
        if val and val.strip():
            available.append("google")
    return available


async def _provider_has_key(db, provider_name: str) -> bool:
    """Check if a provider has its API key configured."""
    key_map = {
        "groq": "groq_api_key",
        "google": "gemini_api_key",
        "claude": "anthropic_api_key",
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
        "ollama": None,  # Local, no key needed
    }
    key_name = key_map.get(provider_name)
    if key_name is None:
        return provider_name == "ollama"  # Ollama is always "available" (but might not be running)
    val = await db.get_stored_api_key(key_name)
    if val and val.strip():
        return True
    # Check alternative key names
    if provider_name == "google":
        val2 = await db.get_stored_api_key("google_ai_key")
        return bool(val2 and val2.strip())
    return False


async def chat_with_fallback(
    primary: BaseProvider,
    messages: list[Message],
    fallback_names: list[str],
    **kwargs,
) -> str:
    """Try the primary provider, then each fallback. Returns the first successful reply.

    Auth errors on the primary are NOT retried (the key is broken).
    Rate limits, timeouts, and transient errors trigger fallback.
    Auth errors on a fallback provider are skipped (try the next one).
    """
    from app.providers.registry import get_provider

    # Try primary
    try:
        reply = await primary.chat(messages, **kwargs)
    except Exception as e:
        reply = f"Error: {primary.name} — {str(e)[:200]}"

    error_kind = classify_error(reply)

    if error_kind == ErrorKind.NONE:
        return reply  # Success!

    if error_kind == ErrorKind.AUTH and not fallback_names:
        return reply  # Auth error and no fallbacks — nothing we can do

    # Auth errors: only skip fallback if there are none. Otherwise try fallbacks.
    logger.warning(
        "Primary provider %s failed (%s: %s), trying %d fallback(s)",
        primary.name, error_kind.value, reply[:80], len(fallback_names),
    )

    # Try each fallback
    last_error = reply
    for i, fb_name in enumerate(fallback_names):
        fb_provider = get_provider(fb_name)
        if not fb_provider:
            logger.warning("Fallback provider '%s' not found, skipping", fb_name)
            continue

        # Get the user's custom model for this fallback provider (if any)
        fb_model = kwargs.get("_fallback_models", {}).get(fb_name)
        fb_kwargs = {**kwargs}
        if fb_model:
            fb_kwargs["model"] = fb_model
        else:
            fb_kwargs.pop("model", None)  # Use provider default

        try:
            fb_reply = await fb_provider.chat(messages, **fb_kwargs)
        except Exception as e:
            fb_reply = f"Error: {fb_name} — {str(e)[:200]}"

        fb_error = classify_error(fb_reply)
        if fb_error == ErrorKind.NONE:
            logger.info("Fallback %s succeeded (attempt %d/%d)", fb_name, i + 1, len(fallback_names))
            return fb_reply
        if fb_error == ErrorKind.AUTH:
            logger.warning("Fallback %s: auth error, skipping to next", fb_name)
            last_error = fb_reply
            continue
        logger.warning("Fallback %s failed (%s), trying next", fb_name, fb_error.value)
        last_error = fb_reply

    # All exhausted
    logger.error("All providers exhausted. Last error: %s", last_error[:200])
    return last_error
