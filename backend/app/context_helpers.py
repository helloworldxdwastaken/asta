"""Helper functions for generating context sections (extracted from context.py)."""
from __future__ import annotations
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.db import Db

import re

logger = logging.getLogger(__name__)

def _is_error_reply(text: str) -> bool:
    """Check if the assistant reply is an error message (to avoid feeding it back)."""
    if not text:
        return False
    t = text.strip().lower()
    return t.startswith("error:") or t.startswith("no ai provider")

def _is_time_reply(text: str) -> bool:
    """Check if the assistant reply is just a time announcement (to avoid feeding it)."""
    # e.g. "It is 12:00 PM."
    if not text:
        return False
    return bool(re.search(r"it is \d{1,2}:\d{2}", text, re.I))

def _get_server_status_section(extra: dict) -> list[str]:
    parts = []
    if extra and extra.get("server_status"):
        ss = extra["server_status"]
        if ss.get("ok"):
            parts.append("--- Server Status (REAL-TIME METRICS) ---")
            parts.append(f"CPU Usage: {ss['cpu_percent']}%")
            parts.append(f"RAM Usage: {ss['ram']['percent']}% ({ss['ram']['used_gb']}GB / {ss['ram']['total_gb']}GB)")
            parts.append(f"Disk Usage: {ss['disk']['percent']}% ({ss['disk']['used_gb']}GB / {ss['disk']['total_gb']}GB)")
            parts.append(f"System Uptime: {ss['uptime_str']}")
            parts.append(f"Asta Version: {ss.get('version', 'Unknown')}")
            parts.append("Use these exact values to answer 'server status' or 'system stats' questions. Do NOT say you cannot check.")
        else:
            parts.append("--- Server Status ---")
            parts.append(f"Status check failed: {ss.get('error')}")
        parts.append("")
    return parts


def _get_files_section(settings, extra: dict) -> list[str]:
    parts = []
    if settings.asta_allowed_paths:
        allowed = [p.strip() for p in settings.asta_allowed_paths.split(",") if p.strip()]
        parts.append("--- Local files ---")
        parts.append("Allowed paths: " + ", ".join(allowed[:5]))
        if extra and extra.get("files_summary"):
            parts.append(extra["files_summary"])
        parts.append("")
    return parts


def _get_drive_section(extra: dict) -> list[str]:
    parts = []
    if extra and extra.get("drive_summary"):
        parts.append("--- Google Drive ---")
        parts.append(extra["drive_summary"])
        parts.append("")
    return parts


def _get_memories_section(user_id: str) -> list[str]:
    from app.memories import load_user_memories
    mem_content = load_user_memories(user_id)
    parts = []
    if mem_content:
        parts.append("--- About you (memories) ---")
        parts.append(mem_content)
        parts.append("Use this when relevant. Do not contradict it. To add a memory, end your message with [SAVE: key: value]. Only save location or preferred name when the user explicitly shares them. Do not save interests, hobbies, concerns, or other personal details. Max 10 important facts total.")
        parts.append("")
    return parts


def _get_docs_section(extra: dict) -> list[str]:
    parts = []
    if extra and extra.get("asta_docs"):
        parts.append("--- Asta Documentation (Source Code & Manual) ---")
        parts.append(extra["asta_docs"])
        parts.append("")
        parts.append("Use the documentation above to answer questions about Asta's features, installation, or configuration. Be helpful and specific.")
        parts.append("CRITICAL: The documentation is ALREADY provided above. Do NOT say 'I will check the docs'. Answer valid questions immediately based on the text above.")
        parts.append("")
    return parts


def _get_past_meetings_section(extra: dict) -> list[str]:
    parts = []
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
    return parts


def _get_rag_section(extra: dict) -> list[str]:
    parts = []
    if extra and "learned_topics" in extra:
        topics_list = extra.get("learned_topics") or []
        parts.append("--- Topics actually learned (RAG store) ---")
        if topics_list:
            names = [t.get("topic", "") for t in topics_list if t.get("topic")]
            parts.append("The only topics you have learned (stored in RAG) are: " + (", ".join(names) if names else "none") + ".")
        else:
            parts.append("You have not learned any topics yet (RAG store is empty).")
        parts.append("When the user asks what you have learned, what you know about, or what topics you learned: ONLY mention the topics listed above. Do NOT claim to have learned about BPA, eSIM, or any other topic not in this list. If the list is empty or 'none', say you have not learned any topics yet.")
        parts.append("")

    if extra and extra.get("rag_summary"):
        parts.append("""
--- RELEVANT LEARNED KNOWLEDGE (RAG) ---
IMPORTANT: The following information comes from your internal knowledge base. 
You MUST prioritize this information over any web search results or general training data. 
If the user asks about a specific term like 'eSimo' and it appears below, use THIS definition, even if it contradicts external sources.
----------------------------------------
""")
        parts.append(extra["rag_summary"])
        parts.append("CRITICAL: The information above is the result of your check. DONT say 'I will check'. Answer immediately based on this.")
        parts.append("----------------------------------------")
    return parts


async def _get_effective_location(db: "Db", user_id: str) -> dict | None:
    """Helper to get location from DB or Memory + Geocoding."""
    loc = await db.get_user_location(user_id)
    if loc:
        return loc
    from app.memories import get_location_from_memories
    from app.time_weather import geocode
    loc_str = get_location_from_memories(user_id)
    if not loc_str:
        return None
    result = await geocode(loc_str)
    if not result:
        return None
    lat, lon, name = result
    await db.set_user_location(user_id, name, lat, lon)
    return {"location_name": name, "latitude": lat, "longitude": lon}


