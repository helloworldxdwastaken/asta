"""Agent-scoped local knowledge retrieval for workspace-driven named agents.

This module provides a lightweight, file-based retrieval path so each agent can
have its own curated corpus under:

    workspace/agent-knowledge/<agent-id>/
      - sources/
      - references/
      - notes/

The retrieval is intentionally simple (lexical overlap over chunked text) so it
works even when embedding providers are unavailable.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.workspace import get_workspace_dir

AGENT_KNOWLEDGE_DIR = "agent-knowledge"
AGENT_KNOWLEDGE_SUBDIRS = ("sources", "references", "notes")

_ALLOWED_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".html",
    ".htm",
}
_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_MAX_FILE_BYTES = 300_000
_MAX_FILES = 80
_MAX_SNIPPETS = 6
_MAX_SNIPPET_CHARS = 900


def _safe_agent_id(agent_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", (agent_id or "").strip().lower())
    return cleaned.strip("-")[:80] or "agent"


def _workspace_knowledge_root() -> Path | None:
    root = get_workspace_dir()
    if not root:
        return None
    return root / AGENT_KNOWLEDGE_DIR


def _ensure_root_readme(root: Path) -> None:
    readme = root / "README.md"
    if readme.exists():
        return
    readme.write_text(
        "\n".join(
            [
                "# Agent Knowledge",
                "",
                "Put per-agent documents here. Asta retrieves relevant snippets when you route",
                "a message to an agent with `@Agent Name: ...`.",
                "",
                "Folder layout:",
                "",
                "- `<agent-id>/sources/` — raw research, copied notes, scraped docs",
                "- `<agent-id>/references/` — stable references, frameworks, playbooks",
                "- `<agent-id>/notes/` — short operator notes and assumptions",
                "",
                "Tips:",
                "",
                "- Prefer Markdown/text files for best retrieval quality.",
                "- Keep files focused by topic instead of one giant dump.",
                "- Include dates for time-sensitive content (pricing, product changes).",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def ensure_agent_knowledge_layout(agent_id: str) -> Path | None:
    """Create workspace/agent-knowledge/<agent-id> and expected subfolders."""
    root = _workspace_knowledge_root()
    if not root:
        return None
    root.mkdir(parents=True, exist_ok=True)
    _ensure_root_readme(root)
    aid = _safe_agent_id(agent_id)
    agent_dir = root / aid
    agent_dir.mkdir(parents=True, exist_ok=True)
    for name in AGENT_KNOWLEDGE_SUBDIRS:
        (agent_dir / name).mkdir(parents=True, exist_ok=True)
    return agent_dir


def get_agent_knowledge_path(agent_id: str) -> Path | None:
    """Return the knowledge path for an agent (and scaffold if missing)."""
    return ensure_agent_knowledge_layout(agent_id)


def _iter_agent_docs(agent_dir: Path) -> list[Path]:
    files: list[Path] = []
    for sub in AGENT_KNOWLEDGE_SUBDIRS:
        base = agent_dir / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except Exception:
                continue
            files.append(path)
            if len(files) >= _MAX_FILES:
                return files
    return files


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _chunk_lines(text: str, *, window: int = 10, step: int = 6) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    if not lines:
        return []
    out: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        window_lines = lines[i : i + window]
        if not window_lines:
            break
        chunk = "\n".join(window_lines).strip()
        if chunk:
            start = i + 1
            end = i + len(window_lines)
            out.append((start, end, chunk))
        i += step
    return out


def retrieve_agent_knowledge_snippets(
    *,
    agent_id: str,
    query: str,
    max_snippets: int = _MAX_SNIPPETS,
) -> list[dict]:
    """Return ranked snippets from local agent docs for the given query."""
    agent_dir = ensure_agent_knowledge_layout(agent_id)
    if not agent_dir:
        return []

    query = (query or "").strip()
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    candidates: list[tuple[float, dict]] = []
    for path in _iter_agent_docs(agent_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        text = text.strip()
        if not text:
            continue

        for line_start, line_end, chunk in _chunk_lines(text):
            chunk_tokens = _tokenize(chunk)
            if not chunk_tokens:
                continue
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue

            # Lexical overlap score + exact phrase boost.
            score = float(len(overlap)) / float(max(1, len(query_tokens)))
            if query.lower() in chunk.lower():
                score += 0.75

            rel = path.relative_to(agent_dir)
            snippet = chunk[:_MAX_SNIPPET_CHARS]
            candidates.append(
                (
                    score,
                    {
                        "source": str(rel),
                        "line_start": line_start,
                        "line_end": line_end,
                        "snippet": snippet,
                        "score": round(score, 4),
                    },
                )
            )

    if not candidates:
        return []

    # Keep highest-scoring unique snippets.
    candidates.sort(key=lambda item: item[0], reverse=True)
    out: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for _, payload in candidates:
        key = (
            str(payload.get("source") or ""),
            int(payload.get("line_start") or 0),
            int(payload.get("line_end") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(payload)
        if len(out) >= max(1, int(max_snippets)):
            break
    return out
