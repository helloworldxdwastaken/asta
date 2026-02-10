"""Spotify skill: search tracks (Client Credentials); playback via user OAuth (devices, play)."""
from __future__ import annotations
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTH_URL = "https://accounts.spotify.com/authorize"
SEARCH_URL = "https://api.spotify.com/v1/search"
DEVICES_URL = "https://api.spotify.com/v1/me/player/devices"
PLAY_URL = "https://api.spotify.com/v1/me/player/play"


def _is_music_search(text: str) -> bool:
    """True if the message is likely asking to search for music/songs on Spotify."""
    t = (text or "").strip().lower()
    if not t or len(t) > 150:
        return False
    triggers = (
        "spotify", "search spotify", "find song", "find track", "search song",
        "search music", "find music", "playlist", "on spotify", "in spotify",
    )
    return any(trig in t for trig in triggers)


def _search_query_from_message(text: str) -> str:
    """Extract search query from message (e.g. 'search spotify for X' -> X)."""
    t = (text or "").strip()
    lower = t.lower()
    for prefix in ("search spotify for ", "search spotify ", "find song ", "find track ", "find music ", "search song ", "search music "):
        if lower.startswith(prefix):
            return t[len(prefix) :].strip()
    for mid in (" on spotify", " in spotify"):
        if mid in lower:
            return t[: lower.index(mid)].strip()
    return t


async def get_spotify_token(client_id: str, client_secret: str) -> str | None:
    """Get access token via Client Credentials flow."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        return data.get("access_token")
    except Exception as e:
        logger.warning("Spotify token failed: %s", e)
        return None


async def search_spotify_tracks(query: str, access_token: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search Spotify for tracks; return list of {name, artist, url}."""
    query = (query or "").strip()
    if not query:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                SEARCH_URL,
                params={"q": query, "type": "track", "limit": max_results},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        tracks = data.get("tracks", {}).get("items") or []
        out = []
        for tr in tracks:
            name = tr.get("name") or ""
            artists = [a.get("name") for a in (tr.get("artists") or []) if a.get("name")]
            artist = ", ".join(artists) if artists else ""
            url = (tr.get("external_urls") or {}).get("spotify") or ""
            uri = tr.get("uri") or ""  # e.g. spotify:track:xxx
            if name:
                out.append({"name": name, "artist": artist, "url": url, "uri": uri})
        return out
    except Exception as e:
        logger.warning("Spotify search failed: %s", e)
        return []


async def spotify_search_if_configured(query: str) -> list[dict[str, Any]]:
    """If Spotify credentials are set (Settings UI or env), get token and search; else return []."""
    from app.keys import get_api_key
    cid = (await get_api_key("spotify_client_id")) or ""
    secret = (await get_api_key("spotify_client_secret")) or ""
    cid, secret = cid.strip(), secret.strip()
    if not cid or not secret:
        return []
    token = await get_spotify_token(cid, secret)
    if not token:
        return []
    return await search_spotify_tracks(query, token, 5)


def is_spotify_search_request(text: str) -> bool:
    return _is_music_search(text)


# ----- User OAuth: playback and devices -----

async def get_user_access_token(user_id: str) -> str | None:
    """Get valid access token for user (refresh if expired). Returns None if not connected."""
    from app.db import get_db
    db = get_db()
    await db.connect()
    row = await db.get_spotify_tokens(user_id)
    if not row:
        return None
    refresh_token = row.get("refresh_token")
    access_token = row.get("access_token")
    expires_at = row.get("expires_at") or "0"
    try:
        exp_ts = float(expires_at)
        if time.time() < exp_ts - 60:  # 1 min buffer
            return access_token
    except (TypeError, ValueError):
        pass
    # Refresh
    from app.keys import get_api_key
    cid = (await get_api_key("spotify_client_id")) or ""
    secret = (await get_api_key("spotify_client_secret")) or ""
    cid, secret = cid.strip(), secret.strip()
    if not cid or not secret:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                auth=(cid, secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        new_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        new_exp = str(time.time() + expires_in)
        if new_token:
            await db.set_spotify_tokens(user_id, refresh_token, new_token, new_exp)
            return new_token
        return access_token
    except Exception as e:
        logger.warning("Spotify refresh token failed: %s", e)
        # If refresh token was revoked (400 invalid_grant), clear stored tokens so status shows disconnected
        resp = getattr(e, "response", None)
        if resp is not None and getattr(resp, "status_code", None) == 400:
            try:
                err_body = resp.json()
                if err_body.get("error") == "invalid_grant":
                    await db.clear_spotify_tokens(user_id)
                    return None
            except Exception:
                pass
        return access_token  # try existing


async def list_user_devices(user_id: str) -> list[dict[str, Any]]:
    """List user's Spotify devices. Returns [{id, name, type, is_active}, ...]."""
    token = await get_user_access_token(user_id)
    if not token:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                DEVICES_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        devices = data.get("devices") or []
        return [
            {"id": d.get("id"), "name": d.get("name") or "Unknown", "type": d.get("type") or "Unknown", "is_active": d.get("is_active", False)}
            for d in devices if d.get("id")
        ]
    except Exception as e:
        logger.warning("Spotify list devices failed: %s", e)
        return []


async def start_playback(user_id: str, device_id: str | None, track_uri: str) -> bool:
    """Start playing a track on the given device (or active device if device_id is None)."""
    token = await get_user_access_token(user_id)
    if not token:
        return False
    params = {}
    if device_id:
        params["device_id"] = device_id
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                PLAY_URL + (f"?{urlencode(params)}" if params else ""),
                json={"uris": [track_uri]},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=10.0,
            )
            if r.status_code in (200, 204):
                return True
            logger.warning("Spotify play failed: %s %s", r.status_code, r.text[:200])
            return False
    except Exception as e:
        logger.warning("Spotify play failed: %s", e)
        return False


def is_play_intent(text: str) -> bool:
    """True if user is asking to play something on Spotify (not just search)."""
    t = (text or "").strip().lower()
    if "play" not in t or "spotify" not in t:
        return False
    return any(k in t for k in ("play ", "play something", "play that", "play it"))


def play_query_from_message(text: str) -> str | None:
    """Extract track query for 'play X' or 'play X on Spotify'. Returns None if not a play request."""
    t = (text or "").strip()
    lower = t.lower()
    if "play " not in lower:
        return None
    rest = t
    for prefix in ("play ", "play the ", "play my "):
        if lower.startswith(prefix):
            rest = t[len(prefix) :].strip()
            break
    for suffix in (" on spotify", " in spotify", " on spotify."):
        if rest.lower().endswith(suffix):
            rest = rest[: -len(suffix)].strip()
    # Drop trailing "on spotify" if still there (e.g. "play X on spotify" with different casing)
    if rest.lower().endswith(" on spotify"):
        rest = rest[: -10].strip()
    return rest if rest else None
