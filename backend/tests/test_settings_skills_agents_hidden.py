from __future__ import annotations

from pathlib import Path

import pytest

import app.routers.settings as settings_router
from app.workspace import ResolvedSkill


class _DummyDB:
    async def connect(self) -> None:
        return None

    async def get_all_skill_toggles(self, user_id: str) -> dict[str, bool]:
        return {}

    async def get_api_keys_status(self) -> dict[str, bool]:
        return {}

    async def get_allowed_paths(self, user_id: str) -> list[str]:
        return []


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value
    return _inner


@pytest.mark.asyncio
async def test_get_skills_marks_workspace_agent_skills(monkeypatch, tmp_path: Path):
    db = _DummyDB()
    skill_dir = tmp_path / "skills" / "my-agent"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: My Agent\n"
        "description: custom agent skill\n"
        "is_agent: true\n"
        "---\n"
        "You are a specialist agent.\n",
        encoding="utf-8",
    )
    resolved = ResolvedSkill(
        name="my-agent",
        description="custom agent skill",
        file_path=skill_md,
        base_dir=skill_dir,
        source="workspace",
    )

    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    monkeypatch.setattr("app.workspace.discover_workspace_skills", lambda: [resolved])
    monkeypatch.setattr(settings_router, "_ollama_reachable", _async_return(False))
    monkeypatch.setattr(settings_router, "_spotify_configured", _async_return(False))
    monkeypatch.setattr(settings_router, "get_effective_exec_bins", _async_return(set()))
    monkeypatch.setattr(settings_router, "resolve_executable", lambda name: None)

    out = await settings_router.get_skills(user_id="default")
    row = next(s for s in out["skills"] if s["id"] == "my-agent")
    assert row["is_agent"] is True
