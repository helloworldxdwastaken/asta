"""OpenRouter provider — 300+ models. OpenAI-compatible."""
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key

BASE_URL = "https://openrouter.ai/api/v1"
# Free model; user can set any OpenRouter model in Settings (e.g. arcee-ai/trinity-large-preview:free)
DEFAULT_MODEL = "arcee-ai/trinity-large-preview:free"


class OpenRouterProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "openrouter"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("openrouter_api_key")
        if not key:
            return "Error: OpenRouter API key not set. Add it in Settings (API keys) or in backend/.env as OPENROUTER_API_KEY. Get a key at https://openrouter.ai/keys"
        client = AsyncOpenAI(api_key=key, base_url=BASE_URL)
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = kwargs.get("model") or DEFAULT_MODEL
        try:
            r = await client.chat.completions.create(
                model=model,
                messages=msgs,
                max_tokens=4096,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e).strip() or repr(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                return "Error: OpenRouter API key invalid or expired. Check Settings → API keys."
            if "429" in msg or "rate" in msg.lower():
                return "Error: OpenRouter rate limit. Wait a moment and try again."
            return f"Error: OpenRouter — {msg[:200]}"
