"""OpenClaw-style workspace: context files (AGENTS.md, USER.md, etc.) and skills from SKILL.md."""
from __future__ import annotations
import json
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
    # Optional from SKILL.md (install instructions, required binaries for exec)
    install_cmd: str | None = None  # e.g. "brew tap antoniorodr/memo && brew install antoniorodr/memo/memo"
    install_label: str | None = None  # e.g. "Install memo via Homebrew"
    required_bins: tuple[str, ...] = ()  # e.g. ("memo",) — must be in exec allowlist


def get_workspace_dir() -> Path | None:
    """Return the workspace root directory, or None if not configured."""
    return get_settings().workspace_path


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Return (frontmatter_text, body). If no valid frontmatter, frontmatter_text is empty."""
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", content, re.DOTALL)
    if not m:
        return "", content
    return m.group(1), m.group(2)


def _read_frontmatter(content: str) -> tuple[dict, str, str]:
    """Parse basic top-level frontmatter fields. Returns (attrs, body, frontmatter_text)."""
    fm, body = _split_frontmatter(content)
    attrs: dict = {}
    if not fm:
        return attrs, body, fm
    for key in ("name", "description", "homepage", "label"):
        m = re.search(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", fm)
        if m:
            attrs[key] = m.group(1).strip().strip("'\"").strip()
    return attrs, body, fm


def _extract_metadata_namespace(frontmatter_text: str) -> dict:
    """Parse metadata map from frontmatter; supports JSON-inline metadata and YAML-ish blocks."""
    fm = frontmatter_text or ""
    if not fm:
        return {}
    # Inline JSON form: metadata: {"openclaw": {...}} or {"clawdbot": {...}}
    m = re.search(r"(?im)^\s*metadata\s*:\s*(\{.*\})\s*$", fm)
    if m:
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                if isinstance(data.get("openclaw"), dict):
                    return data.get("openclaw") or {}
                if isinstance(data.get("clawdbot"), dict):
                    return data.get("clawdbot") or {}
                return data
        except Exception:
            pass

    # YAML-ish block form under metadata: / openclaw: or clawdbot:
    m_block = re.search(r"(?ims)^\s*metadata\s*:\s*(.+)$", fm)
    if not m_block:
        return {}
    meta_block = m_block.group(1)
    ns_m = re.search(r"(?ims)^\s*(openclaw|clawdbot)\s*:\s*(.+)$", meta_block)
    if ns_m:
        # keep raw block for regex extraction below
        return {"__raw_block__": ns_m.group(2)}
    return {"__raw_block__": meta_block}


def _extract_bins_from_frontmatter(frontmatter_text: str) -> tuple[str, ...]:
    """Strictly extract required bins from frontmatter metadata only."""
    ns = _extract_metadata_namespace(frontmatter_text)
    bins: list[str] = []
    # JSON metadata case
    if isinstance(ns.get("requires"), dict):
        for b in (ns.get("requires", {}).get("bins") or []):
            if isinstance(b, str) and b.strip():
                bins.append(b.strip().lower())
    if isinstance(ns.get("install"), list):
        for item in ns.get("install", []):
            if isinstance(item, dict):
                for b in (item.get("bins") or []):
                    if isinstance(b, str) and b.strip():
                        bins.append(b.strip().lower())
    # YAML-ish fallback case
    raw_block = ns.get("__raw_block__")
    if isinstance(raw_block, str):
        for m in re.finditer(r"bins:\s*\[(.*?)\]", raw_block):
            inner = m.group(1)
            for part in re.findall(r"[\"']([^\"']+)[\"']", inner):
                if part.strip():
                    bins.append(part.strip().lower())
    return tuple(dict.fromkeys(bins))


def _skill_install_from_frontmatter(
    frontmatter_text: str, skill_id: str = ""
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Extract install_cmd, install_label, required_bins from frontmatter only."""
    install_cmd: str | None = None
    install_label: str | None = None
    required_bins = _extract_bins_from_frontmatter(frontmatter_text)

    ns = _extract_metadata_namespace(frontmatter_text)
    if isinstance(ns.get("install"), list):
        install_items = [i for i in ns.get("install", []) if isinstance(i, dict)]
        if install_items:
            first = install_items[0]
            label = first.get("label")
            if isinstance(label, str) and label.strip():
                install_label = label.strip()
            formula = first.get("formula")
            if isinstance(formula, str) and formula.strip():
                formula = formula.strip()
                if formula.count("/") >= 2:
                    tap = "/".join(formula.split("/")[:-1])
                    install_cmd = f"brew tap {tap} && brew install {formula}"
                else:
                    install_cmd = f"brew install {formula}"
            module = first.get("module")
            if not install_cmd and isinstance(module, str) and module.strip():
                install_cmd = f"go install {module.strip()}"

    # YAML-ish fallback for label in frontmatter only
    if not install_label:
        m = re.search(r"(?im)^\s*label:\s*(.+?)\s*$", frontmatter_text)
        if m:
            install_label = m.group(1).strip().strip("'\"").strip()
    if not install_cmd:
        m = re.search(r'(?im)^\s*formula:\s*"?([^",\n]+)', frontmatter_text)
        if m:
            formula = m.group(1).strip()
            if formula:
                if formula.count("/") >= 2:
                    tap = "/".join(formula.split("/")[:-1])
                    install_cmd = f"brew tap {tap} && brew install {formula}"
                else:
                    install_cmd = f"brew install {formula}"
    if not install_cmd:
        m = re.search(r'(?im)^\s*module:\s*"?([^",\n]+)', frontmatter_text)
        if m:
            module = m.group(1).strip()
            if module:
                install_cmd = f"go install {module}"

    # Backward-compatible defaults
    if not install_cmd and skill_id == "apple-notes":
        install_cmd = "brew tap antoniorodr/memo && brew install antoniorodr/memo/memo"
    if not install_cmd and skill_id == "things-mac":
        install_cmd = "GOBIN=/opt/homebrew/bin go install github.com/ossianhempel/things3-cli/cmd/things@latest"
    if not install_label and skill_id == "things-mac":
        install_label = "Install things3-cli (go)"
    if not install_label and skill_id == "apple-notes":
        install_label = "Install memo via Homebrew"
    return install_cmd, install_label or None, required_bins


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
            attrs, _, fm_text = _read_frontmatter(raw)
            name = (attrs.get("name") or path.name).strip()
            desc = (attrs.get("description") or "Custom skill.").strip()
            # Normalize id: lowercase, no spaces
            skill_id = re.sub(r"[^a-z0-9_-]", "", name.lower()) or path.name
            install_cmd, install_label, required_bins = _skill_install_from_frontmatter(fm_text, skill_id)
            out.append(ResolvedSkill(
                name=skill_id,
                description=desc,
                file_path=skill_md,
                base_dir=path,
                source="workspace",
                install_cmd=install_cmd,
                install_label=install_label,
                required_bins=required_bins,
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
            loc = m.group(1).strip().strip("_*-").strip()
            if loc and loc.lower() not in ("(optional)", "optional", ""):
                return loc
        if ":" in line:
            _, _, v = line.partition(":")
            v = v.strip().strip("_*-").strip()
            if v and v.lower() not in ("(optional)", "optional"):
                return v
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
