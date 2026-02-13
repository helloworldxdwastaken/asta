"""Google Gemini provider (key from panel Settings or .env)."""
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key


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
                error_message="Google/Gemini API key not set. Add it in Settings (API keys) or in backend/.env as GEMINI_API_KEY or GOOGLE_AI_KEY."
            )
        genai.configure(api_key=key)
        model = genai.GenerativeModel(kwargs.get("model") or "gemini-1.5-flash")
        system = kwargs.get("context", "")
        parts = []
        if system:
            parts.append(system + "\n\n")
        for m in messages:
            parts.append(f"{m['role']}: {m['content']}\n")
        prompt = "".join(parts) + "assistant:"
        try:
            r = await model.generate_content_async(prompt)
            return ProviderResponse(content=(r.text or "").strip())
        except Exception as e:
            msg = str(e)
            if "API key not valid" in msg or "401" in msg:
                 return ProviderResponse(
                    content="",
                    error=ProviderError.AUTH,
                    error_message=f"Google API key invalid: {msg}"
                )
            if "429" in msg or "Resource has been exhausted" in msg:
                 return ProviderResponse(
                    content="",
                    error=ProviderError.RATE_LIMIT,
                    error_message=f"Google rate limit: {msg}"
                )
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Google API error: {msg}"
            )
