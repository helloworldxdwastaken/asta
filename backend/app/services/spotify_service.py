import json
import logging
from typing import Any

from app.db import get_db
from app.spotify_client import (
    start_playback,
    skip_next_track,
    set_volume_percent,
    list_user_devices,
    get_user_access_token,
    extract_playlist_uri,
    play_query_from_message,
    spotify_search_if_configured,
    _search_query_from_message,
    parse_volume_percent,
)

logger = logging.getLogger(__name__)

class SpotifyService:
    @staticmethod
    async def handle_message(user_id: str, text: str, extra_context: dict) -> str | None:
        """
        Process user text for specific Spotify commands.
        Returns a reply string if handled (short-circuiting the LLM), or None if not handled/needs LLM.
        Updates extra_context in-place.
        """
        t_lower = (text or "").strip().lower()

        # 1. Pending Device Selection (e.g. "1", "Kitchen")
        db = get_db()
        pending = await db.get_pending_spotify_play(user_id)
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
                    ok = await start_playback(user_id, device_id, pending["track_uri"])
                    await db.clear_pending_spotify_play(user_id)
                    if ok:
                        return f"Playing on {device_name or 'device'}."
                    else:
                        return f"Failed to play on {device_name or 'device'}."
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse pending spotify choice: {e}")
                pass

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
                row = await db.get_spotify_tokens(user_id)
                if row:
                    return "Token expired. Please reconnect Spotify in Settings."
                else:
                    return "Spotify is not connected. Connect in Settings."
            else:
                results = await spotify_search_if_configured(play_query)
                if not results or not results[0].get("uri"):
                    return f"I couldn't find '{play_query}' on Spotify."
                else:
                    track_uri = results[0]["uri"]
                    track_name = results[0].get("name") or "track"
                    artist = results[0].get("artist") or ""
                    display_name = f"{track_name} by {artist}" if artist else track_name
                    
                    devices = await list_user_devices(user_id)
                    if not devices:
                        return "No active Spotify devices found. Open Spotify on your phone or laptop first."
                    elif len(devices) == 1:
                        dev = devices[0]
                        ok = await start_playback(user_id, dev.get("id"), track_uri)
                        if ok:
                            return f"Playing {display_name} on {dev.get('name')}."
                        return f"Failed to play on {dev.get('name')}."
                    else:
                        await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
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
