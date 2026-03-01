import json

import pytest

from app.config import get_settings
from app.openclaw_compat_tools import (
    parse_openclaw_compat_args,
    run_memory_get_compat,
    run_memory_search_compat,
    run_web_fetch_compat,
    run_web_search_compat,
)


@pytest.fixture
def workspace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTA_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_parse_openclaw_compat_args_aliases():
    out = parse_openclaw_compat_args(
        {
            "max_chars": 120,
            "max_results": 4,
            "min_score": "0.5",
        }
    )
    assert out["maxChars"] == 120
    assert out["maxResults"] == 4
    assert out["minScore"] == "0.5"


@pytest.mark.asyncio
async def test_web_search_compat_returns_structured_payload(monkeypatch):
    def _fake_search_web(query: str, max_results: int = 5, brave_api_key: str | None = None):
        assert query == "test query"
        assert max_results == 3
        return (
            [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "snippet": "Example snippet",
                }
            ],
            None,
        )

    monkeypatch.setattr("app.openclaw_compat_tools.search_web", _fake_search_web)
    raw = await run_web_search_compat({"query": "test query", "count": 3})
    payload = json.loads(raw)
    assert payload["query"] == "test query"
    assert payload["count"] == 1
    assert payload["results"][0]["description"] == "Example snippet"


@pytest.mark.asyncio
async def test_web_fetch_compat_blocks_private_host():
    raw = await run_web_fetch_compat({"url": "http://127.0.0.1:8080/"})
    payload = json.loads(raw)
    assert "error" in payload
    assert "Blocked URL host" in payload["error"]


@pytest.mark.asyncio
async def test_memory_search_and_get_compat(workspace_env):
    (workspace_env / "USER.md").write_text(
        "# USER.md\n\n- **Location:** Test City\n- Likes: matcha tea\n",
        encoding="utf-8",
    )
    mem_dir = workspace_env / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "notes.md").write_text(
        "Project A decision: use adapter layer.\nKeep compatibility tests green.\n",
        encoding="utf-8",
    )

    search_raw = await run_memory_search_compat({"query": "adapter layer", "maxResults": 5}, user_id="default")
    search_payload = json.loads(search_raw)
    assert isinstance(search_payload.get("results"), list)
    assert any(r.get("path") in ("memory/notes.md", "USER.md") for r in search_payload["results"])

    get_raw = await run_memory_get_compat({"path": "memory/notes.md", "from": 1, "lines": 1})
    get_payload = json.loads(get_raw)
    assert get_payload["path"] == "memory/notes.md"
    assert "Project A decision" in get_payload["text"]


@pytest.mark.asyncio
async def test_memory_search_fast_mode_avoids_rag_when_workspace_hit(monkeypatch, workspace_env):
    (workspace_env / "USER.md").write_text("Likes: matcha tea\n", encoding="utf-8")

    def _boom_get_rag():
        raise AssertionError("RAG should not be called in search mode when local hit exists")

    monkeypatch.setattr("app.rag.service.get_rag", _boom_get_rag, raising=False)

    raw = await run_memory_search_compat({"query": "matcha", "mode": "search", "maxResults": 5}, user_id="default")
    payload = json.loads(raw)
    assert payload["mode"] == "search"
    assert payload["fallback_used"] is False
    assert any(r.get("source") == "memory" for r in payload.get("results", []))
