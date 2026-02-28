"""Thinking, reasoning, and stream-delta utilities extracted from handler.py.

All functions here are pure (no DB, no async I/O) and can be imported by
any module without circular-import risk.
"""
from __future__ import annotations

import re
from typing import Any

from app.thinking_capabilities import supports_xhigh_thinking

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_THINK_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh")
_REASONING_MODES = ("off", "on", "stream")
_FINAL_MODES = ("off", "strict")
# OpenClaw-style: Ollama should not require strict <final> tags.
_STRICT_FINAL_UNSUPPORTED_PROVIDERS = frozenset({"ollama"})

_THINK_DIRECTIVE_PATTERN = re.compile(
    r"(?:^|\s)/(?:thinking|think|t)(?=$|\s|:)",
    re.IGNORECASE,
)
_REASONING_DIRECTIVE_PATTERN = re.compile(
    r"(?:^|\s)/(?:reasoning|reason)(?=$|\s|:)",
    re.IGNORECASE,
)
_REASONING_QUICK_TAG_RE = re.compile(
    r"<\s*/?\s*(?:think(?:ing)?|thought|antthinking|final)\b",
    re.IGNORECASE,
)
_REASONING_FINAL_TAG_RE = re.compile(
    r"<\s*/?\s*final\b[^<>]*>",
    re.IGNORECASE,
)
_REASONING_THINK_TAG_RE = re.compile(
    r"<\s*(/?)\s*(?:think(?:ing)?|thought|antthinking)\b[^<>]*>",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Stream-delta helpers
# ---------------------------------------------------------------------------

def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from text (case-insensitive, greedy)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()


def _longest_common_prefix_size(left: str, right: str) -> int:
    max_len = min(len(left), len(right))
    idx = 0
    while idx < max_len and left[idx] == right[idx]:
        idx += 1
    return idx


def _largest_suffix_prefix_overlap(left: str, right: str, *, max_scan: int = 2048) -> int:
    """Return overlap size where suffix(left) == prefix(right)."""
    if not left or not right:
        return 0
    cap = min(len(left), len(right), max_scan)
    for size in range(cap, 0, -1):
        if left.endswith(right[:size]):
            return size
    return 0


def _merge_stream_source_text(current: str, incoming: str) -> str:
    """Merge provider stream text while tolerating duplicated or full-content chunks.

    Providers should send text deltas, but some fallbacks can emit snapshots. This keeps
    the accumulated source text monotonic and avoids duplicate appends.
    """
    cur = current or ""
    inc = incoming or ""
    if not inc:
        return cur
    if not cur:
        return inc

    # Incoming is full snapshot that already includes current content.
    if inc.startswith(cur):
        return inc
    # Incoming is duplicate/older subset.
    if cur.startswith(inc) or inc in cur:
        return cur

    overlap = _largest_suffix_prefix_overlap(cur, inc)
    if overlap > 0:
        return cur + inc[overlap:]

    # Snapshot style fallback that still contains current text somewhere.
    if cur in inc and len(inc) >= len(cur):
        return inc

    return cur + inc


def _compute_incremental_delta(previous: str, current: str) -> str:
    prev = previous or ""
    cur = current or ""
    if not cur:
        return ""
    if cur.startswith(prev):
        return cur[len(prev):]
    common = _longest_common_prefix_size(prev, cur)
    if common > 0:
        return cur[common:]
    return cur


def _plan_stream_text_update(
    *,
    previous: str,
    current: str,
    allow_rewrite: bool = False,
) -> tuple[bool, str, bool]:
    """Plan a streaming text update.

    Returns (should_emit, delta, rewrote_non_prefix).
    """
    prev = previous or ""
    # Only strip leading whitespace — trailing newlines are part of content
    cur = (current or "").lstrip()
    if not cur or cur == prev:
        return False, "", False
    if prev and not cur.startswith(prev):
        if not allow_rewrite:
            return False, "", False
        return True, cur, True
    delta = _compute_incremental_delta(prev, cur)
    if not delta and cur == prev:
        return False, "", False
    return True, delta or cur, False


# ---------------------------------------------------------------------------
# Thinking / reasoning instructions (system prompt generation)
# ---------------------------------------------------------------------------

def _thinking_instruction(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv == "off":
        return ""
    if lv == "minimal":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: minimal. Keep reasoning very brief, but still verify critical facts "
            "and tool outputs before answering."
        )
    if lv == "low":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: low. Spend a bit more effort before answering. "
            "Double-check tool outputs and avoid assumptions."
        )
    if lv == "medium":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: medium. Plan briefly before answering, validate tool output, "
            "and prefer factual, verified replies over quick guesses."
        )
    if lv == "high":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: high. Do deeper internal planning and verification. "
            "For external-state claims (files, reminders, notes, statuses), rely on real tool results only."
        )
    if lv == "xhigh":
        return (
            "\n\n[THINKING]\n"
            "Thinking level: xhigh. Use maximum deliberate planning and strict verification. "
            "For any external-state claim, require concrete tool evidence before asserting results."
        )
    return ""


