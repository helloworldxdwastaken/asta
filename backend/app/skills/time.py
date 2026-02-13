from app.lib.skill import Skill
from typing import Any

class TimeSkill(Skill):
    @property
    def name(self) -> str:
        return "time"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in ("time", "what time", "what's the time", "current time", "what time is it", "clock"))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        # Start background job if needed? Time doesn't really have a "job" other than context gen.
        # But if the user just replied with a location, we might want to geocode it here?
        # Actually context.py logic handles geocoding lazily or we can do it here.
        # Let's keep it simple: context generation triggers the logic.
        
        # Check if we should update location based on this text?
        # In V1 context.py, we didn't explicitly update location in a loop, but we did handle it if "location_just_set" was present.
        # But wait, where is "location_just_set" coming from? It comes from `state_machine` or similar in a full implementation.
        # In this simple refactor, we just provide the time.
        return {}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_time_section
        # Reuse the existing logic since it's complex (geocoding, TZ, etc)
        # We wrap it to fit the interface
        lines = await _get_time_section(db, user_id, extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
