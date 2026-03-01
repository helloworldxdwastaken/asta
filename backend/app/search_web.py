"""Web search: Brave Search API (primary, if key set) → ddgs multi-engine (free fallback)."""
from __future__ import annotations
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ddgs backends to use when falling back — excludes encyclopedias (wikipedia/grokipedia)
# which are useless for real-time web queries.
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


def _brave_api_search(
    query: str,
    api_key: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search via the official Brave Search API (2,000 free queries/month)."""
    import httpx
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": min(max_results, 20)}
    resp = httpx.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for r in (data.get("web", {}).get("results") or []):
        results.append({
            "title": (r.get("title") or "")[:200],
            "snippet": (r.get("description") or "")[:400],
            "url": (r.get("url") or "")[:500],
        })
    return results


def _ddgs_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search via ddgs multi-engine (brave/duckduckgo/google/yahoo scraping — no key needed)."""
    from ddgs import DDGS
    raw = DDGS().text(query, max_results=max_results, backend=_DDGS_BACKENDS)
    results = []
    for r in (raw or []):
        results.append({
            "title": (r.get("title") or "")[:200],
            "snippet": (r.get("body") or r.get("snippet") or "")[:400],
            "url": (r.get("href") or r.get("url") or "")[:500],
        })
    return results


def search_web(
    query: str,
    max_results: int = 5,
    brave_api_key: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Search the web. Returns (results, error).

    Priority:
    1. Brave Search API  — if brave_api_key is set (2,000 free queries/month)
    2. ddgs multi-engine — brave + duckduckgo + google + yahoo scraping (always free)
    """
    query = _extract_query(query)
    if not query or len(query) > 300:
        return ([], None)

    # 1. Brave Search API (most reliable when key configured)
    if brave_api_key:
        try:
            results = _brave_api_search(query, brave_api_key, max_results)
            if results:
                return (results, None)
            logger.debug("Brave API returned 0 results, falling back to ddgs")
        except Exception as e:
            logger.warning("Brave Search API failed (%s), falling back to ddgs", e)

    # 2. ddgs multi-engine fallback
    try:
        results = _ddgs_search(query, max_results)
        return (results, None)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return ([], str(e))
