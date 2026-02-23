import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from app.db import get_db
from app.spotify_client import (
    start_playback,
    skip_next_track,
    set_volume_percent,
    list_user_devices,
    get_user_access_token,
    get_currently_playing,
    list_user_playlists,
    find_playlist_uri_by_name,
    extract_playlist_uri,
    playlist_name_from_message,
    play_query_from_message,
    spotify_search_if_configured,
    search_spotify_artists,
    _search_query_from_message,
    _is_music_search,
    parse_volume_percent,
)

logger = logging.getLogger(__name__)

# Retry request expires after this many seconds (so "Done" only retries recent failures)
SPOTIFY_RETRY_MAX_AGE_SECONDS = 300

# ---- NEW: Config for enhanced features ----
CACHE_TTL_SECONDS = 10 * 60  # 10 minutes
PLAYLIST_MATCH_THRESHOLD = 80
RECOMMENDATIONS_TO_QUEUE = 12
PREFER_ALBUM_CONTEXT_FOR_TRACKS = True


# ---- NEW: Simple TTL cache ----
class _TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        exp, val = item
        if time.time() > exp:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, val: Any, ttl: int = CACHE_TTL_SECONDS) -> None:
        self._store[key] = (time.time() + ttl, val)


_spotify_cache = _TTLCache()


# ---- NEW: Intent parsing ----
_SPOTIFY_WORD = re.compile(r"\bspotify\b", re.IGNORECASE)
_CONTROL_PAT = re.compile(r"\b(pause|resume|skip|next|previous|back|shuffle|repeat|queue|volume)\b", re.IGNORECASE)
_PLAYLIST_PAT = re.compile(r"\bplay\s+(?:my\s+)?playlist\s+(?P<q>.+)$", re.IGNORECASE)
_PLAY_PAT = re.compile(r"\bplay\s+(?P<q>.+)$", re.IGNORECASE)


class Intent:
    def __init__(self, kind: str, query: str | None = None, confidence: float = 0.0, raw: str = ""):
        self.kind = kind
        self.query = query
        self.confidence = confidence
        self.raw = raw


def _parse_intent(text: str) -> Intent | None:
    """Parse user text into Spotify intent with confidence score."""
    t = (text or "").strip()
    if not t:
        return None

    t_lower = t.lower()

    # Control commands
    if _CONTROL_PAT.search(t):
        conf = 0.70 + (0.20 if _SPOTIFY_WORD.search(t) else 0.0)
        return Intent(kind="control", query=t, confidence=conf, raw=t)

    # Playlist commands
    m = _PLAYLIST_PAT.search(t)
    if m:
        return Intent(kind="playlist", query=m.group("q").strip(), confidence=0.92, raw=t)

    # Play something
    m = _PLAY_PAT.search(t)
    if m:
        q = m.group("q").strip()
        # Avoid false positives
        if re.search(r"\b(with|around|along|nice)\b", q, re.IGNORECASE) and not _SPOTIFY_WORD.search(t):
            return None
        conf = 0.65 + (0.20 if _SPOTIFY_WORD.search(t) else 0.0)
        return Intent(kind="track", query=q, confidence=conf, raw=t)

    # Spotify mention without play
    if _SPOTIFY_WORD.search(t):
        return Intent(kind="search", query=t, confidence=0.60, raw=t)

    return None


# ---- NEW: Similarity scoring ----
def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _similarity(a: str, b: str) -> int:
    """Simple similarity 0-100."""
    a_n = _norm(a)
    b_n = _norm(b)
    if not a_n or not b_n:
        return 0
    try:
        from rapidfuzz import fuzz
        return int(fuzz.token_set_ratio(a_n, b_n))
    except Exception:
        from difflib import SequenceMatcher
        return int(SequenceMatcher(None, a_n, b_n).ratio() * 100)