async def _get_time_section(db: "Db", user_id: str, extra: dict) -> list[str]:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.time_weather import get_current_time_utc_12h, get_timezone_for_coords
    
    parts = ["--- Time ---"]
    parts.append("Current time (UTC, 12-hour): " + get_current_time_utc_12h())
    
    loc = await _get_effective_location(db, user_id)
    if loc:
        parts.append(f"User's location: {loc['location_name']}.")
        try:
            tz_name = await get_timezone_for_coords(
                loc["latitude"], loc["longitude"], loc.get("location_name")
            )
            now_local = datetime.now(ZoneInfo(tz_name))
            hour = now_local.hour
            if hour == 0:
                hour12, am_pm = 12, "AM"
            elif hour < 12:
                hour12, am_pm = hour, "AM"
            elif hour == 12:
                hour12, am_pm = 12, "PM"
            else:
                hour12, am_pm = hour - 12, "PM"
            local_str = f"{hour12}:{now_local.minute:02d} {am_pm}"
            logger.info("Context Time Computed: %s for %s (TZ: %s)", local_str, loc['location_name'], tz_name)
            parts.append(f"User's LOCAL time is {local_str} in {loc['location_name']}. THIS IS THE LIVE VALUE — use it exactly.")
        except Exception:
            parts.append("If you cannot compute local time, you may fall back to UTC, but prefer the user's local time when answering.")
    else:
        parts.append("User has not set their location. If they ask for local time, ask where they are; when they reply with a place, the system will save it.")
    
    if extra.get("location_just_set"):
        parts.append(f"(User just set location to: {extra['location_just_set']}. Confirm briefly.)")
    
    parts.append("When the user asks what time it is: use ONLY the 'User's LOCAL time' value above. Do NOT use any time from recent conversation or memory — that may be wrong. Reply with the exact value from the Time section.")
    parts.append("")
    return parts


async def _get_weather_section(db: "Db", user_id: str, extra: dict) -> list[str]:
    from app.time_weather import fetch_weather_with_forecast, get_timezone_for_coords
    parts = ["--- Weather ---"]
    loc = await _get_effective_location(db, user_id)
    if loc:
        tz_str = await get_timezone_for_coords(
            loc["latitude"], loc["longitude"], loc.get("location_name")
        )
        forecast = await fetch_weather_with_forecast(
            loc["latitude"], loc["longitude"], timezone_str=tz_str
        )
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
    return parts


def _get_web_search_section(extra: dict) -> list[str]:
    parts = []
    results = extra.get("search_results") or []
    err = extra.get("search_error")
    if results:
        parts.append("--- Web search results (you HAVE direct web access; use these) ---")
        for i, r in enumerate(results[:5], 1):
            title = (r.get("title") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            url = (r.get("url") or "").strip()
            if title or snippet:
                parts.append(f"{i}. {title}: {snippet[:300]}" + (f" ({url})" if url else ""))
        parts.append("Answer from the above results. Do NOT say you cannot access the web or don't have internet—you do.")
    elif err:
        parts.append("--- Web search ---")
        parts.append(f"Search failed: {err}. Tell the user the search errored. Do NOT say you cannot access the web—Asta can search; the API failed.")
    elif "search_results" in extra:
        # Key exists but empty list -> no results found
        parts.append("--- Web search ---")
        parts.append("Search ran but returned no results. Tell the user nothing was found or suggest rephrasing. Do NOT say you cannot access the web—Asta can search.")
    parts.append("")
    return parts


def _get_lyrics_section(extra: dict) -> list[str]:
    parts = []
    if extra and extra.get("lyrics_searched_query"):
        if extra.get("lyrics_result"):
            lr = extra["lyrics_result"]
            parts.append("--- Lyrics ---")
            parts.append(f"Track: {lr.get('trackName', '')} by {lr.get('artistName', '')}")
            parts.append("Lyrics:")
            parts.append((lr.get("plainLyrics") or "")[:6000])
        else:
            parts.append("--- Lyrics ---")
            parts.append(f"We searched the lyrics database (LRCLIB) for \"{extra['lyrics_searched_query']}\" but found no match. Tell the user briefly that this track isn't in the database (song or artist may be missing or spelled differently). Suggest they double-check the title/artist or try another source.")
        parts.append("")
    return parts


def _get_spotify_section(extra: dict) -> list[str]:
    parts = []
    if not extra:
        return parts
        
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
    return parts


async def _get_reminders_section(db: "Db", user_id: str, extra: dict) -> list[str]:
    parts = ["--- Reminders ---"]
    if extra.get("reminder_needs_location"):
        parts.append("The user asked for a reminder at a specific time (e.g. '7am' or '6pm') but no location is set. Ask: 'Where are you? I need your location to set reminders in your timezone.' Do NOT schedule in UTC.")
        parts.append("")
        return parts

    pending = await db.get_pending_reminders_for_user(user_id, limit=10)
    if pending:
        parts.append("Current pending reminders (real):")
        for r in pending[:5]:
            msg = (r.get("message") or "").strip() or "—"
            run_at = r.get("run_at") or ""
            parts.append(f"  - {msg} at {run_at}")
        parts.append("Do NOT claim they have reminders not listed above.")
    parts.append("Phrases: 'Wake me up at 7am', 'Remind me at 6pm to X', 'Remind me in 30 min to X', 'alarm in 5 min to X'. If location set, times are in their timezone.")
    parts.append("")

    if extra.get("reminder_scheduled"):
        parts.append("--- Just scheduled ---")
        parts.append("You have scheduled a reminder for the user. Briefly confirm it (e.g. 'I'll wake you up at 7:00 AM' or 'I'll remind you at 6pm to call mom'). At the set time the user will get a friendly message on Telegram/WhatsApp or in the web panel.")
        parts.append("")
    return parts


def _get_learning_status_section(extra: dict) -> list[str]:
    parts = []
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
    return parts
