"""Chat and incoming webhook routes."""
import asyncio
import base64
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.handler import handle_message
from app.db import get_db
from app.providers.registry import list_providers
from app.message_queue import queue_key

router = APIRouter()



@router.get("/chat/conversations")
async def list_conversations(
    user_id: str = Query("default"),
    channel: str = Query("web"),
    limit: int = Query(50, ge=1, le=100),
):
    """Return list of conversations for the sidebar."""
    db = get_db()
    await db.connect()
    convs = await db.list_conversations(user_id, channel, limit)
    return {"conversations": convs}


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Query("default"),
):
    db = get_db()
    await db.connect()
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    await db.delete_conversation(conversation_id)
    return {"ok": True}


class ConversationTruncateIn(BaseModel):
    keep_count: int = 0


@router.post("/chat/conversations/{conversation_id}/truncate")
async def truncate_conversation(
    conversation_id: str,
    body: ConversationTruncateIn,
    user_id: str = Query("default"),
):
    db = get_db()
    await db.connect()
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    keep_count = max(0, int(body.keep_count or 0))
    deleted = await db.truncate_conversation_messages(conversation_id, keep_count)
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "keep_count": keep_count,
        "deleted": deleted,
    }


# ── Conversation folders ─────────────────────────────────────────────────────

class FolderIn(BaseModel):
    name: str
    color: str = "#6366F1"

class FolderPatch(BaseModel):
    name: str | None = None
    color: str | None = None

class FolderAssign(BaseModel):
    folder_id: str | None = None


@router.get("/chat/folders")
async def list_folders(user_id: str = Query("default"), channel: str = Query("web")):
    db = get_db(); await db.connect()
    return {"folders": await db.list_folders(user_id, channel)}


@router.post("/chat/folders")
async def create_folder(body: FolderIn, user_id: str = Query("default"), channel: str = Query("web")):
    import uuid
    db = get_db(); await db.connect()
    folder_id = str(uuid.uuid4())
    result = await db.create_folder(user_id, channel, folder_id, body.name.strip(), body.color)
    return result


@router.patch("/chat/folders/{folder_id}")
async def update_folder(folder_id: str, body: FolderPatch, user_id: str = Query("default")):
    db = get_db(); await db.connect()
    await db.update_folder(folder_id, user_id, name=body.name, color=body.color)
    return {"ok": True}


@router.delete("/chat/folders/{folder_id}")
async def delete_folder(folder_id: str, user_id: str = Query("default")):
    db = get_db(); await db.connect()
    await db.delete_folder(folder_id, user_id)
    return {"ok": True}


@router.put("/chat/conversations/{conversation_id}/folder")
async def set_conversation_folder(
    conversation_id: str,
    body: FolderAssign,
    user_id: str = Query("default"),
):
    db = get_db(); await db.connect()
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    await db.set_conversation_folder(conversation_id, user_id, body.folder_id)
    return {"ok": True}


@router.get("/chat/messages")
async def get_chat_messages(
    conversation_id: str = Query(..., description="Conversation ID, e.g. default:web or default:telegram"),
    user_id: str = Query("default", description="User ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """Return recent messages for a conversation so clients can render the thread history."""
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
    web: bool = False  # if true, prefer web_search/web_fetch tools
    image_base64: str | None = None  # optional image payload for vision
    image_mime: str | None = None


class ChatOut(BaseModel):
    reply: str
    conversation_id: str
    provider: str


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn):
    try:
        db = get_db()
        await db.connect()
        cid = body.conversation_id or await db.create_new_conversation(body.user_id, "web")
        provider = body.provider
        if provider == "default":
            provider = await db.get_user_default_ai(body.user_id)
        image_bytes = None
        if body.image_base64:
            try:
                image_bytes = base64.b64decode(body.image_base64)
            except Exception:
                image_bytes = None
        _out: dict = {}
        async with queue_key(f"web:{cid}"):
            reply = await handle_message(
                body.user_id, "web", body.text,
                provider_name=provider,
                conversation_id=cid,
                channel_target="web",
                mood=body.mood,
                extra_context={"force_web": bool(body.web)} if body.web else None,
                image_bytes=image_bytes,
                image_mime=body.image_mime,
                _out=_out,
            )
        actual_provider = _out.get("provider", provider)
        return ChatOut(reply=reply, conversation_id=cid, provider=actual_provider)
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
    cid = body.conversation_id or await db.create_new_conversation(body.user_id, "web")
    provider = body.provider
    if provider == "default":
        provider = await db.get_user_default_ai(body.user_id)

    event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _emit_event(payload: dict) -> None:
        await event_queue.put(payload)

    async def _run_chat() -> None:
        try:
            image_bytes = None
            if body.image_base64:
                try:
                    image_bytes = base64.b64decode(body.image_base64)
                except Exception:
                    image_bytes = None
            _out: dict = {}
            async with queue_key(f"web:{cid}"):
                reply = await handle_message(
                    body.user_id,
                    "web",
                    body.text,
                    provider_name=provider,
                    conversation_id=cid,
                    channel_target="web",
                    mood=body.mood,
                    extra_context={
                        "_stream_event_callback": _emit_event,
                        **({"force_web": True} if body.web else {}),
                    },
                    image_bytes=image_bytes,
                    image_mime=body.image_mime,
                    _out=_out,
                )
            actual_provider = _out.get("provider", provider)
            await event_queue.put(
                {
                    "type": "done",
                    "reply": reply,
                    "conversation_id": cid,
                    "provider": actual_provider,
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
