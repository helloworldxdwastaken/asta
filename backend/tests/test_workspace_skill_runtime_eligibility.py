from pathlib import Path

from app import workspace


def _write_skill(base: Path, folder: str, frontmatter: str) -> None:
    skill_dir = base / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(frontmatter + "\n\n# Skill\n", encoding="utf-8")


def test_runtime_eligibility_filters_darwin_skill_on_linux(monkeypatch, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "apple-notes",
        """---
name: apple-notes
description: Apple Notes via memo
metadata:
  openclaw:
    os: ["darwin"]
    requires: { bins: ["memo"] }
---""",
    )
    _write_skill(
        skills_dir,
        "notes",
        """---
name: notes
description: Workspace markdown notes
metadata:
  openclaw:
    os: ["darwin", "linux"]
---""",
    )

    monkeypatch.setattr(workspace, "get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(workspace, "get_host_os_tag", lambda: "linux")
    monkeypatch.setattr(workspace, "_resolve_bin_for_eligibility", lambda _name: "/usr/bin/memo")

    runtime = workspace.discover_workspace_skills_runtime()
    names = {s.name for s in runtime}
    assert names == {"notes"}


def test_runtime_eligibility_requires_bins_on_supported_os(monkeypatch, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "apple-notes",
        """---
name: apple-notes
description: Apple Notes via memo
metadata:
  openclaw:
    os: ["darwin"]
    requires: { bins: ["memo"] }
---""",
    )

    monkeypatch.setattr(workspace, "get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(workspace, "get_host_os_tag", lambda: "darwin")
    monkeypatch.setattr(workspace, "_resolve_bin_for_eligibility", lambda _name: None)

    runtime = workspace.discover_workspace_skills_runtime()
    assert runtime == []

    monkeypatch.setattr(workspace, "_resolve_bin_for_eligibility", lambda _name: "/opt/homebrew/bin/memo")
    runtime2 = workspace.discover_workspace_skills_runtime()
    assert [s.name for s in runtime2] == ["apple-notes"]
