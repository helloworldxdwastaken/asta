from __future__ import annotations

from pathlib import Path

import pytest

import app.context as context_module
from app.skills.markdown_skill import MarkdownSkill
from app.workspace import ResolvedSkill


class _DummyDB:
    async def get_skill_enabled(self, user_id: str, skill_id: str) -> bool:
        return True


def _mk_markdown_skill(name: str) -> MarkdownSkill:
    return MarkdownSkill(
        ResolvedSkill(
            name=name,
            description=f"{name} description",
            file_path=Path(f"/tmp/{name}/SKILL.md"),
            base_dir=Path(f"/tmp/{name}"),
            source="workspace",
        )
    )


@pytest.mark.asyncio
async def test_available_skills_prompt_respects_agent_skill_filter(monkeypatch):
    skills = [_mk_markdown_skill("alpha"), _mk_markdown_skill("beta")]
    monkeypatch.setattr("app.skills.registry.get_all_skills", lambda: skills)
    db = _DummyDB()

    prompt = await context_module._get_available_skills_prompt(
        db,
        "default",
        skills_in_use=None,
        agent_skill_filter=["alpha"],
    )
    assert "<name>alpha</name>" in prompt
    assert "<name>beta</name>" not in prompt

    empty_prompt = await context_module._get_available_skills_prompt(
        db,
        "default",
        skills_in_use=None,
        agent_skill_filter=[],
    )
    assert empty_prompt == ""

