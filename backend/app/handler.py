"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import json

from app.context import build_context, DEFAULT_USER_ID
from app.db import get_db
from app.providers.registry import get_provider
from app.reminders import parse_reminder, schedule_reminder, send_skill_status
from app.time_weather import geocode, parse_location_from_message


async def handle_message(
    user_id: str,
    channel: str,
    text: str,
    provider_name: str = "groq",
    conversation_id: str | None = None,
    extra_context: dict | None = None,
    channel_target: str = "",
    mood: str | None = None,
) -> str:
    """Process one user message: context + AI + save. Schedules reminders when requested. Returns assistant reply.
    Asta is the agent; it uses whichever AI provider you set (Groq, Gemini, Claude, Ollama)."""
    db = get_db()
    await db.connect()
    cid = conversation_id or await db.get_or_create_conversation(user_id, channel)
    extra = extra_context or {}
    if mood is None:
        mood = await db.get_user_mood(user_id)
    extra["mood"] = mood
    if provider_name == "default":
        provider_name = await db.get_user_default_ai(user_id)

    # If user is setting their location (for time/weather skill), save it now
    location_place = parse_location_from_message(text)
    if location_place:
        result = await geocode(location_place)
        if result:
            lat, lon, name = result
            await db.set_user_location(user_id, name, lat, lon)
            extra["location_just_set"] = name

    # Parse reminder: "wake me up at 7am", "remind me tomorrow at 8am to X", etc.
    tz_str: str | None = None
    loc = await db.get_user_location(user_id)
    if loc:
        from app.time_weather import get_timezone_for_coords
        tz_str = await get_timezone_for_coords(loc["latitude"], loc["longitude"])
    reminder = parse_reminder(text, tz_str=tz_str)
    if reminder:
        run_at = reminder["run_at"]
        msg = reminder.get("message", "Reminder")
        target = channel_target or "web"
        rid = await schedule_reminder(user_id, channel, target, msg, run_at)
        extra["reminder_scheduled"] = True
        extra["reminder_at"] = (reminder.get("display_time") or run_at.strftime("%H:%M")) if run_at else ""

    # Learn about X for Y: parse intent, ask duration if missing, or start background learning job
    from app.learn_about import parse_learn_about, parse_duration_only
    from app.tasks.scheduler import schedule_learning_job
    pending_learn = await db.get_pending_learn_about(user_id)
    if pending_learn and parse_duration_only(text) is not None:
        duration_minutes = parse_duration_only(text)
        topic = pending_learn["topic"]
        await db.clear_pending_learn_about(user_id)
        job_id = schedule_learning_job(
            user_id, topic, duration_minutes,
            channel=channel, channel_target=channel_target or "web",
        )
        extra["learn_about_started"] = {"topic": topic, "duration_minutes": duration_minutes, "job_id": job_id}
    else:
        learn_intent = parse_learn_about(text)
        if learn_intent:
            if learn_intent.get("ask_duration"):
                await db.set_pending_learn_about(user_id, learn_intent["topic"])
                extra["learn_about_ask_duration"] = learn_intent["topic"]
            else:
                job_id = schedule_learning_job(
                    user_id,
                    learn_intent["topic"],
                    learn_intent["duration_minutes"],
                    channel=channel,
                    channel_target=channel_target or "web",
                )
                extra["learn_about_started"] = {
                    "topic": learn_intent["topic"],
                    "duration_minutes": learn_intent["duration_minutes"],
                    "job_id": job_id,
                }

    # Pending Spotify device choice: user replied "1", "2", "Kitchen", etc. → play on that device
    pending = await db.get_pending_spotify_play(user_id)
    if pending and len((text or "").strip()) < 40:
        try:
            devices = json.loads(pending.get("devices_json") or "[]")
            choice = (text or "").strip().lower()
            device_id = None
            device_name = None
            if choice.isdigit() and 1 <= int(choice) <= len(devices):
                idx = int(choice) - 1
                device_id = devices[idx].get("id")
                device_name = devices[idx].get("name")
            else:
                for d in devices:
                    if choice in (d.get("name") or "").lower():
                        device_id = d.get("id")
                        device_name = d.get("name")
                        break
            if device_id:
                from app.spotify_client import start_playback
                ok = await start_playback(user_id, device_id, pending["track_uri"])
                await db.clear_pending_spotify_play(user_id)
                if ok:
                    extra["spotify_played_on"] = device_name or "device"
                else:
                    extra["spotify_play_failed"] = True
                    extra["spotify_play_failed_device"] = device_name or "device"
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # Intent-based skill selection: only run and show skills relevant to this message (saves tokens)
    from app.skill_router import get_skills_to_use, SKILL_STATUS_LABELS
    enabled = set()
    for sid in ("time", "weather", "files", "drive", "rag", "google_search", "lyrics", "spotify", "reminders", "audio_notes"):
        if await db.get_skill_enabled(user_id, sid):
            enabled.add(sid)
    skills_to_use = get_skills_to_use(text, enabled)
    if reminder:
        skills_to_use = skills_to_use | {"reminders"}
    if extra.get("learn_about_started") or extra.get("learn_about_ask_duration"):
        skills_to_use = skills_to_use | {"learn"}

    # Status: only the skills we're actually using, with emojis
    skill_labels = [SKILL_STATUS_LABELS[s] for s in skills_to_use if s in SKILL_STATUS_LABELS]
    if skill_labels and channel in ("telegram", "whatsapp") and channel_target:
        await send_skill_status(channel, channel_target, skill_labels)

    # RAG: only when relevant — retrieve context and actual learned topics (so the model cannot claim it learned things it didn't)
    if "rag" in skills_to_use:
        try:
            from app.rag.service import get_rag
            rag = get_rag()
            rag_summary = await rag.query(text, k=5)
            if rag_summary:
                extra["rag_summary"] = rag_summary
            extra["learned_topics"] = rag.list_topics()
        except Exception:
            extra["learned_topics"] = []

    # Web search: only when relevant
    if "google_search" in skills_to_use:
        import asyncio
        from app.search_web import search_web
        extra["search_results"] = await asyncio.to_thread(search_web, text, 5)

    # Lyrics: only when relevant
    if "lyrics" in skills_to_use:
        from app.lyrics import _extract_lyrics_query, fetch_lyrics
        q = _extract_lyrics_query(text)
        if q:
            extra["lyrics_searched_query"] = q
            extra["lyrics_result"] = await fetch_lyrics(q)

    # Past meetings: when user asks about "last meeting" / "remember the meeting" etc., inject saved meeting notes
    if "audio_notes" in enabled:
        t_lower = (text or "").strip().lower()
        if any(
            phrase in t_lower
            for phrase in (
                "last meeting", "remember the meeting", "previous meeting", "past meeting",
                "what was discussed", "what was said in the meeting", "meeting with ", "meeting we had",
                "remind me what", "do you remember the meeting", "recall the meeting",
            )
        ):
            try:
                past = await db.get_recent_audio_notes(user_id, limit=5)
                if past:
                    extra["past_meetings"] = past
            except Exception:
                pass

    # Spotify: search, play, and basic controls (skip, volume)
    if "spotify" in skills_to_use:
        from app.spotify_client import (
            spotify_search_if_configured,
            _search_query_from_message,
            play_query_from_message,
            get_user_access_token,
            list_user_devices,
            start_playback,
            extract_playlist_uri,
            parse_volume_percent,
            skip_next_track,
            set_volume_percent,
        )
        t_lower = (text or "").strip().lower()

        # Skip / next track
        if any(k in t_lower for k in ("skip", "next song", "next track")):
            ok = await skip_next_track(user_id)
            extra["spotify_play_connected"] = True
            extra["spotify_skipped"] = ok

        # Volume control: set to N%
        vol = parse_volume_percent(text) if "volume" in t_lower or "turn it up" in t_lower or "turn it down" in t_lower else None
        if vol is not None:
            ok = await set_volume_percent(user_id, vol)
            extra["spotify_play_connected"] = True
            extra["spotify_volume_set"] = ok
            extra["spotify_volume_value"] = vol

        # Playlist play (when a playlist URI / URL is present)
        playlist_uri = extract_playlist_uri(text)
        play_query = play_query_from_message(text)
        if playlist_uri:
            token = await get_user_access_token(user_id)
            if not token:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    extra["spotify_reconnect_needed"] = True
                else:
                    extra["spotify_play_connected"] = False
            else:
                extra["spotify_play_connected"] = True
                # Play playlist context on active device
                ok = await start_playback(user_id, None, context_uri=playlist_uri)
                if ok:
                    extra["spotify_played_on"] = "active device"
                else:
                    extra["spotify_play_failed"] = True
                    extra["spotify_play_failed_device"] = "active device"

        elif play_query:
            token = await get_user_access_token(user_id)
            if not token:
                # Distinguish "never connected" vs "had tokens but refresh failed / credentials missing"
                row = await db.get_spotify_tokens(user_id)
                if row:
                    extra["spotify_reconnect_needed"] = True
                else:
                    extra["spotify_play_connected"] = False
            else:
                # User has a valid Spotify connection for playback
                extra["spotify_play_connected"] = True
                results = await spotify_search_if_configured(play_query)
                if not results or not results[0].get("uri"):
                    extra["spotify_results"] = []
                else:
                    track_uri = results[0]["uri"]
                    devices = await list_user_devices(user_id)
                    if not devices:
                        # No active devices – tell the model to ask user to open Spotify somewhere.
                        extra["spotify_devices"] = []
                        extra["spotify_play_track_uri"] = track_uri
                    elif len(devices) == 1:
                        # Exactly one device: play there automatically, no device picker.
                        dev = devices[0]
                        ok = await start_playback(user_id, dev.get("id"), track_uri)
                        if ok:
                            extra["spotify_played_on"] = dev.get("name") or "device"
                        else:
                            extra["spotify_play_failed"] = True
                            extra["spotify_play_failed_device"] = dev.get("name") or "device"
                    else:
                        # Multiple devices: store pending choice and let the model ask which one.
                        await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
                        extra["spotify_devices"] = devices
                        extra["spotify_pending_track_uri"] = track_uri
        else:
            query = _search_query_from_message(text)
            if query:
                extra["spotify_results"] = await spotify_search_if_configured(query)

    # Build context (only sections for skills_in_use to save tokens)
    context = await build_context(db, user_id, cid, extra, skills_in_use=skills_to_use)
    # Load recent messages; skip old assistant error messages so the model doesn't repeat "check your API key"
    recent = await db.get_recent_messages(cid, limit=20)

    def is_error_reply(content: str) -> bool:
        s = (content or "").strip()
        if s.startswith("Error:") or s.startswith("No AI provider"):
            return True
        if "invalid or expired" in s and "API key" in s:
            return True
        if "API key" in s and ("check" in s.lower() or "update" in s.lower() or "renew" in s.lower()):
            return True
        # Treat outdated Spotify connection prompts as transient guidance; don't persist them in history.
        if "Connect Spotify" in s or "connect your Spotify account" in s:
            return True
        return False

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in recent
        if not (m["role"] == "assistant" and is_error_reply(m["content"]))
    ]
    messages.append({"role": "user", "content": text})
    provider = get_provider(provider_name) or get_provider("groq") or get_provider("ollama")
    if not provider:
        return "No AI provider available. Set GROQ_API_KEY or run Ollama."
    # Use user's chosen model for this provider if set (Settings → Model), else provider default
    user_model = await db.get_user_provider_model(user_id, provider.name)
    reply = await provider.chat(messages, context=context, model=user_model or None)
    await db.add_message(cid, "user", text)
    # Don't save error messages as assistant replies — they pollute history and make the model repeat "check your API key" etc.
    if not (reply.strip().startswith("Error:") or reply.strip().startswith("No AI provider")):
        await db.add_message(cid, "assistant", reply, provider.name)
    return reply
