"""Load settings from environment."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


class Settings(BaseSettings):
    app_name: str = "Asta"
    debug: bool = False

    # AI
    openai_api_key: str | None = None
    google_ai_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None  # OpenRouter (300+ models)
    ollama_base_url: str = "http://localhost:11434"

    # Channels
    telegram_bot_token: str | None = None
    asta_whatsapp_bridge_url: str | None = None  # e.g. http://localhost:3001 for outbound reminders

    # Security: allowed paths for file operations (comma-separated)
    asta_allowed_paths: str = ""

    # CORS: extra origins (comma-separated), e.g. http://192.168.1.113:5174 or Tailscale URL
    asta_cors_origins: str = ""

    # Spotify (search only; playback control would need user OAuth)
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(_ENV_FILE)
    return Settings()
