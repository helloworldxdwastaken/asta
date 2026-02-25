from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.db import get_db
import app.routers.chat as chat_router


@pytest.mark.asyncio
async def test_truncate_conversation_route_rewinds_messages():
    db = get_db()
    await db.connect()
    user_id = f"test-truncate-{uuid.uuid4().hex[:8]}"
    cid = await db.create_new_conversation(user_id, "web")
    await db.add_message(cid, "user", "first")
    await db.add_message(cid, "assistant", "first reply")
    await db.add_message(cid, "user", "second")
    await db.add_message(cid, "assistant", "second reply")

    out = await chat_router.truncate_conversation(
        cid,
        chat_router.ConversationTruncateIn(keep_count=2),
        user_id=user_id,
    )
    assert out["ok"] is True
    assert out["deleted"] == 2

    rows = await db.get_recent_messages(cid, limit=20)
    assert [r["content"] for r in rows] == ["first", "first reply"]


@pytest.mark.asyncio
async def test_truncate_conversation_route_checks_user_ownership():
    db = get_db()
    await db.connect()
    owner = f"test-truncate-owner-{uuid.uuid4().hex[:8]}"
    cid = await db.create_new_conversation(owner, "web")

    with pytest.raises(HTTPException) as exc:
        await chat_router.truncate_conversation(
            cid,
            chat_router.ConversationTruncateIn(keep_count=0),
            user_id=f"other-{uuid.uuid4().hex[:6]}",
        )

    assert exc.value.status_code == 403
