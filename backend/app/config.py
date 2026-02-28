"""Load settings from environment."""
import os
import re
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_TELEGRAM_PREFIX_RE = re.compile(r"^(telegram|tg):", re.IGNORECASE)


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


def save_settings_to_env(updates: dict[str, str]) -> None:
    """Persist multiple env keys in backend/.env and refresh cached settings."""
    if not updates:
        return
    
    lines: list[str] = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    
    out: list[str] = []
    remaining = updates.copy()
    
    # Update existing lines
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        
        # Check if this line matches any of our updates
        key, _, _ = line.partition("=")
        key = key.strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
            
    # Add new lines for any remaining updates
    for key, value in remaining.items():
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
        
    _ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    
    # Update in-memory environment
    for key, value in updates.items():
        os.environ[key] = str(value)
        
    get_settings.cache_clear()


def set_env_value(key: str, value: str, *, allow_empty: bool = False) -> None:
    """Persist an env key in backend/.env and refresh cached settings."""
    k = (key or "").strip()
    if not k:
        raise ValueError("key is required")
    v = (value or "").strip()
    if (not v) and (not allow_empty):
        raise ValueError("value is required")

    lines: list[str] = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    replaced = False
    out: list[str] = []
    prefix = f"{k}="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            out.append(line)
            continue
        if line.startswith(prefix):
            out.append(prefix + v)
            replaced = True
            continue
        out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(prefix + v)
    _ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[k] = v
    get_settings.cache_clear()


class Settings(BaseSettings):
    @property
    def telegram_allowlist_configured(self) -> bool:
        return bool((self.asta_telegram_allowed_ids or "").strip())

    @property
    def telegram_allowlist_invalid(self) -> set[str]:
        raw = (self.asta_telegram_allowed_ids or "").strip()
        if not raw:
            return set()
        invalid: set[str] = set()
        for entry in raw.split(","):
            e = _TELEGRAM_PREFIX_RE.sub("", entry.strip()).strip()
            if not e or e == "*":
                continue
            if not e.isdigit():
                invalid.add(e)
        return invalid

    @property
    def telegram_allowed_ids(self) -> set[str]:
        """Numeric Telegram user IDs allowed to use the bot. Empty config = allow all."""
        raw = (self.asta_telegram_allowed_ids or "").strip()
        if not raw:
            return set()
        out: set[str] = set()
        for entry in raw.split(","):
            e = _TELEGRAM_PREFIX_RE.sub("", entry.strip()).strip()
            if e.isdigit():
                out.add(e)
        return out

    @property
    def exec_allowed_bins(self) -> set[str]:
        """Binary names Asta is allowed to run via [ASTA_EXEC] (Claw-like). E.g. memo, things. Empty = exec disabled."""
        s = (self.asta_exec_allowed_bins or "").strip()
        if not s:
            return set()
        return {x.strip().lower() for x in s.split(",") if x.strip()}

    @property
    def exec_security(self) -> str:
        """Exec security mode: deny | allowlist | full."""
        mode = (self.asta_exec_security or "allowlist").strip().lower()
        if mode not in ("deny", "allowlist", "full"):
            return "allowlist"
        return mode

    @property
    def memory_search_mode(self) -> str:
        """Memory search mode: search (fast lexical-first) or hybrid (lexical + RAG)."""
        mode = (self.asta_memory_search_mode or "search").strip().lower()
        if mode not in ("search", "hybrid"):
            return "search"
        return mode

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
    huggingface_api_key: str | None = None
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None  # OpenRouter (300+ models)
    ollama_base_url: str = "http://localhost:11434"
    asta_telegram_username: str | None = None
    asta_pingram_client_id: str | None = None
    asta_pingram_client_secret: str | None = None
    asta_pingram_api_key: str | None = None  # Optional: from dashboard "API Key"; used as Bearer for sender
    asta_pingram_notification_id: str = "cron_alert"
    asta_pingram_template_id: str | None = None
    asta_owner_phone_number: str | None = None

    # Channels
    telegram_bot_token: str | None = None
    # OpenClaw-style: comma-separated Telegram user IDs allowed to use the bot (e.g. 6168747695). If empty, everyone with the token can use it.
    asta_telegram_allowed_ids: str = ""
# OpenClaw-style workspace: AGENTS.md, USER.md, TOOLS.md, SOUL.md and workspace/skills/*/SKILL.md
    # If empty, defaults to project root "workspace" (parent of backend).
    asta_workspace_dir: str = ""

    # Security: allowed paths for file operations (comma-separated)
    asta_allowed_paths: str = ""

    # Exec tool (Claw-like): comma-separated binary names Asta can run (e.g. memo, things). Empty = disabled.
    asta_exec_allowed_bins: str = ""
    # Exec security mode: deny | allowlist | full
    # - deny: exec is disabled
    # - allowlist: only ASTA_EXEC_ALLOWED_BINS (+ enabled skill bins) are allowed
    # - full: any command is allowed (dangerous; use only if you trust the agent/runtime)
    asta_exec_security: str = "allowlist"

    # CORS: extra origins (comma-separated), e.g. http://192.168.1.113:5174 or Tailscale URL
    asta_cors_origins: str = ""
    # Memory search mode: search (fast lexical-first) | hybrid (lexical + rag)
    asta_memory_search_mode: str = "search"

    # Debug UX: show tool usage trace in assistant replies for selected channels.
    asta_show_tool_trace: bool = False
    asta_tool_trace_channels: str = "web"
    # Subagent orchestration (single-user OpenClaw-style)
    asta_subagents_auto_spawn: bool = True
    asta_subagents_max_concurrent: int = 3
    asta_subagents_max_depth: int = 1  # Maximum nesting depth for subagents (1 = no nesting)
    asta_subagents_max_children: int = 5  # Maximum concurrent children per agent
    asta_subagents_archive_after_minutes: int = 60
    # Vision pipeline:
    # - preprocess=True: run a low-cost vision model first, then pass analysis to the main agent model.
    # - provider order: first configured provider in this list is used.
    asta_vision_preprocess: bool = True
    asta_vision_provider_order: str = "openrouter,ollama"
    asta_vision_openrouter_model: str = "nvidia/nemotron-nano-12b-v2-vl:free"

    @property
    def tool_trace_channels(self) -> set[str]:
        s = (self.asta_tool_trace_channels or "").strip().lower()
        if not s:
            return set()
        return {x.strip() for x in s.split(",") if x.strip()}

    # Spotify (search only; playback control would need user OAuth)
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    # Vercel API
    vercel_api_token: str | None = None

    # GitHub API
    github_api_token: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(_ENV_FILE)
    return Settings()
