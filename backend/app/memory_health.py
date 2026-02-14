"""Memory/RAG health checks for diagnostics (OpenClaw doctor-style signal)."""
from __future__ import annotations

import time
from pathlib import Path

from app.config import get_settings
from app.rag.service import check_rag_status

_CACHE_TTL_SECONDS = 30
_memory_health_cache: dict[str, object] = {"ts": 0.0, "value": None}


def _count_workspace_memory_files(root: Path | None) -> tuple[int, bool, bool]:
    if not root:
        return 0, False, False
    try:
        user_md = (root / "USER.md").is_file()
        memory_md = (root / "MEMORY.md").is_file()
        mem_dir = root / "memory"
        file_count = 0
        if mem_dir.is_dir():
            # Keep this bounded for large workspaces.
            for _ in mem_dir.rglob("*.md"):
                file_count += 1
                if file_count >= 2000:
                    break
        return file_count, user_md, memory_md
    except Exception:
        return 0, False, False


async def get_memory_health(*, force: bool = False) -> dict:
    """Return actionable health status for memory search and RAG."""
    now = time.time()
    cached = _memory_health_cache.get("value")
    ts = float(_memory_health_cache.get("ts") or 0.0)
    if (not force) and isinstance(cached, dict) and (now - ts) < _CACHE_TTL_SECONDS:
        return dict(cached)

    settings = get_settings()
    rag = await check_rag_status()
    workspace = settings.workspace_path
    memory_files, has_user_md, has_memory_md = _count_workspace_memory_files(workspace)

    findings: list[dict] = []
    status = "ok"

    if not rag.get("ok"):
        status = "warn"
        findings.append(
            {
                "id": "memory.rag.unavailable",
                "severity": "warn",
                "title": "RAG backend is not ready",
                "detail": rag.get("detail") or rag.get("message") or "Embedding backend is unavailable.",
                "remediation": "Start Ollama and pull nomic-embed-text, then re-check Learning status.",
            }
        )

    if not has_user_md and not has_memory_md and memory_files == 0:
        findings.append(
            {
                "id": "memory.workspace.empty",
                "severity": "info",
                "title": "Workspace memory files are empty",
                "detail": "No USER.md / MEMORY.md / memory/*.md sources found.",
                "remediation": "Add USER.md or memory notes so memory_search has local context to retrieve.",
            }
        )

    out = {
        "status": status,
        "search_mode": settings.memory_search_mode,
        "workspace": {
            "path": str(workspace) if workspace else None,
            "has_user_md": has_user_md,
            "has_memory_md": has_memory_md,
            "memory_file_count": memory_files,
        },
        "rag": {
            "ok": bool(rag.get("ok")),
            "provider": rag.get("provider"),
            "detail": rag.get("detail"),
            "ollama_url": rag.get("ollama_url"),
            "ollama_reason": rag.get("ollama_reason"),
        },
        "findings": findings,
    }
    _memory_health_cache["ts"] = now
    _memory_health_cache["value"] = dict(out)
    return out
