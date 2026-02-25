from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.agent_knowledge as agent_knowledge
import app.routers.agents as agents_router
from app.routers.agents import AgentEnabledIn


@dataclass
class _DummyDB:
    toggles: dict[str, bool] = field(default_factory=dict)

    async def connect(self) -> None:
        return None

    async def get_all_skill_toggles(self, user_id: str) -> dict[str, bool]:
        return dict(self.toggles)

    async def get_skill_enabled(self, user_id: str, skill_id: str) -> bool:
        return bool(self.toggles.get(skill_id, True))

    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool) -> None:
        self.toggles[skill_id] = bool(enabled)


def _write_agent_skill(
    workspace_root: Path,
    *,
    slug: str,
    name: str,
    description: str = "",
    skills_line: str | None = None,
) -> None:
    skill_dir = workspace_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "emoji: 🤖",
                *( [skills_line] if skills_line else [] ),
                "is_agent: true",
                "---",
                "",
                "You are a specialist agent.",
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_agents_list_filters_and_toggle_roundtrip(monkeypatch, tmp_path: Path):
    db = _DummyDB(toggles={"research-analyst": False})
    monkeypatch.setattr(agents_router, "get_db", lambda: db)
    monkeypatch.setattr(
        agents_router,
        "get_settings",
        lambda: SimpleNamespace(workspace_path=tmp_path),
    )
    monkeypatch.setattr(agent_knowledge, "get_workspace_dir", lambda: tmp_path)

    _write_agent_skill(
        tmp_path,
        slug="research-analyst",
        name="Research Analyst",
        description="Competitive intelligence and market landscape analysis.",
    )

    listed = await agents_router.list_agents(user_id="default")
    assert len(listed["agents"]) == 1
    row = listed["agents"][0]
    assert row["id"] == "research-analyst"
    assert row["enabled"] is False
    assert Path(row["knowledge_path"]) == tmp_path / "agent-knowledge" / "research-analyst"

    active_only = await agents_router.list_agents(user_id="default", active_only=True)
    assert active_only["agents"] == []

    inactive_only = await agents_router.list_agents(user_id="default", inactive_only=True)
    assert [a["id"] for a in inactive_only["agents"]] == ["research-analyst"]

    search_hit = await agents_router.list_agents(user_id="default", q="landscape")
    assert [a["id"] for a in search_hit["agents"]] == ["research-analyst"]

    toggled = await agents_router.set_agent_enabled(
        "research-analyst",
        AgentEnabledIn(enabled=True),
        user_id="default",
    )
    assert toggled["agent"]["enabled"] is True
    assert db.toggles["research-analyst"] is True


@pytest.mark.asyncio
async def test_resolve_agent_mention_respects_enabled_state(monkeypatch, tmp_path: Path):
    db = _DummyDB(toggles={"copywriter": False})
    monkeypatch.setattr(agents_router, "get_db", lambda: db)
    monkeypatch.setattr(
        agents_router,
        "get_settings",
        lambda: SimpleNamespace(workspace_path=tmp_path),
    )

    _write_agent_skill(
        tmp_path,
        slug="copywriter",
        name="Copywriter",
        description="Writes conversion-focused product messaging.",
    )

    selected, cleaned = await agents_router.resolve_agent_mention_in_text(
        "@Copywriter: Draft a landing page headline",
        user_id="default",
    )
    assert selected is None
    assert cleaned.startswith("@Copywriter:")

    db.toggles["copywriter"] = True
    selected, cleaned = await agents_router.resolve_agent_mention_in_text(
        "@Copywriter: Draft a landing page headline",
        user_id="default",
    )
    assert selected is not None
    assert selected["id"] == "copywriter"
    assert cleaned == "Draft a landing page headline"


@pytest.mark.asyncio
async def test_agent_skills_roundtrip_create_update(monkeypatch, tmp_path: Path):
    db = _DummyDB()
    monkeypatch.setattr(agents_router, "get_db", lambda: db)
    monkeypatch.setattr(
        agents_router,
        "get_settings",
        lambda: SimpleNamespace(workspace_path=tmp_path),
    )
    monkeypatch.setattr(agent_knowledge, "get_workspace_dir", lambda: tmp_path)

    created = await agents_router.create_agent(
        agents_router.AgentCreate(
            name="Skill Scoped",
            description="Agent with explicit skills",
            emoji="🤖",
            model="",
            thinking="",
            skills=["time", "weather", "time"],
            system_prompt="You are scoped.",
        )
    )
    agent = created["agent"]
    assert agent["id"] == "skill-scoped"
    assert agent["skills"] == ["time", "weather"]

    fetched = await agents_router.get_agent("skill-scoped")
    assert fetched["agent"]["skills"] == ["time", "weather"]

    updated = await agents_router.update_agent(
        "skill-scoped",
        agents_router.AgentUpdate(skills=[]),
    )
    assert updated["agent"]["skills"] == []
