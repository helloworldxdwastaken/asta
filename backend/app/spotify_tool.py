"""Spotify LLM tool: search, play, control, create playlists, add songs, etc.

Single multi-action tool (like reminders/cron) exposed to the LLM when the
Spotify skill is enabled. Replaces the old pre-LLM SpotifyService interceptor.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def get_spotify_tools_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "spotify",
                "description": (
                    "Control Spotify: search for tracks/playlists/artists, play music, "
                    "control playback (pause/resume/skip/previous/shuffle/repeat), adjust volume, "
                    "check what's playing, list your playlists, create a new playlist, "
                    "or add songs to a playlist. Requires Spotify to be connected (OAuth). "
                    "Use action='search' first to find URIs, then 'play' or 'add_to_playlist'. "
                    "For playing by name, pass query directly to action='play'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "search",
                                "play",
                                "control",
                                "volume",
                                "now_playing",
                                "list_playlists",
                                "get_playlist_tracks",
                                "list_devices",
                                "create_playlist",
                                "add_to_playlist",
                                "remove_from_playlist",
                                "queue",
                                "save_track",
                            ],
                            "description": "The Spotify action to perform.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Track/artist/playlist name to search or play.",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["track", "playlist", "artist", "album"],
                            "description": "What to search/play (default: track).",
                        },
                        "uri": {
                            "type": "string",
                            "description": "Spotify URI (e.g. spotify:track:xxx or spotify:playlist:xxx) to play directly.",
                        },
                        "device_id": {
                            "type": "string",
                            "description": "Device ID to play on (optional, auto-selects active device).",
                        },
                        "command": {
                            "type": "string",
                            "enum": [
                                "pause", "resume", "skip", "previous",
                                "shuffle_on", "shuffle_off",
                                "repeat_off", "repeat_track", "repeat_context",
                            ],
                            "description": "Playback control command (required for action=control).",
                        },
                        "volume": {
                            "type": "integer",
                            "description": "Volume 0–100 (required for action=volume).",
                        },
                        "playlist_name": {
                            "type": "string",
                            "description": "Name for the new playlist (required for action=create_playlist).",
                        },
                        "description": {
                            "type": "string",
                            "description": "Playlist description (optional, for action=create_playlist).",
                        },
                        "public": {
                            "type": "boolean",
                            "description": "Whether to make playlist public (for action=create_playlist, default: false).",
                        },
                        "playlist_id": {
                            "type": "string",
                            "description": "Spotify playlist ID to add tracks to (required for action=add_to_playlist).",
                        },
                        "track_uris": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Spotify track URIs (spotify:track:xxx) to add (required for action=add_to_playlist).",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max search results (1–10, default 5).",
                        },
                        "track_uri": {
                            "type": "string",
                            "description": "Single Spotify track URI (spotify:track:xxx) for action=queue or action=save_track.",
                        },
                        "snapshot_id": {
                            "type": "string",
                            "description": "Playlist snapshot_id for action=remove_from_playlist (returned by get_playlist_tracks).",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Pagination offset for action=get_playlist_tracks (default 0).",
                        },
                    },
                    "required": ["action"],
                },
            },
        }
    ]


def parse_spotify_tool_args(args_str: str | dict) -> dict[str, Any]:
    if isinstance(args_str, dict):
        return args_str
    try:
        parsed = json.loads(args_str)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def run_spotify_tool(params: dict[str, Any], user_id: str) -> str:
    """Dispatch a Spotify tool action. Always returns a JSON string."""
    action = (params.get("action") or "").strip().lower()
    dispatch = {
        "now_playing": _do_now_playing,
        "list_devices": _do_list_devices,
        "list_playlists": _do_list_playlists,
        "get_playlist_tracks": _do_get_playlist_tracks,
        "search": _do_search,
        "play": _do_play,
        "control": _do_control,
        "volume": _do_volume,
        "create_playlist": _do_create_playlist,
        "add_to_playlist": _do_add_to_playlist,
        "remove_from_playlist": _do_remove_from_playlist,
        "queue": _do_queue,
        "save_track": _do_save_track,
    }
    fn = dispatch.get(action)
    if fn is None:
        return json.dumps({"ok": False, "error": f"Unknown action: {action!r}"})
    return await fn(user_id, params)


# ---- helpers ----

async def _require_token(user_id: str) -> tuple[str | None, str | None]:
    """Return (token, error_json). If not connected, token is None and error_json is set."""
    from app.spotify_client import get_user_access_token
    token = await get_user_access_token(user_id)
    if not token:
        return None, json.dumps({
            "ok": False,
            "error": "Spotify is not connected. Tell the user to go to Settings → Integrations → Spotify and click Connect.",
        })
    return token, None


# ---- actions ----

async def _do_now_playing(user_id: str, _params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    from app.spotify_client import get_currently_playing
    now = await get_currently_playing(user_id)
    if now is None:
        return json.dumps({"ok": False, "error": "Could not get playback state."})
    return json.dumps({"ok": True, **now})


async def _do_list_devices(user_id: str, _params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    from app.spotify_client import list_user_devices
    devices = await list_user_devices(user_id)
    return json.dumps({"ok": True, "devices": devices})


async def _do_list_playlists(user_id: str, params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    from app.spotify_client import list_user_playlists
    max_results = min(int(params.get("max_results") or 50), 50)
    playlists = await list_user_playlists(user_id, max_results=max_results)
    return json.dumps({"ok": True, "playlists": playlists, "count": len(playlists)})


async def _do_search(user_id: str, params: dict) -> str:
    query = (params.get("query") or "").strip()
    if not query:
        return json.dumps({"ok": False, "error": "query is required for search"})
    search_type = (params.get("type") or "track").lower()
    max_results = min(int(params.get("max_results") or 5), 10)

    token, err = await _require_token(user_id)
    if err:
        # Fall back to client-credentials search for tracks
        if search_type == "track":
            from app.spotify_client import spotify_search_if_configured
            results = await spotify_search_if_configured(query)
            if results:
                return json.dumps({"ok": True, "type": "track", "results": results})
        return err

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.spotify.com/v1/search",
                params={"q": query, "type": search_type, "limit": max_results},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("Spotify search failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)})

    results: list[dict] = []
    if search_type == "track":
        for item in (data.get("tracks") or {}).get("items") or []:
            artists = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]
            results.append({
                "name": item.get("name"),
                "artist": ", ".join(artists),
                "album": (item.get("album") or {}).get("name"),
                "uri": item.get("uri"),
                "url": (item.get("external_urls") or {}).get("spotify"),
            })
    elif search_type == "playlist":
        for item in (data.get("playlists") or {}).get("items") or []:
            if not item:
                continue
            results.append({
                "name": item.get("name"),
                "owner": ((item.get("owner") or {}).get("display_name") or ""),
                "uri": item.get("uri"),
                "url": (item.get("external_urls") or {}).get("spotify"),
                "tracks": ((item.get("tracks") or {}).get("total") or 0),
            })
    elif search_type == "artist":
        for item in (data.get("artists") or {}).get("items") or []:
            results.append({
                "name": item.get("name"),
                "uri": item.get("uri"),
                "url": (item.get("external_urls") or {}).get("spotify"),
                "followers": ((item.get("followers") or {}).get("total") or 0),
            })
    elif search_type == "album":
        for item in (data.get("albums") or {}).get("items") or []:
            artists = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]
            results.append({
                "name": item.get("name"),
                "artist": ", ".join(artists),
                "uri": item.get("uri"),
                "url": (item.get("external_urls") or {}).get("spotify"),
                "release_date": item.get("release_date"),
            })

    return json.dumps({"ok": True, "type": search_type, "results": results})


async def _do_play(user_id: str, params: dict) -> str:
    from app.spotify_client import (
        start_playback, list_user_devices, list_user_playlists,
        find_playlist_uri_by_name, search_spotify_tracks, search_spotify_artists,
    )
    token, err = await _require_token(user_id)
    if err:
        return err

    uri = (params.get("uri") or "").strip()
    query = (params.get("query") or "").strip()
    play_type = (params.get("type") or "track").lower()
    device_id = (params.get("device_id") or "").strip() or None

    # Auto-detect playlist intent: if no explicit type was given and query matches a user playlist, treat as playlist
    if not params.get("type") and play_type == "track" and query:
        try:
            playlists = await list_user_playlists(user_id, max_results=50)
            playlist_uri, matched_name = find_playlist_uri_by_name(query, playlists)
            if playlist_uri:
                play_type = "playlist"
        except Exception:
            pass

    # Auto-select device
    if not device_id:
        devices = await list_user_devices(user_id)
        if devices:
            for d in devices:
                if d.get("is_active"):
                    device_id = d.get("id")
                    break
            if not device_id:
                device_id = (devices[0] or {}).get("id")

    # Play by URI directly
    if uri:
        if uri.startswith("spotify:track:"):
            ok = await start_playback(user_id, device_id, track_uri=uri)
        else:
            ok = await start_playback(user_id, device_id, context_uri=uri)
        return json.dumps({"ok": ok, "uri": uri, "device_id": device_id})

    if not query:
        return json.dumps({"ok": False, "error": "Provide query or uri to play"})

    # Play by name
    if play_type == "playlist":
        playlists = await list_user_playlists(user_id, max_results=50)
        playlist_uri, matched_name = find_playlist_uri_by_name(query, playlists)
        if not playlist_uri:
            # Global playlist search fallback
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        "https://api.spotify.com/v1/search",
                        params={"q": query, "type": "playlist", "limit": 5},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10.0,
                    )
                    r.raise_for_status()
                    items = (r.json().get("playlists") or {}).get("items") or []
                    if items and items[0]:
                        playlist_uri = items[0].get("uri")
                        matched_name = items[0].get("name")
            except Exception:
                pass
        if not playlist_uri:
            return json.dumps({"ok": False, "error": f"Playlist '{query}' not found"})
        ok = await start_playback(user_id, device_id, context_uri=playlist_uri)
        return json.dumps({"ok": ok, "playing": matched_name, "uri": playlist_uri})

    elif play_type == "artist":
        artists = await search_spotify_artists(query, token, max_results=1)
        if not artists:
            return json.dumps({"ok": False, "error": f"Artist '{query}' not found"})
        context_uri = artists[0].get("uri")
        ok = await start_playback(user_id, device_id, context_uri=context_uri)
        return json.dumps({"ok": ok, "playing": artists[0].get("name"), "uri": context_uri})

    else:  # track (default)
        results = await search_spotify_tracks(query, token, max_results=1)
        if not results:
            return json.dumps({"ok": False, "error": f"Track '{query}' not found"})
        track = results[0]
        track_uri = track.get("uri")
        ok = await start_playback(user_id, device_id, track_uri=track_uri)
        display = track.get("name") or query
        artist = track.get("artist")
        if artist:
            display = f"{display} by {artist}"
        return json.dumps({"ok": ok, "playing": display, "uri": track_uri})


async def _do_control(user_id: str, params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    command = (params.get("command") or "").strip().lower()
    if not command:
        return json.dumps({"ok": False, "error": "command is required for control action"})

    headers = {"Authorization": f"Bearer {token}"}
    _cmd_map = {
        "pause":          ("PUT",  "https://api.spotify.com/v1/me/player/pause"),
        "resume":         ("PUT",  "https://api.spotify.com/v1/me/player/play"),
        "skip":           ("POST", "https://api.spotify.com/v1/me/player/next"),
        "previous":       ("POST", "https://api.spotify.com/v1/me/player/previous"),
        "shuffle_on":     ("PUT",  "https://api.spotify.com/v1/me/player/shuffle?state=true"),
        "shuffle_off":    ("PUT",  "https://api.spotify.com/v1/me/player/shuffle?state=false"),
        "repeat_off":     ("PUT",  "https://api.spotify.com/v1/me/player/repeat?state=off"),
        "repeat_track":   ("PUT",  "https://api.spotify.com/v1/me/player/repeat?state=track"),
        "repeat_context": ("PUT",  "https://api.spotify.com/v1/me/player/repeat?state=context"),
    }
    entry = _cmd_map.get(command)
    if not entry:
        return json.dumps({"ok": False, "error": f"Unknown command: {command!r}"})
    method, url = entry
    try:
        async with httpx.AsyncClient() as client:
            if method == "PUT":
                r = await client.put(url, headers=headers, timeout=10.0)
            else:
                r = await client.post(url, headers=headers, timeout=10.0)
        ok = r.status_code in (200, 204)
        return json.dumps({"ok": ok, "command": command})
    except Exception as e:
        logger.warning("Spotify control failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)})


async def _do_volume(user_id: str, params: dict) -> str:
    from app.spotify_client import set_volume_percent
    vol = params.get("volume")
    if vol is None:
        return json.dumps({"ok": False, "error": "volume (0-100) is required"})
    try:
        vol = max(0, min(100, int(vol)))
    except (TypeError, ValueError):
        return json.dumps({"ok": False, "error": "volume must be an integer 0-100"})
    ok = await set_volume_percent(user_id, vol)
    return json.dumps({"ok": ok, "volume": vol})


async def _do_create_playlist(user_id: str, params: dict) -> str:
    from app.spotify_client import create_playlist
    name = (params.get("playlist_name") or params.get("name") or "").strip()
    if not name:
        return json.dumps({"ok": False, "error": "playlist_name is required"})
    public = bool(params.get("public", False))
    description = (params.get("description") or "").strip()
    result = await create_playlist(user_id, name, public=public, description=description)
    if not result:
        return json.dumps({"ok": False, "error": "Failed to create playlist. Is Spotify connected with the correct scopes?"})
    return json.dumps({"ok": True, **result})


async def _do_add_to_playlist(user_id: str, params: dict) -> str:
    from app.spotify_client import add_tracks_to_playlist
    playlist_id = (params.get("playlist_id") or "").strip()
    track_uris = params.get("track_uris") or []
    if not playlist_id:
        return json.dumps({"ok": False, "error": "playlist_id is required"})
    if not isinstance(track_uris, list) or not track_uris:
        return json.dumps({"ok": False, "error": "track_uris (list of spotify:track:xxx URIs) is required"})
    valid_uris = [u for u in track_uris if isinstance(u, str) and u.startswith("spotify:track:")]
    if not valid_uris:
        return json.dumps({"ok": False, "error": "No valid spotify:track: URIs found in track_uris"})
    ok = await add_tracks_to_playlist(user_id, playlist_id, valid_uris)
    return json.dumps({"ok": ok, "added": len(valid_uris), "playlist_id": playlist_id})


async def _do_get_playlist_tracks(user_id: str, params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    playlist_id = (params.get("playlist_id") or "").strip()
    if not playlist_id:
        return json.dumps({"ok": False, "error": "playlist_id is required"})
    offset = int(params.get("offset") or 0)
    max_results = min(int(params.get("max_results") or 50), 100)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
                params={"limit": max_results, "offset": offset, "fields": "total,next,items(track(name,uri,artists(name),album(name)))"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    tracks = []
    for item in (data.get("items") or []):
        t = item.get("track") or {}
        if not t or not t.get("uri"):
            continue
        artists = ", ".join(a.get("name") for a in (t.get("artists") or []) if a.get("name"))
        tracks.append({"name": t.get("name"), "artist": artists, "uri": t.get("uri")})
    return json.dumps({"ok": True, "tracks": tracks, "total": data.get("total", 0), "offset": offset})


async def _do_remove_from_playlist(user_id: str, params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    playlist_id = (params.get("playlist_id") or "").strip()
    track_uris = params.get("track_uris") or []
    if not playlist_id:
        return json.dumps({"ok": False, "error": "playlist_id is required"})
    valid_uris = [u for u in track_uris if isinstance(u, str) and u.startswith("spotify:track:")]
    if not valid_uris:
        return json.dumps({"ok": False, "error": "track_uris with spotify:track: URIs is required"})
    body: dict = {"tracks": [{"uri": u} for u in valid_uris]}
    snapshot_id = (params.get("snapshot_id") or "").strip()
    if snapshot_id:
        body["snapshot_id"] = snapshot_id
    try:
        async with httpx.AsyncClient() as client:
            r = await client.request(
                "DELETE",
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                content=json.dumps(body),
                timeout=10.0,
            )
            ok = r.status_code in (200, 204)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    return json.dumps({"ok": ok, "removed": len(valid_uris)})


async def _do_queue(user_id: str, params: dict) -> str:
    token, err = await _require_token(user_id)
    if err:
        return err
    uri = (params.get("track_uri") or params.get("uri") or "").strip()
    if not uri:
        return json.dumps({"ok": False, "error": "track_uri (spotify:track:xxx) is required"})
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.spotify.com/v1/me/player/queue",
                params={"uri": uri},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            ok = r.status_code in (200, 204)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    return json.dumps({"ok": ok, "queued": uri})


async def _do_save_track(user_id: str, params: dict) -> str:
    """Save/like a track to the user's Liked Songs."""
    token, err = await _require_token(user_id)
    if err:
        return err
    uri = (params.get("track_uri") or params.get("uri") or "").strip()
    if not uri:
        return json.dumps({"ok": False, "error": "track_uri (spotify:track:xxx) is required"})
    track_id = uri.split(":")[-1] if ":" in uri else uri
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                "https://api.spotify.com/v1/me/tracks",
                params={"ids": track_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            ok = r.status_code in (200, 204)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
    return json.dumps({"ok": ok, "saved": uri})
