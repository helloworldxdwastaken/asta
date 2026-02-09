"""Groq provider (key from panel Settings or .env)."""
from openai import AsyncOpenAI
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key


class GroqProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "groq"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("groq_api_key")
        if not key:
            return "Error: Groq API key not set. Add it in Settings (API keys) or in backend/.env as GROQ_API_KEY."
        client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = kwargs.get("model") or "llama-3.3-70b-versatile"
        try:
            r = await client.chat.completions.create(model=model, messages=msgs)
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e).strip() or repr(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                return "Error: Groq API key invalid or expired. Check Settings → API keys."
            if "decommissioned" in msg.lower() or "model_decommissioned" in msg.lower():
                return f"Error: Groq model '{model}' has been decommissioned. In Settings → Model per provider, set Groq to llama-3.3-70b-versatile (or leave blank to use the new default)."
            if "404" in msg or "not found" in msg.lower():
                return f"Error: Groq model '{model}' not found. Try another in Settings → Model (e.g. llama-3.3-70b-versatile or llama-3.1-8b-instant)."
            if "429" in msg or "rate" in msg.lower():
                return "Error: Groq rate limit. Wait a moment and try again."
            return f"Error: Groq API — {msg[:200]}"
