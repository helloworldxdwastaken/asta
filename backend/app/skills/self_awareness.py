from app.lib.skill import Skill
from typing import Any

class SelfAwarenessSkill(Skill):
    @property
    def name(self) -> str:
        return "self_awareness"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        # Explicit Asta/self questions; avoid broad "help" (matches "help me with homework")
        return any(k in t for k in (
            "asta", "documentation", "manual", "how to use asta", "what is this",
            "what can you do", "features", "capabilities", "yourself", "who are you",
            "asta help", "help with asta",
        ))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        import asyncio
        from app.docs import load_asta_docs
        docs = await asyncio.to_thread(load_asta_docs)
        if docs:
            return {"asta_docs": docs}
        return {}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_docs_section
        lines = _get_docs_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
