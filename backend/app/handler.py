"""Core message handler: build context, call AI, persist. Handles mood and reminders."""
import asyncio
import logging
import io
import json
import re
from typing import Any
from PIL import Image
from app.context import build_context
from app.db import get_db
from app.providers.registry import get_provider
from app.providers.base import ProviderResponse, ProviderError
from app.reminders import send_skill_status, send_notification
from app.time_weather import geocode, parse_location_from_message

# Services
from app.services.reminder_service import ReminderService
from app.services.learning_service import LearningService
from app.services.giphy_service import GiphyService
from app.stream_state_machine import AssistantStreamStateMachine
from app.thinking_capabilities import supports_xhigh_thinking

# Extracted modules — pure utilities with no DB/async I/O
from app.handler_thinking import (
    _THINK_LEVELS, _REASONING_MODES, _FINAL_MODES, _STRICT_FINAL_UNSUPPORTED_PROVIDERS,
    _THINK_DIRECTIVE_PATTERN, _REASONING_DIRECTIVE_PATTERN, _REASONING_QUICK_TAG_RE,
    _REASONING_FINAL_TAG_RE, _REASONING_THINK_TAG_RE,
    _strip_think_blocks, _longest_common_prefix_size, _largest_suffix_prefix_overlap,
    _merge_stream_source_text, _compute_incremental_delta, _plan_stream_text_update,
    _thinking_instruction, _normalize_thinking_level, _normalize_reasoning_mode,
    _parse_inline_thinking_directive, _parse_inline_reasoning_directive,
    _supports_xhigh_thinking, _format_thinking_options, _reasoning_instruction,
    _final_tag_instruction, _parse_fenced_code_regions, _is_inside_code_region,
    _parse_inline_code_regions, _build_code_regions, _strip_pattern_outside_code,
    _apply_reasoning_trim, _extract_final_tag_content, _strip_reasoning_tags_from_text,
    _extract_thinking_from_tagged_text, _extract_thinking_from_tagged_stream,
    _format_reasoning_message, _extract_reasoning_blocks,
)
from app.tool_call_parser import (
    _TOOL_TRACE_GROUP, _TOOL_TRACE_DEFAULT_ACTION, _MUTATING_TOOL_NAMES,
    _MUTATING_ACTION_NAMES, _RECOVERABLE_TOOL_ERROR_KEYWORDS,
    _build_tool_trace_label, _dedupe_keep_order, _render_tool_trace,
    _extract_tool_error_message, _is_recoverable_tool_error, _is_likely_mutating_tool_call,
    _build_tool_action_fingerprint, _tool_names_from_defs, _parse_inline_tool_args,
    _extract_textual_tool_calls, _has_tool_call_markup, _strip_tool_call_markup,
    _strip_bracket_tool_protocol,
)

# Extracted handler modules
from app.handler_vision import (
    _extract_inline_image, _extract_pdf_text, _preprocess_document_tags,
    _preprocess_document_tags_async, _extract_native_pdf_documents,
    _run_vision_preprocessor, _INLINE_IMAGE_RE, _NATIVE_VISION_PROVIDERS,
    _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE,
)
from app.handler_streaming import (
    _emit_live_stream_event, _emit_tool_event, _make_status_message,
    _emit_stream_status, _sanitize_silent_reply_markers,
    _emit_reasoning_stream_progressively, _STATUS_PREFIX, _SILENT_REPLY_TOKEN,
)
from app.handler_intent import (
    _is_short_acknowledgment, _is_exec_intent, _is_exec_check_request,
    _is_explicit_apple_notes_request, _is_note_capture_request,
    _is_workspace_notes_list_request, _sanitize_note_path_component,
    _canonicalize_note_write_path, _provider_supports_tools,
    _provider_supports_strict_final, _looks_like_files_check_request,
    _looks_like_image_generation_request, _reply_claims_image_tool_unavailable,
    _extract_image_markdown_from_tool_output, _extract_path_hint,
    _infer_files_directory, _extract_files_search_term, _name_matches_query,
    _looks_like_command_request, _TOOL_CAPABLE_PROVIDERS, _SHORT_ACK_PHRASES,
    _IMAGE_GEN_REQUEST_VERBS, _IMAGE_GEN_REQUEST_OBJECTS,
)
from app.handler_security import (
    _strip_shell_command_leakage, _redact_local_paths,
    _redact_sensitive_reply_content, _load_sensitive_key_values,
    _SENSITIVE_DB_KEY_NAMES,
)
from app.handler_learning import (
    _learn_help_text, _parse_learn_command, _handle_learn_command,
    _subagents_help_text,
)
from app.handler_subagents import (
    _looks_like_auto_subagent_request, _maybe_auto_spawn_subagent,
    _parse_subagents_command, _handle_subagents_command,
)
from app.handler_scheduler import (
    _handle_scheduler_intents, _looks_like_reminder_set_request,
    _looks_like_reminder_list_request, _looks_like_cron_list_request,
    _looks_like_schedule_overview_request, _looks_like_remove_request,
    _looks_like_update_request, _handle_files_check_fallback,
    _handle_workspace_notes_list_fallback, _get_trace_settings,
    _extract_textual_cron_add_protocol, _extract_bracket_cron_add_protocols,
)
from app.handler_context import (
    _append_selected_agent_context, _selected_agent_skill_filter,
    _run_project_update_tool,
)

logger = logging.getLogger(__name__)

# Constants used directly in handle_message
_GIF_COOLDOWN_SECONDS = 30 * 60


