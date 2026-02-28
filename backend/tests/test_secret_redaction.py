import pytest

from app.handler import _redact_sensitive_reply_content


class _FakeDb:
    def __init__(self, values: dict[str, str]):
        self._values = values

    async def get_stored_api_key(self, key_name: str) -> str | None:
        return self._values.get(key_name)


@pytest.mark.asyncio
async def test_redact_sensitive_reply_content_masks_key_values_and_notion_tokens():
    db = _FakeDb({"notion_api_key": "ntn_real_secret_123456"})
    redacted, changed = await _redact_sensitive_reply_content(
        "Token check: ntn_real_secret_123456 and fallback ntn_abcdefghijklmnop123456",
        db,
    )
    assert changed is True
    assert "ntn_real_secret_123456" not in redacted
    assert "ntn_abcdefghijklmnop123456" not in redacted
    assert "[REDACTED_SECRET]" in redacted or "[REDACTED_NOTION_TOKEN]" in redacted
