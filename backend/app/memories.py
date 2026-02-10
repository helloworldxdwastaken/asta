"""User memories: User.md file with place, preferred name, max 10 important facts."""
from __future__ import annotations
import os
import re
from pathlib import Path

MAX_FACTS = 10


def _data_dir() -> Path:
    """Asta data directory (for User.md)."""
    root = Path(__file__).resolve().parent.parent.parent
    data = root / "data"
    data.mkdir(exist_ok=True)
    return data


def _user_md_path(user_id: str) -> Path:
    """Path to User.md for the given user."""
    data = _data_dir()
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "._-") or "default"
    if safe_id == "default":
        return data / "User.md"
    user_dir = data / "users" / safe_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "User.md"


def load_user_memories(user_id: str) -> str:
    """Load User.md content. Returns empty string if file doesn't exist."""
    p = _user_md_path(user_id)
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def save_user_memories(user_id: str, content: str) -> None:
    """Save User.md content."""
    p = _user_md_path(user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")


def _parse_memories(content: str) -> dict[str, str | list[str]]:
    """Parse User.md into structured dict. Keys: location, preferred_name, important (list, max 10)."""
    out: dict[str, str | list[str]] = {"location": "", "preferred_name": "", "important": []}
    if not content.strip():
        return out
    important: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^-\s*\*\*(.+?)\*\*:\s*(.+)$", line)
        if m:
            key, val = m.group(1).strip().lower(), m.group(2).strip()
            if "location" in key:
                out["location"] = val
            elif "name" in key or "preferred" in key:
                out["preferred_name"] = val
            elif "important" in key:
                pass  # section header
            else:
                important.append(val)
        elif line.startswith("- ") and not line.startswith("- **"):
            important.append(line[2:].strip())
    out["important"] = important[:MAX_FACTS]
    return out


def _format_memories(data: dict[str, str | list[str]]) -> str:
    """Format structured dict back to User.md markdown."""
    lines = ["# About you", ""]
    if data.get("location"):
        lines.append(f"- **Location:** {data['location']}")
    if data.get("preferred_name"):
        lines.append(f"- **Preferred name:** {data['preferred_name']}")
    important = data.get("important") or []
    if important:
        lines.append("- **Important:**")
        for item in important[:MAX_FACTS]:
            if isinstance(item, str) and item.strip():
                lines.append(f"  - {item.strip()}")
    return "\n".join(lines).strip() + "\n"


def add_memory(user_id: str, key: str, value: str) -> bool:
    """Add or update one memory. Key can be 'location', 'preferred_name', or an important fact.
    Enforces max 10 important facts. Returns True if updated."""
    key = key.strip().lower()
    value = value.strip()
    if not value:
        return False
    content = load_user_memories(user_id)
    data = _parse_memories(content)
    if key in ("location", "place", "where"):
        data["location"] = value
    elif key in ("name", "preferred_name", "call me"):
        data["preferred_name"] = value
    else:
        # Important fact: add or update, cap at MAX_FACTS
        facts = list(data.get("important") or [])
        # Replace if similar key already exists
        for i, f in enumerate(facts):
            if f.startswith(f"{key}:"):
                facts[i] = f"{key}: {value}"
                data["important"] = facts
                save_user_memories(user_id, _format_memories(data))
                return True
        facts.append(f"{key}: {value}")
        data["important"] = facts[-MAX_FACTS:]
    save_user_memories(user_id, _format_memories(data))
    return True


def parse_save_instructions(reply: str) -> list[tuple[str, str]]:
    """Extract [SAVE: key: value] from AI reply. Returns list of (key, value)."""
    out: list[tuple[str, str]] = []
    pattern = re.compile(r"\[SAVE:\s*([^:\]]+)\s*:\s*([^\]]+)\]", re.IGNORECASE)
    for m in pattern.finditer(reply):
        k, v = m.group(1).strip(), m.group(2).strip()
        if k and v:
            out.append((k, v))
    return out


def strip_save_instructions(reply: str) -> str:
    """Remove [SAVE: key: value] from reply before showing user."""
    return re.sub(r"\[SAVE:\s*[^:\]]+\s*:\s*[^\]]+\]\s*", "", reply, flags=re.IGNORECASE).strip()
