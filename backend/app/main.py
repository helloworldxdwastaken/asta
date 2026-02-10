"""Asta API — control plane for AI, files, channels, and learning."""
import logging
import os
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_db
from app.routers import chat, files, drive, rag, providers, tasks, settings as settings_router, spotify as spotify_router, audio as audio_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: DB + reload reminders + Telegram bot in same event loop. Shutdown: stop bot cleanly."""
    await get_db().connect()
    try:
        from app.reminders import reload_pending_reminders
        await reload_pending_reminders()
    except Exception as e:
        logger.exception("Failed to reload pending reminders: %s", e)
    # Telegram bot: do NOT block API startup if Telegram is unreachable or misconfigured.
    token = await get_db().get_stored_api_key("telegram_bot_token") or get_settings().telegram_bot_token
    app.state.telegram_app = None
    if token:
        try:
            from app.channels.telegram_bot import build_telegram_app, start_telegram_bot_in_loop
            tg_app = build_telegram_app(token)
            await start_telegram_bot_in_loop(tg_app)
            app.state.telegram_app = tg_app
        except Exception as e:
            logger.exception("Failed to start Telegram bot; continuing without it: %s", e)
    yield
    # Shutdown: stop Telegram bot
    if getattr(app.state, "telegram_app", None):
        tg = app.state.telegram_app
        try:
            if tg.updater and tg.updater.running:
                await tg.updater.stop()
            if tg.running:
                await tg.stop()
            await tg.shutdown()
        except Exception as e:
            logger.exception("Telegram bot shutdown: %s", e)


# Read version from file (root/VERSION)
try:
    with open(Path(__file__).resolve().parent.parent.parent / "VERSION", "r") as f:
        VERSION = f.read().strip()
except Exception:
    VERSION = "0.0.0"

app = FastAPI(
    title="Asta",
    description="Asta: personal control plane — AI, WhatsApp, Telegram, files, Drive, RAG.",
    version=VERSION,
    lifespan=lifespan,
)

settings = get_settings()

_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [o.strip() for o in (settings.asta_cors_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(drive.router, prefix="/api", tags=["drive"])
app.include_router(rag.router, prefix="/api", tags=["rag"])
app.include_router(providers.router, prefix="/api", tags=["providers"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(spotify_router.router, prefix="/api", tags=["spotify"])
app.include_router(audio_router.router, prefix="/api", tags=["audio"])
# Also mount at root so /settings/keys works if proxy strips /api
app.include_router(settings_router.router, tags=["settings"])


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": VERSION,
        "docs": "/docs",
        "status": "ok",
    }


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": VERSION}


@app.get("/api/restart")
def restart_get():
    """Allow checking that the route exists; use POST to actually restart."""
    return {"detail": "Use POST to restart the backend.", "method": "POST"}


@app.post("/api/restart")
def restart_backend():
    """Restart backend via asta.sh so port is freed and a fresh process starts (e.g. after changing Telegram token)."""

    def _restart_via_script():
        time.sleep(2.5)  # give time for HTTP response to be sent and flushed
        project_root = Path(__file__).resolve().parent.parent.parent
        script = project_root / "asta.sh"
        if script.is_file():
            try:
                subprocess.Popen(
                    ["bash", str(script), "restart"],
                    cwd=str(project_root),
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                logger.exception("Failed to run asta.sh restart: %s", e)
        logger.warning("Restart requested: exiting process now.")
        os._exit(0)

    threading.Thread(target=_restart_via_script, daemon=True).start()
    return {"message": "Restarting backend…"}


@app.get("/api/whatsapp/qr")
async def whatsapp_qr():
    """Proxy to WhatsApp bridge: return QR code (data URL) or connected status for the panel."""
    import httpx
    url = settings.asta_whatsapp_bridge_url
    if not url:
        return {"connected": False, "qr": None, "error": "Bridge URL not set. Add ASTA_WHATSAPP_BRIDGE_URL in backend/.env (e.g. http://localhost:3001)."}
    base = url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/qr")
            return r.json()
    except Exception as e:
        return {"connected": False, "qr": None, "error": f"Cannot reach bridge at {base}. Start it with: cd services/whatsapp && npm run start"}
