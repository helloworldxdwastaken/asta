import asyncio
import shlex
from app.lib.skill import Skill
from typing import Any


async def run_cmd(cmd: str) -> dict[str, Any]:
    """Run a shell command string safely using shlex.split."""
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return {"stdout": "", "stderr": str(e), "error": str(e), "returncode": 1}

    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    # gh can write results to either stdout or stderr
    out = stdout.decode().strip()
    err = stderr.decode().strip()
    combined = out or err
    return {
        "stdout": combined,
        "stderr": err,
        "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        "returncode": proc.returncode,
    }


class GitHubSkill(Skill):
    """Skill for managing GitHub repositories, issues, PRs, and CI via `gh` CLI.

    Use the `gh` CLI to interact with GitHub. Requires: `gh auth login`
    """

    @property
    def name(self) -> str:
        return "github"

    @property
    def is_always_enabled(self) -> bool:
        return False

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            "github", "repository", "repo", "pull request", "pr", "issue", "issues",
            "github action", "github workflow", "commit", "branch", "merge",
            "create repo", "new repo", "list repos", "github status",
            "gh issue", "gh pr", "gh run",
        ))

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute GitHub operations via gh CLI."""
        # Check if gh is available
        check = await run_cmd("which gh")
        if check.get("error") or not check.get("stdout"):
            return {
                "github_error": "GitHub CLI (`gh`) not installed. Install with: brew install gh",
                "github_needs_cli": True,
            }

        # Check if authenticated
        auth_check = await run_cmd("gh auth status")
        if auth_check.get("error") or "not logged in" in auth_check.get("stderr", "").lower():
            return {
                "github_error": "GitHub not authenticated. Run: gh auth login",
                "github_needs_auth": True,
                "github_auth_instructions": (
                    "1. Run: gh auth login\n"
                    "2. Select GitHub.com\n"
                    "3. Select HTTPS\n"
                    "4. Login with web browser\n"
                    "5. Authorize gh"
                ),
            }

        t = (text or "").strip()
        t_lower = t.lower()
        cmd = None

        # List repos
        if ("list" in t_lower or "my" in t_lower) and "repo" in t_lower:
            limit = self._extract_number(t, "limit") or 10
            cmd = f"gh repo list --limit {limit}"

        # Issues
        elif "issue" in t_lower:
            repo = self._extract_repo(t)
            if "create" in t_lower or "new" in t_lower:
                if not repo:
                    return {"github_error": "Please specify repository: repo: owner/repo"}
                title = self._extract_title(t)
                if not title:
                    return {"github_error": "Please specify issue title: title: <issue title>"}
                body = self._extract_body(t)
                cmd = f"gh issue create --repo {shlex.quote(repo)} --title {shlex.quote(title)}"
                if body:
                    cmd += f" --body {shlex.quote(body)}"
            elif "view" in t_lower or "show" in t_lower:
                number = self._extract_issue_number(t)
                if repo and number:
                    cmd = f"gh issue view {number} --repo {shlex.quote(repo)}"
                else:
                    return {"github_error": "Please specify repository and issue number: repo: owner/repo #123"}
            else:
                if repo:
                    cmd = f"gh issue list --repo {shlex.quote(repo)} --state open"
                else:
                    cmd = "gh issue list --state open"

        # Pull requests
        elif "pull request" in t_lower or " pr " in t_lower or t_lower.startswith("pr "):
            repo = self._extract_repo(t)
            if "create" in t_lower or "new" in t_lower:
                if not repo:
                    return {"github_error": "Please specify repository: repo: owner/repo"}
                title = self._extract_title(t)
                if not title:
                    return {"github_error": "Please specify PR title: title: <PR title>"}
                head = self._extract_branch(t, "head")
                base = self._extract_branch(t, "base") or "main"
                if not head:
                    return {"github_error": "Please specify head branch: head: <branch>"}
                cmd = f"gh pr create --repo {shlex.quote(repo)} --title {shlex.quote(title)} --head {shlex.quote(head)} --base {shlex.quote(base)}"
            elif "view" in t_lower or "check" in t_lower:
                number = self._extract_issue_number(t)
                if repo and number:
                    cmd = f"gh pr view {number} --repo {shlex.quote(repo)}"
                else:
                    return {"github_error": "Please specify repository and PR number: repo: owner/repo #123"}
            else:
                if repo:
                    cmd = f"gh pr list --repo {shlex.quote(repo)} --state open"
                else:
                    cmd = "gh pr list --limit 5"

        # CI / Workflow runs
        elif "action" in t_lower or "workflow" in t_lower or "run" in t_lower:
            repo = self._extract_repo(t)
            if not repo:
                return {"github_error": "Please specify repository: repo: owner/repo"}
            run_id = self._extract_run_id(t)
            if run_id:
                cmd = f"gh run view {run_id} --repo {shlex.quote(repo)}"
            else:
                cmd = f"gh run list --repo {shlex.quote(repo)} --limit 10"

        # Default: list repos
        else:
            cmd = "gh repo list --limit 10"

        if cmd:
            result = await run_cmd(cmd)
            if result.get("error"):
                return {
                    "github_error": result.get("stderr", result.get("error")),
                    "github_command": cmd,
                }
            return {
                "github_output": result.get("stdout", ""),
                "github_command": cmd,
                "github_summary": self._format_summary(result.get("stdout", ""), cmd),
            }

        return {"github_error": "Could not understand GitHub request. Try: 'list my repos', 'list issues', 'create issue', etc."}

    def _extract_repo(self, text: str) -> str | None:
        import re
        m = re.search(r'repo[:\s]*([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', text, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r'\b([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\b', text)
        return m.group(1) if m else None

    def _extract_issue_number(self, text: str) -> int | None:
        import re
        m = re.search(r'#(\d+)', text)
        return int(m.group(1)) if m else None

    def _extract_run_id(self, text: str) -> int | None:
        import re
        m = re.search(r'run[:\s]*(\d+)', text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _extract_number(self, text: str, word: str) -> int | None:
        import re
        m = re.search(rf'{word}[:\s]*(\d+)', text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _extract_title(self, text: str) -> str | None:
        import re
        m = re.search(r'title[:\s]+([^\n]+)', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_body(self, text: str) -> str | None:
        import re
        m = re.search(r'body[:\s]+([^\n]+)', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_branch(self, text: str, prefix: str) -> str | None:
        import re
        m = re.search(rf'{prefix}[:\s]+([a-zA-Z0-9_/.-]+)', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _format_summary(self, output: str, cmd: str) -> str:
        lines = [l for l in output.strip().split("\n") if l.strip()]
        if not lines:
            return "No results found."
        cmd_lower = cmd.lower()
        if "issue list" in cmd_lower:
            return f"Found {len(lines)} issues"
        elif "pr list" in cmd_lower:
            return f"Found {len(lines)} pull requests"
        elif "repo list" in cmd_lower:
            return f"Found {len(lines)} repositories"
        elif "run list" in cmd_lower:
            return f"Found {len(lines)} workflow runs"
        return f"Got {len(lines)} results"

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.context_helpers import _get_github_section
        lines = _get_github_section(extra)
        if lines:
            return "\n".join(lines) + "\n"
        return None