def _normalize_thinking_level(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    collapsed = re.sub(r"[\s_-]+", "", key)
    if collapsed in ("xhigh", "extrahigh"):
        return "xhigh"
    if key in ("off",):
        return "off"
    if key in ("on", "enable", "enabled"):
        return "low"
    if key in ("min", "minimal"):
        return "minimal"
    if key in ("low", "thinkhard", "think-hard", "think_hard"):
        return "low"
    if key in ("mid", "med", "medium", "thinkharder", "think-harder", "harder"):
        return "medium"
    if key in ("high", "ultra", "ultrathink", "thinkhardest", "highest", "max"):
        return "high"
    if key in ("think",):
        return "minimal"
    return None


def _normalize_reasoning_mode(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in ("off", "false", "no", "0", "hide", "hidden", "disable", "disabled"):
        return "off"
    if key in ("on", "true", "yes", "1", "show", "visible", "enable", "enabled"):
        return "on"
    if key in ("stream", "streaming", "draft", "live"):
        return "stream"
    return None


def _parse_inline_thinking_directive(text: str) -> tuple[bool, str | None, str | None, str]:
    """Parse OpenClaw-style inline thinking directive in mixed text.

    Returns (matched, normalized_level_or_none, raw_level_or_none, cleaned_text).
    """
    raw = (text or "")
    m = _THINK_DIRECTIVE_PATTERN.search(raw)
    if not m:
        return False, None, None, raw
    start, end = m.span()
    i = end
    length = len(raw)
    while i < length and raw[i].isspace():
        i += 1
    if i < length and raw[i] == ":":
        i += 1
        while i < length and raw[i].isspace():
            i += 1
    arg_start = i
    while i < length and (raw[i].isalpha() or raw[i] in "-_"):
        i += 1
    raw_level = (raw[arg_start:i] or "").strip().lower() or None
    level = _normalize_thinking_level(raw_level)
    cleaned = (raw[:start] + " " + raw[i:]).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return True, level, raw_level, cleaned


def _parse_inline_reasoning_directive(text: str) -> tuple[bool, str | None, str | None, str]:
    """Parse OpenClaw-style inline reasoning directive in mixed text.

    Returns (matched, normalized_mode_or_none, raw_mode_or_none, cleaned_text).
    """
    raw = (text or "")
    m = _REASONING_DIRECTIVE_PATTERN.search(raw)
    if not m:
        return False, None, None, raw
    start, end = m.span()
    i = end
    length = len(raw)
    while i < length and raw[i].isspace():
        i += 1
    if i < length and raw[i] == ":":
        i += 1
        while i < length and raw[i].isspace():
            i += 1
    arg_start = i
    while i < length and (raw[i].isalpha() or raw[i] in "-_"):
        i += 1
    raw_mode = (raw[arg_start:i] or "").strip().lower() or None
    mode = _normalize_reasoning_mode(raw_mode)
    cleaned = (raw[:start] + " " + raw[i:]).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return True, mode, raw_mode, cleaned


def _supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    return supports_xhigh_thinking(provider, model)


def _format_thinking_options(provider: str | None, model: str | None) -> str:
    options = ["off", "minimal", "low", "medium", "high"]
    if _supports_xhigh_thinking(provider, model):
        options.append("xhigh")
    return ", ".join(options)


def _reasoning_instruction(mode: str) -> str:
    rm = (mode or "off").strip().lower()
    if rm not in ("on", "stream"):
        return ""
    return (
        "\n\n[REASONING]\n"
        "Before your final answer, you MUST include exactly one brief rationale block inside "
        "<think>...</think>. Do not skip it in this mode. "
        "Keep it short (1-3 lines), factual, and directly tied to tool results when tools are used."
    )


def _final_tag_instruction(mode: str) -> str:
    fm = (mode or "off").strip().lower()
    if fm != "strict":
        return ""
    return (
        "\n\n[FINAL]\n"
        "You MUST wrap user-visible output in exactly one <final>...</final> block. "
        "Text outside <final> may be hidden."
    )


# ---------------------------------------------------------------------------
# Code-region mapping (code-fence and inline-code aware text processing)
# ---------------------------------------------------------------------------

def _parse_fenced_code_regions(text: str) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    open_region: tuple[int, str, int] | None = None
    offset = 0
    line_pattern = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
    length = len(text)

    while offset <= length:
        next_newline = text.find("\n", offset)
        line_end = length if next_newline == -1 else next_newline
        line = text[offset:line_end]
        match = line_pattern.match(line)
        if match:
            marker = match.group(2)
            marker_char = marker[0]
            marker_len = len(marker)
            if open_region is None:
                open_region = (offset, marker_char, marker_len)
            elif open_region[1] == marker_char and marker_len >= open_region[2]:
                regions.append((open_region[0], line_end))
                open_region = None
        if next_newline == -1:
            break
        offset = next_newline + 1

    if open_region is not None:
        regions.append((open_region[0], length))

    regions.sort(key=lambda region: region[0])
    return regions


def _is_inside_code_region(index: int, regions: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in regions)


def _parse_inline_code_regions(text: str, fenced_regions: list[tuple[int, int]]) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    open_ticks = 0
    open_start = -1
    i = 0
    fenced_index = 0
    length = len(text)

    while i < length:
        while fenced_index < len(fenced_regions) and i >= fenced_regions[fenced_index][1]:
            fenced_index += 1
        if fenced_index < len(fenced_regions):
            fenced_start, fenced_end = fenced_regions[fenced_index]
            if fenced_start <= i < fenced_end:
                i = fenced_end
                continue
        if text[i] != "`":
            i += 1
            continue

        run_start = i
        run_length = 0
        while i < length and text[i] == "`":
            run_length += 1
            i += 1

        if open_ticks == 0:
            open_ticks = run_length
            open_start = run_start
        elif run_length == open_ticks:
            regions.append((open_start, i))
            open_ticks = 0
            open_start = -1

    if open_ticks > 0 and open_start >= 0:
        regions.append((open_start, length))

    regions.sort(key=lambda region: region[0])
    return regions


def _build_code_regions(text: str) -> list[tuple[int, int]]:
    fenced = _parse_fenced_code_regions(text)
    inline = _parse_inline_code_regions(text, fenced)
    regions = fenced + inline
    regions.sort(key=lambda region: region[0])
    return regions


def _strip_pattern_outside_code(
    text: str,
    pattern: re.Pattern[str],
    code_regions: list[tuple[int, int]],
) -> str:
    if not text:
        return text
    output: list[str] = []
    last_index = 0
    for match in pattern.finditer(text):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        output.append(text[last_index:index])
        last_index = match.end()
    output.append(text[last_index:])
    return "".join(output)


# ---------------------------------------------------------------------------
# Reasoning / thinking tag extraction and stripping
# ---------------------------------------------------------------------------

def _apply_reasoning_trim(value: str, mode: str = "both") -> str:
    trim_mode = (mode or "both").strip().lower()
    if trim_mode == "none":
        return value
    if trim_mode == "start":
        return value.lstrip()
    return value.strip()


def _extract_final_tag_content(text: str) -> tuple[str, bool]:
    """Return content inside <final> blocks (code-safe), plus whether a real final tag was seen."""
    raw = (text or "")
    if not raw:
        return "", False
    code_regions = _build_code_regions(raw)
    in_final = False
    saw_final = False
    last_index = 0
    out_parts: list[str] = []

    for match in _REASONING_FINAL_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        tag_text = match.group(0) or ""
        is_close = bool(re.match(r"<\s*/", tag_text))
        if not in_final and not is_close:
            in_final = True
            saw_final = True
            last_index = match.end()
            continue
        if in_final and is_close:
            out_parts.append(raw[last_index:index])
            in_final = False
            last_index = match.end()

    if in_final:
        out_parts.append(raw[last_index:])

    return "".join(out_parts), saw_final


def _strip_reasoning_tags_from_text(
    text: str,
    *,
    mode: str = "strict",  # strict | preserve
    trim: str = "both",    # none | start | both
    strict_final: bool = False,
) -> str:
    """OpenClaw-style thinking/final tag stripping with code-span safety."""
    raw = (text or "")
    if not raw:
        return raw
    if not _REASONING_QUICK_TAG_RE.search(raw):
        if strict_final:
            return ""
        return _apply_reasoning_trim(raw, trim)

    cleaned = raw
    code_regions = _build_code_regions(cleaned)

    result_parts: list[str] = []
    in_thinking = False
    last_index = 0

    for match in _REASONING_THINK_TAG_RE.finditer(cleaned):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))

        if not in_thinking:
            result_parts.append(cleaned[last_index:index])
            if not is_close:
                in_thinking = True
        elif is_close:
            in_thinking = False

        last_index = match.end()

    mode_norm = (mode or "strict").strip().lower()
    if (not in_thinking) or mode_norm == "preserve":
        result_parts.append(cleaned[last_index:])

    without_thinking = "".join(result_parts)

    if strict_final:
        final_only, saw_final = _extract_final_tag_content(without_thinking)
        if not saw_final:
            return ""
        final_code_regions = _build_code_regions(final_only)
        final_only = _strip_pattern_outside_code(final_only, _REASONING_FINAL_TAG_RE, final_code_regions)
        return _apply_reasoning_trim(final_only, trim)

    pre_code_regions = _build_code_regions(without_thinking)
    without_final_tags = _strip_pattern_outside_code(
        without_thinking,
        _REASONING_FINAL_TAG_RE,
        pre_code_regions,
    )
    return _apply_reasoning_trim(without_final_tags, trim)


