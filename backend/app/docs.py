"""Load Asta documentation for self-awareness skill."""
from pathlib import Path


def _asta_root() -> Path:
    """Asta project root (contains backend/, docs/, README.md)."""
    return Path(__file__).resolve().parent.parent.parent


def load_asta_docs() -> str:
    """Load README.md, CHANGELOG.md, and docs/*.md for self-awareness context."""
    root = _asta_root()
    parts = []
    readme = root / "README.md"
    if readme.is_file():
        try:
            parts.append(f"## README.md\n{readme.read_text(encoding='utf-8')}")
        except Exception:
            pass
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        try:
            parts.append(f"## CHANGELOG.md\n{changelog.read_text(encoding='utf-8')}")
        except Exception:
            pass
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for f in sorted(docs_dir.glob("*.md")):
            try:
                parts.append(f"## {f.name}\n{f.read_text(encoding='utf-8')}")
            except Exception:
                continue
    return "\n\n".join(parts) if parts else ""
