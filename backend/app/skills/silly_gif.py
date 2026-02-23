"""Proactive GIF skill: when enabled, adds instruction for AI to occasionally include GIFs."""
from app.lib.skill import Skill
from typing import Any


class SillyGifSkill(Skill):

    @property
    def name(self) -> str:
        return "silly_gif"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip()
        t_lower = t.lower()

        # Too short or too long to be a casual conversational message
        if len(t) < 8 or len(t) > 120:
            return False

        # Skip anything that looks like a question or task request
        if "?" in t:
            return False
        if any(t_lower.startswith(k) for k in (
            "what", "how", "why", "when", "where", "who", "can you", "could you",
            "please", "remind", "set", "create", "make", "write", "send", "search",
            "find", "play", "list", "show", "get", "tell", "give", "open", "check",
            "delete", "remove", "add", "update", "change", "fix", "help",
        )):
            return False

        # Only fire on casual / social messages
        casual_keywords = (
            "haha", "lol", "lmao", "hehe", "nice", "cool", "awesome", "great",
            "thanks", "thank you", "cheers", "yay", "woo", "amazing", "love it",
            "good morning", "good night", "good evening", "hey", "hi there",
            "happy", "sad", "excited", "bored", "tired", "hungry", "good job",
            "well done", "congrats", "congratulations", "that's funny", "funny",
        )
        return any(k in t_lower for k in casual_keywords)

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        return None
