import asyncio
import os
from app.lib.skill import Skill
from typing import Any
from app.config import get_settings


async def run_cmd(cmd: str) -> dict[str, Any]:
    """Run a shell command and return stdout/stderr."""
    parts = cmd.split()
    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    # gh outputs to both stdout and stderr - combine them
    combined = stdout.decode().strip() or stderr.decode().strip()
    return {
        "stdout": combined,
        "stderr": stderr.decode().strip(),
        "error": None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        "returncode": proc.returncode
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
            "gh ", "gh issue", "gh pr", "gh run",
        ))
    
    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Execute GitHub operations via gh CLI."""
        settings = get_settings()
        
        # Check if gh is available
        check = await run_cmd("which gh")
        if check.get("error") or not check.get("stdout"):
            return {
                "github_error": "GitHub CLI (`gh`) not installed. Install with: brew install gh",
                "github_needs_cli": True
            }
        
        # Check if authenticated
        auth_check = await run_cmd("gh auth status")
        if auth_check.get("error") or "not logged in" in auth_check.get("stderr", "").lower():
            return {
                "github_error": "GitHub not authenticated. Run: gh auth login",
                "github_needs_auth": True,
                "github_auth_instructions": "1. Run: gh auth login\n2. Select GitHub.com\n3. Select HTTPS\n4. Login with web browser\n5. Authorize gh"
            }
        
        t = (text or "").strip()
        
        # Parse common patterns
        cmd = None
        args = []
        
        t_lower = t.lower()
        
        # List repos
        if ("list" in t_lower or "my" in t_lower) and "repo" in t_lower:
            cmd = "gh repo list"
            # Get limit
            limit_match = self._extract_number(t, "limit")
            if limit_match:
                args = ["--limit", str(limit_match)]
            else:
                args = ["--limit", "10"]
        
        # List issues
        elif "issue" in t_lower:
            if "list" in t_lower or "all" in t_lower:
                # Extract repo if mentioned
                repo = self._extract_repo(t)
                if repo:
                    cmd = f"gh issue list --repo {repo}"
                else:
                    cmd = "gh issue list"
                args = ["--state", "open"]
            elif "create" in t_lower or "new" in t_lower:
                repo = self._extract_repo(t)
                if not repo:
                    return {"github_error": "Please specify repository: repo: owner/repo"}
                title = self._extract_title(t)
                if not title:
                    return {"github_error": "Please specify issue title: title: <issue title>"}
                cmd = f"gh issue create --repo {repo} --title \"{title}\""
                # Add body if mentioned
                body = self._extract_body(t)
                if body:
                    cmd += f" --body \"{body}\""
            else:
                # View specific issue
                repo = self._extract_repo(t)
                number = self._extract_issue_number(t)
                if repo and number:
                    cmd = f"gh issue view {number} --repo {repo}"
                else:
                    return {"github_error": "Please specify repository and issue number: repo: owner/repo issue: #123"}
        
        # Pull requests
        elif "pull request" in t_lower or " pr " in t_lower:
            if "list" in t_lower or "all" in t_lower:
                repo = self._extract_repo(t)
                if not repo:
                    return {"github_error": "Please specify repository: repo: owner/repo"}
                cmd = f"gh pr list --repo {repo}"
                args = ["--state", "open"]
            elif "create" in t_lower or "new" in t_lower:
                repo = self._extract_repo(t)
                if not repo:
                    return {"github_error": "Please specify repository: repo: owner/repo"}
                title = self._extract_title(t)
                if not title:
                    return {"github_error": "Please specify PR title: title: <PR title>"}
                head = self._extract_branch(t, "head")
                base = self._extract_branch(t, "base") or "main"
                if not head:
                    return {"github_error": "Please specify head branch: head: <branch>"}
                cmd = f"gh pr create --repo {repo} --title \"{title}\" --head {head} --base {base}"
            elif "view" in t_lower or "check" in t_lower:
                repo = self._extract_repo(t)
                number = self._extract_issue_number(t)
                if repo and number:
                    cmd = f"gh pr view {number} --repo {repo}"
                else:
                    return {"github_error": "Please specify repository and PR number: repo: owner/repo pr: #123"}
            else:
                repo = self._extract_repo(t)
                if repo:
                    cmd = f"gh pr list --repo {repo}"
                else:
                    cmd = "gh pr list --limit 5"
        
        # CI / Workflow runs
        elif "action" in t_lower or "workflow" in t_lower or "run" in t_lower:
            repo = self._extract_repo(t)
            if not repo:
                return {"github_error": "Please specify repository: repo: owner/repo"}
            if "list" in t_lower or "all" in t_lower:
                cmd = f"gh run list --repo {repo}"
                args = ["--limit", "10"]
            else:
                # View specific run
                run_id = self._extract_run_id(t)
                if run_id:
                    cmd = f"gh run view {run_id} --repo {repo}"
                else:
                    cmd = f"gh run list --repo {repo}"
                    args = ["--limit", "5"]
        
        # Commits
        elif "commit" in t_lower:
            repo = self._extract_repo(t)
            if not repo:
                return {"github_error": "Please specify repository: repo: owner/repo"}
            cmd = f"gh api repos/{repo}/commits"
            args = ["--method", "GET", "--paginate"]
        
        # Branches
        elif "branch" in t_lower:
            repo = self._extract_repo(t)
            if not repo:
                return {"github_error": "Please specify repository: repo: owner/repo"}
            if "list" in t_lower or "all" in t_lower:
                cmd = f"gh repo view {repo} --json defaultBranchRef"
            else:
                branch = self._extract_branch(t, "branch")
                if branch:
                    cmd = f"gh api repos/{repo}/branches/{branch}"
                else:
                    cmd = f"gh api repos/{repo}/branches"
        
        # Status / Rate limit
        elif "status" in t_lower:
            cmd = "gh api rate_limit"
        
        # Default: list repos
        else:
            cmd = "gh repo list"
            args = ["--limit", "10"]
        
        # Execute
        if cmd:
            full_cmd = cmd + " " + " ".join(args) if args else cmd
            result = await run_cmd(full_cmd)
            
            if result.get("error"):
                return {
                    "github_error": result.get("stderr", result.get("error")),
                    "github_command": full_cmd
                }
            
            output = result.get("stdout", "")
            
            # Format output based on command type
            return {
                "github_output": output,
                "github_command": full_cmd,
                "github_summary": self._format_summary(output, cmd)
            }
        
        return {"github_error": "Could not understand GitHub request. Try: 'list my repos', 'list issues', 'create issue', etc."}
    
    def _extract_repo(self, text: str) -> str | None:
        import re
        match = re.search(r'repo[:\s]*([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)', text)
        return match.group(1) if match else None
    
    def _extract_issue_number(self, text: str) -> int | None:
        import re
        match = re.search(r'#(\d+)', text)
        return int(match.group(1)) if match else None
    
    def _extract_run_id(self, text: str) -> int | None:
        import re
        match = re.search(r'run[:\s]*(\d+)', text, re.IGNORECASE)
        return int(match.group(1)) if match else None
    
    def _extract_number(self, text: str, word: str) -> int | None:
        import re
        match = re.search(rf'{word}[:\s]*(\d+)', text, re.IGNORECASE)
        return int(match.group(1)) if match else None
    
    def _extract_title(self, text: str) -> str | None:
        import re
        match = re.search(r'title[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_body(self, text: str) -> str | None:
        import re
        match = re.search(r'body[:\s]+([^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_branch(self, text: str, prefix: str) -> str | None:
        import re
        match = re.search(rf'{prefix}[:\s]+([a-zA-Z0-9_-]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _format_summary(self, output: str, cmd: str) -> str:
        lines = output.strip().split("\n")
        if not lines or not lines[0]:
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
