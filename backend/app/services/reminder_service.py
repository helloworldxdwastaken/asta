import re
from typing import Any
from app.db import get_db
from app.reminders import parse_reminder, schedule_reminder
from app.time_weather import get_timezone_for_coords

# Absolute-time patterns: "at 7am", "at 6pm" require user timezone
RE_WAKE_AT = re.compile(
    r"(?:(?:wake\s+me\s+up)|(?:wake\s+up)|(?:alarm)|(?:set\s+(?:an?\s+)?alarm))\s+"
    r"(?:for\s+)?(?:tomorrow\s+)?(?:at\s+)?"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})",
    re.I,
)
RE_REMIND_AT = re.compile(
    r"(?:(?:remind\s+me)|(?:set\s+(?:a\s+)?reminder))\s+"
    r"(?:for\s+)?(?:tomorrow\s+)?(?:at\s+)?"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})"
    r"(?:\s+(?:to\s+)?(.+))?",
    re.I,
)
def _is_absolute_time_reminder(text: str) -> bool:
    """True if text looks like 'at 7am' / 'at 6pm' (needs timezone)."""
    t = (text or "").strip()
    return bool(RE_WAKE_AT.search(t) or RE_REMIND_AT.search(t))


async def _get_effective_location(user_id: str):
    """Get location from DB, or from User.md if DB is empty (geocode and persist)."""
    db = get_db()
    loc = await db.get_user_location(user_id)
    if loc:
        return loc
    from app.memories import get_location_from_memories
    from app.time_weather import geocode
    loc_str = get_location_from_memories(user_id)
    if not loc_str:
        return None
    result = await geocode(loc_str)
    if not result:
        return None
    lat, lon, name = result
    await db.set_user_location(user_id, name, lat, lon)
    return {"location_name": name, "latitude": lat, "longitude": lon}


class ReminderService:
    @staticmethod
    async def process_reminder(user_id: str, text: str, channel: str, channel_target: str) -> dict[str, Any] | None:
        """
        Parse and schedule reminder from text.
        Returns a dict of context updates (e.g. {'reminder_scheduled': True}) or None.
        """
        # Get user timezone if available (from DB or User.md)
        tz_str: str | None = None
        loc = await _get_effective_location(user_id)
        if loc:
            tz_str = await get_timezone_for_coords(loc["latitude"], loc["longitude"], loc.get("location_name"))

        # Absolute times ("at 7am", "at 6pm") require timezone. Don't schedule in UTC when unknown.
        if not tz_str and _is_absolute_time_reminder(text):
            return {
                "reminder_needs_location": True,
                "is_reminder": True,
            }

        reminder = parse_reminder(text, tz_str=tz_str)
        if reminder:
            from app.config import get_settings
            s = get_settings()
            owner_phone = getattr(s, "asta_owner_phone_number", None)
            
            # Default tlg_call to True if phone number is set
            tlg_call = bool(owner_phone)
            
            run_at = reminder["run_at"]
            msg = reminder.get("message", "Reminder")
            
            target = channel_target or "web"
            # If call is requested but no number in target, use owner_phone
            if tlg_call and owner_phone and not (target and (target.startswith("+") or target.isdigit())):
                target = owner_phone

            await schedule_reminder(user_id, channel, target, msg, run_at, tlg_call=tlg_call)
            
            return {
                "reminder_scheduled": True,
                "reminder_at": (reminder.get("display_time") or run_at.strftime("%H:%M")) if run_at else "",
                "is_reminder": True # Flag to help skill selection
            }
        return None
