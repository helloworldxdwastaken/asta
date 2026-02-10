"""User settings (mood, API keys), status, skills, and notifications list."""
import os
import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_settings
from app.db import get_db

router = APIRouter()


async def _ollama_reachable() -> bool:
    """Return True only if Ollama is running and responding at the configured base URL."""
    base = get_settings().ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{base}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


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
    {"id": "calendar", "name": "Google Calendar", "description": "Calendar events (coming soon)"},
    {"id": "rag", "name": "Learning (RAG)", "description": "Learned knowledge and documents"},
    {"id": "time", "name": "Time", "description": "Current time (12h AM/PM). Location is used for your timezone when set."},
    {"id": "weather", "name": "Weather", "description": "Current weather and forecast (today, tomorrow). Set your location once so Asta can answer."},
    {"id": "google_search", "name": "Google search", "description": "Search the web for current information"},
    {"id": "lyrics", "name": "Lyrics", "description": "Find song lyrics (free, no key). Ask e.g. 'lyrics for Bohemian Rhapsody'"},
    {"id": "spotify", "name": "Spotify", "description": "Search songs on Spotify. Set Client ID and Secret in Settings → Spotify (or in backend/.env). Playback on your devices (with device picker) coming soon."},
    {"id": "reminders", "name": "Reminders", "description": "Wake me up or remind me at a time. Set your location so times are in your timezone. E.g. 'Wake me up tomorrow at 7am' or 'Remind me at 6pm to call mom'."},
    {"id": "audio_notes", "name": "Audio notes", "description": "Upload audio (meetings, calls, voice memos); Asta transcribes and formats as meeting notes, action items, or conversation summary. No API key for transcription (runs locally)."},
]

ALLOWED_API_KEY_NAMES = frozenset({
    "groq_api_key", "gemini_api_key", "google_ai_key",
    "anthropic_api_key", "openai_api_key", "openrouter_api_key",
    "telegram_bot_token",
    "spotify_client_id", "spotify_client_secret",
})


class MoodIn(BaseModel):
    mood: str  # serious | friendly | normal


class DefaultAiIn(BaseModel):
    provider: str  # groq | google | claude | ollama | openrouter


@router.get("/settings/default-ai")
async def get_default_ai(user_id: str = "default"):
    db = get_db()
    await db.connect()
    provider = await db.get_user_default_ai(user_id)
    return {"provider": provider}


@router.put("/settings/default-ai")
async def set_default_ai(body: DefaultAiIn, user_id: str = "default"):
    if body.provider not in ("groq", "google", "claude", "ollama", "openai", "openrouter"):
        return {"error": "provider must be groq, google, claude, ollama, openai, or openrouter"}
    db = get_db()
    await db.connect()
    await db.set_user_default_ai(user_id, body.provider)
    return {"provider": body.provider}


# Default models per provider (used when user has not set a custom model)
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-1.5-flash",
    "claude": "claude-3-5-sonnet-20241022",
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
    "openrouter": "arcee-ai/trinity-large-preview:free",
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


class ModelIn(BaseModel):
    provider: str
    model: str  # empty string = use provider default


@router.put("/settings/models")
@router.put("/api/settings/models")
async def set_model(body: ModelIn, user_id: str = "default"):
    """Set which model to use for a provider. Leave model empty to use provider default."""
    if body.provider not in ("groq", "google", "claude", "ollama", "openai", "openrouter"):
        return {"error": "provider must be groq, google, claude, ollama, openai, or openrouter"}
    db = get_db()
    await db.connect()
    await db.set_user_provider_model(user_id, body.provider, body.model.strip())
    return {"provider": body.provider, "model": body.model.strip() or "(default)"}


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
        "whatsapp": bool(s.asta_whatsapp_bridge_url),
    }
    toggles = await db.get_all_skill_toggles(user_id)
    skills_available = {
        "files": bool(s.asta_allowed_paths and s.asta_allowed_paths.strip()),
        "drive": True,  # stub; real check would be OAuth
        "calendar": False,
        "rag": True,
        "time": True,
        "weather": True,
        "google_search": True,
        "lyrics": True,
        "spotify": await _spotify_configured(db),
        "audio_notes": True,
    }
    skills = []
    for sk in SKILLS:
        sid = sk["id"]
        enabled = toggles.get(sid, True)
        available = skills_available.get(sid, False)
        skills.append({
            "id": sid,
            "name": sk["name"],
            "description": sk["description"],
            "enabled": enabled,
            "available": available,
        })
    return {
        "apis": apis,
        "integrations": integrations,
        "skills": skills,
        "app": s.app_name,
        "version": "0.1.0",
    }


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
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None


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


@router.get("/settings/test-key")
@router.get("/api/settings/test-key")
async def test_api_key(provider: str = "groq"):
    """Test a provider's API key with a minimal request. Returns the real error if it fails."""
    from app.keys import get_api_key

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
                model="arcee-ai/trinity-large-preview:free",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=10,
            )
            if r.choices and r.choices[0].message.content:
                return {"ok": True, "message": "OpenRouter key works."}
            return {"ok": True}
        except Exception as e:
            msg = str(e).strip() or repr(e)
            return {"ok": False, "error": msg[:500]}

    return {"ok": False, "error": f"Test not implemented for {provider}. Use groq, openai, openrouter, or spotify."}


class SkillToggleIn(BaseModel):
    skill_id: str
    enabled: bool


@router.get("/settings/skills")
@router.get("/api/settings/skills")
async def get_skills(user_id: str = "default"):
    """List skills with enabled state (and available from status)."""
    db = get_db()
    await db.connect()
    s = get_settings()
    toggles = await db.get_all_skill_toggles(user_id)
    skills_available = {
        "files": bool(s.asta_allowed_paths and s.asta_allowed_paths.strip()),
        "drive": True,
        "calendar": False,
        "rag": True,
        "time": True,
        "weather": True,
        "google_search": True,
        "lyrics": True,
        "spotify": await _spotify_configured(db),
        "audio_notes": True,
    }
    out = []
    for sk in SKILLS:
        sid = sk["id"]
        out.append({
            **sk,
            "enabled": toggles.get(sid, True),
            "available": skills_available.get(sid, False),
        })
    return {"skills": out}


@router.put("/settings/skills")
@router.put("/api/settings/skills")
async def set_skill_toggle(body: SkillToggleIn, user_id: str = "default"):
    """Enable or disable a skill for the AI."""
    valid_ids = {s["id"] for s in SKILLS}
    if body.skill_id not in valid_ids:
        return {"error": f"Unknown skill_id: {body.skill_id}"}
    db = get_db()
    await db.connect()
    await db.set_skill_enabled(user_id, body.skill_id, body.enabled)
    return {"skill_id": body.skill_id, "enabled": body.enabled}


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


@router.delete("/notifications/{id}")
@router.delete("/api/notifications/{id}")
async def delete_notification(id: int, user_id: str = "default"):
    """Delete a reminder/notification."""
    db = get_db()
    await db.connect()
    # Remove from DB
    deleted = await db.delete_reminder(id)
    # Also try to remove from scheduler if it's pending
    from app.tasks.scheduler import get_scheduler
    sch = get_scheduler()
    job_id = f"rem_{id}"
    if sch.get_job(job_id):
        sch.remove_job(job_id)
    return {"ok": deleted, "id": id}
