"""Cross-provider model fallback: try primary AI, then fallbacks.
Inspired by OpenClaw's model-fallback.ts — adapted for Asta's Python stack.
"""
from __future__ import annotations
import logging

from app.provider_flow import (
    classify_provider_disable_reason,
    resolve_main_provider_order,
)
from app.providers.base import (
    BaseProvider,
    Message,
    ProviderResponse,
    ProviderError,
    TextDeltaCallback,
    StreamEventCallback,
    emit_text_delta,
    emit_stream_event,
)

logger = logging.getLogger(__name__)


async def get_available_fallback_providers(
    db,
    user_id: str,
    exclude_provider: str,
) -> list[str]:
    """Return fixed-order fallback providers that are configured and active."""
    ordered = resolve_main_provider_order(exclude_provider)
    states = await db.get_provider_runtime_states(user_id, ordered)
    available: list[str] = []
    for provider_name in ordered:
        if provider_name == exclude_provider:
            continue
        state = states.get(provider_name) or {}
        if not bool(state.get("enabled", True)):
            continue
        if bool(state.get("auto_disabled", False)):
            continue
        if await _provider_has_key(db, provider_name):
            available.append(provider_name)
    return available


async def _provider_has_key(db, provider_name: str) -> bool:
    """Check if a provider has its API key configured."""
    key_map = {
        "claude": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "ollama": None,  # Local, no key needed
    }
    key_name = key_map.get(provider_name)
    if key_name is None and provider_name == "ollama":
        return provider_name == "ollama"  # Ollama is always "available" (but might not be running)
    if key_name is None:
        return False
    val = await db.get_stored_api_key(key_name)
    return bool(val and val.strip())


async def _runtime_provider_allowed(runtime_db, user_id: str, provider_name: str) -> tuple[bool, str]:
    if not runtime_db or not user_id:
        return True, ""
    try:
        states = await runtime_db.get_provider_runtime_states(user_id, [provider_name])
        state = states.get(provider_name) or {}
    except Exception as e:
        logger.debug("Runtime state check failed for %s: %s", provider_name, e)
        return True, ""
    enabled = bool(state.get("enabled", True))
    auto_disabled = bool(state.get("auto_disabled", False))
    reason = str(state.get("disabled_reason") or "").strip().lower()
    if not enabled:
        return False, "disabled"
    if auto_disabled:
        return False, reason or "auto-disabled"
    return True, ""


async def _runtime_mark_success(runtime_db, user_id: str, provider_name: str) -> None:
    if not runtime_db or not user_id:
        return
    try:
        await runtime_db.clear_provider_auto_disabled(user_id, provider_name)
    except Exception as e:
        logger.debug("Failed clearing auto-disable for provider %s: %s", provider_name, e)


async def _runtime_mark_failure(runtime_db, user_id: str, provider_name: str, response: ProviderResponse) -> None:
    if not runtime_db or not user_id or not response.error:
        return
    reason = classify_provider_disable_reason(
        provider_error=response.error,
        error_message=response.error_message,
    )
    if not reason:
        return
    try:
        await runtime_db.mark_provider_auto_disabled(user_id, provider_name, reason)
        logger.warning(
            "Auto-disabled provider %s due to %s failure: %s",
            provider_name,
            reason,
            str(response.error_message or "")[:220],
        )
    except Exception as e:
        logger.debug("Failed auto-disabling provider %s: %s", provider_name, e)


async def chat_with_fallback(
    primary: BaseProvider,
    messages: list[Message],
    fallback_names: list[str],
    **kwargs,
) -> tuple[ProviderResponse, BaseProvider | None]:
    """Try the primary provider, then each fallback. Returns (response, provider_used).
    provider_used is the provider that produced the response (for tool-call follow-up); None on failure."""
    from app.providers.registry import get_provider

    fallback_models = kwargs.pop("_fallback_models", {})
    runtime_db = kwargs.pop("_runtime_db", None)
    runtime_user_id = str(kwargs.pop("_runtime_user_id", "") or "").strip()

    primary_allowed, primary_reason = await _runtime_provider_allowed(runtime_db, runtime_user_id, primary.name)

    # Try primary
    if primary_allowed:
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
            await _runtime_mark_success(runtime_db, runtime_user_id, primary.name)
            return (response, primary)
        await _runtime_mark_failure(runtime_db, runtime_user_id, primary.name, response)
    else:
        response = ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=f"Provider '{primary.name}' is currently unavailable ({primary_reason}).",
        )
    if not fallback_names:
        return (response, None)

    logger.warning(
        "Primary provider %s failed (%s: %s), trying %d fallback(s)",
        primary.name, response.error.value if response.error else "unknown", response.error_message, len(fallback_names),
    )

    last_response = response
    for i, fb_name in enumerate(fallback_names):
        fb_allowed, fb_reason = await _runtime_provider_allowed(runtime_db, runtime_user_id, fb_name)
        if not fb_allowed:
            logger.info("Skipping fallback provider %s (%s)", fb_name, fb_reason or "disabled")
            continue
        fb_provider = get_provider(fb_name)
        if not fb_provider:
            logger.warning("Fallback provider '%s' not found, skipping", fb_name)
            continue
        fb_model = fallback_models.get(fb_name) if isinstance(fallback_models, dict) else None
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
            await _runtime_mark_success(runtime_db, runtime_user_id, fb_name)
            logger.info("Fallback %s succeeded (attempt %d/%d)", fb_name, i + 1, len(fallback_names))
            return (fb_response, fb_provider)
        await _runtime_mark_failure(runtime_db, runtime_user_id, fb_name, fb_response)
        logger.warning("Fallback %s failed (%s), trying next", fb_name, fb_response.error.value)
        last_response = fb_response

    logger.error("All providers exhausted. Last error: %s", last_response.error_message)
    return (last_response, None)


