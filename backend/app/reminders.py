"""Parse reminder intent, schedule, and send notifications (WhatsApp, Telegram, web)."""
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


# "remind me in 30 min to do X", "remind me in 2 hours to X"
RE_IN_MINUTES = re.compile(
    r"remind\s+me\s+in\s+(\d+)\s*(min(?:ute)?s?|hr?s?|hours?)\s+(?:to\s+)?(.+)",
    re.I,
)
# "alarm in 5 min to X", "put/set alarm in 5 min", "timer 10 min", "set timer for 2h"
RE_ALARM_TIMER = re.compile(
    r"(?:(?:put|set)\s+(?:a\s+)?)?(?:alarm|timer)\s+(?:in\s+)?(?:for\s+)?(\d+)\s*(min(?:ute)?s?|hr?s?|hours?|m|h)(?:\s+(?:to\s+)?(.+))?",
    re.I,
)
# "5 min from now", "alarm 5 min from now", "reminder 5 minutes from now"
RE_FROM_NOW = re.compile(
    r"(?:(?:alarm|reminder|remind)\s+(?:me\s+)?)?(\d+)\s*(min(?:ute)?s?|hr?s?|hours?|m|h)\s+from\s+now(?:\s+(?:to\s+)?(.+))?",
    re.I,
)
# "remind me at 6pm to X", "remind me at 18:00 to X", "remind me tomorrow at 8am to X"
RE_REMIND_AT = re.compile(
    r"(?:(?:remind\s+me)|(?:set\s+(?:a\s+)?reminder))\s+"
    r"(?:for\s+)?(?:tomorrow\s+)?(?:at\s+)?"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})"
    r"(?:\s+(?:to\s+)?(.+))?",
    re.I,
)
# "wake me up at 7am", "wake me up tomorrow at 7am", "alarm at 7am", "set an alarm for 10am"
RE_WAKE_AT = re.compile(
    r"(?:(?:wake\s+me\s+up)|(?:wake\s+up)|(?:alarm)|(?:set\s+(?:an?\s+)?alarm))\s+"
    r"(?:for\s+)?(?:tomorrow\s+)?(?:at\s+)?"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})",
    re.I,
)


def _display_time(time_str: str) -> str:
    """Normalize time string for display (e.g. '7am' -> '7:00 AM')."""
    t = time_str.strip().lower()
    if not t:
        return time_str
    has_am_pm = "am" in t or "pm" in t
    t = t.replace("am", "").replace("pm", "").strip()
    if ":" in t:
        h, mi = t.split(":", 1)
        hour, minute = int(h.strip()), int(mi.strip())
    else:
        hour, minute = int(t), 0
    if has_am_pm:
        if hour == 0:
            hour, suffix = 12, "AM"
        elif hour < 12:
            suffix = "AM"
        elif hour == 12:
            suffix = "PM"
        else:
            hour, suffix = hour - 12, "PM"
        return f"{hour}:{minute:02d} {suffix}"
    return f"{hour}:{minute:02d}"


