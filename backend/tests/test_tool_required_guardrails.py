import json
from unittest.mock import patch

import pytest

from app.handler import handle_message
from app.providers.base import ProviderResponse


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="ok")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


async def _fake_chat_with_fallback_no_tools(primary, messages, fallback_names, **kwargs):
    return ProviderResponse(content="I'll check that now."), primary


@pytest.mark.asyncio
async def test_files_check_uses_deterministic_fallback_when_model_skips_tools(monkeypatch):
    async def _fake_list_directory(path: str, user_id: str, db):
        return json.dumps(
            {
                "path": "/Users/test/Desktop",
                "entries": [
                    {"name": "TattooStudioWebsite", "kind": "dir", "size": None},
                    {"name": "todo.txt", "kind": "file", "size": 22},
                ],
            }
        )

    monkeypatch.setattr("app.files_tool.list_directory", _fake_list_directory)

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback_no_tools),
    ):
        reply = await handle_message(
            user_id="test-files-fallback",
            channel="web",
            text="Can you check my desktop for TattooStudioWebsite?",
            provider_name="openai",
        )

    assert 'I checked /Users/test/Desktop and found 1 match(es) for "TattooStudioWebsite"' in reply
    assert "TattooStudioWebsite" in reply


@pytest.mark.asyncio
async def test_exec_check_without_tool_call_returns_unverified_guardrail():
    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback_no_tools),
    ):
        reply = await handle_message(
            user_id="test-exec-guardrail",
            channel="web",
            text="Can you check my Apple notes?",
            provider_name="openai",
        )

    assert "I couldn't verify that yet because no Terminal tool call was executed." in reply


@pytest.mark.asyncio
async def test_bracket_files_protocol_executes_tools_and_does_not_leak():
    async def _fake_chat_with_fallback_bracket(primary, messages, fallback_names, **kwargs):
        return ProviderResponse(
            content='[allow_path: path="~/Desktop"]\n[list_directory: path="~/Desktop"]'
        ), primary

    class _SecondPassProvider:
        name = "openai"

        async def chat(self, messages, **kwargs):
            return ProviderResponse(content="I found 4 screenshots on your Desktop.")

    async def _fake_allow_path(path: str, user_id: str, db):
        return f"Allowed path: {path}"

    async def _fake_list_directory(path: str, user_id: str, db):
        return json.dumps(
            {
                "path": "/Users/test/Desktop",
                "entries": [
                    {"name": "Screenshot 1.png", "kind": "file", "size": 1200},
                    {"name": "Screenshot 2.png", "kind": "file", "size": 1400},
                    {"name": "Screenshot 3.png", "kind": "file", "size": 1000},
                    {"name": "Screenshot 4.png", "kind": "file", "size": 1100},
                ],
            }
        )

    with (
        patch("app.handler.get_provider", return_value=_SecondPassProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback_bracket),
        patch("app.files_tool.allow_path", side_effect=_fake_allow_path),
        patch("app.files_tool.list_directory", side_effect=_fake_list_directory),
    ):
        reply = await handle_message(
            user_id="test-files-bracket-protocol",
            channel="web",
            text="Nice any screenshots on my desktop?",
            provider_name="openai",
        )

    low = reply.lower()
    assert "[allow_path:" not in low
    assert "[list_directory:" not in low
    assert "i found 4 screenshots" in low
