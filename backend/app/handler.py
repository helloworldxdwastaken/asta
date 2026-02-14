"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import logging
import io
import json
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

# Short acknowledgments: when user sends only this, we nudge the model to reply with one phrase
_SHORT_ACK_PHRASES = frozenset({
    "ok", "okay", "thanks", "thank you", "thx", "bye", "got it", "no", "sure", "yep", "yes",
    "cool", "nice", "np", "alright", "k", "kk", "done", "good", "great", "perfect",
})

_DESKTOP_REQUEST_HINTS = (
    "desktop",
    "check my desktop",
    "list my desktop",
    "what files",
    "files on my desktop",
    "on my desktop",
    "screenshot files",
    "delete screenshots",
)

_EXEC_INTENT_HINTS = (
    "apple notes",
    "memo",
    "things",
    "things app",
    "things inbox",
)

_TOOL_CAPABLE_PROVIDERS = frozenset({"openai", "groq", "openrouter", "claude", "google"})


def _is_short_acknowledgment(text: str) -> bool:
    """True if the message is only a short acknowledgment (ok, thanks, etc.)."""
    t = (text or "").strip().lower()
    if len(t) > 25:
        return False
    # Exact match or single word/phrase from list
    if t in _SHORT_ACK_PHRASES:
        return True
    # "thanks!" or "ok." etc.
    base = t.rstrip(".!")
    if base in _SHORT_ACK_PHRASES:
        return True
    return False


