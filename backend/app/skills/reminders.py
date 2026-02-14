from app.lib.skill import Skill
from typing import Any

class RemindersSkill(Skill):
    @property
    def name(self) -> str:
        return "reminders"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(
            k in t
            for k in (
                "remind me",
                "wake me up",
                "wake up at",
                "alarm at",
                "alarm in",
                "alarm or reminder",
                "alarm",
                "reminder",
                "timer",
                "wake up tomorrow",
                "remind me tomorrow",
                "min from now",
                "remove reminder",
                "delete reminder",
                "cancel reminder",
            )
        )

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_reminders_section
        lines = await _get_reminders_section(db, user_id, extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
