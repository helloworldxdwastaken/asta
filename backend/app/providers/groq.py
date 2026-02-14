"""Groq provider (key from panel Settings or .env)."""
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key


def _reasoning_effort_from_level(level: str | None) -> str | None:
    lv = (level or "").strip().lower()
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
