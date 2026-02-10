"""Local file management (allowed paths only) + Asta knowledge + User memories."""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.config import get_settings

router = APIRouter()

# Virtual roots for Asta knowledge and User memories
ASTA_KNOWLEDGE = "asta:knowledge"
USER_MEMORIES = "user:memories"


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


def _asta_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _asta_docs() -> list[tuple[str, str]]:
    """Return (name, path) for README and docs/*.md."""
    root = _asta_root()
    out: list[tuple[str, str]] = []
    readme = root / "README.md"
    if readme.is_file():
        out.append(("README.md", f"{ASTA_KNOWLEDGE}/README.md"))
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for f in sorted(docs_dir.glob("*.md")):
            out.append((f.name, f"{ASTA_KNOWLEDGE}/docs/{f.name}"))
    return out


@router.get("/files/list")
async def list_files(directory: str = "", user_id: str = "default"):
    """List files. Supports virtual roots: asta:knowledge, user:memories."""
    allowed = _allowed_paths()

    if directory == ASTA_KNOWLEDGE:
        docs = _asta_docs()
        entries = [{"name": n, "path": p, "dir": False, "size": None} for n, p in docs]
        return {"root": ASTA_KNOWLEDGE, "entries": entries}

    if directory == USER_MEMORIES:
        from app.memories import load_user_memories
        content = load_user_memories(user_id)
        entries = [{"name": "User.md", "path": f"{USER_MEMORIES}/User.md", "dir": False, "size": len(content.encode("utf-8"))}]
        return {"root": USER_MEMORIES, "entries": entries}

    if not allowed:
        roots = [ASTA_KNOWLEDGE, USER_MEMORIES]
        return {"roots": roots, "entries": []}

    roots = [ASTA_KNOWLEDGE, USER_MEMORIES] + [str(a) for a in allowed]

    if directory:
        # Real path
        try:
            p = Path(directory).resolve()
            _ensure_allowed(p)
        except HTTPException:
            raise
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

    return {"roots": roots, "entries": []}


def _read_virtual(path: str, user_id: str) -> str:
    """Read content for virtual path."""
    if path.startswith(f"{ASTA_KNOWLEDGE}/"):
        rel = path[len(ASTA_KNOWLEDGE) + 1:]
        root = _asta_root()
        if rel == "README.md":
            fp = root / "README.md"
        elif rel.startswith("docs/"):
            fp = root / rel
        else:
            fp = root / rel
        if fp.is_file():
            return fp.read_text(encoding="utf-8")
        raise HTTPException(404, "File not found")
    if path == f"{USER_MEMORIES}/User.md" or path == "user:memories/User.md":
        from app.memories import load_user_memories
        return load_user_memories(user_id) or "# About you\n\n(No memories yet. Tell Asta your name, location, or important facts.)"
    raise HTTPException(404, "File not found")


@router.get("/files/read")
async def read_file(path: str, user_id: str = "default"):
    """Read file content. Supports virtual paths (asta:knowledge/..., user:memories/User.md). Returns JSON {path, content}."""
    if path.startswith(ASTA_KNOWLEDGE) or path.startswith(USER_MEMORIES):
        content = _read_virtual(path, user_id)
        return {"path": path, "content": content}

    p = Path(path).resolve()
    _ensure_allowed(p)
    if not p.is_file():
        raise HTTPException(404, "Not a file")
    content = p.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}
