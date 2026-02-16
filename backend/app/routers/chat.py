"""Chat and incoming webhook routes."""
import asyncio
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.handler import handle_message
from app.db import get_db
from app.providers.registry import list_providers
from app.message_queue import queue_key

router = APIRouter()


def _normalize_wa_number(raw: str) -> str:
    base = (raw or "").strip()
    if "@" in base:
        base = base.split("@", 1)[0]
    return "".join(ch for ch in base if ch.isdigit())


def _whatsapp_sender_allowed(
    *,
    whitelist: set[str],
    owner_number: str,
    self_chat_only: bool,
    raw_number: str,
) -> bool:
    clean = _normalize_wa_number(raw_number)
    owner = _normalize_wa_number(owner_number)
    if self_chat_only:
        return bool(owner) and clean == owner
    if not whitelist:
        return True
    return (clean in whitelist) or (raw_number in whitelist)


@router.get("/chat/messages")
async def get_chat_messages(
    conversation_id: str = Query(..., description="Conversation ID, e.g. default:web or default:telegram"),
    user_id: str = Query("default", description="User ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """Return recent messages for a conversation so the web UI can show Web vs Telegram thread."""
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    db = get_db()
    await db.connect()
    rows = await db.get_recent_messages(conversation_id, limit=limit)
    return {"conversation_id": conversation_id, "messages": rows}


class ChatIn(BaseModel):
    text: str
    provider: str = "default"
    user_id: str = "default"
    conversation_id: str | None = None
    mood: str | None = None  # serious | friendly | normal


class ChatOut(BaseModel):
    reply: str
    conversation_id: str
    provider: str


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn):
    try:
        db = get_db()
        await db.connect()
        cid = body.conversation_id or await db.get_or_create_conversation(body.user_id, "web")
        provider = body.provider
        if provider == "default":
            provider = await db.get_user_default_ai(body.user_id)
        async with queue_key(f"web:{cid}"):
            reply = await handle_message(
                body.user_id, "web", body.text,
                provider_name=provider,
                conversation_id=cid,
                channel_target="web",
                mood=body.mood,
            )
        return ChatOut(reply=reply, conversation_id=cid, provider=provider)
    except Exception as e:
        reply = str(e).strip() or "Unknown error"
        if not reply.startswith("Error:"):
            reply = f"Error: {reply[:300]}"
        return ChatOut(reply=reply, conversation_id=body.conversation_id or "default:web", provider=body.provider)


@router.post("/chat/stream")
async def chat_stream(body: ChatIn):
    """Streaming chat endpoint (SSE): emits assistant/reasoning/status/done events."""
    db = get_db()
    await db.connect()
    cid = body.conversation_id or await db.get_or_create_conversation(body.user_id, "web")
    provider = body.provider
    if provider == "default":
        provider = await db.get_user_default_ai(body.user_id)

    event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _emit_event(payload: dict) -> None:
        await event_queue.put(payload)

    async def _run_chat() -> None:
        try:
            async with queue_key(f"web:{cid}"):
                reply = await handle_message(
                    body.user_id,
                    "web",
                    body.text,
                    provider_name=provider,
                    conversation_id=cid,
                    channel_target="web",
                    mood=body.mood,
                    extra_context={"_stream_event_callback": _emit_event},
                )
            await event_queue.put(
                {
                    "type": "done",
                    "reply": reply,
                    "conversation_id": cid,
                    "provider": provider,
                }
            )
        except Exception as e:
            msg = str(e).strip() or "Unknown error"
            if not msg.startswith("Error:"):
                msg = f"Error: {msg[:300]}"
            await event_queue.put(
                {
                    "type": "error",
                    "error": msg,
                    "conversation_id": cid,
                    "provider": provider,
                }
            )
        finally:
            await event_queue.put(None)

    task = asyncio.create_task(_run_chat(), name=f"chat-stream:{cid}")

    async def _sse_iter():
        meta = {
            "type": "meta",
            "conversation_id": cid,
            "provider": provider,
        }
        yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"
        while True:
            item = await event_queue.get()
            if item is None:
                break
            event_name = str(item.get("type") or "message")
            yield f"event: {event_name}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
        await task

    return StreamingResponse(
        _sse_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class IncomingWhatsApp(BaseModel):
    from_number: str
    reply_to: str | None = None
    message: str


@router.post("/incoming/whatsapp")
async def incoming_whatsapp(body: IncomingWhatsApp):
    """Called by WhatsApp bridge when a message is received. Reminders will be sent back to this number."""
    from app.config import get_settings
    from app.db import get_db
    import logging
    
    settings = get_settings()
    whitelist = set(settings.whatsapp_whitelist)
    
    # Add auto-detected owner from DB
    owner = ""
    try:
        db = get_db()
        await db.connect()
        owner = (await db.get_system_config("whatsapp_owner")) or ""
        if owner:
            whitelist.add(owner)
    except Exception as e:
        logging.error(f"Failed to get whatsapp_owner: {e}")
    
    reply_target = (body.reply_to or body.from_number or "").strip()
    user_id = f"wa:{body.from_number}"
    # Strip suffix (e.g. @s.whatsapp.net or @lid) for whitelist check
    if not _whatsapp_sender_allowed(
        whitelist=whitelist,
        owner_number=owner,
        self_chat_only=bool(settings.asta_whatsapp_self_chat_only),
        raw_number=body.from_number,
    ):
        logging.warning(f"WhatsApp message from {body.from_number} ignored by policy.")
        return {"ignored": True}

    async with queue_key(f"whatsapp:{reply_target or body.from_number}"):
        reply = await handle_message(
            user_id, "whatsapp", body.message, provider_name="default",
            channel_target=reply_target or body.from_number,
        )

    return {"reply": reply}