def _is_desktop_request(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(k in t for k in _DESKTOP_REQUEST_HINTS)


def _is_exec_intent(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(k in t for k in _EXEC_INTENT_HINTS)


def _provider_supports_tools(provider_name: str) -> bool:
    return (provider_name or "").strip().lower() in _TOOL_CAPABLE_PROVIDERS


def _looks_like_reminder_set_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # List/status questions should not schedule.
    if any(
        q in t for q in (
            "do i have reminder",
            "do i have any reminder",
            "what reminders",
            "list reminders",
            "show reminders",
            "pending reminders",
            "any reminders",
        )
    ):
        return False
    return any(
        k in t for k in (
            "remind me",
            "set reminder",
            "set a reminder",
            "alarm at",
            "alarm for",
            "set alarm",
            "set an alarm",
            "wake me up",
            "set timer",
            "timer for",
        )
    )


def _summarize_directory_json(raw: str, max_items: int = 40) -> str | None:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        path = data.get("path") or "~/Desktop"
        entries = data.get("entries") or []
        if not isinstance(entries, list):
            return None
        dirs = [e for e in entries if isinstance(e, dict) and e.get("kind") == "dir"]
        files = [e for e in entries if isinstance(e, dict) and e.get("kind") == "file"]
        lines = [
            f"I checked `{path}`.",
            f"Found {len(dirs)} folder(s) and {len(files)} file(s).",
        ]
        shown = entries[:max_items]
        if shown:
            lines.append("")
            lines.append("Top entries:")
            for e in shown:
                if not isinstance(e, dict):
                    continue
                name = str(e.get("name") or "")
                kind = "dir" if e.get("kind") == "dir" else "file"
                size = e.get("size")
                if kind == "file" and isinstance(size, int):
                    lines.append(f"- {name} ({size} bytes)")
                else:
                    lines.append(f"- {name} ({kind})")
        if len(entries) > max_items:
            lines.append(f"...and {len(entries) - max_items} more.")
        return "\n".join(lines).strip()
    except Exception:
        return None


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
    # OpenClaw-style flow uses tool calls for capable providers; keep this as a fallback for providers without tools.
    if "reminders" in enabled and not _provider_supports_tools(provider_name):
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

    # OpenClaw-style: Apple Notes (and other exec) work only via the exec tool. Model calls exec(command);
    # we run it and return the result — no proactive run or context injection.

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
    # Built-in skills are intent-routed; workspace skills are selected by the model via <available_skills> + read tool.
    context = await build_context(db, user_id, cid, extra=extra, skills_in_use=skills_to_use)
    
    # Silly GIF skill: Proactive instruction (not intent-based)
    if "silly_gif" in enabled:
        context += (
            "\n\n[SKILL: SILLY GIF ENABLED]\n"
            "You can occasionally (10-20% chance) send a relevant GIF by adding `[gif: search term]` at the end of your message. "
            "Only do this when the mood is friendly or fun. Example: 'That's awesome! [gif: happy dance]'"
        )

    # Short acknowledgment: force a one-phrase reply (model often ignores SOUL otherwise)
    if _is_short_acknowledgment(text):
        context += (
            "\n\n[IMPORTANT] The user just sent a very short acknowledgment (e.g. ok, thanks). "
            "Reply with ONE short phrase only (e.g. 'Got it!', 'Anytime!', 'Take care!'). "
            "Do not add extra sentences like 'Let me know if you need anything.'"
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

    # Exec tool (Claw-style): when allowlist is non-empty, pass tool so model can call exec(command)
    from app.exec_tool import get_effective_exec_bins, get_exec_tool_openai_def, run_allowlisted_command, parse_exec_arguments
    effective_bins = await get_effective_exec_bins(db)
    # Guardrail: only expose exec when the user message is likely asking for an exec-backed workflow.
    # This prevents models (especially free ones) from misusing exec for unrelated requests.
    offer_exec = _is_exec_intent(text)
    tools = list(get_exec_tool_openai_def(effective_bins)) if (effective_bins and offer_exec) else []
    if effective_bins and offer_exec:
        logger.info("Exec allowlist: %s; passing tools to provider=%s", sorted(effective_bins), provider.name)
    elif "notes" in text.lower() or "memo" in text.lower():
        logger.warning("User asked for notes/memo but exec allowlist is empty (enable Apple Notes skill or set ASTA_EXEC_ALLOWED_BINS)")

    # Workspace read tool (OpenClaw-style skills): lets model read selected SKILL.md on demand.
    from app.workspace import discover_workspace_skills
    workspace_skill_names = {s.name for s in discover_workspace_skills()}
    has_enabled_workspace_skills = any(name in enabled for name in workspace_skill_names)
    if has_enabled_workspace_skills:
        from app.workspace_read_tool import get_workspace_read_tool_openai_def
        tools = tools + get_workspace_read_tool_openai_def()

    # Files tool: list_directory, read_file, allow_path — when user has Files skill so they can "check desktop" / request access
    if "files" in enabled:
        from app.files_tool import get_files_tools_openai_def
        tools = tools + get_files_tools_openai_def()
    # Reminders tool: status/list/add/remove (one-shot reminders)
    if "reminders" in enabled:
        from app.reminders_tool import get_reminders_tool_openai_def
        tools = tools + get_reminders_tool_openai_def()
    # Cron tool: status/list/add/update/remove for recurring jobs
    from app.cron_tool import get_cron_tool_openai_def
    tools = tools + get_cron_tool_openai_def()
    tools = tools if tools else None

    from app.providers.fallback import chat_with_fallback, get_available_fallback_providers
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model

    chat_kwargs = dict(
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )
    if tools:
        chat_kwargs["tools"] = tools

    response, provider_used = await chat_with_fallback(
        provider, messages, fallback_names, **chat_kwargs
    )
    if tools and provider_used:
        has_tc = bool(response.tool_calls)
        logger.info("Provider %s returned tool_calls=%s (count=%s)", provider_used.name, has_tc, len(response.tool_calls or []))

    # Tool-call loop: if model requested exec (or other tools), run and re-call same provider until done
    MAX_TOOL_ROUNDS = 3
    current_messages = list(messages)
    ran_exec_tool = False
    ran_files_tool = False
    reminder_tool_scheduled = False
    last_exec_stdout: str = ""
    for _ in range(MAX_TOOL_ROUNDS):
        if not response.tool_calls or not provider_used:
            break
        # Append assistant message (with content + tool_calls) and run each exec call
        asst_content = response.content or ""
        asst_tool_calls = response.tool_calls
        current_messages.append({
            "role": "assistant",
            "content": asst_content,
            "tool_calls": asst_tool_calls,
        })
        for tc in asst_tool_calls:
            fn = (tc.get("function") or {}) if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("function", {}).get("name")
            args_str = fn.get("arguments") or "{}"
            if name == "exec":
                params = parse_exec_arguments(args_str)
                cmd = (params.get("command") or "").strip()
                timeout_sec = params.get("timeout_sec")
                workdir = params.get("workdir") if isinstance(params.get("workdir"), str) else None
                logger.info("Exec tool called: command=%r", cmd)
                stdout, stderr, ok = await run_allowlisted_command(
                    cmd,
                    allowed_bins=effective_bins,
                    timeout_seconds=timeout_sec if isinstance(timeout_sec, int) else None,
                    workdir=workdir,
                )
                ran_exec_tool = True
                last_exec_stdout = stdout
                logger.info("Exec result: ok=%s stdout_len=%s stderr_len=%s", ok, len(stdout), len(stderr))
                if ok or stdout or stderr:
                    out = f"stdout:\n{stdout}\n" + (f"stderr:\n{stderr}\n" if stderr else "")
                else:
                    out = f"error: {stderr or 'Command not allowed or failed.'}"
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "list_directory":
                from app.files_tool import list_directory as list_dir, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await list_dir(path, user_id, db)
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "read_file":
                from app.files_tool import read_file_content as read_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await read_file_fn(path, user_id, db)
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "allow_path":
                from app.files_tool import allow_path as allow_path_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await allow_path_fn(path, user_id, db)
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "delete_file":
                from app.files_tool import delete_file as delete_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_file_fn(path, user_id, db, permanently=permanently)
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "delete_matching_files":
                from app.files_tool import (
                    delete_matching_files as delete_matching_files_fn,
                    parse_files_tool_args as parse_files_args,
                )
                params = parse_files_args(args_str)
                directory = (params.get("directory") or "").strip()
                glob_pattern = (params.get("glob_pattern") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_matching_files_fn(
                    directory,
                    glob_pattern,
                    user_id,
                    db,
                    permanently=permanently,
                )
                ran_files_tool = True
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "read":
                from app.workspace_read_tool import read_workspace_file, parse_workspace_read_args
                params = parse_workspace_read_args(args_str)
                path = (params.get("path") or "").strip()
                out = await read_workspace_file(path)
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "reminders":
                from app.reminders_tool import run_reminders_tool, parse_reminders_tool_args
                params = parse_reminders_tool_args(args_str)
                out = await run_reminders_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                if (params.get("action") or "").strip().lower() == "add":
                    try:
                        parsed = json.loads(out)
                        if isinstance(parsed, dict) and parsed.get("ok") is True:
                            reminder_tool_scheduled = True
                            extra["reminder_scheduled"] = True
                            extra["reminder_at"] = (
                                parsed.get("display_time")
                                or parsed.get("run_at")
                                or ""
                            )
                    except Exception:
                        pass
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            elif name == "cron":
                from app.cron_tool import run_cron_tool, parse_cron_tool_args
                params = parse_cron_tool_args(args_str)
                out = await run_cron_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
            else:
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": "Unknown tool."})
        # Re-call same provider with updated messages (no fallback switch); use that provider's model
        tool_kwargs = {**chat_kwargs}
        if provider_used.name == provider.name:
            tool_kwargs["model"] = user_model or None
        else:
            tool_kwargs["model"] = fallback_models.get(provider_used.name)
        # Give the model more time when it has to summarize large tool output (e.g. memo notes)
        if provider_used.name == "openrouter":
            tool_kwargs["timeout"] = 90
        response = await provider_used.chat(current_messages, **tool_kwargs)
        if response.error:
            break

    reply = (response.content or "").strip()

    # If there was a fatal error (Auth/RateLimit) and no content, show the error message to the user
    if not reply and response.error:
        reply = f"Error: {response.error_message or 'Unknown provider error'}"
    # OpenClaw-style: generic fallback when we ran exec but got no reply (no skill-specific hints)
    if not reply and ran_exec_tool:
        if last_exec_stdout:
            reply = "I ran the command and got output, but the model didn't return a reply. **Command output:**\n\n```\n"
            max_show = 2000
            excerpt = last_exec_stdout.strip()[:max_show] + ("…" if len(last_exec_stdout) > max_show else "")
            reply += excerpt + "\n```"
        else:
            reply = "I ran the command but didn't get a reply back. Try again or rephrase."

    
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
        # Safety: only honor legacy [ASTA_EXEC] fallback when current user message is clearly exec-intent.
        # Prevents unrelated requests (e.g. reminders/lists) from accidentally running stale exec commands.
        if _is_exec_intent(text):
            from app.exec_tool import get_effective_exec_bins, run_allowlisted_command
            effective_bins = await get_effective_exec_bins(db)
            for m in exec_matches:
                cmd = m.group(1).strip()
                stdout, stderr, ok = await run_allowlisted_command(cmd, allowed_bins=effective_bins)
                if ok or stdout or stderr:
                    exec_outputs.append(f"Command: {cmd}\nOutput:\n{stdout}\n" + (f"Stderr:\n{stderr}\n" if stderr else ""))
                else:
                    exec_outputs.append(f"Command: {cmd}\nError: {stderr or 'Command not allowed or failed.'}")
            if exec_outputs:
                exec_message = "[Command output from Asta]\n\n" + "\n---\n\n".join(exec_outputs)
                exec_message += "\n\nReply to the user based on this output. Do not use [ASTA_EXEC] in your reply."
                messages_plus = list(messages) + [{"role": "assistant", "content": reply}] + [{"role": "user", "content": exec_message}]
                response2, _ = await chat_with_fallback(
                    provider, messages_plus, fallback_names,
                    context=context, model=user_model or None,
                    _fallback_models=fallback_models,
                )
                if response2.content and not response2.error:
                    reply = response2.content
        # Always strip raw block from user-visible reply.
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

    # Reliability fallback: for tool-capable providers that skipped reminder tool calls,
    # schedule directly from parser so clear reminder intents still work.
    if (
        "reminders" in enabled
        and _provider_supports_tools(provider_name)
        and _looks_like_reminder_set_request(text)
        and not extra.get("reminder_scheduled")
        and not reminder_tool_scheduled
    ):
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)
            if reminder_result.get("reminder_scheduled"):
                when = (reminder_result.get("reminder_at") or "").strip()
                reply = f"Done. I set your reminder{f' for {when}' if when else ''}."
            elif reminder_result.get("reminder_needs_location"):
                reply = "I can set that, but I need your location/timezone first. Tell me your city and country."

    # Post-reply validation: AI claimed it set a reminder but we didn't
    if "reminders" in skills_to_use and not extra.get("reminder_scheduled"):
        lower = reply.lower()
        if any(p in lower for p in ("i've set a reminder", "i set a reminder", "reminder set", "i'll remind you", "i'll send you a message at")):
            reply += "\n\n_I couldn't parse that reminder. Try: \"remind me in 5 min to X\" or \"alarm in 5 min to take a shower\"_"

    # OpenClaw-style: single generic fallback when reply is empty (no skill-specific hints)
    if not reply or not reply.strip():
        reply = "I didn't get a reply back. Try again or rephrase."

    # Reliability fallback for desktop requests on models that skip tool calls:
    # do a real Desktop listing directly so reply is grounded in actual file system state.
    if _is_desktop_request(text) and "files" in enabled and not ran_files_tool:
        from app.files_tool import allow_path as allow_path_fn, list_directory as list_dir
        # Try listing directly; if not allowed, request/allow Desktop then list.
        desktop = "~/Desktop"
        listing = await list_dir(desktop, user_id, db)
        if "not in the allowed list" in listing.lower():
            await allow_path_fn(desktop, user_id, db)
            listing = await list_dir(desktop, user_id, db)
        summarized = _summarize_directory_json(listing)
        if summarized:
            reply = summarized
        elif listing.startswith("Error:"):
            reply = f"I couldn't check your Desktop yet: {listing}"

    # Always persist assistant reply (including errors) so web UI matches what user saw on Telegram
    await db.add_message(cid, "assistant", reply, provider.name if not reply.strip().startswith("Error:") and not reply.strip().startswith("No AI provider") else None)
    return reply
