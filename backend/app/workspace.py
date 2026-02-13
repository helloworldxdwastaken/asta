"""OpenClaw-style workspace: context files (AGENTS.md, USER.md, etc.) and skills from SKILL.md."""
from __future__ import annotations
import re
from pathlib import Path
from typing import NamedTuple

from app.config import get_settings


class ResolvedSkill(NamedTuple):
    """A skill discovered from workspace/skills/<name>/SKILL.md."""
    name: str
    description: str
    file_path: Path
    base_dir: Path
    source: str  # "workspace"


def get_workspace_dir() -> Path | None:
    """Return the workspace root directory, or None if not configured."""
    return get_settings().workspace_path


def _read_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (attrs, body)."""
    attrs: dict = {}
    body = content
    if content.startswith("---"):
        end = content.index("---", 3) if "---" in content[3:] else -1
        if end != -1:
            fm = content[3:end].strip()
            body = content[end + 3:].lstrip()
            for line in fm.split("\n"):
                if ":" in line:
                    k, _, v = line.partition(":")
                    k, v = k.strip(), v.strip().strip("'\"").strip()
                    attrs[k.strip().lower()] = v
    return attrs, body


def discover_workspace_skills() -> list[ResolvedSkill]:
    """Scan workspace/skills for SKILL.md files. Return list of ResolvedSkill."""
    root = get_workspace_dir()
    if not root:
        return []
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    out: list[ResolvedSkill] = []
    for path in sorted(skills_dir.iterdir()):
        if not path.is_dir():
            continue
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            raw = skill_md.read_text(encoding="utf-8", errors="replace")
            attrs, _ = _read_frontmatter(raw)
            name = attrs.get("name") or path.name
            desc = attrs.get("description") or "Custom skill."
            # Normalize id: lowercase, no spaces
            skill_id = re.sub(r"[^a-z0-9_-]", "", name.lower()) or path.name
            out.append(ResolvedSkill(
                name=skill_id,
                description=desc,
                file_path=skill_md,
                base_dir=path,
                source="workspace",
            ))
        except Exception:
            continue
    return out


# Optional context files (OpenClaw-style). User context = workspace/USER.md only (no separate data/User.md).
WORKSPACE_CONTEXT_FILES = ("AGENTS.md", "USER.md", "SOUL.md", "TOOLS.md")


def get_location_from_workspace_user_md() -> str | None:
    """Extract location from workspace/USER.md (e.g. '**Location:** City, Country' or '- **Location:** ...'). Returns None if not set."""
    root = get_workspace_dir()
    if not root:
        return None
    user_md = root / "USER.md"
    if not user_md.is_file():
        return None
    try:
        content = user_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    for line in content.splitlines():
        line = line.strip()
        if not line or not line.lower().startswith(("- **location", "**location", "location:")):
            continue
        # Match **Location:** value or - **Location:** value
        m = re.search(r"\*\*Location\*\*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().strip("-").strip()
            if loc:
                return loc
        if ":" in line:
            _, _, v = line.partition(":")
            if v.strip():
                return v.strip()
    return None


def get_workspace_context_section() -> str | None:
    """Read AGENTS.md, USER.md, SOUL.md, TOOLS.md and return a single context block."""
    root = get_workspace_dir()
    if not root:
        return None
    parts: list[str] = []
    for filename in WORKSPACE_CONTEXT_FILES:
        path = root / filename
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    parts.append(f"--- {filename} ---\n{content}\n")
            except Exception:
                pass
    if not parts:
        return None
    return "\n".join(parts)
