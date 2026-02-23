"""User settings (mood, API keys), status, skills, and notifications list."""
import io
import logging
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
import httpx
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings, set_env_value
from app.db import get_db
from app.exec_tool import get_effective_exec_bins, resolve_executable
from app.model_policy import (
    OPENROUTER_DEFAULT_MODEL_CHAIN,
    OPENROUTER_RECOMMENDED_MODELS,
    classify_openrouter_model_csv,
)
from app.provider_flow import (
    DEFAULT_MAIN_PROVIDER,
    MAIN_PROVIDER_CHAIN,
    normalize_main_provider,
)
from app.ollama_catalog import (
    ollama_list_tool_models,
    resolve_ollama_model_name,
)
from app.whatsapp_bridge import get_whatsapp_bridge_status

router = APIRouter()
logger = logging.getLogger(__name__)

MAIN_PROVIDER_LABELS = {
    "claude": "Claude",
    "ollama": "Ollama",
    "openrouter": "OpenRouter",
}


async def _ollama_reachable() -> bool:
    """Return True only if Ollama is running and responding at the configured base URL (and response looks like Ollama)."""
    base = (get_settings().ollama_base_url or "").strip() or "http://localhost:11434"
    base = base.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/api/tags")
            if r.status_code != 200:
                return False
            data = r.json()
            # Ollama /api/tags returns {"models": [...]}; ensure we got a real Ollama response
            return isinstance(data, dict) and "models" in data
    except Exception:
        return False


async def _ollama_list_models() -> list[str]:
    """Return tool-capable Ollama model names. Empty if Ollama unreachable or none expose tools capability."""
    return await ollama_list_tool_models()


async def _spotify_configured(db) -> bool:
    """True if Spotify Client ID and Secret are set (DB or env)."""
    from app.keys import get_api_key
    cid = await get_api_key("spotify_client_id")
    secret = await get_api_key("spotify_client_secret")
    return bool((cid or "").strip() and (secret or "").strip())

# Skills the AI can use; user can toggle each on/off.
SKILLS = [
    {"id": "files", "name": "Files", "description": "Local file access and summaries"},
    {"id": "drive", "name": "Google Drive", "description": "Drive files and summaries"},
    {"id": "rag", "name": "Learning (RAG)", "description": "Learned knowledge and documents"},
    {"id": "learn", "name": "Learn about topic", "description": "Say 'learn about X for 30 min' (or 'research/study/become an expert on X') to have Asta learn and store a topic in RAG."},
    {"id": "time", "name": "Time", "description": "Current time (12h AM/PM). Location is used for your timezone when set."},
    {"id": "weather", "name": "Weather", "description": "Current weather and forecast (today, tomorrow). Set your location once so Asta can answer."},
    {"id": "google_search", "name": "Google search", "description": "Search the web for current information"},
    {"id": "lyrics", "name": "Lyrics", "description": "Find song lyrics (free, no key). Ask e.g. 'lyrics for Bohemian Rhapsody'"},
    {"id": "spotify", "name": "Spotify", "description": "Search songs on Spotify. Set Client ID and Secret in Settings → Spotify (or in backend/.env). You can also connect your Spotify account for playback on your devices (with device picker)."},
    {"id": "reminders", "name": "Reminders", "description": "Wake me up or remind me at a time. Set your location so times are in your timezone. E.g. 'Wake me up tomorrow at 7am' or 'Remind me at 6pm to call mom'."},
    {"id": "audio_notes", "name": "Audio notes", "description": "Upload audio (meetings, calls, voice memos); Asta transcribes and formats as meeting notes, action items, or conversation summary. No API key for transcription (runs locally)."},
    {"id": "silly_gif", "name": "Silly GIF", "description": "Occasionally replies with a relevant GIF in friendly chats. Requires Giphy API key."},
    {"id": "self_awareness", "name": "Self Awareness", "description": "When asked about Asta (features, docs, how to use): injects README + CHANGELOG + docs/*.md and workspace context so the model answers from real docs. User context comes from workspace/USER.md."},
    {"id": "server_status", "name": "Server Status", "description": "Monitor system metrics like CPU, RAM, Disk and Uptime. Ask 'server status' or '/status'."},
    {"id": "google_workspace", "name": "Google Workspace", "description": "Read Gmail, Google Calendar, Drive, and Contacts via the `gog` CLI. Install: brew install gogcli, then gog auth add your@gmail.com --services gmail,calendar,drive,contacts"},
    {"id": "github", "name": "GitHub", "description": "Manage repos, issues, pull requests, and CI runs via the `gh` CLI. Install: brew install gh, then gh auth login"},
    {"id": "vercel", "name": "Vercel", "description": "Check deployments and projects via the `vercel` CLI. Install: npm i -g vercel, then vercel login"},
]

ALLOWED_API_KEY_NAMES = frozenset({
    "groq_api_key", "gemini_api_key", "google_ai_key",
    "anthropic_api_key", "openai_api_key", "openrouter_api_key",
    "telegram_bot_token", "giphy_api_key",
    "spotify_client_id", "spotify_client_secret",
    "notion_api_key",
})


class MoodIn(BaseModel):
    mood: str  # serious | friendly | normal


class DefaultAiIn(BaseModel):
    provider: str  # claude | ollama | openrouter


class ThinkingIn(BaseModel):
    thinking_level: str  # off | minimal | low | medium | high | xhigh


class ReasoningIn(BaseModel):
    reasoning_mode: str  # off | on | stream


class FinalModeIn(BaseModel):
    final_mode: str  # off | strict


class VisionSettingsIn(BaseModel):
    preprocess: bool
    provider_order: str
    openrouter_model: str


class TelegramUsernameIn(BaseModel):
    username: str = Field(..., description="Telegram username starting with @")


