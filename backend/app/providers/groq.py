"""Groq provider (key from panel Settings or .env)."""
from openai import AsyncOpenAI
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


class GroqProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "groq"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("groq_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Groq API key not set. Add it in Settings (API keys) or in backend/.env as GROQ_API_KEY."
            )
        client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        system = kwargs.get("context", "")
        msgs = []
        for m in messages:
            msg = {"role": m["role"], "content": m.get("content") or ""}
            if "tool_calls" in m:
                msg["tool_calls"] = m["tool_calls"]
            if "tool_call_id" in m:
                msg["tool_call_id"] = m["tool_call_id"]
            msgs.append(msg)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = kwargs.get("model") or "llama-3.3-70b-versatile"
        tools = kwargs.get("tools")
        try:
            create_kwargs = {"model": model, "messages": msgs}
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
            tool_calls = None
            if getattr(msg, "tool_calls", None):
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": getattr(tc, "type", "function"),
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                    }
                    for tc in msg.tool_calls
                ]
            return ProviderResponse(content=content, tool_calls=tool_calls)
        except Exception as e:
            msg = str(e).strip() or repr(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.AUTH,
                    error_message=f"Groq API key invalid or expired: {msg}"
                )
            if "decommissioned" in msg.lower() or "model_decommissioned" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.MODEL_NOT_FOUND,
                    error_message=f"Groq model '{model}' has been decommissioned."
                )
            if "404" in msg or "not found" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.MODEL_NOT_FOUND,
                    error_message=f"Groq model '{model}' not found."
                )
            if "429" in msg or "rate" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.RATE_LIMIT,
                    error_message=f"Groq rate limit: {msg}"
                )
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Groq API error: {msg[:200]}"
            )

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        key = await get_api_key("groq_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Groq API key not set. Add it in Settings (API keys) or in backend/.env as GROQ_API_KEY."
            )
        client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        system = kwargs.get("context", "")
        msgs = []
        for m in messages:
            msg = {"role": m["role"], "content": m.get("content") or ""}
            if "tool_calls" in m:
                msg["tool_calls"] = m["tool_calls"]
            if "tool_call_id" in m:
                msg["tool_call_id"] = m["tool_call_id"]
            msgs.append(msg)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = kwargs.get("model") or "llama-3.3-70b-versatile"
        tools = kwargs.get("tools")
        try:
            create_kwargs = {"model": model, "messages": msgs, "stream": True}
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

            return ProviderResponse(
                content="".join(content_parts).strip(),
                tool_calls=finalize_stream_tool_calls(stream_tool_calls),
            )
        except Exception as e:
            msg = str(e).strip() or repr(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.AUTH,
                    error_message=f"Groq API key invalid or expired: {msg}"
                )
            if "decommissioned" in msg.lower() or "model_decommissioned" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.MODEL_NOT_FOUND,
                    error_message=f"Groq model '{model}' has been decommissioned."
                )
            if "404" in msg or "not found" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.MODEL_NOT_FOUND,
                    error_message=f"Groq model '{model}' not found."
                )
            if "429" in msg or "rate" in msg.lower():
                return ProviderResponse(
                    content="",
                    error=ProviderError.RATE_LIMIT,
                    error_message=f"Groq rate limit: {msg}"
                )
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Groq API error: {msg[:200]}"
            )
