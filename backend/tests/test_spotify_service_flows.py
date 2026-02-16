import json

import pytest

from app.services import spotify_service


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


class FakeSpotifyDb:
    def __init__(self) -> None:
        self.pending = None
        self.retry = None
        self.tokens = None
        self.retry_set_calls: list[tuple[str, str, str]] = []
        self.pending_set_calls: list[tuple[str, str, str]] = []
        self.pending_cleared = False
        self.retry_cleared = False

    async def get_pending_spotify_play(self, user_id: str):
        return self.pending

    async def get_spotify_retry_request(self, user_id: str):
        return self.retry

    async def clear_spotify_retry_request(self, user_id: str):
        self.retry_cleared = True
        self.retry = None

    async def set_spotify_retry_request(self, user_id: str, play_query: str, track_uri: str):
        self.retry_set_calls.append((user_id, play_query, track_uri))

    async def set_pending_spotify_play(self, user_id: str, track_uri: str, devices_json: str):
        self.pending_set_calls.append((user_id, track_uri, devices_json))

    async def clear_pending_spotify_play(self, user_id: str):
        self.pending_cleared = True
        self.pending = None

    async def get_spotify_tokens(self, user_id: str):
        return self.tokens


@pytest.mark.asyncio
async def test_spotify_service_ignores_non_spotify_text(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="remind me tomorrow to call mom",
        extra_context={},
    )
    assert out is None


@pytest.mark.asyncio
async def test_spotify_play_without_connection_sets_retry(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(spotify_service, "get_user_access_token", _async_return(None))

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="play thunderstruck on spotify",
        extra_context={},
    )

    assert out == "Spotify is not connected. Connect in Settings."
    assert db.retry_set_calls == [("default", "thunderstruck", "")]


@pytest.mark.asyncio
async def test_spotify_pending_device_selection_plays_and_clears(monkeypatch):
    db = FakeSpotifyDb()
    db.pending = {
        "track_uri": "spotify:track:abc",
        "devices_json": json.dumps(
            [
                {"id": "d1", "name": "Phone"},
                {"id": "d2", "name": "Kitchen Speaker"},
            ]
        ),
    }
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(spotify_service, "start_playback", _async_return(True))

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="2",
        extra_context={},
    )

    assert out == "Playing on Kitchen Speaker."
    assert db.pending_cleared is True


@pytest.mark.asyncio
async def test_spotify_skip_command_short_circuits(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(spotify_service, "skip_next_track", _async_return(True))

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="skip",
        extra_context={},
    )
    assert out == "Skipped."


@pytest.mark.asyncio
async def test_spotify_search_injects_results_context_for_llm(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(
        spotify_service,
        "spotify_search_if_configured",
        _async_return(
            [
                {
                    "name": "One More Time",
                    "artist": "Daft Punk",
                    "uri": "spotify:track:xyz",
                }
            ]
        ),
    )

    extra: dict = {}
    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="search spotify for daft punk",
        extra_context=extra,
    )
    assert out is None
    assert extra.get("spotify_results")
    assert extra["spotify_results"][0]["name"] == "One More Time"


@pytest.mark.asyncio
async def test_spotify_now_playing_returns_current_track(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(
        spotify_service,
        "get_currently_playing",
        _async_return(
            {
                "is_playing": True,
                "track": "Despacito",
                "artist": "Luis Fonsi",
                "album": "VIDA",
            }
        ),
    )

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="what song is playing now?",
        extra_context={},
    )
    assert out == "Now playing: Despacito by Luis Fonsi."


@pytest.mark.asyncio
async def test_spotify_play_my_playlist_by_name(monkeypatch):
    db = FakeSpotifyDb()
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    monkeypatch.setattr(spotify_service, "get_user_access_token", _async_return("token"))
    monkeypatch.setattr(
        spotify_service,
        "list_user_playlists",
        _async_return([{"name": "Latino", "uri": "spotify:playlist:abc"}]),
    )
    monkeypatch.setattr(
        spotify_service,
        "find_playlist_uri_by_name",
        lambda q, playlists: ("spotify:playlist:abc", "Latino"),
    )
    monkeypatch.setattr(
        spotify_service,
        "list_user_devices",
        _async_return([{"id": "d1", "name": "Phone"}]),
    )
    monkeypatch.setattr(spotify_service, "start_playback", _async_return(True))

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="play my playlist latino",
        extra_context={},
    )

    assert out == "Playing playlist Latino on Phone."


@pytest.mark.asyncio
async def test_pending_playlist_uri_uses_context_playback(monkeypatch):
    db = FakeSpotifyDb()
    db.pending = {
        "track_uri": "spotify:playlist:abc123",
        "devices_json": json.dumps([{"id": "d1", "name": "Phone"}]),
    }
    monkeypatch.setattr(spotify_service, "get_db", lambda: db)
    seen: dict = {}

    async def _start_capture(*args, **kwargs):
        seen.update(kwargs)
        return True

    monkeypatch.setattr(spotify_service, "start_playback", _start_capture)

    out = await spotify_service.SpotifyService.handle_message(
        user_id="default",
        text="1",
        extra_context={},
    )

    assert out == "Playing on Phone."
    assert seen.get("context_uri") == "spotify:playlist:abc123"
    assert seen.get("track_uri") is None