async def _generate_conversation_title(
    cid: str,
    user_text: str,
    assistant_reply: str,
    provider_name: str,
) -> None:
    """Generate an AI title for a new conversation and persist it.
    Fires as a background task after the first exchange completes.
    """
    try:
        db = get_db()
        # Guard: skip if title already set (e.g. parallel request)
        existing = await db.get_conversation_title(cid)
        if existing:
            return
        provider = get_provider(provider_name)
        # Strip <think> blocks from the reply before using as context, and disable
        # thinking for this call so the response itself won't contain reasoning blocks.
        clean_reply = _strip_think_blocks(assistant_reply)
        snippet = (user_text[:300] + "\n\n" + clean_reply[:300]).strip()
        messages = [
            {
                "role": "user",
                "content": (
                    "Give this conversation a short title (3–6 words, sentence case, "
                    "no punctuation at the end). Reply with ONLY the title, nothing else.\n\n"
                    + snippet
                ),
            }
        ]
        response = await provider.chat(messages, thinking_level="off", reasoning_mode="off")
        if response.error:
            logger.debug("Auto-title provider error: %s", response.error_message or response.error)
            return
        raw = _strip_think_blocks(response.content or "")
        title = raw.strip().strip('"').strip("'")
        if len(title) > 80:
            title = title[:80]
        # Fallback: if model only generated thinking with no output (e.g. Ollama/DeepSeek),
        # derive a title from the user's message instead.
        if not title:
            words = user_text.strip().split()
            title = " ".join(words[:7])
            if len(user_text.split()) > 7:
                title += "…"
            title = title[:80]
        if title:
            await db.set_conversation_title(cid, title)
            logger.debug("Auto-titled conversation %s → %r", cid, title)
    except Exception as e:
        logger.debug("Could not auto-title conversation %s: %s", cid, e)


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
    _out: dict | None = None,
    user_role: str = "admin",
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

    # Extract inline image early — before any text processing touches the huge base64 blob
    if not image_bytes:
        text, inline_img, inline_mime = _extract_inline_image(text)
        if inline_img:
            image_bytes = inline_img
            image_mime = inline_mime
            logger.info("Extracted inline image from text (%d bytes, %s)", len(inline_img), inline_mime)
            try:
                img = Image.open(io.BytesIO(image_bytes))
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                out_buf = io.BytesIO()
                img.save(out_buf, format="JPEG", quality=70, optimize=True)
                image_bytes = out_buf.getvalue()
                image_mime = "image/jpeg"
                logger.info("Inline image compressed: %d bytes", len(image_bytes))
            except Exception as e:
                logger.warning("Inline image compression failed: %s", e)

    raw_user_text = text
    cid = conversation_id or await db.get_or_create_conversation(user_id, channel)
    # Persist user message early so Telegram (and web) thread shows it even if handler or provider fails later
    user_content = f" [Image: {image_mime or 'image/jpeg'}] {text}" if image_bytes else text
    await db.add_message(cid, "user", user_content)
    extra = extra_context or {}
    try:
        # Named-agent routing syntax from UI: "@Agent Name: message".
        from app.routers.agents import resolve_agent_mention_in_text
        from app.agent_knowledge import (
            ensure_agent_knowledge_layout,
            retrieve_agent_knowledge_snippets,
        )

        selected_agent, cleaned_text = await resolve_agent_mention_in_text(text, user_id=user_id, user_role=user_role)
        if selected_agent:
            text = (cleaned_text or "").strip() or text
            aid = str(selected_agent.get("id") or "").strip()
            selected_payload = {
                "id": aid,
                "name": str(selected_agent.get("name") or "").strip(),
                "description": str(selected_agent.get("description") or "").strip(),
                "system_prompt": str(selected_agent.get("system_prompt") or "").strip(),
            }
            agent_skills_raw = selected_agent.get("skills")
            if isinstance(agent_skills_raw, list):
                agent_skills = [
                    str(s).strip().lower()
                    for s in agent_skills_raw
                    if str(s).strip()
                ]
                if agent_skills_raw == []:
                    selected_payload["skills"] = []
                elif agent_skills:
                    selected_payload["skills"] = list(dict.fromkeys(agent_skills))
            knowledge_path = ensure_agent_knowledge_layout(aid)
            if knowledge_path:
                selected_payload["knowledge_path"] = str(knowledge_path)
            extra["selected_agent"] = selected_payload

            # Agent-scoped model/thinking defaults (unless subagent overrides are explicit).
            agent_model = str(selected_agent.get("model") or "").strip()
            if agent_model and not extra.get("subagent_model_override"):
                extra["agent_model_override"] = agent_model
            agent_thinking = str(selected_agent.get("thinking") or "").strip().lower()
            if agent_thinking and not extra.get("subagent_thinking_override"):
                extra["agent_thinking_override"] = agent_thinking

            snippets = retrieve_agent_knowledge_snippets(agent_id=aid, query=text)
            if snippets:
                extra["agent_knowledge_snippets"] = snippets
                logger.info(
                    "Agent knowledge: selected=%s snippets=%d query=%r",
                    aid,
                    len(snippets),
                    text[:120],
                )
            logger.info("Agent routing: selected=%s name=%s", aid, selected_payload.get("name") or aid)
    except Exception as e:
        logger.warning("Agent routing/knowledge failed: %s", e)

    stream_event_callback = extra.get("_stream_event_callback")
    if not callable(stream_event_callback):
        stream_event_callback = None
    stream_events_enabled = bool(stream_event_callback) and (channel or "").strip().lower() == "web"
    live_stream_machine: AssistantStreamStateMachine | None = None
    if mood is None:
        mood = await db.get_user_mood(user_id)
    extra["mood"] = mood
    thinking_level = await db.get_user_thinking_level(user_id)
    thinking_override = (
        extra.get("subagent_thinking_override")
        or extra.get("agent_thinking_override")
        or ""
    ).strip().lower()
    if thinking_override in _THINK_LEVELS:
        thinking_level = thinking_override
    extra["thinking_level"] = thinking_level
    reasoning_mode = await db.get_user_reasoning_mode(user_id)
    extra["reasoning_mode"] = reasoning_mode
    reasoning_mode_norm = (reasoning_mode or "").strip().lower()
    final_mode = await db.get_user_final_mode(user_id)
    if final_mode not in _FINAL_MODES:
        final_mode = "off"
    extra["final_mode"] = final_mode
    if provider_name == "default":
        provider_name = await db.get_user_default_ai(user_id)
    strict_final_mode_requested = final_mode == "strict"
    strict_final_mode_enabled = (
        strict_final_mode_requested
        and _provider_supports_strict_final(provider_name)
    )
    if strict_final_mode_requested and not strict_final_mode_enabled:
        logger.info(
            "Strict final mode requested but disabled for provider=%s (OpenClaw-style provider guardrail).",
            provider_name,
        )

    # OpenClaw-style inline directives:
    # - /t <level>, /think:<level>, /thinking <level>
    # - /reasoning <off|on|stream>, /reason <mode>
    # - supports mixed text (e.g. "please /think high run this")
    # - /think (query current level)
    # - /reasoning (query current mode)
    model_override = (
        extra.get("subagent_model_override")
        or extra.get("agent_model_override")
        or ""
    ).strip()
    directive_model = model_override or await db.get_user_provider_model(user_id, provider_name)
    think_options = _format_thinking_options(provider_name, directive_model)

    directive_text = text
    think_matched, think_level, think_raw_level, think_rest = _parse_inline_thinking_directive(directive_text)
    if think_matched:
        directive_text = think_rest
    reasoning_matched, reasoning_level, reasoning_raw_level, reasoning_rest = _parse_inline_reasoning_directive(directive_text)
    if reasoning_matched:
        directive_text = reasoning_rest

    if think_matched:
        if think_raw_level is None:
            reply = (
                f"Current thinking level: {thinking_level}. "
                f"Options: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if think_level not in _THINK_LEVELS:
            reply = (
                f'Unrecognized thinking level "{think_raw_level}". '
                f"Valid levels: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if think_level == "xhigh" and not _supports_xhigh_thinking(provider_name, directive_model):
            reply = (
                'Thinking level "xhigh" is not supported for your current model. '
                f"Valid levels: {think_options}."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        await db.set_user_thinking_level(user_id, think_level)
        thinking_level = await db.get_user_thinking_level(user_id)
        extra["thinking_level"] = thinking_level

    if reasoning_matched:
        if reasoning_raw_level is None:
            reply = (
                f"Current reasoning mode: {reasoning_mode}. "
                "Options: off, on, stream."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        if reasoning_level not in _REASONING_MODES:
            reply = (
                f'Unrecognized reasoning mode "{reasoning_raw_level}". '
                "Valid levels: off, on, stream."
            )
            await db.add_message(cid, "assistant", reply, "script")
            return reply
        await db.set_user_reasoning_mode(user_id, reasoning_level)
        reasoning_mode = await db.get_user_reasoning_mode(user_id)
        extra["reasoning_mode"] = reasoning_mode
        reasoning_mode_norm = (reasoning_mode or "").strip().lower()

    if think_matched or reasoning_matched:
        text = directive_text
        if not text:
            parts: list[str] = []
            if think_matched and think_raw_level is not None:
                parts.append(f"Thinking level set to {thinking_level}.")
            if reasoning_matched and reasoning_raw_level is not None:
                parts.append(f"Reasoning mode set to {reasoning_mode}.")
            reply = " ".join(parts).strip() or "OK."
            await db.add_message(cid, "assistant", reply, "script")
            return reply

    # OpenClaw-style explicit subagent command UX (single-user):
    # /subagents list|spawn|info|send|stop
    subagents_cmd_reply = await _handle_subagents_command(
        text=text,
        user_id=user_id,
        conversation_id=cid,
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
    )
    if subagents_cmd_reply is not None:
        await db.add_message(cid, "assistant", subagents_cmd_reply, "script")
        return subagents_cmd_reply

    # Learn command - explicit /learn X only (not automatic from conversation)
    learn_cmd_reply = await _handle_learn_command(
        user_id=user_id,
        text=text,
        channel=channel,
        channel_target=channel_target,
    )
    if learn_cmd_reply is not None:
        await db.add_message(cid, "assistant", learn_cmd_reply, "script")
        return learn_cmd_reply

    auto_subagent_reply = await _maybe_auto_spawn_subagent(
        user_id=user_id,
        conversation_id=cid,
        text=text,
        provider_name=provider_name,
        channel=channel,
        channel_target=channel_target,
    )
    if auto_subagent_reply is not None:
        await db.add_message(cid, "assistant", auto_subagent_reply, "script")
        return auto_subagent_reply

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
    agent_skill_filter = _selected_agent_skill_filter(extra)
    if agent_skill_filter is not None:
        enabled &= set(agent_skill_filter)
        logger.info(
            "Applied selected-agent skill filter: allowed=%s enabled_after_filter=%s",
            agent_skill_filter,
            sorted(enabled),
        )

    # --- SERVICE CALLS (only when skill is enabled) ---

    # 1. Reminders
    # OpenClaw-style flow uses tool calls for capable providers; keep this as a fallback for providers without tools.
    if "reminders" in enabled and not _provider_supports_tools(provider_name):
        reminder_result = await ReminderService.process_reminder(user_id, text, channel, channel_target)
        if reminder_result:
            extra.update(reminder_result)

    # 2. Learning - DISABLED: automatic "learn about X" from conversation removed
    # Only /learn command now triggers learning (handled above)
    # if "learn" in enabled:
    #     learning_result = await LearningService.process_learning(user_id, text, channel, channel_target)
    #     if learning_result:
    #         extra.update(learning_result)

    # 3. Spotify: populate connection status in extra so context section can inform the LLM.
    # Actual Spotify actions are handled via the spotify LLM tool (Option B - tool-based).
    if "spotify" in enabled:
        from app.spotify_client import get_user_access_token as _spotify_get_token
        _spotify_token = await _spotify_get_token(user_id)
        if _spotify_token:
            extra["spotify_play_connected"] = True
        else:
            _spotify_row = await db.get_spotify_tokens(user_id)
            if _spotify_row:
                extra["spotify_reconnect_needed"] = True
            else:
                extra["spotify_play_connected"] = False

    # --- END SERVICE CALLS ---

    # Intent-based skill selection: only run and show skills relevant to this message (saves tokens)
    # Strip inline images and document tags so base64 blobs don't trigger false skill matches
    _skill_text = re.sub(r'!\[[^\]]*\]\(data:[^)]+\)', '', text)
    _skill_text = re.sub(r'<document\s+[^>]*>[\s\S]*?</document>', '', _skill_text).strip()
    from app.skill_router import get_skills_to_use, SKILL_STATUS_LABELS

    skills_to_use = get_skills_to_use(_skill_text or text, enabled)

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
    if skill_labels and channel == "telegram" and channel_target:
        # On Telegram, skip skills that are tool-handled — _emit_tool_event already fires a
        # notification when the tool is actually called, so the skill-status label would be
        # a redundant (and premature) duplicate message.
        _TOOL_HANDLED_SKILLS = {"reminders", "cron", "spotify"}
        tg_labels = skill_labels if not _provider_supports_tools(provider_name) else [
            SKILL_STATUS_LABELS.get(s, f"📄 Using {s}…")
            for s in skills_to_use
            if s not in _TOOL_HANDLED_SKILLS
        ]
        if tg_labels:
            await send_skill_status(channel, channel_target, tg_labels)
    if skill_labels and (reasoning_mode or "").lower() == "stream":
        await _emit_stream_status(
            db=db,
            conversation_id=cid,
            channel=channel,
            channel_target=channel_target,
            text=" • ".join(skill_labels),
            stream_event_callback=stream_event_callback,
        )

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
    context = await build_context(db, user_id, cid, extra=extra, skills_in_use=skills_to_use, user_role=user_role)
    context = _append_selected_agent_context(context, extra)

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
    # Providers with native thinking APIs don't need prompt-injected <think> instructions
    _NATIVE_THINKING_PROVIDERS = frozenset({"claude", "google"})
    if provider_name not in _NATIVE_THINKING_PROVIDERS:
        context += _thinking_instruction(thinking_level)
    if provider_name in ("openrouter", "ollama"):
        context += _reasoning_instruction(reasoning_mode)
    context += _final_tag_instruction("strict" if strict_final_mode_enabled else "off")
    if extra.get("force_web"):
        context += (
            "\n\n[WEB MODE]\n"
            "Prefer using web_search and web_fetch for up-to-date information when the user asks factual/current questions. "
            "After using web tools, synthesize a normal helpful answer (don't dump raw tool output)."
        )
    if channel != "subagent":
        context += (
            "\n\n[SUBAGENTS]\n"
            "For long or parallelizable work, use sessions_spawn to delegate a focused background subagent run. "
            "Use sessions_list/sessions_history to inspect results."
        )

    effective_user_text = text
    pdf_documents: list[dict] | None = None  # Native PDF pass-through for Claude
    # Extract text from any embedded PDF documents before sending to provider
    if "<document " in effective_user_text:
        logger.info("Found <document> tag in text, running async preprocessing (text len=%d)", len(effective_user_text))
        if provider_name == "claude":
            # Claude handles PDFs natively via document content blocks — skip preprocessing
            effective_user_text, pdf_documents = _extract_native_pdf_documents(effective_user_text)
            pdf_documents = pdf_documents or None
            if pdf_documents:
                logger.info("Extracted %d PDF(s) for native Claude pass-through", len(pdf_documents))
            # Still preprocess any remaining non-PDF <document> tags
            if "<document " in effective_user_text:
                effective_user_text = await _preprocess_document_tags_async(effective_user_text, provider_name=provider_name)
        else:
            effective_user_text = await _preprocess_document_tags_async(effective_user_text, provider_name=provider_name)
        logger.info("Document preprocessing complete (result len=%d)", len(effective_user_text))
        # Guide: answer about the document directly, don't over-process with tools
        if pdf_documents:
            context += (
                "\n\n[DOCUMENT ATTACHED]\n"
                "The user attached a PDF file. The raw PDF is passed directly to you as a document content block. "
                "Answer their question about the document directly — do NOT use tools or workspace skills to re-process it. "
                "Do NOT read any SKILL.md files unless the user explicitly asks to use a specific service (e.g. 'save to notes'). "
                "If asked to summarize, extract info, or answer questions about it, analyze the PDF directly."
            )
        else:
            context += (
                "\n\n[DOCUMENT ATTACHED]\n"
                "The user attached a file. The extracted text is in the message. "
                "Answer their question about the document directly — do NOT use tools or workspace skills to re-process it. "
                "Do NOT read any SKILL.md files unless the user explicitly asks to use a specific service (e.g. 'save to notes'). "
                "If asked to summarize, extract info, or answer questions about it, use the extracted text inline."
            )

    if image_bytes:
        if provider_name in _NATIVE_VISION_PROVIDERS:
            # Provider supports native vision — pass image directly, skip preprocessor
            logger.info("Provider %s supports native vision; passing image directly", provider_name)
        else:
            # Use vision preprocessor for providers without native vision
            vision_result = await _run_vision_preprocessor(
                text=text,
                image_bytes=image_bytes,
                image_mime=image_mime,
            )
            if vision_result:
                analysis, vision_provider, vision_model = vision_result
                source = vision_provider + (f"/{vision_model}" if vision_model else "")
                context += (
                    "\n\n[VISION PREPROCESSOR]\n"
                    "The user shared an image. A separate vision model already analyzed it. "
                    "Use the vision analysis block from the user message as the image observation source."
                )
                effective_user_text = (
                    f"{text}\n\n"
                    f"[VISION_ANALYSIS source={source}]\n"
                    f"{analysis}\n"
                    f"[/VISION_ANALYSIS]"
                )
                image_bytes = None
                image_mime = None
                logger.info("Vision preprocess complete using %s", source)
            else:
                await db.add_message(cid, "assistant", _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE, "script")
                return _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE

    # Load recent messages; skip old assistant error messages so the model doesn't repeat "check your API key"
    recent = await db.get_recent_messages(cid, limit=20)
    if text != raw_user_text and recent:
        last = recent[-1]
        if isinstance(last, dict) and last.get("role") == "user" and str(last.get("content") or "") == user_content:
            # When inline directives are stripped, avoid sending both raw and cleaned user text.
            recent = recent[:-1]

    messages = [
        {
            "role": m["role"],
            # Strip textual tool-call markup from saved assistant messages before sending to
            # the model — older messages may have <tool_call> / [ASTA_TOOL_CALL] tags stored
            # in the DB. If the model sees these in its own history it will try to re-execute
            # them, causing repeated identical tool calls on every new request.
            "content": _strip_tool_call_markup(m["content"]) if m["role"] == "assistant"
                else (_preprocess_document_tags(m["content"]) if "<document " in (m["content"] or "") else (m["content"] or "")),
        }
        for m in recent
        # Simple heuristic for old string-based errors in DB, plus new structured ones if we saved them
        if not (
            m["role"] == "assistant"
            and (
                m["content"].startswith("Error:")
                or m["content"].startswith("No AI provider")
                or m["content"].startswith(_STATUS_PREFIX)
            )
        )
    ]
    messages.append({"role": "user", "content": effective_user_text})


    # Context compaction: summarize older messages if history is too long.
    # Pass model + provider_name so the budget scales with the model's context window.
    # NOTE: user_model is not yet resolved here; use directive_model (same value at this point).
    from app.compaction import compact_history
    provider_for_compact = get_provider(provider_name)
    if provider_for_compact:
        try:
            messages = await compact_history(
                messages,
                provider_for_compact,
                model=directive_model,
                provider_name=provider_name,
                context=context,
            )
        except TypeError as e:
            # Backward-compat for tests/mocks patching compact_history with older signatures.
            err = str(e).lower()
            if "unexpected keyword argument" in err and ("model" in err or "provider_name" in err):
                messages = await compact_history(
                    messages,
                    provider_for_compact,
                    context=context,
                )
            else:
                raise

    provider = get_provider(provider_name)
    if not provider:
        return f"No AI provider found for '{provider_name}'. Check your provider settings."
    if image_bytes and provider_name not in _NATIVE_VISION_PROVIDERS:
        # Image wasn't preprocessed and provider doesn't support native vision — block
        await db.add_message(cid, "assistant", _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE, "script")
        return _VISION_PREPROCESSOR_UNAVAILABLE_MESSAGE
    user_model = await db.get_user_provider_model(user_id, provider.name)
    model_override = (
        extra.get("subagent_model_override")
        or extra.get("agent_model_override")
        or ""
    ).strip()
    if model_override:
        user_model = model_override
    if thinking_level == "xhigh" and not _supports_xhigh_thinking(provider.name, user_model):
        # Keep stored preference intact, but downgrade unsupported runtime requests.
        thinking_level = "high"
        extra["thinking_level"] = thinking_level

    # ── Role-based tool gating ──────────────────────────────────────────────
    _is_admin = (user_role == "admin")

    # Exec tool (Claw-style): expose based on exec security policy. Admin-only.
    from app.exec_tool import (
        get_effective_exec_bins,
        get_bash_tool_openai_def,
        get_exec_tool_openai_def,
        prepare_allowlisted_command,
        run_allowlisted_command,
        parse_exec_arguments,
        truncate_output_tail,
        OUTPUT_EVENT_TAIL_CHARS,
    )
    from app.config import get_settings
    tools: list = []
    offer_exec = False
    if _is_admin:
        effective_bins = await get_effective_exec_bins(db, user_id)
        exec_mode = get_settings().exec_security
        offer_exec = exec_mode != "deny" and (exec_mode == "full" or bool(effective_bins))
        if offer_exec:
            tools = list(get_exec_tool_openai_def(effective_bins, security_mode=exec_mode))
            tools = tools + get_bash_tool_openai_def(effective_bins, security_mode=exec_mode)
            logger.info("Exec allowlist: %s; passing tools to provider=%s", sorted(effective_bins), provider.name)
            # Process tool companion for long-running exec sessions
            from app.process_tool import get_process_tool_openai_def
            tools = tools + get_process_tool_openai_def()
        elif "notes" in text.lower() or "memo" in text.lower():
            logger.warning("User asked for notes/memo but exec allowlist is empty (enable Apple Notes skill or set ASTA_EXEC_ALLOWED_BINS)")

    # Coding compatibility tools: admin-only (read/write/edit with alias normalization).
    from app.workspace import discover_workspace_skills
    workspace_skill_names = {s.name for s in discover_workspace_skills()}
    has_enabled_workspace_skills = any(name in enabled for name in workspace_skill_names)
    if _is_admin:
        offer_coding_compat = has_enabled_workspace_skills or ("files" in enabled)
        if offer_coding_compat:
            from app.coding_compat_tool import get_coding_compat_tools_openai_def
            from app.apply_patch_compat_tool import get_apply_patch_compat_tool_openai_def
            tools = tools + get_coding_compat_tools_openai_def()
            tools = tools + get_apply_patch_compat_tool_openai_def()

    # Web/memory tools: allowed for ALL users (web search, etc.)
    if has_enabled_workspace_skills or extra.get("force_web"):
        from app.openclaw_compat_tools import get_openclaw_web_memory_tools_openai_def
        from app.message_compat_tool import get_message_compat_tool_openai_def
        tools = tools + get_openclaw_web_memory_tools_openai_def()
        tools = tools + get_message_compat_tool_openai_def()

    # Files tool: admin-only
    if _is_admin and "files" in enabled:
        from app.files_tool import get_files_tools_openai_def
        tools = tools + get_files_tools_openai_def()
    # Reminders tool: admin-only
    if _is_admin and "reminders" in enabled:
        from app.reminders_tool import get_reminders_tool_openai_def
        tools = tools + get_reminders_tool_openai_def()
    # Cron tool: admin-only
    if _is_admin:
        from app.cron_tool import get_cron_tool_openai_def
        tools = tools + get_cron_tool_openai_def()
    # Spotify tool: admin-only
    if _is_admin and "spotify" in enabled:
        from app.spotify_tool import get_spotify_tools_openai_def
        tools = tools + get_spotify_tools_openai_def()
    # Image generation tool — allowed for ALL users
    from app.keys import get_api_key as _get_api_key_img
    _gemini_key = await _get_api_key_img("gemini_api_key") or await _get_api_key_img("google_ai_key")
    _hf_key = await _get_api_key_img("huggingface_api_key")
    if _gemini_key or _hf_key:
        from app.image_gen_tool import get_image_gen_tool_openai_def
        tools = tools + get_image_gen_tool_openai_def()
    # PDF generation tool — allowed for ALL users
    from app.pdf_tool import get_pdf_tool_openai_def, is_fitz_available
    if is_fitz_available():
        tools = tools + get_pdf_tool_openai_def()
    # Office document generation (pptx/docx/xlsx) — allowed for ALL users
    from app.office_tool import (
        get_pptx_tool_openai_def, get_docx_tool_openai_def, get_xlsx_tool_openai_def,
        is_pptx_available, is_docx_available, is_xlsx_available,
    )
    if is_pptx_available():
        tools = tools + get_pptx_tool_openai_def()
    if is_docx_available():
        tools = tools + get_docx_tool_openai_def()
    if is_xlsx_available():
        tools = tools + get_xlsx_tool_openai_def()
    # Subagent orchestration: admin-only
    if _is_admin and channel != "subagent":
        from app.subagent_orchestrator import get_subagent_tools_openai_def
        tools = tools + get_subagent_tools_openai_def()
    # Project update tool: only when this conversation belongs to a project folder
    _conv_folder_id = await db.get_conversation_folder_id(cid)
    if _conv_folder_id:
        tools = (tools or []) + [
            {
                "type": "function",
                "function": {
                    "name": "project_update",
                    "description": (
                        "Update the current project's context notes (project.md). "
                        "Call this when you learn important information about the project — goals, decisions, preferences, "
                        "key findings, or status changes. Keep entries concise. "
                        "Do NOT call this for every message — only when genuinely important context should be persisted "
                        "for future conversations in this project."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["append", "replace_section", "read"],
                                "description": "append: add a new entry. replace_section: replace a named section. read: read current project.md",
                            },
                            "section": {
                                "type": "string",
                                "description": "Section name (e.g., 'Summary', 'Decisions', 'Status', 'Open Questions'). Required for replace_section.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write. For append: a concise bullet point or paragraph. For replace_section: the full new section content.",
                            },
                        },
                        "required": ["action"],
                    },
                },
            }
        ]
    # MCP tools: add tool definitions from connected MCP servers
    try:
        from app import mcp_client
        await mcp_client.ensure_initialized(db)
        mcp_tool_defs = mcp_client.get_tool_definitions()
        if mcp_tool_defs:
            tools = tools + mcp_tool_defs
            logger.info("MCP tools added: %s", [d["function"]["name"] for d in mcp_tool_defs])
    except Exception as e:
        logger.warning("MCP initialization skipped: %s", e)

    tools = tools if tools else None

    from app.providers.fallback import (
        chat_with_fallback,
        chat_with_fallback_stream,
        get_available_fallback_providers,
    )
    fallback_names = await get_available_fallback_providers(db, user_id, exclude_provider=provider.name)
    fallback_models = {}
    for fb_name in fallback_names:
        fb_model = await db.get_user_provider_model(user_id, fb_name)
        if fb_model:
            fallback_models[fb_name] = fb_model

    chat_kwargs = dict(
        context=context, model=user_model or None,
        _fallback_models=fallback_models,
        _runtime_db=db,
        _runtime_user_id=user_id,
        image_bytes=image_bytes,
        image_mime=image_mime,
        thinking_level=thinking_level,
        reasoning_mode=reasoning_mode,
        pdf_documents=pdf_documents,
    )
    if tools:
        chat_kwargs["tools"] = tools
    allowed_tool_names = _tool_names_from_defs(tools)

    # Stream reasoning when explicitly set to "stream" mode, or when Claude's native
    # thinking is active (thinkingLevel != "off") — Claude users should always see
    # the thought process when they've enabled thinking.
    _thinking_level_norm = (thinking_level or "off").strip().lower()
    live_stream_reasoning_enabled = reasoning_mode_norm in ("stream", "on") or (
        provider_name == "claude" and _thinking_level_norm not in ("off", "")
    )
    # Enable provider streaming for real-time web assistant deltas, even when reasoning mode is off.
    live_model_stream_enabled = live_stream_reasoning_enabled or stream_events_enabled
    live_stream_reasoning_emitted = False

    async def _emit_live_assistant_text(text_value: str, delta: str) -> None:
        if not stream_events_enabled:
            return
        await _emit_live_stream_event(
            stream_event_callback,
            {
                "type": "assistant",
                "text": (text_value or "").lstrip(),
                "delta": delta or "",
            },
        )

    async def _emit_live_reasoning_text(text_value: str, delta: str) -> None:
        next_text = (text_value or "").strip()
        if not next_text:
            return
        if stream_events_enabled:
            await _emit_live_stream_event(
                stream_event_callback,
                {
                    "type": "reasoning",
                    "text": next_text,
                    "delta": delta or "",
                },
            )
            return
        await _emit_stream_status(
            db=db,
            conversation_id=cid,
            channel=channel,
            channel_target=channel_target,
            text=next_text,
            stream_event_callback=stream_event_callback,
            stream_event_type="reasoning",
        )

    def _extract_live_assistant_text(raw_stream_text: str) -> str:
        assistant_live = _strip_reasoning_tags_from_text(
            raw_stream_text,
            mode="strict",
            trim="both",
            strict_final=strict_final_mode_enabled,
        )
        return _strip_bracket_tool_protocol(_strip_tool_call_markup(assistant_live or "")).strip()

    async def _on_model_stream_event(payload: dict[str, Any]) -> None:
        if not live_stream_machine:
            return
        await live_stream_machine.on_event(payload)

    async def _on_model_text_delta(delta_text: str) -> None:
        if not live_stream_machine or not delta_text:
            return
        await live_stream_machine.on_event({"type": "text_delta", "delta": delta_text})

    if live_model_stream_enabled:
        live_stream_machine = AssistantStreamStateMachine(
            merge_source_text=_merge_stream_source_text,
            plan_text_update=_plan_stream_text_update,
            extract_assistant_text=_extract_live_assistant_text,
            extract_reasoning_text=_extract_thinking_from_tagged_stream,
            format_reasoning=_format_reasoning_message,
            emit_assistant=_emit_live_assistant_text,
            emit_reasoning=_emit_live_reasoning_text,
            stream_reasoning=live_stream_reasoning_enabled,
        )

    if live_model_stream_enabled:
        response, provider_used = await chat_with_fallback_stream(
            provider,
            messages,
            fallback_names,
            on_stream_event=_on_model_stream_event,
            **chat_kwargs,
        )
        live_stream_reasoning_emitted = bool(
            live_stream_machine and live_stream_machine.reasoning_emitted
        )
    else:
        response, provider_used = await chat_with_fallback(
            provider, messages, fallback_names, **chat_kwargs
        )
    if tools and not response.tool_calls:
        parsed_calls, cleaned = _extract_textual_tool_calls(response.content or "", allowed_tool_names)
        if parsed_calls:
            response.tool_calls = parsed_calls
            response.content = cleaned
            logger.info(
                "Parsed textual tool-call fallback from provider=%s (count=%s)",
                provider_used.name if provider_used else provider.name,
                len(parsed_calls),
            )
    if tools and provider_used:
        has_tc = bool(response.tool_calls)
        logger.info("Provider %s returned tool_calls=%s (count=%s)", provider_used.name, has_tc, len(response.tool_calls or []))

    # Tool-call loop: if model requested exec (or other tools), run and re-call same provider until done
    # Safety cap: maximum tool-call iterations per request to prevent infinite loops.
    # 100 allows complex multi-step tasks (e.g. YouTube pipeline) while bounding runaway agents.
    MAX_TOOL_ROUNDS = 100
    # Compress older messages every N rounds to keep the context window from overflowing.
    # 15 balances memory retention vs. token budget (~60k tokens per compaction window).
    COMPACT_EVERY_N_ROUNDS = 15
    current_messages = list(messages)

    # Initialize tool loop detector for this conversation
    from app.tool_loop_detection import get_session_detector, inject_loop_warning
    loop_detector = get_session_detector(cid)

    # Track if a critical loop was detected to break the tool execution
    critical_loop_detected = False
    critical_loop_message = ""

    ran_exec_tool = False
    ran_any_tool = False
    exec_tool_call_count = 0   # count exec calls within this request to trigger script nudge
    ran_files_tool = False
    ran_image_gen_tool = False
    ran_reminders_tool = False
    ran_cron_tool = False
    used_tool_labels: list[str] = []
    reminder_tool_scheduled = False
    last_exec_stdout: str = ""
    last_exec_stderr: str = ""
    last_exec_command: str = ""
    last_exec_error: str = ""
    last_tool_output: str = ""
    last_tool_label: str = ""
    last_tool_error: str = ""
    last_tool_error_label: str = ""
    last_tool_error_mutating = False
    last_tool_error_fingerprint: str = ""

    def _record_tool_outcome(
        *,
        tool_name: str,
        tool_output: str,
        tool_args: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> None:
        nonlocal ran_any_tool, last_tool_output, last_tool_label
        nonlocal last_tool_error, last_tool_error_label, last_tool_error_mutating, last_tool_error_fingerprint

        ran_any_tool = True
        label = _build_tool_trace_label(tool_name, action)
        output_text = (tool_output or "").strip()
        last_tool_output = output_text
        last_tool_label = label

        mutating = _is_likely_mutating_tool_call(tool_name, tool_args)
        fingerprint = _build_tool_action_fingerprint(tool_name, tool_args)
        error_text = _extract_tool_error_message(output_text)
        if error_text:
            last_tool_error = error_text
            last_tool_error_label = label
            last_tool_error_mutating = mutating
            last_tool_error_fingerprint = fingerprint
            return

        if not last_tool_error:
            return

        if last_tool_error_mutating:
            if last_tool_error_fingerprint and fingerprint == last_tool_error_fingerprint:
                last_tool_error = ""
                last_tool_error_label = ""
                last_tool_error_mutating = False
                last_tool_error_fingerprint = ""
            return

        # Non-mutating errors are recoverable once any later tool call succeeds.
        last_tool_error = ""
        last_tool_error_label = ""
        last_tool_error_mutating = False
        last_tool_error_fingerprint = ""

    for _round in range(MAX_TOOL_ROUNDS):
        if tools and not response.tool_calls:
            parsed_calls, cleaned = _extract_textual_tool_calls(response.content or "", allowed_tool_names)
            if parsed_calls:
                response.tool_calls = parsed_calls
                response.content = cleaned
                logger.info(
                    "Parsed textual tool-call fallback mid-round from provider=%s (count=%s)",
                    provider_used.name if provider_used else provider.name,
                    len(parsed_calls),
                )
        if not response.tool_calls or not provider_used:
            break
        # Append assistant message (with content + tool_calls) and run each exec call
        # Strip any textual tool-call markup (e.g. <tool_call> XML from Trinity/Qwen models)
        # from the content before storing it in the conversation history. If the model
        # sees its own <tool_call> tags in prior turns it will try to re-execute them,
        # causing identical-command loops.
        asst_content = _strip_tool_call_markup(response.content or "")
        asst_tool_calls = response.tool_calls
        current_messages.append({
            "role": "assistant",
            "content": asst_content,
            "tool_calls": asst_tool_calls,
        })

        # Track seen IDs to prevent duplicates
        seen_ids = set()

        for tc in asst_tool_calls:
            fn = (tc.get("function") or {}) if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("function", {}).get("name")
            args_str = fn.get("arguments") or "{}"
            args_data: dict[str, Any] = {}
            if isinstance(args_str, dict):
                args_data = args_str
            elif isinstance(args_str, str):
                try:
                    parsed_args = json.loads(args_str)
                    if isinstance(parsed_args, dict):
                        args_data = parsed_args
                except Exception:
                    args_data = {}

            # SECURITY: Validate tool name against registry
            if not name:
                logger.warning("Tool call missing name: %s", tc)
                out = "Error: Tool call missing name"
                _record_tool_outcome(tool_name="tool_call", tool_output=out, tool_args=args_data)
                # Truncate extremely large tool output to prevent context overflow/model failure
                MAX_CHARS = 10000
                if len(out) > MAX_CHARS:
                    logger.info("Truncating tool output from %d to %d chars", len(out), MAX_CHARS)
                    out = out[:MAX_CHARS] + f"\n\n[TRUNCATED: original output was {len(out)} chars]"
                current_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
                continue

            # Normalize and validate tool name
            name = name.strip().lower()
            out = None
            if name not in allowed_tool_names:
                logger.warning("Tool '%s' not in allowed tools: %s", name, sorted(allowed_tool_names))
                out = f"Error: Tool '{name}' not available (not in registry)"

            # SECURITY: Validate database availability for tools that need it
            db_required_tools = {
                "list_directory", "read_file", "write_file", "delete_file",
                "delete_matching_files", "allow_path", "reminders", "cron",
                "message", "agents_list", "sessions_spawn", "sessions_list",
                "sessions_history", "sessions_send", "sessions_stop"
            }
            if name in db_required_tools and db is None:
                out = f"Error: Database not available for tool '{name}'"
                logger.error("Tool %s requires database but db is None", name)

            # Validate and normalize tool_call_id
            tool_call_id = tc.get("id", "")
            if not tool_call_id:
                logger.warning("Tool call missing ID, generating fallback: %s", name)
                tool_call_id = f"{name}_{len(current_messages)}"

            # Check for duplicate IDs
            if tool_call_id in seen_ids:
                logger.error("Duplicate tool_call_id: %s", tool_call_id)
                tool_call_id = f"{tool_call_id}_dup_{len(seen_ids)}"
            seen_ids.add(tool_call_id)

            # === TOOL LOOP DETECTION ===
            # Check for loops before executing the tool
            if loop_detector and name:
                loop_result = loop_detector.detect_loop(name, args_data)
                if loop_result.stuck:
                    if loop_result.level == "critical":
                        # Critical - block the tool execution
                        critical_loop_detected = True
                        critical_loop_message = loop_result.message
                        logger.warning(f"Tool loop blocked: {name} - {loop_result.message}")
                        out = f"Error: Tool execution blocked due to loop detection.\n\n{loop_result.message}"
                        current_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": out})
                        continue
                    else:
                        # Warning - inject warning into tool result but allow execution
                        logger.info(f"Tool loop warning: {name} - {loop_result.message}")
                        # Record the call anyway so we can track progress
                        loop_detector.record_tool_call(name, args_data, tool_call_id)
                        # Note: We'll record the outcome after execution
                else:
                    # No loop detected - record the call
                    loop_detector.record_tool_call(name, args_data, tool_call_id)
            # === END TOOL LOOP DETECTION ===

            if name:
                await _emit_tool_event(
                    phase="start",
                    name=name,
                    label=_build_tool_trace_label(name),
                    channel=channel,
                    channel_target=channel_target,
                    stream_event_callback=stream_event_callback,
                )
            if name in ("exec", "bash"):
                params = parse_exec_arguments(args_str)
                cmd = (params.get("command") or "").strip()
                timeout_sec = params.get("timeout_sec")
                yield_ms = params.get("yield_ms")
                background = bool(params.get("background"))
                pty = bool(params.get("pty"))
                workdir = params.get("workdir") if isinstance(params.get("workdir"), str) else None
                logger.info("Exec tool called: command=%r", cmd)
                precheck_argv, precheck_err = prepare_allowlisted_command(
                    cmd,
                    allowed_bins=effective_bins,
                )
                if (
                    precheck_err
                    and exec_mode == "allowlist"
                    and "not in allowlist" in precheck_err.lower()
                ):
                    from app.exec_approvals import create_pending_exec_approval

                    approval_id, requested_bin = await create_pending_exec_approval(
                        db=db,
                        user_id=user_id,
                        channel=channel,
                        channel_target=channel_target,
                        command=cmd,
                        timeout_sec=timeout_sec if isinstance(timeout_sec, int) else None,
                        workdir=workdir,
                        background=background,
                        pty=pty,
                    )
                    out = (
                        f"approval-needed: id={approval_id} binary={requested_bin or 'unknown'} command={cmd}\n"
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny."
                    )
                    ran_exec_tool = True
                    last_exec_command = cmd
                    last_exec_stdout = ""
                    last_exec_stderr = ""
                    last_exec_error = (
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny."
                    )
                    used_tool_labels.append(_build_tool_trace_label(name))
                elif precheck_err and exec_mode != "allowlist":
                    ran_exec_tool = True
                    last_exec_command = cmd
                    last_exec_stdout = ""
                    last_exec_stderr = ""
                    last_exec_error = precheck_err
                    used_tool_labels.append(_build_tool_trace_label(name))
                    out = f"error: {precheck_err}"
                else:
                    # precheck_argv is intentionally not reused; runtime functions re-validate for safety.
                    _ = precheck_argv
                    if background or isinstance(yield_ms, int) or pty:
                        from app.process_tool import run_exec_with_process_support

                        exec_result = await run_exec_with_process_support(
                            cmd,
                            allowed_bins=effective_bins,
                            timeout_seconds=timeout_sec if isinstance(timeout_sec, int) else None,
                            workdir=workdir,
                            background=background,
                            yield_ms=yield_ms if isinstance(yield_ms, int) else None,
                            pty=pty,
                        )
                        status = (exec_result.get("status") or "").strip().lower()
                        if status == "running":
                            ok = True
                            stdout = json.dumps(exec_result, indent=0)
                            stderr = ""
                        elif status in ("completed", "failed"):
                            stdout = (exec_result.get("stdout") or "").strip()
                            stderr = (exec_result.get("stderr") or "").strip()
                            ok = bool(exec_result.get("ok")) if "ok" in exec_result else (status == "completed")
                        else:
                            stdout = ""
                            stderr = (exec_result.get("error") or "Exec failed").strip()
                            ok = False
                    else:
                        stdout, stderr, ok = await run_allowlisted_command(
                            cmd,
                            allowed_bins=effective_bins,
                            timeout_seconds=timeout_sec if isinstance(timeout_sec, int) else None,
                            workdir=workdir,
                        )
                    ran_exec_tool = True
                    exec_tool_call_count += 1
                    used_tool_labels.append(_build_tool_trace_label(name))
                    last_exec_command = cmd
                    last_exec_stdout = stdout
                    last_exec_stderr = stderr
                    if not ok:
                        last_exec_error = (stderr or stdout or "").strip() or "Command not allowed or failed."
                    else:
                        last_exec_error = ""
                    logger.info("Exec result: ok=%s stdout_len=%s stderr_len=%s", ok, len(stdout), len(stderr))
                    if ok or stdout or stderr:
                        out = f"stdout:\n{stdout}\n" + (f"stderr:\n{stderr}\n" if stderr else "")
                    else:
                        out = f"error: {stderr or 'Command not allowed or failed.'}"
            elif name == "process":
                from app.process_tool import parse_process_tool_args, run_process_tool

                params = parse_process_tool_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("process", str(params.get("action") or "")))
                out = await run_process_tool(params)
                _record_tool_outcome(
                    tool_name="process",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
            elif name == "list_directory":
                from app.files_tool import list_directory as list_dir, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await list_dir(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("list_directory"))
            elif name == "read_file":
                from app.files_tool import read_file_content as read_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                _rf_offset = int(params["offset"]) if isinstance(params.get("offset"), int) and params["offset"] > 0 else 0
                out = await read_file_fn(
                    path, user_id, db,
                    offset=_rf_offset,
                    model=user_model,
                    provider=provider_name,
                )
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("read_file"))
            elif name == "write_file":
                from app.files_tool import write_file as write_file_fn, parse_files_tool_args as parse_files_args

                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                if _is_note_capture_request(text):
                    path = _canonicalize_note_write_path(path)
                    params["path"] = path
                content = params.get("content")
                out = await write_file_fn(path, content if isinstance(content, str) else "", user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("write_file"))
            elif name == "allow_path":
                from app.files_tool import allow_path as allow_path_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                out = await allow_path_fn(path, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("allow_path"))
            elif name == "delete_file":
                from app.files_tool import delete_file as delete_file_fn, parse_files_tool_args as parse_files_args
                params = parse_files_args(args_str)
                path = (params.get("path") or "").strip()
                permanently = bool(params.get("permanently")) if isinstance(params, dict) else False
                out = await delete_file_fn(path, user_id, db, permanently=permanently)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label("delete_file"))
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
                used_tool_labels.append(_build_tool_trace_label("delete_matching_files"))
            elif name in ("read", "write", "edit"):
                from app.coding_compat_tool import (
                    parse_coding_compat_args,
                    run_read_compat,
                    run_write_compat,
                    run_edit_compat,
                )

                params = parse_coding_compat_args(args_str)
                if name == "read":
                    out = await run_read_compat(params, user_id, db, model=user_model, provider=provider_name)
                elif name == "write":
                    if _is_note_capture_request(text):
                        note_path = _canonicalize_note_write_path(str(params.get("path") or ""))
                        params["path"] = note_path
                    out = await run_write_compat(params, user_id, db)
                else:
                    out = await run_edit_compat(params, user_id, db)
                ran_files_tool = True
                used_tool_labels.append(_build_tool_trace_label(name))
            elif name == "generate_pdf":
                from app.pdf_tool import generate_pdf as generate_pdf_fn, parse_pdf_tool_args

                params = parse_pdf_tool_args(args_str)
                pdf_content = (params.get("content") or "").strip()
                pdf_filename = (params.get("filename") or "document.pdf").strip()
                pdf_title = params.get("title")
                if not pdf_content:
                    out = "Error: content is required"
                else:
                    pdf_path = generate_pdf_fn(pdf_content, filename=pdf_filename, title=pdf_title)
                    import os as _os
                    pdf_safe = _os.path.basename(pdf_path)
                    out = f"PDF generated successfully. Download: /api/files/download-pdf/{pdf_safe}"
                used_tool_labels.append(_build_tool_trace_label("generate_pdf"))
            elif name == "generate_pptx":
                from app.office_tool import generate_pptx as _gen_pptx, parse_pptx_tool_args

                params = parse_pptx_tool_args(args_str)
                slides = params.get("slides")
                if not slides or not isinstance(slides, list):
                    out = "Error: slides array is required"
                else:
                    pptx_filename = (params.get("filename") or "presentation.pptx").strip()
                    pptx_theme = (params.get("theme") or "dark").strip()
                    pptx_path = _gen_pptx(slides, filename=pptx_filename, theme=pptx_theme)
                    import os as _os
                    pptx_safe = _os.path.basename(pptx_path)
                    out = f"Presentation generated successfully. Download: /api/files/download-office/{pptx_safe}"
                used_tool_labels.append(_build_tool_trace_label("generate_pptx"))
            elif name == "generate_docx":
                from app.office_tool import generate_docx as _gen_docx, parse_docx_tool_args

                params = parse_docx_tool_args(args_str)
                docx_content = (params.get("content") or "").strip()
                if not docx_content:
                    out = "Error: content is required"
                else:
                    docx_filename = (params.get("filename") or "document.docx").strip()
                    docx_title = params.get("title")
                    docx_path = _gen_docx(docx_content, filename=docx_filename, title=docx_title)
                    import os as _os
                    docx_safe = _os.path.basename(docx_path)
                    out = f"Document generated successfully. Download: /api/files/download-office/{docx_safe}"
                used_tool_labels.append(_build_tool_trace_label("generate_docx"))
            elif name == "generate_xlsx":
                from app.office_tool import generate_xlsx as _gen_xlsx, parse_xlsx_tool_args

                params = parse_xlsx_tool_args(args_str)
                xlsx_sheets = params.get("sheets")
                if not xlsx_sheets or not isinstance(xlsx_sheets, list):
                    out = "Error: sheets array is required"
                else:
                    xlsx_filename = (params.get("filename") or "spreadsheet.xlsx").strip()
                    xlsx_title = params.get("title")
                    xlsx_path = _gen_xlsx(xlsx_sheets, filename=xlsx_filename, title=xlsx_title)
                    import os as _os
                    xlsx_safe = _os.path.basename(xlsx_path)
                    out = f"Spreadsheet generated successfully. Download: /api/files/download-office/{xlsx_safe}"
                used_tool_labels.append(_build_tool_trace_label("generate_xlsx"))
            elif name == "web_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("web_search"))
                out = await run_web_search_compat(params)
            elif name == "web_fetch":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_web_fetch_compat

                params = parse_openclaw_compat_args(args_str)
                # Inject model/provider so web_fetch can compute adaptive page cap.
                params["_model"] = user_model
                params["_provider"] = provider_name
                used_tool_labels.append(_build_tool_trace_label("web_fetch"))
                out = await run_web_fetch_compat(params)
            elif name == "memory_search":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_search_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_search"))
                out = await run_memory_search_compat(params, user_id=user_id)
            elif name == "memory_get":
                from app.openclaw_compat_tools import parse_openclaw_compat_args, run_memory_get_compat

                params = parse_openclaw_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("memory_get"))
                out = await run_memory_get_compat(params, model=user_model, provider=provider_name)
                _record_tool_outcome(tool_name="memory_get", tool_output=out, tool_args=params)
            elif name == "apply_patch":
                from app.apply_patch_compat_tool import parse_apply_patch_compat_args, run_apply_patch_compat

                params = parse_apply_patch_compat_args(args_str)
                used_tool_labels.append(_build_tool_trace_label("apply_patch"))
                out = await run_apply_patch_compat(params)
                ran_files_tool = True
            elif name == "message":
                from app.message_compat_tool import parse_message_compat_args, run_message_compat

                params = parse_message_compat_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("message", str(params.get("action") or "send"))
                )
                out = await run_message_compat(
                    params,
                    current_channel=channel,
                    current_target=channel_target,
                )
            elif name == "reminders":
                from app.reminders_tool import run_reminders_tool, parse_reminders_tool_args
                params = parse_reminders_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("reminders", str(params.get("action") or ""))
                )
                out = await run_reminders_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                ran_reminders_tool = True
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
                _record_tool_outcome(
                    tool_name="reminders",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
            elif name == "cron":
                from app.cron_tool import run_cron_tool, parse_cron_tool_args
                params = parse_cron_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("cron", str(params.get("action") or ""))
                )
                out = await run_cron_tool(
                    params,
                    user_id=user_id,
                    channel=channel,
                    channel_target=channel_target,
                    db=db,
                )
                ran_cron_tool = True
                _record_tool_outcome(
                    tool_name="cron",
                    tool_output=out,
                    tool_args=params,
                    action=str(params.get("action") or ""),
                )
            elif name in (
                "agents_list",
                "sessions_spawn",
                "sessions_list",
                "sessions_history",
                "sessions_send",
                "sessions_stop",
            ):
                from app.subagent_orchestrator import parse_subagent_tool_args, run_subagent_tool

                params = parse_subagent_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label(name)
                )
                out = await run_subagent_tool(
                    tool_name=name,
                    params=params,
                    user_id=user_id,
                    parent_conversation_id=cid,
                    provider_name=provider_name,
                    channel=channel,
                    channel_target=channel_target,
                )
            elif name == "spotify":
                from app.spotify_tool import parse_spotify_tool_args, run_spotify_tool
                params = parse_spotify_tool_args(args_str)
                used_tool_labels.append(
                    _build_tool_trace_label("spotify", str(params.get("action") or ""))
                )
                out = await run_spotify_tool(params, user_id=user_id)
            elif name == "image_gen":
                from app.image_gen_tool import run_image_gen
                prompt = (args_data.get("prompt") or "").strip() if isinstance(args_data, dict) else ""
                used_tool_labels.append(_build_tool_trace_label("image_gen"))
                out = await run_image_gen(user_id=user_id, prompt=prompt)
                ran_image_gen_tool = True
            elif name == "project_update":
                out = await _run_project_update_tool(args_data, cid, db)
                used_tool_labels.append(_build_tool_trace_label("project_update", str((args_data or {}).get("action") or "")))
            elif name and name.startswith("mcp_"):
                # Route to MCP server
                from app import mcp_client
                if mcp_client.is_mcp_tool(name):
                    out = await mcp_client.call_tool(name, args_data)
                    used_tool_labels.append(_build_tool_trace_label(name))
                else:
                    out = f"Error: MCP tool '{name}' not found"
            else:
                out = "Unknown tool."

            if out is not None:
                # Record if not already handled specifically in branches (like process/reminders/cron)
                # Note: most tools were refactored to use this common block.
                recorded_tools = (
                    "process", "reminders", "cron", "agents_list", "sessions_spawn",
                    "sessions_list", "sessions_history", "sessions_send", "sessions_stop"
                )
                if name not in recorded_tools:
                    _record_tool_outcome(tool_name=name or "unknown", tool_output=out, tool_args=args_data)

                # Truncate tool output to prevent context overflow / provider failure.
                # OpenClaw-style adaptive paging:
                #   - exec/bash: tail truncation (keep last N chars of stdout)
                #   - read/coding tools: already paged at source with offset hint; safety cap here
                #   - pageable non-read tools (memory_get): already paged at source; safety cap only
                #   - non-pageable tools (web_fetch, list_dir, memory_search): hard cap, no offset hint
                if name in ("exec", "bash"):
                    if len(out) > OUTPUT_EVENT_TAIL_CHARS:
                        logger.info("Truncating exec output from %d to last %d chars", len(out), OUTPUT_EVENT_TAIL_CHARS)
                        out = truncate_output_tail(out, OUTPUT_EVENT_TAIL_CHARS)
                else:
                    from app.adaptive_paging import compute_page_chars, truncate_with_offset_hint
                    _tool_page_chars = compute_page_chars(user_model, provider_name)
                    if len(out) > _tool_page_chars:
                        logger.info(
                            "Truncating tool %s output from %d to %d chars (adaptive, model=%s)",
                            name, len(out), _tool_page_chars, user_model or "unknown",
                        )
                        # Tools that support offset-based pagination get a continuation hint.
                        # Non-pageable tools get a plain truncation notice (no offset hint).
                        # Tools that do their own offset-based pagination at the source.
                        # These already append a continuation hint, so we add one here too
                        # (for the rare case where the safety net fires on top of their output).
                        _offset_pageable = name in (
                            "read", "read_file", "read_workspace_file",
                            "memory_get",  # already paged at source with from= hint
                        )
                        if _offset_pageable:
                            out = truncate_with_offset_hint(out, max_chars=_tool_page_chars, offset=0)
                        else:
                            out = out[:_tool_page_chars] + (
                                f"\n\n[Output truncated to {_tool_page_chars} chars."
                                " Use a more specific query or request a smaller range.]"
                            )

                if name:
                    await _emit_tool_event(
                        phase="end",
                        name=name,
                        label=_build_tool_trace_label(name),
                        channel=channel,
                        channel_target=channel_target,
                        stream_event_callback=stream_event_callback,
                    )
                current_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": out})

        # If the model has made 6+ exec calls in a row, nudge it hard to write a script
        SCRIPT_NUDGE_THRESHOLD = 6
        if exec_tool_call_count == SCRIPT_NUDGE_THRESHOLD:
            current_messages.append({
                "role": "user",
                "content": (
                    f"[SYSTEM NOTICE] You have made {exec_tool_call_count} exec calls. "
                    "Stop making individual exec calls now. "
                    "Write a single bash script to workspace/scripts/tmp/ that does ALL remaining steps, "
                    "then run it in one exec call. Use python3 -c to parse JSON and chain IDs. "
                    "Do it now without explaining — just write_file then exec."
                ),
            })
            logger.info("Script nudge injected after %d exec calls", exec_tool_call_count)

        # Compact old tool rounds every N rounds (OpenClaw-style context compaction).
        # Replaces old tool call/result pairs with a concise inline summary so long
        # agentic tasks don't overflow the context window.
        if _round > 0 and _round % COMPACT_EVERY_N_ROUNDS == 0:
            from app.compaction import compact_tool_rounds
            current_messages, _did_compact = compact_tool_rounds(current_messages)
            if _did_compact:
                logger.info("Tool history compacted at round %d (%d messages remaining)", _round, len(current_messages))

        # Re-call same provider with updated messages (no fallback switch); use that provider's model
        tool_kwargs = {**chat_kwargs}
        if provider_used.name == provider.name:
            tool_kwargs["model"] = user_model or None
        else:
            tool_kwargs["model"] = fallback_models.get(provider_used.name)
        # Give the model more time when it has to summarize large tool output (e.g. memo notes)
        if provider_used.name == "openrouter":
            tool_kwargs["timeout"] = 90
        elif provider_used.name == "claude":
            tool_kwargs["timeout"] = 120
        if live_model_stream_enabled and hasattr(provider_used, "chat_stream"):
            if live_stream_machine:
                await live_stream_machine.on_event(
                    {"type": "message_start", "provider": provider_used.name}
                )
            response = await provider_used.chat_stream(
                current_messages,
                on_text_delta=_on_model_text_delta,
                **tool_kwargs,
            )
            if live_stream_machine:
                await live_stream_machine.on_event(
                    {
                        "type": "text_end",
                        "provider": provider_used.name,
                        "content": response.content or "",
                    }
                )
                await live_stream_machine.on_event(
                    {
                        "type": "message_end",
                        "provider": provider_used.name,
                        "content": response.content or "",
                    }
                )
                live_stream_reasoning_emitted = live_stream_machine.reasoning_emitted
        else:
            response = await provider_used.chat(current_messages, **tool_kwargs)
        if response.error:
            break

    # Detect if the tool loop was exhausted (hit MAX_TOOL_ROUNDS) while the model
    # still had pending tool calls — i.e. the task needed more steps than allowed.
    # In this case, tell the user clearly instead of silently dropping the work.
    _tool_rounds_exhausted = ran_any_tool and bool(response.tool_calls)

    raw_reply = (response.content or "").strip()

    if _tool_rounds_exhausted and not response.error:
        exhausted_note = (
            f"\n\n_(I hit my action limit ({MAX_TOOL_ROUNDS} steps) mid-task and couldn't finish. "
            "Try breaking the task into smaller parts or ask me to write a script to handle it in one go.)_"
        )
        raw_reply = (raw_reply + exhausted_note).strip()
        logger.info("Tool rounds exhausted (%d/%d) — appending user-facing note", MAX_TOOL_ROUNDS, MAX_TOOL_ROUNDS)

    # If the model ran a tool but returned empty content (or content that is *only*
    # tool-call markup, which will be empty after stripping), nudge it to synthesize.
    # This handles Trinity/Qwen models that output <tool_call> XML as their entire
    # response text alongside structured tool_calls — after stripping the XML the
    # effective content is empty, so we need the same synthesis nudge.
    _raw_reply_is_only_markup = (
        bool(raw_reply)
        and _has_tool_call_markup(raw_reply)
        and not _strip_tool_call_markup(raw_reply).strip()
    )
    if (not raw_reply or _raw_reply_is_only_markup) and ran_any_tool and last_tool_output and not response.error and provider_used:
        logger.info("Model returned empty after tool use — injecting synthesis nudge (provider=%s)", provider_used.name)
        # For Anthropic/Claude: do NOT append an extra user message — tool_result messages are
        # already wrapped as user messages in _to_anthropic_messages(), so adding another user
        # message creates consecutive user messages which is invalid and causes a 400 error.
        # Anthropic will naturally synthesize when re-called with tool_results present and no tools.
        # For other providers: append an explicit synthesis request.
        if provider_used.name != "claude":
            current_messages.append({
                "role": "user",
                "content": (
                    "The tool ran successfully. Now write your reply to the user based on the results above. "
                    "Be direct and concrete — do not call any more tools, just respond."
                ),
            })
        try:
            nudge_kwargs = {**chat_kwargs}
            nudge_kwargs.pop("tools", None)  # no more tool calls, just synthesize
            nudge_kwargs.pop("tool_choice", None)
            if provider_used.name == "openrouter":
                nudge_kwargs["timeout"] = 60
            nudge_resp = await provider_used.chat(current_messages, **nudge_kwargs)
            if nudge_resp.content and not nudge_resp.error:
                response = nudge_resp
                raw_reply = nudge_resp.content.strip()
                logger.info("Synthesis nudge succeeded (content_len=%d)", len(raw_reply))
        except Exception as _nudge_err:
            logger.warning("Synthesis nudge failed: %s", _nudge_err)

    had_tool_markup = _has_tool_call_markup(raw_reply)
    reply = _strip_tool_call_markup(raw_reply)
    reply = _strip_bracket_tool_protocol(reply)
    # Only show this error when NO tool was actually executed — if tools ran
    # successfully and the model just returned markup with no surrounding text,
    # the synthesis nudge above already handled producing a real reply.
    if not reply and had_tool_markup and not response.error and not ran_any_tool:
        reply = "I couldn't execute that tool call format. Ask again and I'll retry with tools."
    reply, suppress_user_reply = _sanitize_silent_reply_markers(reply)

    # If there was a fatal error (Auth/RateLimit) and no content, show the error message to the user
    if not reply and response.error:
        reply = f"Error: {response.error_message or 'Unknown provider error'}"

    # OpenClaw-style preference: scheduler actions should be executed via tools.
    # If a tool-capable model skipped reminders/cron tool calls, apply deterministic fallback
    # from tool logic so we don't hallucinate list/remove outcomes.
    scheduler_fallback_used = False
    has_explicit_scheduler_protocol = bool(
        re.search(r"(?is)\[\s*cron\s*:", raw_reply or "")
        or re.search(r"(?is)\[ASTA_CRON_(?:ADD|REMOVE):", raw_reply or "")
        or re.search(r"(?im)^\s*CRON\s+ACTION\s*=\s*(?:add|remove)\b", raw_reply or "")
    )
    if (
        _provider_supports_tools(provider_name)
        and not ran_reminders_tool
        and not ran_cron_tool
        and not has_explicit_scheduler_protocol
    ):
        scheduler_fallback = await _handle_scheduler_intents(
            db=db,
            user_id=user_id,
            conversation_id=cid,
            text=text,
            channel=channel,
            channel_target=channel_target,
            reminders_enabled=("reminders" in enabled),
        )
        if scheduler_fallback:
            fallback_reply, fallback_label = scheduler_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)
            scheduler_fallback_used = True

    # OpenClaw-style guardrail: if model skipped files tool calls on a clear files-check request,
    # run deterministic listing fallback (or return a factual access error) instead of pretending.
    if (
        _provider_supports_tools(provider_name)
        and "files" in enabled
        and not ran_files_tool
    ):
        files_fallback = await _handle_files_check_fallback(
            db=db,
            user_id=user_id,
            text=text,
        )
        if files_fallback:
            fallback_reply, fallback_label = files_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)

    # Generic "notes" requests should use workspace markdown notes, not Apple Notes exec.
    # Apply deterministic fallback so model misrouting (e.g. memo commands) can't hallucinate.
    if (
        _provider_supports_tools(provider_name)
        and "files" in enabled
        and _is_workspace_notes_list_request(text)
    ):
        notes_fallback = await _handle_workspace_notes_list_fallback(text=text)
        if notes_fallback:
            fallback_reply, fallback_label = notes_fallback
            reply = fallback_reply
            used_tool_labels.append(fallback_label)

    # Image generation guardrail: some fallback models occasionally reply with
    # "I don't have access to image tools" even when image_gen is available.
    # If image intent is clear and no image tool call ran, execute deterministic fallback.
    if (
        _provider_supports_tools(provider_name)
        and not ran_image_gen_tool
        and (_looks_like_image_generation_request(text) or _reply_claims_image_tool_unavailable(reply))
    ):
        from app.image_gen_tool import run_image_gen

        image_prompt = (text or "").strip()
        image_tool_output = await run_image_gen(user_id=user_id, prompt=image_prompt)
        _record_tool_outcome(
            tool_name="image_gen",
            tool_output=image_tool_output,
            tool_args={"prompt": image_prompt},
            action="fallback",
        )
        image_markdown, image_error = _extract_image_markdown_from_tool_output(image_tool_output)
        if image_markdown:
            reply = image_markdown
            used_tool_labels.append(_build_tool_trace_label("image_gen", "fallback"))
        elif image_error:
            reply = image_error
            used_tool_labels.append(_build_tool_trace_label("image_gen", "fallback"))

    # Strict no-fake-check rule for exec-backed checks (Apple Notes/Things): if no exec tool ran,
    # do not allow unverified "I checked..." claims.
    if (
        _provider_supports_tools(provider_name)
        and _is_exec_check_request(text)
        and not ran_exec_tool
    ):
        reply = (
            "I couldn't verify that yet because no Terminal tool call was executed. "
            "Ask again and I'll run the check with tools."
        )
        used_tool_labels.append(_build_tool_trace_label("exec", "required"))

    # Reasoning visibility mode (OpenClaw-like):
    # - off: hide extracted <think> blocks
    # - on/stream: show extracted reasoning above final answer
    effective_reply_provider = provider_used.name if provider_used else provider_name
    strict_final_for_reply = (
        strict_final_mode_requested
        and _provider_supports_strict_final(effective_reply_provider)
    )
    final_text, extracted_reasoning = _extract_reasoning_blocks(
        reply,
        strict_final=strict_final_for_reply,
    )
    reasoning_mode_norm = (reasoning_mode or "").strip().lower()
    if reasoning_mode_norm == "off":
        # Never leak raw <think> blocks to user output.
        reply = final_text
    elif extracted_reasoning:
        if reasoning_mode_norm == "stream":
            if not live_stream_reasoning_emitted:
                if stream_events_enabled:
                    formatted_reasoning = _format_reasoning_message(extracted_reasoning)
                    if formatted_reasoning:
                        await _emit_live_reasoning_text(formatted_reasoning, formatted_reasoning)
                        live_stream_reasoning_emitted = True
                else:
                    await _emit_reasoning_stream_progressively(
                        db=db,
                        conversation_id=cid,
                        channel=channel,
                        channel_target=channel_target,
                        reasoning=extracted_reasoning,
                    )
            # Stream mode emits reasoning as status; final user reply should stay clean.
            reply = final_text
        elif stream_events_enabled:
            # Streaming web with reasoning "on": emit reasoning as a separate SSE
            # event so the client can display it in the thinking block, and keep
            # the reply text clean (no "Reasoning:\n..." prefix).
            formatted_reasoning = _format_reasoning_message(extracted_reasoning)
            if formatted_reasoning and not live_stream_reasoning_emitted:
                await _emit_live_reasoning_text(formatted_reasoning, formatted_reasoning)
                live_stream_reasoning_emitted = True
            reply = final_text
        else:
            # Non-streaming channels (telegram, etc.): embed reasoning in reply text
            formatted_reasoning = _format_reasoning_message(extracted_reasoning)
            if formatted_reasoning:
                reply = f"{formatted_reasoning}\n\n{final_text}".strip()
            else:
                reply = final_text
    else:
        reply = final_text

    # OpenClaw-style fallback when we ran exec but model returned no user-facing reply:
    # surface the last concrete exec failure first, then raw output excerpt.
    if not reply and ran_exec_tool:
        max_show = 2000
        if last_exec_error:
            safe_cmd = (last_exec_command or "").replace("`", "'")
            if len(safe_cmd) > 140:
                safe_cmd = safe_cmd[:140] + "…"
            excerpt = last_exec_error[:max_show] + ("…" if len(last_exec_error) > max_show else "")
            if safe_cmd:
                reply = f"Exec failed for `{safe_cmd}`: {excerpt}"
            else:
                reply = f"Exec failed: {excerpt}"
        else:
            combined = "\n".join(
                part for part in ((last_exec_stdout or "").strip(), (last_exec_stderr or "").strip()) if part
            ).strip()
            if combined:
                reply = "I ran the command and got output, but the model didn't return a reply. **Command output:**\n\n```\n"
                excerpt = combined[:max_show] + ("…" if len(combined) > max_show else "")
                reply += excerpt + "\n```"
            else:
                reply = "I ran the command but didn't get a reply back. Try again or rephrase."

    # OpenClaw-style fallback for non-exec tools: surface concrete tool failure first.
    if not reply and last_tool_error:
        should_show_tool_error = last_tool_error_mutating or (not _is_recoverable_tool_error(last_tool_error))
        if should_show_tool_error:
            max_show = 2000
            excerpt = last_tool_error[:max_show] + ("…" if len(last_tool_error) > max_show else "")
            label = last_tool_error_label or "Tool"
            reply = f"Warning: {label} failed: {excerpt}"

    # If a tool ran successfully but the model produced no final text, do NOT dump raw tool output
    # to the user (it looks broken/leaky). Log it server-side and return a clean retry message.
    if not reply and ran_any_tool and last_tool_output:
        label = last_tool_label or "a tool"
        try:
            logger.warning(
                "Tool ran but model returned empty reply (label=%s, tool_output_len=%d)",
                label,
                len(last_tool_output or ""),
            )
        except Exception:
            pass
        # Show at least a preview of the tool output to be helpful
        output_preview = _redact_local_paths((last_tool_output or "")[:500])
        if len(last_tool_output or "") > 500:
            output_preview += "..."
        reply = (
            f"I used {label} and got output, but couldn't generate a response. "
            f"Output preview: {output_preview}\n\n"
            "Try rephrasing your request."
        )


    # Expand GIF tags
    if "[gif:" in reply:
        match = re.search(r"\[gif:\s*(.+?)\]", reply, re.IGNORECASE)
        if match:
            from app.cooldowns import is_cooldown_ready, mark_cooldown_now

            query = match.group(1).strip()
            can_send_gif = await is_cooldown_ready(
                db,
                user_id,
                "gif_reply",
                _GIF_COOLDOWN_SECONDS,
            )
            if can_send_gif:
                gif_markdown = await GiphyService.get_gif(query)
                if gif_markdown:
                    reply = reply.replace(match.group(0), "\n" + gif_markdown)
                    await mark_cooldown_now(db, user_id, "gif_reply")
                else:
                    reply = reply.replace(match.group(0), "")
            else:
                reply = reply.replace(match.group(0), "")

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
            from app.exec_tool import (
                get_effective_exec_bins,
                prepare_allowlisted_command,
                run_allowlisted_command,
            )
            effective_bins = await get_effective_exec_bins(db, user_id)
            for m in exec_matches:
                cmd = m.group(1).strip()
                precheck_argv, precheck_err = prepare_allowlisted_command(
                    cmd,
                    allowed_bins=effective_bins,
                )
                _ = precheck_argv
                if (
                    precheck_err
                    and exec_mode == "allowlist"
                    and "not in allowlist" in precheck_err.lower()
                ):
                    from app.exec_approvals import create_pending_exec_approval

                    approval_id, requested_bin = await create_pending_exec_approval(
                        db=db,
                        user_id=user_id,
                        channel=channel,
                        channel_target=channel_target,
                        command=cmd,
                    )
                    exec_outputs.append(
                        f"Command: {cmd}\n"
                        "Approval is blocking this action. In Telegram: open /approvals and tap Once, Always, or Deny.\n"
                        f"Approval id: {approval_id}\n"
                        f"Binary: {requested_bin or 'unknown'}"
                    )
                    continue
                stdout, stderr, ok = await run_allowlisted_command(cmd, allowed_bins=effective_bins)
                if ok or stdout or stderr:
                    exec_outputs.append(f"Command: {cmd}\nOutput:\n{stdout}\n" + (f"Stderr:\n{stderr}\n" if stderr else ""))
                else:
                    exec_outputs.append(f"Command: {cmd}\nError: {stderr or 'Command not allowed or failed.'}")
            if exec_outputs:
                exec_message = "[Command output from Asta]\n\n" + "\n---\n\n".join(exec_outputs)
                exec_message += "\n\nReply to the user based on this output. Do not use [ASTA_EXEC] in your reply."
                from app.exec_tool import truncate_output_tail, OUTPUT_EVENT_TAIL_CHARS
                exec_message = truncate_output_tail(exec_message, OUTPUT_EVENT_TAIL_CHARS)
                messages_plus = list(messages) + [{"role": "assistant", "content": reply}] + [{"role": "user", "content": exec_message}]
                response2, _ = await chat_with_fallback(
                    provider, messages_plus, fallback_names,
                    context=context, model=user_model or None,
                    _fallback_models=fallback_models,
                    _runtime_db=db,
                    _runtime_user_id=user_id,
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
        if _is_note_capture_request(text):
            file_path = _canonicalize_note_write_path(file_path)
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
    textual_cron, reply = _extract_textual_cron_add_protocol(reply)
    if textual_cron:
        try:
            from app.cron_runner import add_cron_job_to_scheduler
            from app.tasks.scheduler import get_scheduler

            job_id = await db.add_cron_job(
                user_id,
                textual_cron["name"],
                textual_cron["cron_expr"],
                textual_cron["message"],
                tz=textual_cron.get("tz") or None,
                channel=channel,
                channel_target=channel_target,
            )
            add_cron_job_to_scheduler(
                get_scheduler(),
                job_id,
                textual_cron["cron_expr"],
                textual_cron.get("tz") or None,
            )
            used_tool_labels.append(_build_tool_trace_label("cron", "add/fallback"))
            if reply:
                reply = reply + "\n\n"
            reply += f"I've scheduled cron job \"{textual_cron['name']}\" ({textual_cron['cron_expr']})."
        except Exception as e:
            if reply:
                reply = reply + "\n\n"
            reply += f"I couldn't schedule the cron job: {e}."

    bracket_cron_adds, reply = _extract_bracket_cron_add_protocols(reply)
    if bracket_cron_adds:
        from app.cron_runner import add_cron_job_to_scheduler
        from app.tasks.scheduler import get_scheduler

        confirmations: list[str] = []
        for item in bracket_cron_adds:
            try:
                job_id = await db.add_cron_job(
                    user_id,
                    item["name"],
                    item["cron_expr"],
                    item["message"],
                    tz=item.get("tz") or None,
                    channel=channel,
                    channel_target=channel_target,
                )
                add_cron_job_to_scheduler(
                    get_scheduler(),
                    job_id,
                    item["cron_expr"],
                    item.get("tz") or None,
                )
                confirmations.append(f"I've scheduled cron job \"{item['name']}\" ({item['cron_expr']}).")
                used_tool_labels.append(_build_tool_trace_label("cron", "add/fallback"))
            except Exception as e:
                confirmations.append(f"I couldn't schedule cron job \"{item['name']}\": {e}.")
        if confirmations:
            if reply:
                reply = reply + "\n\n"
            reply += "\n".join(confirmations)

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
        and not ran_reminders_tool
        and not scheduler_fallback_used
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

    # Avoid leaking internal shell snippets when user didn't ask for commands.
    if not _looks_like_command_request(text):
        stripped_reply, removed_shell = _strip_shell_command_leakage(reply)
        if removed_shell:
            reply = stripped_reply

    reply, removed_secrets = await _redact_sensitive_reply_content(reply, db)
    if removed_secrets:
        logger.warning("Redacted sensitive data from assistant reply before returning to user")

    # Re-sanitize in case post-processing introduced marker leakage.
    reply, suppress_now = _sanitize_silent_reply_markers(reply)
    suppress_user_reply = suppress_user_reply or suppress_now

    # OpenClaw-style: single generic fallback when reply is empty (no skill-specific hints)
    if (not suppress_user_reply) and (not reply or not reply.strip()):
        reply = "I didn't get a reply back. Try again or rephrase."

    # Optional trace: show tool activity in Telegram/Web replies for debugging.
    trace_settings = _get_trace_settings()
    channel_norm = (channel or "").strip().lower()
    # Telegram already gets proactive "skill status" pings; avoid noisy duplicate footer there.
    allow_trace_for_channel = channel_norm != "telegram"
    if (
        (not suppress_user_reply)
        and trace_settings.asta_show_tool_trace
        and allow_trace_for_channel
        and channel_norm in trace_settings.tool_trace_channels
    ):
        trace_line = _render_tool_trace(used_tool_labels)
        if reply:
            reply = f"{reply}\n\n{trace_line}"
        else:
            reply = trace_line

    if stream_events_enabled and reply.strip():
        final_visible_reply = reply.strip()
        prior_live_reply = live_stream_machine.assistant_text if live_stream_machine else ""
        if final_visible_reply != prior_live_reply:
            final_delta = _compute_incremental_delta(prior_live_reply, final_visible_reply)
            # Safety: if delta equals the full reply and prior content is non-empty,
            # the strings share no prefix — appending the full delta would duplicate content.
            # Skip the emit; the saved reply is the source of truth.
            skip_delta = prior_live_reply and final_delta == final_visible_reply
            if not skip_delta:
                await _emit_live_stream_event(
                    stream_event_callback,
                    {
                        "type": "assistant",
                        "text": final_visible_reply,
                        "delta": final_delta,
                    },
                )

    # Silent control-path: no assistant message emitted/persisted.
    if suppress_user_reply and not reply.strip():
        if _out is not None:
            _out["provider"] = effective_reply_provider
        return ""

    # Always persist assistant reply (including errors) so history matches what users saw in-chat.
    await db.add_message(cid, "assistant", reply, provider.name if not reply.strip().startswith("Error:") and not reply.strip().startswith("No AI provider") else None)

    # Auto-title: fire background task on first exchange only (no title stored yet)
    if reply.strip() and not reply.strip().startswith("Error:"):
        existing_title = await db.get_conversation_title(cid)
        if not existing_title:
            asyncio.create_task(
                _generate_conversation_title(cid, text, reply, effective_reply_provider),
                name=f"auto-title:{cid}",
            )

    if _out is not None:
        _out["provider"] = effective_reply_provider
    return reply
