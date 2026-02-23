"""Agents API — create, list, update, delete named agents backed by workspace/skills/<name>/SKILL.md."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api/agents", tags=["agents"])

AGENT_FLAG = "is_agent: true"  # marker line in frontmatter to identify agent skills


def _agents_dir() -> Path | None:
    ws = get_settings().workspace_path
    if not ws:
        return None
    return ws / "skills"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-")[:40]


def _skill_path(slug: str) -> Path | None:
    base = _agents_dir()
    if not base:
        return None
    return base / slug / "SKILL.md"


def _read_agent(slug: str) -> dict | None:
    path = _skill_path(slug)
    if not path or not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    # Only treat as an agent if marker is present
    if AGENT_FLAG not in content:
        return None
    # Parse frontmatter
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)", content, re.DOTALL)
    fm, body = (m.group(1), m.group(2)) if m else ("", content)

    def _fm(key: str) -> str:
        r = re.search(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", fm)
        return r.group(1).strip().strip("\"'") if r else ""

    return {
        "id": slug,
        "name": _fm("name") or slug,
        "description": _fm("description"),
        "emoji": _fm("emoji") or "🤖",
        "model": _fm("model"),
        "thinking": _fm("thinking"),
        "system_prompt": body.strip(),
    }


def _write_agent(slug: str, name: str, description: str, emoji: str, model: str, thinking: str, system_prompt: str) -> None:
    base = _agents_dir()
    if not base:
        raise HTTPException(status_code=500, detail="Workspace path not configured")
    base.mkdir(parents=True, exist_ok=True)
    folder = base / slug
    folder.mkdir(exist_ok=True)
    path = folder / "SKILL.md"

    fm_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"emoji: {emoji}",
    ]
    if model:
        fm_lines.append(f"model: {model}")
    if thinking:
        fm_lines.append(f"thinking: {thinking}")
    fm_lines.append(AGENT_FLAG)
    fm_lines.append("---")
    fm_lines.append("")
    if system_prompt:
        fm_lines.append(system_prompt)

    path.write_text("\n".join(fm_lines) + "\n", encoding="utf-8")


def _list_agents() -> list[dict]:
    base = _agents_dir()
    if not base or not base.exists():
        return []
    agents = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        a = _read_agent(folder.name)
        if a:
            agents.append(a)
    return agents


# ── Models ────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: str = ""
    emoji: str = "🤖"
    model: str = ""
    thinking: str = ""
    system_prompt: str = ""


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    emoji: str | None = None
    model: str | None = None
    thinking: str | None = None
    system_prompt: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_agents():
    """List all named agents."""
    return {"agents": _list_agents()}


@router.post("", status_code=201)
async def create_agent(body: AgentCreate):
    """Create a new named agent."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    slug = _slugify(body.name)
    if _read_agent(slug):
        raise HTTPException(status_code=409, detail=f"Agent '{slug}' already exists")
    _write_agent(
        slug=slug,
        name=body.name.strip(),
        description=body.description.strip(),
        emoji=body.emoji.strip() or "🤖",
        model=body.model.strip(),
        thinking=body.thinking.strip(),
        system_prompt=body.system_prompt.strip(),
    )
    return {"agent": _read_agent(slug)}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get a single agent by id (slug)."""
    a = _read_agent(agent_id)
    if not a:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {"agent": a}


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate):
    """Update an existing agent's fields."""
    existing = _read_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    name = (body.name.strip() if body.name is not None else existing["name"])
    description = (body.description.strip() if body.description is not None else existing["description"])
    emoji = (body.emoji.strip() if body.emoji is not None else existing["emoji"]) or "🤖"
    model = (body.model.strip() if body.model is not None else existing["model"])
    thinking = (body.thinking.strip() if body.thinking is not None else existing["thinking"])
    system_prompt = (body.system_prompt.strip() if body.system_prompt is not None else existing["system_prompt"])

    _write_agent(agent_id, name, description, emoji, model, thinking, system_prompt)
    return {"agent": _read_agent(agent_id)}


@router.delete("/{agent_id}", status_code=200)
async def delete_agent(agent_id: str):
    """Delete an agent by id."""
    path = _skill_path(agent_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    existing = _read_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"'{agent_id}' is not an agent skill")
    import shutil
    shutil.rmtree(path.parent, ignore_errors=True)
    return {"ok": True, "deleted": agent_id}
