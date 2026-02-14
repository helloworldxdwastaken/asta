"""Claw-style cron: recurring jobs (5-field cron expr). Fire message through handler and notify user."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.db import (
    encode_one_shot_reminder_id,
    get_db,
    is_one_shot_cron_expr,
    one_shot_cron_expr_to_run_at,
)
from app.reminders import _format_reminder_message, send_notification

logger = logging.getLogger(__name__)

CRON_JOB_PREFIX = "cron_"


def _fire_cron_job_sync(cron_job_id: int) -> None:
    """Called by scheduler (sync). Run async fire."""
    asyncio.run(_fire_cron_job_async(cron_job_id))


async def _fire_cron_job_async(cron_job_id: int) -> None:
    """Load cron job, run message through handler, send reply to user."""
    db = get_db()
    await db.connect()
    job = await db.get_cron_job(cron_job_id)
    if not job or not job.get("enabled", 1):
        return
    user_id = job.get("user_id") or "default"
    channel = job.get("channel") or "web"
    channel_target = (job.get("channel_target") or "").strip()
    message = (job.get("message") or "").strip()
    cron_expr = (job.get("cron_expr") or "").strip()
    if not message:
        return
    if is_one_shot_cron_expr(cron_expr):
        # One-shot reminders should not call handle_message again.
        try:
            await send_notification(channel, channel_target, _format_reminder_message(message))
        except Exception as e:
            logger.exception("One-shot reminder job %s failed: %s", cron_job_id, e)
            return
        await db.mark_reminder_sent(encode_one_shot_reminder_id(cron_job_id))
        return
    try:
        from app.handler import handle_message
        reply = await handle_message(
            user_id,
            channel,
            message,
            provider_name="default",
            channel_target=channel_target,
        )
        if reply and channel_target and channel in ("telegram", "whatsapp"):
            await send_notification(channel, channel_target, reply)
    except Exception as e:
        logger.exception("Cron job %s failed: %s", cron_job_id, e)
        if channel_target and channel in ("telegram", "whatsapp"):
            await send_notification(channel, channel_target, f"Cron job failed: {str(e)[:300]}")


def _parse_iso_utc(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _make_cron_trigger(cron_expr: str, tz_str: str | None):
    """Build trigger from cron expr or one-shot @at expression."""
    if is_one_shot_cron_expr(cron_expr):
        run_at = _parse_iso_utc(one_shot_cron_expr_to_run_at(cron_expr) or "")
        if not run_at:
            raise ValueError(f"Invalid one-shot cron expression: {cron_expr}")
        return DateTrigger(run_date=run_at)

    tz = None
    if (tz_str or "").strip():
        try:
            tz = ZoneInfo(tz_str.strip())
        except Exception:
            tz = None
    # APScheduler 3.x: CronTrigger.from_crontab(expr, timezone=tz)
    try:
        return CronTrigger.from_crontab(cron_expr, timezone=tz)
    except Exception:
        # Fallback: assume UTC
        return CronTrigger.from_crontab(cron_expr, timezone=timezone.utc)


def add_cron_job_to_scheduler(sch: BackgroundScheduler, job_id: int, cron_expr: str, tz_str: str | None) -> None:
    """Register one cron job with the scheduler."""
    job_id_str = f"{CRON_JOB_PREFIX}{job_id}"
    if sch.get_job(job_id_str):
        sch.remove_job(job_id_str)
    trigger = _make_cron_trigger(cron_expr, tz_str)
    sch.add_job(
        _fire_cron_job_sync,
        trigger,
        id=job_id_str,
        args=[job_id],
        replace_existing=True,
    )
    logger.info("Scheduled cron job %s: %s (tz=%s)", job_id, cron_expr, tz_str or "local")


async def reload_cron_jobs() -> None:
    """Load all enabled cron jobs from DB and add to scheduler (call on startup)."""
    from app.tasks.scheduler import get_scheduler
    db = get_db()
    await db.connect()
    jobs = await db.get_all_enabled_cron_jobs()
    sch = get_scheduler()
    # Remove any existing cron jobs from scheduler so we don't duplicate
    for j in sch.get_jobs():
        if j.id and j.id.startswith(CRON_JOB_PREFIX):
            sch.remove_job(j.id)
    fired_due = 0
    now_utc = datetime.now(timezone.utc)
    for j in jobs:
        job_id = j.get("id")
        cron_expr = (j.get("cron_expr") or "").strip()
        tz_str = (j.get("tz") or "").strip() or None
        if not job_id or not cron_expr:
            continue
        if is_one_shot_cron_expr(cron_expr):
            run_at = _parse_iso_utc(one_shot_cron_expr_to_run_at(cron_expr) or "")
            if run_at and run_at <= now_utc:
                try:
                    await _fire_cron_job_async(int(job_id))
                    fired_due += 1
                except Exception as e:
                    logger.warning("Could not fire due one-shot reminder %s: %s", job_id, e)
                continue
        try:
            add_cron_job_to_scheduler(sch, job_id, cron_expr, tz_str)
        except Exception as e:
            logger.warning("Could not schedule cron job %s (%s): %s", job_id, cron_expr, e)
    if jobs:
        logger.info("Reloaded %d cron job(s) (%d fired immediately)", len(jobs), fired_due)
