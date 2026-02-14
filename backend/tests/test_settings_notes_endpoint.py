import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.routers import settings as settings_router


@pytest.mark.asyncio
async def test_get_workspace_notes_lists_markdown_sorted_and_limited(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    notes = workspace / "notes"
    sub = notes / "sub"
    sub.mkdir(parents=True, exist_ok=True)

    first = notes / "first.md"
    second = sub / "second.md"
    ignored = notes / "ignore.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    ignored.write_text("ignore", encoding="utf-8")

    os.utime(first, (1_000, 1_000))
    os.utime(second, (2_000, 2_000))

    monkeypatch.setattr(settings_router, "get_settings", lambda: SimpleNamespace(workspace_path=workspace))

    out = await settings_router.get_workspace_notes(limit=1)
    notes_out = out.get("notes") or []
    assert len(notes_out) == 1
    assert notes_out[0]["name"] == "second.md"
    assert notes_out[0]["path"] == "notes/sub/second.md"


@pytest.mark.asyncio
async def test_get_workspace_notes_returns_empty_without_notes_dir(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings_router, "get_settings", lambda: SimpleNamespace(workspace_path=workspace))

    out = await settings_router.get_workspace_notes(limit=20)
    assert out == {"notes": []}


@pytest.mark.asyncio
async def test_get_workspace_notes_includes_legacy_nested_workspace_notes(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    legacy_notes = workspace / "workspace" / "notes"
    legacy_notes.mkdir(parents=True, exist_ok=True)
    note = legacy_notes / "legacy.md"
    note.write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(settings_router, "get_settings", lambda: SimpleNamespace(workspace_path=workspace))

    out = await settings_router.get_workspace_notes(limit=20)
    notes_out = out.get("notes") or []
    assert any(item.get("path") == "workspace/notes/legacy.md" for item in notes_out)
