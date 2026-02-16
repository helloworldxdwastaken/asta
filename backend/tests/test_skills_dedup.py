from pathlib import Path

from app.routers import settings as settings_router
from app.skills import registry as skill_registry
from app.workspace import ResolvedSkill


def _ws_skill(name: str, folder: str = "skill") -> ResolvedSkill:
    base = Path(f"/tmp/{folder}")
    return ResolvedSkill(
        name=name,
        description=f"{name} skill",
        file_path=base / "SKILL.md",
        base_dir=base,
        source="workspace",
    )


def test_settings_skill_catalog_dedupes_colliding_ids(monkeypatch):
    monkeypatch.setattr(
        settings_router,
        "SKILLS",
        [
            {"id": "weather", "name": "Weather", "description": "builtin weather"},
            {"id": "files", "name": "Files", "description": "builtin files"},
        ],
    )
    monkeypatch.setattr(
        "app.workspace.discover_workspace_skills",
        lambda: [
            _ws_skill("weather", "ws-weather"),
            _ws_skill("notes", "ws-notes"),
            _ws_skill("WEATHER", "ws-weather-2"),
        ],
    )

    out = settings_router._get_all_skill_defs()
    ids = [str(s.get("id")) for s in out]

    assert ids == ["weather", "files", "notes"]


def test_registry_dedupes_builtin_and_workspace_collisions(monkeypatch):
    class _DummySkill:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(
        skill_registry,
        "_BUILTIN_SKILLS",
        [_DummySkill("weather"), _DummySkill("weather"), _DummySkill("time")],
    )
    monkeypatch.setattr(
        skill_registry,
        "discover_workspace_skills_runtime",
        lambda: [
            _ws_skill("time", "ws-time"),
            _ws_skill("notes", "ws-notes"),
        ],
    )

    out = skill_registry.get_all_skills()
    names = [str(getattr(s, "name", "")) for s in out]

    assert names == ["weather", "time", "notes"]
