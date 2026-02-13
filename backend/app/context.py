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
    
    # 0. OpenClaw-style workspace context (AGENTS.md, USER.md, SOUL.md, TOOLS.md)
    from app.workspace import get_workspace_context_section
    workspace_ctx = get_workspace_context_section()
    if workspace_ctx:
        parts.append(workspace_ctx)
        parts.append("")
    
    # 1. System instruction & Tone
    parts.extend(_get_system_header(extra.get("mood")))

    # 2. Recent Conversation
    if conversation_id:
        parts.extend(await _get_recent_conversation(db, conversation_id, skills_in_use))

    # 3. Connected Channels & State
    parts.extend(await _get_state_section(db, user_id, extra))

    # 3a. Exec tool (Claw-like): when enabled, model can run allowlisted commands
    from app.config import get_settings
    _settings = get_settings()
    if _settings.exec_allowed_bins:
        bins = ", ".join(sorted(_settings.exec_allowed_bins))
        parts.append(
            f"[EXEC] You can run shell commands by outputting [ASTA_EXEC: command][/ASTA_EXEC]. "
            f"Allowed binaries: {bins}. Asta will run the command and use the output to answer. "
            "E.g. for Apple Notes: [ASTA_EXEC: memo notes][/ASTA_EXEC] or [ASTA_EXEC: memo notes -s \"Eli\"][/ASTA_EXEC]. "
            "For Things: [ASTA_EXEC: things inbox][/ASTA_EXEC]. Use one block per command."
        )
        parts.append("")

    # 3a2. Cron (Claw-style recurring jobs): model can add/remove cron jobs
    parts.append(
        "[CRON] You can schedule recurring jobs (like OpenClaw cron). "
        "To add: [ASTA_CRON_ADD: name|cron_expr|tz|message][/ASTA_CRON_ADD]. "
        "Use 5-field cron: minute hour day month day_of_week (e.g. 0 8 * * * = daily 8am). "
        "tz is optional (e.g. America/Los_Angeles). "
        "Example: [ASTA_CRON_ADD: Daily Update|0 7 * * *||Run daily update check and report][/ASTA_CRON_ADD]. "
        "To remove: [ASTA_CRON_REMOVE: name][/ASTA_CRON_REMOVE]. "
        "When the cron runs, the message is sent to the AI and the reply is delivered to the user."
    )
    parts.append("")

    # 3b. OpenClaw-style available skills (name, description, location) — model uses this to decide which skill applies
    parts.append(await _get_available_skills_prompt(db, user_id, skills_in_use))

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


# Built-in skill descriptions for OpenClaw-style available_skills block (id -> description)
_BUILTIN_SKILL_DESCRIPTIONS: dict[str, str] = {
    "files": "Local file access and summaries.",
    "drive": "Drive files and summaries.",
    "rag": "Learned knowledge and documents.",
    "learn": "Say 'learn about X for 30 min' to have Asta learn and store a topic in RAG.",
    "time": "Current time (12h AM/PM). Location is used for your timezone when set.",
    "weather": "Current weather and forecast (today, tomorrow). Set your location once so Asta can answer.",
    "google_search": "Search the web for current information.",
    "lyrics": "Find song lyrics (free, no key). Ask e.g. 'lyrics for Bohemian Rhapsody'.",
    "spotify": "Search songs on Spotify. Playback on devices (with device picker) when configured.",
    "reminders": "Wake me up or remind me at a time. Set your location so times are in your timezone.",
    "audio_notes": "Upload audio; Asta transcribes and formats as meeting notes. No API key (runs locally).",
    "silly_gif": "Occasionally replies with a relevant GIF in friendly chats. Requires Giphy API key.",
    "self_awareness": "Answers about Asta (features, docs, how to use) using README + docs and workspace/USER.md. No separate data folder.",
    "server_status": "Monitor system metrics (CPU, RAM, Disk, Uptime). Ask 'server status' or '/status'.",
}


async def _get_available_skills_prompt(db: "Db", user_id: str, skills_in_use: set[str] | None) -> str:
    """OpenClaw-style: list of skills with name, description, location so the model knows what exists and when to use each."""
    from app.skills.registry import get_all_skills
    from app.skills.markdown_skill import MarkdownSkill
    from app.workspace import discover_workspace_skills

    lines = [
        "",
        "The following skills provide specialized instructions for specific tasks.",
        "When the task matches a skill's description, use the instructions in the [SKILL: name] sections below.",
        "When a skill file references a relative path, resolve it against the skill directory (parent of SKILL.md) and use that absolute path in tool commands.",
        "",
        "<available_skills>",
    ]
    for skill in get_all_skills():
        try:
            enabled = await db.get_skill_enabled(user_id, skill.name)
        except Exception:
            enabled = True
        if not enabled and not getattr(skill, "is_always_enabled", False):
            continue
        if isinstance(skill, MarkdownSkill):
            r = skill._resolved
            desc = r.description
            loc = str(r.file_path)
        else:
            desc = _BUILTIN_SKILL_DESCRIPTIONS.get(skill.name, f"Skill: {skill.name}.")
            loc = "(injected in [SKILL: name] section below when selected)"
        lines.append("  <skill>")
        lines.append(f"    <name>{skill.name}</name>")
        lines.append(f"    <description>{desc}</description>")
        lines.append(f"    <location>{loc}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    lines.append("")
    return "\n".join(lines)


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


