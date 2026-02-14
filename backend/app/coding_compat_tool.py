"""OpenClaw-style coding tool compatibility wrappers: read/write/edit."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.files_tool import _allowed_paths, _path_is_allowed
from app.routers.files import write_to_allowed_path

if TYPE_CHECKING:
    from app.db import Db

DEFAULT_MAX_READ_CHARS = 60_000
MAX_READ_CHARS_CAP = 200_000


def get_coding_compat_tools_openai_def() -> list[dict]:
    """OpenAI-style coding tools compatible with OpenClaw/Claude-style arg names."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": (
                    "Read a text file. Supports both `path` and `file_path` parameter names. "
                    "Relative paths resolve under workspace."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to file"},
                        "file_path": {"type": "string", "description": "Alias for path"},
                        "max_chars": {"type": "integer", "description": "Optional max output characters"},
                        "maxChars": {"type": "integer", "description": "CamelCase alias for max_chars"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write",
                "description": (
                    "Write full file content. Supports `path`/`file_path`. "
                    "Relative paths resolve under workspace."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to file"},
                        "file_path": {"type": "string", "description": "Alias for path"},
                        "content": {"type": "string", "description": "Exact file content to write"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit",
                "description": (
                    "Edit file content by replacing one text occurrence. Supports aliases: "
                    "`path`/`file_path`, `oldText`/`old_string`, `newText`/`new_string`."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to file"},
                        "file_path": {"type": "string", "description": "Alias for path"},
                        "oldText": {"type": "string", "description": "Text to replace"},
                        "newText": {"type": "string", "description": "Replacement text"},
                        "old_string": {"type": "string", "description": "Alias for oldText"},
                        "new_string": {"type": "string", "description": "Alias for newText"},
                    },
                },
            },
        },
    ]


def parse_coding_compat_args(arguments_str: str | dict) -> dict:
    """Normalize compatibility argument aliases into canonical keys."""
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except Exception:
        data = {}

    out = dict(data)
    if not isinstance(out.get("path"), str) and isinstance(out.get("file_path"), str):
        out["path"] = out["file_path"]
    if not isinstance(out.get("oldText"), str) and isinstance(out.get("old_string"), str):
        out["oldText"] = out["old_string"]
    if not isinstance(out.get("newText"), str) and isinstance(out.get("new_string"), str):
        out["newText"] = out["new_string"]
    if not isinstance(out.get("max_chars"), int):
        max_chars = out.get("maxChars")
        if isinstance(max_chars, int):
            out["max_chars"] = max_chars
        elif isinstance(max_chars, str) and max_chars.strip().isdigit():
            out["max_chars"] = int(max_chars.strip())
    return out


async def _resolve_compatible_path(
    raw_path: str,
    user_id: str,
    db: "Db | None",
) -> tuple[Path | None, str | None]:
    path = (raw_path or "").strip()
    if not path:
        return None, "path is required."
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        workspace = get_settings().workspace_path
        if workspace:
            candidate = (workspace / candidate).resolve()
        else:
            allowed = await _allowed_paths(db, user_id)
            if not allowed:
                return None, "Relative path requires workspace or allowed paths."
            candidate = (allowed[0] / candidate).resolve()
    else:
        candidate = candidate.resolve()
    allowed = await _allowed_paths(db, user_id)
    if not _path_is_allowed(candidate, allowed):
        return (
            None,
            (
                f"Path {candidate} is not in the allowed list. "
                "Add it in Settings -> Files, or ask to allow that path first."
            ),
        )
    return candidate, None


async def run_read_compat(params: dict, user_id: str, db: "Db | None") -> str:
    path, err = await _resolve_compatible_path((params.get("path") or ""), user_id, db)
    if err:
        return f"Error: {err}"
    if not path or not path.is_file():
        return f"Error: not a file: {path}"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
    max_chars_raw = params.get("max_chars")
    max_chars = DEFAULT_MAX_READ_CHARS
    if isinstance(max_chars_raw, int):
        max_chars = max(1, min(max_chars_raw, MAX_READ_CHARS_CAP))
    if len(content) > max_chars:
        return content[:max_chars] + "\n... (truncated)"
    return content


async def run_write_compat(params: dict, user_id: str, db: "Db | None") -> str:
    path = (params.get("path") or "").strip()
    if not path:
        return "Error: path is required."
    content = params.get("content")
    if not isinstance(content, str):
        return "Error: content must be a string."
    try:
        written = await write_to_allowed_path(user_id, path, content)
        return json.dumps({"ok": True, "path": written}, indent=0)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


async def run_edit_compat(params: dict, user_id: str, db: "Db | None") -> str:
    path, err = await _resolve_compatible_path((params.get("path") or ""), user_id, db)
    if err:
        return f"Error: {err}"
    if not path or not path.is_file():
        return f"Error: not a file: {path}"
    old_text = params.get("oldText")
    new_text = params.get("newText")
    if not isinstance(old_text, str) or old_text == "":
        return "Error: oldText (or old_string) is required and must be non-empty."
    if not isinstance(new_text, str):
        return "Error: newText (or new_string) is required and must be a string."
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
    idx = content.find(old_text)
    if idx < 0:
        return "Error: oldText not found in file."
    updated = content.replace(old_text, new_text, 1)
    try:
        path.write_text(updated, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"
    payload = {
        "ok": True,
        "path": str(path),
        "replaced": 1,
    }
    return json.dumps(payload, indent=0)
