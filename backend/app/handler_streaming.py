"""Streaming helper functions extracted from handler.py."""

import asyncio  # noqa: F401
import logging
import re

from typing import Any
from inspect import isawaitable

from app.reminders import send_notification
from app.handler_thinking import _format_reasoning_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SILENT_REPLY_TOKEN = "NO_REPLY"
_STATUS_PREFIX = "[[ASTA_STATUS]]"


# ---------------------------------------------------------------------------
# Stream helpers
# ---------------------------------------------------------------------------

async def _emit_live_stream_event(
    callback,
    payload: dict[str, Any],
) -> None:
    """Best-effort stream event emitter for web SSE/live callbacks."""
    if not callable(callback):
        return
    try:
        maybe = callback(payload)
        if isawaitable(maybe):
            await maybe
    except Exception as e:
        logger.debug("Live stream event callback failed: %s", e)


async def _emit_tool_event(
    *,
    phase: str,          # "start" or "end"
    name: str,
    label: str,
    channel: str,
    channel_target: str,
    stream_event_callback=None,
) -> None:
    """Emit an infrastructure-level tool event (OpenClaw style).
    - web: SSE event with type=tool_start or tool_end
    - telegram: send status message on start only (no noise on end)
    """
    event_type = "tool_start" if phase == "start" else "tool_end"
    if callable(stream_event_callback):
        await _emit_live_stream_event(
            stream_event_callback,
            {"type": event_type, "name": name, "label": label},
        )
    ch = (channel or "").strip().lower()
    if ch == "telegram" and channel_target and phase == "start":
        from app.reminders import send_notification
        try:
            await send_notification(ch, channel_target, f"🔧 {label}…")
        except Exception as e:
            logger.debug("Could not send tool status to telegram: %s", e)


def _make_status_message(text: str) -> str:
    return f"{_STATUS_PREFIX}{(text or '').strip()}"


async def _emit_stream_status(
    *,
    db,
    conversation_id: str,
    channel: str,
    channel_target: str,
    text: str,
    stream_event_callback=None,
    stream_event_type: str = "status",
) -> None:
    msg = (text or "").strip()
    if not msg:
        return
    if callable(stream_event_callback):
        await _emit_live_stream_event(
            stream_event_callback,
            {
                "type": stream_event_type,
                "text": msg,
            },
        )
    ch = (channel or "").strip().lower()
    if ch == "telegram" and channel_target:
        try:
            await send_notification(ch, channel_target, msg)
        except Exception as e:
            logger.debug("Could not send stream status to channel=%s: %s", ch, e)
    # For live-stream web requests, status is delivered over SSE and should stay ephemeral.
    if ch == "web" and not callable(stream_event_callback):
        try:
            await db.add_message(conversation_id, "assistant", _make_status_message(msg), "script")
        except Exception as e:
            logger.debug("Could not persist stream status to web conversation: %s", e)


def _sanitize_silent_reply_markers(text: str) -> tuple[str, bool]:
    """Strip NO_REPLY control marker and tell whether this should be a silent/no-output reply."""
    raw = (text or "")
    if not raw.strip():
        return "", False

    # Exact control token means "do not emit assistant text".
    if re.fullmatch(r"(?is)\s*NO_REPLY\s*", raw):
        return "", True

    # Remove standalone NO_REPLY lines and trailing token leakage.
    cleaned = re.sub(r"(?im)^\s*NO_REPLY\s*$", "", raw)
    cleaned = re.sub(r"(?i)\s*NO_REPLY\s*$", "", cleaned)
    cleaned = re.sub(r"(?i)^\s*NO_REPLY\s*", "", cleaned)
    cleaned = cleaned.strip()

    # If stripping markers left no user-facing text, keep it silent.
    if not cleaned:
        return "", True
    return cleaned, False


async def _emit_reasoning_stream_progressively(
    *,
    db,
    conversation_id: str,
    channel: str,
    channel_target: str,
    reasoning: str,
) -> None:
    lines = [line.strip() for line in (reasoning or "").splitlines() if line.strip()]
    if not lines:
        return
    built: list[str] = []
    for line in lines:
        built.append(line)
        formatted = _format_reasoning_message("\n".join(built))
        if not formatted:
            continue
        await _emit_stream_status(
            db=db,
            conversation_id=conversation_id,
            channel=channel,
            channel_target=channel_target,
            text=formatted,
        )