async def chat_with_fallback_stream(
    primary: BaseProvider,
    messages: list[Message],
    fallback_names: list[str],
    *,
    on_text_delta: TextDeltaCallback | None = None,
    on_stream_event: StreamEventCallback | None = None,
    **kwargs,
) -> tuple[ProviderResponse, BaseProvider | None]:
    """Streaming variant of chat_with_fallback.

    Attempts live streaming on providers that implement chat_stream, while preserving
    the same fallback/error behavior as chat_with_fallback.
    """
    from app.providers.registry import get_provider

    fallback_models = kwargs.pop("_fallback_models", {})
    runtime_db = kwargs.pop("_runtime_db", None)
    runtime_user_id = str(kwargs.pop("_runtime_user_id", "") or "").strip()

    async def _call_stream_capable(p, msgs, cb, stream_cb, **call_kwargs) -> ProviderResponse:
        await emit_stream_event(stream_cb, {"type": "message_start", "provider": p.name})
        saw_text = False

        async def _forward_delta(delta: str) -> None:
            nonlocal saw_text
            if not delta:
                return
            if not saw_text:
                saw_text = True
                await emit_stream_event(stream_cb, {"type": "text_start", "provider": p.name})
            await emit_stream_event(
                stream_cb,
                {"type": "text_delta", "provider": p.name, "delta": delta},
            )
            await emit_text_delta(cb, delta)

        if hasattr(p, "chat_stream"):
            out = await p.chat_stream(msgs, on_text_delta=_forward_delta, **call_kwargs)
        else:
            out = await p.chat(msgs, **call_kwargs)
            if out.content:
                await _forward_delta(out.content)

        if not out.error:
            if not saw_text and out.content:
                await emit_stream_event(stream_cb, {"type": "text_start", "provider": p.name})
                await emit_stream_event(
                    stream_cb,
                    {"type": "text_delta", "provider": p.name, "delta": out.content},
                )
                await emit_text_delta(cb, out.content)
                saw_text = True
            if saw_text:
                await emit_stream_event(
                    stream_cb,
                    {"type": "text_end", "provider": p.name, "content": out.content or ""},
                )
            await emit_stream_event(
                stream_cb,
                {"type": "message_end", "provider": p.name, "content": out.content or ""},
            )
        return out

    primary_allowed, primary_reason = await _runtime_provider_allowed(runtime_db, runtime_user_id, primary.name)
    if primary_allowed:
        try:
            response = await _call_stream_capable(
                primary,
                messages,
                on_text_delta,
                on_stream_event,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Primary provider {primary.name} stream exception: {e}")
            response = ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=str(e)
            )
        if not response.error:
            await _runtime_mark_success(runtime_db, runtime_user_id, primary.name)
            return (response, primary)
        await _runtime_mark_failure(runtime_db, runtime_user_id, primary.name, response)
    else:
        response = ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=f"Provider '{primary.name}' is currently unavailable ({primary_reason}).",
        )
    if not fallback_names:
        return (response, None)

    logger.warning(
        "Primary provider %s (stream) failed (%s: %s), trying %d fallback(s)",
        primary.name, response.error.value if response.error else "unknown", response.error_message, len(fallback_names),
    )

    last_response = response
    for i, fb_name in enumerate(fallback_names):
        fb_allowed, fb_reason = await _runtime_provider_allowed(runtime_db, runtime_user_id, fb_name)
        if not fb_allowed:
            logger.info("Skipping fallback provider %s (%s)", fb_name, fb_reason or "disabled")
            continue
        fb_provider = get_provider(fb_name)
        if not fb_provider:
            logger.warning("Fallback provider '%s' not found, skipping", fb_name)
            continue
        fb_model = fallback_models.get(fb_name) if isinstance(fallback_models, dict) else None
        fb_kwargs = {**kwargs}
        if fb_model:
            fb_kwargs["model"] = fb_model
        else:
            fb_kwargs.pop("model", None)
        try:
            fb_response = await _call_stream_capable(
                fb_provider,
                messages,
                on_text_delta,
                on_stream_event,
                **fb_kwargs,
            )
        except Exception as e:
            fb_response = ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"{fb_name} exception: {str(e)}"
            )
        if not fb_response.error:
            await _runtime_mark_success(runtime_db, runtime_user_id, fb_name)
            logger.info("Fallback %s (stream) succeeded (attempt %d/%d)", fb_name, i + 1, len(fallback_names))
            return (fb_response, fb_provider)
        await _runtime_mark_failure(runtime_db, runtime_user_id, fb_name, fb_response)
        logger.warning("Fallback %s failed (%s), trying next", fb_name, fb_response.error.value)
        last_response = fb_response

    logger.error("All providers exhausted (stream). Last error: %s", last_response.error_message)
    return (last_response, None)
