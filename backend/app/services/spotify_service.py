import json
import logging
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


def _is_retry_phrase(text: str) -> bool:
    """True if user is saying to retry (e.g. after opening Spotify or connecting)."""
    t = (text or "").strip().lower()
    if len(t) > 30:
        return False
    return t in ("done", "try again", "again", "retry", "yes", "go", "ok", "okay") or t in (
        "done.", "try again.", "again.", "retry.", "yes.", "go.", "ok.", "okay.",
    )


def _is_retry_request_valid(retry: dict[str, Any] | None) -> bool:
    """True if retry request exists and is not too old."""
    if not retry or not retry.get("created_at"):
        return False
    try:
        # SQLite datetime('now') is UTC
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
    """Play URI on device, treating tracks vs contexts correctly."""
    if (uri or "").startswith("spotify:track:"):
        return await start_playback(user_id, device_id, track_uri=uri)
    return await start_playback(user_id, device_id, context_uri=uri)


def _has_spotify_intent(text: str, pending_play: bool, retry_request: dict[str, Any] | None = None) -> bool:
    """True only when message has explicit Spotify/music intent (not generic text)."""
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
    return False


class SpotifyService:
    @staticmethod
    async def handle_message(user_id: str, text: str, extra_context: dict) -> str | None:
        """
        Process user text for specific Spotify commands.
        Returns a reply string if handled (short-circuiting the LLM), or None if not handled/needs LLM.
        Updates extra_context in-place.
        Only runs when message has explicit Spotify/music intent (avoids hijacking reminders, questions, etc).
        """
        t_lower = (text or "").strip().lower()
        db = get_db()

        # 0. Pending device selection state + retry request (for "Done" / "Try again")
        pending = await db.get_pending_spotify_play(user_id)
        pending_play = bool(pending and len(text.strip()) < 40)
        retry_request = await db.get_spotify_retry_request(user_id)
        if retry_request and not _is_retry_request_valid(retry_request):
            await db.clear_spotify_retry_request(user_id)
            retry_request = None

        # Early exit: no Spotify intent -> let LLM handle
        if not _has_spotify_intent(text, pending_play, retry_request):
            return None

        # 0b. Retry last play (user said "Done" / "Try again" after no devices or not connected)
        if _is_retry_phrase(text) and retry_request:
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
                # We had a track; just list devices and play
                devices = await list_user_devices(user_id)
                if not devices:
                    await db.set_spotify_retry_request(user_id, play_query, track_uri)
                    return "No active Spotify devices found. Open Spotify on your phone or laptop first."
                if len(devices) == 1:
                    dev = devices[0]
                    ok = await _start_uri_on_device(user_id, dev.get("id"), track_uri)
                    if ok:
                        return "Playing on {0}.".format(dev.get("name") or "device")
                    return "Failed to play on {0}.".format(dev.get("name") or "device")
                await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
                dev_list = ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
                return "Which device?\n{0}".format(dev_list)
            if play_query:
                # No track yet (e.g. was "not connected"); search and play
                results = await spotify_search_if_configured(play_query)
                if not results or not results[0].get("uri"):
                    return f"I couldn't find '{play_query}' on Spotify."
                track_uri = results[0]["uri"]
                track_name = results[0].get("name") or "track"
                artist = results[0].get("artist") or ""
                display_name = f"{track_name} by {artist}" if artist else track_name
                devices = await list_user_devices(user_id)
                if not devices:
                    await db.set_spotify_retry_request(user_id, play_query, track_uri)
                    return "No active Spotify devices found. Open Spotify on your phone or laptop first."
                if len(devices) == 1:
                    dev = devices[0]
                    ok = await _start_uri_on_device(user_id, dev.get("id"), track_uri)
                    if ok:
                        return f"Playing {display_name} on {dev.get('name')}."
                    return f"Failed to play on {dev.get('name')}."
                await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
                dev_list = ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
                return f"Found {display_name}. Which device?\n{dev_list}"
            return None

        # 1. Pending Device Selection (e.g. "1", "Kitchen")
        if pending and len(text.strip()) < 40:
            try:
                devices = json.loads(pending.get("devices_json") or "[]")
                choice = text.strip().lower()
                device_id = None
                device_name = None
                
                # Check index (1-based)
                if choice.isdigit() and 1 <= int(choice) <= len(devices):
                    idx = int(choice) - 1
                    device_id = devices[idx].get("id")
                    device_name = devices[idx].get("name")
                else:
                    # Check name match
                    for d in devices:
                        if choice in (d.get("name") or "").lower():
                            device_id = d.get("id")
                            device_name = d.get("name")
                            # Don't break immediately if multiple match? First match is fine.
                            break
                
                if device_id:
                    ok = await _start_uri_on_device(user_id, device_id, pending["track_uri"])
                    await db.clear_pending_spotify_play(user_id)
                    if ok:
                        return f"Playing on {device_name or 'device'}."
                    else:
                        return f"Failed to play on {device_name or 'device'}."
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse pending spotify choice: {e}")
                pass

        # 2a. Now Playing
        if _is_now_playing_query(text):
            now = await get_currently_playing(user_id)
            if now is None:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    return "I need to reconnect to Spotify. Please check Settings."
                return "Spotify is not connected. Connect in Settings."
            track = (now.get("track") or "").strip()
            artist = (now.get("artist") or "").strip()
            if not track:
                return "Nothing is currently playing on Spotify."
            who = f" by {artist}" if artist else ""
            if now.get("is_playing"):
                return f"Now playing: {track}{who}."
            return f"Spotify is paused on: {track}{who}."

        # 2. Skip / Next
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

        # 4. Playlist URI / Link
        playlist_uri = extract_playlist_uri(text)
        if playlist_uri:
            token = await get_user_access_token(user_id)
            if not token:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    return "I need to reconnect to Spotify. Please check Settings."
                else:
                    return "Spotify is not connected. Go to Settings > Spotify to connect."
            else:
                ok = await start_playback(user_id, None, context_uri=playlist_uri)
                if ok:
                    return "Starting playlist..."
                return "Failed to start playlist."

        # 5. "Play X" query
        play_query = play_query_from_message(text)
        if play_query:
            token = await get_user_access_token(user_id)
            if not token:
                await db.set_spotify_retry_request(user_id, play_query, "")
                row = await db.get_spotify_tokens(user_id)
                if row:
                    return "Token expired. Please reconnect Spotify in Settings."
                else:
                    return "Spotify is not connected. Connect in Settings."
            else:
                playlist_name = playlist_name_from_message(text)
                if playlist_name:
                    playlists = await list_user_playlists(user_id, max_results=50)
                    playlist_uri, matched_name = find_playlist_uri_by_name(playlist_name, playlists)
                    if not playlist_uri:
                        return f"I couldn't find a playlist named '{playlist_name}'."
                    devices = await list_user_devices(user_id)
                    if not devices:
                        await db.set_spotify_retry_request(user_id, f"playlist:{matched_name or playlist_name}", playlist_uri)
                        return "No active Spotify devices found. Open Spotify on your phone or laptop first."
                    if len(devices) == 1:
                        dev = devices[0]
                        ok = await _start_uri_on_device(user_id, dev.get("id"), playlist_uri)
                        if ok:
                            return f"Playing playlist {matched_name or playlist_name} on {dev.get('name')}."
                        return f"Failed to play on {dev.get('name')}."
                    await db.set_pending_spotify_play(user_id, playlist_uri, json.dumps(devices))
                    dev_list = ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
                    return f"Found playlist {matched_name or playlist_name}. Which device?\n{dev_list}"

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
                    # No track found — try artist (e.g. "Play Bob Dylan")
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
                        return "No active Spotify devices found. Open Spotify on your phone or laptop first."
                    elif len(devices) == 1:
                        dev = devices[0]
                        ok = await start_playback(user_id, dev.get("id"), track_uri=track_uri, context_uri=context_uri)
                        if ok:
                            return f"Playing {display_name} on {dev.get('name')}."
                        return f"Failed to play on {dev.get('name')}."
                    else:
                        await db.set_pending_spotify_play(user_id, track_uri or context_uri or "", json.dumps(devices))
                        dev_list = ", ".join([f"{i+1}. {d.get('name')}" for i, d in enumerate(devices)])
                        return f"Found {display_name}. Which device?\n{dev_list}"

        # 6. General Search - Fallback
        # If user explicitly asks to "search spotify for X", we might want to return results.
        # But 'play' is handled above. If we just return None here, the LLM will handle "search" 
        # using the context injected by checking 'spotify' skill later?
        # Actually context builder runs BEFORE this returns? No. 
        # In handler.py, handle_message runs service FIRST.
        # So we can inject context here and let LLM talk about it if it's just a broad search.
        
        query = _search_query_from_message(text)
        if query:
             extra_context["spotify_results"] = await spotify_search_if_configured(query)
             # Return None so LLM summarizes the search results
             return None
        
        return None
