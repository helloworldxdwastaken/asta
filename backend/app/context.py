"""Build unified context for the AI: connections, recent chat, files, Drive, RAG."""
from __future__ import annotations
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.db import Db

logger = logging.getLogger(__name__)

# Default user id when not in a multi-user setup
DEFAULT_USER_ID = "default"

from app.context_helpers import _is_error_reply, _is_time_reply

async def build_context(
    db: "Db",
    user_id: str,
    conversation_id: str | None,
    extra: dict | None = None,
    skills_in_use: set[str] | None = None,
) -> str:
    """Build a context string the AI can use. If skills_in_use is set, only include those skill sections (saves tokens)."""
    extra = extra or {}
    
    parts = []
    
    # 1. System instruction & Tone
    parts.extend(_get_system_header(extra.get("mood")))

    # 2. Recent Conversation
    if conversation_id:
        parts.extend(await _get_recent_conversation(db, conversation_id, skills_in_use))

    # 3. Connected Channels & State
    parts.extend(await _get_state_section(db, user_id, extra))

    # 4. Skill Sections
    from app.skills.registry import get_all_skills
    
    # Iterate over all registered skills
    # We use a fixed order from registry to ensure context stability
    for skill in get_all_skills():
        # Check if enabled for user
        is_enabled = await db.get_skill_enabled(user_id, skill.name)
        if not is_enabled and not skill.is_always_enabled:
             continue
             
        # Check if selected by router (skills_in_use)
        # If skills_in_use is None, we default to "include everything" (e.g. debugging)
        if skills_in_use is not None and skill.name not in skills_in_use:
             continue

        try:
            # We must pass 'db' here!
            section = await skill.get_context_section(db, user_id, extra)
            if section:
                parts.append(section)
        except Exception as e:
            logger.error(f"Error building context for skill {skill.name}: {e}")
            parts.append(f"<!-- Error loading {skill.name} context -->")

    parts.append("Answer using the above context when relevant. Be concise and helpful.")
    return "\n".join(parts)


def _get_system_header(mood: str | None) -> list[str]:
    mood = mood or "normal"
    _mood_map = {
        "serious": "Reply in a serious, professional tone. Be direct and factual.",
        "friendly": "Reply in a warm, friendly tone. Use a bit of warmth and personality.",
        "normal": "Reply in a balanced, helpful tone—neither stiff nor overly casual.",
    }
    mood_instruction = _mood_map.get(mood, _mood_map["normal"])
    return [
        "You are Asta, the user's agent. You use whichever AI model is configured (Groq, Gemini, Claude, Ollama) and have access to the user's connected services.",
        "TONE: " + mood_instruction,
        "CORE DIRECTIVE: If you have learned knowledge (RAG) about a topic, it takes precedence over general knowledge or web search results.",
        "Use the context below to understand what is connected and recent history.",
        "",
    ]


async def _get_recent_conversation(db: "Db", conversation_id: str, skills_in_use: set[str] | None) -> list[str]:
    """Get recent messages, skipping error replies and stale time checks."""
    parts = []
    try:
        recent = await db.get_recent_messages(conversation_id, limit=10)
        if recent:
            parts.append("--- Recent conversation ---")
            skip_time_replies = skills_in_use and "time" in skills_in_use
            for m in recent:
                if m["role"] == "assistant" and _is_error_reply(m["content"]):
                    continue
                if skip_time_replies and m["role"] == "assistant" and _is_time_reply(m["content"]):
                    continue  # Don't show old time answers — use live value from Time section
                role = "User" if m["role"] == "user" else "Assistant"
                parts.append(f"{role}: {m['content'][:500]}")
            parts.append("")
    except Exception:
        pass
    return parts


async def _get_state_section(db: "Db", user_id: str, extra: dict) -> list[str]:
    """Connected channels and factual state (pending reminders count, location name)."""
    parts = []
    # Channels
    channels = []
    from app.keys import get_api_key
    token = await get_api_key("telegram_bot_token")
    if token:
        channels.append("Telegram")
    channels.append("Web panel")
    parts.append("--- Connected ---")
    parts.append("Channels: " + ", ".join(channels))
    parts.append("")

    # Ground truth
    pending = await db.get_pending_reminders_for_user(user_id, limit=10)
    loc = await db.get_user_location(user_id)
    loc_str = loc["location_name"] if loc else None
    if not loc_str:
        from app.memories import get_location_from_memories
        loc_str = get_location_from_memories(user_id) or "not set"
    parts.append("--- State (factual) ---")
    parts.append(f"Pending reminders: {len(pending)}. Location: {loc_str}. Use this — do not invent reminders or location.")
    parts.append("")
    return parts


