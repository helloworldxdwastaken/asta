"""OpenClaw-style assistant stream event state machine for live UI updates."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from inspect import isawaitable

logger = logging.getLogger(__name__)

StreamEvent = dict[str, str]
MergeSourceTextFn = Callable[[str, str], str]
PlanTextUpdateFn = Callable[..., tuple[bool, str, bool]]
ExtractAssistantTextFn = Callable[[str], str]
ExtractReasoningTextFn = Callable[[str], str]
FormatReasoningFn = Callable[[str], str]
EmitStreamTextFn = Callable[[str, str], Awaitable[None] | None]


async def _maybe_await(value) -> None:
    if isawaitable(value):
        await value


class AssistantStreamStateMachine:
    """State machine for assistant streaming text + reasoning visibility.

    Mirrors the OpenClaw lifecycle model:
    - `message_start` resets per-message source buffer
    - `text_delta`/`text_start`/`text_end` append chunk-time text with dedupe
    - `message_end` finalizes the current assistant message boundary
    """

    def __init__(
        self,
        *,
        merge_source_text: MergeSourceTextFn,
        plan_text_update: PlanTextUpdateFn,
        extract_assistant_text: ExtractAssistantTextFn,
        extract_reasoning_text: ExtractReasoningTextFn,
        format_reasoning: FormatReasoningFn,
        emit_assistant: EmitStreamTextFn,
        emit_reasoning: EmitStreamTextFn,
        stream_reasoning: bool = False,
    ) -> None:
        self._merge_source_text = merge_source_text
        self._plan_text_update = plan_text_update
        self._extract_assistant_text = extract_assistant_text
        self._extract_reasoning_text = extract_reasoning_text
        self._format_reasoning = format_reasoning
        self._emit_assistant = emit_assistant
        self._emit_reasoning = emit_reasoning
        self._stream_reasoning = bool(stream_reasoning)

        self._message_open = False
        self._source_buffer = ""
        self._assistant_text = ""
        self._reasoning_text = ""
        self._allow_assistant_rewrite = False
        self._allow_reasoning_rewrite = False
        self._reasoning_emitted = False

    @property
    def reasoning_emitted(self) -> bool:
        return self._reasoning_emitted

    @property
    def assistant_text(self) -> str:
        return self._assistant_text

    async def on_event(self, event: StreamEvent | None) -> None:
        if not isinstance(event, dict):
            return
        evt_type = str(event.get("type") or "").strip().lower()
        if not evt_type:
            return
        if evt_type == "message_start":
            self.on_message_start()
            return
        if evt_type in ("text_delta", "text_start", "text_end"):
            await self._on_text_event(
                evt_type=evt_type,
                delta=str(event.get("delta") or ""),
                content=str(event.get("content") or ""),
            )
            return
        if evt_type == "message_end":
            await self.on_message_end(content=str(event.get("content") or ""))
            return

    def on_message_start(self) -> None:
        # New provider pass/tool-recall pass can restart from scratch while prior
        # assistant/reasoning text may already be visible in the UI.
        self._source_buffer = ""
        self._allow_assistant_rewrite = bool(self._assistant_text)
        self._allow_reasoning_rewrite = bool(self._reasoning_text)
        self._message_open = True

    async def on_message_end(self, *, content: str = "") -> None:
        if content:
            await self._on_text_event(evt_type="text_end", content=content)
        self._message_open = False

    async def _on_text_event(self, *, evt_type: str, delta: str = "", content: str = "") -> None:
        if not self._message_open:
            self.on_message_start()

        chunk = self._resolve_chunk(evt_type=evt_type, delta=delta, content=content)
        if not chunk:
            return

        merged = self._merge_source_text(self._source_buffer, chunk)
        if merged == self._source_buffer:
            return
        self._source_buffer = merged
        await self._emit_live_from_buffer()

    def _resolve_chunk(self, *, evt_type: str, delta: str, content: str) -> str:
        if evt_type == "text_delta":
            return delta

        if delta:
            return delta

        if not content:
            return ""

        # Some providers replay full content on text_end instead of delta.
        current = self._source_buffer
        if not current:
            return content
        if content.startswith(current):
            return content[len(current) :]
        if current.startswith(content) or content in current:
            return ""
        return content

    async def _emit_live_from_buffer(self) -> None:
        assistant_live = (self._extract_assistant_text(self._source_buffer) or "").strip()
        if assistant_live:
            await self._emit_assistant_text(assistant_live)

        if not self._stream_reasoning:
            return
        reasoning_live = (self._extract_reasoning_text(self._source_buffer) or "").strip()
        if not reasoning_live:
            return
        formatted = self._format_reasoning(reasoning_live)
        if not formatted:
            return
        self._reasoning_emitted = True
        await self._emit_reasoning_text(formatted)

    async def _emit_assistant_text(self, text_value: str) -> None:
        should_emit, delta, rewrote = self._plan_text_update(
            previous=self._assistant_text,
            current=text_value,
            allow_rewrite=self._allow_assistant_rewrite,
        )
        if not should_emit:
            return
        self._assistant_text = text_value
        if rewrote or self._allow_assistant_rewrite:
            self._allow_assistant_rewrite = False
        await _maybe_await(self._emit_assistant(text_value, delta))

    async def _emit_reasoning_text(self, text_value: str) -> None:
        should_emit, delta, rewrote = self._plan_text_update(
            previous=self._reasoning_text,
            current=text_value,
            allow_rewrite=self._allow_reasoning_rewrite,
        )
        if not should_emit:
            return
        self._reasoning_text = text_value
        if rewrote or self._allow_reasoning_rewrite:
            self._allow_reasoning_rewrite = False
        await _maybe_await(self._emit_reasoning(text_value, delta))
