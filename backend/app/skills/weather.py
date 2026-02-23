from app.lib.skill import Skill
from typing import Any


class WeatherSkill(Skill):

    @property
    def name(self) -> str:
        return "weather"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()

        # Explicit weather words — always match
        if any(k in t for k in (
            "weather", "temperature", "forecast", "rain", "sunny", "cloudy",
            "humidity", "wind", "snow", "storm", "hot outside", "cold outside",
            "should i bring", "what to wear", "degrees",
        )):
            return True

        # "today" / "tomorrow" only match when combined with weather-like context
        weather_ctx = any(k in t for k in ("outside", "umbrella", "jacket", "coat", "warm", "cold", "hot"))
        if weather_ctx and any(k in t for k in ("today", "tomorrow")):
            return True

        return False

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_weather_section
        lines = await _get_weather_section(db, user_id, extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
