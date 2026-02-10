"""Web search skill: search the web (ddgs multi-backend: bing, brave, duckduckgo, etc.)."""
from __future__ import annotations
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _extract_query(text: str) -> str:
    """Strip boilerplate like 'check the web about', 'search for' to get a cleaner query."""
    t = (text or "").strip()
    for prefix in (
        r"check\s+the\s+web\s+(?:about|for)\s+",
        r"search\s+(?:the\s+web|online)\s+(?:for|about)\s+",
        r"look\s+(?:it\s+)?up\s+(?:for\s+)?",
        r"search\s+for\s+",
        r"look\s+up\s+",
    ):
        t = re.sub(prefix, "", t, flags=re.I)
    return t.strip() or text.strip()


def search_web(query: str, max_results: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    """Search the web; return (results, error). Uses ddgs with backend=auto (multiple engines)."""
    query = _extract_query(query)
    if not query or len(query) > 300:
        return ([], None)
    try:
        from ddgs import DDGS
        raw = DDGS().text(query, max_results=max_results, backend="auto")
        results = []
        for r in (raw or []):
            results.append({
                "title": (r.get("title") or "")[:200],
                "snippet": (r.get("body") or r.get("snippet") or "")[:400],
                "url": (r.get("href") or r.get("url") or "")[:500],
            })
        return (results, None)
    except Exception as e:
        err_msg = str(e)
        logger.warning("Web search failed: %s", e)
        return ([], err_msg)
