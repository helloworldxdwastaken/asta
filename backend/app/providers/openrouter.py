"""OpenRouter provider — 300+ models with fallback support."""
import json
import logging
import re
from openai import AsyncOpenAI, APITimeoutError
from app.providers.base import (
    BaseProvider,
    Message,
    ProviderResponse,
    ProviderError,
    TextDeltaCallback,
    emit_text_delta,
    finalize_stream_tool_calls,
    merge_stream_tool_call_delta,
)
from app.keys import get_api_key
from app.model_policy import (
    OPENROUTER_DEFAULT_MODEL_CHAIN,
    classify_openrouter_model_csv,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"


def _normalize_tool_calls(raw: list | None) -> list[dict] | None:
    """Convert OpenRouter/OpenAI response tool_calls to our list[dict] format. Handles both object and dict items."""
    if not raw:
        return None
    out = []
    for tc in raw:
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            out.append({
                "id": tc.get("id", ""),
                "type": tc.get("type", "function"),
                "function": {
                    "name": fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", ""),
                    "arguments": (fn.get("arguments") or "{}") if isinstance(fn, dict) else (getattr(fn, "arguments", None) or "{}"),
                },
            })
        else:
            fn = getattr(tc, "function", None)
            out.append({
                "id": getattr(tc, "id", ""),
                "type": getattr(tc, "type", "function"),
                "function": {
                    "name": getattr(fn, "name", "") if fn else "",
                    "arguments": (getattr(fn, "arguments", None) or "{}") if fn else "{}",
                },
            })
    return out if out else None


def _extract_tool_call_from_text(text: str, allowed_names: set[str]) -> tuple[list[dict] | None, str]:
    """Fallback parser for models that return tool intent in text instead of structured tool_calls."""
    m = re.search(r"\[ASTA_TOOL_CALL\]\s*(\{.*?\})\s*\[/ASTA_TOOL_CALL\]", text, re.DOTALL)
    if not m:
        return None, text
    payload_raw = m.group(1).strip()
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return None, text
    if not isinstance(payload, dict):
        return None, text
    name = str(payload.get("name") or "").strip()
    if not name or (allowed_names and name not in allowed_names):
        return None, text
    args = payload.get("arguments")
    if not isinstance(args, dict):
        args = {}
    tool_calls = [
        {
            "id": "openrouter_tool_call",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        }
    ]
    cleaned = (text[: m.start()] + text[m.end() :]).strip()
    return tool_calls, cleaned
# Tool-stable default chain (Kimi primary, Trinity fallback).
DEFAULT_MODEL = OPENROUTER_DEFAULT_MODEL_CHAIN
# Timeout per model attempt (seconds). 60 helps when we send large tool output (e.g. memo notes) and wait for a summary.
MODEL_TIMEOUT = 60


def _reasoning_effort_from_level(level: str | None) -> str | None:
    lv = (level or "").strip().lower()
    if lv == "minimal":
        return "low"
    if lv == "xhigh":
        return "high"
    if lv in ("low", "medium", "high"):
        return lv
    return None


def _is_reasoning_param_unsupported_error(msg: str) -> bool:
    low = (msg or "").lower()
    return ("reasoning_effort" in low) or ("unknown parameter" in low) or ("unrecognized request argument" in low)


class OpenRouterProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "openrouter"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("openrouter_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="OpenRouter API key not set. Add it in Settings (API keys) or in backend/.env as OPENROUTER_API_KEY. Get a key at https://openrouter.ai/keys"
            )
        timeout = kwargs.get("timeout") or MODEL_TIMEOUT
        client = AsyncOpenAI(api_key=key, base_url=BASE_URL, timeout=timeout)
        system = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str | None = kwargs.get("image_mime", "image/jpeg")

        msgs = []
        tools = kwargs.get("tools")
        allowed_tool_names: set[str] = set()
        for t in (tools or []):
            fn = t.get("function") if isinstance(t, dict) else None
            if isinstance(fn, dict):
                n = (fn.get("name") or "").strip()
                if n:
                    allowed_tool_names.add(n)
        if system:
            # OpenRouter fallback protocol: if a specific model fails structured tool_calls,
            # it may still emit this tag; handler will parse it.
            if tools:
                system = (
                    system
                    + "\n\nTOOL-CALL PROTOCOL (fallback): If you need a tool and cannot emit native tool_calls, "
                    + "output exactly one tag:\n[ASTA_TOOL_CALL]{\"name\":\"tool_name\",\"arguments\":{...}}[/ASTA_TOOL_CALL]\n"
                    + f"Allowed tool names: {', '.join(sorted(allowed_tool_names))}."
                )
            msgs.append({"role": "system", "content": system})

        # Base64 encode if image present
        image_data_url = ""
        if image_bytes:
            import base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:{image_mime};base64,{b64}"

        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "user" and image_data_url and m == messages[-1]:
                msgs.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": content},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                })
            else:
                msg = {"role": role, "content": content}
                if "tool_calls" in m:
                    msg["tool_calls"] = m["tool_calls"]
                if "tool_call_id" in m:
                    msg["tool_call_id"] = m["tool_call_id"]
                msgs.append(msg)

        # Support comma-separated models: first is primary, rest are fallbacks.
        # Guardrail: keep OpenRouter model selection on Kimi/Trinity families for tool reliability.
        model_raw = str(kwargs.get("model") or DEFAULT_MODEL).strip()
        if image_bytes:
            # Force vision model if image present
            model_raw = "nvidia/nemotron-nano-12b-v2-vl:free"
        else:
            allowed_models, rejected_models = classify_openrouter_model_csv(model_raw)
            if rejected_models:
                logger.warning(
                    "OpenRouter model policy dropped unsupported model(s): %s",
                    ", ".join(rejected_models),
                )
            if not allowed_models:
                allowed_models, _ = classify_openrouter_model_csv(DEFAULT_MODEL)
            model_raw = ",".join(allowed_models)
            
        models = [m.strip() for m in model_raw.split(",") if m.strip()]
        if not models:
            models = [m.strip() for m in DEFAULT_MODEL.split(",") if m.strip()]

        last_error = ""
        for i, model in enumerate(models):
            try:
                create_kwargs = {"model": model, "messages": msgs, "max_tokens": 4096}
                if tools:
                    create_kwargs["tools"] = tools
                    create_kwargs["tool_choice"] = "auto"
                effort = _reasoning_effort_from_level(kwargs.get("thinking_level"))
                if effort:
                    create_kwargs["reasoning_effort"] = effort
                try:
                    r = await client.chat.completions.create(**create_kwargs)
                except Exception as first_err:
                    if effort and _is_reasoning_param_unsupported_error(str(first_err)):
                        create_kwargs.pop("reasoning_effort", None)
                        r = await client.chat.completions.create(**create_kwargs)
                    else:
                        raise
                msg = r.choices[0].message
                content = (msg.content or "").strip()
                raw_tc = getattr(msg, "tool_calls", None)
                tool_calls = _normalize_tool_calls(raw_tc)
                if tools and raw_tc is None and hasattr(r, "choices") and r.choices:
                    finish = getattr(r.choices[0], "finish_reason", None) or getattr(msg, "finish_reason", None)
                    logger.info("OpenRouter model=%s returned no tool_calls (finish_reason=%s, content_len=%s)", model, finish, len(content))
                    parsed_calls, cleaned = _extract_tool_call_from_text(content, allowed_tool_names)
                    if parsed_calls:
                        return ProviderResponse(content=cleaned, tool_calls=parsed_calls)
                return ProviderResponse(content=content, tool_calls=tool_calls)
            except APITimeoutError:
                err_msg = f"Model {model} timed out after {MODEL_TIMEOUT}s"
                last_error = err_msg
                if i < len(models) - 1:
                    logger.warning("%s, trying fallback %s", last_error, models[i + 1])
                else:
                    logger.error("All models exhausted. %s", last_error)
            except Exception as e:
                msg = str(e).strip() or repr(e)
                # Auth errors won't be fixed by a different model — return immediately
                if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                    return ProviderResponse(
                        content="",
                        error=ProviderError.AUTH,
                        error_message="OpenRouter API key invalid or expired. Check Settings → API keys."
                    )
                last_error = msg
                if i < len(models) - 1:
                    logger.warning("Model %s failed (%s), trying fallback %s", model, msg[:100], models[i + 1])
                else:
                    logger.error("All models exhausted. Last error from %s: %s", model, msg[:200])

        if "429" in last_error or "rate" in last_error.lower():
            return ProviderResponse(
                content="",
                error=ProviderError.RATE_LIMIT,
                error_message="All models rate-limited. Wait a moment and try again."
            )
        return ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=f"OpenRouter — {last_error[:200]}"
        )

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        key = await get_api_key("openrouter_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="OpenRouter API key not set. Add it in Settings (API keys) or in backend/.env as OPENROUTER_API_KEY. Get a key at https://openrouter.ai/keys"
            )
        timeout = kwargs.get("timeout") or MODEL_TIMEOUT
        client = AsyncOpenAI(api_key=key, base_url=BASE_URL, timeout=timeout)
        system = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str | None = kwargs.get("image_mime", "image/jpeg")

        msgs = []
        tools = kwargs.get("tools")
        allowed_tool_names: set[str] = set()
        for t in (tools or []):
            fn = t.get("function") if isinstance(t, dict) else None
            if isinstance(fn, dict):
                n = (fn.get("name") or "").strip()
                if n:
                    allowed_tool_names.add(n)
        if system:
            if tools:
                system = (
                    system
                    + "\n\nTOOL-CALL PROTOCOL (fallback): If you need a tool and cannot emit native tool_calls, "
                    + "output exactly one tag:\n[ASTA_TOOL_CALL]{\"name\":\"tool_name\",\"arguments\":{...}}[/ASTA_TOOL_CALL]\n"
                    + f"Allowed tool names: {', '.join(sorted(allowed_tool_names))}."
                )
            msgs.append({"role": "system", "content": system})

        image_data_url = ""
        if image_bytes:
            import base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:{image_mime};base64,{b64}"

        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "user" and image_data_url and m == messages[-1]:
                msgs.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": content},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                })
            else:
                msg = {"role": role, "content": content}
                if "tool_calls" in m:
                    msg["tool_calls"] = m["tool_calls"]
                if "tool_call_id" in m:
                    msg["tool_call_id"] = m["tool_call_id"]
                msgs.append(msg)

        model_raw = str(kwargs.get("model") or DEFAULT_MODEL).strip()
        if image_bytes:
            model_raw = "nvidia/nemotron-nano-12b-v2-vl:free"
        else:
            allowed_models, rejected_models = classify_openrouter_model_csv(model_raw)
            if rejected_models:
                logger.warning(
                    "OpenRouter model policy dropped unsupported model(s): %s",
                    ", ".join(rejected_models),
                )
            if not allowed_models:
                allowed_models, _ = classify_openrouter_model_csv(DEFAULT_MODEL)
            model_raw = ",".join(allowed_models)

        models = [m.strip() for m in model_raw.split(",") if m.strip()]
        if not models:
            models = [m.strip() for m in DEFAULT_MODEL.split(",") if m.strip()]

        last_error = ""
        for i, model in enumerate(models):
            try:
                create_kwargs = {"model": model, "messages": msgs, "max_tokens": 4096, "stream": True}
                if tools:
                    create_kwargs["tools"] = tools
                    create_kwargs["tool_choice"] = "auto"
                effort = _reasoning_effort_from_level(kwargs.get("thinking_level"))
                if effort:
                    create_kwargs["reasoning_effort"] = effort
                try:
                    stream = await client.chat.completions.create(**create_kwargs)
                except Exception as first_err:
                    if effort and _is_reasoning_param_unsupported_error(str(first_err)):
                        create_kwargs.pop("reasoning_effort", None)
                        stream = await client.chat.completions.create(**create_kwargs)
                    else:
                        raise

                content_parts: list[str] = []
                stream_tool_calls: dict[int, dict] = {}
                async for chunk in stream:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    delta = getattr(choices[0], "delta", None)
                    if not delta:
                        continue
                    delta_content = getattr(delta, "content", None)
                    text_delta = ""
                    if isinstance(delta_content, str):
                        text_delta = delta_content
                    elif isinstance(delta_content, list):
                        text_delta = "".join(
                            str(getattr(part, "text", "") if not isinstance(part, dict) else part.get("text", "") or "")
                            for part in delta_content
                        )
                    if text_delta:
                        content_parts.append(text_delta)
                        await emit_text_delta(on_text_delta, text_delta)

                    delta_tool_calls = getattr(delta, "tool_calls", None) or []
                    for tc_delta in delta_tool_calls:
                        merge_stream_tool_call_delta(stream_tool_calls, tc_delta)

                content = "".join(content_parts).strip()
                tool_calls = finalize_stream_tool_calls(stream_tool_calls)
                if tools and not tool_calls:
                    parsed_calls, cleaned = _extract_tool_call_from_text(content, allowed_tool_names)
                    if parsed_calls:
                        return ProviderResponse(content=cleaned, tool_calls=parsed_calls)
                return ProviderResponse(content=content, tool_calls=tool_calls)
            except APITimeoutError:
                err_msg = f"Model {model} timed out after {MODEL_TIMEOUT}s"
                last_error = err_msg
                if i < len(models) - 1:
                    logger.warning("%s, trying fallback %s", last_error, models[i + 1])
                else:
                    logger.error("All models exhausted. %s", last_error)
            except Exception as e:
                msg = str(e).strip() or repr(e)
                if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                    return ProviderResponse(
                        content="",
                        error=ProviderError.AUTH,
                        error_message="OpenRouter API key invalid or expired. Check Settings → API keys."
                    )
                last_error = msg
                if i < len(models) - 1:
                    logger.warning("Model %s failed (%s), trying fallback %s", model, msg[:100], models[i + 1])
                else:
                    logger.error("All models exhausted. Last error from %s: %s", model, msg[:200])

        if "429" in last_error or "rate" in last_error.lower():
            return ProviderResponse(
                content="",
                error=ProviderError.RATE_LIMIT,
                error_message="All models rate-limited. Wait a moment and try again."
            )
        return ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=f"OpenRouter — {last_error[:200]}"
        )
