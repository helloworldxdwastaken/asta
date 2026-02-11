from datetime import datetime
from typing import Any
from app.db import get_db
from app.reminders import parse_reminder, schedule_reminder
from app.time_weather import get_timezone_for_coords

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
            
        reminder = parse_reminder(text, tz_str=tz_str)
        if reminder:
            run_at = reminder["run_at"]
            msg = reminder.get("message", "Reminder")
            target = channel_target or "web"
            await schedule_reminder(user_id, channel, target, msg, run_at)
            
            return {
                "reminder_scheduled": True,
                "reminder_at": (reminder.get("display_time") or run_at.strftime("%H:%M")) if run_at else "",
                "is_reminder": True # Flag to help skill selection
            }
        return None