class PingramSettingsIn(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    api_key: str | None = None
    notification_id: str = "cron_alert"
    template_id: str | None = None
    phone_number: str | None = None


class PingramTestCallIn(BaseModel):
    """Optional creds: if omitted or masked, use stored settings (so Test call works after Save)."""
    client_id: str | None = None
    client_secret: str | None = None
    api_key: str | None = None
    notification_id: str | None = None
    test_number: str = ""
    template_id: str | None = None


@router.get("/settings/default-ai")
async def get_default_ai(user_id: str = "default"):
    db = get_db()
    await db.connect()
    provider = normalize_main_provider(await db.get_user_default_ai(user_id))
    return {"provider": provider}


@router.put("/settings/default-ai")
async def set_default_ai(body: DefaultAiIn, user_id: str = "default"):
    provider = normalize_main_provider(body.provider)
    if provider != (body.provider or "").strip().lower():
        return {"error": f"provider must be one of: {', '.join(MAIN_PROVIDER_CHAIN)}"}
    db = get_db()
    await db.connect()
    await db.set_user_default_ai(user_id, provider)
    await db.set_provider_runtime_enabled(user_id, provider, True)
    return {"provider": provider}


@router.get("/settings/thinking")
@router.get("/api/settings/thinking")
async def get_thinking(user_id: str = "default"):
    db = get_db()
    await db.connect()
    level = await db.get_user_thinking_level(user_id)
    return {"thinking_level": level}


@router.put("/settings/thinking")
@router.put("/api/settings/thinking")
async def set_thinking(body: ThinkingIn, user_id: str = "default"):
    level = (body.thinking_level or "").strip().lower()
    if level not in ("off", "minimal", "low", "medium", "high", "xhigh"):
        raise HTTPException(status_code=400, detail="thinking_level must be off, minimal, low, medium, high, or xhigh")
    db = get_db()
    await db.connect()
    await db.set_user_thinking_level(user_id, level)
    return {"thinking_level": level}


@router.get("/settings/reasoning")
@router.get("/api/settings/reasoning")
async def get_reasoning(user_id: str = "default"):
    db = get_db()
    await db.connect()
    mode = await db.get_user_reasoning_mode(user_id)
    return {"reasoning_mode": mode}


@router.put("/settings/reasoning")
@router.put("/api/settings/reasoning")
async def set_reasoning(body: ReasoningIn, user_id: str = "default"):
    mode = (body.reasoning_mode or "").strip().lower()
    if mode not in ("off", "on", "stream"):
        raise HTTPException(status_code=400, detail="reasoning_mode must be off, on, or stream")
    db = get_db()
    await db.connect()
    await db.set_user_reasoning_mode(user_id, mode)
    return {"reasoning_mode": mode}


@router.get("/settings/final-mode")
@router.get("/api/settings/final-mode")
async def get_final_mode(user_id: str = "default"):
    db = get_db()
    await db.connect()
    mode = await db.get_user_final_mode(user_id)
    return {"final_mode": mode}


@router.put("/settings/final-mode")
@router.put("/api/settings/final-mode")
async def set_final_mode(body: FinalModeIn, user_id: str = "default"):
    mode = (body.final_mode or "").strip().lower()
    if mode not in ("off", "strict"):
        raise HTTPException(status_code=400, detail="final_mode must be off or strict")
    db = get_db()
    await db.connect()
    await db.set_user_final_mode(user_id, mode)
    return {"final_mode": mode}


@router.get("/settings/vision")
@router.get("/api/settings/vision")
async def get_vision_settings():
    s = get_settings()
    return {
        "preprocess": bool(getattr(s, "asta_vision_preprocess", True)),
        "provider_order": str(getattr(s, "asta_vision_provider_order", "openrouter,claude,openai") or ""),
        "openrouter_model": str(
            getattr(s, "asta_vision_openrouter_model", "nvidia/nemotron-nano-12b-v2-vl:free") or ""
        ),
    }


@router.put("/settings/vision")
@router.put("/api/settings/vision")
async def set_vision_settings(body: VisionSettingsIn):
    order_raw = (body.provider_order or "").strip().lower()
    allowed = {"openrouter", "claude", "openai"}
    parsed_order = [p.strip() for p in order_raw.split(",") if p.strip()]
    if parsed_order and any(p not in allowed for p in parsed_order):
        raise HTTPException(
            status_code=400,
            detail="provider_order must only include: openrouter, claude, openai",
        )
    provider_order = ",".join(parsed_order) if parsed_order else "openrouter,claude,openai"
    openrouter_model = (
        (body.openrouter_model or "").strip()
        or "nvidia/nemotron-nano-12b-v2-vl:free"
    )

    set_env_value("ASTA_VISION_PREPROCESS", "true" if bool(body.preprocess) else "false")
    set_env_value("ASTA_VISION_PROVIDER_ORDER", provider_order)
    set_env_value("ASTA_VISION_OPENROUTER_MODEL", openrouter_model)
    return {
        "preprocess": bool(body.preprocess),
        "provider_order": provider_order,
        "openrouter_model": openrouter_model,
    }


class ProviderEnabledIn(BaseModel):
    provider: str
    enabled: bool


@router.get("/settings/provider-flow")
@router.get("/api/settings/provider-flow")
async def get_provider_flow(user_id: str = "default"):
    """Return fixed provider priority, connection status, and runtime enable/disable state."""
    db = get_db()
    await db.connect()
    default_provider = normalize_main_provider(await db.get_user_default_ai(user_id))
    runtime_states = await db.get_provider_runtime_states(user_id, MAIN_PROVIDER_CHAIN)
    models = await db.get_all_provider_models(user_id)
    connected_map = {
        "claude": bool((await db.get_stored_api_key("anthropic_api_key") or "").strip()),
        "openrouter": bool((await db.get_stored_api_key("openrouter_api_key") or "").strip()),
        "ollama": await _ollama_reachable(),
    }
    providers = []
    for idx, provider in enumerate(MAIN_PROVIDER_CHAIN, start=1):
        state = runtime_states.get(provider) or {}
        enabled = bool(state.get("enabled", True))
        auto_disabled = bool(state.get("auto_disabled", False))
        disabled_reason = str(state.get("disabled_reason") or "").strip()
        connected = bool(connected_map.get(provider, False))
        providers.append(
            {
                "provider": provider,
                "label": MAIN_PROVIDER_LABELS.get(provider, provider.title()),
                "position": idx,
                "connected": connected,
                "enabled": enabled,
                "auto_disabled": auto_disabled,
                "disabled_reason": disabled_reason,
                "active": bool(connected and enabled and not auto_disabled),
                "model": str(models.get(provider) or ""),
                "default_model": str(DEFAULT_MODELS.get(provider) or ""),
            }
        )
    return {
        "default_provider": default_provider,
        "order": list(MAIN_PROVIDER_CHAIN),
        "providers": providers,
    }


@router.put("/settings/provider-flow/provider-enabled")
@router.put("/api/settings/provider-flow/provider-enabled")
async def set_provider_enabled(body: ProviderEnabledIn, user_id: str = "default"):
    provider = normalize_main_provider(body.provider)
    if provider != (body.provider or "").strip().lower():
        raise HTTPException(
            status_code=400,
            detail=f"provider must be one of: {', '.join(MAIN_PROVIDER_CHAIN)}",
        )
    db = get_db()
    await db.connect()
    await db.set_provider_runtime_enabled(user_id, provider, bool(body.enabled))
    states = await db.get_provider_runtime_states(user_id, [provider])
    state = states.get(provider) or {}
    return {
        "provider": provider,
        "enabled": bool(state.get("enabled", True)),
        "auto_disabled": bool(state.get("auto_disabled", False)),
        "disabled_reason": str(state.get("disabled_reason") or "").strip(),
    }


class FallbackProvidersIn(BaseModel):
    providers: str  # comma-separated, e.g. "google,openai" or "" to disable


@router.get("/settings/fallback")
@router.get("/api/settings/fallback")
async def get_fallback_providers(user_id: str = "default"):
    """Get fixed fallback order (primary removed from claude->ollama->openrouter chain)."""
    db = get_db()
    await db.connect()
    primary = normalize_main_provider(await db.get_user_default_ai(user_id))
    order = [p for p in MAIN_PROVIDER_CHAIN if p != primary]
    return {"providers": ",".join(order)}


@router.put("/settings/fallback")
@router.put("/api/settings/fallback")
async def set_fallback_providers(body: FallbackProvidersIn, user_id: str = "default"):
    """Fallback order is fixed for now; this endpoint is retained for compatibility."""
    primary = DEFAULT_MAIN_PROVIDER
    try:
        db = get_db()
        await db.connect()
        primary = normalize_main_provider(await db.get_user_default_ai(user_id))
    except Exception:
        pass
    order = [p for p in MAIN_PROVIDER_CHAIN if p != primary]
    return {
        "providers": ",".join(order),
        "locked": True,
        "message": "Fallback order is fixed (claude -> ollama -> openrouter).",
    }


# Default models per provider (used when user has not set a custom model)
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-1.5-flash",
    "claude": "claude-3-5-sonnet-20241022",
    "ollama": "auto (tool-capable local model)",
    "openai": "gpt-4o-mini",
    "openrouter": OPENROUTER_DEFAULT_MODEL_CHAIN,
}


