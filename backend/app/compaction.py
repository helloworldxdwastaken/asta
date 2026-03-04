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
    return sum(estimate_tokens(m.get("content") or "") + 4 for m in messages)  # +4 for role/formatting overhead


def compact_tool_rounds(
    messages: list[dict],
    keep_recent_rounds: int = 8,
) -> tuple[list[dict], bool]:
    """Compact old tool-call/result rounds to reduce context size in the tool loop.

    Keeps the preamble (system + user messages before any tool rounds) and the
    last ``keep_recent_rounds`` assistant+tool_calls rounds intact. Older rounds
    are replaced with a concise inline summary appended to the last user message.

    No LLM call is made — this is a pure, fast, structural compaction.

    Returns:
        (compacted_messages, did_compact)
    """
    import json as _json

    # Find indices of all assistant messages that started a tool round
    tool_round_starts = [
        i for i, m in enumerate(messages)
        if m.get("role") == "assistant" and m.get("tool_calls")
    ]

    if len(tool_round_starts) <= keep_recent_rounds:
        return messages, False

    cutoff_idx = tool_round_starts[-keep_recent_rounds]
    first_tool_idx = tool_round_starts[0]

    preamble = messages[:first_tool_idx]   # system + user turns before any tool use
    to_compact = messages[first_tool_idx:cutoff_idx]  # old rounds → summarise
    to_keep = messages[cutoff_idx:]                   # recent rounds → keep intact

    # Build a concise text summary of the compacted rounds
    summary_lines: list[str] = []
    for msg in to_compact:
        role = msg.get("role", "")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in (msg.get("tool_calls") or []):
                fn = tc.get("function") or {}
                name = fn.get("name", "tool")
                args_raw = fn.get("arguments") or "{}"
                try:
                    args = _json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    main_arg = (
                        args.get("query") or args.get("url") or args.get("path") or
                        args.get("command") or args.get("action") or ""
                    )
                    arg_hint = str(main_arg)[:80] if main_arg else ""
                except Exception:
                    arg_hint = ""
                summary_lines.append(f"• {name}({arg_hint})")
        elif role == "tool":
            content = (msg.get("content") or "")[:150].replace("\n", " ")
            if content:
                summary_lines.append(f"  → {content}")

    n_rounds = sum(
        1 for m in to_compact if m.get("role") == "assistant" and m.get("tool_calls")
    )
    summary_text = (
        f"\n\n[COMPACTED: {n_rounds} prior tool rounds]\n"
        + "\n".join(summary_lines)
        + "\n[END COMPACTED HISTORY]"
    )

    # Append summary to the last user message in preamble so we don't create
    # consecutive user messages (which Anthropic rejects).
    compacted_preamble = list(preamble)
    for idx in range(len(compacted_preamble) - 1, -1, -1):
        if compacted_preamble[idx].get("role") == "user":
            original = compacted_preamble[idx].get("content") or ""
            compacted_preamble[idx] = {
                **compacted_preamble[idx],
                "content": original + summary_text,
            }
            break
    else:
        # No user message in preamble — add one so to_keep (starting with assistant) is valid
        compacted_preamble.append({"role": "user", "content": summary_text.strip()})

    return compacted_preamble + list(to_keep), True


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
        from app.context_helpers import _is_error_reply
        if _is_error_reply(summary):
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
