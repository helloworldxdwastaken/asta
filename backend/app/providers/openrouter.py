"""OpenRouter provider — 300+ models with fallback support."""
import json
import logging
import re
from openai import AsyncOpenAI, APITimeoutError
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key

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
# Free model; user can set any OpenRouter model in Settings (e.g. arcee-ai/trinity-large-preview:free)
DEFAULT_MODEL = "arcee-ai/trinity-large-preview:free"
# Timeout per model attempt (seconds). 60 helps when we send large tool output (e.g. memo notes) and wait for a summary.
MODEL_TIMEOUT = 60


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

        # Support comma-separated models: first is primary, rest are fallbacks
        model_raw = kwargs.get("model") or DEFAULT_MODEL
        if image_bytes:
            # Force vision model if image present
            model_raw = "nvidia/nemotron-nano-12b-v2-vl:free"
            
        models = [m.strip() for m in model_raw.split(",") if m.strip()]
        if not models:
            models = [DEFAULT_MODEL]

        last_error = ""
        for i, model in enumerate(models):
            try:
                create_kwargs = {"model": model, "messages": msgs, "max_tokens": 4096}
                if tools:
                    create_kwargs["tools"] = tools
                    create_kwargs["tool_choice"] = "auto"
                r = await client.chat.completions.create(**create_kwargs)
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
