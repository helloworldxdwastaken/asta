from __future__ import annotations

from pathlib import Path

from app.handler import _append_selected_agent_context
from app.workspace import ResolvedSkill


def _mk_resolved_skill(skill_id: str, path: Path) -> ResolvedSkill:
    return ResolvedSkill(
        name=skill_id,
        description=f"{skill_id} skill",
        file_path=path,
        base_dir=path.parent,
        source="workspace",
    )


def test_selected_agent_context_preloads_single_allowed_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / "notion"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Notion\nUse POST /v1/search with JSON body.\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.workspace.discover_workspace_skills",
        lambda: [_mk_resolved_skill("notion", skill_md)],
    )

    base = "base-context"
    extra = {
        "selected_agent": {
            "id": "notion-operator",
            "name": "Notion Operator",
            "description": "Notion specialist",
            "system_prompt": "Use Notion first.",
            "skills": ["notion"],
        }
    }

    out = _append_selected_agent_context(base, extra)
    assert "[AGENT SKILL DIRECTIVES]" in out
    assert "Preloaded allowed skill 'notion'" in out
    assert "Use POST /v1/search with JSON body." in out


def test_selected_agent_context_does_not_preload_when_multiple_allowed_skills(monkeypatch, tmp_path):
    skill_dir = tmp_path / "notion"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Notion\nDo things.\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.workspace.discover_workspace_skills",
        lambda: [_mk_resolved_skill("notion", skill_md)],
    )

    base = "base-context"
    extra = {
        "selected_agent": {
            "id": "notion-operator",
            "name": "Notion Operator",
            "skills": ["notion", "google_search"],
        }
    }

    out = _append_selected_agent_context(base, extra)
    assert "[AGENT SKILL DIRECTIVES]" not in out
