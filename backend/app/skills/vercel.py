import asyncio
import os
from app.lib.skill import Skill
from typing import Any
from app.config import get_settings


async def run_cmd(cmd: str, cwd: str = None) -> dict[str, Any]:
    """Run a shell command and return stdout/stderr."""
    parts = cmd.split()
    # Default to project root where .vercel config exists
    if not cwd:
        cwd = "/Users/tokyo/asta"
    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    # Combine stdout and stderr (some CLI tools like vercel output to stderr)
    combined = stdout.decode().strip() or stderr.decode().strip()
    return {
        "stdout": combined,
        "stderr": stderr.decode().strip(),
        "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        "returncode": proc.returncode
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
            "vc ", "vercel ",
        ))
    
    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute Vercel operations via vercel CLI."""
        settings = get_settings()
        
        # Check if vercel is available
        check = await run_cmd("which vercel")
        if check.get("error") or not check.get("stdout"):
            # Try vc alias
            check = await run_cmd("which vc")
            if check.get("error") or not check.get("stdout"):
                return {
                    "vercel_error": "Vercel CLI (`vercel`) not installed. Install with: npm i -g vercel",
                    "vercel_needs_cli": True
                }
        
        t = (text or "").strip()
        t_lower = t.lower()
        
        # Parse commands
        cmd = None
        args = []
        
        # List projects
        if "list" in t_lower and ("project" in t_lower or "vercel" in t_lower):
            cmd = "vercel projects list"
        
        # List deployments
        elif "list" in t_lower and "deployment" in t_lower:
            # Use vercel ls to list deployments
            cmd = "vercel ls"
        
        # Deployment status
        elif "status" in t_lower or "get" in t_lower:
            # Use vercel ls to show deployments
            cmd = "vercel ls"
        
        # Cancel deployment
        elif "cancel" in t_lower:
            deployment_id = self._extract_deployment_id(t)
            if not deployment_id:
                return {"vercel_error": "Please specify deployment ID: deployment: <id>"}
            cmd = f"vercel deployment cancel {deployment_id}"
        
        # Deploy / create deployment
        elif "deploy" in t_lower or "create" in t_lower:
            # For now just list projects
            cmd = "vercel projects list"
        
        # Default: list projects
        else:
            cmd = "vercel projects list"
        
        # Execute
        if cmd:
            full_cmd = cmd + " " + " ".join(args) if args else cmd
            result = await run_cmd(full_cmd)
            
            if result.get("error"):
                stderr = result.get("stderr", "")
                # Check for auth issues
                if "not authenticated" in stderr.lower() or "login" in stderr.lower():
                    return {
                        "vercel_error": "Vercel not authenticated. Run: vercel login",
                        "vercel_needs_auth": True,
                        "vercel_auth_instructions": "1. Run: vercel login (your email)\n2. Check email to verify\n3. Then run: vercel link"
                    }
                return {
                    "vercel_error": result.get("stderr", result.get("error")),
                    "vercel_command": full_cmd
                }
            
            output = result.get("stdout", "")
            
            return {
                "vercel_output": output,
                "vercel_command": full_cmd,
                "vercel_summary": self._format_summary(output, cmd)
            }
        
        return {"vercel_error": "Could not understand Vercel request. Try: 'list vercel projects', 'list deployments', etc."}
    
    def _extract_project(self, text: str) -> str | None:
        import re
        match = re.search(r'project[:\s]+([a-zA-Z0-9\-_]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_deployment_id(self, text: str) -> str | None:
        import re
        match = re.search(r'deployment[:\s]+([a-zA-Z0-9\-_]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _format_summary(self, output: str, cmd: str) -> str:
        lines = output.strip().split("\n")
        if not lines or not lines[0]:
            return "No results found."
        
        cmd_lower = cmd.lower()
        if "projects" in cmd_lower:
            return f"Found {len(lines)} projects"
        elif "deployment" in cmd_lower:
            return f"Found {len(lines)} deployments"
        
        return f"Got {len(lines)} results"
    
    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_vercel_section
        lines = _get_vercel_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