@router.get("/settings/models")
@router.get("/api/settings/models")
async def get_models(user_id: str = "default"):
    """Get custom model name per provider (empty = use provider default)."""
    db = get_db()
    await db.connect()
    custom = await db.get_all_provider_models(user_id)
    return {
        "models": {
            p: custom.get(p) or ""
            for p in ("groq", "google", "claude", "ollama", "openai", "openrouter")
        },
        "defaults": DEFAULT_MODELS,
    }


@router.get("/settings/available-models")
@router.get("/api/settings/available-models")
async def get_available_models():
    """List available tool-capable models per provider used by Settings/Dashboard pickers."""
    ollama_models = await _ollama_list_models()
    # For cloud providers (openai, anthropic, google, groq), we return empty list
    # as they use API keys and models are determined by the provider's API
    # The user can set any model name for these providers
    return {
        "ollama": ollama_models,
        "openrouter": list(OPENROUTER_RECOMMENDED_MODELS),
        "openai": [],  # Uses OpenAI API, user can specify any model
        "claude": [],  # Uses Anthropic API, user can specify any model  
        "google": [],   # Uses Google API, user can specify any model
        "groq": [],    # Uses Groq API, user can specify any model
    }


class ModelIn(BaseModel):
    provider: str
    model: str  # empty string = use provider default


@router.put("/settings/models")
@router.put("/api/settings/models")
async def set_model(body: ModelIn, user_id: str = "default"):
    """Set which model to use for a provider. Leave model empty to use provider default."""
    if body.provider not in ("groq", "google", "claude", "ollama", "openai", "openrouter"):
        return {"error": "provider must be groq, google, claude, ollama, openai, or openrouter"}
    model_value = (body.model or "").strip()

    if body.provider == "openrouter" and model_value:
        allowed, rejected = classify_openrouter_model_csv(model_value)
        if rejected:
            raise HTTPException(
                status_code=400,
                detail=(
                    "OpenRouter model policy only allows Kimi/Trinity models for tool reliability. "
                    f"Rejected: {', '.join(rejected)}. "
                    f"Allowed families: {', '.join(OPENROUTER_RECOMMENDED_MODELS)}"
                ),
            )
        if not allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No allowed OpenRouter models provided. "
                    f"Use one of: {', '.join(OPENROUTER_RECOMMENDED_MODELS)}"
                ),
            )
        model_value = ",".join(allowed)

    if body.provider == "ollama" and model_value:
        if "," in model_value:
            raise HTTPException(
                status_code=400,
                detail="Ollama model must be a single local model name (no comma-separated list).",
            )
        tool_models = await _ollama_list_models()
        if not tool_models:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No tool-capable Ollama models detected. "
                    "Pull one that supports tools (e.g. gpt-oss:20b, llama3.3, qwen2.5-coder:32b)."
                ),
            )
        resolved = resolve_ollama_model_name(model_value, tool_models)
        if resolved not in tool_models:
            preview = ", ".join(tool_models[:8])
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Ollama model '{model_value}' is not tool-capable on this machine. "
                    f"Detected tool-capable models: {preview}"
                ),
            )
        model_value = resolved

    db = get_db()
    await db.connect()
    await db.set_user_provider_model(user_id, body.provider, model_value)
    return {"provider": body.provider, "model": model_value or "(default)"}


