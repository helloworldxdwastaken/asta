"""Chat and incoming webhook routes."""
import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.handler import handle_message
from app.db import get_db
from app.providers.registry import list_providers
from app.message_queue import queue_key
from app.auth_utils import get_current_user_id, get_current_user_role

router = APIRouter()



@router.get("/chat/conversations")
async def list_conversations(
    request: Request,
    channel: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """Return list of conversations for the sidebar."""
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    convs = await db.list_conversations(user_id, channel, limit)
    return {"conversations": convs}


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    request: Request,
    conversation_id: str,
):
    user_id = get_current_user_id(request)
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
    request: Request,
    conversation_id: str,
    body: ConversationTruncateIn,
):
    user_id = get_current_user_id(request)
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
async def list_folders(request: Request, channel: str = Query("web")):
    user_id = get_current_user_id(request)
    db = get_db(); await db.connect()
    return {"folders": await db.list_folders(user_id, channel)}


@router.post("/chat/folders")
async def create_folder(request: Request, body: FolderIn, channel: str = Query("web")):
    import uuid
    user_id = get_current_user_id(request)
    db = get_db(); await db.connect()
    folder_id = str(uuid.uuid4())
    result = await db.create_folder(user_id, channel, folder_id, body.name.strip(), body.color)
    return result


@router.patch("/chat/folders/{folder_id}")
async def update_folder(request: Request, folder_id: str, body: FolderPatch):
    user_id = get_current_user_id(request)
    db = get_db(); await db.connect()
    await db.update_folder(folder_id, user_id, name=body.name, color=body.color)
    return {"ok": True}


@router.delete("/chat/folders/{folder_id}")
async def delete_folder(request: Request, folder_id: str):
    user_id = get_current_user_id(request)
    db = get_db(); await db.connect()
    await db.delete_folder(folder_id, user_id)
    return {"ok": True}


_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "workspace"


def _project_dir(folder_id: str) -> Path:
    return _WORKSPACE_ROOT / "projects" / folder_id


async def _verify_folder_owner(request: Request, folder_id: str):
    """Verify the current user owns the folder. Raises 403 if not."""
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    owner = await db.get_folder_owner(folder_id)
    if not owner or owner != user_id:
        raise HTTPException(status_code=403, detail="Folder not found or access denied")
    return user_id


@router.post("/chat/folders/{folder_id}/files")
async def upload_project_file(
    request: Request,
    folder_id: str,
    file: UploadFile = File(...),
):
    """Upload a file to a project folder."""
    await _verify_folder_owner(request, folder_id)
    project_dir = _project_dir(folder_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    filename = os.path.basename(file.filename or "upload")
    dest = project_dir / filename
    content = await file.read()
    dest.write_bytes(content)
    return {"ok": True, "path": str(dest), "filename": filename}


@router.get("/chat/folders/{folder_id}/files")
async def list_project_files(request: Request, folder_id: str):
    """List files in a project folder."""
    await _verify_folder_owner(request, folder_id)
    project_dir = _project_dir(folder_id)
    if not project_dir.exists():
        return {"files": []}
    files = []
    for p in sorted(project_dir.iterdir()):
        if p.is_file() and p.name != "project.md":
            stat = p.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            files.append({"name": p.name, "size": stat.st_size, "modified": mtime})
    return {"files": files}


@router.delete("/chat/folders/{folder_id}/files/{filename}")
async def delete_project_file(request: Request, folder_id: str, filename: str):
    """Delete a specific file from a project folder."""
    await _verify_folder_owner(request, folder_id)
    dest = _project_dir(folder_id) / os.path.basename(filename)
    if dest.exists() and dest.is_file():
        dest.unlink()
    return {"ok": True}


@router.get("/chat/folders/{folder_id}/context")
async def get_project_context(request: Request, folder_id: str):
    """Return the content of project.md for a project folder."""
    await _verify_folder_owner(request, folder_id)
    project_md = _project_dir(folder_id) / "project.md"
    content = project_md.read_text(encoding="utf-8") if project_md.exists() else ""
    return {"content": content}


@router.put("/chat/conversations/{conversation_id}/folder")
async def set_conversation_folder(
    request: Request,
    conversation_id: str,
    body: FolderAssign,
):
    user_id = get_current_user_id(request)
    db = get_db(); await db.connect()
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    await db.set_conversation_folder(conversation_id, user_id, body.folder_id)
    return {"ok": True}


@router.get("/chat/messages")
async def get_chat_messages(
    request: Request,
    conversation_id: str = Query(..., description="Conversation ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """Return recent messages for a conversation so clients can render the thread history."""
    user_id = get_current_user_id(request)
    if not conversation_id.startswith(user_id + ":"):
        raise HTTPException(403, "Conversation does not belong to this user")
    db = get_db()
    await db.connect()
    rows = await db.get_recent_messages(conversation_id, limit=limit)
    return {"conversation_id": conversation_id, "messages": rows}


class ChatIn(BaseModel):
    text: str
    provider: str = "default"
    user_id: str = "default"  # kept for backward compat but overridden by JWT
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
async def chat(request: Request, body: ChatIn):
    user_id = get_current_user_id(request)
    user_role = get_current_user_role(request)
    try:
        db = get_db()
        await db.connect()
        cid = body.conversation_id or await db.create_new_conversation(user_id, "web")
        provider = body.provider
        if provider == "default":
            provider = await db.get_user_default_ai(user_id)
        image_bytes = None
        if body.image_base64:
            try:
                image_bytes = base64.b64decode(body.image_base64)
            except Exception:
                image_bytes = None
        _out: dict = {}
        async with queue_key(f"web:{cid}"):
            reply = await handle_message(
                user_id, "web", body.text,
                provider_name=provider,
                conversation_id=cid,
                channel_target="web",
                mood=body.mood,
                extra_context={"force_web": bool(body.web)} if body.web else None,
                image_bytes=image_bytes,
                image_mime=body.image_mime,
                _out=_out,
                user_role=user_role,
            )
        actual_provider = _out.get("provider", provider)
        return ChatOut(reply=reply, conversation_id=cid, provider=actual_provider)
    except Exception as e:
        reply = str(e).strip() or "Unknown error"
        if not reply.startswith("Error:"):
            reply = f"Error: {reply[:300]}"
        return ChatOut(reply=reply, conversation_id=body.conversation_id or f"{user_id}:web", provider=body.provider)


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatIn):
    """Streaming chat endpoint (SSE): emits assistant/reasoning/status/done events."""
    user_id = get_current_user_id(request)
    user_role = get_current_user_role(request)
    db = get_db()
    await db.connect()
    cid = body.conversation_id or await db.create_new_conversation(user_id, "web")
    provider = body.provider
    if provider == "default":
        provider = await db.get_user_default_ai(user_id)

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
                    user_id,
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
                    user_role=user_role,
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
