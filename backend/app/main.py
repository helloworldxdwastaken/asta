"""Asta API — control plane for AI, files, channels, and learning."""
import asyncio
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
from app.db import get_db, DB_PATH, _is_sqlite_locked_error
from app.routers import chat, files, drive, rag, providers, tasks, settings as settings_router, spotify as spotify_router, audio as audio_router, cron as cron_router, agents as agents_router

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
    """Startup: validate DB, reload reminders, ensure User.md, start Telegram. Shutdown: cleanup."""

    # 1. Validate database connection FIRST
    try:
        db = get_db()
        await db.connect()
        logger.info("✓ Database connected: %s", os.path.basename(DB_PATH))
    except Exception as e:
        logger.critical("✗ Failed to connect to database: %s", e)
        raise RuntimeError("Database initialization failed") from e

    # 2. Validate workspace path if configured
    try:
        ws = get_settings().workspace_path
        if ws:
            if not ws.exists():
                logger.warning("⚠ Workspace path does not exist: %s", ws)
            else:
                logger.info("✓ Workspace path: %s", ws)
    except Exception as e:
        logger.warning("⚠ Could not validate workspace path: %s", e)

    # 3. Recover interrupted subagent runs (non-fatal)
    try:
        from app.subagent_orchestrator import recover_subagent_runs_on_startup
        recovered = await recover_subagent_runs_on_startup()
        if recovered:
            logger.info("✓ Recovered %d interrupted subagent run(s)", recovered)
    except Exception as e:
        logger.error("⚠ Subagent recovery failed (non-fatal): %s", e)
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
    # Also tolerate transient SQLite lock contention during restarts.
    token: str | None = None
    db = get_db()
    for attempt in range(6):
        try:
            token = await db.get_stored_api_key("telegram_bot_token")
            break
        except Exception as e:
            if not _is_sqlite_locked_error(e):
                logger.exception("Failed to load Telegram token from DB; continuing with env token: %s", e)
                break
            delay = 0.25 * (attempt + 1)
            if attempt == 5:
                logger.warning(
                    "Could not read Telegram token from DB after retries (database lock). "
                    "Continuing without DB token."
                )
                break
            logger.warning(
                "Database locked while reading Telegram token (attempt %d/6), retrying in %.2fs",
                attempt + 1,
                delay,
            )
            await asyncio.sleep(delay)
    token = token or get_settings().telegram_bot_token
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
    description="Asta: personal control plane — AI, Telegram, files, Drive, RAG.",
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
app.include_router(agents_router.router, tags=["agents"])
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


