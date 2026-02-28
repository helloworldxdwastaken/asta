"""Claude (Anthropic) provider (key from panel Settings or .env)."""
import base64
import json

from anthropic import AsyncAnthropic
from app.providers.base import (
    BaseProvider, Message, ProviderResponse, ProviderError,
    TextDeltaCallback, StreamEventCallback,
    emit_text_delta, emit_stream_event,
)
from app.keys import get_api_key

_THINKING_BUDGET: dict[str, int] = {
    "minimal": 1024,
    "low":     2048,
    "medium":  4096,
    "high":    8192,
    "xhigh":   16000,
}


class ClaudeProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "claude"

    @staticmethod
    def _to_anthropic_messages(
        messages: list[Message],
        *,
        image_b64: str | None = None,
        image_mime: str = "image/jpeg",
    ) -> list[dict]:
        out: list[dict] = []
        image_idx = -1
        if image_b64:
            for i in range(len(messages) - 1, -1, -1):
                role = (messages[i].get("role") or "").strip().lower()
                if role == "user":
                    image_idx = i
                    break
        for idx, m in enumerate(messages):
            role = (m.get("role") or "").strip().lower()
            content = m.get("content") or ""
            if role == "assistant" and m.get("tool_calls"):
                blocks: list[dict] = []
                if content:
                    blocks.append({"type": "text", "text": str(content)})
                for tc in (m.get("tool_calls") or []):
                    fn = tc.get("function") or {}
                    args_raw = fn.get("arguments") or "{}"
                    args: dict = {}
                    try:
                        if isinstance(args_raw, str):
                            parsed = json.loads(args_raw)
                            if isinstance(parsed, dict):
                                args = parsed
                        elif isinstance(args_raw, dict):
                            args = args_raw
                    except Exception:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or "tool_call",
                            "name": fn.get("name") or "",
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
                continue
            if role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id") or "",
                                "content": str(content),
                            }
                        ],
                    }
                )
                continue
            if role != "assistant" and image_b64 and image_idx == idx:
                text_content = str(content or "").strip() or "Please analyze this image."
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_content},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_mime or "image/jpeg",
                                    "data": image_b64,
                                },
                            },
                        ],
                    }
                )
                continue
            out.append({"role": "assistant" if role == "assistant" else "user", "content": str(content)})
        return out

    @staticmethod
    def _to_anthropic_tools(openai_tools: list[dict] | None) -> list[dict]:
        tools: list[dict] = []
        for t in (openai_tools or []):
            fn = t.get("function") if isinstance(t, dict) else None
            if not isinstance(fn, dict):
                continue
            name = (fn.get("name") or "").strip()
            if not name:
                continue
            tools.append(
                {
                    "name": name,
                    "description": fn.get("description") or "",
                    "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return tools

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("anthropic_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Anthropic API key not set. Add it in Settings (API keys) or in backend/.env as ANTHROPIC_API_KEY."
            )
        timeout = kwargs.get("timeout")
        client = AsyncAnthropic(api_key=key, timeout=float(timeout) if timeout else 120.0)
        system = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str = (kwargs.get("image_mime") or "image/jpeg").strip() or "image/jpeg"
        image_b64: str | None = None
        if image_bytes:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        msgs = self._to_anthropic_messages(messages, image_b64=image_b64, image_mime=image_mime)
        model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        tools = self._to_anthropic_tools(kwargs.get("tools"))
        thinking_level = str(kwargs.get("thinking_level") or "off").strip().lower()
        budget = _THINKING_BUDGET.get(thinking_level)
        max_tokens = max(budget + 2000, 8096) if budget else 8096
        try:
            create_kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                system=system or None,
                messages=msgs,
            )
            if tools:
                create_kwargs["tools"] = tools
            if budget:
                create_kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                create_kwargs["betas"] = ["interleaved-thinking-2025-05-14"]
            r = await client.messages.create(**create_kwargs)
            # Capture token usage
            _usage = getattr(r, "usage", None)
            _in = getattr(_usage, "input_tokens", 0) or 0
            _out = getattr(_usage, "output_tokens", 0) or 0
            if _in or _out:
                try:
                    from app.db import get_db
                    await get_db().record_usage("claude", model, _in, _out)
                except Exception:
                    pass
            text_blocks: list[str] = []
            tool_calls: list[dict] = []
            for b in (r.content or []):
                btype = getattr(b, "type", "")
                if btype == "thinking":
                    thinking_text = (getattr(b, "thinking", "") or "").strip()
                    if thinking_text:
                        text_blocks.append(f"<think>{thinking_text}</think>")
                elif btype == "text":
                    text = (getattr(b, "text", "") or "").strip()
                    if text:
                        text_blocks.append(text)
                elif btype == "tool_use":
                    args = getattr(b, "input", None)
                    try:
                        args_str = json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False)
                    except Exception:
                        args_str = "{}"
                    tool_calls.append(
                        {
                            "id": getattr(b, "id", "") or "tool_call",
                            "type": "function",
                            "function": {
                                "name": getattr(b, "name", "") or "",
                                "arguments": args_str,
                            },
                        }
                    )
            content = "\n".join(text_blocks).strip()
            return ProviderResponse(content=content, tool_calls=tool_calls or None)
        except Exception as e:
            msg = str(e)
            if "authentication" in msg.lower() or "401" in msg:
                return ProviderResponse(
                    content="", 
                    error=ProviderError.AUTH, 
                    error_message=f"Anthropic API key invalid: {msg}"
                )
            if "rate limit" in msg.lower() or "429" in msg:
                return ProviderResponse(
                    content="", 
                    error=ProviderError.RATE_LIMIT, 
                    error_message=f"Anthropic rate limit: {msg}"
                )
            if "not found" in msg.lower() or "404" in msg:
                 return ProviderResponse(
                    content="", 
                    error=ProviderError.MODEL_NOT_FOUND, 
                    error_message=f"Anthropic model {model} not found: {msg}"
                )
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Anthropic error: {msg}"
            )

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        on_stream_event: StreamEventCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        key = await get_api_key("anthropic_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Anthropic API key not set. Add it in Settings (API keys) or in backend/.env as ANTHROPIC_API_KEY.",
            )
        client = AsyncAnthropic(api_key=key)
        system = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str = (kwargs.get("image_mime") or "image/jpeg").strip() or "image/jpeg"
        image_b64 = base64.b64encode(image_bytes).decode() if image_bytes else None
        msgs = self._to_anthropic_messages(messages, image_b64=image_b64, image_mime=image_mime)
        model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        tools = self._to_anthropic_tools(kwargs.get("tools"))
        thinking_level = str(kwargs.get("thinking_level") or "off").strip().lower()

        budget = _THINKING_BUDGET.get(thinking_level)
        max_tokens = max(budget + 2000, 8096) if budget else 8096

        create_kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": msgs,
            "stream": True,
        }
        if system:
            create_kwargs["system"] = system
        if tools:
            create_kwargs["tools"] = tools
        if budget:
            create_kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
            create_kwargs["betas"] = ["interleaved-thinking-2025-05-14"]

        await emit_stream_event(on_stream_event, {"type": "message_start"})
        content_parts: list[str] = []
        tool_calls_list: list[dict] = []
        in_thinking = False
        cur_tool_id = cur_tool_name = cur_tool_args = ""
        _stream_in_tokens = 0
        _stream_out_tokens = 0

        try:
            stream = await client.messages.create(**create_kwargs)
            async for event in stream:
                etype = getattr(event, "type", "")
                if etype == "message_start":
                    _u = getattr(getattr(event, "message", None), "usage", None)
                    _stream_in_tokens = getattr(_u, "input_tokens", 0) or 0
                elif etype == "message_delta":
                    _u = getattr(event, "usage", None)
                    _stream_out_tokens = getattr(_u, "output_tokens", 0) or 0

                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    btype = getattr(block, "type", "") if block else ""
                    if btype == "thinking":
                        in_thinking = True
                        content_parts.append("<think>")
                        await emit_text_delta(on_text_delta, "<think>")
                    elif btype == "tool_use":
                        cur_tool_id = getattr(block, "id", "") or ""
                        cur_tool_name = getattr(block, "name", "") or ""
                        cur_tool_args = ""

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", "") if delta else ""
                    if dtype == "thinking_delta":
                        text = getattr(delta, "thinking", "") or ""
                        if text:
                            content_parts.append(text)
                            await emit_text_delta(on_text_delta, text)
                    elif dtype == "text_delta":
                        text = getattr(delta, "text", "") or ""
                        if text:
                            content_parts.append(text)
                            await emit_text_delta(on_text_delta, text)
                    elif dtype == "input_json_delta":
                        cur_tool_args += getattr(delta, "partial_json", "") or ""

                elif etype == "content_block_stop":
                    if in_thinking:
                        content_parts.append("</think>")
                        await emit_text_delta(on_text_delta, "</think>")
                        in_thinking = False
                    elif cur_tool_name:
                        try:
                            args = json.loads(cur_tool_args) if cur_tool_args else {}
                        except Exception:
                            args = {}
                        tool_calls_list.append({
                            "id": cur_tool_id or "tool_call",
                            "type": "function",
                            "function": {"name": cur_tool_name, "arguments": json.dumps(args)},
                        })
                        cur_tool_id = cur_tool_name = cur_tool_args = ""

        except Exception as e:
            msg = str(e)
            if "authentication" in msg.lower() or "401" in msg:
                return ProviderResponse(content="", error=ProviderError.AUTH, error_message=f"Anthropic API key invalid: {msg}")
            if "rate limit" in msg.lower() or "429" in msg:
                return ProviderResponse(content="", error=ProviderError.RATE_LIMIT, error_message=f"Anthropic rate limit: {msg}")
            return ProviderResponse(content="", error=ProviderError.TRANSIENT, error_message=f"Anthropic streaming error: {msg}")

        content = "".join(content_parts).strip()
        await emit_stream_event(on_stream_event, {"type": "message_end", "content": content})
        if _stream_in_tokens or _stream_out_tokens:
            try:
                from app.db import get_db
                await get_db().record_usage("claude", model, _stream_in_tokens, _stream_out_tokens)
            except Exception:
                pass
        return ProviderResponse(content=content, tool_calls=tool_calls_list or None)
