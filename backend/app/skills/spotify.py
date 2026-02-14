from app.lib.skill import Skill
from typing import Any

class SpotifySkill(Skill):
    @property
    def name(self) -> str:
        return "spotify"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        if any(k in t for k in (
            "spotify", "search spotify", "find song", "find track", "search song", "search music",
            "on spotify", "in spotify", "what song is playing", "what's playing", "playing on spotify",
        )):
            return True
        if "play " in t:
            return True
        return False

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_spotify_section
        lines = _get_spotify_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
