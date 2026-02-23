"""Context compaction: summarize long conversation histories.
Inspired by OpenClaw's compaction.ts — adapted for Asta's Python stack.

When conversation history exceeds a token threshold, the oldest messages
are summarized into a compact digest to stay within context limits.
"""
from __future__ import annotations
import logging
from app.providers.base import BaseProvider, Message

logger = logging.getLogger(__name__)

# Rough estimate: ~1.3 tokens per word for English text
TOKENS_PER_WORD = 1.3
# Minimum messages before we consider compacting (don't compact tiny histories)
MIN_MESSAGES_TO_COMPACT = 6
# Fraction of the model's context window to use as the compaction threshold.
# We compact when history > 40% of the context window.
COMPACTION_CONTEXT_SHARE = 0.40
# Fallback budget for unknown models (tokens): conservative default
DEFAULT_MAX_TOKENS = 4_000
# Floor: never compact below 1k tokens (avoids thrashing on tiny models)
COMPACTION_FLOOR_TOKENS = 1_000
# Ceiling: never compact above 80k tokens (large-context models don't need it often)
COMPACTION_CEILING_TOKENS = 80_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate from word count. Good enough for budget decisions."""
    return max(1, int(len(text.split()) * TOKENS_PER_WORD))


def estimate_messages_tokens(messages: list[Message]) -> int:
    """Total estimated tokens across all messages."""
    return sum(estimate_tokens(m["content"]) + 4 for m in messages)  # +4 for role/formatting overhead


def _compute_compaction_budget(
    model: str | None = None,
    provider: str | None = None,
    max_tokens: int | None = None,
) -> int:
    """Return the compaction token budget for the given model.

    If an explicit max_tokens is passed, it takes precedence.
    Otherwise, derive from the model's context window (40% share).
    Falls back to DEFAULT_MAX_TOKENS for unknown models.
    """
    if max_tokens is not None and max_tokens > 0:
        return max_tokens
    from app.adaptive_paging import _lookup_context_tokens
    tokens = _lookup_context_tokens(model, provider)
    if tokens and tokens > 0:
        budget = int(tokens * COMPACTION_CONTEXT_SHARE)
        return max(COMPACTION_FLOOR_TOKENS, min(budget, COMPACTION_CEILING_TOKENS))
    return DEFAULT_MAX_TOKENS


async def compact_history(
    messages: list[Message],
    provider: BaseProvider,
    max_tokens: int | None = None,
    model: str | None = None,
    provider_name: str | None = None,
    **kwargs,
) -> list[Message]:
    """Compact conversation history if it exceeds the model-aware token budget.

    Strategy:
    - If total tokens <= budget or < MIN_MESSAGES_TO_COMPACT: return unchanged
    - Split into old and recent halves
    - Summarize old messages using the AI provider
    - Return [summary_message] + recent_messages

    Args:
        max_tokens:    Explicit budget override (tokens). If None, derived from model.
        model:         Model name for context-window lookup.
        provider_name: Provider name for context-window lookup.
    """
    if len(messages) < MIN_MESSAGES_TO_COMPACT:
        return messages

    budget = _compute_compaction_budget(model, provider_name, max_tokens)
    total = estimate_messages_tokens(messages)
    if total <= budget:
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
        "Compacted %d messages (%d tokens, budget=%d) → summary + %d recent messages",
        len(old_msgs), estimate_messages_tokens(old_msgs), budget, len(recent_msgs),
    )

    # Return compacted history
    summary_msg: Message = {
        "role": "assistant",
        "content": f"[Previously discussed] {summary}",
    }
    return [summary_msg] + recent_msgs
