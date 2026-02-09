"""Google Gemini provider (key from panel Settings or .env)."""
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key


class GoogleProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "google"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("gemini_api_key") or await get_api_key("google_ai_key")
        if not key:
            return "Error: Google/Gemini API key not set. Add it in Settings (API keys) or in backend/.env as GEMINI_API_KEY or GOOGLE_AI_KEY."
        genai.configure(api_key=key)
        model = genai.GenerativeModel(kwargs.get("model") or "gemini-1.5-flash")
        system = kwargs.get("context", "")
        parts = []
        if system:
            parts.append(system + "\n\n")
        for m in messages:
            parts.append(f"{m['role']}: {m['content']}\n")
        prompt = "".join(parts) + "assistant:"
        r = await model.generate_content_async(prompt)
        return (r.text or "").strip()
