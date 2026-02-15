"""Claude (Anthropic) provider (key from panel Settings or .env)."""
import base64
import json

from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key


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
        client = AsyncAnthropic(api_key=key)
        system = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_mime: str = (kwargs.get("image_mime") or "image/jpeg").strip() or "image/jpeg"
        image_b64: str | None = None
        if image_bytes:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        msgs = self._to_anthropic_messages(messages, image_b64=image_b64, image_mime=image_mime)
        model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        tools = self._to_anthropic_tools(kwargs.get("tools"))
        try:
            create_kwargs = dict(
                model=model,
                max_tokens=2048,
                system=system or None,
                messages=msgs,
            )
            if tools:
                create_kwargs["tools"] = tools
            r = await client.messages.create(**create_kwargs)
            text_blocks: list[str] = []
            tool_calls: list[dict] = []
            for b in (r.content or []):
                btype = getattr(b, "type", "")
                if btype == "text":
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
