"""Parse 'learn about X for Y' / 'learn about X' and duration-only replies (e.g. '30 min')."""
from __future__ import annotations
import re
from typing import Any

# "learn about next.js for 30 minutes", "learn about coffee for 2 hours"
RE_LEARN_ABOUT_WITH_DURATION = re.compile(
    r"learn\s+about\s+(.+?)\s+for\s+(\d+)\s*(min(?:ute)?s?|hr?s?|hours?)\b",
    re.I,
)
# "learn about next.js", "learn about X" (no duration)
RE_LEARN_ABOUT_TOPIC_ONLY = re.compile(
    r"learn\s+about\s+(.+?)$",
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


def parse_learn_about(text: str) -> dict[str, Any] | None:
    """
    If message is 'learn about X for Y', return {topic, duration_minutes, ask_duration: False}.
    If message is 'learn about X' (no duration), return {topic, ask_duration: True}.
    Otherwise return None.
    """
    t = (text or "").strip()
    if not t or len(t) > 500:
        return None

    # With duration first
    m = RE_LEARN_ABOUT_WITH_DURATION.search(t)
    if m:
        topic = (m.group(1) or "").strip()
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
    m = RE_LEARN_ABOUT_TOPIC_ONLY.search(t)
    if m:
        topic = (m.group(1) or "").strip()
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
