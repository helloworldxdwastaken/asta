import pytest

from app.apply_patch_compat_tool import (
    parse_apply_patch_compat_args,
    run_apply_patch_compat,
)
from app.config import get_settings


@pytest.fixture
def workspace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTA_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_parse_apply_patch_compat_args_alias():
    parsed = parse_apply_patch_compat_args({"patch": "*** Begin Patch\n*** End Patch"})
    assert parsed["input"] == "*** Begin Patch\n*** End Patch"


@pytest.mark.asyncio
async def test_apply_patch_add_update_delete(workspace_env):
    (workspace_env / "a.txt").write_text("hello world\n", encoding="utf-8")
    (workspace_env / "c.txt").write_text("to-delete\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: a.txt
@@
-hello world
+hello asta
*** Add File: b.txt
+one
+two
*** Delete File: c.txt
*** End Patch"""
    out = await run_apply_patch_compat({"input": patch})
    assert out.startswith("Success. Updated the following files:")
    assert "M a.txt" in out
    assert "A b.txt" in out
    assert "D c.txt" in out
    assert (workspace_env / "a.txt").read_text(encoding="utf-8") == "hello asta\n"
    assert (workspace_env / "b.txt").read_text(encoding="utf-8") == "one\ntwo\n"
    assert not (workspace_env / "c.txt").exists()


@pytest.mark.asyncio
async def test_apply_patch_move_file(workspace_env):
    (workspace_env / "src.txt").write_text("old value\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: src.txt
*** Move to: moved.txt
@@
-old value
+new value
*** End Patch"""
    out = await run_apply_patch_compat({"input": patch})
    assert out.startswith("Success.")
    assert (workspace_env / "moved.txt").read_text(encoding="utf-8") == "new value\n"
    assert not (workspace_env / "src.txt").exists()


@pytest.mark.asyncio
async def test_apply_patch_blocks_escape_path(workspace_env):
    patch = """*** Begin Patch
*** Add File: ../evil.txt
+oops
*** End Patch"""
    out = await run_apply_patch_compat({"input": patch})
    assert out.startswith("Error:")
    assert "inside workspace" in out
    assert not (workspace_env.parent / "evil.txt").exists()


@pytest.mark.asyncio
async def test_apply_patch_update_missing_lines_errors(workspace_env):
    (workspace_env / "x.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: x.txt
@@
-missing
+new
*** End Patch"""
    out = await run_apply_patch_compat({"input": patch})
    assert out.startswith("Error:")
    assert "Failed to find expected lines" in out
