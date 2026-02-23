import asyncio
import shlex
from app.lib.skill import Skill
from typing import Any


async def run_cmd(cmd: str, cwd: str | None = None) -> dict[str, Any]:
    """Run a shell command string safely using shlex.split."""
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return {"stdout": "", "stderr": str(e), "error": str(e), "returncode": 1}

    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,  # None = inherit backend working directory
    )
    stdout, stderr = await proc.communicate()
    out = stdout.decode().strip()
    err = stderr.decode().strip()
    combined = out or err
    return {
        "stdout": combined,
        "stderr": err,
        "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        "returncode": proc.returncode,
    }


class VercelSkill(Skill):
    """Skill for managing Vercel deployments and projects via Vercel CLI.

    Use the `vercel` CLI to interact with Vercel. Requires: `vercel login`
    """

    @property
    def name(self) -> str:
        return "vercel"

    @property
    def is_always_enabled(self) -> bool:
        return False

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            "vercel", "deploy", "deployment", "vercel deploy", "vercel project",
            "cancel deployment", "list deployments", "get deployment",
            "vercel status", "deploy to vercel", "vercel build",
        ))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute Vercel operations via vercel CLI."""
        # Check if vercel is available
        check = await run_cmd("which vercel")
        if check.get("error") or not check.get("stdout"):
            check = await run_cmd("which vc")
            if check.get("error") or not check.get("stdout"):
                return {
                    "vercel_error": "Vercel CLI (`vercel`) not installed. Install with: npm i -g vercel",
                    "vercel_needs_cli": True,
                }

        t = (text or "").strip()
        t_lower = t.lower()
        cmd = None

        if "list" in t_lower and "project" in t_lower:
            cmd = "vercel projects list"
        elif "list" in t_lower and "deployment" in t_lower:
            cmd = "vercel ls"
        elif "cancel" in t_lower:
            deployment_id = self._extract_deployment_id(t)
            if not deployment_id:
                return {"vercel_error": "Please specify deployment ID: deployment: <id>"}
            cmd = f"vercel deployment cancel {shlex.quote(deployment_id)}"
        elif "status" in t_lower or "get" in t_lower:
            cmd = "vercel ls"
        elif "deploy" in t_lower or "create" in t_lower:
            cmd = "vercel projects list"
        else:
            cmd = "vercel projects list"

        if cmd:
            result = await run_cmd(cmd)
            if result.get("error"):
                stderr = result.get("stderr", "")
                if "not authenticated" in stderr.lower() or "login" in stderr.lower():
                    return {
                        "vercel_error": "Vercel not authenticated. Run: vercel login",
                        "vercel_needs_auth": True,
                        "vercel_auth_instructions": (
                            "1. Run: vercel login (your email)\n"
                            "2. Check email to verify\n"
                            "3. Then run: vercel link"
                        ),
                    }
                return {
                    "vercel_error": result.get("stderr", result.get("error")),
                    "vercel_command": cmd,
                }
            return {
                "vercel_output": result.get("stdout", ""),
                "vercel_command": cmd,
                "vercel_summary": self._format_summary(result.get("stdout", ""), cmd),
            }

        return {"vercel_error": "Could not understand Vercel request. Try: 'list vercel projects', 'list deployments', etc."}

    def _extract_deployment_id(self, text: str) -> str | None:
        import re
        m = re.search(r'deployment[:\s]+([a-zA-Z0-9\-_]+)', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _format_summary(self, output: str, cmd: str) -> str:
        lines = [l for l in output.strip().split("\n") if l.strip()]
        if not lines:
            return "No results found."
        if "projects" in cmd.lower():
            return f"Found {len(lines)} projects"
        elif "deployment" in cmd.lower():
            return f"Found {len(lines)} deployments"
        return f"Got {len(lines)} results"

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_vercel_section
        lines = _get_vercel_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
