from app.lib.skill import Skill
from typing import Any
from app.learn_about import parse_learn_about

class LearningSkill(Skill):
    @property
    def name(self) -> str:
        return "learn"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        return parse_learn_about(text or "") is not None

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_learning_status_section
        lines = _get_learning_status_section(extra)
        if lines:
             return "\n".join(lines) + "\n"
        return None
