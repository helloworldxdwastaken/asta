"""Context compaction: summarize long conversation histories.
Inspired by OpenClaw's compaction.ts — adapted for Asta's Python stack.

When conversation history exceeds a token threshold, the oldest messages
are summarized into a compact digest to stay within context limits.
"""
from __future__ import annotations
import logging
from app.providers.base import BaseProvider, Message

logger = logging.getLogger(__name__)

# Token budget: summarize if total exceeds this
DEFAULT_MAX_TOKENS = 3000
# Rough estimate: ~1.3 tokens per word for English text
TOKENS_PER_WORD = 1.3
# Minimum messages before we consider compacting (don't compact tiny histories)
MIN_MESSAGES_TO_COMPACT = 6


def estimate_tokens(text: str) -> int:
    """Rough token estimate from word count. Good enough for budget decisions."""
    return max(1, int(len(text.split()) * TOKENS_PER_WORD))


def estimate_messages_tokens(messages: list[Message]) -> int:
    """Total estimated tokens across all messages."""
    return sum(estimate_tokens(m["content"]) + 4 for m in messages)  # +4 for role/formatting overhead


async def compact_history(
    messages: list[Message],
    provider: BaseProvider,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    **kwargs,
) -> list[Message]:
    """Compact conversation history if it exceeds the token budget.

    Strategy:
    - If total tokens <= max_tokens or < MIN_MESSAGES_TO_COMPACT: return unchanged
    - Split into old and recent halves
    - Summarize old messages using the AI provider
    - Return [summary_message] + recent_messages
    """
    if len(messages) < MIN_MESSAGES_TO_COMPACT:
        return messages

    total = estimate_messages_tokens(messages)
    if total <= max_tokens:
        return messages

    # Split: summarize the older half, keep the recent half intact
    split_point = len(messages) // 2
    old_msgs = messages[:split_point]
    recent_msgs = messages[split_point:]

    # Build a summary prompt
    conversation_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in old_msgs
    )

    summary_prompt: list[Message] = [
        {
            "role": "user",
            "content": (
                "Summarize the following conversation history into a brief, factual digest. "
                "Keep important facts, decisions, and context. Be concise (2-4 sentences max). "
                "Do NOT add greetings or commentary — only the summary.\n\n"
                f"--- CONVERSATION ---\n{conversation_text}\n--- END ---"
            ),
        }
    ]

    try:
        summary = await provider.chat(summary_prompt, **kwargs)
        # Make sure we got a real summary, not an error
        from app.providers.fallback import is_error_reply
        if is_error_reply(summary):
            logger.warning("Compaction summary failed (error reply), keeping full history")
            return messages
        if not summary.strip():
            return messages
    except Exception as e:
        logger.warning("Compaction failed (%s), keeping full history", e)
        return messages

    logger.info(
        "Compacted %d messages (%d tokens) → summary + %d recent messages",
        len(old_msgs), estimate_messages_tokens(old_msgs), len(recent_msgs),
    )

    # Return compacted history
    summary_msg: Message = {
        "role": "assistant",
        "content": f"[Previously discussed] {summary}",
    }
    return [summary_msg] + recent_msgs
