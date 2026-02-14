from app.lib.skill import Skill
from typing import Any

class FilesSkill(Skill):
    @property
    def name(self) -> str:
        return "files"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        return any(k in t for k in (
            "file", "files", "document", "folder", "path", "directory",
            "save", "write", "create", "store", "put it in",
            "desktop", "allow access", "allow my", "enter my", "check my desktop", "what can i delete",
            "what files", "files i have", "on my desktop", "list my desktop",
        ))

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        from app.config import get_settings
        from app.context_helpers import _get_files_section
        settings = get_settings()
        lines = _get_files_section(settings, extra)
        # Include user's granted paths (OpenClaw-style allowlist) and workspace
        try:
            allowed_db = await db.get_allowed_paths(user_id)
            if allowed_db:
                if not lines:
                    lines = ["--- Local files ---"]
                lines.append("User-granted paths: " + ", ".join(allowed_db[:8]))
            if settings.workspace_path:
                if not lines:
                    lines = ["--- Local files ---"]
                lines.append("Workspace root: " + str(settings.workspace_path))
        except Exception:
            pass
        if lines:
            lines.append("If the user asks for a file or path not in the list above, tell them: open Files, try to open that path, and click 'Grant access' to add it.")
            if settings.workspace_path:
                lines.append("")
                lines.append("To CREATE or SAVE a new file when the user asks (e.g. 'save that to a file', 'create a shopping list'):")
                lines.append("Output the following block with the path (relative to workspace, e.g. shopping-list.md or notes/foo.md) and the exact content:")
                lines.append("[ASTA_WRITE_FILE: path/filename.md]")
                lines.append("content here (markdown or text)")
                lines.append("[/ASTA_WRITE_FILE]")
                lines.append("The file will be created under the workspace. Use a sensible path like shopping-list.md or notes/title.md.")
            return "\n".join(lines) + "\n"
        return None