@router.get("/settings/mood")
async def get_mood(user_id: str = "default"):
    db = get_db()
    await db.connect()
    mood = await db.get_user_mood(user_id)
    return {"mood": mood}


@router.put("/settings/mood")
async def set_mood(body: MoodIn, user_id: str = "default"):
    if body.mood not in ("serious", "friendly", "normal"):
        return {"error": "mood must be serious, friendly, or normal"}
    db = get_db()
    await db.connect()
    await db.set_user_mood(user_id, body.mood)
    return {"mood": body.mood}


@router.get("/status")
@router.get("/api/status")
async def get_status(user_id: str = "default"):
    """Full status: which APIs have keys, which integrations are configured, which skills are enabled and available."""
    db = get_db()
    await db.connect()
    s = get_settings()
    api_status = await db.get_api_keys_status()
    ollama_ok = await _ollama_reachable()
    whatsapp = await get_whatsapp_bridge_status(s.asta_whatsapp_bridge_url)
    from app.memory_health import get_memory_health
    from app.security_audit import collect_security_warnings
    memory = await get_memory_health()
    security = await collect_security_warnings(db, user_id=user_id)
    thinking_level = await db.get_user_thinking_level(user_id)
    reasoning_mode = await db.get_user_reasoning_mode(user_id)
    final_mode = await db.get_user_final_mode(user_id)
    apis = {
        "groq": api_status.get("groq_api_key", False),
        "gemini": api_status.get("gemini_api_key", False) or api_status.get("google_ai_key", False),
        "claude": api_status.get("anthropic_api_key", False),
        "openai": api_status.get("openai_api_key", False),
        "openrouter": api_status.get("openrouter_api_key", False),
        "ollama": ollama_ok,
    }
    integrations = {
        "telegram": bool(api_status.get("telegram_bot_token") or s.telegram_bot_token),
        # Single-user semantics: integration is "on" only when linked and connected.
        "whatsapp": bool(whatsapp.get("connected")),
    }
    toggles = await db.get_all_skill_toggles(user_id)
    files_avail = bool(s.asta_allowed_paths and s.asta_allowed_paths.strip()) or bool(s.workspace_path)
    try:
        files_avail = files_avail or bool(await db.get_allowed_paths(user_id))
    except Exception:
        pass
    skills_available = {
        "files": files_avail,
        "drive": False,  # OAuth not wired yet; stub only
        "rag": ollama_ok,
        "time": True,
        "weather": True,
        "google_search": True,
        "lyrics": True,
        "spotify": await _spotify_configured(db),
        "reminders": True,
        "learn": True,
        "audio_notes": True,
        "self_awareness": True,
        "silly_gif": api_status.get("giphy_api_key", False),
        "server_status": True,
        # CLI-based skills: available if binary is found
        "google_workspace": bool(__import__('shutil').which('gog') or __import__('os').path.isfile('/opt/homebrew/bin/gog')),
        "github": bool(__import__('shutil').which('gh') or __import__('os').path.isfile('/opt/homebrew/bin/gh')),
        "vercel": bool(__import__('shutil').which('vercel') or __import__('os').path.isfile('/usr/local/bin/vercel')),
    }
    skills = []
    for sk in _get_all_skill_defs():
        sid = sk["id"]
        enabled = toggles.get(sid, True)
        available = skills_available.get(sid, True)
        skills.append({
            "id": sid,
            "name": sk["name"],
            "description": sk["description"],
            "enabled": enabled,
            "available": available,
        })
    # Read version
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent.parent
        with open(root / "VERSION", "r") as f:
            version = f.read().strip()
    except Exception:
        version = "0.0.0"

    return {
        "apis": apis,
        "integrations": integrations,
        "memory": memory,
        "security": security,
        "thinking": {"level": thinking_level},
        "reasoning": {"mode": reasoning_mode},
        "final": {"mode": final_mode},
        "channels": {
            "telegram": {
                "configured": bool(api_status.get("telegram_bot_token") or s.telegram_bot_token),
            },
            "whatsapp": whatsapp,
        },
        "skills": skills,
        "app": s.app_name,
        "version": version,
    }


@router.get("/settings/memory-health")
@router.get("/api/settings/memory-health")
async def memory_health_endpoint(force: bool = False):
    """Doctor-style memory diagnostics (no model call)."""
    from app.memory_health import get_memory_health

    return await get_memory_health(force=force)


@router.get("/settings/security-audit")
@router.get("/api/settings/security-audit")
async def security_audit_endpoint(user_id: str = "default"):
    """Return lightweight security findings for risky runtime configuration."""
    from app.security_audit import collect_security_warnings

    db = get_db()
    await db.connect()
    return await collect_security_warnings(db, user_id=user_id)


@router.get("/settings/keys")
async def get_api_keys_status():
    """Which API keys are set (no values returned). Frontend uses this to show 'Set' / 'Not set'."""
    db = get_db()
    await db.connect()
    status = await db.get_api_keys_status()
    return {name: status.get(name, False) for name in ALLOWED_API_KEY_NAMES}


class ApiKeysIn(BaseModel):
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    google_ai_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    telegram_bot_token: str | None = None
    giphy_api_key: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    notion_api_key: str | None = None


@router.put("/settings/keys")
async def set_api_keys(body: ApiKeysIn):
    """Store API keys from the frontend. Stored in DB (backend/asta.db); never committed to git."""
    db = get_db()
    await db.connect()
    for name in ALLOWED_API_KEY_NAMES:
        val = getattr(body, name, None)
        if val is not None:
            await db.set_stored_api_key(name, val)
    return {"ok": True}


