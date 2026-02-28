"""OpenClaw-compatible message tool (single-user subset)."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from app.reminders import send_notification

SUPPORTED_MESSAGE_ACTIONS = (
    "send",
    "reply",
    "react",
    "edit",
    "unsend",
    "sendPoll",
    "sendAttachment",
    "sendWithEffect",
)

_SUPPORTED_ACTION_SET = {a.lower() for a in SUPPORTED_MESSAGE_ACTIONS}
_ACTION_MAP = {
    "send": "send",
    "reply": "reply",
    "react": "react",
    "edit": "edit",
    "unsend": "unsend",
    "sendpoll": "sendPoll",
    "sendattachment": "sendAttachment",
    "sendwitheffect": "sendWithEffect",
}


def get_message_compat_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "message",
                "description": (
                    "Single-user message tool compatibility. "
                    "Supports rich message actions with channel-specific capabilities. "
                    "Messages are constrained to the current channel/target."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": list(SUPPORTED_MESSAGE_ACTIONS)},
                        "text": {"type": "string"},
                        "message": {"type": "string", "description": "Alias for text"},
                        "content": {"type": "string", "description": "Alias for text"},
                        "channel": {"type": "string", "description": "Optional channel override"},
                        "to": {"type": "string", "description": "Optional target override"},
                        "channel_target": {"type": "string", "description": "Alias for to"},
                        "target": {"type": "string", "description": "Alias for to"},
                        "messageId": {"type": "string", "description": "Message ID for react/edit/unsend"},
                        "message_id": {"type": "string", "description": "Alias for messageId"},
                        "replyTo": {"type": "string", "description": "Message ID to reply to"},
                        "question": {"type": "string", "description": "Poll question for sendPoll"},
                        "options": {
                            "description": "Poll options for sendPoll. Array preferred, comma/newline string also supported.",
                            "oneOf": [
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "string"},
                            ],
                        },
                        "maxSelections": {"type": "integer", "description": "Max selections hint (sendPoll). >1 enables multi-answer poll."},
                        "durationSeconds": {"type": "integer", "description": "Poll open period in seconds (Telegram: 5-600)."},
                        "durationHours": {"type": "integer", "description": "Optional poll duration in hours."},
                        "silent": {"type": "boolean", "description": "Send poll silently if channel supports it."},
                        "isAnonymous": {"type": "boolean", "description": "Whether poll answers are anonymous."},
                        "threadId": {"type": "string", "description": "Forum topic thread id for Telegram supergroups."},
                        "emoji": {"type": "string", "description": "Reaction emoji (default 👍)"},
                        "remove": {"type": "boolean", "description": "Remove reaction when true"},
                        "path": {"type": "string", "description": "Attachment path for sendAttachment"},
                        "buffer": {"type": "string", "description": "Base64 attachment payload for sendAttachment"},
                        "filename": {"type": "string", "description": "Filename for buffer attachment"},
                        "caption": {"type": "string", "description": "Attachment caption"},
                        "effect": {"type": "string", "description": "Effect hint for sendWithEffect"},
                    },
                },
            },
        }
    ]


def parse_message_compat_args(arguments_str: str | dict) -> dict:
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except Exception:
        data = {}

    out = dict(data)
    action_raw = out.get("action")
    if isinstance(action_raw, str):
        out["action"] = _canonicalize_action(action_raw)
    if not isinstance(out.get("text"), str):
        for alias in ("message", "content", "body"):
            if isinstance(out.get(alias), str):
                out["text"] = out[alias]
                break
    if not isinstance(out.get("to"), str):
        for alias in ("channel_target", "target"):
            if isinstance(out.get(alias), str):
                out["to"] = out[alias]
                break
    if not isinstance(out.get("message_id"), str):
        for alias in ("messageId", "id"):
            if isinstance(out.get(alias), str):
                out["message_id"] = out[alias]
                break
            if isinstance(out.get(alias), int):
                out["message_id"] = str(out[alias])
                break
    if not isinstance(out.get("reply_to"), str):
        reply_to = out.get("replyTo")
        if isinstance(reply_to, str):
            out["reply_to"] = reply_to
        elif isinstance(reply_to, int):
            out["reply_to"] = str(reply_to)
    if "maxSelections" not in out and "max_selections" in out:
        out["maxSelections"] = out.get("max_selections")
    if "durationSeconds" not in out and "duration_seconds" in out:
        out["durationSeconds"] = out.get("duration_seconds")
    if "durationHours" not in out and "duration_hours" in out:
        out["durationHours"] = out.get("duration_hours")
    if "threadId" not in out and "thread_id" in out:
        out["threadId"] = out.get("thread_id")
    if "isAnonymous" not in out and "is_anonymous" in out:
        out["isAnonymous"] = out.get("is_anonymous")
    if not isinstance(out.get("action"), str):
        out["action"] = "send"
    return out


def _canonicalize_action(value: object) -> str:
    if not isinstance(value, str):
        return "send"
    raw = value.strip()
    if not raw:
        return "send"
    norm = raw.replace("_", "").replace("-", "").lower()
    return _ACTION_MAP.get(norm, raw)


def _to_positive_int(value: object) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _decode_base64_payload(payload: str) -> bytes | None:
    raw = (payload or "").strip()
    if not raw:
        return None
    # Support "data:*;base64,<payload>" as well as raw base64 text.
    if "," in raw and ";base64" in raw.split(",", 1)[0]:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        return None


def _to_non_negative_int(value: object) -> int | None:
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed >= 0 else None
    return None


def _normalize_poll_options(raw: object) -> list[str]:
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if str(v).strip()]
    elif isinstance(raw, str):
        chunks = [x.strip() for x in raw.replace("\r", "\n").replace(",", "\n").split("\n")]
        values = [x for x in chunks if x]
    else:
        values = []
    # Telegram supports 2..10 options.
    uniq: list[str] = []
    seen: set[str] = set()
    for v in values:
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    return uniq[:10]


async def _run_telegram_message_action(action: str, chat_id: str, params: dict) -> dict:
    from telegram import Bot, ReactionTypeEmoji
    from app.keys import get_api_key

    token = await get_api_key("telegram_bot_token")
    if not token:
        return {"ok": False, "error": "Telegram bot token is not configured."}
    bot = Bot(token=token)

    text = (params.get("text") or "").strip()
    message_id = _to_positive_int(params.get("message_id"))
    reply_to = _to_positive_int(params.get("reply_to")) or message_id

    if action in ("send", "sendWithEffect"):
        if not text:
            return {"ok": False, "error": "text is required for this action."}
        sent = await bot.send_message(chat_id=chat_id, text=text)
        payload = {
            "ok": True,
            "status": "sent",
            "action": action,
            "message_id": sent.message_id,
        }
        if action == "sendWithEffect":
            payload["effect"] = (params.get("effect") or "")
            payload["effect_applied"] = False
            payload["note"] = "Channel does not support message effects natively; sent as normal text."
        return payload

    if action == "reply":
        if not text:
            return {"ok": False, "error": "text is required for reply."}
        if not reply_to:
            return {"ok": False, "error": "replyTo (or messageId) is required for reply."}
        sent = await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to)
        return {
            "ok": True,
            "status": "sent",
            "action": "reply",
            "message_id": sent.message_id,
            "reply_to": reply_to,
        }

    if action == "react":
        if not message_id:
            return {"ok": False, "error": "messageId is required for react."}
        emoji = (params.get("emoji") or "👍").strip() or "👍"
        remove = _to_bool(params.get("remove"), default=False)
        if remove:
            await bot.set_message_reaction(chat_id=chat_id, message_id=message_id, reaction=[])
        else:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji)],
            )
        return {
            "ok": True,
            "status": "updated",
            "action": "react",
            "message_id": message_id,
            "emoji": emoji,
            "remove": remove,
        }

    if action == "edit":
        if not message_id:
            return {"ok": False, "error": "messageId is required for edit."}
        if not text:
            return {"ok": False, "error": "text is required for edit."}
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
        return {
            "ok": True,
            "status": "updated",
            "action": "edit",
            "message_id": message_id,
        }

    if action == "unsend":
        if not message_id:
            return {"ok": False, "error": "messageId is required for unsend."}
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return {
            "ok": True,
            "status": "deleted",
            "action": "unsend",
            "message_id": message_id,
        }

    if action == "sendAttachment":
        caption = (params.get("caption") or "").strip()
        path_raw = (params.get("path") or "").strip()
        file_bytes: bytes | None = None
        filename = (params.get("filename") or "").strip() or "attachment.bin"
        if path_raw:
            p = Path(path_raw).expanduser()
            try:
                p = p.resolve()
            except Exception:
                return {"ok": False, "error": "Invalid attachment path."}
            if not p.is_file():
                return {"ok": False, "error": f"Attachment not found: {p}"}
            try:
                file_bytes = p.read_bytes()
                filename = p.name
            except Exception as e:
                return {"ok": False, "error": f"Could not read attachment: {e}"}
        else:
            buffer_payload = params.get("buffer")
            if isinstance(buffer_payload, str):
                file_bytes = _decode_base64_payload(buffer_payload)
            if not file_bytes:
                return {"ok": False, "error": "sendAttachment requires `path` or base64 `buffer`."}
        if len(file_bytes) > 20 * 1024 * 1024:
            return {"ok": False, "error": "Attachment exceeds 20MB limit for compatibility mode."}

        from io import BytesIO
        sent = await bot.send_document(
            chat_id=chat_id,
            document=BytesIO(file_bytes),
            filename=filename,
            caption=caption or None,
        )
        return {
            "ok": True,
            "status": "sent",
            "action": "sendAttachment",
            "message_id": sent.message_id,
            "filename": filename,
        }

    if action == "sendPoll":
        question = (params.get("question") or params.get("text") or "").strip()
        options = _normalize_poll_options(params.get("options"))
        if not question:
            return {"ok": False, "error": "question is required for sendPoll."}
        if len(options) < 2:
            return {"ok": False, "error": "sendPoll requires at least 2 options."}
        if len(options) > 10:
            return {"ok": False, "error": "sendPoll supports at most 10 options."}

        max_selections = _to_positive_int(params.get("maxSelections")) or 1
        allows_multiple_answers = max_selections > 1

        duration_seconds = _to_positive_int(params.get("durationSeconds"))
        if duration_seconds is None:
            duration_hours = _to_non_negative_int(params.get("durationHours"))
            if duration_hours is not None and duration_hours > 0:
                duration_seconds = duration_hours * 3600
        if duration_seconds is not None:
            duration_seconds = max(5, min(duration_seconds, 600))

        silent = _to_bool(params.get("silent"), default=False)
        is_anonymous = _to_bool(params.get("isAnonymous"), default=True)
        thread_id = _to_positive_int(params.get("threadId"))
        if thread_id is None:
            thread_id = _to_positive_int(params.get("message_thread_id"))

        sent = await bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=options,
            allows_multiple_answers=allows_multiple_answers,
            is_anonymous=is_anonymous,
            open_period=duration_seconds,
            disable_notification=silent,
            message_thread_id=thread_id,
        )
        poll = getattr(sent, "poll", None)
        return {
            "ok": True,
            "status": "sent",
            "action": "sendPoll",
            "message_id": sent.message_id,
            "poll_id": getattr(poll, "id", None),
            "question": question,
            "options": options,
            "allows_multiple_answers": allows_multiple_answers,
            "duration_seconds": duration_seconds,
            "silent": silent,
            "is_anonymous": is_anonymous,
            "thread_id": thread_id,
        }

    return {"ok": False, "error": f"Unsupported action: {action}"}


async def run_message_compat(
    params: dict,
    *,
    current_channel: str,
    current_target: str,
) -> str:
    action = _canonicalize_action(params.get("action"))
    action_key = action.lower()
    if action_key not in _SUPPORTED_ACTION_SET:
        return json.dumps(
            {
                "ok": False,
                "error": "Unsupported action.",
                "action": action_key,
                "supported_actions": list(SUPPORTED_MESSAGE_ACTIONS),
            },
            indent=0,
        )

    requested_channel = (params.get("channel") or current_channel or "").strip().lower()
    effective_channel = (current_channel or "").strip().lower()
    if requested_channel and effective_channel and requested_channel != effective_channel:
        return json.dumps(
            {
                "ok": False,
                "error": "Cross-channel send is disabled in single-user mode.",
                "channel": effective_channel,
            },
            indent=0,
        )

    to = (params.get("to") or current_target or "").strip()
    if effective_channel == "telegram" and not to:
        return json.dumps(
            {"ok": False, "error": f"target is required for {effective_channel} sends"},
            indent=0,
        )
    if current_target and to and to != current_target:
        return json.dumps(
            {
                "ok": False,
                "error": "Cross-target send is disabled in single-user mode.",
                "target": current_target,
            },
            indent=0,
        )
    resolved_channel = effective_channel or requested_channel or "web"
    if resolved_channel == "telegram":
        try:
            payload = await _run_telegram_message_action(action, to, params)
        except Exception as e:
            payload = {"ok": False, "error": f"Telegram action failed: {e}", "action": action}
        payload["channel"] = resolved_channel
        payload["target"] = to
        return json.dumps(payload, indent=0)

    # Web fallback supports only simple send.
    if action_key != "send":
        return json.dumps(
            {
                "ok": False,
                "error": f"Action '{action}' is not supported on channel '{resolved_channel}'.",
                "action": action,
                "channel": resolved_channel,
                "target": to,
                "supported_actions": ["send"],
            },
            indent=0,
        )

    text = (params.get("text") or "").strip()
    if not text:
        return json.dumps({"ok": False, "error": "text is required for action=send"}, indent=0)
    await send_notification(resolved_channel, to, text)
    return json.dumps(
        {
            "ok": True,
            "status": "sent",
            "action": "send",
            "channel": resolved_channel,
            "target": to,
        },
        indent=0,
    )
