"""Chat and incoming webhook routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.handler import handle_message
from app.db import get_db
from app.providers.registry import list_providers

router = APIRouter()


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


class IncomingWhatsApp(BaseModel):
    from_number: str
    message: str


@router.post("/incoming/whatsapp")
@router.post("/incoming/whatsapp")
async def incoming_whatsapp(body: IncomingWhatsApp):
    """Called by WhatsApp bridge when a message is received. Reminders will be sent back to this number."""
    from app.config import get_settings
    from app.db import get_db
    import logging
    
    settings = get_settings()
    whitelist = settings.whatsapp_whitelist
    
    # Add auto-detected owner from DB
    try:
        db = get_db()
        await db.connect()
        owner = await db.get_system_config("whatsapp_owner")
        if owner:
            whitelist.add(owner)
    except Exception as e:
        logging.error(f"Failed to get whatsapp_owner: {e}")
    
    user_id = f"wa:{body.from_number}"
    # Strip suffix (e.g. @s.whatsapp.net or @lid) for whitelist check
    clean_number = body.from_number.split("@")[0] if "@" in body.from_number else body.from_number

    # Whitelist check
    if whitelist and clean_number not in whitelist and body.from_number not in whitelist:
        logging.warning(f"WhatsApp message from {body.from_number} ignored (not in whitelist).")
        return {"ignored": True}

    reply = await handle_message(
        user_id, "whatsapp", body.message, provider_name="default",
        channel_target=body.from_number,
    )

    return {"reply": reply}
