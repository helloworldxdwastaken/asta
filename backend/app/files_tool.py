"""Tools for listing/reading allowed paths and requesting access (e.g. Desktop). Used when the user asks to 'check my desktop' or 'what can I delete'."""
from __future__ import annotations
import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.adaptive_paging import compute_page_chars, truncate_with_offset_hint

if TYPE_CHECKING:
    from app.db import Db

logger = logging.getLogger(__name__)


async def _allowed_paths(db: "Db | None", user_id: str) -> list[Path]:
    """Same logic as files router: env + DB allowlist + workspace."""
    s = get_settings()
    out: list[Path] = []
    if s.asta_allowed_paths:
        for p in s.asta_allowed_paths.split(","):
            if p.strip():
                out.append(Path(p.strip()).resolve())
    if db:
        try:
            await db.connect()
            for p in await db.get_allowed_paths(user_id):
                if p.strip():
                    out.append(Path(p).resolve())
        except Exception:
            pass
    if s.workspace_path:
        out.append(s.workspace_path)
    return list(dict.fromkeys(out))


def _path_is_allowed(absolute: Path, allowed: list[Path]) -> bool:
    absolute = absolute.resolve()
    if not allowed:
        return False
    for base in allowed:
        try:
            absolute.relative_to(base)
            return True
        except ValueError:
            continue
    return False


async def list_directory(path: str, user_id: str, db: "Db | None") -> str:
    """List directory contents. Path can be e.g. ~/Desktop or /Users/you/Desktop. Returns JSON-like summary or error message."""
    path = (path or "").strip()
    if not path:
        return "Error: path is required."
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return f"Error: not a directory: {p}"
    allowed = await _allowed_paths(db, user_id)
    if not _path_is_allowed(p, allowed):
        return (
            f"Path {p} is not in the allowed list. "
            "The user can add it in Settings → Files (Allowed paths), or say 'allow my Desktop' / 'allow access to my Desktop' to add it."
        )
    entries = []
    for c in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        try:
            stat = c.stat()
            kind = "dir" if c.is_dir() else "file"
            size = stat.st_size if c.is_file() else None
            entries.append({"name": c.name, "kind": kind, "size": size})
        except (OSError, PermissionError):
            continue
    return json.dumps({"path": str(p), "entries": entries[:200]}, indent=0)


async def read_file_content(
    path: str,
    user_id: str,
    db: "Db | None",
    max_chars: int | None = None,
    offset: int = 0,
    *,
    model: str | None = None,
    provider: str | None = None,
) -> str:
    """Read file content with adaptive paging. Returns content or error message.

    Args:
        max_chars: Hard cap on chars. If None, derives from model context window.
        offset:    Character offset for pagination (0 = start of file).
        model:     Model name for adaptive page cap.
        provider:  Provider name for adaptive page cap.
    """
    path = (path or "").strip()
    if not path:
        return "Error: path is required."
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return f"Error: not a file: {p}"
    allowed = await _allowed_paths(db, user_id)
    if not _path_is_allowed(p, allowed):
        return (
            f"Path {p} is not in the allowed list. "
            "The user can add it in Settings → Files, or say 'allow my Desktop' to add a folder."
        )
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        page_chars = max_chars if max_chars and max_chars > 0 else compute_page_chars(model, provider)
        if offset > 0:
            content = content[offset:]
        return truncate_with_offset_hint(content, max_chars=page_chars, offset=offset)
    except Exception as e:
        return f"Error reading file: {e}"


async def write_file(path: str, content: str, user_id: str, db: "Db | None") -> str:
    """Write file content under allowed/workspace paths."""
    path = (path or "").strip()
    if not path:
        return "Error: path is required."
    if not isinstance(content, str):
        return "Error: content must be a string."
    if not db:
        return "Error: database not available."
    try:
        from app.routers.files import write_to_allowed_path

        written = await write_to_allowed_path(user_id, path, content)
        return json.dumps({"ok": True, "path": written}, indent=0)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


