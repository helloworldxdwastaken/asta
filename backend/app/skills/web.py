from app.lib.skill import Skill
from typing import Any


class GoogleSearchSkill(Skill):

    @property
    def name(self) -> str:
        return "google_search"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()

        # Explicit search-intent phrases
        if any(k in t for k in (
            "search for", "search the web", "search online", "search online for",
            "look up", "look it up", "find out", "check the web",
            "google ", "google it", "search google",
            "what's the latest", "latest news", "recent news", "current news",
            "news about", "what happened to", "what happened with",
        )):
            return True

        # Time-sensitive current-events queries
        if any(k in t for k in (
            "today's", "right now", "currently", "as of today",
            "this week", "this month", "breaking news",
        )):
            return True

        return False

    async def execute(self, user_id: str, text: str, extra_context: dict) -> dict[str, Any] | None:
        # Skip web search if RAG already found strong relevant content
        if extra_context.get("rag_found_content"):
            return None

        import asyncio
        from app.search_web import search_web
        from app.db import get_db

        db = get_db()
        brave_key = await db.get_stored_api_key("brave_search_api_key") if db._conn else None

        try:
            results, err = await asyncio.to_thread(search_web, text, 5, brave_key or None)
            return {"search_results": results, "search_error": err}
        except Exception as e:
            return {"search_error": str(e)}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_web_search_section
        lines = _get_web_search_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
