"""Test that all handler sub-modules import cleanly and export expected symbols."""


def test_handler_thinking_imports():
    from app.handler_thinking import (
        _strip_think_blocks,
        _thinking_instruction,
        _normalize_thinking_level,
        _extract_reasoning_blocks,
        _format_reasoning_message,
        _THINK_LEVELS,
    )
    assert isinstance(_THINK_LEVELS, tuple)


def test_handler_vision_imports():
    from app.handler_vision import (
        _extract_inline_image,
        _run_vision_preprocessor,
        _preprocess_document_tags_async,
        _extract_pdf_text,
        _assess_pdf_text_quality,
        _NATIVE_VISION_PROVIDERS,
    )
    assert "claude" in _NATIVE_VISION_PROVIDERS


def test_handler_streaming_imports():
    from app.handler_streaming import (
        _emit_live_stream_event,
        _emit_tool_event,
        _make_status_message,
        _sanitize_silent_reply_markers,
        _STATUS_PREFIX,
        _SILENT_REPLY_TOKEN,
    )
    assert _STATUS_PREFIX == "[[ASTA_STATUS]]"


def test_handler_intent_imports():
    from app.handler_intent import (
        _is_exec_intent,
        _is_short_acknowledgment,
        _looks_like_image_generation_request,
        _looks_like_files_check_request,
        _looks_like_command_request,
        _is_note_capture_request,
        _is_workspace_notes_list_request,
        _TOOL_CAPABLE_PROVIDERS,
    )
    assert "openai" in _TOOL_CAPABLE_PROVIDERS


def test_handler_security_imports():
    from app.handler_security import (
        _strip_shell_command_leakage,
        _redact_local_paths,
        _redact_sensitive_reply_content,
        _dedupe_secret_values,
        _SENSITIVE_DB_KEY_NAMES,
    )
    assert "notion_api_key" in _SENSITIVE_DB_KEY_NAMES


def test_handler_learning_imports():
    from app.handler_learning import (
        _parse_learn_command,
        _learn_help_text,
        _handle_learn_command,
    )
    assert callable(_parse_learn_command)


def test_handler_subagents_imports():
    from app.handler_subagents import (
        _looks_like_auto_subagent_request,
        _parse_subagents_command,
        _handle_subagents_command,
        _subagents_help_text,
    )
    assert callable(_looks_like_auto_subagent_request)


def test_handler_context_imports():
    from app.handler_context import (
        _append_selected_agent_context,
        _selected_agent_skill_filter,
        _run_project_update_tool,
    )
    assert callable(_append_selected_agent_context)


def test_handler_scheduler_imports():
    from app.handler_scheduler import (
        _looks_like_reminder_set_request,
        _looks_like_reminder_list_request,
        _looks_like_cron_list_request,
    )
    assert callable(_looks_like_reminder_set_request)


def test_handler_reexports():
    """Functions imported by handler.py are available as re-exports."""
    from app.handler import (
        _is_exec_intent,
        _redact_local_paths,
        _strip_shell_command_leakage,
        _emit_live_stream_event,
        _looks_like_image_generation_request,
        _parse_learn_command,
        _looks_like_auto_subagent_request,
        _append_selected_agent_context,
    )
    assert callable(_is_exec_intent)
    assert callable(_redact_local_paths)
