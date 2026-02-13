"""Local file management (allowed paths only) + Asta knowledge + User memories. OpenClaw-style: request access when path not allowed."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_settings
from app.db import get_db

router = APIRouter()


class FileWriteIn(BaseModel):
    content: str


async def write_to_allowed_path(user_id: str, path: str, content: str) -> str:
    """Write content to an allowed path (or workspace-relative). Returns the absolute path written. Raises ValueError if not allowed."""
    allowed = await _allowed_paths(user_id)
    if not allowed:
        raise ValueError("No allowed paths")
    path_str = path.strip()
    p = Path(path_str)
    if not p.is_absolute():
        s = get_settings()
        if s.workspace_path:
            p = (s.workspace_path / path_str).resolve()
        elif allowed:
            p = (Path(allowed[0]) / path_str).resolve()
        else:
            raise ValueError("Relative path requires workspace")
    else:
        p = p.resolve()
    try:
        _ensure_allowed(p, allowed)
    except PathAccessRequest as e:
        raise ValueError(f"Path not allowed: {e.requested_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


class PathAccessRequest(Exception):
    """Raised when a path is not in the allowlist — client can show 'Grant access' and call allow-path."""
    def __init__(self, requested_path: Path) -> None:
        self.requested_path = Path(requested_path).resolve()


# Virtual roots for Asta knowledge and User memories
ASTA_KNOWLEDGE = "asta:knowledge"
USER_MEMORIES = "user:memories"


async def _allowed_paths(user_id: str = "default") -> list[Path]:
    """Env ASTA_ALLOWED_PATHS + user's DB allowlist + workspace root if set (OpenClaw-style)."""
    s = get_settings()
    out: list[Path] = []
    if s.asta_allowed_paths:
        for p in s.asta_allowed_paths.split(","):
            if p.strip():
                out.append(Path(p.strip()).resolve())
    db = get_db()
    await db.connect()
    for p in await db.get_allowed_paths(user_id):
        if p.strip():
            out.append(Path(p).resolve())
    if s.workspace_path:
        out.append(s.workspace_path)
    return list(dict.fromkeys(out))  # dedupe preserving order


def _ensure_allowed(absolute: Path, allowed: list[Path]) -> None:
    """Raise PathAccessRequest if path is not under any allowed base (so client can show Grant access)."""
    absolute = absolute.resolve()
    if not allowed:
        raise HTTPException(403, "No allowed paths configured. Add ASTA_ALLOWED_PATHS in Settings or grant access to a path.")
    for base in allowed:
        try:
            absolute.relative_to(base)
            return
        except ValueError:
            continue
    raise PathAccessRequest(absolute)


def _asta_root() -> Path:
    """Asta project root (contains backend/, docs/, README.md)."""
    return Path(__file__).resolve().parent.parent.parent.parent


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
    """List files. Virtual roots: asta:knowledge. User context = workspace/USER.md (not listed here)."""
    allowed = await _allowed_paths(user_id)

    if directory == ASTA_KNOWLEDGE:
        docs = _asta_docs()
        entries = [{"name": n, "path": p, "dir": False, "size": None} for n, p in docs]
        return {"root": ASTA_KNOWLEDGE, "entries": entries}

    if directory == USER_MEMORIES:
        from app.memories import ensure_user_md, load_user_memories
        ensure_user_md(user_id)
        content = load_user_memories(user_id)
        entries = [{"name": "User.md", "path": f"{USER_MEMORIES}/User.md", "dir": False, "size": len(content.encode("utf-8"))}]
        return {"root": USER_MEMORIES, "entries": entries}

    if not allowed:
        roots = [ASTA_KNOWLEDGE]
        return {"roots": roots, "entries": []}

    roots = [ASTA_KNOWLEDGE] + [str(a) for a in allowed]

    if directory:
        # Real path
        try:
            p = Path(directory).resolve()
            _ensure_allowed(p, allowed)
        except PathAccessRequest:
            raise HTTPException(403, "Path not in allowed list")
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
        from app.memories import ensure_user_md, load_user_memories
        ensure_user_md(user_id)
        return load_user_memories(user_id)
    raise HTTPException(404, "File not found")


@router.get("/files/read")
async def read_file(path: str, user_id: str = "default"):
    """Read file content. If path not allowed, returns 403 with code PATH_ACCESS_REQUEST so client can show 'Grant access'."""
    if path.startswith(ASTA_KNOWLEDGE) or path.startswith(USER_MEMORIES):
        content = _read_virtual(path, user_id)
        return {"path": path, "content": content}

    p = Path(path).resolve()
    allowed = await _allowed_paths(user_id)
    try:
        _ensure_allowed(p, allowed)
    except PathAccessRequest as e:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Path not in allowed list. You can grant access in Settings → Allowed paths or use the Grant access button.",
                "code": "PATH_ACCESS_REQUEST",
                "requested_path": str(e.requested_path),
            },
        )
    if not p.is_file():
        raise HTTPException(404, "Not a file")
    content = p.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


@router.put("/files/write")
async def write_file(path: str, body: FileWriteIn, user_id: str = "default"):
    """Write content. Supports: user:memories/User.md (memories) or any path under allowed/workspace (create file)."""
    if path == f"{USER_MEMORIES}/User.md" or path == "user:memories/User.md":
        from app.memories import save_user_memories
        save_user_memories(user_id, body.content)
        return {"path": path, "ok": True}

    try:
        written = await write_to_allowed_path(user_id, path, body.content)
        return {"path": written, "ok": True}
    except ValueError as e:
        raise HTTPException(403, str(e))


class AllowPathIn(BaseModel):
    path: str


@router.get("/files/allowed-paths")
async def get_allowed_paths(user_id: str = "default"):
    """List allowed path bases (env + user allowlist). For UI to show and manage."""
    paths = await _allowed_paths(user_id)
    return {"paths": [str(p) for p in paths]}


@router.post("/files/allow-path")
@router.put("/files/allow-path")
async def allow_path(body: AllowPathIn, user_id: str = "default"):
    """Add a path to the user's allowlist (OpenClaw-style: grant access when AI or user requests it). Path can be file or directory. If file, also add parent dir so listing works."""
    p = Path(body.path.strip()).resolve()
    if not p.exists():
        raise HTTPException(400, "Path does not exist")
    db = get_db()
    await db.connect()
    await db.add_allowed_path(user_id, str(p))
    if p.is_file():
        parent = p.parent
        if parent != p and str(parent) != "/":
            await db.add_allowed_path(user_id, str(parent))
    return {"path": str(p), "ok": True}
