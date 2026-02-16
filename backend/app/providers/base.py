from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import TypedDict, Any
from dataclasses import dataclass, field
from enum import Enum


class Message(TypedDict):
    role: str  # "user" | "assistant" | "system"
    content: str


class ProviderError(str, Enum):
    """Standardized error kinds for providers."""
    AUTH = "auth"                # API key invalid
    RATE_LIMIT = "rate_limit"    # Rate limited
    MODEL_NOT_FOUND = "model"    # Model doesn't exist
    TIMEOUT = "timeout"          # Timed out
    TRANSIENT = "transient"      # Unknown/transient error (connection reset, 500, etc)
    NONE = "none"                # (Not used in error field, but for logic)


# Tool call (OpenClaw-style): model requested to run a tool. Handler runs it and re-calls with result.
ToolCall = dict  # {"id": str, "type": "function", "function": {"name": str, "arguments": str}}
TextDeltaCallback = Callable[[str], Awaitable[None] | None]
StreamEventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class ProviderResponse:
    """Standardized response from an AI provider."""
    content: str
    error: ProviderError | None = None
    error_message: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    # When the model requests a tool (e.g. exec): list of tool calls. Handler runs them and re-calls.
    tool_calls: list[ToolCall] | None = None


def _get_field(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


async def emit_text_delta(callback: TextDeltaCallback | None, delta: str) -> None:
    if not callback or not delta:
        return
    maybe = callback(delta)
    if isawaitable(maybe):
        await maybe


async def emit_stream_event(callback: StreamEventCallback | None, payload: dict[str, Any]) -> None:
    if not callback or not isinstance(payload, dict):
        return
    maybe = callback(payload)
    if isawaitable(maybe):
        await maybe


def merge_stream_tool_call_delta(
    store: dict[int, ToolCall],
    delta: Any,
) -> None:
    idx_raw = _get_field(delta, "index", None)
    try:
        idx = int(idx_raw) if idx_raw is not None else len(store)
    except Exception:
        idx = len(store)

    entry = store.setdefault(
        idx,
        {
            "id": "",
            "type": "function",
            "function": {"name": "", "arguments": ""},
        },
    )

    tc_id = _get_field(delta, "id", None)
    if tc_id:
        entry["id"] = str(tc_id)

    tc_type = _get_field(delta, "type", None)
    if tc_type:
        entry["type"] = str(tc_type)

    function_delta = _get_field(delta, "function", None) or {}
    fn_name = _get_field(function_delta, "name", None)
    fn_args = _get_field(function_delta, "arguments", None)

    if fn_name:
        # Some providers send full name in one chunk; others can split.
        name = str(fn_name)
        entry["function"]["name"] = (
            name if not entry["function"]["name"] else entry["function"]["name"] + name
        )
    if fn_args:
        entry["function"]["arguments"] += str(fn_args)


def finalize_stream_tool_calls(store: dict[int, ToolCall]) -> list[ToolCall] | None:
    if not store:
        return None
    out: list[ToolCall] = []
    for idx in sorted(store.keys()):
        entry = store[idx]
        fn = entry.get("function") or {}
        out.append(
            {
                "id": str(entry.get("id") or f"tool_{idx}"),
                "type": str(entry.get("type") or "function"),
                "function": {
                    "name": str(fn.get("name") or ""),
                    "arguments": str(fn.get("arguments") or "{}"),
                },
            }
        )
    return out


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        """Send messages and return assistant reply."""
        ...

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        on_stream_event: StreamEventCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Streaming variant. Default falls back to non-streaming chat."""
        await emit_stream_event(on_stream_event, {"type": "message_start"})
        response = await self.chat(messages, **kwargs)
        if response.content:
            await emit_stream_event(on_stream_event, {"type": "text_start"})
            await emit_text_delta(on_text_delta, response.content)
            await emit_stream_event(
                on_stream_event,
                {"type": "text_delta", "delta": response.content},
            )
            await emit_stream_event(
                on_stream_event,
                {"type": "text_end", "content": response.content},
            )
        await emit_stream_event(
            on_stream_event,
            {"type": "message_end", "content": response.content or ""},
        )
        return response

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider id, e.g. 'ollama', 'claude', 'google'."""
        ...
