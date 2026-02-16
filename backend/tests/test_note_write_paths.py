import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.handler import _canonicalize_note_write_path, handle_message
from app.providers.base import ProviderResponse
from app.routers import files as files_router


class _DummyProvider:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="")


async def _fake_compact_history(messages, provider, context=None, max_tokens=None):
    return messages


def test_canonicalize_note_write_path_handles_workspace_prefixed_variants():
    assert (
        _canonicalize_note_write_path("~/workspace/notes/work-door-design.md")
        == "notes/work-door-design.md"
    )
    assert _canonicalize_note_write_path("workspace/notes/sub/idea.txt") == "notes/sub/idea.md"
    assert _canonicalize_note_write_path("notes/quick-note") == "notes/quick-note.md"


def test_canonicalize_note_write_path_rewrites_absolute_and_home_paths_to_workspace_notes():
    assert _canonicalize_note_write_path("/Users/tokyo/asta/backend/notes/work-door-design.txt") == "notes/work-door-design.md"
    assert _canonicalize_note_write_path("~/notes/personal/idea") == "notes/personal/idea.md"


@pytest.mark.asyncio
async def test_handle_message_note_request_forces_notes_directory():
    turn = 0
    captured_path: dict[str, str] = {}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return (
                ProviderResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc_note_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path":"~/workspace/notes/work-door-design.md","content":"note body"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content="Saved."), primary

    async def _fake_write_file(path: str, content: str, user_id: str, db):
        captured_path["value"] = path
        return json.dumps({"ok": True, "path": f"/tmp/{path}"})

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.files_tool.write_file", side_effect=_fake_write_file),
    ):
        reply = await handle_message(
            user_id="test-note-path-canonical",
            channel="web",
            text="Take a note the door is 1.90 x 0.80",
            provider_name="openai",
        )

    assert captured_path.get("value") == "notes/work-door-design.md"
    assert "notes/work-door-design.md" in reply
    assert "didn't get a reply back" not in reply.lower()


@pytest.mark.asyncio
async def test_handle_message_note_request_rewrites_absolute_paths_to_workspace_notes():
    turn = 0
    captured_path: dict[str, str] = {}

    async def _fake_chat_with_fallback(primary, messages, fallback_names, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return (
                ProviderResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc_note_abs_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path":"/Users/tokyo/asta/backend/notes/work-door-design.md","content":"note body"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content="Saved."), primary

    async def _fake_write_file(path: str, content: str, user_id: str, db):
        captured_path["value"] = path
        return json.dumps({"ok": True, "path": f"/tmp/{path}"})

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.files_tool.write_file", side_effect=_fake_write_file),
    ):
        reply = await handle_message(
            user_id="test-note-path-abs",
            channel="web",
            text="Take a note the door is 1.90 x 0.80",
            provider_name="openai",
        )

    assert captured_path.get("value") == "notes/work-door-design.md"
    assert "notes/work-door-design.md" in reply
    assert "didn't get a reply back" not in reply.lower()


@pytest.mark.asyncio
async def test_handle_message_non_note_request_keeps_original_write_path():
    turn = 0
    captured_path: dict[str, str] = {}

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
                                "arguments": '{"path":"src/main.py","content":"print(1)"}',
                            },
                        }
                    ],
                ),
                primary,
            )
        return ProviderResponse(content="Done."), primary

    async def _fake_write_file(path: str, content: str, user_id: str, db):
        captured_path["value"] = path
        return json.dumps({"ok": True, "path": f"/tmp/{path}"})

    with (
        patch("app.handler.get_provider", return_value=_DummyProvider()),
        patch("app.compaction.compact_history", side_effect=_fake_compact_history),
        patch("app.providers.fallback.chat_with_fallback", side_effect=_fake_chat_with_fallback),
        patch("app.files_tool.write_file", side_effect=_fake_write_file),
    ):
        reply = await handle_message(
            user_id="test-note-path-non-note",
            channel="web",
            text="create src main file",
            provider_name="openai",
        )

    assert captured_path.get("value") == "src/main.py"
    assert "src/main.py" in reply
    assert "didn't get a reply back" not in reply.lower()


@pytest.mark.asyncio
async def test_write_to_allowed_path_normalizes_workspace_prefixed_relative_paths(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    async def _fake_allowed_paths(user_id: str = "default"):
        return [workspace]

    monkeypatch.setattr(files_router, "_allowed_paths", _fake_allowed_paths)
    monkeypatch.setattr(files_router, "get_settings", lambda: SimpleNamespace(workspace_path=workspace))

    written = await files_router.write_to_allowed_path(
        user_id="default",
        path="~/workspace/notes/door.md",
        content="hello",
    )

    expected = workspace / "notes" / "door.md"
    assert written == str(expected)
    assert expected.read_text(encoding="utf-8") == "hello"


@pytest.mark.asyncio
async def test_read_file_resolves_workspace_relative_note_paths(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    note = workspace / "notes" / "door.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("door details", encoding="utf-8")

    async def _fake_allowed_paths(user_id: str = "default"):
        return [workspace]

    monkeypatch.setattr(files_router, "_allowed_paths", _fake_allowed_paths)
    monkeypatch.setattr(files_router, "get_settings", lambda: SimpleNamespace(workspace_path=workspace))

    out = await files_router.read_file(path="notes/door.md", user_id="default")

    assert out["path"] == "notes/door.md"
    assert out["content"] == "door details"
