from __future__ import annotations

import pytest

from app.channels import telegram_bot


class _FakeMessage:
    def __init__(self):
        self.texts: list[str] = []
        self.photos: list[tuple[bytes | str, str | None]] = []
        self.animations: list[str] = []

    async def reply_text(self, text: str, **kwargs):
        self.texts.append(text)

    async def reply_photo(self, photo=None, caption: str | None = None, **kwargs):
        if isinstance(photo, str):
            payload: bytes | str = photo
        elif hasattr(photo, "getvalue"):
            payload = photo.getvalue()
        elif hasattr(photo, "read"):
            payload = photo.read()
        else:
            payload = b""
        self.photos.append((payload, caption))

    async def reply_animation(self, animation: str, **kwargs):
        self.animations.append(animation)


@pytest.mark.asyncio
async def test_send_markdown_media_reply_data_url_sends_photo_and_text():
    msg = _FakeMessage()
    reply = "Here you go\n![cyborg](data:image/png;base64,aGVsbG8=)"

    sent = await telegram_bot._send_markdown_media_reply(msg, reply, user_id="u")

    assert sent is True
    assert any("Here you go" in t for t in msg.texts)
    assert len(msg.photos) == 1
    assert msg.photos[0][0] == b"hello"
    assert msg.photos[0][1] == "cyborg"
    assert not msg.animations


@pytest.mark.asyncio
async def test_send_markdown_media_reply_gif_sends_animation():
    msg = _FakeMessage()
    reply = "lol\n![fun](https://media.giphy.com/media/abc123/giphy.gif)"

    sent = await telegram_bot._send_markdown_media_reply(msg, reply, user_id="u")

    assert sent is True
    assert len(msg.animations) == 1
    assert msg.animations[0].endswith(".gif")
