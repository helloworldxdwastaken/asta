from app.lib.skill import Skill
from typing import Any


class RagSkill(Skill):

    @property
    def name(self) -> str:
        return "rag"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()

        # Explicit memory/learning queries
        if any(k in t for k in (
            "remember", "what did i tell you", "what did we discuss",
            "what have you learned", "what did you learn", "what do you know about",
            "my notes", "saved notes", "you learned", "what you know",
            "look up in memory", "from memory",
        )):
            return True

        # RAG-stored personal knowledge
        if any(k in t for k in (
            "i told you", "i mentioned", "i said", "as i told",
            "my preference", "my info", "about me",
        )):
            return True

        return False

    async def execute(self, user_id: str, text: str, extra_context: dict) -> dict[str, Any] | None:
        try:
            from app.rag.service import get_rag
            rag = get_rag()
            rag_summary = await rag.query(text, k=5)

            result = {}
            if rag_summary and len(rag_summary.strip()) > 10:
                result["rag_summary"] = rag_summary
                result["rag_found_content"] = True
            elif rag_summary:
                result["rag_summary"] = rag_summary

            result["learned_topics"] = rag.list_topics()
            return result
        except Exception:
            return {"learned_topics": []}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_rag_section
        lines = _get_rag_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
