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

    # 3a. Exec (OpenClaw-style): when enabled, use the exec tool to run allowlisted commands. Model calls the tool; we run and return output.
    from app.exec_tool import get_effective_exec_bins
    effective_bins = await get_effective_exec_bins(db, user_id)
    from app.config import get_settings
    exec_mode = get_settings().exec_security
    if exec_mode != "deny" and (exec_mode == "full" or effective_bins):
        bins = "any command (security=full)" if exec_mode == "full" else ", ".join(sorted(effective_bins))
        parts.append(
            f"[EXEC] Allowed binaries: {bins}. Use the exec tool when the user asks to check Apple Notes (memo notes, memo notes -s \"query\"), "
            "list Things (things inbox), or run another allowlisted CLI. Do not say you will check — call the exec tool with the command; you will get the real output and then answer. "
            "For long-running commands, exec supports background/yield (background=true or yield_ms). "
            "When exec returns status=running with session_id, use the process tool to manage it: list, poll, log, write, kill, clear, remove. "
            "If exec tool output says 'approval-needed' with an id, tell the user approval is blocking the action and to open /approvals and tap Once, Always, or Deny. "
            "Fallback: if the exec tool is not available, you can output [ASTA_EXEC: command][/ASTA_EXEC] (e.g. [ASTA_EXEC: memo notes][/ASTA_EXEC]) in your reply."
        )
        parts.append("")

    # 3a1. Files tools: list/read/allow/delete for allowed paths
    if skills_in_use and "files" in skills_in_use:
        parts.append(
            "[FILES] You have list_directory, read_file, write_file, allow_path, delete_file, and delete_matching_files tools. "
            "When the user asks 'what files on my desktop', 'list my desktop', 'what do I have on desktop', or similar: call allow_path(\"~/Desktop\") to request access, then list_directory(\"~/Desktop\") to list the files. Do not say you cannot run ls — use these tools instead. "
            "If the path is already allowed, list_directory works directly. "
            "For save/create requests (e.g. shopping list), call write_file with a sensible workspace path and exact content. "
            "For deleting one file use delete_file(path). For multiple similar files (like screenshots) use delete_matching_files(directory, glob_pattern). "
            "Only paths under the user's home can be added via allow_path."
        )
        parts.append("")

    # 3a2. Reminders tool (one-shot)
    # Keep guidance whenever reminders are enabled since the tool is available globally.
    if await db.get_skill_enabled(user_id, "reminders"):
        parts.append(
            "[REMINDERS] Use the reminders tool for one-time reminders. "
            "Use action='add' with natural text (e.g. 'remind me in 30 min to call mom', 'wake me up tomorrow at 7am'). "
            "Use action='list' or action='status' when the user asks what reminders exist. "
            "Use action='update' with id (+ text/run_at/message) when user asks to edit one. "
            "Use action='remove' with id when user asks to delete one."
        )
        parts.append("")

    # 3a3. Cron (Claw-style recurring jobs): use cron tool actions for recurring schedules
    parts.append(
        "[CRON] For recurring jobs, use the cron tool (actions: status, list, add, update, remove, run, runs, wake). "
        "Use 5-field cron expressions: minute hour day month day_of_week (e.g. 0 8 * * * means every day at 08:00). "
        "When adding, provide name, cron_expr, and message; tz is optional. "
        "Use run with id to trigger immediately (run_mode=force|due), runs to inspect recent execution history, and wake to refresh scheduler state."
    )
    parts.append("")

    # 3b. OpenClaw-style available skills (workspace skills only): model selects one and reads SKILL.md via read tool.
    skills_prompt = await _get_available_skills_prompt(
        db,
        user_id,
        skills_in_use,
        agent_skill_filter=_resolve_selected_agent_skill_filter(extra),
    )
    if skills_prompt:
        parts.append(skills_prompt)

    # 4. Skill Sections
    from app.skills.registry import get_all_skills
    from app.skills.markdown_skill import MarkdownSkill
    
    # Iterate over all registered skills
    # We use a fixed order from registry to ensure context stability
    for skill in get_all_skills():
        # OpenClaw-style workspace skills are read on-demand via the `read` tool.
        # Do not preload SKILL.md bodies into context.
        if isinstance(skill, MarkdownSkill):
            continue
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


def _resolve_selected_agent_skill_filter(extra: dict) -> list[str] | None:
    """Read selected agent skills from extra context.

    Returns:
    - None: no agent-level filter configured (all enabled skills allowed)
    - []: explicit deny-all skills for this selected agent
    - [ids...]: allowlist for this selected agent
    """
    selected = extra.get("selected_agent") if isinstance(extra, dict) else None
    if not isinstance(selected, dict):
        return None
    raw = selected.get("skills")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        sid = str(item).strip().lower()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        normalized.append(sid)
    return normalized


async def _get_available_skills_prompt(
    db: "Db",
    user_id: str,
    skills_in_use: set[str] | None,
    agent_skill_filter: list[str] | None = None,
) -> str:
    """OpenClaw-style list of workspace skills with name/description/location."""
    from app.skills.registry import get_all_skills
    from app.skills.markdown_skill import MarkdownSkill

    skill_lines: list[str] = []
    markdown_skill_names: set[str] = set()
    allowed = set(agent_skill_filter) if agent_skill_filter is not None else None
    for skill in get_all_skills():
        try:
            enabled = await db.get_skill_enabled(user_id, skill.name)
        except Exception:
            enabled = True
        if not enabled and not getattr(skill, "is_always_enabled", False):
            continue
        if not isinstance(skill, MarkdownSkill):
            continue
        if allowed is not None and skill.name not in allowed:
            continue
        r = skill._resolved
        markdown_skill_names.add(skill.name)
        skill_lines.append("  <skill>")
        skill_lines.append(f"    <name>{skill.name}</name>")
        skill_lines.append(f"    <description>{r.description}</description>")
        skill_lines.append(f"    <location>{str(r.file_path)}</location>")
        skill_lines.append("  </skill>")
    if not skill_lines:
        return ""
    lines = [
        "",
        "## Skills (mandatory)",
        "Before replying: scan <available_skills> <description> entries.",
        "- If exactly one skill clearly applies: call `read` on its <location>, then follow it.",
        "- If multiple could apply: choose the most specific one, then read/follow it.",
        "- If none clearly apply: do not read any SKILL.md.",
        "Constraints: never read more than one skill up front; only read after selecting.",
        "When a selected skill references relative paths, resolve them from the skill directory (parent of SKILL.md).",
        "Notes policy: prefer `notes` (workspace markdown files) for generic note-taking/reading.",
        "Only select `apple-notes` when the user explicitly asks for Apple Notes / Notes.app / iCloud Notes / `memo`.",
        "",
        "<available_skills>",
    ]
    if not ({"notes", "apple-notes"} <= markdown_skill_names):
        lines = [l for l in lines if not l.startswith("Notes policy:") and not l.startswith("Only select `apple-notes`")]
    lines.extend(skill_lines)
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
