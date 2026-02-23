"""OpenClaw-style read tool for workspace files (SKILL.md and referenced files)."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.adaptive_paging import compute_page_chars, truncate_with_offset_hint, DEFAULT_PAGE_CHARS

MAX_READ_CHARS = DEFAULT_PAGE_CHARS  # legacy alias; real limit is now adaptive


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


async def read_workspace_file(
    path: str,
    max_chars: int | None = None,
    offset: int = 0,
    *,
    model: str | None = None,
    provider: str | None = None,
) -> str:
    """Read a workspace file by absolute or workspace-relative path with adaptive paging.

    Args:
        path:      Workspace-relative or absolute path.
        max_chars: Hard cap on output chars. If None, derives from model context window.
        offset:    Character offset to start reading from (for pagination).
        model:     Model name, used to auto-compute adaptive page cap.
        provider:  Provider name, used to refine context window lookup.
    """
    resolved, err = _resolve_workspace_path(path)
    if err:
        return f"Error: {err}"
    if not resolved or not resolved.is_file():
        return f"Error: not a file: {resolved}"
    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
    page_chars = max_chars if max_chars and max_chars > 0 else compute_page_chars(model, provider)
    if offset > 0:
        content = content[offset:]
    return truncate_with_offset_hint(content, max_chars=page_chars, offset=offset)


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
