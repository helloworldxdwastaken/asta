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
    # WhatsApp Whitelist (comma-separated numbers or list)
    asta_whatsapp_allowed_numbers: str | int | list[str] = []

    @property
    def whatsapp_whitelist(self) -> set[str]:
        val = self.asta_whatsapp_allowed_numbers
        if not val:
            return set()
        if isinstance(val, (str, int)):
            nums = str(val).split(",")
        else:
            nums = val
        # Clean up
        return {str(n).strip() for n in nums if str(n).strip()}

    @property
    def telegram_allowed_ids(self) -> set[str]:
        """Telegram user IDs allowed to use the bot (OpenClaw-style allowlist). Empty = allow all."""
        s = (self.asta_telegram_allowed_ids or "").strip()
        if not s:
            return set()
        return {x.strip() for x in s.split(",") if x.strip()}

    @property
    def exec_allowed_bins(self) -> set[str]:
        """Binary names Asta is allowed to run via [ASTA_EXEC] (Claw-like). E.g. memo, things. Empty = exec disabled."""
        s = (self.asta_exec_allowed_bins or "").strip()
        if not s:
            return set()
        return {x.strip().lower() for x in s.split(",") if x.strip()}

    @property
    def workspace_path(self) -> Path | None:
        """Resolved OpenClaw-style workspace directory. Asta always has a default: workspace/ at project root (created if missing)."""
        if (s := (self.asta_workspace_dir or "").strip()):
            p = Path(s).resolve()
            if p.is_dir():
                return p
            p.mkdir(parents=True, exist_ok=True)
            return p
        # Default: project root / workspace (parent of backend). Create so file creation etc. work out of the box.
        backend_dir = Path(__file__).resolve().parent.parent
        default = backend_dir.parent / "workspace"
        default.mkdir(parents=True, exist_ok=True)
        return default

    # App
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
    # OpenClaw-style: comma-separated Telegram user IDs allowed to use the bot (e.g. 6168747695). If empty, everyone with the token can use it.
    asta_telegram_allowed_ids: str = ""
    asta_whatsapp_bridge_url: str | None = None  # e.g. http://localhost:3001 for outbound reminders

    # OpenClaw-style workspace: AGENTS.md, USER.md, TOOLS.md, SOUL.md and workspace/skills/*/SKILL.md
    # If empty, defaults to project root "workspace" (parent of backend).
    asta_workspace_dir: str = ""

    # Security: allowed paths for file operations (comma-separated)
    asta_allowed_paths: str = ""

    # Exec tool (Claw-like): comma-separated binary names Asta can run (e.g. memo, things). Empty = disabled.
    asta_exec_allowed_bins: str = ""

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
