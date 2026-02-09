"""Lyrics skill: find song lyrics via LRCLIB (free, no API key)."""
from __future__ import annotations
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)
LRCLIB_SEARCH = "https://lrclib.net/api/search"


def _extract_lyrics_query(text: str) -> str | None:
    """If the message looks like a lyrics/song request, return the search query; else None."""
    t = (text or "").strip()
    if not t or len(t) > 200:
        return None
    lower = t.lower()
    # "lyrics for X", "lyrics of X", "find lyrics X", etc. (at start)
    for prefix in ("lyrics for ", "lyrics of ", "lyrics ", "find lyrics ", "song lyrics ", "lyric ", "get lyrics "):
        if lower.startswith(prefix):
            return t[len(prefix) :].strip()
    # "What are the lyrics of X", "can you get the lyrics of X" (anywhere)
    for phrase in ("lyrics of ", "lyrics for "):
        if phrase in lower:
            idx = lower.index(phrase)
            return t[idx + len(phrase) :].strip()
    # "bohemian rhapsody lyrics" or "shape of you lyric" -> use the part before lyrics
    for suffix in (" lyrics", " lyric"):
        if lower.endswith(suffix):
            return t[: -len(suffix)].strip()
    if " lyrics " in lower:
        idx = lower.index(" lyrics ")
        return (t[:idx] + t[idx + 8 :]).strip()
    if " lyric " in lower:
        idx = lower.index(" lyric ")
        return (t[:idx] + t[idx + 7 :]).strip()
    # Follow-up: "a song by Gigi Perez", "artist Gigi Perez", "by Gigi Perez", "singer X"
    for prefix in ("song by ", "a song by ", "the song by ", "artist ", "singer "):
        if lower.startswith(prefix):
            return t[len(prefix) :].strip()
    if " by " in lower:
        # "something by Gigi Perez" or "by Gigi Perez or something" -> take the part after " by "
        idx = lower.index(" by ")
        after = t[idx + 3 :].strip()
        # drop trailing " or something" / " or similar"
        for suffix in (" or something", " or similar", " or so"):
            if after.lower().endswith(suffix):
                after = after[: -len(suffix)].strip()
            if after.lower().endswith(suffix.rstrip()):
                after = after[: -len(suffix.rstrip())].strip()
        if after and len(after) < 80:
            return after
    return None


async def _search_lrclib(client: httpx.AsyncClient, q: str) -> list[dict] | None:
    """Run LRCLIB search; return list of hits or None."""
    try:
        r = await client.get(
            LRCLIB_SEARCH,
            params={"q": q},
            headers={"User-Agent": "Asta/1.0 (https://github.com/asta-app)"},
        )
        r.raise_for_status()
        data = r.json()
        if not data or not isinstance(data, list):
            return None
        return data
    except Exception as e:
        logger.warning("LRCLIB search %r failed: %s", q, e)
        return None


def _first_with_lyrics(hits: list[dict]) -> dict[str, Any] | None:
    """Return first hit that has plainLyrics."""
    for first in hits:
        plain = (first.get("plainLyrics") or "").strip()
        if plain:
            return {
                "trackName": first.get("trackName") or "",
                "artistName": first.get("artistName") or "",
                "plainLyrics": plain[:8000],
            }
    return None


async def fetch_lyrics(query: str) -> dict[str, Any] | None:
    """Search LRCLIB and return first match with lyrics: {trackName, artistName, plainLyrics}. None if not found."""
    query = (query or "").strip()
    if not query:
        return None
    async with httpx.AsyncClient(timeout=10.0) as client:
        hits = await _search_lrclib(client, query)
        if hits:
            result = _first_with_lyrics(hits)
            if result:
                return result
        # Try alternate order: "Artist Track" and "Track Artist" (LRCLIB often matches better)
        if " by " in query.lower():
            before, _, after = query.lower().partition(" by ")
            before, after = before.strip(), after.strip()
            if before and after:
                for q in (f"{after} {before}", f"{before} {after}"):
                    hits = await _search_lrclib(client, q)
                    if hits:
                        result = _first_with_lyrics(hits)
                        if result:
                            return result
    return None


def is_lyrics_request(text: str) -> bool:
    """True if the message is likely asking for lyrics."""
    return _extract_lyrics_query(text) is not None