@router.post("/settings/whatsapp/logout")
@router.post("/api/settings/whatsapp/logout")
async def whatsapp_logout():
    """Logout WhatsApp session (clear auth)."""
    s = get_settings()
    url = s.asta_whatsapp_bridge_url
    if not url:
        return {"ok": False, "error": "WhatsApp bridge not configured"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{url.rstrip('/')}/logout")
            if r.status_code == 200:
                return {"ok": True}
            return {"ok": False, "error": f"Bridge error: {r.text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class WhatsAppOwnerIn(BaseModel):
    number: str


class WhatsAppPolicyIn(BaseModel):
    allowed_numbers: str = ""
    self_chat_only: bool = False
    owner_number: str | None = None


@router.post("/settings/whatsapp/owner")
@router.post("/api/settings/whatsapp/owner")
async def set_whatsapp_owner(body: WhatsAppOwnerIn):
    """Set the auto-detected WhatsApp owner number."""
    db = get_db()
    await db.connect()
    # Normalize: remove non-digits just in case, or trust the bridge
    num = "".join(filter(str.isdigit, body.number))
    await db.set_system_config("whatsapp_owner", num)
    return {"ok": True, "number": num}


@router.get("/settings/whatsapp/policy")
@router.get("/api/settings/whatsapp/policy")
async def get_whatsapp_policy():
    """Return WhatsApp sender policy controls for UI."""
    s = get_settings()
    db = get_db()
    await db.connect()
    owner = (await db.get_system_config("whatsapp_owner")) or ""
    return {
        "allowed_numbers": sorted(s.whatsapp_whitelist),
        "self_chat_only": bool(s.asta_whatsapp_self_chat_only),
        "owner_number": owner,
    }


@router.put("/settings/whatsapp/policy")
@router.put("/api/settings/whatsapp/policy")
async def set_whatsapp_policy(body: WhatsAppPolicyIn):
    """Update WhatsApp sender policy controls."""
    # Normalize comma/newline separated numbers into digits-only CSV.
    parts = re.split(r"[\s,]+", body.allowed_numbers or "")
    nums = sorted({"".join(ch for ch in p if ch.isdigit()) for p in parts if p.strip()})
    set_env_value("ASTA_WHATSAPP_ALLOWED_NUMBERS", ",".join(nums), allow_empty=True)
    set_env_value("ASTA_WHATSAPP_SELF_CHAT_ONLY", "1" if body.self_chat_only else "0")

    owner = "".join(ch for ch in (body.owner_number or "") if ch.isdigit())
    db = get_db()
    await db.connect()
    if owner:
        await db.set_system_config("whatsapp_owner", owner)
    return {
        "ok": True,
        "allowed_numbers": nums,
        "self_chat_only": bool(body.self_chat_only),
        "owner_number": owner or ((await db.get_system_config("whatsapp_owner")) or ""),
    }


@router.get("/settings/test-key")
@router.get("/api/settings/test-key")
async def test_api_key(provider: str = "groq", user_id: str = "default"):
    """Test a provider's API key with a minimal request. Returns the real error if it fails."""
    from app.keys import get_api_key
    db = get_db()
    await db.connect()

    if provider == "spotify":
        cid = (await get_api_key("spotify_client_id")) or ""
        secret = (await get_api_key("spotify_client_secret")) or ""
        cid, secret = cid.strip(), secret.strip()
        if not cid or not secret:
            return {"ok": False, "error": "Spotify Client ID and Secret not set. Add them in Settings → Spotify and save first."}
        try:
            from app.spotify_client import get_spotify_token
            token = await get_spotify_token(cid, secret)
            if token:
                return {"ok": True, "message": "Spotify credentials work. You can search songs; connect your account for playback."}
            return {"ok": False, "error": "Spotify rejected the credentials (invalid or expired). Check Client ID and Secret in the Developer Dashboard."}
        except Exception as e:
            return {"ok": False, "error": (str(e).strip() or repr(e))[:500]}

    if provider == "groq":
        key = await get_api_key("groq_api_key")
        if not key:
            return {"ok": False, "error": "No Groq API key set. Add one in Settings and save first."}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
            r = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=10,
            )
            if r.choices and r.choices[0].message.content:
                return {"ok": True, "message": "Groq key works."}
            return {"ok": True}
        except Exception as e:
            msg = str(e).strip() or repr(e)
            return {"ok": False, "error": msg[:500]}

    if provider == "openai":
        key = await get_api_key("openai_api_key")
        if not key:
            return {"ok": False, "error": "No OpenAI API key set. Add one in Settings and save first."}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key)
            r = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=10,
            )
            if r.choices and r.choices[0].message.content:
                return {"ok": True, "message": "OpenAI key works."}
            return {"ok": True}
        except Exception as e:
            msg = str(e).strip() or repr(e)
            return {"ok": False, "error": msg[:500]}

    if provider == "openrouter":
        key = await get_api_key("openrouter_api_key")
        if not key:
            return {"ok": False, "error": "No OpenRouter API key set. Add one in Settings and save first. Get a key at https://openrouter.ai/keys"}
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
            r = await client.chat.completions.create(
                model=OPENROUTER_RECOMMENDED_MODELS[-1],
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=10,
            )
            if r.choices and r.choices[0].message.content:
                await db.clear_provider_auto_disabled(user_id, "openrouter")
                return {"ok": True, "message": "OpenRouter key works."}
            return {"ok": True}
        except Exception as e:
            msg = str(e).strip() or repr(e)
            return {"ok": False, "error": msg[:500]}

    if provider == "claude":
        key = await get_api_key("anthropic_api_key")
        if not key:
            return {"ok": False, "error": "No Anthropic API key set. Add one in Settings and save first."}
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=key)
            r = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=12,
                messages=[{"role": "user", "content": "Reply with OK"}],
            )
            text = ""
            for block in (getattr(r, "content", None) or []):
                if getattr(block, "type", "") == "text":
                    text = (getattr(block, "text", "") or "").strip()
                    if text:
                        break
            if text:
                await db.clear_provider_auto_disabled(user_id, "claude")
                return {"ok": True, "message": "Claude key works."}
            return {"ok": True}
        except Exception as e:
            msg = str(e).strip() or repr(e)
            return {"ok": False, "error": msg[:500]}

    if provider == "ollama":
        ok = await _ollama_reachable()
        if not ok:
            return {"ok": False, "error": "Ollama is not reachable. Start Ollama and verify OLLAMA_BASE_URL."}
        await db.clear_provider_auto_disabled(user_id, "ollama")
        return {"ok": True, "message": "Ollama is reachable."}

    return {"ok": False, "error": f"Test not implemented for {provider}. Use claude, ollama, groq, openai, openrouter, or spotify."}


