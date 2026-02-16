import json
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


@pytest.mark.asyncio
async def test_exec_empty_model_reply_surfaces_last_exec_error(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "full")
    get_settings.cache_clear()

    async def _fake_run_allowlisted_command(
        cmd: str,
        allowed_bins=None,
        timeout_seconds=None,
        workdir=None,
    ):
        assert cmd == "echo should-fail"
        return "", "Command exited with code 2", False

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
                                "arguments": '{"command":"echo should-fail"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content=""), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.exec_tool.run_allowlisted_command", side_effect=_fake_run_allowlisted_command),
    ):
        reply = await handle_message(
            user_id="test-exec-openclaw-fallback",
            channel="web",
            text="Run this command",
            provider_name="openai",
        )

    assert "Exec failed" in reply
    assert "Command exited with code 2" in reply
    assert "didn't get a reply back" not in reply.lower()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_files_write_empty_model_reply_surfaces_last_tool_error():
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
                            "id": "tc_write_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path":"notes/work-door.txt","content":"door notes"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content=""), primary

    async def _fake_write_file(path: str, content: str, user_id: str, db):
        assert path == "notes/work-door.md"
        return "Error: Path /Users/test/notes/work-door.md is not in the allowed list."

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.files_tool.write_file", side_effect=_fake_write_file),
    ):
        reply = await handle_message(
            user_id="test-files-write-fallback-error",
            channel="web",
            text="Take a note about the door size",
            provider_name="openai",
        )

    assert "Files (write) failed" in reply
    assert "allowed list" in reply
    assert "didn't get a reply back" not in reply.lower()


@pytest.mark.asyncio
async def test_files_write_empty_model_reply_surfaces_tool_output_excerpt():
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
                            "id": "tc_write_2",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path":"notes/work-door.txt","content":"door notes"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content=""), primary

    async def _fake_write_file(path: str, content: str, user_id: str, db):
        assert path == "notes/work-door.md"
        return json.dumps({"ok": True, "path": "/Users/test/workspace/notes/work-door.md"}, indent=0)

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.files_tool.write_file", side_effect=_fake_write_file),
    ):
        reply = await handle_message(
            user_id="test-files-write-fallback-output",
            channel="web",
            text="Take a note about the door size",
            provider_name="openai",
        )

    assert "I ran Files (write) but the model didn't return a reply." in reply
    assert "/Users/test/workspace/notes/work-door.md" in reply
    assert "didn't get a reply back" not in reply.lower()


@pytest.mark.asyncio
async def test_generic_notes_request_prefers_workspace_notes_over_exec_error(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "full")
    get_settings.cache_clear()

    async def _fake_run_allowlisted_command(
        cmd: str,
        allowed_bins=None,
        timeout_seconds=None,
        workdir=None,
    ):
        assert cmd == "memo notes list"
        return "", "Error: Got unexpected extra argument (list)", False

    async def _fake_get_workspace_notes(limit: int = 20):
        return {
            "notes": [
                {
                    "name": "work-door-design.md",
                    "path": "notes/work-door-design.md",
                    "size": 1200,
                    "modified_at": "2026-02-16T18:20:00Z",
                }
            ]
        }

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
                            "id": "tc_exec_notes_1",
                            "type": "function",
                            "function": {
                                "name": "exec",
                                "arguments": '{"command":"memo notes list"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content=""), primary

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.exec_tool.run_allowlisted_command", side_effect=_fake_run_allowlisted_command),
        patch("app.routers.settings.get_workspace_notes", side_effect=_fake_get_workspace_notes),
    ):
        reply = await handle_message(
            user_id="test-notes-fallback-over-exec-error",
            channel="web",
            text="What notes I have?",
            provider_name="openai",
        )

    assert "You have 1 workspace note(s)" in reply
    assert "work-door-design.md" in reply
    assert "Exec failed" not in reply
    get_settings.cache_clear()
