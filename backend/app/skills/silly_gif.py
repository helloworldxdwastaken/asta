"""Proactive GIF skill: when enabled, adds instruction for AI to occasionally include GIFs."""
from app.lib.skill import Skill
from typing import Any

class SillyGifSkill(Skill):
    @property
    def name(self) -> str:
        return "silly_gif"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        # Proactive skill: conversational messages, not questions (reduces over-triggering)
        t = (text or "").strip()
        if len(t) < 5 or len(t) >= 100 or "?" in t:
            return False
        # Don't trigger on short affirmations (e.g. "Yeah do that") so file-save follow-ups use files skill
        lower = t.lower()
        if lower in ("yeah", "yes", "do that", "ok", "sure", "go ahead", "please", "do it", "yep", "okay") or (len(t) < 25 and any(w in lower for w in ("do it", "go ahead", "yes", "yeah", "ok", "sure"))):
            return False
        return True

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        # No data to gather; handler adds proactive instruction when this skill is in use
        return {}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        # Instruction is injected by handler when silly_gif in skills_to_use
        return None
