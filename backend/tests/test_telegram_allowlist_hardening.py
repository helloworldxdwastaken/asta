from types import SimpleNamespace

from app.channels.telegram_bot import _normalize_allow_bin, _telegram_user_allowed
from app.config import get_settings


def _fake_update(user_id: int):
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id))


def test_telegram_allowlist_parses_numeric_ids_only(monkeypatch):
    monkeypatch.setenv("ASTA_TELEGRAM_ALLOWED_IDS", "tg:123, telegram:456, @name, abc")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.telegram_allowed_ids == {"123", "456"}
    assert settings.telegram_allowlist_invalid == {"@name", "abc"}
    get_settings.cache_clear()


def test_telegram_allowlist_fails_closed_when_configured_but_invalid(monkeypatch):
    monkeypatch.setenv("ASTA_TELEGRAM_ALLOWED_IDS", "@someone")
    get_settings.cache_clear()
    assert _telegram_user_allowed(_fake_update(123456)) is False
    get_settings.cache_clear()


def test_telegram_allowlist_allows_all_when_not_configured(monkeypatch):
    monkeypatch.delenv("ASTA_TELEGRAM_ALLOWED_IDS", raising=False)
    get_settings.cache_clear()
    assert _telegram_user_allowed(_fake_update(123456)) is True
    get_settings.cache_clear()


def test_normalize_allow_bin_handles_paths_and_case():
    assert _normalize_allow_bin("/opt/homebrew/bin/RG") == "rg"
    assert _normalize_allow_bin("memo,") == "memo"
