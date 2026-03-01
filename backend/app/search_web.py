"""Web search via ddgs multi-engine (brave, duckduckgo, google, yahoo — no API key needed)."""
from __future__ import annotations
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Explicit backends — excludes encyclopedias (wikipedia/grokipedia) from web search
_DDGS_BACKENDS = "brave,duckduckgo,google,yahoo"


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
    """Search the web using ddgs (brave + duckduckgo + google + yahoo). No API key needed."""
    query = _extract_query(query)
    if not query or len(query) > 300:
        return ([], None)
    try:
        from ddgs import DDGS
        raw = DDGS().text(query, max_results=max_results, backend=_DDGS_BACKENDS)
        results = []
        for r in (raw or []):
            results.append({
                "title": (r.get("title") or "")[:200],
                "snippet": (r.get("body") or r.get("snippet") or "")[:400],
                "url": (r.get("href") or r.get("url") or "")[:500],
            })
        return (results, None)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return ([], str(e))