def _score_playlist(pl: dict[str, Any], q: str, my_user_spotify_id: str | None) -> int:
    """Score playlist match: exact + similarity + owner bonus."""
    qn = _norm(q)
    name = pl.get("name", "")
    nn = _norm(name)

    score = 0
    if nn == qn and qn:
        score += 100
    score += _similarity(name, q)

    owner_id = (pl.get("owner") or {}).get("id")
    if my_user_spotify_id and owner_id == my_user_spotify_id:
        score += 30  # Personal playlist bonus

    return score


def _pick_best_playlist(playlists: list[dict[str, Any]], query: str, my_spotify_id: str | None) -> tuple[int, dict[str, Any]] | None:
    """Pick best matching playlist from list."""
    best: tuple[int, dict[str, Any]] | None = None
    for pl in playlists:
        sc = _score_playlist(pl, query, my_spotify_id)
        if best is None or sc > best[0]:
            best = (sc, pl)
    return best


# ---- Original helper functions ----
def _is_retry_phrase(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) > 30:
        return False
    return t in ("done", "try again", "again", "retry", "yes", "go", "ok", "okay") or t in (
        "done.", "try again.", "again.", "retry.", "yes.", "go.", "ok.", "okay.",
    )


def _is_retry_request_valid(retry: dict[str, Any] | None) -> bool:
    if not retry or not retry.get("created_at"):
        return False
    try:
        created = datetime.fromisoformat(retry["created_at"].replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created).total_seconds()
        return age <= SPOTIFY_RETRY_MAX_AGE_SECONDS
    except (ValueError, TypeError):
        return False


