from app.docs import load_asta_docs
from app.routers.files import _asta_docs, ASTA_KNOWLEDGE


def test_load_asta_docs_includes_changelog_section():
    docs = load_asta_docs()
    assert "## CHANGELOG.md" in docs


def test_asta_knowledge_virtual_root_includes_changelog():
    docs = _asta_docs()
    paths = {path for _, path in docs}
    assert f"{ASTA_KNOWLEDGE}/CHANGELOG.md" in paths
