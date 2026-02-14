"""Claw-like exec: run allowlisted shell commands and return output. Used when the model outputs [ASTA_EXEC: cmd][/ASTA_EXEC] or calls the exec tool (OpenClaw-style)."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from app.db import Db

logger = logging.getLogger(__name__)

EXEC_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120
MAX_OUTPUT_BYTES = 100_000

SYSTEM_CONFIG_EXEC_BINS_KEY = "exec_allowed_bins_extra"

# Search order for resolving bare binary names when PATH is minimal (e.g. backend started by IDE)
_EXEC_SEARCH_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin")


def resolve_executable(name: str) -> str | None:
    """Return full path to executable if findable (PATH or common prefixes); None otherwise."""
    name = (name or "").strip()
    if not name or os.path.sep in name or Path(name).is_absolute():
        return name if name and os.path.isfile(name) and os.access(name, os.X_OK) else None
    resolved = shutil.which(name)
    if resolved:
        return resolved
    home_bin = os.path.expanduser("~/.local/bin")
    for prefix in (*_EXEC_SEARCH_PREFIXES, home_bin):
        candidate = os.path.join(prefix, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


async def get_effective_exec_bins(db: Db | None) -> set[str]:
    """OpenClaw-style: env + DB + bins from all workspace skills (autoAllowSkills)."""
    settings = get_settings()
    allowed = set(settings.exec_allowed_bins or [])
    if db:
        try:
            await db.connect()
            extra = await db.get_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY)
            if extra:
                for b in extra.split(","):
                    b = b.strip().lower()
                    if b:
                        allowed.add(b)
        except Exception:
            pass
    # Bins from all workspace skills (OpenClaw autoAllowSkills: any skill in workspace contributes its required_bins)
    from app.workspace import discover_workspace_skills
    for skill in discover_workspace_skills():
        for b in (skill.required_bins or ()):
            if b:
                allowed.add(b.strip().lower())
    return allowed


def _resolve_safe_workdir(raw: str | None) -> Path | None:
    val = (raw or "").strip()
    if not val:
        return None
    p = Path(val).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        return None
    home = Path.home().resolve()
    try:
        p.relative_to(home)
        return p
    except ValueError:
        pass
    workspace = get_settings().workspace_path
    if workspace:
        try:
            p.relative_to(workspace.resolve())
            return p
        except ValueError:
            pass
    return None


async def run_allowlisted_command(
    cmd: str,
    allowed_bins: set[str] | None = None,
    timeout_seconds: int | None = None,
    workdir: str | None = None,
) -> tuple[str, str, bool]:
    """Run a command if its binary is in the exec allowlist. Returns (stdout, stderr, success).
    Command is parsed with shlex; the first token (binary name or path) must be in allowed bins.
    If allowed_bins is None, uses env only (no DB merge). Pass get_effective_exec_bins(db) for env+DB."""
    cmd = (cmd or "").strip()
    if not cmd:
        return "", "Empty command.", False
    if allowed_bins is not None:
        allowed = allowed_bins
    else:
        allowed = get_settings().exec_allowed_bins
    if not allowed:
        return "", "Exec is disabled (ASTA_EXEC_ALLOWED_BINS not set).", False
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return "", f"Invalid command: {e}", False
    if not parts:
        return "", "Empty command.", False
    binary = Path(parts[0]).name.lower()
    if binary not in allowed:
        logger.warning("Exec rejected: binary %r not in allowlist %s", binary, sorted(allowed))
        return "", f"Command not allowed (binary '{binary}' not in allowlist).", False
    # Resolve binary to full path so we find it even when backend's PATH is minimal (e.g. IDE/launcher)
    exe = parts[0]
    if os.path.sep not in exe and not Path(exe).is_absolute():
        resolved = resolve_executable(exe)
        if resolved:
            parts = [resolved] + list(parts[1:])
        else:
            logger.warning("Exec: binary %r not found in PATH or fallback paths", exe)
    cwd_path = _resolve_safe_workdir(workdir)
    if workdir and cwd_path is None:
        return "", "Invalid workdir. Use a directory under your home or workspace.", False

    timeout = EXEC_TIMEOUT_SECONDS
    if isinstance(timeout_seconds, int):
        timeout = max(1, min(timeout_seconds, MAX_TIMEOUT_SECONDS))

    try:
        proc = await asyncio.create_subprocess_exec(
            *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_path) if cwd_path else None,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace").strip()
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace").strip()
        if len(stdout) > MAX_OUTPUT_BYTES:
            stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... (truncated)"
        if len(stderr) > MAX_OUTPUT_BYTES:
            stderr = stderr[:MAX_OUTPUT_BYTES] + "\n... (truncated)"
        success = proc.returncode == 0
        return stdout, stderr, success
    except asyncio.TimeoutError:
        hint = ""
        if "memo" in cmd.lower():
            hint = " On macOS, permission is per process: run the Asta backend from Terminal (e.g. ./asta.sh start), then when you ask for notes approve the system dialog for the backend process."
        return "", f"Command timed out after {timeout}s.{hint}", False
    except FileNotFoundError:
        return "", f"Binary not found: {parts[0]}", False
    except Exception as e:
        logger.warning("Exec failed for %s: %s", cmd[:80], e)
        return "", str(e), False


def get_exec_tool_openai_def(allowed_bins: set[str]) -> list[dict]:
    """OpenAI-style tool definition for exec (Claw-style). Pass to providers that support tools. When model calls exec with a command, handler runs it and re-calls with result."""
    bins_str = ", ".join(sorted(allowed_bins)) if allowed_bins else "none"
    return [
        {
            "type": "function",
            "function": {
                "name": "exec",
                "description": (
                    "Run a shell command on the user's machine. Use this when the user asks to check Apple Notes (command: memo notes or memo notes -s \"search\"), "
                    "list or search Things (command: things inbox, things search \"query\"), or run another allowlisted CLI. "
                    f"Allowed binaries: {bins_str}. Only use commands that start with one of these. "
                    "Do NOT use exec to list directories (e.g. ls) — use list_directory instead. Do NOT use exec for Spotify (what's playing, search, play) — that is handled by the Spotify skill and Settings."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The full shell command to run (e.g. memo notes, memo notes -s \"gift cards\", things inbox).",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": f"Optional timeout in seconds (1-{MAX_TIMEOUT_SECONDS}).",
                        },
                        "workdir": {
                            "type": "string",
                            "description": "Optional working directory (must be under user's home or workspace).",
                        },
                    },
                    "required": ["command"],
                },
            },
        }
    ]


def parse_exec_arguments(arguments_str: str) -> dict:
    """Parse tool call arguments JSON (may be a string). Returns dict with 'command' key."""
    try:
        if isinstance(arguments_str, dict):
            return arguments_str
        data = json.loads(arguments_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
