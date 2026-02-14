"""Decide which skills to run for a message (intent-based, save tokens). Only run and show status for relevant skills."""
from __future__ import annotations


from app.skills.registry import get_all_skills
from app.skills.markdown_skill import MarkdownSkill

def get_skills_to_use(text: str, enabled_skill_ids: set[str], user_id: str = "default") -> set[str]:
    """Return subset of enabled skills that are relevant to this message. Saves tokens and shows only used tools."""
    out: set[str] = set()
    
    # 1. Iterate built-in skills and check eligibility.
    # Workspace Markdown skills are selected OpenClaw-style by the model from <available_skills>.
    for skill in get_all_skills():
        if isinstance(skill, MarkdownSkill):
            continue
        if skill.name in enabled_skill_ids:
            if skill.check_eligibility(text, user_id):
                out.add(skill.name)

    # 2. Refinements / conflicts (ported from original logic)
    
    # Spotify vs Lyrics logic: 
    # If "play" is in text, Spotify handles it, Lyrics shouldn't trigger unless explicitly asked.
    # Note: The LyricsSkill check_eligibility already handles "play " exclusion.
    # But checking conflict between spotify search vs lyrics search might still be needed if logic overlaps.
    
    # Lyrics specific cleanup: if lyrics is active, generic search/rag might need to be suppressed 
    # to avoid double-answering if the user asking for lyrics which look like a question.
    if "lyrics" in out:
        # If we are strictly looking for lyrics, don't fallback to RAG/Web unless necessary.
        # But wait, original logic discarded google_search/rag.
        # Let's keep that behavior?
        # "lyrics" skill returns lyrics text. RAG/Web return text.
        # If we have lyrics, we usually don't want a wikipedia summary of the song.
        out.discard("google_search")
        out.discard("rag")

    return out


# Emoji + label for each skill (for status message)
SKILL_STATUS_LABELS: dict[str, str] = {
    "time": "🕐 Checking time…",
    "weather": "🌤️ Checking weather…",
    "files": "📁 Checking files…",
    "drive": "📂 Checking Drive…",
    "rag": "📚 Checking learned knowledge…",
    "learn": "📖 Learning about topic…",
    "google_search": "🔍 Searching the web…",
    "lyrics": "🎵 Finding lyrics…",
    "spotify": "🎧 Searching Spotify…",
    "reminders": "⏰ Setting reminder…",
    "audio_notes": "🎤 Processing audio…",
    "self_awareness": "🧠 Checking self-knowledge…",
    "server_status": "🖥️ Checking server status…",
}
