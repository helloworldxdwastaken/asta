"""Cross-provider model fallback: try primary AI, then fallbacks.
Inspired by OpenClaw's model-fallback.ts — adapted for Asta's Python stack.
"""
from __future__ import annotations
import logging
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError

logger = logging.getLogger(__name__)


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
) -> tuple[ProviderResponse, BaseProvider | None]:
    """Try the primary provider, then each fallback. Returns (response, provider_used).
    provider_used is the provider that produced the response (for tool-call follow-up); None on failure."""
    from app.providers.registry import get_provider

    # Try primary
    try:
        response = await primary.chat(messages, **kwargs)
    except Exception as e:
        logger.error(f"Primary provider {primary.name} exception: {e}")
        response = ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=str(e)
        )

    if not response.error:
        return (response, primary)

    if response.error == ProviderError.AUTH:
        return (response, None)
    if not fallback_names:
        return (response, None)

    logger.warning(
        "Primary provider %s failed (%s: %s), trying %d fallback(s)",
        primary.name, response.error.value, response.error_message, len(fallback_names),
    )

    last_response = response
    for i, fb_name in enumerate(fallback_names):
        fb_provider = get_provider(fb_name)
        if not fb_provider:
            logger.warning("Fallback provider '%s' not found, skipping", fb_name)
            continue
        fb_model = kwargs.get("_fallback_models", {}).get(fb_name)
        fb_kwargs = {**kwargs}
        if fb_model:
            fb_kwargs["model"] = fb_model
        else:
            fb_kwargs.pop("model", None)
        try:
            fb_response = await fb_provider.chat(messages, **fb_kwargs)
        except Exception as e:
            fb_response = ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"{fb_name} exception: {str(e)}"
            )
        if not fb_response.error:
            logger.info("Fallback %s succeeded (attempt %d/%d)", fb_name, i + 1, len(fallback_names))
            return (fb_response, fb_provider)
        if fb_response.error == ProviderError.AUTH:
            logger.warning("Fallback %s: auth error, skipping to next", fb_name)
            last_response = fb_response
            continue
        logger.warning("Fallback %s failed (%s), trying next", fb_name, fb_response.error.value)
        last_response = fb_response

    logger.error("All providers exhausted. Last error: %s", last_response.error_message)
    return (last_response, None)
