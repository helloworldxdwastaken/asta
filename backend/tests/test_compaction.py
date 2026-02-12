"""Tests for context compaction."""
import asyncio
import pytest
from app.compaction import estimate_tokens, estimate_messages_tokens, MIN_MESSAGES_TO_COMPACT, DEFAULT_MAX_TOKENS


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 1

    def test_short(self):
        tokens = estimate_tokens("hello world")
        assert tokens >= 2

    def test_longer(self):
        text = "This is a moderately long sentence with several words in it."
        tokens = estimate_tokens(text)
        assert 10 < tokens < 20


class TestEstimateMessagesTokens:
    def test_empty(self):
        assert estimate_messages_tokens([]) == 0

    def test_single(self):
        msgs = [{"role": "user", "content": "hello"}]
        tokens = estimate_messages_tokens(msgs)
        assert tokens > 0

    def test_multiple(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there, how are you doing today?"},
        ]
        tokens = estimate_messages_tokens(msgs)
        assert tokens > estimate_messages_tokens(msgs[:1])


class TestCompactHistoryThreshold:
    """Test that compact_history returns messages unchanged when under threshold."""

    @pytest.mark.asyncio
    async def test_short_history_unchanged(self):
        """Messages below MIN_MESSAGES_TO_COMPACT should pass through unchanged."""
        from unittest.mock import AsyncMock
        from app.compaction import compact_history

        mock_provider = AsyncMock()
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello!"},
        ]
        result = await compact_history(msgs, mock_provider)
        assert result == msgs
        mock_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_token_limit_unchanged(self):
        """Even with enough messages, if under token limit, no compaction."""
        from unittest.mock import AsyncMock
        from app.compaction import compact_history

        mock_provider = AsyncMock()
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ] * 4  # 8 messages, but very short
        result = await compact_history(msgs, mock_provider, max_tokens=99999)
        assert result == msgs
        mock_provider.chat.assert_not_called()
