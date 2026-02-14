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


async def get_effective_exec_bins(db: Db | None, user_id: str | None = None) -> set[str]:
    """OpenClaw-style: env + DB + bins from enabled workspace skills (autoAllowSkills)."""
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
    # Bins from enabled workspace skills only (OpenClaw autoAllowSkills behavior).
    from app.workspace import discover_workspace_skills, is_skill_runtime_eligible
    for skill in discover_workspace_skills():
        # OpenClaw-style: only host-eligible skills should influence runtime command surface.
        if not is_skill_runtime_eligible(skill, require_bins=False):
            continue
        if db and user_id:
            try:
                if not await db.get_skill_enabled(user_id, skill.name):
                    continue
            except Exception:
                pass
        for b in (skill.required_bins or ()):
            if b:
                allowed.add(b.strip().lower())
    return allowed


def resolve_safe_workdir(raw: str | None) -> Path | None:
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


def prepare_allowlisted_command(
    cmd: str,
    *,
    allowed_bins: set[str] | None = None,
) -> tuple[list[str] | None, str | None]:
    """Parse and validate command against exec security policy. Returns (argv, error)."""
    cmd = (cmd or "").strip()
    if not cmd:
        return None, "Empty command."
    settings = get_settings()
    security_mode = settings.exec_security
    if security_mode == "deny":
        return None, "Exec is disabled (ASTA_EXEC_SECURITY=deny)."
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return None, f"Invalid command: {e}"
    if not parts:
        return None, "Empty command."
    binary = Path(parts[0]).name.lower()
    if security_mode == "allowlist":
        allowed = allowed_bins if allowed_bins is not None else settings.exec_allowed_bins
        if not allowed:
            return None, "Exec is disabled (ASTA_EXEC_ALLOWED_BINS not set; security=allowlist)."
        if binary not in allowed:
            logger.warning("Exec rejected: binary %r not in allowlist %s", binary, sorted(allowed))
            return None, f"Command not allowed (binary '{binary}' not in allowlist)."
    exe = parts[0]
    if os.path.sep not in exe and not Path(exe).is_absolute():
        resolved = resolve_executable(exe)
        if resolved:
            parts = [resolved] + list(parts[1:])
        else:
            logger.warning("Exec: binary %r not found in PATH or fallback paths", exe)
    return parts, None


async def run_allowlisted_command(
    cmd: str,
    allowed_bins: set[str] | None = None,
    timeout_seconds: int | None = None,
    workdir: str | None = None,
) -> tuple[str, str, bool]:
    """Run a command if its binary is in the exec allowlist. Returns (stdout, stderr, success).
    Command is parsed with shlex; the first token (binary name or path) must be in allowed bins.
    If allowed_bins is None, uses env only (no DB merge). Pass get_effective_exec_bins(db) for env+DB."""
    parts, err = prepare_allowlisted_command(cmd, allowed_bins=allowed_bins)
    if err:
        return "", err, False
    assert parts is not None
    cwd_path = resolve_safe_workdir(workdir)
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


def get_exec_tool_openai_def(allowed_bins: set[str], security_mode: str | None = None) -> list[dict]:
    """OpenAI-style tool definition for exec (Claw-style). Pass to providers that support tools. When model calls exec with a command, handler runs it and re-calls with result."""
    mode = (security_mode or get_settings().exec_security).strip().lower()
    bins_str = ", ".join(sorted(allowed_bins)) if allowed_bins else "none"
    policy_line = (
        f"Security policy: {mode}. "
        + (
            "Any command is allowed (dangerous mode)." if mode == "full"
            else f"Allowed binaries: {bins_str}."
        )
    )
    return [
        {
            "type": "function",
            "function": {
                "name": "exec",
                "description": (
                    "Run a shell command on the user's machine. Use this when the user asks to check Apple Notes (command: memo notes or memo notes -s \"search\"), "
                    "list or search Things (command: things inbox, things search \"query\"), or run another allowlisted CLI. "
                    + policy_line + " "
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
                        "timeout": {
                            "type": "integer",
                            "description": f"OpenClaw-compatible alias for timeout_sec (seconds, 1-{MAX_TIMEOUT_SECONDS}).",
                        },
                        "timeoutSec": {
                            "type": "integer",
                            "description": f"CamelCase alias for timeout_sec (seconds, 1-{MAX_TIMEOUT_SECONDS}).",
                        },
                        "yield_ms": {
                            "type": "integer",
                            "description": "Optional yield window in milliseconds for auto-background behavior (e.g. 10000).",
                        },
                        "yieldMs": {
                            "type": "integer",
                            "description": "OpenClaw-compatible alias for yield_ms.",
                        },
                        "background": {
                            "type": "boolean",
                            "description": "If true, start command in background and return a process session id.",
                        },
                        "pty": {
                            "type": "boolean",
                            "description": "If true, run command in a pseudo-terminal (TTY-like behavior).",
                        },
                        "tty": {
                            "type": "boolean",
                            "description": "Alias for pty.",
                        },
                        "workdir": {
                            "type": "string",
                            "description": "Optional working directory (must be under user's home or workspace).",
                        },
                        "workDir": {
                            "type": "string",
                            "description": "CamelCase alias for workdir.",
                        },
                    },
                    "required": ["command"],
                },
            },
        }
    ]


def get_bash_tool_openai_def(allowed_bins: set[str], security_mode: str | None = None) -> list[dict]:
    """OpenClaw-compatible bash alias (same runtime path as exec)."""
    tools = get_exec_tool_openai_def(allowed_bins, security_mode=security_mode)
    fn = dict(tools[0].get("function") or {})
    fn["name"] = "bash"
    desc = str(fn.get("description") or "")
    fn["description"] = (
        "Alias of exec for OpenClaw compatibility. Use the same command semantics and safety policy. "
        + desc
    )
    return [{"type": "function", "function": fn}]


def parse_exec_arguments(arguments_str: str) -> dict:
    """Parse tool call arguments JSON (may be a string). Returns dict with 'command' key."""
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    def _int_or_none(*keys: str) -> int | None:
        for key in keys:
            val = data.get(key)
            if isinstance(val, bool):
                continue
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                raw = val.strip()
                if raw.isdigit():
                    return int(raw)
        return None

    command = data.get("command")
    if not isinstance(command, str):
        command = data.get("cmd")

    workdir = data.get("workdir")
    if not isinstance(workdir, str):
        workdir = data.get("workDir")
    if not isinstance(workdir, str):
        workdir = data.get("cwd")

    background_raw = data.get("background")
    background = False
    if isinstance(background_raw, bool):
        background = background_raw
    elif isinstance(background_raw, str):
        background = background_raw.strip().lower() in ("1", "true", "yes", "on")
    pty_raw = data.get("pty")
    if not isinstance(pty_raw, (bool, str)):
        pty_raw = data.get("tty")
    pty = False
    if isinstance(pty_raw, bool):
        pty = pty_raw
    elif isinstance(pty_raw, str):
        pty = pty_raw.strip().lower() in ("1", "true", "yes", "on")

    out: dict = {}
    if isinstance(command, str):
        out["command"] = command
    timeout_sec = _int_or_none("timeout_sec", "timeout", "timeoutSec")
    if isinstance(timeout_sec, int):
        out["timeout_sec"] = timeout_sec
    yield_ms = _int_or_none("yield_ms", "yieldMs")
    if isinstance(yield_ms, int):
        out["yield_ms"] = yield_ms
    out["background"] = background
    out["pty"] = pty
    if isinstance(workdir, str):
        out["workdir"] = workdir
    return out
