"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import logging
import io
import re
from PIL import Image
from app.context import build_context
from app.db import get_db
from app.providers.registry import get_provider
from app.providers.base import ProviderResponse, ProviderError
from app.reminders import send_skill_status
from app.time_weather import geocode, parse_location_from_message

# Services
from app.services.spotify_service import SpotifyService
from app.services.reminder_service import ReminderService
from app.services.learning_service import LearningService
from app.services.giphy_service import GiphyService

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
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> str:
    """Process one user message: context + AI + save. Schedules reminders when requested. Returns assistant reply.
    Asta is the agent; it uses whichever AI provider you set (Groq, Gemini, Claude, Ollama)."""
    db = get_db()
    await db.connect()

    # Image optimization: compress/resize to speed up API
    if image_bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Max dimension 1024px
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size))
            
            # Convert to RGB if necessary (e.g. RGBA/PNG to JPEG)
            if img.mode != "RGB":
                img = img.convert("RGB")
                
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=70, optimize=True)
            image_bytes = out_buf.getvalue()
            image_mime = "image/jpeg"
            logger.info("Image compressed: %d bytes", len(image_bytes))
        except Exception as e:
            logger.warning("Image compression failed: %s", e)

    cid = conversation_id or await db.get_or_create_conversation(user_id, channel)
    # Persist user message early so Telegram (and web) thread shows it even if handler or provider fails later
    user_content = f" [Image: {image_mime or 'image/jpeg'}] {text}" if image_bytes else text
    await db.add_message(cid, "user", user_content)
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

    # Build enabled skills early so we can gate service calls by toggle (built-in + workspace skills)
    from app.skills.registry import get_all_skills as _get_all_skills
    enabled = set()
    for skill in _get_all_skills():
        if await db.get_skill_enabled(user_id, skill.name):
            enabled.add(skill.name)

    # --- SERVICE CALLS (only when skill is enabled) ---

    # 1. Reminders
    if "reminders" in enabled:
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)

    # 2. Learning
    if "learn" in enabled:
        learning_result = await LearningService.process_learning(user_id, text, channel, channel_target)
        if learning_result:
            extra.update(learning_result)

    # 3. Spotify
    if "spotify" in enabled:
        spotify_reply = await SpotifyService.handle_message(user_id, text, extra)
        if spotify_reply:
            await db.add_message(cid, "assistant", spotify_reply, "script")
            return spotify_reply

    # --- END SERVICE CALLS ---

    # Intent-based skill selection: only run and show skills relevant to this message (saves tokens)
    from app.skill_router import get_skills_to_use, SKILL_STATUS_LABELS
    
    skills_to_use = get_skills_to_use(text, enabled)
    
    # When user says "yeah do that" / "yes" after AI offered to save to a file, include files skill
    if "files" in enabled and "files" not in skills_to_use:
        short_affirmation = text.strip().lower() in (
            "yeah", "yes", "do that", "ok", "sure", "go ahead", "please", "do it", "yep", "okay",
        ) or (len(text.strip()) < 25 and any(w in text.lower() for w in ("do it", "go ahead", "yes", "yeah", "ok", "sure")))
        if short_affirmation:
            recent = await db.get_recent_messages(cid, limit=3)
            if recent and recent[-1].get("role") == "assistant":
                last_content = (recent[-1].get("content") or "").lower()
                if any(k in last_content for k in ("save", "file", "write", "create a file", "save it to")):
                    skills_to_use = skills_to_use | {"files"}
                    logger.info("Including files skill for affirmation after save offer")
    
    # Force include skills if services triggered them
    if extra.get("is_reminder"):
        skills_to_use = skills_to_use | {"reminders"}
    if extra.get("is_learning"):
        skills_to_use = skills_to_use | {"learn"}
    if extra.get("location_just_set"):
        skills_to_use = skills_to_use | {"time", "weather"}

    # If user asks for time/weather but no location (DB or User.md), ask for their location
    # REMOVED: fast-fail check. We now let it fall through to build_context, which has instructions
    # to ask for location if missing. This allows combined intents (e.g. "check notes and time")
    # to succeed on the "notes" part even if location is invalid.


    # Status: only the skills we're actually using, with emojis (workspace skills get generic label)
    skill_labels = [SKILL_STATUS_LABELS.get(s, f"📄 Using {s}…") for s in skills_to_use]
    if skill_labels and channel in ("telegram", "whatsapp") and channel_target:
        await send_skill_status(channel, channel_target, skill_labels)

    # Execute skills to gather data (populate `extra`)
    from app.skills.registry import get_skill_by_name, get_all_skills

    # Sort skills: RAG before Google Search (Search sees RAG content); then registry order for stability
    priority_order = ["rag", "google_search"]
    skill_names = list(get_all_skills())
    name_to_idx = {s.name: i for i, s in enumerate(skill_names)}

    def _skill_sort_key(name: str) -> tuple[int, int]:
        prio = priority_order.index(name) if name in priority_order else 999
        idx = name_to_idx.get(name, 999)
        return (prio, idx)

    sorted_skills = sorted(skills_to_use, key=_skill_sort_key)
    logger.info("Executing skills: %s (Original: %s)", sorted_skills, skills_to_use)

    for skill_name in sorted_skills:
        skill = get_skill_by_name(skill_name)
        if skill:
            try:
                logger.info("Skill %s executing...", skill_name)
                skill_result = await skill.execute(user_id, text, extra)
                if skill_result:
                    logger.info("Skill %s returned data: %s", skill_name, list(skill_result.keys()))
                    extra.update(skill_result)
                else:
                    logger.debug("Skill %s returned None", skill_name)
            except Exception as e:
                logger.error("Skill %s execution failed: %s", skill_name, e, exc_info=True)

    # 4. Build Context (Prompt Engineering)
    # The new `build_context` signature takes `skills_in_use`.
    context = await build_context(db, user_id, cid, extra=extra, skills_in_use=skills_to_use)
    
    # Silly GIF skill: Proactive instruction (not intent-based)
    if "silly_gif" in enabled: 
        context += (
            "\n\n[SKILL: SILLY GIF ENABLED]\n"
            "You can occasionally (10-20% chance) send a relevant GIF by adding `[gif: search term]` at the end of your message. "
            "Only do this when the mood is friendly or fun. Example: 'That's awesome! [gif: happy dance]'"
        )

    # Load recent messages; skip old assistant error messages so the model doesn't repeat "check your API key"
    recent = await db.get_recent_messages(cid, limit=20)

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in recent
        # Simple heuristic for old string-based errors in DB, plus new structured ones if we saved them
        if not (m["role"] == "assistant" and (m["content"].startswith("Error:") or m["content"].startswith("No AI provider")))
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
    from app.providers.fallback import chat_with_fallback, get_available_fallback_providers
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    # Collect each fallback's custom model (so we use the right model per provider)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model

    response = await chat_with_fallback(
        provider, messages, fallback_names,
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )
    
    reply = response.content
    
    # If there was a fatal error (Auth/RateLimit) and no content, show the error message to the user
    if not reply and response.error:
         reply = f"Error: {response.error_message or 'Unknown provider error'}"

    
    # Expand GIF tags
    if "[gif:" in reply:
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

    # Claw-like exec: run allowlisted commands from [ASTA_EXEC: cmd][/ASTA_EXEC], then re-call model with output
    exec_pattern = re.compile(r"\[ASTA_EXEC:\s*([^\]]+)\]\s*\[/ASTA_EXEC\]", re.IGNORECASE)
    exec_matches = list(exec_pattern.finditer(reply))
    exec_outputs: list[str] = []
    if exec_matches:
        from app.exec_tool import run_allowlisted_command
        for m in exec_matches:
            cmd = m.group(1).strip()
            stdout, stderr, ok = await run_allowlisted_command(cmd)
            if ok or stdout or stderr:
                exec_outputs.append(f"Command: {cmd}\nOutput:\n{stdout}\n" + (f"Stderr:\n{stderr}\n" if stderr else ""))
            else:
                exec_outputs.append(f"Command: {cmd}\nError: {stderr or 'Command not allowed or failed.'}")
        if exec_outputs:
            exec_message = "[Command output from Asta]\n\n" + "\n---\n\n".join(exec_outputs)
            exec_message += "\n\nReply to the user based on this output. Do not use [ASTA_EXEC] in your reply."
            messages_plus = list(messages) + [{"role": "assistant", "content": reply}] + [{"role": "user", "content": exec_message}]
            response2 = await chat_with_fallback(
                provider, messages_plus, fallback_names,
                context=context, model=user_model or None,
                _fallback_models=fallback_models,
            )
            if response2.content and not response2.error:
                reply = response2.content
        # Strip any [ASTA_EXEC] blocks from reply so the user never sees the raw block
        reply = exec_pattern.sub("", reply).strip() or reply

    # Create file when AI outputs [ASTA_WRITE_FILE: path]...[/ASTA_WRITE_FILE]
    write_match = re.search(
        r"\[ASTA_WRITE_FILE:\s*([^\]]+)\]\s*\n?(.*?)\[/ASTA_WRITE_FILE\]",
        reply,
        re.DOTALL | re.IGNORECASE,
    )
    if write_match:
        file_path = write_match.group(1).strip()
        file_content = write_match.group(2).strip()
        try:
            from app.routers.files import write_to_allowed_path
            written = await write_to_allowed_path(user_id, file_path, file_content)
            reply = reply.replace(write_match.group(0), f"I've saved that to `{written}`.")
            logger.info("Created file via ASTA_WRITE_FILE: %s", written)
        except Exception as e:
            reply = reply.replace(write_match.group(0), f"I couldn't create that file: {e}.")
            logger.warning("ASTA_WRITE_FILE failed: %s", e)

    # Claw-style cron: [ASTA_CRON_ADD: name|cron_expr|tz|message][/ASTA_CRON_ADD] and [ASTA_CRON_REMOVE: name][/ASTA_CRON_REMOVE]
    cron_add_pattern = re.compile(r"\[ASTA_CRON_ADD:\s*([^\]]+)\]\s*\[/ASTA_CRON_ADD\]", re.IGNORECASE)
    for m in list(cron_add_pattern.finditer(reply)):
        raw = m.group(1).strip()
        parts = [p.strip() for p in raw.split("|", 3)]
        if len(parts) >= 3:
            name, cron_expr = parts[0], parts[1]
            tz = (parts[2] if len(parts) == 4 else None) or None
            message = parts[3] if len(parts) == 4 else parts[2]
            if name and cron_expr and message:
                try:
                    from app.cron_runner import add_cron_job_to_scheduler
                    from app.tasks.scheduler import get_scheduler
                    job_id = await db.add_cron_job(user_id, name, cron_expr, message, tz=tz, channel=channel, channel_target=channel_target)
                    add_cron_job_to_scheduler(get_scheduler(), job_id, cron_expr, tz)
                    reply = reply.replace(m.group(0), f"I've scheduled cron job \"{name}\" ({cron_expr}).")
                except Exception as e:
                    reply = reply.replace(m.group(0), f"I couldn't schedule the cron job: {e}.")
            else:
                reply = reply.replace(m.group(0), "I couldn't parse the cron job (need name|cron_expr|tz|message).")
        else:
            reply = reply.replace(m.group(0), "I couldn't parse the cron job (use name|cron_expr|tz|message).")
    cron_remove_pattern = re.compile(r"\[ASTA_CRON_REMOVE:\s*([^\]]+)\]\s*\[/ASTA_CRON_REMOVE\]", re.IGNORECASE)
    for m in list(cron_remove_pattern.finditer(reply)):
        name = m.group(1).strip()
        if name:
            try:
                from app.cron_runner import reload_cron_jobs
                deleted = await db.delete_cron_job_by_name(user_id, name)
                if deleted:
                    await reload_cron_jobs()
                    reply = reply.replace(m.group(0), f"I've removed the cron job \"{name}\".")
                else:
                    reply = reply.replace(m.group(0), f"No cron job named \"{name}\" found.")
            except Exception as e:
                reply = reply.replace(m.group(0), f"I couldn't remove the cron job: {e}.")
        else:
            reply = reply.replace(m.group(0), "I couldn't parse the cron job name.")

    # Post-reply validation: AI claimed it set a reminder but we didn't
    if "reminders" in skills_to_use and not extra.get("reminder_scheduled"):
        lower = reply.lower()
        if any(p in lower for p in ("i've set a reminder", "i set a reminder", "reminder set", "i'll remind you", "i'll send you a message at")):
            reply += "\n\n_I couldn't parse that reminder. Try: \"remind me in 5 min to X\" or \"alarm in 5 min to take a shower\"_"

    # Always persist assistant reply (including errors) so web UI matches what user saw on Telegram
    await db.add_message(cid, "assistant", reply, provider.name if not reply.strip().startswith("Error:") and not reply.strip().startswith("No AI provider") else None)
    return reply
