"""Claw-like exec: run allowlisted shell commands and return output. Used when the model outputs [ASTA_EXEC: cmd][/ASTA_EXEC]."""
import asyncio
import logging
import shlex
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

EXEC_TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 100_000


async def run_allowlisted_command(cmd: str) -> tuple[str, str, bool]:
    """Run a command if its binary is in the exec allowlist. Returns (stdout, stderr, success).
    Command is parsed with shlex; the first token (binary name or path) must be in allowed bins."""
    cmd = (cmd or "").strip()
    if not cmd:
        return "", "Empty command.", False
    settings = get_settings()
    allowed = settings.exec_allowed_bins
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
        return "", f"Command not allowed (binary '{binary}' not in allowlist).", False
    try:
        proc = await asyncio.create_subprocess_exec(
            *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=EXEC_TIMEOUT_SECONDS
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
        return "", f"Command timed out after {EXEC_TIMEOUT_SECONDS}s.", False
    except FileNotFoundError:
        return "", f"Binary not found: {parts[0]}", False
    except Exception as e:
        logger.warning("Exec failed for %s: %s", cmd[:80], e)
        return "", str(e), False
