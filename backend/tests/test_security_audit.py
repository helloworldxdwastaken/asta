import pytest

from app.config import get_settings
from app.db import get_db
from app.security_audit import collect_security_warnings


@pytest.mark.asyncio
async def test_security_audit_flags_exec_full_and_invalid_telegram_allowlist(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "full")
    monkeypatch.setenv("ASTA_TELEGRAM_ALLOWED_IDS", "@name")
    get_settings.cache_clear()

    db = get_db()
    await db.connect()
    result = await collect_security_warnings(db, user_id="default")

    assert result["has_critical"] is True
    ids = {f["id"] for f in result["findings"]}
    assert "exec.mode.full" in ids
    assert "telegram.allowlist.invalid_entries" in ids
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_security_audit_flags_risky_allowlist_bins(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "allowlist")
    monkeypatch.setenv("ASTA_EXEC_ALLOWED_BINS", "memo,python,curl")
    monkeypatch.delenv("ASTA_TELEGRAM_ALLOWED_IDS", raising=False)
    get_settings.cache_clear()

    db = get_db()
    await db.connect()
    result = await collect_security_warnings(db, user_id="default")
    ids = {f["id"] for f in result["findings"]}
    assert "exec.allowlist.risky_bins" in ids
    get_settings.cache_clear()