def parse_reminder(text: str, tz_str: str | None = None) -> dict[str, Any] | None:
    """Extract reminder from user message. Uses tz_str (e.g. 'Asia/Jerusalem') for 'at 7am' / 'tomorrow at 7am'.
    Returns { run_at (timezone-aware UTC), message, display_time, wake_up? } or None."""
    text = text.strip()
    tz = ZoneInfo(tz_str) if tz_str else None
    now_utc = datetime.now(timezone.utc)
    ref_now = datetime.now(tz) if tz else now_utc

    def _parse_delta(num: int, unit: str):
        u = (unit or "").lower()
        if "h" == u or "hr" in u or "hour" in u:
            return timedelta(hours=num)
        return timedelta(minutes=num)

    # "remind me in 30 min to do X"
    m = RE_IN_MINUTES.search(text)
    if m:
        num, unit, msg = int(m.group(1)), (m.group(2) or "").lower(), (m.group(3) or "").strip()
        run_at = now_utc + _parse_delta(num, unit)
        return {"message": msg or "Reminder", "run_at": run_at, "display_time": None}

    # "alarm in 5 min to X", "put alarm in 5 min", "timer 10 min"
    m = RE_ALARM_TIMER.search(text)
    if m:
        num, unit, msg = int(m.group(1)), (m.group(2) or "").lower(), (m.group(3) or "").strip()
        run_at = now_utc + _parse_delta(num, unit)
        return {"message": msg or "Reminder", "run_at": run_at, "display_time": None}

    # "5 min from now", "alarm 5 min from now", "reminder 5 minutes from now"
    m = RE_FROM_NOW.search(text)
    if m:
        num, unit, msg = int(m.group(1)), (m.group(2) or "").lower(), (m.group(3) or "").strip()
        run_at = now_utc + _parse_delta(num, unit)
        return {"message": msg or "Reminder", "run_at": run_at, "display_time": None}

    # "wake me up at 7am" / "wake me up tomorrow at 7am" / "alarm at 7am"
    m = RE_WAKE_AT.search(text)
    if m:
        time_str = (m.group(1) or "").strip()
        if not time_str:
            return None
        ref = ref_now + timedelta(days=1) if "tomorrow" in text.lower() else ref_now
        run_at_local = _parse_time_today(time_str, ref)
        if run_at_local is None:
            return None
        if run_at_local <= ref_now:
            run_at_local += timedelta(days=1)
        run_at_utc = run_at_local.astimezone(timezone.utc) if run_at_local.tzinfo else run_at_local.replace(tzinfo=timezone.utc)
        display = _display_time(time_str)
        return {"message": display, "run_at": run_at_utc, "display_time": display, "wake_up": True}

    # "remind me at 6pm to X", "set a reminder for tomorrow 11am", etc.
    m = RE_REMIND_AT.search(text)
    if m:
        time_str = (m.group(1) or "").strip()
        msg = (m.group(2) or "").strip()
        if not time_str:
            return None
        ref = ref_now + timedelta(days=1) if "tomorrow" in text.lower() else ref_now
        run_at_local = _parse_time_today(time_str, ref)
        if run_at_local is None:
            return None
        if run_at_local <= ref_now:
            run_at_local += timedelta(days=1)
        run_at_utc = run_at_local.astimezone(timezone.utc) if run_at_local.tzinfo else run_at_local.replace(tzinfo=timezone.utc)
        return {"message": msg or "Reminder", "run_at": run_at_utc, "display_time": _display_time(time_str)}
    return None


def _parse_time_today(time_str: str, ref: datetime) -> datetime | None:
    """Parse '6pm', '18:00', '6:30pm' into datetime on ref's date (same timezone as ref)."""
    time_str = time_str.strip().lower()
    try:
        if "am" in time_str or "pm" in time_str:
            is_pm = "pm" in time_str
            time_str = time_str.replace("am", "").replace("pm", "").strip()
            if ":" in time_str:
                h, mi = time_str.split(":", 1)
                hour, minute = int(h.strip()), int(mi.strip())
            else:
                hour, minute = int(time_str), 0
            if is_pm and hour < 12:
                hour += 12
            if not is_pm and hour == 12:
                hour = 0
        else:
            if ":" in time_str:
                h, mi = time_str.split(":", 1)
                hour, minute = int(h.strip()), int(mi.strip())
            else:
                hour, minute = int(time_str), 0
        run_at = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return run_at
    except (ValueError, AttributeError):
        return None


async def schedule_reminder(
    user_id: str,
    channel: str,
    channel_target: str,
    message: str,
    run_at: datetime,
) -> int:
    """Persist reminder and add one-shot scheduler job. Returns reminder id."""
    from app.cron_runner import add_cron_job_to_scheduler
    from app.db import decode_one_shot_reminder_id, get_db, run_at_to_one_shot_cron_expr
    from app.tasks.scheduler import get_scheduler

    db = get_db()
    await db.connect()
    run_at_iso = run_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    rid = await db.add_reminder(user_id, channel, channel_target, message, run_at_iso)
    one_shot_id = decode_one_shot_reminder_id(rid)
    if one_shot_id is not None:
        sch = get_scheduler()
        add_cron_job_to_scheduler(
            sch,
            one_shot_id,
            run_at_to_one_shot_cron_expr(run_at_iso),
            None,
        )
    else:
        # Legacy fallback for pre-migration reminder ids.
        sch = get_scheduler()
        sch.add_job(
            _fire_reminder,
            "date",
            run_date=run_at,
            args=[rid],
            id=f"rem_{rid}",
        )
    return rid


