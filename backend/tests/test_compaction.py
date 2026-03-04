"""Tests for context compaction."""
import asyncio
import pytest
from app.compaction import (
    estimate_tokens,
    estimate_messages_tokens,
    MIN_MESSAGES_TO_COMPACT,
    DEFAULT_MAX_TOKENS,
    compact_tool_rounds,
)


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


def _make_tool_round(tool_name: str, arg: str, result: str, idx: int) -> list[dict]:
    """Helper: build one assistant+tool_calls + tool_result round."""
    tc_id = f"call_{idx}"
    return [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": tc_id, "function": {"name": tool_name, "arguments": f'{{"query": "{arg}"}}'}}],
        },
        {"role": "tool", "tool_call_id": tc_id, "content": result},
    ]


class TestCompactToolRounds:
    def test_no_compaction_below_threshold(self):
        """Fewer rounds than keep_recent_rounds → unchanged."""
        msgs = [{"role": "user", "content": "find competitors"}]
        for i in range(5):
            msgs.extend(_make_tool_round("web_search", f"query {i}", f"result {i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=8)
        assert not did_compact
        assert result == msgs

    def test_compacts_when_above_threshold(self):
        """More rounds than keep_recent_rounds → old rounds summarised."""
        msgs = [{"role": "user", "content": "find competitors"}]
        for i in range(12):
            msgs.extend(_make_tool_round("web_search", f"query {i}", f"result {i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=4)
        assert did_compact
        # Should have fewer messages than original
        assert len(result) < len(msgs)

    def test_keeps_recent_rounds_intact(self):
        """The last keep_recent_rounds assistant+tool messages must survive unchanged."""
        msgs = [{"role": "user", "content": "task"}]
        for i in range(10):
            msgs.extend(_make_tool_round("web_search", f"q{i}", f"r{i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=3)
        assert did_compact
        # Last 3 rounds = 6 messages (3 * [assistant, tool])
        # The last 6 messages in result must match the last 6 in original
        assert result[-6:] == msgs[-6:]

    def test_summary_appended_to_user_message(self):
        """Compacted summary is appended to the original user message content."""
        msgs = [{"role": "user", "content": "find competitors"}]
        for i in range(10):
            msgs.extend(_make_tool_round("web_search", f"site{i}", f"found site{i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=3)
        assert did_compact
        user_msg = next(m for m in result if m.get("role") == "user")
        assert "find competitors" in user_msg["content"]
        assert "COMPACTED" in user_msg["content"]
        assert "web_search" in user_msg["content"]

    def test_no_consecutive_user_messages(self):
        """Result must never have two consecutive user messages."""
        msgs = [{"role": "user", "content": "task"}]
        for i in range(12):
            msgs.extend(_make_tool_round("web_search", f"q{i}", f"r{i}", i))
        result, _ = compact_tool_rounds(msgs, keep_recent_rounds=4)
        for i in range(len(result) - 1):
            assert not (result[i].get("role") == "user" and result[i + 1].get("role") == "user"), \
                f"Consecutive user messages at index {i}"

    def test_valid_structure_starts_user_then_assistant(self):
        """After compaction, user msg → assistant+tool_calls is valid for Anthropic."""
        msgs = [{"role": "user", "content": "task"}]
        for i in range(10):
            msgs.extend(_make_tool_round("web_search", f"q{i}", f"r{i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=3)
        assert did_compact
        # Find the user message and check the next is assistant+tool_calls
        for i, m in enumerate(result):
            if m.get("role") == "user":
                if i + 1 < len(result):
                    assert result[i + 1].get("role") == "assistant"

    def test_handles_none_content_in_tool_calls(self):
        """Messages with None content (common in tool-call assistant turns) don't crash."""
        msgs = [{"role": "user", "content": "task"}]
        for i in range(10):
            tc_id = f"call_{i}"
            msgs.append({
                "role": "assistant",
                "content": None,  # None content — must be handled
                "tool_calls": [{"id": tc_id, "function": {"name": "web_search", "arguments": "{}"}}],
            })
            msgs.append({"role": "tool", "tool_call_id": tc_id, "content": f"result {i}"})
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=3)
        assert did_compact
        assert len(result) > 0

    def test_tool_names_appear_in_summary(self):
        """Tool names from compacted rounds appear in the summary text."""
        msgs = [{"role": "user", "content": "research task"}]
        for i in range(10):
            msgs.extend(_make_tool_round("web_fetch", f"https://example{i}.com", f"page content {i}", i))
        result, did_compact = compact_tool_rounds(msgs, keep_recent_rounds=3)
        assert did_compact
        user_msg = next(m for m in result if m.get("role") == "user")
        assert "web_fetch" in user_msg["content"]
