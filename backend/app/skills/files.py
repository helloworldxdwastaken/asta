from app.lib.skill import Skill
from typing import Any

class FilesSkill(Skill):
    @property
    def name(self) -> str:
        return "files"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in ("file", "files", "document", "folder", "path", "directory"))

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.config import get_settings
        from app.context_helpers import _get_files_section
        settings = get_settings()
        lines = _get_files_section(settings, extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
