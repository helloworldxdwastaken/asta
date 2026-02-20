import asyncio
import os
import json
from app.lib.skill import Skill
from typing import Any


async def run_cmd(cmd: str) -> dict[str, Any]:
    """Run a shell command and return stdout/stderr."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return {
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
        "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        "returncode": proc.returncode
    }


class GoogleWorkspaceSkill(Skill):
    """Skill for managing Gmail, Google Calendar, Drive, Contacts, Sheets, and Docs via `gog` CLI.
    
    Use the `gog` CLI to interact with Google Workspace. Requires: `gog auth add`
    Install: brew install gogcli
    Docs: https://gogcli.sh
    """
    
    # Default account for commands
    DEFAULT_ACCOUNT = "dronx.enmanuel@gmail.com"
    
    @property
    def name(self) -> str:
        return "google_workspace"
    
    @property
    def is_always_enabled(self) -> bool:
        return False
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            "gmail", "google mail", "email", "inbox",
            "calendar", "google calendar", "event", "meeting", "schedule",
            "drive", "google drive", "google sheet", "google doc",
            "contacts", "google contacts",
            "gog ", "gmail ", "calendar ",
        ))
    
    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute Google Workspace operations via gog CLI."""
        
        # Check if gog is available
        check = await run_cmd("which gog")
        if check.get("error") or not check.get("stdout"):
            return {
                "gog_error": "Google Workspace CLI (`gog`) not installed. Install with: brew install gogcli",
                "gog_needs_cli": True
            }
        
        # Check if authenticated
        auth_check = await run_cmd("gog auth list")
        if auth_check.get("error") or not auth_check.get("stdout"):
            return {
                "gog_error": "Google Workspace not authenticated. Run: gog auth add you@gmail.com --services gmail,calendar",
                "gog_needs_auth": True,
                "gog_auth_instructions": "1. Get OAuth client ID from Google Cloud Console\n2. Run: gog auth credentials /path/to/client_secret.json\n3. Run: gog auth add you@gmail.com --services gmail,calendar,drive,contacts,docs,sheets"
            }
        
        t = (text or "").strip()
        t_lower = t.lower()
        
        # Determine which service to use
        cmd = None
        args = []
        
        # GMAIL operations
        if any(k in t_lower for k in ("gmail", "email", "inbox", "mail")):
            # Search emails
            if "search" in t_lower or "find" in t_lower or "list" in t_lower:
                query = self._extract_query(t)
                limit = self._extract_limit(t) or 10
                cmd = f"gog gmail search '{query}' --max {limit} --json --account {self.DEFAULT_ACCOUNT}"
            
            # Send email
            elif "send" in t_lower or "email" in t_lower and "check" not in t_lower:
                to = self._extract_email(t, "to")
                subject = self._extract_subject(t)
                body = self._extract_body(t)
                
                if not to:
                    return {"gog_error": "Please specify recipient: to: someone@example.com"}
                if not subject:
                    return {"gog_error": "Please specify subject: subject: Your Subject"}
                
                cmd = f"gog gmail send --to {to} --subject \"{subject}\" --account {self.DEFAULT_ACCOUNT}"
                if body:
                    cmd += f" --body \"{body}\""
            
            # Read specific message
            elif any(k in t_lower for k in ("read", "view", "show", "get")):
                query = self._extract_query(t)
                limit = self._extract_limit(t) or 5
                cmd = f"gog gmail search '{query}' --max {limit} --json --account {self.DEFAULT_ACCOUNT}"
            
            else:
                # Default: search recent emails
                cmd = f"gog gmail search 'newer_than:7d' --max 10 --json --account {self.DEFAULT_ACCOUNT}"
        
        # CALENDAR operations
        elif any(k in t_lower for k in ("calendar", "event", "meeting", "schedule")):
            # List events
            if "list" in t_lower or "events" in t_lower or "today" in t_lower or "tomorrow" in t_lower:
                # Extract time range
                if "today" in t_lower:
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    start = now.strftime("%Y-%m-%d")
                    end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                elif "tomorrow" in t_lower:
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    start = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                    end = (now + timedelta(days=2)).strftime("%Y-%m-%d")
                else:
                    # Default: next 7 days
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    start = now.strftime("%Y-%m-%d")
                    end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
                
                cmd = f"gog calendar events primary --from {start} --to {end} --json --account {self.DEFAULT_ACCOUNT}"
            
            # Create event
            elif "create" in t_lower or "add" in t_lower or "new" in t_lower:
                title = self._extract_title(t)
                start_time = self._extract_datetime(t, "start") or self._extract_datetime(t, "from")
                end_time = self._extract_datetime(t, "end") or self._extract_datetime(t, "to")
                
                if not title:
                    return {"gog_error": "Please specify event title: title: Meeting Name"}
                if not start_time:
                    return {"gog_error": "Please specify start time: start: 2024-01-15T14:00"}
                
                cmd = f"gog calendar create primary --summary \"{title}\" --from {start_time} --account {self.DEFAULT_ACCOUNT}"
                if end_time:
                    cmd += f" --to {end_time}"
                
                # Add location if mentioned
                location = self._extract_location(t)
                if location:
                    cmd += f" --location \"{location}\""
            
            # Default: list upcoming events
            else:
                from datetime import datetime, timedelta
                now = datetime.now()
                start = now.strftime("%Y-%m-%d")
                end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
                cmd = f"gog calendar events primary --from {start} --to {end} --json --account {self.DEFAULT_ACCOUNT}"
        
        # DRIVE operations
        elif "drive" in t_lower:
            if "search" in t_lower or "find" in t_lower or "list" in t_lower:
                query = self._extract_query(t)
                limit = self._extract_limit(t) or 10
                cmd = f"gog drive search \"{query}\" --max {limit} --json"
            else:
                cmd = "gog drive search \"\" --max 10 --json"
        
        # CONTACTS
        elif "contact" in t_lower:
            if "list" in t_lower or "all" in t_lower:
                limit = self._extract_limit(t) or 20
                cmd = f"gog contacts list --max {limit} --json"
            else:
                cmd = "gog contacts list --max 20 --json"
        
        # Default: list recent emails
        else:
            cmd = "gog gmail search 'newer_than:7d' --max 10 --json"
        
        # Execute
        if cmd:
            result = await run_cmd(cmd)
            
            if result.get("error"):
                return {
                    "gog_error": result.get("stderr", result.get("error")),
                    "gog_command": cmd
                }
            
            output = result.get("stdout", "")
            
            # Try to parse JSON for better formatting
            try:
                data = json.loads(output) if output else []
                return {
                    "gog_output": output,
                    "gog_data": data,
                    "gog_command": cmd,
                    "gog_summary": self._format_summary(data, cmd)
                }
            except json.JSONDecodeError:
                return {
                    "gog_output": output,
                    "gog_command": cmd,
                    "gog_summary": self._format_output(output, cmd)
                }
        
        return {"gog_error": "Could not understand Google Workspace request."}
    
    def _extract_query(self, text: str) -> str:
        import re
        # Extract query from various patterns
        match = re.search(r'(?:query|search|find)[:\s]+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Common patterns
        match = re.search(r'(?:newer_than|from|to)[:\s]+(\S+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "newer_than:7d"
    
    def _extract_limit(self, text: str) -> int | None:
        import re
        match = re.search(r'(?:limit|max)[:\s]*(\d+)', text, re.IGNORECASE)
        return int(match.group(1)) if match else None
    
    def _extract_email(self, text: str, prefix: str) -> str | None:
        import re
        match = re.search(rf'{prefix}[:\s]+([^\s,]+@[^\s,]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_subject(self, text: str) -> str | None:
        import re
        match = re.search(r'subject[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_body(self, text: str) -> str | None:
        import re
        match = re.search(r'(?:body|message)[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_title(self, text: str) -> str | None:
        import re
        match = re.search(r'(?:title|summary|event)[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_location(self, text: str) -> str | None:
        import re
        match = re.search(r'location[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_datetime(self, text: str, prefix: str) -> str | None:
        import re
        # ISO format: 2024-01-15T14:00
        match = re.search(rf'{prefix}[:\s]+(\d{{4}}-\d{{2}}-\d{{2}}(?:T\d{{2}}:\d{{2}})?)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _format_summary(self, data: Any, cmd: str) -> str:
        if isinstance(data, list):
            count = len(data)
            cmd_lower = cmd.lower()
            if "gmail" in cmd_lower:
                return f"Found {count} emails"
            elif "calendar" in cmd_lower:
                return f"Found {count} events"
            elif "drive" in cmd_lower:
                return f"Found {count} files"
            elif "contact" in cmd_lower:
                return f"Found {count} contacts"
            return f"Got {count} results"
        return "Got results"
    
    def _format_output(self, output: str, cmd: str) -> str:
        lines = output.strip().split("\n")
        count = len([l for l in lines if l.strip()])
        cmd_lower = cmd.lower()
        if "gmail" in cmd_lower:
            return f"Found {count} emails"
        elif "calendar" in cmd_lower:
            return f"Found {count} events"
        return f"Got {count} results"
    
    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        # For now, just run a quick check on recent emails
        result = await run_cmd("gog gmail search 'newer_than:1d' --max 3 --json 2>/dev/null")
        if result.get("stdout"):
            return f"[Google Workspace] Recent emails available. Ask to see them.\n"
        return None