def _is_now_playing_query(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(
        k in t
        for k in (
            "what song is playing",
            "what's playing",
            "what is playing",
            "now playing",
            "currently playing",
            "playing now",
        )
    )


async def _start_uri_on_device(user_id: str, device_id: str | None, uri: str) -> bool:
    if (uri or "").startswith("spotify:track:"):
        return await start_playback(user_id, device_id, track_uri=uri)
    return await start_playback(user_id, device_id, context_uri=uri)


# ---- NEW: Enhanced playlist search ----
async def _get_my_playlists_cached(user_id: str, spotify_token: str) -> list[dict[str, Any]]:
    """Get user playlists with caching."""
    cache_key = f"spotify_playlists:{user_id}"
    cached = _spotify_cache.get(cache_key)
    if cached is not None:
        return cached

    playlists = await list_user_playlists(user_id, max_results=50)
    _spotify_cache.set(cache_key, playlists)
    return playlists


async def _get_my_user_id(spotify_token: str) -> str | None:
    """Get current user's Spotify ID."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {spotify_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("id")
    except Exception as e:
        logger.warning("Failed to get Spotify user ID: %s", e)
        return None


async def _search_playlists_global(query: str, spotify_token: str) -> list[dict[str, Any]]:
    """Fallback: search global playlists."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.spotify.com/v1/search",
                params={"type": "playlist", "q": query, "limit": 20},
                headers={"Authorization": f"Bearer {spotify_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return ((data.get("playlists") or {}).get("items") or [])
    except Exception as e:
        logger.warning("Failed to search playlists globally: %s", e)
        return []


async def _get_recommendations(spotify_token: str, seed_track_id: str, limit: int = 12) -> list[dict[str, Any]]:
    """Get track recommendations based on seed track."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.spotify.com/v1/recommendations",
                params={"seed_tracks": seed_track_id, "limit": limit},
                headers={"Authorization": f"Bearer {spotify_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("tracks") or []
    except Exception as e:
        logger.warning("Failed to get recommendations: %s", e)
        return []


async def _queue_track(spotify_token: str, track_uri: str) -> bool:
    """Add track to queue."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.spotify.com/v1/me/player/queue?uri={track_uri}",
                headers={"Authorization": f"Bearer {spotify_token}"},
                timeout=10.0,
            )
            return r.status_code in (200, 204)
    except Exception as e:
        logger.warning("Failed to queue track: %s", e)
        return False


async def _ensure_active_device(spotify_token: str, user_id: str) -> str | None:
    """Ensure there's an active device, transfer if needed. Returns device_id or None."""
    devices = await list_user_devices(user_id)
    if not devices:
        return None
    
    # Check for active device
    for d in devices:
        if d.get("is_active"):
            return d.get("id")
    
    # Transfer to first available device
    target_id = devices[0].get("id")
    if target_id:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                await client.put(
                    "https://api.spotify.com/v1/me/player",
                    json={"device_ids": [target_id], "play": False},
                    headers={"Authorization": f"Bearer {spotify_token}"},
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning("Failed to transfer device: %s", e)
    
    return target_id


def _has_spotify_intent(text: str, pending_play: bool, retry_request: dict[str, Any] | None = None) -> bool:
    t = (text or "").strip().lower()
    if pending_play and len(text.strip()) < 40:
        return True
    if _is_retry_phrase(text) and _is_retry_request_valid(retry_request):
        return True
    if _is_now_playing_query(text):
        return True
    if any(k in t for k in ("skip", "next song", "next track")):
        return True
    if any(k in t for k in ("volume", "turn it up", "turn it down")):
        return True
    if extract_playlist_uri(text):
        return True
    if play_query_from_message(text):
        return True
    if _is_music_search(text):
        return True
    # Also catch natural-language requests like "can you play music" / "play something"
    intent = _parse_intent(text)
    if intent and intent.confidence >= 0.65:
        return True
    # Status / connection queries — e.g. "is spotify connected", "reconnect spotify"
    if any(k in t for k in (
        "spotify connected", "spotify status", "spotify account",
        "reconnect spotify", "connect spotify", "spotify not working",
        "spotify link", "spotify auth", "spotify login",
    )):
        return True
    return False


class SpotifyService:
    @staticmethod
    async def handle_message(user_id: str, text: str, extra_context: dict, channel: str = "") -> str | None:
        t_lower = (text or "").strip().lower()
        db = get_db()
        
        extra_context["spotify_channel"] = channel

        # 0. Pending device selection + retry
        pending = await db.get_pending_spotify_play(user_id)
        pending_play = bool(pending and len(text.strip()) < 40)
        retry_request = await db.get_spotify_retry_request(user_id)
        if retry_request and not _is_retry_request_valid(retry_request):
            await db.clear_spotify_retry_request(user_id)
            retry_request = None

        # Early exit: no Spotify intent
        if not _has_spotify_intent(text, pending_play, retry_request):
            return None

        # ---- Populate spotify_play_connected so LLM always knows the connection status ----
        _token_check = await get_user_access_token(user_id)
        if _token_check:
            extra_context["spotify_play_connected"] = True
        else:
            row = await db.get_spotify_tokens(user_id)
            if row:
                extra_context["spotify_reconnect_needed"] = True
            else:
                extra_context["spotify_play_connected"] = False

        # ---- NEW: Intent-based processing ----
        intent = _parse_intent(text)
        
        # If high confidence intent, use enhanced handlers
        if intent and intent.confidence >= 0.65:
            token = _token_check
            if not token:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    return "I need to reconnect to Spotify. Please check Settings."
                return "Spotify is not connected. Connect in Settings."
            
            # Control intent
            if intent.kind == "control":
                return await SpotifyService._handle_control(user_id, token, intent.raw)
            
            # Playlist intent - with personal priority
            if intent.kind == "playlist":
                return await SpotifyService._handle_playlist_enhanced(user_id, token, intent.query or "")
            
            # Track intent - with album context + recommendations
            if intent.kind == "track":
                return await SpotifyService._handle_track_enhanced(user_id, token, intent.query or "")

        # ---- Fallback to original handlers ----
        
        # 0b. Retry
        if _is_retry_phrase(text) and retry_request:
            return await SpotifyService._handle_retry(user_id, text, db, retry_request)

        # 1. Pending device selection
        if pending and len(text.strip()) < 40:
            return await SpotifyService._handle_device_selection(user_id, text, pending, db)

        # 2a. Now Playing
        if _is_now_playing_query(text):
            return await SpotifyService._handle_now_playing(user_id)

        # 2. Skip
        if any(k in t_lower for k in ("skip", "next song", "next track")):
            ok = await skip_next_track(user_id)
            if ok:
                return "Skipped."
            return "Failed to skip (is Spotify playing?)."

        # 3. Volume
        vol = parse_volume_percent(text) if "volume" in t_lower or "turn it up" in t_lower or "turn it down" in t_lower else None
        if vol is not None:
            ok = await set_volume_percent(user_id, vol)
            if ok:
                return f"Volume set to {vol}%."
            return "Failed to set volume."

        # 4. Playlist URI
        playlist_uri = extract_playlist_uri(text)
        if playlist_uri:
            token = _token_check
            if not token:
                return "Spotify is not connected. Go to Settings > Spotify to connect."
            ok = await start_playback(user_id, None, context_uri=playlist_uri)
            if ok:
                return "Starting playlist..."
            return "Failed to start playlist."

        # 5. Play query (original handler)
        play_query = play_query_from_message(text)
        if play_query:
            return await SpotifyService._handle_play_query_original(user_id, play_query, text, db)

        # 6. Search fallback
        query = _search_query_from_message(text)
        if query:
            extra_context["spotify_results"] = await spotify_search_if_configured(query)
            return None

        return None

    # ---- NEW: Enhanced handlers ----
    
    @staticmethod
    async def _handle_control(user_id: str, token: str, raw: str) -> str:
        """Handle control commands: pause, resume, skip, shuffle, repeat."""
        t = raw.lower()
        
        await _ensure_active_device(token, user_id)
        
        import httpx
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {token}"}
            
            if "pause" in t:
                await client.put("https://api.spotify.com/v1/me/player/pause", headers=headers)
                return "Paused."
            
            if "resume" in t or "play" in t:
                await client.put("https://api.spotify.com/v1/me/player/play", headers=headers)
                return "Resumed."
            
            if "next" in t or "skip" in t:
                await client.post("https://api.spotify.com/v1/me/player/next", headers=headers)
                return "Skipped."
            
            if "previous" in t or "back" in t:
                await client.post("https://api.spotify.com/v1/me/player/previous", headers=headers)
                return "Went back."
            
            if "shuffle" in t:
                state = "off" in t and "on" not in t
                await client.put(
                    f"https://api.spotify.com/v1/me/player/shuffle?state={str(not state).lower()}",
                    headers=headers
                )
                return f"Shuffle {'on' if not state else 'off'}."
            
            if "repeat" in t:
                if "off" in t:
                    state = "off"
                elif "track" in t:
                    state = "track"
                else:
                    state = "context"
                await client.put(
                    f"https://api.spotify.com/v1/me/player/repeat?state={state}",
                    headers=headers
                )
                return f"Repeat set to {state}."
        
        return "Command not recognized."

    @staticmethod
    async def _handle_playlist_enhanced(user_id: str, token: str, playlist_name: str) -> str:
        """Enhanced playlist playing with personal priority."""
        if not playlist_name:
            return "Playlist name is empty."
        
        my_user_id = await _get_my_user_id(token)
        
        # 1. Get user's playlists first (personal priority)
        my_playlists = await _get_my_playlists_cached(user_id, token)
        best = _pick_best_playlist(my_playlists, playlist_name, my_user_id)
        
        # 2. Fallback to global search if no good match
        if not best or best[0] < PLAYLIST_MATCH_THRESHOLD:
            global_playlists = await _search_playlists_global(playlist_name, token)
            best_global = _pick_best_playlist(global_playlists, playlist_name, my_user_id)
            if best_global and (not best or best_global[0] > best[0]):
                best = best_global
        
        if not best:
            return f"Couldn't find a playlist matching '{playlist_name}'."
        
        score, pl = best
        uri = pl.get("uri")
        name = pl.get("name", "Unknown playlist")
        
        if not uri:
            return "Playlist found but missing URI."
        
        # Ensure device and play
        device_id = await _ensure_active_device(token, user_id)
        ok = await start_playback(user_id, device_id, context_uri=uri)
        
        if ok:
            owner = (pl.get("owner") or {}).get("display_name") or (pl.get("owner") or {}).get("id") or "unknown"
            return f"Playing playlist: {name} (score: {score})"
        return f"Failed to play playlist: {name}"

    @staticmethod
    async def _handle_track_enhanced(user_id: str, token: str, query: str) -> str:
        """Enhanced track playing with album context + recommendations."""
        if not query:
            return "Track query is empty."
        
        # Search for track
        results = await spotify_search_if_configured(query)
        if not results or not results[0].get("uri"):
            return f"Couldn't find a track for '{query}'."
        
        track = results[0]
        track_uri = track.get("uri")
        track_id = track.get("id")
        track_name = track.get("name", "Unknown track")
        artists = track.get("artist", "")
        
        # Get album URI for context playback
        album_uri = None
        # Need to fetch full track info for album URI
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"https://api.spotify.com/v1/tracks/{track_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                if r.status_code == 200:
                    track_data = r.json()
                    album_uri = (track_data.get("album") or {}).get("uri")
        except Exception as e:
            logger.warning("Failed to get track album: %s", e)
        
        # Ensure device
        device_id = await _ensure_active_device(token, user_id)
        
        if PREFER_ALBUM_CONTEXT_FOR_TRACKS and album_uri and track_uri:
            # Play in album context
            import httpx
            async with httpx.AsyncClient() as client:
                await client.put(
                    "https://api.spotify.com/v1/me/player/play",
                    json={"context_uri": album_uri, "offset": {"uri": track_uri}},
                    headers={"Authorization": f"Bearer {token}"},
                )
            mode = "album"
        else:
            # Play single track
            ok = await start_playback(user_id, device_id, track_uri=track_uri)
            if not ok:
                return f"Failed to play: {track_name}"
            mode = "single"
        
        # Queue recommendations for continued playback
        if track_id and mode == "single":
            recs = await _get_recommendations(token, track_id, RECOMMENDATIONS_TO_QUEUE)
            for r in recs:
                r_uri = r.get("uri")
                if r_uri and r_uri != track_uri:
                    await _queue_track(token, r_uri)
        
        display = f"{track_name} by {artists}" if artists else track_name
        return f"Playing: {display}"

    # ---- Original handlers (for fallback) ----
    
    @staticmethod
    async def _handle_retry(user_id: str, text: str, db, retry_request: dict) -> str:
        play_query = retry_request.get("play_query") or ""
        track_uri = (retry_request.get("track_uri") or "").strip()
        await db.clear_spotify_retry_request(user_id)
        
        token = await get_user_access_token(user_id)
        if not token:
            row = await db.get_spotify_tokens(user_id)
            if row:
                return "I need to reconnect to Spotify. Please check Settings."
            return "Spotify is not connected. Connect in Settings."
        
        if track_uri:
            devices = await list_user_devices(user_id)
            if not devices:
                await db.set_spotify_retry_request(user_id, play_query, track_uri)
                return "No active Spotify devices found. Open Spotify first."
            if len(devices) == 1:
                dev = devices[0]
                ok = await _start_uri_on_device(user_id, dev.get("id"), track_uri)
                return f"Playing on {dev.get('name')}." if ok else f"Failed on {dev.get('name')}."
            await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
            return "Which device?\n" + ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
        
        if play_query:
            results = await spotify_search_if_configured(play_query)
            if not results or not results[0].get("uri"):
                return f"I couldn't find '{play_query}' on Spotify."
            track_uri = results[0]["uri"]
            devices = await list_user_devices(user_id)
            if not devices:
                await db.set_spotify_retry_request(user_id, play_query, track_uri)
                return "No active Spotify devices found."
            if len(devices) == 1:
                dev = devices[0]
                ok = await _start_uri_on_device(user_id, dev.get("id"), track_uri)
                return f"Playing on {dev.get('name')}." if ok else f"Failed."
            await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
            return "Which device?\n" + ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
        
        return None

    @staticmethod
    async def _handle_device_selection(user_id: str, text: str, pending, db) -> str:
        try:
            devices = json.loads(pending.get("devices_json") or "[]")
            choice = text.strip().lower()
            device_id = None
            device_name = None
            
            if choice.isdigit() and 1 <= int(choice) <= len(devices):
                idx = int(choice) - 1
                device_id = devices[idx].get("id")
                device_name = devices[idx].get("name")
            else:
                for d in devices:
                    if choice in (d.get("name") or "").lower():
                        device_id = d.get("id")
                        device_name = d.get("name")
                        break
            
            if device_id:
                ok = await _start_uri_on_device(user_id, device_id, pending["track_uri"])
                await db.clear_pending_spotify_play(user_id)
                return f"Playing on {device_name or 'device'}." if ok else f"Failed on {device_name or 'device'}."
        except Exception as e:
            logger.warning(f"Failed to parse device choice: {e}")
        return None

    @staticmethod
    async def _handle_now_playing(user_id: str) -> str:
        now = await get_currently_playing(user_id)
        if now is None:
            row = await get_db().get_spotify_tokens(user_id)
            if row:
                return "I need to reconnect to Spotify."
            return "Spotify is not connected."
        track = (now.get("track") or "").strip()
        artist = (now.get("artist") or "").strip()
        if not track:
            return "Nothing is currently playing."
        who = f" by {artist}" if artist else ""
        if now.get("is_playing"):
            return f"Now playing: {track}{who}."
        return f"Paused: {track}{who}."

    @staticmethod
    async def _handle_play_query_original(user_id: str, play_query: str, original_text: str, db) -> str:
        """Original play query handler (fallback)."""
        token = await get_user_access_token(user_id)
        if not token:
            await db.set_spotify_retry_request(user_id, play_query, "")
            row = await db.get_spotify_tokens(user_id)
            if row:
                return "Token expired. Please reconnect in Settings."
            return "Spotify is not connected."
        
        # Check for playlist
        playlist_name = playlist_name_from_message(original_text)
        if playlist_name:
            playlists = await list_user_playlists(user_id, max_results=50)
            playlist_uri, matched_name = find_playlist_uri_by_name(playlist_name, playlists)
            if not playlist_uri:
                return f"I couldn't find playlist '{playlist_name}'."
            devices = await list_user_devices(user_id)
            if not devices:
                await db.set_spotify_retry_request(user_id, f"playlist:{matched_name or playlist_name}", playlist_uri)
                return "No active Spotify devices found."
            if len(devices) == 1:
                dev = devices[0]
                ok = await _start_uri_on_device(user_id, dev.get("id"), playlist_uri)
                return f"Playing on {dev.get('name')}." if ok else "Failed."
            await db.set_pending_spotify_play(user_id, playlist_uri, json.dumps(devices))
            return "Which device?\n" + ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
        
        # Search track
        results = await spotify_search_if_configured(play_query)
        track_uri = None
        context_uri = None
        display_name = play_query
        
        if results and results[0].get("uri"):
            track_uri = results[0]["uri"]
            track_name = results[0].get("name") or "track"
            artist = results[0].get("artist") or ""
            display_name = f"{track_name} by {artist}" if artist else track_name
        else:
            artist_results = await search_spotify_artists(play_query, token, 1)
            if artist_results and artist_results[0].get("uri"):
                context_uri = artist_results[0]["uri"]
                display_name = artist_results[0].get("name") or play_query
            else:
                return f"I couldn't find '{play_query}' on Spotify."
        
        if track_uri or context_uri:
            devices = await list_user_devices(user_id)
            if not devices:
                await db.set_spotify_retry_request(user_id, play_query, track_uri or context_uri or "")
                return "No active Spotify devices found."
            if len(devices) == 1:
                dev = devices[0]
                ok = await start_playback(user_id, dev.get("id"), track_uri=track_uri, context_uri=context_uri)
                return f"Playing {display_name} on {dev.get('name')}." if ok else "Failed."
            await db.set_pending_spotify_play(user_id, track_uri or context_uri or "", json.dumps(devices))
            return f"Which device?\n" + ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
        
        return None
