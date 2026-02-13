from app.lib.skill import Skill
from typing import Any

class WeatherSkill(Skill):
    @property
    def name(self) -> str:
        return "weather"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in ("weather", "temperature", "forecast", "tomorrow", "today", "rain", "sunny", "temperature"))

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_weather_section
        lines = await _get_weather_section(db, user_id, extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
