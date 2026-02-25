"""Agents API — create, list, update, delete named agents backed by workspace/skills/<name>/SKILL.md."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent_knowledge import ensure_agent_knowledge_layout, get_agent_knowledge_path
from app.config import get_settings
from app.db import get_db

router = APIRouter(prefix="/api/agents", tags=["agents"])

AGENT_FLAG = "is_agent: true"  # marker line in frontmatter to identify agent skills
_AGENT_MENTION_RE = re.compile(r"^\s*@([^:\n]{1,120})\s*:\s*(.*)$", re.DOTALL)


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

    def _fm_list(key: str) -> list[str] | None:
        r = re.search(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", fm)
        if not r:
            return None
        raw = r.group(1).strip()
        if not raw:
            return []
        values: list[str] = []
        # Prefer JSON list syntax: skills: ["time","weather"]
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, list):
                values = [str(v).strip().lower() for v in decoded if str(v).strip()]
            elif isinstance(decoded, str):
                values = [decoded.strip().lower()] if decoded.strip() else []
        except Exception:
            # Fallback: comma-separated or bracketed CSV-like value.
            cleaned = raw
            if cleaned.startswith("[") and cleaned.endswith("]"):
                cleaned = cleaned[1:-1]
            values = [
                part.strip().strip("\"'").lower()
                for part in cleaned.split(",")
                if part.strip().strip("\"'")
            ]
        # Keep stable order, dedup, and normalize ids.
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            sid = re.sub(r"[^a-z0-9_-]", "", item)
            if not sid or sid in seen:
                continue
            seen.add(sid)
            normalized.append(sid)
        return normalized

    return {
        "id": slug,
        "name": _fm("name") or slug,
        "description": _fm("description"),
        "emoji": _fm("emoji") or "🤖",
        "model": _fm("model"),
        "thinking": _fm("thinking"),
        "skills": _fm_list("skills"),
        "system_prompt": body.strip(),
    }


async def resolve_agent_mention_in_text(text: str, user_id: str = "default") -> tuple[dict | None, str]:
    """Parse @Agent Name: message prefixes and resolve to an enabled named agent."""
    raw = text or ""
    m = _AGENT_MENTION_RE.match(raw)
    if not m:
        return None, raw
    mention = (m.group(1) or "").strip()
    remainder = (m.group(2) or "").strip()
    if not mention:
        return None, raw
    mention_norm = mention.lower()
    mention_slug = _slugify(mention)
    db = get_db()
    await db.connect()
    for agent in _list_agents():
        aid = str(agent.get("id") or "").strip().lower()
        name = str(agent.get("name") or "").strip().lower()
        if mention_norm in {aid, name} or mention_slug == aid:
            # Respect marketplace add/remove state: disabled agents should not be routable.
            if aid and not await db.get_skill_enabled(user_id, aid):
                return None, raw
            return agent, remainder or raw
    return None, raw


def _normalize_skill_ids(skills: list[str] | None) -> list[str] | None:
    if skills is None:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for raw in skills:
        sid = re.sub(r"[^a-z0-9_-]", "", str(raw).strip().lower())
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def _write_agent(
    slug: str,
    name: str,
    description: str,
    emoji: str,
    model: str,
    thinking: str,
    system_prompt: str,
    skills: list[str] | None = None,
) -> None:
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
    normalized_skills = _normalize_skill_ids(skills)
    if normalized_skills is not None:
        fm_lines.append(f"skills: {json.dumps(normalized_skills, ensure_ascii=True)}")
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


def _agent_matches_query(agent: dict, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    hay = " ".join(
        [
            str(agent.get("id") or ""),
            str(agent.get("name") or ""),
            str(agent.get("description") or ""),
        ]
    ).lower()
    return q in hay


# ── Models ────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: str = ""
    emoji: str = "🤖"
    model: str = ""
    thinking: str = ""
    skills: list[str] | None = None
    system_prompt: str = ""


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    emoji: str | None = None
    model: str | None = None
    thinking: str | None = None
    skills: list[str] | None = None
    system_prompt: str | None = None


class AgentEnabledIn(BaseModel):
    enabled: bool


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_agents(
    user_id: str = "default",
    q: str | None = None,
    active_only: bool = False,
    inactive_only: bool = False,
):
    """List named agents with search and active/inactive filtering."""
    db = get_db()
    await db.connect()
    toggles = await db.get_all_skill_toggles(user_id)

    out: list[dict] = []
    for agent in _list_agents():
        aid = str(agent.get("id") or "")
        enabled = bool(toggles.get(aid, True))
        if active_only and not enabled:
            continue
        if inactive_only and enabled:
            continue
        if not _agent_matches_query(agent, q or ""):
            continue
        ensure_agent_knowledge_layout(aid)
        payload = dict(agent)
        payload["enabled"] = enabled
        payload["knowledge_path"] = str(get_agent_knowledge_path(aid) or "")
        out.append(payload)
    return {"agents": out}


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
        skills=_normalize_skill_ids(body.skills),
        system_prompt=body.system_prompt.strip(),
    )
    ensure_agent_knowledge_layout(slug)
    created = _read_agent(slug)
    if not created:
        raise HTTPException(status_code=500, detail="Agent created but could not be loaded")
    created["enabled"] = True
    created["knowledge_path"] = str(get_agent_knowledge_path(slug) or "")
    return {"agent": created}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get a single agent by id (slug)."""
    a = _read_agent(agent_id)
    if not a:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    db = get_db()
    await db.connect()
    a["enabled"] = await db.get_skill_enabled("default", agent_id)
    ensure_agent_knowledge_layout(agent_id)
    a["knowledge_path"] = str(get_agent_knowledge_path(agent_id) or "")
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
    skills = (_normalize_skill_ids(body.skills) if body.skills is not None else existing.get("skills"))
    system_prompt = (body.system_prompt.strip() if body.system_prompt is not None else existing["system_prompt"])

    _write_agent(agent_id, name, description, emoji, model, thinking, system_prompt, skills=skills)
    updated = _read_agent(agent_id)
    if not updated:
        raise HTTPException(status_code=500, detail=f"Agent '{agent_id}' could not be reloaded")
    db = get_db()
    await db.connect()
    updated["enabled"] = await db.get_skill_enabled("default", agent_id)
    ensure_agent_knowledge_layout(agent_id)
    updated["knowledge_path"] = str(get_agent_knowledge_path(agent_id) or "")
    return {"agent": updated}


@router.put("/{agent_id}/enabled")
async def set_agent_enabled(agent_id: str, body: AgentEnabledIn, user_id: str = "default"):
    """Toggle whether an agent is active (marketplace add/remove behavior)."""
    existing = _read_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    db = get_db()
    await db.connect()
    await db.set_skill_enabled(user_id, agent_id, bool(body.enabled))
    existing["enabled"] = bool(body.enabled)
    ensure_agent_knowledge_layout(agent_id)
    existing["knowledge_path"] = str(get_agent_knowledge_path(agent_id) or "")
    return {"agent": existing}


@router.post("/{agent_id}/knowledge/scaffold")
async def scaffold_agent_knowledge(agent_id: str):
    """Ensure local knowledge folders exist for the specified agent."""
    existing = _read_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    path = ensure_agent_knowledge_layout(agent_id)
    return {"ok": bool(path), "agent_id": agent_id, "knowledge_path": str(path or "")}


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
