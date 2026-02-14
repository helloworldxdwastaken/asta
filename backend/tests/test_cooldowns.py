import pytest

from app.cooldowns import is_cooldown_ready, mark_cooldown_now


class _FakeDb:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get_system_config(self, key: str) -> str | None:
        return self._store.get(key)

    async def set_system_config(self, key: str, value: str) -> None:
        self._store[key] = value


@pytest.mark.asyncio
async def test_cooldown_blocks_until_window_passes(monkeypatch):
    db = _FakeDb()
    now_values = [1000, 1005, 1011]

    monkeypatch.setattr("app.cooldowns.time.time", lambda: now_values.pop(0))

    assert await is_cooldown_ready(db, "default", "gif_reply", 10) is True
    await mark_cooldown_now(db, "default", "gif_reply")
    assert await is_cooldown_ready(db, "default", "gif_reply", 10) is False
    assert await is_cooldown_ready(db, "default", "gif_reply", 10) is True


@pytest.mark.asyncio
async def test_cooldown_is_scoped_by_action_and_user(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr("app.cooldowns.time.time", lambda: 2000)
    await mark_cooldown_now(db, "default", "gif_reply")

    assert await is_cooldown_ready(db, "default", "gif_reply", 60) is False
    assert await is_cooldown_ready(db, "default", "telegram_auto_reaction", 60) is True
    assert await is_cooldown_ready(db, "another-user", "gif_reply", 60) is True
