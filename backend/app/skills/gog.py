import asyncio
import os
import json
import shlex
from app.lib.skill import Skill
from typing import Any

# Homebrew puts binaries here on Apple Silicon and Intel Macs
_GOG_PATH = "/opt/homebrew/bin/gog"
_FALLBACK_PATH = "/usr/local/bin/gog"


def _gog_bin() -> str | None:
    """Return path to gog binary, or None if not found."""
    for p in (_GOG_PATH, _FALLBACK_PATH):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    # Also check PATH
    import shutil
    return shutil.which("gog")


async def run_gog(args: list[str], timeout: float = 15.0) -> dict[str, Any]:
    """Run `gog <args>` safely (no shell injection) and return stdout/stderr."""
    gog = _gog_bin()
    if not gog:
        return {"stdout": "", "stderr": "", "error": "gog not found", "returncode": 127}

    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")

    try:
        proc = await asyncio.create_subprocess_exec(
            gog, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip(),
            "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"stdout": "", "stderr": "", "error": "Timed out", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": "", "error": str(e), "returncode": -1}


def _default_account() -> str:
    """Return the configured Google account from env (GOG_ACCOUNT or GOOGLE_ACCOUNT)."""
    return (
        os.environ.get("GOG_ACCOUNT")
        or os.environ.get("GOOGLE_ACCOUNT")
        or ""
    )


