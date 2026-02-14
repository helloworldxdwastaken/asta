from pathlib import Path

import pytest

from app.routers import settings as settings_router
from app.workspace import ResolvedSkill


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


def _apple_notes_skill(tmp_path: Path) -> ResolvedSkill:
    skill_md = tmp_path / "apple-notes" / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text("# Apple Notes skill\n", encoding="utf-8")
    return ResolvedSkill(
        name="apple-notes",
        description="Apple Notes via memo",
        file_path=skill_md,
        base_dir=skill_md.parent,
        source="workspace",
        install_cmd="brew tap antoniorodr/memo && brew install antoniorodr/memo/memo",
        install_label="Install memo via Homebrew",
        required_bins=("memo",),
    )


class FakeSettingsDb:
    def __init__(self) -> None:
        self.toggles: dict[str, bool] = {}
        self.system_config: dict[str, str] = {}

    async def connect(self):
        return None

    async def get_all_skill_toggles(self, user_id: str):
        return dict(self.toggles)

    async def get_api_keys_status(self):
        return {}

    async def get_allowed_paths(self, user_id: str):
        return []

    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool):
        self.toggles[skill_id] = enabled

    async def get_skill_enabled(self, user_id: str, skill_id: str):
        return self.toggles.get(skill_id, True)

    async def get_system_config(self, key: str):
        return self.system_config.get(key, "")

    async def set_system_config(self, key: str, value: str):
        self.system_config[key] = value


@pytest.mark.asyncio
async def test_apple_notes_requires_bin_on_path_and_in_exec_allowlist(monkeypatch, tmp_path):
    db = FakeSettingsDb()
    skill = _apple_notes_skill(tmp_path)

    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    monkeypatch.setattr("app.workspace.discover_workspace_skills", lambda: [skill])
    monkeypatch.setattr(settings_router, "_ollama_reachable", _async_return(False))
    monkeypatch.setattr(settings_router, "_spotify_configured", _async_return(False))
    monkeypatch.setattr(settings_router, "resolve_executable", lambda name: "/opt/homebrew/bin/memo" if name == "memo" else None)

    monkeypatch.setattr(settings_router, "get_effective_exec_bins", _async_return(set()))
    out = await settings_router.get_skills(user_id="default")
    apple = next(s for s in out["skills"] if s["id"] == "apple-notes")
    assert apple["available"] is False
    assert apple["action_hint"] == "Install & enable exec"

    monkeypatch.setattr(settings_router, "get_effective_exec_bins", _async_return({"memo"}))
    out2 = await settings_router.get_skills(user_id="default")
    apple2 = next(s for s in out2["skills"] if s["id"] == "apple-notes")
    assert apple2["available"] is True
    assert apple2["action_hint"] is None


@pytest.mark.asyncio
async def test_set_skill_toggle_syncs_workspace_bins_into_exec_allowlist(monkeypatch, tmp_path):
    db = FakeSettingsDb()
    db.system_config["exec_allowed_bins_extra"] = "curl"
    skill = _apple_notes_skill(tmp_path)

    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    monkeypatch.setattr("app.workspace.discover_workspace_skills", lambda: [skill])

    await settings_router.set_skill_toggle(
        settings_router.SkillToggleIn(skill_id="apple-notes", enabled=True),
        user_id="default",
    )
    enabled_bins = {b for b in db.system_config["exec_allowed_bins_extra"].split(",") if b}
    assert enabled_bins == {"curl", "memo"}

    await settings_router.set_skill_toggle(
        settings_router.SkillToggleIn(skill_id="apple-notes", enabled=False),
        user_id="default",
    )
    disabled_bins = {b for b in db.system_config["exec_allowed_bins_extra"].split(",") if b}
    assert disabled_bins == {"curl"}


@pytest.mark.asyncio
async def test_workspace_skill_unavailable_on_unsupported_os(monkeypatch, tmp_path):
    db = FakeSettingsDb()
    skill = _apple_notes_skill(tmp_path)

    monkeypatch.setattr(settings_router, "get_db", lambda: db)
    monkeypatch.setattr("app.workspace.discover_workspace_skills", lambda: [skill._replace(supported_os=("darwin",))])
    monkeypatch.setattr(settings_router, "_ollama_reachable", _async_return(False))
    monkeypatch.setattr(settings_router, "_spotify_configured", _async_return(False))
    monkeypatch.setattr(settings_router, "get_effective_exec_bins", _async_return({"memo"}))
    monkeypatch.setattr(settings_router, "resolve_executable", lambda name: "/opt/homebrew/bin/memo" if name == "memo" else None)
    monkeypatch.setattr("app.workspace.get_host_os_tag", lambda: "linux")

    out = await settings_router.get_skills(user_id="default")
    apple = next(s for s in out["skills"] if s["id"] == "apple-notes")
    assert apple["available"] is False
    assert "Only on darwin" in (apple["action_hint"] or "")
