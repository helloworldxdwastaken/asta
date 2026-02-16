from unittest.mock import patch

import pytest

from app.audio_notes import process_audio_to_notes
from app.db import get_db
from app.providers.base import ProviderError, ProviderResponse


class _DummyProviderOk:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content="Formatted meeting notes.")


class _DummyProviderErr:
    name = "openai"

    async def chat(self, messages, **kwargs):
        return ProviderResponse(
            content="",
            error=ProviderError.RATE_LIMIT,
            error_message="rate limited",
        )


@pytest.mark.asyncio
async def test_audio_notes_accepts_provider_response_object():
    db = get_db()
    await db.connect()
    user_id = "test-audio-provider-response-ok"
    await db.set_skill_enabled(user_id, "audio_notes", True)

    with (
        patch("app.audio_notes.transcribe_audio", return_value="hello transcript"),
        patch("app.audio_notes.get_provider", side_effect=lambda _name: _DummyProviderOk()),
    ):
        out = await process_audio_to_notes(
            b"dummy",
            filename="voice.wav",
            instruction="meeting notes",
            user_id=user_id,
        )

    assert out["transcript"] == "hello transcript"
    assert out["formatted"] == "Formatted meeting notes."


@pytest.mark.asyncio
async def test_audio_notes_returns_format_error_when_provider_response_has_error():
    db = get_db()
    await db.connect()
    user_id = "test-audio-provider-response-error"
    await db.set_skill_enabled(user_id, "audio_notes", True)

    with (
        patch("app.audio_notes.transcribe_audio", return_value="hello transcript"),
        patch("app.audio_notes.get_provider", side_effect=lambda _name: _DummyProviderErr()),
    ):
        out = await process_audio_to_notes(
            b"dummy",
            filename="voice.wav",
            instruction="meeting notes",
            user_id=user_id,
        )

    assert out["transcript"] == "hello transcript"
    assert out["formatted"].startswith("Formatting failed:")