class GoogleWorkspaceSkill(Skill):
    """Manage Gmail, Google Calendar, Drive, Contacts via `gog` CLI.

    Requires: brew install gogcli  →  gog auth add your@gmail.com --services gmail,calendar,drive,contacts
    Docs: https://gogcli.sh
    """

    @property
    def name(self) -> str:
        return "google_workspace"

    @property
    def is_always_enabled(self) -> bool:
        return False

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            # Gmail
            "gmail", "email", "inbox", "mail", "unread", "send email", "check email",
            "read email", "my emails", "my inbox",
            # Calendar
            "calendar", "event", "meeting", "schedule", "appointment",
            "what do i have", "what's on my", "add to calendar", "create event",
            # Drive
            "google drive", "drive file", "my drive",
            # Contacts
            "google contacts", "my contacts",
            # Generic Google
            "google doc", "google sheet",
            # CLI
            "gog ",
        ))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute Google Workspace operations via gog CLI."""

        # 1. Check binary
        if not _gog_bin():
            return {
                "gog_error": "Google Workspace CLI (`gog`) not installed.",
                "gog_fix": "Install with: brew install gogcli",
                "gog_needs_cli": True,
            }

        # 2. Check auth
        auth = await run_gog(["auth", "list"])
        if auth.get("error") or not auth.get("stdout"):
            return {
                "gog_error": "Google Workspace not authenticated.",
                "gog_fix": (
                    "1. brew install gogcli\n"
                    "2. gog auth credentials /path/to/client_secret.json\n"
                    "3. gog auth add your@gmail.com --services gmail,calendar,drive,contacts"
                ),
                "gog_needs_auth": True,
            }

        account = _default_account()
        t = (text or "").strip()
        t_lower = t.lower()

        # --- Gmail ---
        if any(k in t_lower for k in ("gmail", "email", "inbox", "mail", "unread")):
            if any(k in t_lower for k in ("send", "write", "compose")):
                to = self._extract_field(t, "to")
                subject = self._extract_field(t, "subject") or "No Subject"
                body = self._extract_field(t, "body") or self._extract_field(t, "message") or ""
                if not to:
                    return {"gog_error": "Please specify recipient: to: someone@example.com"}
                args = ["gmail", "send", "--to", to, "--subject", subject, "--account", account]
                if body:
                    args += ["--body", body]
            else:
                query = self._extract_field(t, "query") or self._extract_field(t, "search") or "newer_than:7d"
                limit = str(self._extract_number(t, "limit") or 10)
                args = ["gmail", "search", query, "--max", limit, "--json", "--account", account]

        # --- Calendar ---
        elif any(k in t_lower for k in ("calendar", "event", "meeting", "schedule", "appointment")):
            if any(k in t_lower for k in ("create", "add", "new", "schedule")):
                title = self._extract_field(t, "title") or self._extract_field(t, "summary")
                start = self._extract_field(t, "start") or self._extract_field(t, "from")
                end = self._extract_field(t, "end") or self._extract_field(t, "to")
                if not title:
                    return {"gog_error": "Please specify event title: title: Meeting Name"}
                if not start:
                    return {"gog_error": "Please specify start time: start: 2025-01-15T14:00"}
                args = ["calendar", "create", "primary", "--summary", title, "--from", start, "--account", account]
                if end:
                    args += ["--to", end]
                loc = self._extract_field(t, "location")
                if loc:
                    args += ["--location", loc]
            else:
                from datetime import datetime, timedelta
                now = datetime.now()
                if "today" in t_lower:
                    start_d = now.strftime("%Y-%m-%d")
                    end_d = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                elif "tomorrow" in t_lower:
                    start_d = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                    end_d = (now + timedelta(days=2)).strftime("%Y-%m-%d")
                else:
                    start_d = now.strftime("%Y-%m-%d")
                    end_d = (now + timedelta(days=7)).strftime("%Y-%m-%d")
                args = ["calendar", "events", "primary", "--from", start_d, "--to", end_d,
                        "--json", "--account", account]

        # --- Drive ---
        elif "drive" in t_lower:
            query = self._extract_field(t, "query") or self._extract_field(t, "search") or ""
            limit = str(self._extract_number(t, "limit") or 10)
            args = ["drive", "search", query, "--max", limit, "--json"]

        # --- Contacts ---
        elif "contact" in t_lower:
            limit = str(self._extract_number(t, "limit") or 20)
            args = ["contacts", "list", "--max", limit, "--json"]

        else:
            # Default: recent emails
            args = ["gmail", "search", "newer_than:7d", "--max", "10", "--json", "--account", account]

        result = await run_gog(args)
        cmd_str = "gog " + " ".join(shlex.quote(a) for a in args)

        if result.get("error"):
            return {
                "gog_error": result.get("stderr") or result.get("error"),
                "gog_command": cmd_str,
            }

        output = result.get("stdout", "")
        try:
            data = json.loads(output) if output else []
            return {
                "gog_output": output,
                "gog_data": data,
                "gog_command": cmd_str,
                "gog_summary": self._format_summary(data, args),
            }
        except json.JSONDecodeError:
            return {
                "gog_output": output,
                "gog_command": cmd_str,
            }

    # ── helpers ────────────────────────────────────────────────────────────────

    def _extract_field(self, text: str, name: str) -> str | None:
        import re
        m = re.search(rf'{re.escape(name)}[:\s]+["\']?([^"\'\n]+)["\']?', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_number(self, text: str, word: str) -> int | None:
        import re
        m = re.search(rf'(?:{re.escape(word)})[:\s]*(\d+)', text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _format_summary(self, data: Any, args: list[str]) -> str:
        count = len(data) if isinstance(data, list) else 1
        joined = " ".join(args[:2])
        if "gmail" in joined:
            return f"Found {count} emails"
        if "calendar" in joined:
            return f"Found {count} events"
        if "drive" in joined:
            return f"Found {count} files"
        if "contacts" in joined:
            return f"Found {count} contacts"
        return f"Got {count} results"

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        # Don't re-check auth on every message — use cached result from execute() if present.
        # execute() is called before get_context_section() by the skill runner.
        if extra.get("gog_error"):
            # execute() already ran and failed
            return None
        if not _gog_bin():
            return None
        # Light auth check (cached by OS) — fast after first call
        auth = await run_gog(["auth", "list"])
        if auth.get("error") or not auth.get("stdout"):
            return None
        account = _default_account()
        return (
            f"[Google Workspace] Authenticated as {account}. "
            "You can read/search Gmail, list Calendar events, search Drive files, and list Contacts.\n"
        )