async def reload_pending_reminders() -> None:
    """Startup migration hook for legacy reminders."""
    from app.db import get_db

    db = get_db()
    await db.connect()
    moved = await db.migrate_legacy_pending_reminders_to_one_shot()
    if moved:
        logger.info("Migrated %d legacy pending reminder(s) to one-shot cron jobs", moved)


def _fire_reminder(reminder_id: int) -> None:
    """Run when reminder is due: send notification and mark sent."""
    import asyncio
    asyncio.run(_fire_reminder_async(reminder_id))


def _format_reminder_message(stored_message: str) -> str:
    """Turn stored reminder text into a friendly message (e.g. wake-up at 7 AM)."""
    msg = (stored_message or "").strip()
    # Wake-up style: stored as "7:00 AM" or generic "Reminder" / "wake up"
    if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)$", msg, re.I):
        return f"Good morning! ☀️ You asked to wake up at {msg}. Time to rise and shine!"
    if msg.lower() in ("reminder", "wake up", "wake", ""):
        return "⏰ Reminder! You asked me to nudge you — here it is."
    return msg


async def _fire_reminder_async(reminder_id: int) -> None:
    from app.db import get_db
    db = get_db()
    await db.connect()

    reminder = await db.get_pending_reminder_by_id(reminder_id)
    if not reminder:
        logger.debug("Reminder %s no longer pending, skipping", reminder_id)
        return

    # Format and send notification
    text = _format_reminder_message(reminder["message"])
    await send_notification(
        reminder["channel"],
        reminder["channel_target"],
        text
    )

    # Mark as sent
    await db.mark_reminder_sent(reminder_id)


async def send_notification(channel: str, target: str, message: str) -> None:
    """Send notification to user on the given channel (whatsapp, telegram, web)."""
    if channel == "telegram" and target:
        try:
            await send_telegram_message(target, message)
        except Exception as e:
            logger.warning("Failed to send reminder notification (channel=%s, target=%s): %s", channel, target, e)
            # Don't re-raise - continue with attempt marked
    elif channel == "whatsapp" and target:
        s = get_settings()
        url = getattr(s, "asta_whatsapp_bridge_url", None) or os.environ.get("ASTA_WHATSAPP_BRIDGE_URL")
        if url:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{url.rstrip('/')}/send",
                    json={"to": target, "message": message},
                    timeout=10.0,
                )
    # web: stored in reminders with status=sent; panel can list them
    return


async def send_skill_status(channel: str, channel_target: str, labels: list[str]) -> None:
    """Send a short status to Telegram/WhatsApp showing which skills are in use (e.g. 'Searching the web… • Checking the weather…')."""
    if not channel_target or channel not in ("telegram", "whatsapp"):
        return
    if not labels:
        return
    message = " • ".join(labels)
    await send_notification(channel, channel_target, message)


async def send_telegram_message(chat_id: str, text: str) -> None:
    from app.keys import get_api_key
    from telegram import Bot
    token = await get_api_key("telegram_bot_token")
    if not token:
        return
    bot = Bot(token=token)
    from app.channels.telegram_bot import to_telegram_format
    plain = (text or "").strip()[:4096]
    formatted = to_telegram_format(plain)
    try:
        await bot.send_message(chat_id=chat_id, text=formatted, parse_mode="HTML")
    except Exception as e:
        msg = str(e).lower()
        if "parse entities" in msg or "unmatched end tag" in msg:
            logger.warning("Telegram HTML parse failed for reminder, falling back to plain text: %s", e)
            await bot.send_message(chat_id=chat_id, text=plain)
            return
        raise