async def allow_path(path: str, user_id: str, db: "Db | None") -> str:
    """Add a path to the user's allowed list (request access). Only allows paths under the user's home directory."""
    path = (path or "").strip()
    if not path:
        return "Error: path is required."
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: path does not exist: {p}"
    home = Path.home()
    try:
        p.relative_to(home)
    except ValueError:
        return f"Error: for safety, only paths under your home directory can be added. {p} is not under {home}."
    if not db:
        return "Error: database not available."
    await db.connect()
    await db.add_allowed_path(user_id, str(p))
    if p.is_file():
        parent = p.parent
        if str(parent) != "/":
            await db.add_allowed_path(user_id, str(parent))
    return f"Added {p} to your allowed paths. You can now ask me to list or read files there."


def _resolve_trash_target(path: Path) -> Path:
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    target = trash_dir / path.name
    if not target.exists():
        return target
    stem = path.stem
    suffix = path.suffix
    idx = 2
    while True:
        candidate = trash_dir / f"{stem} {idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def _safe_remove(path: Path, permanently: bool) -> tuple[bool, str]:
    try:
        if permanently:
            path.unlink()
            return True, f"Deleted file: {path}"
        target = _resolve_trash_target(path)
        shutil.move(str(path), str(target))
        return True, f"Moved to Trash: {path.name}"
    except Exception as e:
        return False, f"Failed to remove {path}: {e}"


async def delete_file(path: str, user_id: str, db: "Db | None", permanently: bool = False) -> str:
    """Delete one file (or move to Trash by default)."""
    path = (path or "").strip()
    if not path:
        return "Error: path is required."
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: path does not exist: {p}"
    if p.is_dir():
        return f"Error: directory deletion is not supported by this tool: {p}"
    allowed = await _allowed_paths(db, user_id)
    if not _path_is_allowed(p, allowed):
        return (
            f"Path {p} is not in the allowed list. "
            "The user can add it in Settings -> Files, or say 'allow my Desktop' to add a folder."
        )
    ok, msg = _safe_remove(p, permanently=bool(permanently))
    return msg if ok else f"Error: {msg}"


async def delete_matching_files(
    directory: str,
    glob_pattern: str,
    user_id: str,
    db: "Db | None",
    permanently: bool = False,
    max_delete: int = 50,
) -> str:
    """Delete matching files in a directory (or move to Trash by default)."""
    directory = (directory or "").strip()
    glob_pattern = (glob_pattern or "").strip()
    if not directory:
        return "Error: directory is required."
    if not glob_pattern:
        return "Error: glob_pattern is required."
    d = Path(directory).expanduser().resolve()
    if not d.is_dir():
        return f"Error: not a directory: {d}"
    allowed = await _allowed_paths(db, user_id)
    if not _path_is_allowed(d, allowed):
        return (
            f"Path {d} is not in the allowed list. "
            "The user can add it in Settings -> Files, or say 'allow my Desktop' to add a folder."
        )
    matched: list[Path] = []
    try:
        for p in sorted(d.glob(glob_pattern)):
            if p.is_file():
                matched.append(p.resolve())
            if len(matched) >= max_delete:
                break
    except Exception as e:
        return f"Error: invalid glob pattern: {e}"
    if not matched:
        return f"No files matched '{glob_pattern}' in {d}."

    deleted = 0
    errors: list[str] = []
    names: list[str] = []
    for p in matched:
        ok, msg = _safe_remove(p, permanently=bool(permanently))
        if ok:
            deleted += 1
            names.append(p.name)
        else:
            errors.append(msg)

    payload = {
        "directory": str(d),
        "pattern": glob_pattern,
        "deleted_count": deleted,
        "deleted_files": names,
        "error_count": len(errors),
        "errors": errors[:10],
    }
    return json.dumps(payload, indent=0)


