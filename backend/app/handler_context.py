"""Extracted context-building and agent-filtering helpers from handler.py."""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _append_selected_agent_context(context: str, extra: dict) -> str:
    selected = extra.get("selected_agent") if isinstance(extra, dict) else None
    if not isinstance(selected, dict):
        return context

    aid = str(selected.get("id") or "").strip()
    name = str(selected.get("name") or "").strip() or aid or "agent"
    desc = str(selected.get("description") or "").strip()
    agent_prompt = str(selected.get("system_prompt") or "").strip()

    sections: list[str] = []
    sections.append("[SELECTED AGENT]")
    sections.append(f"You are currently routed to agent '{name}' (id: {aid or 'unknown'}).")
    if desc:
        sections.append(f"Agent description: {desc}")
    skills = selected.get("skills")
    if isinstance(skills, list):
        normalized = [str(s).strip() for s in skills if str(s).strip()]
        if normalized:
            sections.append(f"Allowed skills for this agent: {', '.join(normalized)}")
        else:
            sections.append("Allowed skills for this agent: (none)")
    sections.append(
        "Follow this agent's intent and style for this turn, while still obeying higher-priority safety/policy instructions."
    )
    if agent_prompt:
        sections.append("")
        sections.append("[AGENT PROMPT]")
        sections.append(agent_prompt)

    # Reliability boost: if this agent is constrained to exactly one workspace
    # skill, preload that SKILL.md so the model does not skip/forget to read it.
    # This is especially important for API-heavy skills (e.g. Notion) where small
    # command mistakes lead to false negatives.
    skills_for_agent = selected.get("skills")
    if isinstance(skills_for_agent, list):
        normalized_skill_ids: list[str] = []
        seen_skill_ids: set[str] = set()
        for item in skills_for_agent:
            sid = str(item).strip().lower()
            if not sid or sid in seen_skill_ids:
                continue
            seen_skill_ids.add(sid)
            normalized_skill_ids.append(sid)
        if len(normalized_skill_ids) == 1:
            try:
                from app.workspace import discover_workspace_skills

                target_skill_id = normalized_skill_ids[0]
                resolved = next(
                    (s for s in discover_workspace_skills() if str(s.name).strip().lower() == target_skill_id),
                    None,
                )
                if resolved and resolved.file_path.is_file():
                    raw_skill = resolved.file_path.read_text(encoding="utf-8", errors="replace").strip()
                    if raw_skill:
                        # Safety cap to avoid unbounded prompt growth from unusually large skill files.
                        max_chars = 12000
                        if len(raw_skill) > max_chars:
                            raw_skill = raw_skill[:max_chars].rstrip() + "\n\n[TRUNCATED FOR CONTEXT SIZE]"
                        sections.append("")
                        sections.append("[AGENT SKILL DIRECTIVES]")
                        sections.append(
                            f"Preloaded allowed skill '{target_skill_id}' from {resolved.file_path}. "
                            "Follow these instructions exactly for this turn."
                        )
                        sections.append("")
                        sections.append(raw_skill)
            except Exception as e:
                logger.warning("Could not preload selected agent skill context: %s", e)

    snippets = extra.get("agent_knowledge_snippets") if isinstance(extra, dict) else None
    if isinstance(snippets, list) and snippets:
        sections.append("")
        sections.append("[AGENT KNOWLEDGE SNIPPETS]")
        sections.append(
            "These were retrieved from the agent's local knowledge folder. Prefer them when relevant."
        )
        for idx, item in enumerate(snippets[:6], start=1):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "unknown")
            line_start = int(item.get("line_start") or 0)
            line_end = int(item.get("line_end") or 0)
            excerpt = str(item.get("snippet") or "").strip()
            if not excerpt:
                continue
            sections.append(f"{idx}. Source: {source}:{line_start}-{line_end}")
            sections.append(excerpt)
            sections.append("")

    payload = "\n".join(sections).strip()
    if not payload:
        return context
    return context + "\n\n" + payload


def _selected_agent_skill_filter(extra: dict) -> list[str] | None:
    selected = extra.get("selected_agent") if isinstance(extra, dict) else None
    if not isinstance(selected, dict):
        return None
    raw = selected.get("skills")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        sid = str(item).strip().lower()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        normalized.append(sid)
    return normalized


_PROJECT_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent / "workspace"
_PROJECT_MD_TEMPLATE = """# Project Context

_Auto-maintained by Asta. Last updated: {ts}_

## Summary
[What this project is about]

## Key Decisions
- [decisions made]

## Status
[current status]

## Notes
- [other important info]
"""


async def _run_project_update_tool(args: Any, conversation_id: str, db: Any) -> str:
    """Execute the project_update tool: read/append/replace_section on project.md."""
    if not isinstance(args, dict):
        return "Error: invalid arguments."
    action = str(args.get("action") or "read").strip()
    folder_id = await db.get_conversation_folder_id(conversation_id)
    if not folder_id:
        return "Error: this conversation does not belong to a project folder."
    project_dir = _PROJECT_WORKSPACE_ROOT / "projects" / folder_id
    project_dir.mkdir(parents=True, exist_ok=True)
    project_md = project_dir / "project.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    if action == "read":
        if not project_md.exists():
            return "(project.md is empty — no context yet)"
        return project_md.read_text(encoding="utf-8")
    elif action == "append":
        content = str(args.get("content") or "").strip()
        if not content:
            return "Error: content is required for append."
        if not project_md.exists():
            project_md.write_text(_PROJECT_MD_TEMPLATE.format(ts=ts), encoding="utf-8")
        existing = project_md.read_text(encoding="utf-8")
        # Update the "Last updated" timestamp
        import re as _re
        existing = _re.sub(r"_Auto-maintained by Asta\. Last updated: [^_]+_", f"_Auto-maintained by Asta. Last updated: {ts}_", existing)
        entry = f"\n- [{ts}] {content}"
        # Append to Notes section if it exists, else add at end
        if "## Notes" in existing:
            existing = existing.rstrip() + entry + "\n"
        else:
            existing = existing.rstrip() + "\n\n## Notes\n" + entry + "\n"
        project_md.write_text(existing, encoding="utf-8")
        return f"Appended to project.md."
    elif action == "replace_section":
        section = str(args.get("section") or "").strip()
        content = str(args.get("content") or "").strip()
        if not section:
            return "Error: section is required for replace_section."
        if not project_md.exists():
            project_md.write_text(_PROJECT_MD_TEMPLATE.format(ts=ts), encoding="utf-8")
        existing = project_md.read_text(encoding="utf-8")
        import re as _re
        # Update timestamp
        existing = _re.sub(r"_Auto-maintained by Asta\. Last updated: [^_]+_", f"_Auto-maintained by Asta. Last updated: {ts}_", existing)
        header = f"## {section}"
        # Find the section and replace its content
        section_pattern = _re.compile(
            rf"(^## {_re.escape(section)}\s*\n)(.*?)(?=^## |\Z)",
            _re.MULTILINE | _re.DOTALL,
        )
        replacement = f"## {section}\n{content}\n\n"
        if section_pattern.search(existing):
            existing = section_pattern.sub(replacement, existing)
        else:
            # Section doesn't exist, append it
            existing = existing.rstrip() + f"\n\n## {section}\n{content}\n"
        project_md.write_text(existing, encoding="utf-8")
        return f"Updated section '{section}' in project.md."
    else:
        return f"Error: unknown action '{action}'."
