import uuid
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.db import get_db
from app.exec_tool import SYSTEM_CONFIG_EXEC_BINS_KEY
from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None, **kwargs):
    return messages


@pytest.mark.asyncio
async def test_exec_disallowed_bin_creates_pending_approval(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "allowlist")
    monkeypatch.setenv("ASTA_EXEC_ALLOWED_BINS", "memo")
    get_settings.cache_clear()

    db = get_db()
    await db.connect()
    # Keep test deterministic even if prior tests/users persisted extra allowlist bins.
    await db.set_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY, "")
    user_id = f"test-exec-approval-{uuid.uuid4().hex[:8]}"

    existing = await db.list_pending_exec_approvals(limit=100)
    existing_ids = {str(r.get("approval_id") or "") for r in existing}

    turn = 0

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return (
                ProviderResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc_exec_1",
                            "type": "function",
                            "function": {
                                "name": "exec",
                                "arguments": "{\"command\":\"rg todo\"}",
                            },
                        }
                    ],
                ),
                primary,
            )
        tool_contents = [str(m.get("content") or "") for m in messages if m.get("role") == "tool"]
        assert any("approval-needed:" in t for t in tool_contents)
        return ProviderResponse(content="This needs your approval first."), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
    ):
        reply = await handle_message(
            user_id=user_id,
            channel="web",
            text="search notes for todo",
            provider_name="openai",
        )

    assert reply.strip()

    pending = await db.list_pending_exec_approvals(limit=100)
    created = [
        row
        for row in pending
        if str(row.get("approval_id") or "") not in existing_ids
        and str(row.get("user_id") or "") == user_id
    ]
    assert len(created) == 1
    row = created[0]
    assert row["binary"] == "rg"
    assert row["command"] == "rg todo"
    assert row["status"] == "pending"

    get_settings.cache_clear()
