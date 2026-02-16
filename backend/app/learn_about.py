"""Parse learning intents and duration-only replies.

Supported intent forms include:
- "learn about X [for Y]"
- "become an expert on X [for Y]"
- "study X [for Y]"
- "research X [for Y]"
"""
from __future__ import annotations
import re
from typing import Any

# Optional polite prefixes, then supported learn verbs.
# Examples:
# - "learn about next.js for 30 minutes"
# - "can you research coffee for 2 hours?"
# - "please become an expert on kubernetes"
_LEARN_PREFIX = r"(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|would\s+you\s+|i\s+want\s+you\s+to\s+)?"
_LEARN_VERB = r"(?:learn\s+about|become\s+(?:an?\s+)?expert\s+on|be\s+(?:an?\s+)?expert\s+on|study|research)"

# Intent with duration: "<verb> <topic> for <N> <unit>"
RE_LEARN_INTENT_WITH_DURATION = re.compile(
    rf"^\s*{_LEARN_PREFIX}{_LEARN_VERB}\s+(.+?)\s+for\s+(\d+)\s*(min(?:ute)?s?|hr?s?|hours?)\s*[?.!]*\s*$",
    re.I,
)

# Intent without duration: "<verb> <topic>"
RE_LEARN_INTENT_TOPIC_ONLY = re.compile(
    rf"^\s*{_LEARN_PREFIX}{_LEARN_VERB}\s+(.+?)\s*[?.!]*\s*$",
    re.I,
)

# Duration-only reply: "30 min", "2 hours", "1 hr"
RE_DURATION_ONLY = re.compile(
    r"^(\d+)\s*(min(?:ute)?s?|hr?s?|hours?)\s*$",
    re.I,
)


def _parse_duration_minutes(num: int, unit: str) -> int:
    u = (unit or "").lower()
    if "hr" in u or "hour" in u:
        return num * 60
    return num


def _normalize_topic(raw: str) -> str:
    topic = (raw or "").strip()
    topic = re.sub(r"\s+", " ", topic)
    # Remove trailing punctuation while keeping meaningful symbols inside topic names.
    topic = topic.rstrip("?.!,;:")
    return topic.strip()


def parse_learn_about(text: str) -> dict[str, Any] | None:
    """
    If message is a supported learn intent with duration, return
    {topic, duration_minutes, ask_duration: False}.
    If message is a supported learn intent without duration, return
    {topic, ask_duration: True}.
    Otherwise return None.
    """
    t = (text or "").strip()
    if not t or len(t) > 500:
        return None

    # With duration first
    m = RE_LEARN_INTENT_WITH_DURATION.match(t)
    if m:
        topic = _normalize_topic(m.group(1) or "")
        if not topic:
            return None
        num, unit = int(m.group(2)), (m.group(3) or "").strip()
        duration_minutes = _parse_duration_minutes(num, unit)
        if duration_minutes <= 0:
            duration_minutes = 30
        if duration_minutes > 24 * 60:  # cap at 24h
            duration_minutes = 24 * 60
        return {"topic": topic, "duration_minutes": duration_minutes, "ask_duration": False}

    # Topic only
    m = RE_LEARN_INTENT_TOPIC_ONLY.match(t)
    if m:
        topic = _normalize_topic(m.group(1) or "")
        if not topic:
            return None
        return {"topic": topic, "ask_duration": True}

    return None


def parse_duration_only(text: str) -> int | None:
    """
    If message is only a duration (e.g. '30 min', '2 hours'), return duration in minutes.
    Otherwise return None.
    """
    t = (text or "").strip()
    if not t or len(t) > 50:
        return None
    m = RE_DURATION_ONLY.match(t)
    if not m:
        return None
    num, unit = int(m.group(1)), (m.group(2) or "").strip()
    minutes = _parse_duration_minutes(num, unit)
    if minutes <= 0:
        return None
    if minutes > 24 * 60:
        minutes = 24 * 60
    return minutes
