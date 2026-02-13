from app.lib.skill import Skill
from typing import Any

class AudioNotesSkill(Skill):
    @property
    def name(self) -> str:
        return "audio_notes"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            "audio notes", "voice memo", "meeting notes", "transcript",
            "last meeting", "previous meeting", "my notes", "saved notes",
            "what did we discuss", "meeting summary",
        ))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        from app.db import get_db
        db = get_db()
        await db.connect()
        notes = await db.get_recent_audio_notes(user_id, limit=5)
        return {
            "past_meetings": [
                {
                    "created_at": n.get("created_at", ""),
                    "title": n.get("title", "Meeting"),
                    "formatted": n.get("formatted", ""),
                }
                for n in notes
            ],
        }

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_past_meetings_section
        lines = _get_past_meetings_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