def _extract_thinking_from_tagged_text(text: str) -> str:
    """Extract text inside closed <think>/<thinking>/<thought>/<antthinking> blocks."""
    raw = (text or "")
    if not raw:
        return ""
    if not _REASONING_QUICK_TAG_RE.search(raw):
        return ""

    code_regions = _build_code_regions(raw)
    reasoning_parts: list[str] = []
    in_thinking = False
    reasoning_start = 0

    for match in _REASONING_THINK_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))

        if not in_thinking and not is_close:
            in_thinking = True
            reasoning_start = match.end()
            continue

        if in_thinking and is_close:
            chunk = raw[reasoning_start:index].strip()
            if chunk:
                reasoning_parts.append(chunk)
            in_thinking = False

    return "\n\n".join(reasoning_parts).strip()


def _extract_thinking_from_tagged_stream(text: str) -> str:
    """Streaming-friendly extraction: closed blocks first, otherwise last open block tail."""
    raw = (text or "")
    if not raw:
        return ""
    if not _REASONING_QUICK_TAG_RE.search(raw):
        return ""

    closed = _extract_thinking_from_tagged_text(raw)
    if closed:
        return closed

    code_regions = _build_code_regions(raw)
    last_open_start: int | None = None
    last_open_end: int | None = None
    last_close_start: int | None = None

    for match in _REASONING_THINK_TAG_RE.finditer(raw):
        index = match.start()
        if _is_inside_code_region(index, code_regions):
            continue
        is_close = bool(match.group(1))
        if is_close:
            last_close_start = index
        else:
            last_open_start = index
            last_open_end = match.end()

    if last_open_start is None or last_open_end is None:
        return ""
    if last_close_start is not None and last_close_start > last_open_start:
        return closed

    return raw[last_open_end:].strip()


def _format_reasoning_message(text: str) -> str:
    trimmed = (text or "").strip()
    if not trimmed:
        return ""
    return f"Reasoning:\n{trimmed}"


def _extract_reasoning_blocks(text: str, *, strict_final: bool = False) -> tuple[str, str]:
    raw = (text or "")
    if not raw:
        return "", ""
    final_text = _strip_reasoning_tags_from_text(
        raw,
        mode="strict",
        trim="both",
        strict_final=strict_final,
    )
    reasoning_text = _extract_thinking_from_tagged_text(raw)
    if not reasoning_text:
        reasoning_text = _extract_thinking_from_tagged_stream(raw)
    return final_text, reasoning_text
