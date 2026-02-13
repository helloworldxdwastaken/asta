from app.lib.skill import Skill
from typing import Any

class RagSkill(Skill):
    @property
    def name(self) -> str:
        return "rag"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        # "Learn about X" logic (handled by a side-effect, but shares 'rag' skill mostly)
        # Actually in skill_router 'learn' is separate (out.add("learn")) but context is shared.
        # Let's handle generic RAG retrieval intents here.
        if any(k in t for k in ("remember", "notes", "saved", "learned", "what did i", "my notes", "what did you learn", "what have you learned", "what do you know about")):
            return True
        if any(k in t for k in ("what is ", "who is ", "what are ", "tell me about ")):
            return True
        if "?" in t and len(t) > 15 :
             # Broad catch-all for questions (simple heuristic)
             return True
        return False

    async def execute(self, user_id: str, text: str, extra_context: dict) -> dict[str, Any] | None:
        try:
            from app.rag.service import get_rag
            rag = get_rag()
            # Query for relevant content
            rag_summary = await rag.query(text, k=5)
            
            result = {}
            if rag_summary and len(rag_summary.strip()) > 10:
                result["rag_summary"] = rag_summary
                result["rag_found_content"] = True # Signal to other skills
            elif rag_summary:
                result["rag_summary"] = rag_summary
                
            # Always get list of topics for "What have you learned?" questions
            result["learned_topics"] = rag.list_topics()
            return result
        except Exception as e:
            # If RAG fails, we just don't have context. Not fatal.
            return {"learned_topics": []}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_rag_section
        lines = _get_rag_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
