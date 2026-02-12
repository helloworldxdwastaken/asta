"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import logging
from app.context import build_context
from app.db import get_db
from app.providers.registry import get_provider
from app.reminders import send_skill_status
from app.time_weather import geocode, parse_location_from_message

# Services
from app.services.spotify_service import SpotifyService
from app.services.reminder_service import ReminderService
from app.services.learning_service import LearningService
from app.services.giphy_service import GiphyService
from app.server_status import get_server_status

logger = logging.getLogger(__name__)

async def handle_message(
    user_id: str,
    channel: str,
    text: str,
    provider_name: str = "default",
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
    # 1. Explicit syntax "I'm in Paris"
    location_place = parse_location_from_message(text)
    
    # 2. Check if we *asked* for location recently (pending request)
    if not location_place:
        if await db.get_pending_location_request(user_id):
            # Treat the entire text as a potential location (e.g. "Holon, Israel")
            # But skip if it's too long or looks like a command
            clean_text = text.strip()
            if len(clean_text) < 100 and " " in clean_text: # Simple heuristic: cities usually have short names, maybe allow single words too?
                 # Actually single word cities exist "London". Let's allow anything short enough.
                 location_place = clean_text
            elif len(clean_text) < 50:
                 location_place = clean_text
    
    if location_place:
        result = await geocode(location_place)
        if result:
            lat, lon, name = result
            await db.set_user_location(user_id, name, lat, lon)
            await db.clear_pending_location_request(user_id) # Clear flag
            extra["location_just_set"] = name
            # If we just set location, we might want to ACK it here or let the context know
        else:
            # If we were pending and failed to geocode, maybe we shouldn't clear? 
            # Or maybe we should to avoid getting stuck. Let's clear if it was an explicit "I'm in X" 
            # but if it was pending, maybe they said "No thanks". 
            # For now, let's just log and move on.
            if await db.get_pending_location_request(user_id):
                 await db.clear_pending_location_request(user_id) # Assume they replied something else


    # --- SERVICE CALLS ---

    # 1. Reminders
    reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
    if reminder_result:
        extra.update(reminder_result)

    # 2. Learning
    learning_result = await LearningService.process_learning(user_id, text, channel, channel_target)
    if learning_result:
        extra.update(learning_result)

    # 3. Spotify
    # Returns a string if it handled the request fully (e.g. "Playing X", "Skipped"); None otherwise.
    spotify_reply = await SpotifyService.handle_message(user_id, text, extra)
    if spotify_reply:
         await db.add_message(cid, "user", text)
         await db.add_message(cid, "assistant", spotify_reply, "script")
         return spotify_reply

    # --- END SERVICE CALLS ---

    # Intent-based skill selection: only run and show skills relevant to this message (saves tokens)
    from app.skill_router import get_skills_to_use, SKILL_STATUS_LABELS
    enabled = set()
    for sid in ("time", "weather", "files", "drive", "rag", "google_search", "lyrics", "spotify", "reminders", "audio_notes", "silly_gif", "self_awareness", "server_status"):
        if await db.get_skill_enabled(user_id, sid):
            enabled.add(sid)
    
    skills_to_use = get_skills_to_use(text, enabled)
    
    # Force include skills if services triggered them
    if extra.get("is_reminder"):
        skills_to_use = skills_to_use | {"reminders"}
    if extra.get("is_learning"):
        skills_to_use = skills_to_use | {"learn"}

    # If user asks for time/weather but no location (DB or User.md), ask for their location
    # REMOVED: fast-fail check. We now let it fall through to build_context, which has instructions
    # to ask for location if missing. This allows combined intents (e.g. "check notes and time")
    # to succeed on the "notes" part even if location is invalid.


    # Status: only the skills we're actually using, with emojis
    skill_labels = [SKILL_STATUS_LABELS[s] for s in skills_to_use if s in SKILL_STATUS_LABELS]
    if skill_labels and channel in ("telegram", "whatsapp") and channel_target:
        await send_skill_status(channel, channel_target, skill_labels)

    # RAG: only when relevant — retrieve context and actual learned topics (so the model cannot claim it learned things it didn't)
    rag_found_content = False
    if "rag" in skills_to_use:
        try:
            from app.rag.service import get_rag
            rag = get_rag()
            rag_summary = await rag.query(text, k=5)
            if rag_summary and len(rag_summary.strip()) > 10:
                # RAG found content - skip web search to avoid conflicting results
                rag_found_content = True
                extra["rag_summary"] = rag_summary
                if "google_search" in skills_to_use:
                    skills_to_use.discard("google_search")
                    logger.info(f"Skipping web search because RAG found {len(rag_summary)} chars of content")
            elif rag_summary:
                extra["rag_summary"] = rag_summary
            extra["learned_topics"] = rag.list_topics()
        except Exception:
            extra["learned_topics"] = []

    # Web search: only when relevant (and RAG didn't find good content)
    if "google_search" in skills_to_use:
        import asyncio
        from app.search_web import search_web
        results, err = await asyncio.to_thread(search_web, text, 5)
        extra["search_results"] = results
        extra["search_error"] = err

    # Server Status: only when relevant
    if "server_status" in skills_to_use:
        extra["server_status"] = get_server_status()

    # Lyrics: only when relevant
    if "lyrics" in skills_to_use:
        from app.lyrics import _extract_lyrics_query, fetch_lyrics
        q = _extract_lyrics_query(text)
        if q:
            extra["lyrics_searched_query"] = q
            extra["lyrics_result"] = await fetch_lyrics(q)

    # Self Awareness: Asta documentation (README.md + docs/*.md)
    if "self_awareness" in skills_to_use:
        t_lower = text.lower()
        if any(k in t_lower for k in ("asta", "help", "documentation", "manual", "how to use", "what is this", "what can you do", "features", "capabilities", "yourself", "who are you")):
            try:
                import os
                import glob
                # backend/app/handler.py -> ... -> asta root
                root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                docs = []
                
                # 1. README.md
                readme_path = os.path.join(root, "README.md")
                if os.path.exists(readme_path):
                    docs.append(f"--- README.md ---\n{open(readme_path, encoding='utf-8').read()}")
                
                # 2. docs/*.md
                docs_dir = os.path.join(root, "docs")
                if os.path.exists(docs_dir):
                    for f in sorted(glob.glob(os.path.join(docs_dir, "*.md"))):
                        name = os.path.basename(f)
                        content = open(f, encoding='utf-8').read()
                        docs.append(f"--- docs/{name} ---\n{content}")
                
                if docs:
                    extra["asta_docs"] = "\n\n".join(docs)
            except Exception as e:
                logger.error(f"Failed to read docs: {e}")

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
    
    # Build context (only sections for skills_in_use to save tokens)
    context = await build_context(db, user_id, cid, extra, skills_in_use=skills_to_use)
    
    # Silly GIF skill: Proactive instruction (not intent-based)
    if "silly_gif" in enabled:
        context += (
            "\n\n[SKILL: SILLY GIF ENABLED]\n"
            "You can occasionally (10-20% chance) send a relevant GIF by adding `[gif: search term]` at the end of your message. "
            "Only do this when the mood is friendly or fun. Example: 'That's awesome! [gif: happy dance]'"
        )
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
        if "Connect Spotify" in s or "connect your Spotify account" in s:
            return True
        return False

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in recent
        if not (m["role"] == "assistant" and is_error_reply(m["content"]))
    ]
    messages.append({"role": "user", "content": text})

    # Context compaction: summarize older messages if history is too long
    from app.compaction import compact_history
    provider_for_compact = get_provider(provider_name)
    if provider_for_compact:
        messages = await compact_history(messages, provider_for_compact, context=context)

    provider = get_provider(provider_name)
    if not provider:
        return f"No AI provider found for '{provider_name}'. Check your provider settings."
    user_model = await db.get_user_provider_model(user_id, provider.name)

    # Cross-provider fallback: if primary fails, try other configured providers
    from app.providers.fallback import chat_with_fallback, get_available_fallback_providers, is_error_reply as is_provider_error
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    # Collect each fallback's custom model (so we use the right model per provider)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model
    reply = await chat_with_fallback(
        provider, messages, fallback_names,
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
    )
    
    # Expand GIF tags
    if "[gif:" in reply:
        import re
        match = re.search(r"\[gif:\s*(.+?)\]", reply, re.IGNORECASE)
        if match:
             query = match.group(1).strip()
             gif_markdown = await GiphyService.get_gif(query)
             if gif_markdown:
                 reply = reply.replace(match.group(0), "\n" + gif_markdown)
             else:
                 reply = reply.replace(match.group(0), "") # Remove tag if failed

    # Extract and apply memories from [SAVE: key: value] in reply
    from app.memories import parse_save_instructions, strip_save_instructions, add_memory
    for k, v in parse_save_instructions(reply):
        add_memory(user_id, k, v)
    reply = strip_save_instructions(reply)

    # Post-reply validation: AI claimed it set a reminder but we didn't
    if "reminders" in skills_to_use and not extra.get("reminder_scheduled"):
        lower = reply.lower()
        if any(p in lower for p in ("i've set a reminder", "i set a reminder", "reminder set", "i'll remind you", "i'll send you a message at")):
            reply += "\n\n_I couldn't parse that reminder. Try: \"remind me in 5 min to X\" or \"alarm in 5 min to take a shower\"_"

    await db.add_message(cid, "user", text)
    if not (reply.strip().startswith("Error:") or reply.strip().startswith("No AI provider")):
        await db.add_message(cid, "assistant", reply, provider.name)
    return reply
