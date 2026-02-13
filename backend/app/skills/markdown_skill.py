"""OpenClaw-style skill: instructions from workspace/skills/<name>/SKILL.md."""
from __future__ import annotations
import re
from typing import Any

from app.lib.skill import Skill
from app.workspace import ResolvedSkill


class MarkdownSkill(Skill):
    """Skill that provides context from a SKILL.md file. No execute(); model follows the instructions in context."""

    def __init__(self, resolved: ResolvedSkill) -> None:
        self._resolved = resolved

    @property
    def name(self) -> str:
        return self._resolved.name

    def check_eligibility(self, text: str, user_id: str) -> bool:
        # Simple heuristic: if any significant word from the description appears in the message, consider eligible.
        t = (text or "").strip().lower()
        desc = (self._resolved.description or "").lower()
        # Use words from description (skip very short)
        words = [w for w in re.split(r"\W+", desc) if len(w) >= 3]
        return any(w in t for w in words)

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def get_context_section(self, db: Any, user_id: str, extra: dict[str, Any]) -> str | None:
        path = self._resolved.file_path
        if not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8", errors="replace").strip()
            if not content:
                return None
            return f"[SKILL: {self._resolved.name}]\n{content}\n"
        except Exception:
            return None
