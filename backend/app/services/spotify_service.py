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
    async def handle_message(user_id: str, text: str, extra_context: dict) -> bool:
        """
        Process user text for specific Spotify commands.
        Returns True if a Spotify action was triggered/handled, False otherwise.
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
                            break
                
                if device_id:
                    ok = await start_playback(user_id, device_id, pending["track_uri"])
                    await db.clear_pending_spotify_play(user_id)
                    if ok:
                        extra_context["spotify_played_on"] = device_name or "device"
                    else:
                        extra_context["spotify_play_failed"] = True
                        extra_context["spotify_play_failed_device"] = device_name or "device"
                    return True # Handled pending choice
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse pending spotify choice: {e}")
                pass

        # 2. Skip / Next
        if any(k in t_lower for k in ("skip", "next song", "next track")):
            ok = await skip_next_track(user_id)
            extra_context["spotify_play_connected"] = True
            extra_context["spotify_skipped"] = ok
            return True

        # 3. Volume
        vol = parse_volume_percent(text) if "volume" in t_lower or "turn it up" in t_lower or "turn it down" in t_lower else None
        if vol is not None:
            ok = await set_volume_percent(user_id, vol)
            extra_context["spotify_play_connected"] = True
            extra_context["spotify_volume_set"] = ok
            extra_context["spotify_volume_value"] = vol
            return True

        # 4. Playlist URI / Link
        playlist_uri = extract_playlist_uri(text)
        if playlist_uri:
            token = await get_user_access_token(user_id)
            if not token:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    extra_context["spotify_reconnect_needed"] = True
                else:
                    extra_context["spotify_play_connected"] = False
            else:
                extra_context["spotify_play_connected"] = True
                ok = await start_playback(user_id, None, context_uri=playlist_uri)
                if ok:
                    extra_context["spotify_played_on"] = "active device"
                else:
                    extra_context["spotify_play_failed"] = True
                    extra_context["spotify_play_failed_device"] = "active device"
            return True

        # 5. "Play X" query
        play_query = play_query_from_message(text)
        if play_query:
            token = await get_user_access_token(user_id)
            if not token:
                row = await db.get_spotify_tokens(user_id)
                if row:
                    extra_context["spotify_reconnect_needed"] = True
                else:
                    extra_context["spotify_play_connected"] = False
            else:
                extra_context["spotify_play_connected"] = True
                results = await spotify_search_if_configured(play_query)
                if not results or not results[0].get("uri"):
                    extra_context["spotify_results"] = []
                else:
                    track_uri = results[0]["uri"]
                    devices = await list_user_devices(user_id)
                    if not devices:
                        extra_context["spotify_devices"] = []
                        extra_context["spotify_play_track_uri"] = track_uri
                    elif len(devices) == 1:
                        dev = devices[0]
                        ok = await start_playback(user_id, dev.get("id"), track_uri)
                        if ok:
                            extra_context["spotify_played_on"] = dev.get("name") or "device"
                        else:
                            extra_context["spotify_play_failed"] = True
                            extra_context["spotify_play_failed_device"] = dev.get("name") or "device"
                    else:
                        await db.set_pending_spotify_play(user_id, track_uri, json.dumps(devices))
                        extra_context["spotify_devices"] = devices
                        extra_context["spotify_pending_track_uri"] = track_uri
            return True

        # 6. General Search (Fallback if enabled)
        # Note: In the original handler, this was run if "spotify" was in skills_to_use.
        # We might want to keep this separate or ensure it's called only when relevant.
        query = _search_query_from_message(text)
        if query:
             extra_context["spotify_results"] = await spotify_search_if_configured(query)
             return True
        
        return False
