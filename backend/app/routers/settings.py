"""User settings (mood, API keys), status, skills, and notifications list."""
import io
import os
import re
import shutil
import tempfile
import zipfile
import httpx
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.db import get_db
from app.exec_tool import get_effective_exec_bins, resolve_executable

router = APIRouter()


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
    """Return list of Ollama model names (e.g. ['llama3.2', 'mistral']). Empty if Ollama unreachable."""
    base = (get_settings().ollama_base_url or "").strip() or "http://localhost:11434"
    base = base.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/api/tags")
            if r.status_code != 200:
                return []
            data = r.json()
            models = data.get("models") if isinstance(data, dict) else []
            if not isinstance(models, list):
                return []
            names = []
            for m in models:
                if isinstance(m, dict) and m.get("name"):
                    names.append(str(m["name"]).strip())
                elif isinstance(m, dict) and m.get("model"):
                    names.append(str(m["model"]).strip())
            return sorted(names)
    except Exception:
        return []


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
    {"id": "learn", "name": "Learn about topic", "description": "Say 'learn about X for 30 min' to have Asta learn and store a topic in RAG."},
    {"id": "time", "name": "Time", "description": "Current time (12h AM/PM). Location is used for your timezone when set."},
    {"id": "weather", "name": "Weather", "description": "Current weather and forecast (today, tomorrow). Set your location once so Asta can answer."},
    {"id": "google_search", "name": "Google search", "description": "Search the web for current information"},
    {"id": "lyrics", "name": "Lyrics", "description": "Find song lyrics (free, no key). Ask e.g. 'lyrics for Bohemian Rhapsody'"},
    {"id": "spotify", "name": "Spotify", "description": "Search songs on Spotify. Set Client ID and Secret in Settings → Spotify (or in backend/.env). Playback on your devices (with device picker) coming soon."},
    {"id": "reminders", "name": "Reminders", "description": "Wake me up or remind me at a time. Set your location so times are in your timezone. E.g. 'Wake me up tomorrow at 7am' or 'Remind me at 6pm to call mom'."},
    {"id": "audio_notes", "name": "Audio notes", "description": "Upload audio (meetings, calls, voice memos); Asta transcribes and formats as meeting notes, action items, or conversation summary. No API key for transcription (runs locally)."},
    {"id": "silly_gif", "name": "Silly GIF", "description": "Occasionally replies with a relevant GIF in friendly chats. Requires Giphy API key."},
    {"id": "self_awareness", "name": "Self Awareness", "description": "When asked about Asta (features, docs, how to use): injects README + docs/*.md and workspace context so the model answers from real docs. User context comes from workspace/USER.md."},
    {"id": "server_status", "name": "Server Status", "description": "Monitor system metrics like CPU, RAM, Disk and Uptime. Ask 'server status' or '/status'."},
]

ALLOWED_API_KEY_NAMES = frozenset({
    "groq_api_key", "gemini_api_key", "google_ai_key",
    "anthropic_api_key", "openai_api_key", "openrouter_api_key",
    "telegram_bot_token", "giphy_api_key",
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


class FallbackProvidersIn(BaseModel):
    providers: str  # comma-separated, e.g. "google,openai" or "" to disable


@router.get("/settings/fallback")
@router.get("/api/settings/fallback")
async def get_fallback_providers(user_id: str = "default"):
    """Get configured fallback providers (comma-separated). Empty = auto-detect from key availability."""
    db = get_db()
    await db.connect()
    providers = await db.get_user_fallback_providers(user_id)
    return {"providers": providers}


@router.put("/settings/fallback")
@router.put("/api/settings/fallback")
async def set_fallback_providers(body: FallbackProvidersIn, user_id: str = "default"):
    """Set fallback provider order (comma-separated, e.g. 'google,openai'). Empty = auto-detect."""
    valid = {"groq", "google", "claude", "ollama", "openai", "openrouter"}
    if body.providers.strip():
        names = [n.strip() for n in body.providers.split(",") if n.strip()]
        bad = [n for n in names if n not in valid]
        if bad:
            return {"error": f"Unknown provider(s): {', '.join(bad)}. Valid: {', '.join(sorted(valid))}"}
    db = get_db()
    await db.connect()
    await db.set_user_fallback_providers(user_id, body.providers.strip())
    return {"providers": body.providers.strip()}


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


@router.get("/settings/available-models")
@router.get("/api/settings/available-models")
async def get_available_models():
    """List available models per provider (e.g. Ollama local models). For dashboard Brain section."""
    ollama_models = await _ollama_list_models()
    return {
        "ollama": ollama_models,
        # Other providers use API keys; we don't list their model catalogs here
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
        "skills": skills,
        "app": s.app_name,
        "version": version,
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
    giphy_api_key: str | None = None
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


def _get_all_skill_defs():
    """Built-in + OpenClaw-style workspace skills for API (id, name, description, install_cmd, install_label, required_bins)."""
    from app.workspace import discover_workspace_skills
    out = []
    for s in SKILLS:
        out.append({**s, "install_cmd": None, "install_label": None, "required_bins": []})
    for r in discover_workspace_skills():
        out.append({
            "id": r.name,
            "name": r.name.replace("-", " ").replace("_", " ").title(),
            "description": r.description or "Workspace skill (SKILL.md).",
            "install_cmd": getattr(r, "install_cmd", None),
            "install_label": getattr(r, "install_label", None),
            "required_bins": list(getattr(r, "required_bins", ())),
        })
    return out


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
    effective_exec_bins = await get_effective_exec_bins(db)
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
    }
    all_skill_defs = _get_all_skill_defs()
    out = []
    for sk in all_skill_defs:
        sid = sk["id"]
        available = skills_available.get(sid, True)
        required_bins = sk.get("required_bins") or []
        if required_bins:
            # Exec-based skill: available if all bins are in allowlist and findable (PATH or common paths)
            on_path = all(resolve_executable(b) for b in required_bins)
            in_allowlist = all(b.lower() in effective_exec_bins for b in required_bins)
            available = on_path and in_allowlist
        action_hint = action_hints.get(sid) if not available else None
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
    """Enable or disable a skill for the AI (built-in or workspace). When enabling a skill with required_bins (e.g. apple-notes), auto-adds those bins to exec allowlist."""
    all_defs = _get_all_skill_defs()
    valid_ids = {s["id"] for s in all_defs}
    if body.skill_id not in valid_ids:
        return {"error": f"Unknown skill_id: {body.skill_id}"}
    db = get_db()
    await db.connect()
    await db.set_skill_enabled(user_id, body.skill_id, body.enabled)
    # When enabling a skill that requires exec bins (e.g. memo for apple-notes), add them to DB allowlist
    if body.enabled:
        skill_def = next((s for s in all_defs if s["id"] == body.skill_id), None)
        required_bins = (skill_def or {}).get("required_bins") or []
        if required_bins:
            from app.exec_tool import SYSTEM_CONFIG_EXEC_BINS_KEY
            extra = (await db.get_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY)) or ""
            existing = {b.strip().lower() for b in extra.split(",") if b.strip()}
            for b in required_bins:
                existing.add(b.strip().lower())
            await db.set_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY, ",".join(sorted(existing)))
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
    return {"ok": true, "message": "Update triggered. System will restart shortly."}