class SkillToggleIn(BaseModel):
    skill_id: str
    enabled: bool


def _get_all_skill_defs():
    """Built-in + OpenClaw-style workspace skills for API (id, name, description, install_cmd, install_label, required_bins)."""
    from app.workspace import discover_workspace_skills
    out = []
    for s in SKILLS:
        out.append({**s, "source": "builtin", "install_cmd": None, "install_label": None, "required_bins": []})
    for r in discover_workspace_skills():
        out.append({
            "id": r.name,
            "name": r.name.replace("-", " ").replace("_", " ").title(),
            "description": r.description or "Workspace skill (SKILL.md).",
            "source": "workspace",
            "install_cmd": getattr(r, "install_cmd", None),
            "install_label": getattr(r, "install_label", None),
            "required_bins": list(getattr(r, "required_bins", ())),
            "supported_os": list(getattr(r, "supported_os", ())),
        })
    deduped: list[dict] = []
    seen_ids: set[str] = set()
    for sk in out:
        sid = str(sk.get("id") or "").strip().lower()
        if not sid:
            continue
        if sid in seen_ids:
            logger.warning("Duplicate skill id '%s' in skill catalog; keeping first entry only.", sid)
            continue
        seen_ids.add(sid)
        deduped.append(sk)
    return deduped


@router.get("/settings/skills")
@router.get("/api/settings/skills")
async def get_skills(user_id: str = "default"):
    """List skills with enabled state (and available from status). Includes install_cmd, install_label, required_bins for skills that need them."""
    db = get_db()
    await db.connect()
    s = get_settings()
    toggles = await db.get_all_skill_toggles(user_id)
    api_status = await db.get_api_keys_status()
    ollama_ok = await _ollama_reachable()
    files_available = bool(s.asta_allowed_paths and s.asta_allowed_paths.strip()) or bool(s.workspace_path)
    try:
        files_available = files_available or bool(await db.get_allowed_paths(user_id))
    except Exception:
        pass
    effective_exec_bins = await get_effective_exec_bins(db, user_id)
    skills_available = {
        "files": files_available,
        "drive": False,  # OAuth not wired yet
        "rag": ollama_ok,
        "time": True,
        "weather": True,
        "google_search": True,
        "lyrics": True,
        "spotify": await _spotify_configured(db),
        "reminders": True,
        "learn": True,
        "audio_notes": True,
        "self_awareness": True,
        "silly_gif": api_status.get("giphy_api_key", False),
        "server_status": True,
    }
    action_hints = {
        "files": "Configure paths",
        "drive": "Connect",
        "rag": "Set up Ollama",
        "spotify": "Connect",
        "silly_gif": "Set API key",
        "google_workspace": "Configure in Google tab (requires gog CLI)",
    }
    all_skill_defs = _get_all_skill_defs()
    from app.workspace import get_host_os_tag
    host_os = get_host_os_tag()
    out = []
    for sk in all_skill_defs:
        sid = sk["id"]
        available = skills_available.get(sid, True)
        supported_os = [str(x).lower() for x in (sk.get("supported_os") or []) if str(x).strip()]
        os_ok = (not supported_os) or (host_os in supported_os)
        if not os_ok:
            available = False
        required_bins = sk.get("required_bins") or []
        if required_bins:
            # Exec-based skill: available if all bins are in allowlist and findable (PATH or common paths)
            on_path = all(resolve_executable(b) for b in required_bins)
            in_allowlist = all(b.lower() in effective_exec_bins for b in required_bins)
            available = available and on_path and in_allowlist
        action_hint = action_hints.get(sid) if not available else None
        if not available and not os_ok:
            action_hint = f"Only on {', '.join(supported_os)}"
        if required_bins and not available and not action_hint:
            action_hint = "Install & enable exec"
        out.append({
            **sk,
            "enabled": toggles.get(sid, True),
            "available": available,
            "action_hint": action_hint,
        })
    return {"skills": out}


@router.put("/settings/skills")
@router.put("/api/settings/skills")
async def set_skill_toggle(body: SkillToggleIn, user_id: str = "default"):
    """Enable or disable a skill for the AI (built-in or workspace)."""
    all_defs = _get_all_skill_defs()
    valid_ids = {s["id"] for s in all_defs}
    if body.skill_id not in valid_ids:
        return {"error": f"Unknown skill_id: {body.skill_id}"}
    db = get_db()
    await db.connect()
    await db.set_skill_enabled(user_id, body.skill_id, body.enabled)
    # Keep exec allowlist aligned with enabled workspace skills:
    # preserve manually configured non-workspace bins, but sync workspace bins dynamically.
    from app.exec_tool import SYSTEM_CONFIG_EXEC_BINS_KEY
    from app.workspace import discover_workspace_skills

    workspace_skills = discover_workspace_skills()
    all_workspace_bins: set[str] = set()
    enabled_workspace_bins: set[str] = set()
    for ws in workspace_skills:
        ws_bins = {b.strip().lower() for b in (ws.required_bins or ()) if b.strip()}
        if not ws_bins:
            continue
        all_workspace_bins |= ws_bins
        if await db.get_skill_enabled(user_id, ws.name):
            enabled_workspace_bins |= ws_bins

    extra = (await db.get_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY)) or ""
    existing = {b.strip().lower() for b in extra.split(",") if b.strip()}
    next_bins = {b for b in existing if b not in all_workspace_bins}
    next_bins |= enabled_workspace_bins
    await db.set_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY, ",".join(sorted(next_bins)))
    return {"skill_id": body.skill_id, "enabled": body.enabled}


