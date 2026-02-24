"""Resolve API keys: stored (DB) first, then env. Used by providers."""
from app.config import get_settings
from app.db import get_db

_ENV_KEYS = {
    "groq_api_key": "groq_api_key",
    "gemini_api_key": "gemini_api_key",
    "google_ai_key": "google_ai_key",
    "huggingface_api_key": "huggingface_api_key",
    "anthropic_api_key": "anthropic_api_key",
    "openai_api_key": "openai_api_key",
    "openrouter_api_key": "openrouter_api_key",
    "telegram_bot_token": "telegram_bot_token",
    "spotify_client_id": "spotify_client_id",
    "spotify_client_secret": "spotify_client_secret",
}


async def get_api_key(key_name: str) -> str | None:
    """Return API key: from DB if set, else from env. Used by AI providers."""
    db = get_db()
    await db.connect()
    stored = await db.get_stored_api_key(key_name)
    if stored:
        return stored
    s = get_settings()
    val = getattr(s, key_name, None)
    return (val or "").strip() or None
