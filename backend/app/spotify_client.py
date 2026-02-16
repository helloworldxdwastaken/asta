"""Spotify skill: search tracks (Client Credentials); playback via user OAuth (devices, play)."""
from __future__ import annotations
import logging
import re
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
NEXT_URL = "https://api.spotify.com/v1/me/player/next"
VOLUME_URL = "https://api.spotify.com/v1/me/player/volume"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
PLAYLISTS_URL = "https://api.spotify.com/v1/me/playlists"


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


def _search_query_from_message(text: str) -> str | None:
    """Extract search query from message (e.g. 'search spotify for X' -> X). Returns None if no explicit Spotify/search intent."""
    t = (text or "").strip()
    lower = t.lower()
    for prefix in ("search spotify for ", "search spotify ", "find song ", "find track ", "find music ", "search song ", "search music "):
        if lower.startswith(prefix):
            q = t[len(prefix) :].strip()
            return q if q else None
    for mid in (" on spotify", " in spotify"):
        if mid in lower:
            q = t[: lower.index(mid)].strip()
            return q if q else None
    return None


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


async def search_spotify_artists(query: str, access_token: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Search Spotify for artists; return list of {name, uri}."""
    query = (query or "").strip()
    if not query:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                SEARCH_URL,
                params={"q": query, "type": "artist", "limit": max_results},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        artists = data.get("artists", {}).get("items") or []
        return [{"name": a.get("name") or "", "uri": a.get("uri") or ""} for a in artists if a.get("uri")]
    except Exception as e:
        logger.warning("Spotify artist search failed: %s", e)
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


async def start_playback(user_id: str, device_id: str | None, track_uri: str | None = None, context_uri: str | None = None) -> bool:
    """Start playback on the given device (or active device).

    - If context_uri is set (e.g. playlist/album URI), Spotify will play that context.
    - Else, if track_uri is set, it plays that single track.
    """
    token = await get_user_access_token(user_id)
    if not token:
        return False
    if not context_uri and not track_uri:
        return False
    params = {}
    if device_id:
        params["device_id"] = device_id
    try:
        async with httpx.AsyncClient() as client:
            body: dict[str, Any] = {}
            if context_uri:
                body["context_uri"] = context_uri
            elif track_uri:
                body["uris"] = [track_uri]
            r = await client.put(
                PLAY_URL + (f"?{urlencode(params)}" if params else ""),
                json=body,
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
    """Extract track query for 'play X' or 'play X on Spotify'. Returns None if not a play request.
    Requires message to START with play intent (avoids 'remind me to play guitar' etc)."""
    t = (text or "").strip()
    lower = t.lower()
    rest = None
    for prefix in ("play ", "play the ", "play my ", "hey play ", "ok play ", "please play "):
        if lower.startswith(prefix):
            rest = t[len(prefix) :].strip()
            break
    if rest is None:
        return None
    for suffix in (" on spotify", " in spotify", " on spotify."):
        if rest.lower().endswith(suffix):
            rest = rest[: -len(suffix)].strip()
    if rest.lower().endswith(" on spotify"):
        rest = rest[: -10].strip()
    return rest if rest else None


def extract_playlist_uri(text: str) -> str | None:
    """Extract a Spotify playlist URI from text (spotify:playlist:ID or https://open.spotify.com/playlist/ID...)."""
    t = (text or "").strip()
    lower = t.lower()
    if "spotify.com/playlist/" in lower:
        start = lower.index("spotify.com/playlist/") + len("spotify.com/playlist/")
        end = start
        while end < len(lower) and lower[end] not in ("?", " ", "\n", "\t"):
            end += 1
        playlist_id = lower[start:end]
        if playlist_id:
            return f"spotify:playlist:{playlist_id}"
    if "spotify:playlist:" in lower:
        start = lower.index("spotify:playlist:") + len("spotify:playlist:")
        end = start
        while end < len(lower) and lower[end] not in ("?", " ", "\n", "\t"):
            end += 1
        playlist_id = lower[start:end]
        if playlist_id:
            return f"spotify:playlist:{playlist_id}"
    return None


def playlist_name_from_message(text: str) -> str | None:
    """Extract playlist name from phrases like 'play my playlist latino'."""
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.match(
        r"^\s*(?:hey\s+|ok\s+|okay\s+|please\s+)?play\s+(?:my\s+|the\s+)?playlist\s+(.+?)\s*$",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    name = (m.group(1) or "").strip()
    for suffix in (" on spotify", " in spotify", " on spotify.", " in spotify."):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name or None


def _normalize_playlist_match(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def find_playlist_uri_by_name(query: str, playlists: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Find best playlist URI by exact/substr match (case/punct-insensitive)."""
    qn = _normalize_playlist_match(query)
    if not qn:
        return None, None
    for p in playlists:
        name = str(p.get("name") or "")
        if _normalize_playlist_match(name) == qn:
            return str(p.get("uri") or "") or None, name
    for p in playlists:
        name = str(p.get("name") or "")
        if qn in _normalize_playlist_match(name):
            return str(p.get("uri") or "") or None, name
    return None, None


async def list_user_playlists(user_id: str, max_results: int = 50) -> list[dict[str, Any]]:
    """List user playlists. Returns [{name, uri, owner, tracks_total}, ...]."""
    token = await get_user_access_token(user_id)
    if not token:
        return []
    limit = max(1, min(int(max_results or 50), 50))
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                PLAYLISTS_URL,
                params={"limit": limit},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        items = data.get("items") or []
        out: list[dict[str, Any]] = []
        for item in items:
            uri = (item.get("uri") or "").strip()
            if not uri:
                continue
            out.append(
                {
                    "name": (item.get("name") or "").strip(),
                    "uri": uri,
                    "owner": ((item.get("owner") or {}).get("display_name") or "").strip(),
                    "tracks_total": int(((item.get("tracks") or {}).get("total") or 0)),
                }
            )
        return out
    except Exception as e:
        logger.warning("Spotify list playlists failed: %s", e)
        return []


async def get_currently_playing(user_id: str) -> dict[str, Any] | None:
    """Get currently playing track metadata for the user.

    Returns None when user is not connected or request fails.
    Returns {"is_playing": bool, "track": str|None, "artist": str|None, "album": str|None}.
    """
    token = await get_user_access_token(user_id)
    if not token:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                CURRENTLY_PLAYING_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if r.status_code == 204:
                return {"is_playing": False, "track": None, "artist": None, "album": None}
            r.raise_for_status()
            data = r.json()
        item = data.get("item") if isinstance(data, dict) else None
        if not item:
            return {"is_playing": bool(data.get("is_playing")) if isinstance(data, dict) else False, "track": None, "artist": None, "album": None}
        artists = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]
        artist = ", ".join(artists) if artists else None
        return {
            "is_playing": bool(data.get("is_playing")),
            "track": (item.get("name") or None),
            "artist": artist,
            "album": ((item.get("album") or {}).get("name") or None),
        }
    except Exception as e:
        logger.warning("Spotify currently playing failed: %s", e)
        return None


def parse_volume_percent(text: str) -> int | None:
    """Parse volume percentage from text like 'set volume to 30%', 'volume 50'."""
    import re

    nums = re.findall(r"\b(\d{1,3})\b", text or "")
    if not nums:
        return None
    try:
        val = int(nums[0])
    except ValueError:
        return None
    if val < 0:
        val = 0
    if val > 100:
        val = 100
    return val


async def skip_next_track(user_id: str) -> bool:
    """Skip to the next track on the active device."""
    token = await get_user_access_token(user_id)
    if not token:
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                NEXT_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if r.status_code in (200, 204):
                return True
            logger.warning("Spotify skip failed: %s %s", r.status_code, r.text[:200])
            return False
    except Exception as e:
        logger.warning("Spotify skip failed: %s", e)
        return False


async def set_volume_percent(user_id: str, volume_percent: int) -> bool:
    """Set playback volume (0–100) on the active device."""
    token = await get_user_access_token(user_id)
    if not token:
        return False
    if volume_percent < 0:
        volume_percent = 0
    if volume_percent > 100:
        volume_percent = 100
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                VOLUME_URL + f"?{urlencode({'volume_percent': volume_percent})}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if r.status_code in (200, 204):
                return True
            logger.warning("Spotify volume failed: %s %s", r.status_code, r.text[:200])
            return False
    except Exception as e:
        logger.warning("Spotify volume failed: %s", e)
        return False
