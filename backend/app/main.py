"""Asta API — control plane for AI, files, channels, and learning."""
import logging
import os
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_db
from app.whatsapp_bridge import get_whatsapp_bridge_status
from app.routers import chat, files, drive, rag, providers, tasks, settings as settings_router, spotify as spotify_router, audio as audio_router, cron as cron_router

logger = logging.getLogger(__name__)

# Ensure app.* loggers emit INFO to stderr (captured in backend.log when run via asta.sh)
_app_log = logging.getLogger("app")
_app_log.setLevel(logging.INFO)
if not _app_log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_log.addHandler(_h)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: DB + reload reminders + ensure User.md + Telegram bot. Shutdown: stop bot cleanly."""
    await get_db().connect()
    try:
        from app.memories import ensure_user_md
        ensure_user_md("default")
    except Exception as e:
        logger.exception("Failed to ensure User.md: %s", e)
    try:
        from app.reminders import reload_pending_reminders
        await reload_pending_reminders()
        try:
            from app.cron_runner import reload_cron_jobs, add_cron_job_to_scheduler
            from app.tasks.scheduler import get_scheduler
            await reload_cron_jobs()
            # Auto-updater skill: ensure "Daily Auto-Update" cron exists when skill is present
            try:
                ws = get_settings().workspace_path
                auto_updater_skill = ws and (ws / "skills" / "auto-updater-100").is_dir()
                if auto_updater_skill:
                    db = get_db()
                    jobs = await db.get_cron_jobs("default")
                    has_auto_update = any((j.get("name") or "").strip() == "Daily Auto-Update" for j in jobs)
                    if not has_auto_update:
                        job_id = await db.add_cron_job(
                            "default",
                            "Daily Auto-Update",
                            "0 4 * * *",
                            "Run daily auto-updates: check for Asta updates and update all skills. Report what was updated.",
                            tz="",
                            channel="web",
                            channel_target="",
                        )
                        add_cron_job_to_scheduler(get_scheduler(), job_id, "0 4 * * *", None)
                        logger.info("Created Daily Auto-Update cron job for auto-updater skill")
            except Exception as e:
                logger.debug("Could not ensure auto-updater cron: %s", e)
        except Exception as e:
            logger.exception("Failed to reload cron jobs: %s", e)
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
app.include_router(cron_router.router, prefix="/api", tags=["cron"])
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
    runtime = await get_whatsapp_bridge_status(settings.asta_whatsapp_bridge_url)
    base = (runtime.get("bridge_url") or "").rstrip("/")
    if not runtime.get("configured"):
        return {"connected": False, "qr": None, "error": runtime.get("error"), "status": runtime}
    if not runtime.get("reachable"):
        return {"connected": False, "qr": None, "error": runtime.get("error"), "status": runtime}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/qr")
            payload = r.json() if r.content else {}
            if not isinstance(payload, dict):
                payload = {"connected": bool(runtime.get("connected")), "qr": None}
            if "connected" not in payload:
                payload["connected"] = bool(runtime.get("connected"))
            if "qr" not in payload:
                payload["qr"] = None
            payload["status"] = runtime
            if runtime.get("error") and not payload.get("error"):
                payload["error"] = runtime["error"]
            return payload
    except Exception:
        return {"connected": False, "qr": None, "error": runtime.get("error"), "status": runtime}
