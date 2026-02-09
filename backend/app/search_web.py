"""Web search skill: search the web (DuckDuckGo, no API key)."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the web; return list of {title, snippet, url}. Empty list on error."""
    query = (query or "").strip()
    if not query or len(query) > 300:
        return []
    try:
        from duckduckgo_search import DDGS
        results = []
        for r in DDGS().text(query, max_results=max_results):
            results.append({
                "title": (r.get("title") or "")[:200],
                "snippet": (r.get("body") or "")[:400],
                "url": (r.get("href") or "")[:500],
            })
        return results
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return []