def get_files_tools_openai_def() -> list[dict]:
    """OpenAI-style tool definitions for list/read/write/allow/delete file operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": (
                    "List files and folders in a directory (e.g. Desktop, Documents). "
                    "Use when the user asks to 'check my desktop', 'what's on my desktop', 'list files in X', or 'what can I delete'. "
                    "Path can be ~/Desktop, /Users/username/Desktop, or any path the user has allowed. "
                    "If the path is not allowed, tell the user to say 'allow my Desktop' or add it in Settings → Files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path, e.g. ~/Desktop or /Users/you/Desktop",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    "Read the text content of a file. Use when the user asks to open, read, or show a file. "
                    "Path must be in the user's allowed list (or they can say 'allow my Desktop' first). "
                    "If output ends with a continuation hint, call again with offset=N to read the next page."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full path to the file"},
                        "offset": {
                            "type": "integer",
                            "description": "Character offset to start reading from (for pagination, default 0)",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": (
                    "Write text/markdown content to a file under allowed paths or workspace. "
                    "Use this when the user asks to save or create a file (e.g. shopping list, notes)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Target file path. Relative paths are resolved under workspace.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Exact file content to write.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "allow_path",
                "description": (
                    "Add a path to the user's allowed list so you can list/read there (request access). "
                    "Use when the user says 'allow my Desktop', 'you can access my desktop', 'grant access to X', or asks you to 'enter' or 'check' a folder they haven't allowed yet. "
                    "Only paths under the user's home directory can be added. Call this first, then list_directory to show contents."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to allow, e.g. ~/Desktop or /Users/you/Documents",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": (
                    "Delete one file from an allowed path. "
                    "By default it moves the file to Trash (safer). Set permanently=true only when the user clearly asked for permanent deletion."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full file path to delete"},
                        "permanently": {
                            "type": "boolean",
                            "description": "If true, delete permanently instead of moving to Trash",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_matching_files",
                "description": (
                    "Delete files matching a glob pattern inside a directory (e.g. '~/Desktop' + 'Screenshot *.png'). "
                    "Use this when user asks to delete multiple similar files. "
                    "By default files are moved to Trash. "
                    "If the user asks to delete screenshot files and doesn't name a folder, prefer directory='~/Desktop'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path, e.g. ~/Desktop",
                        },
                        "glob_pattern": {
                            "type": "string",
                            "description": "Glob pattern, e.g. 'Screenshot *.png' or '*.tmp'",
                        },
                        "permanently": {
                            "type": "boolean",
                            "description": "If true, delete permanently instead of moving to Trash",
                        },
                    },
                    "required": ["directory", "glob_pattern"],
                },
            },
        },
    ]


def parse_files_tool_args(arguments_str: str) -> dict:
    """Parse tool call arguments JSON with validation."""

    # If already a dict, validate it
    if isinstance(arguments_str, dict):
        # Validate expected keys exist and are correct types
        validated = {}

        # Path validation (common to all file operations)
        if "path" in arguments_str:
            path = arguments_str["path"]
            validated["path"] = str(path) if path is not None else ""

        # Content validation (for write operations)
        if "content" in arguments_str:
            content = arguments_str["content"]
            validated["content"] = str(content) if content is not None else ""

        # Action validation (if present)
        if "action" in arguments_str:
            validated["action"] = str(arguments_str["action"])

        # delete_matching_files: directory, glob_pattern (pattern as alias), permanently
        if "directory" in arguments_str:
            validated["directory"] = str(arguments_str["directory"]) if arguments_str["directory"] is not None else ""
        if "glob_pattern" in arguments_str:
            validated["glob_pattern"] = str(arguments_str["glob_pattern"]) if arguments_str["glob_pattern"] is not None else ""
        elif "pattern" in arguments_str:
            validated["glob_pattern"] = str(arguments_str["pattern"]) if arguments_str["pattern"] is not None else ""
        if "permanently" in arguments_str:
            validated["permanently"] = bool(arguments_str["permanently"])

        # Legacy pattern key for any consumer that expects it
        if "pattern" in arguments_str:
            validated["pattern"] = str(arguments_str["pattern"]) if arguments_str["pattern"] is not None else ""

        return validated

    # Parse JSON string
    try:
        data = json.loads(arguments_str)
        if isinstance(data, dict):
            # Recursively validate the parsed dict
            return parse_files_tool_args(data)
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}
