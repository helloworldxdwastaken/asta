"""OpenRouter provider — 300+ models with fallback support."""
import logging
from openai import AsyncOpenAI, APITimeoutError
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"
# Free model; user can set any OpenRouter model in Settings (e.g. arcee-ai/trinity-large-preview:free)
DEFAULT_MODEL = "arcee-ai/trinity-large-preview:free"
# Timeout per model attempt (seconds) — keeps fallbacks responsive
MODEL_TIMEOUT = 30


class OpenRouterProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "openrouter"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("openrouter_api_key")
        if not key:
            return "Error: OpenRouter API key not set. Add it in Settings (API keys) or in backend/.env as OPENROUTER_API_KEY. Get a key at https://openrouter.ai/keys"
        client = AsyncOpenAI(api_key=key, base_url=BASE_URL, timeout=MODEL_TIMEOUT)
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        if system:
            msgs = [{"role": "system", "content": system}] + msgs

        # Support comma-separated models: first is primary, rest are fallbacks
        model_raw = kwargs.get("model") or DEFAULT_MODEL
        models = [m.strip() for m in model_raw.split(",") if m.strip()]
        if not models:
            models = [DEFAULT_MODEL]

        last_error = ""
        for i, model in enumerate(models):
            try:
                r = await client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    max_tokens=4096,
                )
                return (r.choices[0].message.content or "").strip()
            except APITimeoutError:
                last_error = f"Model {model} timed out after {MODEL_TIMEOUT}s"
                if i < len(models) - 1:
                    logger.warning("%s, trying fallback %s", last_error, models[i + 1])
                else:
                    logger.error("All models exhausted. %s", last_error)
            except Exception as e:
                msg = str(e).strip() or repr(e)
                # Auth errors won't be fixed by a different model — return immediately
                if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                    return "Error: OpenRouter API key invalid or expired. Check Settings → API keys."
                last_error = msg
                if i < len(models) - 1:
                    logger.warning("Model %s failed (%s), trying fallback %s", model, msg[:100], models[i + 1])
                else:
                    logger.error("All models exhausted. Last error from %s: %s", model, msg[:200])

        if "429" in last_error or "rate" in last_error.lower():
            return "Error: All models rate-limited. Wait a moment and try again."
        return f"Error: OpenRouter — {last_error[:200]}"

