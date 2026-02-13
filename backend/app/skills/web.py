from app.lib.skill import Skill
from typing import Any

class GoogleSearchSkill(Skill):
    @property
    def name(self) -> str:
        return "google_search"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        # Explicit search intent only; avoid broad "what is"/"who is" (let RAG handle)
        return any(k in t for k in (
            "search for", "look up", "find out", "latest ", "check the web", "search the web", "search online",
            "look it up", "google ", "search the web for", "search online for",
        ))

    async def execute(self, user_id: str, text: str, extra_context: dict) -> dict[str, Any] | None:
        # Prioritization: If RAG already found good unique content, skip web search
        # This prevents the model from ignoring RAG in favor of generic web results
        if extra_context.get("rag_found_content"):
            return None

        import asyncio
        from app.search_web import search_web
        
        try:
            results, err = await asyncio.to_thread(search_web, text, 5)
            return {"search_results": results, "search_error": err}
        except Exception as e:
            return {"search_error": str(e)}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_web_search_section
        lines = _get_web_search_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
