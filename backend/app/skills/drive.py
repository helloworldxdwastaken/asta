from app.lib.skill import Skill
from typing import Any

class DriveSkill(Skill):
    @property
    def name(self) -> str:
        return "drive"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in ("drive", "gdrive", "google drive"))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        # Drive is a stub: OAuth not wired yet. Return placeholder summary.
        from app.routers.drive import drive_status
        status = await drive_status()
        summary = status.get("summary", "Connect Google Drive in Settings.")
        return {"drive_summary": summary}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_drive_section
        lines = _get_drive_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
