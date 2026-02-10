"""Decide which skills to run for a message (intent-based, save tokens). Only run and show status for relevant skills."""
from __future__ import annotations


def get_skills_to_use(text: str, enabled_skill_ids: set[str]) -> set[str]:
    """Return subset of enabled skills that are relevant to this message. Saves tokens and shows only used tools."""
    t = (text or "").strip().lower()
    out: set[str] = set()

    # Time: time-related or short location reply (so we can answer "what time" after they set location)
    if "time" in enabled_skill_ids:
        if any(k in t for k in ("time", "what time", "what's the time", "current time", "what time is it")):
            out.add("time")
        elif len(t) < 60 and "," in t:
            # Short reply might be a location ("Holon, Israel")
            out.add("time")
        elif len(t) < 40 and "?" in t:
            out.add("time")
    # Weather: weather, temperature, forecast, tomorrow
    if "weather" in enabled_skill_ids:
        if any(k in t for k in ("weather", "temperature", "forecast", "tomorrow", "today", "rain", "sunny", "temperature")):
            out.add("weather")
        elif len(t) < 60 and "," in t:
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

    # Reminders: wake me up, remind me at, alarm
    if "reminders" in enabled_skill_ids:
        if any(k in t for k in ("remind me", "wake me up", "wake up at", "alarm at", "wake up tomorrow", "remind me tomorrow")):
            out.add("reminders")

    # Web search: look up, search for (not spotify), what is, who is, when did, or question
    if "google_search" in enabled_skill_ids and "spotify" not in out:
        if any(k in t for k in ("search for", "look up", "find out", "what is ", "who is ", "when did", "latest ", "current ")):
            out.add("google_search")
        elif "?" in t and len(t) > 10:  # general question
            out.add("google_search")

    # Learn about X (for Y time): start background learning job
    if "rag" in enabled_skill_ids:
        if "learn about" in t:
            out.add("learn")
    # RAG (notes/learned): remember, notes, saved, learned, or question about knowledge
    if "rag" in enabled_skill_ids:
        if any(k in t for k in ("remember", "notes", "saved", "learned", "what did i", "my notes", "what did you learn", "what have you learned", "what do you know about")):
            out.add("rag")
        elif "?" in t and len(t) > 15:
            out.add("rag")

    # When the message is clearly a lyrics request, don't add generic question skills (so status shows only "Finding lyrics…")
    if "lyrics" in out and any(k in t for k in ("lyrics of", "lyrics for", "lyrics to", "what are the lyrics", "song lyrics", "get lyrics", "find lyrics")):
        out.discard("google_search")
        out.discard("rag")

    # Files: file, document, folder, path
    if "files" in enabled_skill_ids:
        if any(k in t for k in ("file", "files", "document", "folder", "path", "directory")):
            out.add("files")

    # Drive: drive, google drive
    if "drive" in enabled_skill_ids:
        if any(k in t for k in ("drive", "gdrive", "google drive")):
            out.add("drive")

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
}
