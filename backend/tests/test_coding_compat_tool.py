import json

import pytest

from app.coding_compat_tool import (
    parse_coding_compat_args,
    run_edit_compat,
    run_read_compat,
    run_write_compat,
)
from app.config import get_settings


@pytest.fixture
def workspace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTA_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_parse_coding_compat_args_aliases():
    parsed = parse_coding_compat_args(
        {
            "file_path": "notes/test.md",
            "old_string": "old",
            "new_string": "new",
            "maxChars": "123",
        }
    )
    assert parsed["path"] == "notes/test.md"
    assert parsed["oldText"] == "old"
    assert parsed["newText"] == "new"
    assert parsed["max_chars"] == 123


@pytest.mark.asyncio
async def test_read_write_edit_compat_relative_workspace_paths(workspace_env):
    write_params = parse_coding_compat_args(
        {
            "file_path": "notes/test.md",
            "content": "hello world",
        }
    )
    wrote = await run_write_compat(write_params, user_id="default", db=None)
    wrote_payload = json.loads(wrote)
    assert wrote_payload["ok"] is True

    read_params = parse_coding_compat_args({"path": "notes/test.md"})
    content = await run_read_compat(read_params, user_id="default", db=None)
    assert content == "hello world"

    edit_params = parse_coding_compat_args(
        {
            "path": "notes/test.md",
            "old_string": "world",
            "new_string": "asta",
        }
    )
    edited = await run_edit_compat(edit_params, user_id="default", db=None)
    edited_payload = json.loads(edited)
    assert edited_payload["ok"] is True
    assert edited_payload["replaced"] == 1

    content_after = await run_read_compat(read_params, user_id="default", db=None)
    assert content_after == "hello asta"
    assert (workspace_env / "notes" / "test.md").is_file()


@pytest.mark.asyncio
async def test_read_compat_blocks_paths_outside_allowed_workspace(workspace_env):
    outside = workspace_env.parent / "outside-compat-test.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        result = await run_read_compat({"path": str(outside)}, user_id="default", db=None)
        assert result.startswith("Error:")
        assert "not in the allowed list" in result
    finally:
        outside.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_edit_compat_requires_oldtext_and_newtext(workspace_env):
    target = workspace_env / "edit-check.txt"
    target.write_text("hello", encoding="utf-8")

    missing_old = await run_edit_compat(
        {"path": str(target), "newText": "x"},
        user_id="default",
        db=None,
    )
    assert "oldText" in missing_old

    missing_new = await run_edit_compat(
        {"path": str(target), "oldText": "hello"},
        user_id="default",
        db=None,
    )
    assert "newText" in missing_new
