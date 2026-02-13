from app.lib.skill import Skill
from app.lyrics import _extract_lyrics_query, fetch_lyrics
from typing import Any

class LyricsSkill(Skill):
    @property
    def name(self) -> str:
        return "lyrics"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        if "play " in t:
            return False
        if any(k in t for k in ("lyrics for", "lyrics of", "find lyrics", "song lyrics", "get lyrics", " lyrics", " lyric ")):
            return True
        elif any(k in t for k in ("song by", " by ", "artist ", "singer ")) and len(t) > 5:
            # Heuristic from skill_router.py
            return True
        return False

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        query = _extract_lyrics_query(text)
        if not query:
            return {}
        result = await fetch_lyrics(query)
        return {
            "lyrics_searched_query": query,
            "lyrics_result": result,
        }

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_lyrics_section
        lines = _get_lyrics_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