@router.post("/settings/skills/upload")
@router.post("/api/skills/upload")
async def upload_skill_zip(file: UploadFile = File(...)):
    """Upload a zip file containing an OpenClaw-style skill (folder with SKILL.md). Extracts to workspace/skills/<skill_id>/."""
    from app.workspace import get_workspace_dir
    root = get_workspace_dir()
    if not root:
        raise HTTPException(400, "Workspace not configured. Create a workspace/ directory or set ASTA_WORKSPACE_DIR.")
    skills_dir = root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload must be a .zip file.")
    try:
        body = await file.read()
        if len(body) > 20 * 1024 * 1024:
            raise HTTPException(400, "Zip file too large (max 20 MB).")
    except Exception as e:
        raise HTTPException(400, f"Failed to read file: {e}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(io.BytesIO(body), "r") as z:
                z.extractall(tmp_path)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid zip file.")
        entries = list(tmp_path.iterdir())
        skill_id = None
        source_dir = None
        if len(entries) == 1 and entries[0].is_dir():
            inner = entries[0]
            if (inner / "SKILL.md").is_file():
                skill_id = re.sub(r"[^a-z0-9_-]", "", inner.name.lower()) or inner.name
                source_dir = inner
        if not source_dir:
            if (tmp_path / "SKILL.md").is_file():
                stem = Path(file.filename).stem
                skill_id = re.sub(r"[^a-z0-9_-]", "", stem.lower()) or stem
                source_dir = tmp_path
        if not skill_id or not source_dir:
            raise HTTPException(
                400,
                "Zip must contain SKILL.md at the root or inside a single top-level folder (OpenClaw style).",
            )
        dest = skills_dir / skill_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source_dir, dest)
    return {"skill_id": skill_id, "ok": True}


def _spotify_redirect_uri(request: Request | None = None) -> str:
    """Redirect URI for Spotify OAuth (used in dashboard and connect URL).

    Spotify no longer accepts http://localhost/... redirect URIs.
    For local development, they recommend using the loopback address:
    http://127.0.0.1:<port>/callback instead.
    """
    base = os.environ.get("ASTA_BASE_URL", "").strip() or (str(request.base_url).rstrip("/") if request else "http://127.0.0.1:8010")
    # For local dev, prefer 127.0.0.1 over localhost so it matches Spotify's rules
    if base.startswith("http://localhost"):
        base = base.replace("http://localhost", "http://127.0.0.1", 1)
    return f"{base}/api/spotify/callback"


@router.get("/spotify/setup")
@router.get("/api/spotify/setup")
async def get_spotify_setup(request: Request):
    """Return instructions and URLs for configuring Spotify (for the Settings UI)."""
    redirect_uri = _spotify_redirect_uri(request)
    steps = [
        "Go to the Spotify Developer Dashboard (link below) and log in with your Spotify account.",
        "Click **Create app**. Fill in name and description (e.g. “Asta”), accept the terms, then Create.",
        "Open your app → **Settings**. Copy **Client ID** and **Client secret** and paste them below.",
        "For playback on your devices: in the app settings under **Redirect URIs**, add: **" + redirect_uri + "** then Save.",
    ]
    base = os.environ.get("ASTA_BASE_URL", "").strip() or str(request.base_url).rstrip("/")
    connect_url = f"{base}/api/spotify/connect?user_id=default"
    return {"dashboard_url": "https://developer.spotify.com/dashboard", "docs_url": "https://developer.spotify.com/documentation/web-api", "steps": steps, "redirect_uri": redirect_uri, "connect_url": connect_url}


@router.get("/notifications")
@router.get("/api/notifications")
async def get_notifications(user_id: str = "default", limit: int = 50):
    """List reminders/notifications for the user (for panel)."""
    db = get_db()
    await db.connect()
    items = await db.get_notifications(user_id, limit=limit)
    return {"notifications": items}


@router.get("/settings/notes")
@router.get("/api/settings/notes")
async def get_workspace_notes(limit: int = 20):
    """List markdown notes from workspace/notes for Dashboard (local notes, not Apple Notes)."""
    lim = max(1, min(int(limit), 100))
    workspace = get_settings().workspace_path
    if not workspace:
        return {"notes": []}

    items: list[dict] = []
    candidates = [workspace / "memos", workspace / "notes", workspace / "workspace" / "notes"]
    for notes_dir in candidates:
        if not notes_dir.exists() or not notes_dir.is_dir():
            continue
        for file_path in notes_dir.rglob("*.md"):
            if not file_path.is_file():
                continue
            try:
                st = file_path.stat()
            except OSError:
                continue
            rel = file_path.relative_to(workspace).as_posix()
            items.append(
                {
                    "name": file_path.name,
                    "path": rel,
                    "size": int(st.st_size),
                    "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    if not items:
        return {"notes": []}
    seen_paths: set[str] = set()
    deduped: list[dict] = []
    for item in sorted(items, key=lambda x: x["modified_at"], reverse=True):
        path = str(item.get("path") or "")
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        deduped.append(item)
    return {"notes": deduped[:lim]}


@router.delete("/notifications/{id}")
@router.delete("/api/notifications/{id}")
async def delete_notification(id: int, user_id: str = "default"):
    """Delete a reminder/notification."""
    from app.db import decode_one_shot_reminder_id
    db = get_db()
    await db.connect()
    # Remove from DB
    deleted = await db.delete_reminder(id, user_id)
    # Also try to remove from scheduler if it's pending
    from app.tasks.scheduler import get_scheduler
    sch = get_scheduler()
    legacy_job_id = f"rem_{id}"
    if sch.get_job(legacy_job_id):
        sch.remove_job(legacy_job_id)
    one_shot_id = decode_one_shot_reminder_id(id)
    if one_shot_id is not None:
        cron_job_id = f"cron_{one_shot_id}"
        if sch.get_job(cron_job_id):
            sch.remove_job(cron_job_id)
    return {"ok": deleted, "id": id}


@router.get("/settings/server-status")
@router.get("/api/settings/server-status")
async def server_status_endpoint():
    """Get system metrics for the dashboard."""
    from app.server_status import get_server_status
    return get_server_status()


@router.get("/api/settings/check-update")
@router.get("/settings/check-update")
async def check_update():
    """Check if a new version is available on GitHub."""
    import subprocess
    from pathlib import Path
    
    root = Path(__file__).resolve().parent.parent.parent.parent
    try:
        # 1. Fetch
        subprocess.run(["git", "fetch", "origin", "main"], cwd=str(root), capture_output=True, timeout=5)
        
        # 2. Get local hash
        local_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True)
        local_hash = local_res.stdout.strip()
        
        # 3. Get remote hash
        remote_res = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(root), capture_output=True, text=True)
        remote_hash = remote_res.stdout.strip()
        
        available = (local_hash != remote_hash) and bool(remote_hash)
        
        return {
            "update_available": available,
            "local": local_hash[:7],
            "remote": remote_hash[:7] if remote_hash else "Unknown"
        }
    except Exception as e:
        return {"update_available": False, "error": str(e)}


