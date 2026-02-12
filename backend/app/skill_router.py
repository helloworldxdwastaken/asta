"""Decide which skills to run for a message (intent-based, save tokens). Only run and show status for relevant skills."""
from __future__ import annotations


def get_skills_to_use(text: str, enabled_skill_ids: set[str]) -> set[str]:
    """Return subset of enabled skills that are relevant to this message. Saves tokens and shows only used tools."""
    t = (text or "").strip().lower()
    out: set[str] = set()

    # Time: ONLY when explicitly asking about time (not for general questions)
    if "time" in enabled_skill_ids:
        if any(k in t for k in ("time", "what time", "what's the time", "current time", "what time is it", "clock")):
            out.add("time")
        elif len(t) < 60 and "," in t and not any(k in t for k in ("what is", "who is", "?")):
            # Short reply might be a location ("Holon, Israel") - but not if it's a question
            out.add("time")
    
    # Weather: weather, temperature, forecast, tomorrow
    if "weather" in enabled_skill_ids:
        if any(k in t for k in ("weather", "temperature", "forecast", "tomorrow", "today", "rain", "sunny", "temperature")):
            out.add("weather")
        elif len(t) < 60 and "," in t and not any(k in t for k in ("what is", "who is", "?")):
            out.add("weather")

    # Spotify: search or play — check first so "play X" doesn't trigger lyrics
    if "spotify" in enabled_skill_ids:
        if any(k in t for k in ("spotify", "search spotify", "find song", "find track", "search song", "search music", "on spotify", "in spotify")):
            out.add("spotify")
        if "play " in t:
            out.add("spotify")

    # Lyrics: only when explicitly asking for lyrics (not when asking to play music)
    if "lyrics" in enabled_skill_ids and "play " not in t:
        if any(k in t for k in ("lyrics for", "lyrics of", "find lyrics", "song lyrics", "get lyrics", " lyrics", " lyric ")):
            out.add("lyrics")
        elif any(k in t for k in ("song by", " by ", "artist ", "singer ")) and len(t) > 5:
            out.add("lyrics")

    # Reminders: wake me up, remind me at, alarm, timer
    if "reminders" in enabled_skill_ids:
        if any(k in t for k in ("remind me", "wake me up", "wake up at", "alarm at", "alarm in", "alarm or reminder", "alarm", "reminder", "timer", "wake up tomorrow", "remind me tomorrow", "min from now")):
            out.add("reminders")

    # Learn about X (for Y time): start background learning job
    if "rag" in enabled_skill_ids:
        if "learn about" in t:
            out.add("learn")
    
    # RAG (notes/learned): PRIORITY for "what is" questions - check learned knowledge first
    if "rag" in enabled_skill_ids:
        if any(k in t for k in ("remember", "notes", "saved", "learned", "what did i", "my notes", "what did you learn", "what have you learned", "what do you know about")):
            out.add("rag")
        elif any(k in t for k in ("what is ", "who is ", "what are ", "tell me about ")):
            # "What is X?" should check RAG first
            out.add("rag")
        elif "?" in t and len(t) > 15 and "time" not in out:
            # General questions check RAG (unless already handling time)
            out.add("rag")

    # Web search: AFTER RAG - look up, search for, check the web, or questions not handled by other skills
    # Skip if we're already handling time/spotify to keep answers focused
    if "google_search" in enabled_skill_ids and "spotify" not in out and "time" not in out:
        if any(k in t for k in (
            "search for", "look up", "find out", "latest ", "check the web", "search the web", "search online",
            "look it up", "search for ", "google ", "look up "
        )):
            out.add("google_search")
        elif any(k in t for k in ("what is ", "who is ", "when did ", "what are ", "tell me about ")):
            # Also add web search for "what is" questions (will work alongside RAG)
            out.add("google_search")
        elif "?" in t and len(t) > 10 and "rag" in out:
            # If RAG is already checking, also add web search as backup
            out.add("google_search")

    # When the message is clearly a lyrics request, don't add generic question skills (so status shows only "Finding lyrics…")
    if "lyrics" in out and any(k in t for k in ("lyrics of", "lyrics for", "lyrics to", "what are the lyrics", "song lyrics", "get lyrics", "find lyrics")):
        out.discard("google_search")
        out.discard("rag")

    # Files: file, document, folder, path, directory
    if "files" in enabled_skill_ids:
        if any(k in t for k in ("file", "files", "document", "folder", "path", "directory")):
            out.add("files")
            
    # Self Awareness: Asta documentation/help
    if "self_awareness" in enabled_skill_ids:
        if any(k in t for k in ("asta", "help", "documentation", "manual", "how to use", "what is this", "what can you do", "features", "capabilities", "yourself", "who are you")):
            out.add("self_awareness")

    # Drive: drive, google drive
    if "drive" in enabled_skill_ids:
        if any(k in t for k in ("drive", "gdrive", "google drive")):
            out.add("drive")

    # Server Status: CPU, RAM, Disk, Uptime, Status
    if "server_status" in enabled_skill_ids:
        if any(k in t for k in ("server status", "system stats", "cpu usage", "ram usage", "disk space", "uptime", "/status")):
            out.add("server_status")
        elif t == "status":
            out.add("server_status")

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
    "silly_gif": "🎬 Searching Giphy…",
}
