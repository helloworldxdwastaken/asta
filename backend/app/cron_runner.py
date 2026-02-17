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


def _fire_cron_job_sync(
    cron_job_id: int,
    trigger: str = "schedule",
    run_mode: str = "due",
) -> None:
    """Called by scheduler (sync). Run async fire."""
    asyncio.run(_fire_cron_job_async(cron_job_id, trigger=trigger, run_mode=run_mode))


async def _fire_cron_job_async(
    cron_job_id: int,
    *,
    trigger: str = "schedule",
    run_mode: str = "due",
) -> dict[str, object]:
    """Load cron job, run message through handler, send reply to user."""
    db = get_db()
    await db.connect()
    trigger_norm = (trigger or "schedule").strip().lower() or "schedule"
    mode_norm = (run_mode or "due").strip().lower() or "due"
    run_status = "unknown"
    run_output = ""
    run_error = ""

    job = await db.get_cron_job(cron_job_id)
    if not job:
        return {
            "ok": False,
            "id": int(cron_job_id),
            "status": "missing",
            "trigger": trigger_norm,
            "run_mode": mode_norm,
        }
    user_id = job.get("user_id") or "default"
    if not job.get("enabled", 1):
        await db.add_cron_job_run(
            cron_job_id=int(cron_job_id),
            user_id=str(user_id),
            trigger=trigger_norm,
            run_mode=mode_norm,
            status="disabled",
            output="Cron job is disabled.",
        )
        return {
            "ok": False,
            "id": int(cron_job_id),
            "status": "disabled",
            "trigger": trigger_norm,
            "run_mode": mode_norm,
        }
    channel = job.get("channel") or "web"
    channel_target = (job.get("channel_target") or "").strip()
    message = (job.get("message") or "").strip()
    cron_expr = (job.get("cron_expr") or "").strip()
    if not message:
        await db.add_cron_job_run(
            cron_job_id=int(cron_job_id),
            user_id=str(user_id),
            trigger=trigger_norm,
            run_mode=mode_norm,
            status="skipped",
            output="Cron message is empty.",
        )
        return {
            "ok": False,
            "id": int(cron_job_id),
            "status": "skipped",
            "trigger": trigger_norm,
            "run_mode": mode_norm,
        }
    payload_kind = (job.get("payload_kind") or "agentturn").strip().lower()
    tlg_call = bool(job.get("tlg_call") or False)
    
    if tlg_call and channel_target:
        # User wants a voice call via Pingram (NotificationAPI)
        from app.reminders import trigger_pingram_voice_call
        
        # If channel is telegram, we might not have a phone number in channel_target.
        # But if the user entered a phone number there, it will work.
        if channel_target.startswith("+") or channel_target.isdigit():
            logger.info("Cron job %s: Triggering Pingram Voice Call to %s", cron_job_id, channel_target)
            try:
                # We use the job message as the voice payload
                call_msg = message or f"This is Asta calling for your job {job.get('name') or cron_job_id}"
                await trigger_pingram_voice_call(channel_target, call_msg)
            except Exception as e:
                logger.warning("Failed to trigger Pingram call for job %s: %s", cron_job_id, e)
        else:
            logger.warning("Cron job %s: Call enabled but target %s doesn't look like a phone number", cron_job_id, channel_target)
            # Fallback to placeholder notification
            try:
                await send_notification(channel, channel_target, "📞 **INCOMING ASTA CALL...** (Setup @username in Settings)")
            except Exception as e:
                logger.warning("Failed to trigger call placeholder for job %s: %s", cron_job_id, e)

    if is_one_shot_cron_expr(cron_expr) or payload_kind not in ("agentturn",):
        # One-shot reminders or jobs explicitly set to notify/systemevent should not call handle_message as an AI turn.
        try:
            await send_notification(channel, channel_target, _format_reminder_message(message))
            run_status = "ok"
            run_output = f"Direct notification sent via {channel}: {_format_reminder_message(message)}"
            if is_one_shot_cron_expr(cron_expr):
                await db.mark_reminder_sent(encode_one_shot_reminder_id(cron_job_id))
        except Exception as e:
            logger.exception("Direct notification job %s failed: %s", cron_job_id, e)
            run_status = "error"
            run_error = str(e)
    else:
        # For recurring jobs (agentturn), call AI
        try:
            from app.handler import handle_message
            reply = await handle_message(
                user_id=str(user_id),
                channel=channel,
                channel_target=channel_target,
                text=message,
                is_ai_turn=True,
            )
            run_status = "ok"
            run_output = (reply or "").strip()
        except Exception as e:
            logger.exception("Cron job %s (AI turn) failed: %s", cron_job_id, e)
            run_status = "error"
            run_error = str(e)

    await db.add_cron_job_run(
        cron_job_id=int(cron_job_id),
        user_id=str(user_id),
        trigger=trigger_norm,
        run_mode=mode_norm,
        status=run_status,
        output=run_output,
        error=run_error,
    )
    return {
        "ok": run_status == "ok",
        "id": int(cron_job_id),
        "status": run_status,
        "output": run_output[:300] if run_output else "",
        "error": run_error[:300] if run_error else "",
        "trigger": trigger_norm,
        "run_mode": mode_norm,
    }


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
        args=[job_id, "schedule", "due"],
        replace_existing=True,
    )
    logger.info("Scheduled cron job %s: %s (tz=%s)", job_id, cron_expr, tz_str or "local")


async def run_cron_job_now(cron_job_id: int, *, run_mode: str = "force") -> dict[str, object]:
    """Run a cron job immediately (manual trigger) and return execution summary."""
    return await _fire_cron_job_async(
        int(cron_job_id),
        trigger="manual",
        run_mode=(run_mode or "force"),
    )


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
