"""Google Gemini provider — OpenAI-compatible API, vision + tools support."""
import base64
import logging

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

logger = logging.getLogger(__name__)

GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-2.5-flash"
MODEL_TIMEOUT = 90


def _clean(s: object) -> str:
    """Strip lone surrogate characters that cause UTF-8/JSON serialization failures."""
    if not isinstance(s, str):
        return s  # type: ignore[return-value]
    return s.encode("utf-8", errors="replace").decode("utf-8")


def _build_client(key: str, timeout: int) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=key,
        base_url=GOOGLE_BASE_URL,
        timeout=timeout,
    )


def _build_msgs(messages: list[Message], system: str, image_bytes: bytes | None, image_mime: str) -> list[dict]:
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})

    image_data_url = ""
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:{image_mime};base64,{b64}"

    for m in messages:
        role = m["role"]
        content = _clean(m.get("content") or "")
        if role == "user" and image_data_url and m == messages[-1]:
            msgs.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": content},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            })
        else:
            msg: dict = {"role": role, "content": content}
            if "tool_calls" in m:
                msg["tool_calls"] = m["tool_calls"]
            if "tool_call_id" in m:
                msg["tool_call_id"] = m["tool_call_id"]
            msgs.append(msg)
    return msgs


def _parse_tool_calls(raw_tool_calls) -> list[dict] | None:
    if not raw_tool_calls:
        return None
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments or "{}",
            },
        }
        for tc in raw_tool_calls
    ]


def _classify_error(e: Exception) -> ProviderResponse:
    msg = str(e)
    if "API key not valid" in msg or "401" in msg:
        return ProviderResponse(content="", error=ProviderError.AUTH, error_message=f"Google API key invalid: {msg}")
    if "429" in msg or "quota" in msg.lower() or "Resource has been exhausted" in msg:
        return ProviderResponse(content="", error=ProviderError.RATE_LIMIT, error_message=f"Google rate limit: {msg}")
    return ProviderResponse(content="", error=ProviderError.TRANSIENT, error_message=f"Google error: {msg}")


class GoogleProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "google"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("gemini_api_key") or await get_api_key("google_ai_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message=(
                    "Google/Gemini API key not set. "
                    "Add it in Settings (API keys) or in backend/.env as GEMINI_API_KEY. "
                    "Get a free key at https://aistudio.google.com/apikey"
                ),
            )

        timeout = kwargs.get("timeout") or MODEL_TIMEOUT
        client = _build_client(key, timeout)
        model = kwargs.get("model") or DEFAULT_MODEL
        system = _clean(kwargs.get("context", ""))
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str = kwargs.get("image_mime") or "image/jpeg"
        tools = kwargs.get("tools")

        msgs = _build_msgs(messages, system, image_bytes, image_mime)

        try:
            create_kwargs: dict = {"model": model, "messages": msgs, "max_tokens": 8096}
            if tools:
                create_kwargs["tools"] = tools
                create_kwargs["tool_choice"] = "auto"

            r = await client.chat.completions.create(**create_kwargs)
            choice = r.choices[0] if r.choices else None
            if not choice:
                return ProviderResponse(content="", error=ProviderError.TRANSIENT, error_message="Google returned empty response")

            content = _clean(choice.message.content or "")
            tool_calls = _parse_tool_calls(choice.message.tool_calls)
            return ProviderResponse(content=content, tool_calls=tool_calls)

        except APITimeoutError:
            return ProviderResponse(content="", error=ProviderError.TRANSIENT, error_message=f"Google API timeout after {timeout}s")
        except Exception as e:
            return _classify_error(e)

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        key = await get_api_key("gemini_api_key") or await get_api_key("google_ai_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Google API key not set.",
            )

        timeout = kwargs.get("timeout") or MODEL_TIMEOUT
        client = _build_client(key, timeout)
        model = kwargs.get("model") or DEFAULT_MODEL
        system = _clean(kwargs.get("context", ""))
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str = kwargs.get("image_mime") or "image/jpeg"
        tools = kwargs.get("tools")

        msgs = _build_msgs(messages, system, image_bytes, image_mime)

        try:
            create_kwargs: dict = {"model": model, "messages": msgs, "max_tokens": 8096, "stream": True}
            if tools:
                create_kwargs["tools"] = tools
                create_kwargs["tool_choice"] = "auto"

            stream = await client.chat.completions.create(**create_kwargs)

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
                if isinstance(delta_content, str) and delta_content:
                    content_parts.append(delta_content)
                    await emit_text_delta(on_text_delta, delta_content)

                delta_tool_calls = getattr(delta, "tool_calls", None) or []
                for tc_delta in delta_tool_calls:
                    merge_stream_tool_call_delta(stream_tool_calls, tc_delta)

            content = _clean("".join(content_parts).strip())
            tool_calls = finalize_stream_tool_calls(stream_tool_calls)
            return ProviderResponse(content=content, tool_calls=tool_calls)

        except APITimeoutError:
            return ProviderResponse(content="", error=ProviderError.TRANSIENT, error_message=f"Google stream timeout after {timeout}s")
        except Exception as e:
            return _classify_error(e)
