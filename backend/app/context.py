"""Build unified context for the AI: connections, recent chat, files, Drive, RAG."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db import Db

# Default user id when not in a multi-user setup
DEFAULT_USER_ID = "default"


async def build_context(
    db: "Db",
    user_id: str,
    conversation_id: str | None,
    extra: dict | None = None,
    skills_in_use: set[str] | None = None,
) -> str:
    """Build a context string the AI can use. If skills_in_use is set, only include those skill sections (saves tokens)."""
    extra = extra or {}
    only_skills = skills_in_use  # when set, we only add sections for these skills
    def _use(skill_id: str) -> bool:
        return only_skills is None or skill_id in only_skills
    mood = extra.get("mood") or "normal"
    _mood_map = {
        "serious": "Reply in a serious, professional tone. Be direct and factual.",
        "friendly": "Reply in a warm, friendly tone. Use a bit of warmth and personality.",
        "normal": "Reply in a balanced, helpful tone—neither stiff nor overly casual.",
    }
    mood_instruction = _mood_map.get(mood, _mood_map["normal"])

    parts = [
        "You are Asta, the user's agent. You use whichever AI model is configured (Groq, Gemini, Claude, Ollama) and have access to the user's connected services.",
        "TONE: " + mood_instruction,
        "Use the context below to understand what is connected and recent history.",
        "",
    ]

    # Recent conversation (last 10 messages). Skip assistant error replies so the model doesn't repeat "check your API key".
    def _is_error_reply(content: str) -> bool:
        s = (content or "").strip()
        if s.startswith("Error:") or s.startswith("No AI provider"):
            return True
        if "invalid or expired" in s and "API key" in s:
            return True
        if "API key" in s and ("check" in s.lower() or "update" in s.lower() or "renew" in s.lower()):
            return True
        return False

    if conversation_id:
        try:
            recent = await db.get_recent_messages(conversation_id, limit=10)
            if recent:
                parts.append("--- Recent conversation ---")
                for m in recent:
                    if m["role"] == "assistant" and _is_error_reply(m["content"]):
                        continue
                    role = "User" if m["role"] == "user" else "Assistant"
                    parts.append(f"{role}: {m['content'][:500]}")
                parts.append("")
        except Exception:
            pass

    # Connected channels
    channels = []
    from app.config import get_settings
    s = get_settings()
    from app.keys import get_api_key
    token = await get_api_key("telegram_bot_token")
    if token:
        channels.append("Telegram")
    channels.append("Web panel")
    parts.append("--- Connected ---")
    parts.append("Channels: " + ", ".join(channels))
    parts.append("")

    # Only include context for skills that are enabled (user can turn off in Skills tab)
    files_enabled = await db.get_skill_enabled(user_id, "files")
    drive_enabled = await db.get_skill_enabled(user_id, "drive")
    rag_enabled = await db.get_skill_enabled(user_id, "rag")
    time_enabled = await db.get_skill_enabled(user_id, "time")
    weather_enabled = await db.get_skill_enabled(user_id, "weather")
    google_search_enabled = await db.get_skill_enabled(user_id, "google_search")
    lyrics_enabled = await db.get_skill_enabled(user_id, "lyrics")
    spotify_enabled = await db.get_skill_enabled(user_id, "spotify")
    reminders_enabled = await db.get_skill_enabled(user_id, "reminders")

    # Files summary (allowed paths)
    if files_enabled and _use("files") and s.asta_allowed_paths:
        allowed = [p.strip() for p in s.asta_allowed_paths.split(",") if p.strip()]
        parts.append("--- Local files ---")
        parts.append("Allowed paths: " + ", ".join(allowed[:5]))
        if extra and extra.get("files_summary"):
            parts.append(extra["files_summary"])
        parts.append("")

    # Drive summary
    if drive_enabled and _use("drive") and extra and extra.get("drive_summary"):
        parts.append("--- Google Drive ---")
        parts.append(extra["drive_summary"])
        parts.append("")

    # Past meetings (saved when user chose "meeting notes"; user can ask "last meeting?" etc.)
    if extra and extra.get("past_meetings"):
        parts.append("--- Past meetings (saved) ---")
        for m in extra["past_meetings"][:5]:
            created = m.get("created_at") or ""
            title = m.get("title") or "Meeting"
            formatted = (m.get("formatted") or "")[:2000]
            parts.append(f"[{title} | {created}]")
            parts.append(formatted)
            parts.append("")
        parts.append("Use the above when the user asks about the last meeting, a previous meeting, or what was discussed. Answer from this context.")
        parts.append("")

    # Actual topics in RAG store — prevent the model from claiming it learned about topics that are not stored
    if rag_enabled and _use("rag") and extra and "learned_topics" in extra:
        topics_list = extra.get("learned_topics") or []
        parts.append("--- Topics actually learned (RAG store) ---")
        if topics_list:
            names = [t.get("topic", "") for t in topics_list if t.get("topic")]
            parts.append("The only topics you have learned (stored in RAG) are: " + (", ".join(names) if names else "none") + ".")
        else:
            parts.append("You have not learned any topics yet (RAG store is empty).")
        parts.append("When the user asks what you have learned, what you know about, or what topics you learned: ONLY mention the topics listed above. Do NOT claim to have learned about BPA, eSIM, or any other topic not in this list. If the list is empty or 'none', say you have not learned any topics yet.")
        parts.append("")

    # RAG / learned knowledge summary (retrieved chunks for this question)
    if rag_enabled and _use("rag") and extra and extra.get("rag_summary"):
        parts.append("--- Relevant learned knowledge ---")
        parts.append(extra["rag_summary"])
        parts.append("")

    # Time (separate skill)
    if time_enabled and _use("time"):
        from app.time_weather import get_current_time_utc_12h
        parts.append("--- Time ---")
        parts.append("Current time (UTC, 12-hour): " + get_current_time_utc_12h())
        parts.append("When the user asks for the time: start with a clock emoji and give the time in 12-hour AM/PM, one short line. Example: '🕐 11:25 PM in Holon.' or '🕐 It's 11:25 PM.' Do NOT explain UTC or timezone math.")
        loc = await db.get_user_location(user_id)
        if loc:
            parts.append(f"User's location: {loc['location_name']} (use for their local time).")
        else:
            parts.append("User has not set their location. If they ask for local time, ask where they are; when they reply with a place, the system will save it.")
        if extra.get("location_just_set"):
            parts.append(f"(User just set location to: {extra['location_just_set']}. Confirm briefly.)")
        parts.append("")

    # Weather (separate skill; includes today and tomorrow forecast)
    if weather_enabled and _use("weather"):
        from app.time_weather import fetch_weather_with_forecast
        parts.append("--- Weather ---")
        loc = await db.get_user_location(user_id)
        if loc:
            forecast = await fetch_weather_with_forecast(loc["latitude"], loc["longitude"])
            parts.append(f"User's location: {loc['location_name']}.")
            parts.append(f"Current: {forecast.get('current', 'unavailable')}.")
            parts.append(f"Today: {forecast.get('today', 'unavailable')}.")
            parts.append(f"Tomorrow: {forecast.get('tomorrow', 'unavailable')}.")
            parts.append("You can answer questions about current weather, today, or tomorrow (e.g. 'weather tomorrow'). Do not send the user to weather.com.")
        else:
            parts.append(
                "User has not set their location. If they ask for weather, ask where they are. "
                "When they reply with a place (e.g. 'London', 'Tokyo', 'I'm in Paris'), the system will save it; then you can give weather and forecast."
            )
        if extra.get("location_just_set"):
            parts.append(f"(User just set location to: {extra['location_just_set']}. Confirm briefly.)")
        parts.append("")

    # Web search results (when skill enabled and we ran a search)
    if google_search_enabled and _use("google_search") and extra and extra.get("search_results"):
        parts.append("--- Web search results ---")
        for i, r in enumerate(extra["search_results"][:5], 1):
            title = (r.get("title") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            url = (r.get("url") or "").strip()
            if title or snippet:
                parts.append(f"{i}. {title}: {snippet[:300]}" + (f" ({url})" if url else ""))
        parts.append("")

    # Lyrics (when skill enabled and we ran a search)
    if lyrics_enabled and _use("lyrics") and extra and extra.get("lyrics_searched_query"):
        if extra.get("lyrics_result"):
            lr = extra["lyrics_result"]
            parts.append("--- Lyrics ---")
            parts.append(f"Track: {lr.get('trackName', '')} by {lr.get('artistName', '')}")
            parts.append("Lyrics:")
            parts.append((lr.get("plainLyrics") or "")[:6000])
            parts.append("")
        else:
            parts.append("--- Lyrics ---")
            parts.append(f"We searched the lyrics database (LRCLIB) for \"{extra['lyrics_searched_query']}\" but found no match. Tell the user briefly that this track isn't in the database (song or artist may be missing or spelled differently). Suggest they double-check the title/artist or try another source.")
            parts.append("")

    # Spotify: search results or play (devices / connected status)
    if spotify_enabled and _use("spotify") and extra:
        if extra.get("spotify_reconnect_needed"):
            parts.append("--- Spotify play ---")
            parts.append("The user asked to play something. They had connected Spotify before but the connection is no longer valid (e.g. session expired or app credentials changed). Reply with ONE short sentence: tell them to go to Settings → Spotify and click 'Connect Spotify' again to re-authorize. Do NOT say they have never connected.")
            parts.append("")
        elif extra.get("spotify_play_connected") is False:
            parts.append("--- Spotify play ---")
            parts.append("The user asked to play something but has not connected their Spotify account. Reply with ONE short sentence: tell them to go to Settings → Spotify and click 'Connect Spotify' (one-time). After they connect, Asta WILL start playback on their devices — do NOT say you cannot control Spotify or that you can only give commands.")
            parts.append("")
        elif extra.get("spotify_play_connected") is True:
            parts.append("--- Spotify play ---")
            parts.append("The user HAS connected their Spotify account for playback. Do NOT tell them to connect or reconnect. Instead, either list devices to choose from or confirm playback started, based on the context above.")
            parts.append("")
        elif extra.get("spotify_devices") is not None and len(extra.get("spotify_devices", [])) == 0 and extra.get("spotify_play_track_uri"):
            parts.append("--- Spotify play ---")
            parts.append("No Spotify devices are available. Tell the user to open Spotify on a phone, computer, or speaker first, then ask again.")
            parts.append("")
        elif extra.get("spotify_play_failed"):
            dev = extra.get("spotify_play_failed_device") or "that device"
            parts.append("--- Spotify play ---")
            parts.append(f"Playback failed on {dev}. Reply briefly that it didn't start and suggest: open the Spotify app on that device (phone/computer/speaker), make sure they have Spotify Premium if required for 'play on device', then try again or pick another device.")
            parts.append("")
        elif extra.get("spotify_played_on"):
            parts.append("--- Spotify play ---")
            parts.append(f"Playing on {extra['spotify_played_on']}. Confirm briefly (e.g. 'Playing on {extra['spotify_played_on']}!').")
            parts.append("")
        if extra.get("spotify_skipped"):
            parts.append("--- Spotify control ---")
            parts.append("You skipped to the next track successfully. Briefly confirm (e.g. 'Skipped to the next track.').")
            parts.append("")
        if extra.get("spotify_volume_set"):
            parts.append("--- Spotify control ---")
            vol = extra.get("spotify_volume_value")
            if isinstance(vol, int):
                parts.append(f"You set the Spotify volume to {vol}%. Briefly confirm (e.g. 'Volume set to {vol}%.').")
            else:
                parts.append("You adjusted the Spotify volume successfully. Confirm briefly.")
            parts.append("")
        elif extra.get("spotify_devices") and len(extra["spotify_devices"]) >= 1:
            parts.append("--- Spotify play ---")
            dev_list = ", ".join(f"{i+1}. {d.get('name', 'Device')}" for i, d in enumerate(extra["spotify_devices"]))
            parts.append(f"Asta will start playback when the user picks a device. List: {dev_list}. Ask: 'On which device? 1. X, 2. Y — reply with the number or name.' When they reply, the system plays on that device. Do NOT say you cannot control Spotify.")
            parts.append("")
        elif extra.get("spotify_results"):
            parts.append("--- Spotify search results ---")
            for i, tr in enumerate(extra["spotify_results"][:5], 1):
                name = tr.get("name") or ""
                artist = tr.get("artist") or ""
                url = tr.get("url") or ""
                parts.append(f"{i}. {name}" + (f" — {artist}" if artist else "") + (f" {url}" if url else ""))
            parts.append("")

    # Reminders: user can ask to wake up or be reminded at a time
    if reminders_enabled and _use("reminders"):
        parts.append("--- Reminders ---")
        parts.append("The user can say e.g. 'Wake me up tomorrow at 7am', 'Remind me at 6pm to call mom', 'Remind me in 30 min to take the cake out'. You will send them a message at that time on Telegram/WhatsApp or web. If they have set their location, times are in their timezone.")
        parts.append("")

    if extra.get("reminder_scheduled"):
        parts.append("--- Just scheduled ---")
        parts.append("You have scheduled a reminder for the user. Briefly confirm it (e.g. 'I'll wake you up at 7:00 AM' or 'I'll remind you at 6pm to call mom'). At the set time the user will get a friendly message on Telegram/WhatsApp or in the web panel.")
        parts.append("")

    # Learn about X: user asked for duration (we will ask) or we started the job
    if extra.get("learn_about_ask_duration"):
        topic = extra["learn_about_ask_duration"]
        parts.append("--- Learn about (no duration) ---")
        parts.append(f"The user asked to learn about '{topic}' but did not say for how long. Ask briefly: 'For how long should I learn? (e.g. 30 minutes, 2 hours)'.")
        parts.append("")
    if extra.get("learn_about_started"):
        info = extra["learn_about_started"]
        topic = info.get("topic", "")
        duration = info.get("duration_minutes", 0)
        parts.append("--- Learn about (started) ---")
        parts.append(f"You started a background learning job: topic '{topic}' for {duration} minutes. Reply in one short sentence that you're learning about it and will notify them when done (e.g. 'I'll learn about {topic} for {duration} minutes and ping you when I'm done.'). Do NOT explain how RAG or search works.")
        parts.append("")

    parts.append("Answer using the above context when relevant. Be concise and helpful.")
    return "\n".join(parts)
