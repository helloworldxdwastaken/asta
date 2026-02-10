"""Local file management (allowed paths only)."""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.config import get_settings

router = APIRouter()


def _allowed_paths() -> list[Path]:
    s = get_settings()
    if not s.asta_allowed_paths:
        return []
    return [Path(p.strip()).resolve() for p in s.asta_allowed_paths.split(",") if p.strip()]


def _ensure_allowed(absolute: Path) -> None:
    allowed = _allowed_paths()
    if not allowed:
        raise HTTPException(403, "No allowed paths configured (ASTA_ALLOWED_PATHS)")
    for base in allowed:
        try:
            absolute.resolve().relative_to(base)
            return
        except ValueError:
            continue
    raise HTTPException(403, "Path not in allowed list")


@router.get("/files/list")
async def list_files(directory: str = ""):
    """List files in an allowed directory."""
    allowed = _allowed_paths()
    if not allowed:
        return {"entries": [], "roots": []}
    if directory:
        p = Path(directory).resolve()
        _ensure_allowed(p)
        if not p.is_dir():
            raise HTTPException(404, "Not a directory")
        root = str(p)
        entries = []
        for c in p.iterdir():
            try:
                stat = c.stat()
                entries.append({
                    "name": c.name,
                    "path": str(c),
                    "dir": c.is_dir(),
                    "size": stat.st_size if c.is_file() else None,
                })
            except (OSError, PermissionError):
                continue
        return {"root": root, "entries": sorted(entries, key=lambda x: (not x["dir"], x["name"].lower()))}
    return {"roots": [str(a) for a in allowed], "entries": []}


@router.get("/files/read")
async def read_file(path: str):
    """Read file content (text). Path must be under allowed."""
    p = Path(path).resolve()
    _ensure_allowed(p)
    if not p.is_file():
        raise HTTPException(404, "Not a file")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(500, str(e))
