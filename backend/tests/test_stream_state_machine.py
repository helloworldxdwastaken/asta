from __future__ import annotations

import pytest

from app.handler import (
    _format_reasoning_message,
    _merge_stream_source_text,
    _plan_stream_text_update,
    _strip_reasoning_tags_from_text,
    _extract_thinking_from_tagged_stream,
)
from app.stream_state_machine import AssistantStreamStateMachine


@pytest.mark.asyncio
async def test_stream_state_machine_allows_single_rewrite_after_message_start():
    assistant_events: list[tuple[str, str]] = []

    async def _emit_assistant(text: str, delta: str) -> None:
        assistant_events.append((text, delta))

    machine = AssistantStreamStateMachine(
        merge_source_text=lambda _cur, incoming: incoming,
        plan_text_update=_plan_stream_text_update,
        extract_assistant_text=lambda value: value,
        extract_reasoning_text=lambda _value: "",
        format_reasoning=lambda value: value,
        emit_assistant=_emit_assistant,
        emit_reasoning=lambda _text, _delta: None,
        stream_reasoning=False,
    )

    await machine.on_event({"type": "message_start"})
    await machine.on_event({"type": "text_delta", "delta": "Checking files..."})
    await machine.on_event({"type": "text_delta", "delta": "Found 3 files"})
    # Same message, non-prefix rewrite should be blocked.
    assert assistant_events == [("Checking files...", "Checking files...")]

    await machine.on_event({"type": "message_start"})
    await machine.on_event({"type": "text_delta", "delta": "Found 3 files"})
    # New message boundary allows a single non-prefix rewrite.
    assert assistant_events[-1] == ("Found 3 files", "Found 3 files")


@pytest.mark.asyncio
async def test_stream_state_machine_streams_reasoning_and_final_text():
    assistant_events: list[tuple[str, str]] = []
    reasoning_events: list[tuple[str, str]] = []

    async def _emit_assistant(text: str, delta: str) -> None:
        assistant_events.append((text, delta))

    async def _emit_reasoning(text: str, delta: str) -> None:
        reasoning_events.append((text, delta))

    machine = AssistantStreamStateMachine(
        merge_source_text=_merge_stream_source_text,
        plan_text_update=_plan_stream_text_update,
        extract_assistant_text=lambda raw: _strip_reasoning_tags_from_text(
            raw,
            mode="strict",
            trim="both",
            strict_final=False,
        ),
        extract_reasoning_text=_extract_thinking_from_tagged_stream,
        format_reasoning=_format_reasoning_message,
        emit_assistant=_emit_assistant,
        emit_reasoning=_emit_reasoning,
        stream_reasoning=True,
    )

    await machine.on_event({"type": "message_start"})
    await machine.on_event({"type": "text_delta", "delta": "<think>step one\n"})
    await machine.on_event({"type": "text_delta", "delta": "step two</think>\nFinal"})
    await machine.on_event({"type": "text_delta", "delta": " answer"})

    assert machine.reasoning_emitted is True
    assert reasoning_events
    assert "step two" in reasoning_events[-1][0]
    assert assistant_events
    assert assistant_events[-1][0] == "Final answer"


@pytest.mark.asyncio
async def test_stream_state_machine_uses_text_end_content_snapshot():
    assistant_events: list[tuple[str, str]] = []

    async def _emit_assistant(text: str, delta: str) -> None:
        assistant_events.append((text, delta))

    machine = AssistantStreamStateMachine(
        merge_source_text=_merge_stream_source_text,
        plan_text_update=_plan_stream_text_update,
        extract_assistant_text=lambda value: value,
        extract_reasoning_text=lambda _value: "",
        format_reasoning=lambda value: value,
        emit_assistant=_emit_assistant,
        emit_reasoning=lambda _text, _delta: None,
        stream_reasoning=False,
    )

    await machine.on_event({"type": "message_start"})
    await machine.on_event({"type": "text_end", "content": "Hello world"})
    await machine.on_event({"type": "message_end", "content": "Hello world"})

    assert assistant_events[-1] == ("Hello world", "Hello world")
