"""Spotify OAuth (connect, callback), devices, and play."""
import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.db import get_db
from app.keys import get_api_key
from app.spotify_client import get_user_access_token, list_user_devices, start_playback
from app.routers.settings import _spotify_redirect_uri


class PlayIn(BaseModel):
    device_id: str | None = None
    track_uri: str = ""

logger = logging.getLogger(__name__)
router = APIRouter()

SCOPES = "user-read-playback-state user-modify-playback-state user-read-private playlist-read-private playlist-modify-private playlist-modify-public user-library-modify user-library-read"


@router.get("/spotify/connect")
async def spotify_connect(request: Request, user_id: str = "default"):
    """Redirect user to Spotify to authorize (for playback). After auth, Spotify redirects to callback."""
    cid = (await get_api_key("spotify_client_id")) or ""
    cid = cid.strip()
    if not cid:
        return {"error": "Spotify Client ID not set. Add it in Settings → Spotify."}
    # Use the same redirect URI helper as the Settings UI so it always matches
    redirect_uri = _spotify_redirect_uri(request)
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": user_id,
        "show_dialog": "false",
    }
    url = "https://accounts.spotify.com/authorize?" + urlencode(params)
    return RedirectResponse(url=url)


@router.get("/spotify/callback")
async def spotify_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Exchange code for tokens and store. Redirect to frontend with success/failure."""
    try:
        from app.config import get_settings
        origins = [o.strip() for o in (get_settings().asta_cors_origins or "").split(",") if o.strip()]
        frontend_origin = origins[0] if origins else "http://localhost:5173"
    except Exception:
        frontend_origin = "http://localhost:5173"
    if error or not code:
        return RedirectResponse(url=f"{frontend_origin}/settings?spotify=error&msg=" + (error or "no_code"))
    user_id = state or "default"
    cid = (await get_api_key("spotify_client_id")) or ""
    secret = (await get_api_key("spotify_client_secret")) or ""
    cid, secret = cid.strip(), (secret or "").strip()
    if not cid or not secret:
        return RedirectResponse(url=f"{frontend_origin}/settings?spotify=error&msg=credentials")
    import httpx
    # Must match the redirect URI used when sending the user to Spotify
    redirect_uri = _spotify_redirect_uri(request)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
                auth=(cid, secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        refresh = data.get("refresh_token")
        access = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        if not refresh or not access:
            return RedirectResponse(url=f"{frontend_origin}/settings?spotify=error&msg=no_tokens")
        import time
        expires_at = str(time.time() + expires_in)
        db = get_db()
        await db.connect()
        await db.set_spotify_tokens(user_id, refresh, access, expires_at)
        return RedirectResponse(url=f"{frontend_origin}/settings?spotify=connected")
    except Exception as e:
        logger.exception("Spotify callback: %s", e)
        return RedirectResponse(url=f"{frontend_origin}/settings?spotify=error&msg=exchange")


@router.get("/spotify/devices")
async def spotify_devices(user_id: str = "default"):
    """List user's Spotify devices (for 'where to play' picker)."""
    devices = await list_user_devices(user_id)
    return {"devices": devices, "connected": len(devices) > 0}


@router.post("/spotify/play")
async def spotify_play(body: PlayIn, user_id: str = "default"):
    """Start playback on a device. track_uri e.g. spotify:track:xxx."""
    if not (body.track_uri or "").strip():
        return {"ok": False, "error": "track_uri required"}
    ok = await start_playback(user_id, body.device_id, body.track_uri.strip())
    return {"ok": ok, "error": None if ok else "Playback failed (device active?)"}


@router.get("/spotify/status")
async def spotify_status(user_id: str = "default"):
    """Whether the user has connected Spotify for playback."""
    token = await get_user_access_token(user_id)
    return {"connected": bool(token)}


@router.post("/spotify/disconnect")
async def spotify_disconnect(user_id: str = "default"):
    """Clear stored Spotify tokens so the user can re-authorize."""
    from app.db import get_db
    db = get_db()
    await db.connect()
    await db.clear_spotify_tokens(user_id)
    return {"disconnected": True}
