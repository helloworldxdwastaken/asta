"""OpenAI provider (GPT-4o, gpt-4o-mini, etc.)."""
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "openai"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("openai_api_key")
        if not key:
            return "Error: OpenAI API key not set. Add it in Settings (API keys) or in backend/.env as OPENAI_API_KEY."
        client = AsyncOpenAI(api_key=key)
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = kwargs.get("model") or DEFAULT_MODEL
        try:
            r = await client.chat.completions.create(model=model, messages=msgs)
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e).strip() or repr(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                return "Error: OpenAI API key invalid or expired. Check Settings → API keys."
            if "429" in msg or "rate" in msg.lower():
                return "Error: OpenAI rate limit. Wait a moment and try again."
            return f"Error: OpenAI API — {msg[:200]}"