@router.post("/api/settings/update")
@router.post("/settings/update")
async def trigger_update():
    """Run ./asta.sh update in the background."""
    import subprocess
    import threading
    import os
    import time
    from pathlib import Path
    
    root = Path(__file__).resolve().parent.parent.parent.parent
    script = root / "asta.sh"

    if not script.exists():
        return {"ok": False, "error": "asta.sh not found"}

    def _do_update():
        time.sleep(1) # wait for response
        subprocess.Popen(
            ["bash", str(script), "update"],
            cwd=str(root),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    threading.Thread(target=_do_update, daemon=True).start()
    return {"ok": True, "message": "Update triggered. System will restart shortly."}


@router.get("/settings/pingram")
@router.get("/api/settings/pingram")
async def get_pingram_settings(user_id: str = "default"):
    """Return Pingram (NotificationAPI) settings."""
    s = get_settings()
    cid = getattr(s, "asta_pingram_client_id", "") or ""
    # Mask client ID to comfort user about "leaking real key"
    masked_cid = cid[:4] + "..." + cid[-4:] if len(cid) > 8 else (cid[:2] + "..." if cid else "")
    is_secret_set = bool(getattr(s, "asta_pingram_client_secret", None))
    api_key = getattr(s, "asta_pingram_api_key", None) or ""
    return {
        "client_id": masked_cid,
        "client_secret": "****" if is_secret_set else "",
        "api_key": "****" if api_key else "",
        "api_key_set": bool(api_key),
        "notification_id": getattr(s, "asta_pingram_notification_id", "cron_alert"),
        "template_id": getattr(s, "asta_pingram_template_id", ""),
        "phone_number": getattr(s, "asta_owner_phone_number", ""),
        "is_secret_set": is_secret_set
    }


@router.post("/settings/pingram")
@router.post("/api/settings/pingram")
async def set_pingram_settings(body: PingramSettingsIn, user_id: str = "default"):
    """Update Pingram (NotificationAPI) settings."""
    from app.config import save_settings_to_env
    
    updates = {}
    if body.client_id is not None:
        updates["ASTA_PINGRAM_CLIENT_ID"] = body.client_id
    if body.client_secret is not None:
        # If it's the masked version, don't update
        if "*" not in body.client_secret:
            updates["ASTA_PINGRAM_CLIENT_SECRET"] = body.client_secret
    if body.notification_id is not None:
        updates["ASTA_PINGRAM_NOTIFICATION_ID"] = body.notification_id
    if body.template_id is not None:
        updates["ASTA_PINGRAM_TEMPLATE_ID"] = body.template_id
    if body.phone_number is not None:
        updates["ASTA_OWNER_PHONE_NUMBER"] = body.phone_number
    if body.api_key is not None:
        if "*" not in (body.api_key or ""):
            updates["ASTA_PINGRAM_API_KEY"] = body.api_key or ""
        # if masked, don't overwrite

    if updates:
        save_settings_to_env(updates)
        s = get_settings()
        if "ASTA_PINGRAM_CLIENT_ID" in updates:
            s.asta_pingram_client_id = updates["ASTA_PINGRAM_CLIENT_ID"]
        if "ASTA_PINGRAM_CLIENT_SECRET" in updates:
            s.asta_pingram_client_secret = updates["ASTA_PINGRAM_CLIENT_SECRET"]
        if "ASTA_PINGRAM_API_KEY" in updates:
            s.asta_pingram_api_key = updates["ASTA_PINGRAM_API_KEY"]
        if "ASTA_PINGRAM_NOTIFICATION_ID" in updates:
            s.asta_pingram_notification_id = updates["ASTA_PINGRAM_NOTIFICATION_ID"]
        if "ASTA_PINGRAM_TEMPLATE_ID" in updates:
            s.asta_pingram_template_id = updates["ASTA_PINGRAM_TEMPLATE_ID"]
        if "ASTA_OWNER_PHONE_NUMBER" in updates:
            s.asta_owner_phone_number = updates["ASTA_OWNER_PHONE_NUMBER"]

    return {"ok": True}


@router.post("/settings/pingram/test-call")
@router.post("/api/settings/pingram/test-call")
async def test_pingram_call(body: PingramTestCallIn):
    """Trigger a test Pingram voice call. Uses the same code path as cron/reminders (trigger_pingram_voice_call)."""
    clean_number = (body.test_number or "").strip()
    if not clean_number:
        return {"ok": False, "error": "Test number is required."}
    if not clean_number.startswith("+"):
        clean_number = "+" + clean_number

    # Use stored settings only (same as cron). Save your Client ID, API Key or Secret, Notification ID, Template ID first.
    from app.reminders import trigger_pingram_voice_call
    test_message = "This is a test call from Asta. Your Pingram integration is working correctly."
    ok = await trigger_pingram_voice_call(clean_number, test_message, template_id=None)
    if ok:
        return {"ok": True}
    return {"ok": False, "error": "Voice call failed. Check Settings are saved (Client ID, API Key or Client Secret, Notification ID, Template ID) and see backend logs or NotificationAPI dashboard for details."}


@router.get("/settings/telegram/username")
@router.get("/api/settings/telegram/username")
async def get_telegram_username():
    """Return the configured Telegram username for voice calls."""
    s = get_settings()
    return {"username": getattr(s, "asta_telegram_username", None)}


@router.post("/settings/telegram/username")
@router.post("/api/settings/telegram/username")
async def set_telegram_username(body: TelegramUsernameIn):
    """Update the Telegram username for voice calls."""
    username = (body.username or "").strip()
    if username and not username.startswith("@"):
        username = "@" + username
    
    set_env_value("ASTA_TELEGRAM_USERNAME", username, allow_empty=True)
    return {"ok": True, "username": username}
