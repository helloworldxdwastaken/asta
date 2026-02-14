"""OpenClaw-style read tool for workspace files (SKILL.md and referenced files)."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings

MAX_READ_CHARS = 60_000


def _workspace_root() -> Path | None:
    root = get_settings().workspace_path
    if not root:
        return None
    try:
        return root.resolve()
    except Exception:
        return None


def _resolve_workspace_path(raw_path: str) -> tuple[Path | None, str | None]:
    root = _workspace_root()
    if not root:
        return None, "Workspace is not configured."
    path_str = (raw_path or "").strip()
    if not path_str:
        return None, "path is required."
    candidate = Path(path_str).expanduser()
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"path must be inside workspace: {root}"
    return candidate, None


async def read_workspace_file(path: str, max_chars: int = MAX_READ_CHARS) -> str:
    """Read a workspace file by absolute or workspace-relative path."""
    resolved, err = _resolve_workspace_path(path)
    if err:
        return f"Error: {err}"
    if not resolved or not resolved.is_file():
        return f"Error: not a file: {resolved}"
    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
    if len(content) > max_chars:
        content = content[:max_chars] + "\n... (truncated)"
    return content


def get_workspace_read_tool_openai_def() -> list[dict]:
    """OpenAI-style function tool: read(path) for workspace files."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": (
                    "Read a text file from the workspace. Use this to open a selected skill's SKILL.md "
                    "and any files it references with relative paths."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Workspace-relative or absolute file path, e.g. "
                                "skills/weather/SKILL.md or /Users/me/asta/workspace/skills/weather/SKILL.md"
                            ),
                        }
                    },
                    "required": ["path"],
                },
            },
        }
    ]


def parse_workspace_read_args(arguments_str: str) -> dict:
    """Parse tool call args JSON for read(path)."""
    if isinstance(arguments_str, dict):
        return arguments_str
    try:
        data = json.loads(arguments_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
