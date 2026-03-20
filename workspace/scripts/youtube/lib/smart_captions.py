#!/usr/bin/env python3
"""
Smart Captions Engine — word-level highlighting, ASS subtitle generation, caption presets.

Techniques borrowed from AutoSub-Py (NLP keyword coloring) and Subtitle Burner (animation styles).

Usage:
    from lib.smart_captions import generate_captions, CaptionPreset

    # Generate word-level captions with highlighting
    generate_captions(
        video_path="input.mp4",
        output_srt="captions.srt",
        output_ass="captions.ass",
        preset=CaptionPreset.SHORTS,
    )
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# Add ~/.local/bin to PATH (pipx installs whisper there)
_local_bin = Path.home() / ".local" / "bin"
if _local_bin.is_dir() and str(_local_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_local_bin}:{os.environ.get('PATH', '')}"


# ── Caption Presets ────────────────────────────────────────────────────────────

class CaptionPreset(Enum):
    SHORTS = "shorts"        # 1-2 words at a time, bounce, big text (TikTok/Shorts)
    STANDARD = "standard"    # Full line, fade-in, clean (long-form YouTube)
    KARAOKE = "karaoke"      # Full line visible, current word highlighted
    MINIMAL = "minimal"      # Small, bottom, no animation


@dataclass
class CaptionStyle:
    font_name: str = "Arial Black"
    font_size: int = 22
    primary_color: str = "&H00FFFFFF"      # white (AABBGGRR in ASS)
    highlight_color: str = "&H0000FFFF"    # yellow
    outline_color: str = "&H00000000"      # black
    back_color: str = "&H80000000"         # semi-transparent black
    outline_width: int = 3
    shadow_depth: int = 1
    alignment: int = 2                     # 2=bottom-center, 8=top-center, 5=middle
    margin_v: int = 50
    margin_l: int = 40
    margin_r: int = 40
    words_per_group: int = 0               # 0 = full line
    bold: bool = True
    animation: str = "none"                # none, fade, bounce, highlight
    emphasis_color: str = "&H0000FFFF"     # yellow for emphasis words
    number_color: str = "&H00FFFF00"       # cyan for numbers


PRESET_STYLES = {
    CaptionPreset.SHORTS: CaptionStyle(
        font_name="Arial Black",
        font_size=52,
        primary_color="&H00FFFFFF",
        highlight_color="&H0000FFFF",
        emphasis_color="&H000080FF",     # orange for emphasis
        number_color="&H00FFFF00",       # cyan for numbers
        outline_color="&H00000000",
        back_color="&H00000000",         # no background box
        outline_width=5,
        shadow_depth=3,
        alignment=5,          # middle of screen
        margin_v=20,
        words_per_group=2,
        bold=True,
        animation="bounce",
    ),
    CaptionPreset.STANDARD: CaptionStyle(
        font_name="Arial",
        font_size=22,
        primary_color="&H00FFFFFF",
        outline_width=3,
        shadow_depth=1,
        alignment=2,
        margin_v=50,
        words_per_group=0,    # full line
        bold=False,
        animation="fade",
    ),
    CaptionPreset.KARAOKE: CaptionStyle(
        font_name="Arial Black",
        font_size=26,
        primary_color="&H40FFFFFF",        # dimmed white for non-active
        highlight_color="&H0000FFFF",      # bright yellow for active word
        outline_width=3,
        shadow_depth=1,
        alignment=2,
        margin_v=50,
        words_per_group=0,    # full line, but highlight sweeps
        bold=True,
        animation="highlight",
    ),
    CaptionPreset.MINIMAL: CaptionStyle(
        font_name="Arial",
        font_size=18,
        primary_color="&H00FFFFFF",
        outline_width=2,
        shadow_depth=0,
        alignment=2,
        margin_v=30,
        words_per_group=0,
        bold=False,
        animation="none",
    ),
}


# ── Contrast Detection ─────────────────────────────────────────────────────────

def _parse_ass_color(color_str: str) -> tuple[int, int, int]:
    """Parse ASS color (&HAABBGGRR) to (R, G, B). Alpha is ignored."""
    # Strip &H prefix and trailing &
    hex_str = color_str.replace("&H", "").replace("&", "")
    if len(hex_str) == 8:
        # AABBGGRR
        b = int(hex_str[2:4], 16)
        g = int(hex_str[4:6], 16)
        r = int(hex_str[6:8], 16)
    elif len(hex_str) == 6:
        b = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        r = int(hex_str[4:6], 16)
    else:
        return (255, 255, 255)
    return (r, g, b)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.1 relative luminance calculation."""
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colors (1:1 to 21:1)."""
    l1 = _relative_luminance(*color1)
    l2 = _relative_luminance(*color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_caption_contrast(style: CaptionStyle) -> list[str]:
    """
    Check if caption colors meet WCAG AA contrast standards.
    Returns list of warnings (empty = all good).
    """
    warnings = []

    # Parse colors
    primary = _parse_ass_color(style.primary_color)
    outline = _parse_ass_color(style.outline_color)
    highlight = _parse_ass_color(style.highlight_color)
    emphasis = _parse_ass_color(style.emphasis_color)

    # Check primary text vs outline (most important — this is the text readability)
    ratio = _contrast_ratio(primary, outline)
    if ratio < 4.5:
        warnings.append(
            f"Primary text vs outline contrast is {ratio:.1f}:1 (needs ≥4.5:1 for WCAG AA). "
            f"Text may be hard to read on some backgrounds."
        )

    # Check highlight vs outline
    ratio_hl = _contrast_ratio(highlight, outline)
    if ratio_hl < 3.0:
        warnings.append(
            f"Highlight color vs outline contrast is {ratio_hl:.1f}:1 (needs ≥3.0:1). "
            f"Highlighted words may be hard to see."
        )

    # Check emphasis vs outline
    ratio_em = _contrast_ratio(emphasis, outline)
    if ratio_em < 3.0:
        warnings.append(
            f"Emphasis color vs outline contrast is {ratio_em:.1f}:1 (needs ≥3.0:1). "
            f"Emphasis words may be hard to see."
        )

    # Check if outline is thick enough for readability on varied backgrounds
    if style.outline_width < 2:
        warnings.append(
            f"Outline width is {style.outline_width}px — recommend ≥2px for readability on varied backgrounds."
        )

    return warnings


def sample_video_brightness(video_path: str, sample_count: int = 5) -> Optional[float]:
    """
    Sample average brightness of video frames to detect if captions need adjustment.
    Returns 0.0 (black) to 1.0 (white), or None if can't sample.
    """
    try:
        # Extract a few frames and get average brightness
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-print_format", "json", video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None

        duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
        if duration <= 0:
            return None

        # Sample brightness at evenly spaced points using signalstats
        brightnesses = []
        for i in range(sample_count):
            t = duration * (i + 1) / (sample_count + 1)
            result = subprocess.run(
                [
                    "ffmpeg", "-ss", str(t), "-i", video_path,
                    "-vframes", "1", "-vf", "signalstats",
                    "-f", "null", "-",
                ],
                capture_output=True, text=True, timeout=10,
            )
            # Parse YAVG (luma average) from signalstats output
            for line in result.stderr.split("\n"):
                if "YAVG" in line:
                    match = re.search(r"YAVG:(\d+\.?\d*)", line)
                    if match:
                        brightnesses.append(float(match.group(1)) / 255.0)
                    break

        return sum(brightnesses) / len(brightnesses) if brightnesses else None
    except Exception:
        return None


def auto_adjust_style_for_video(
    style: CaptionStyle,
    video_path: str,
) -> CaptionStyle:
    """
    Auto-adjust caption colors based on video brightness.
    Bright videos get dark text; dark videos keep white text.
    """
    brightness = sample_video_brightness(video_path)
    if brightness is None:
        return style  # can't detect, keep defaults

    import copy
    adjusted = copy.deepcopy(style)

    if brightness > 0.7:
        # Bright video — use dark text with light outline
        adjusted.primary_color = "&H00000000"       # black text
        adjusted.outline_color = "&H00FFFFFF"        # white outline
        adjusted.highlight_color = "&H000000FF"      # dark red highlight
        adjusted.emphasis_color = "&H00004080"       # dark yellow
        adjusted.back_color = "&H80FFFFFF"           # semi-transparent white bg
        print(f"  [contrast] Bright video detected (avg={brightness:.2f}) — using dark text")
    elif brightness < 0.3:
        # Dark video — white text is fine, ensure strong outline
        adjusted.outline_width = max(adjusted.outline_width, 3)
        adjusted.shadow_depth = max(adjusted.shadow_depth, 2)
        print(f"  [contrast] Dark video detected (avg={brightness:.2f}) — boosting outline")
    else:
        # Mid-range — ensure adequate outline
        adjusted.outline_width = max(adjusted.outline_width, 2)
        print(f"  [contrast] Mid-brightness video (avg={brightness:.2f}) — default styling OK")

    return adjusted


# ── NLP Keyword Detection ─────────────────────────────────────────────────────

# Words that should be emphasized (colored differently)
EMPHASIS_PATTERNS = [
    r"\b(amazing|incredible|insane|shocking|unbelievable|mind-?blowing|revolutionary)\b",
    r"\b(breaking|exclusive|urgent|critical|important|massive|huge)\b",
    r"\b(secret|hidden|unknown|revealed|exposed|truth)\b",
    r"\b(best|worst|top|first|last|only|never|always|every)\b",
    r"\b(free|new|now|today|just|finally|actually)\b",
]

EMOTION_PATTERNS = [
    r"\b(love|hate|fear|angry|happy|sad|excited|scared|worried)\b",
    r"\b(beautiful|terrible|horrible|wonderful|perfect|awful)\b",
]

NUMBER_PATTERN = re.compile(r"\b\d[\d,.]*%?\b")


def classify_word(word: str) -> str:
    """Classify a word for styling: 'emphasis', 'emotion', 'number', or 'normal'."""
    clean = word.strip(".,!?;:\"'()-").lower()
    if NUMBER_PATTERN.match(clean):
        return "number"
    for pat in EMPHASIS_PATTERNS:
        if re.match(pat, clean, re.IGNORECASE):
            return "emphasis"
    for pat in EMOTION_PATTERNS:
        if re.match(pat, clean, re.IGNORECASE):
            return "emotion"
    return "normal"


# ── Whisper Integration ────────────────────────────────────────────────────────

@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    confidence: float = 1.0
    word_type: str = "normal"  # normal, emphasis, emotion, number


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[WordTiming] = field(default_factory=list)


def transcribe_whisper_local(video_path: str) -> list[Segment]:
    """Transcribe using local Whisper with word-level timestamps (JSON output)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Try whisper CLI with word_timestamps
        cmd = [
            "whisper", video_path,
            "--model", "base",
            "--output_format", "json",
            "--output_dir", tmpdir,
            "--word_timestamps", "True",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print("Whisper timed out after 5 minutes. Try a shorter video or use the API.", file=sys.stderr)
            return []
        if result.returncode != 0:
            print(f"Whisper error: {result.stderr[:500]}", file=sys.stderr)
            return []

        # Find the JSON output
        json_files = list(Path(tmpdir).glob("*.json"))
        if not json_files:
            print("Whisper produced no JSON output", file=sys.stderr)
            return []

        with open(json_files[0]) as f:
            data = json.load(f)

    segments = []
    for seg in data.get("segments", []):
        words = []
        for w in seg.get("words", []):
            word_text = w.get("word", "").strip()
            if not word_text:
                continue
            wt = WordTiming(
                word=word_text,
                start=w.get("start", seg["start"]),
                end=w.get("end", seg["end"]),
                confidence=w.get("probability", 1.0),
                word_type=classify_word(word_text),
            )
            words.append(wt)
        segments.append(Segment(
            text=seg.get("text", "").strip(),
            start=seg["start"],
            end=seg["end"],
            words=words,
        ))
    return segments


def transcribe_whisper_api(video_path: str) -> list[Segment]:
    """Transcribe using OpenAI Whisper API with word-level timestamps."""
    from urllib.request import Request, urlopen
    import tempfile

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("No OPENAI_API_KEY set, cannot use Whisper API", file=sys.stderr)
        return []

    # Extract audio first (API has 25MB limit)
    audio_path = tempfile.mktemp(suffix=".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-q:a", "4", audio_path],
        capture_output=True,
    )

    # Call API with word timestamps
    import urllib.request

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n"
    ).encode() + audio_data + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"whisper-1\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="response_format"\r\n\r\n'
        f"verbose_json\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\n'
        f"word\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    req = Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    try:
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"Whisper API error: {e}", file=sys.stderr)
        os.unlink(audio_path)
        return []

    os.unlink(audio_path)

    # Build a sorted list of all words with timestamps
    all_words = sorted(data.get("words", []), key=lambda w: w.get("start", 0))

    segments = []
    word_idx = 0
    for seg in data.get("segments", []):
        words = []
        seg_start = seg["start"]
        seg_end = seg["end"]
        # Assign words that fall within this segment's time range
        while word_idx < len(all_words):
            w = all_words[word_idx]
            w_start = w.get("start", 0)
            # If word starts after segment ends, stop (belongs to next segment)
            if w_start > seg_end + 0.5:
                break
            # If word overlaps this segment, include it
            if w_start >= seg_start - 0.1:
                word_text = w.get("word", "").strip()
                if word_text:
                    words.append(WordTiming(
                        word=word_text,
                        start=w_start,
                        end=w.get("end", w_start + 0.2),
                        word_type=classify_word(word_text),
                    ))
            word_idx += 1
        segments.append(Segment(
            text=seg.get("text", "").strip(),
            start=seg_start,
            end=seg_end,
            words=words,
        ))
    return segments


def transcribe(video_path: str, method: str = "auto") -> list[Segment]:
    """Transcribe video, trying local Whisper first, then API."""
    if method == "api":
        return transcribe_whisper_api(video_path)
    if method == "local":
        return transcribe_whisper_local(video_path)

    # Auto: try local first
    from shutil import which
    if which("whisper"):
        segments = transcribe_whisper_local(video_path)
        if segments:
            return segments

    # Fallback to API
    if os.environ.get("OPENAI_API_KEY"):
        return transcribe_whisper_api(video_path)

    print("ERROR: Neither local Whisper nor OPENAI_API_KEY available.", file=sys.stderr)
    print("Install: pip install openai-whisper  OR  set OPENAI_API_KEY", file=sys.stderr)
    return []


# ── ASS Subtitle Generation ───────────────────────────────────────────────────

def _ts(seconds: float) -> str:
    """Convert seconds to ASS timestamp: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _srt_ts(seconds: float) -> str:
    """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _color_for_type(word_type: str, style: CaptionStyle) -> str:
    """Get ASS color override for a word type."""
    if word_type == "emphasis":
        return style.emphasis_color
    elif word_type == "emotion":
        return "&H004080FF"  # orange-red
    elif word_type == "number":
        return style.number_color
    return ""


def _group_words(words: list[WordTiming], group_size: int) -> list[list[WordTiming]]:
    """Group words into chunks for display (e.g., 2 words at a time for Shorts)."""
    if group_size <= 0:
        return [words]  # return all as one group
    return [words[i:i + group_size] for i in range(0, len(words), group_size)]


def generate_ass(
    segments: list[Segment],
    style: CaptionStyle,
    video_width: int = 1920,
    video_height: int = 1080,
) -> str:
    """Generate ASS subtitle content with word-level styling."""
    # ASS header
    header = f"""[Script Info]
Title: Smart Captions
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},&H000000FF,{style.outline_color},{style.back_color},{-1 if style.bold else 0},0,0,0,100,100,0,0,1,{style.outline_width},{style.shadow_depth},{style.alignment},{style.margin_l},{style.margin_r},{style.margin_v},1
Style: Highlight,{style.font_name},{style.font_size},{style.highlight_color},&H000000FF,{style.outline_color},{style.back_color},{-1 if style.bold else 0},0,0,0,100,100,0,0,1,{style.outline_width},{style.shadow_depth},{style.alignment},{style.margin_l},{style.margin_r},{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []

    for seg in segments:
        if not seg.words:
            # Fallback: no word-level timing, show full segment
            text = seg.text
            if style.animation == "fade":
                text = r"{\fad(200,200)}" + text
            lines.append(f"Dialogue: 0,{_ts(seg.start)},{_ts(seg.end)},Default,,0,0,0,,{text}")
            continue

        if style.animation == "highlight":
            # Karaoke mode: show full line, highlight current word
            _generate_karaoke_lines(seg, style, lines)
        elif style.words_per_group > 0:
            # Grouped mode (Shorts): show N words at a time
            _generate_grouped_lines(seg, style, lines)
        else:
            # Standard: show full line with optional animation + keyword coloring
            _generate_standard_lines(seg, style, lines)

    return header + "\n".join(lines) + "\n"


def _generate_karaoke_lines(seg: Segment, style: CaptionStyle, lines: list):
    """Karaoke: full line visible, active word highlighted with color sweep."""
    for i, active_word in enumerate(seg.words):
        # Build the full line with the active word highlighted
        parts = []
        for j, w in enumerate(seg.words):
            if j == i:
                # Active word: highlighted color + slightly larger
                parts.append(
                    r"{\c" + style.highlight_color + r"\fscx110\fscy110}" +
                    w.word +
                    r"{\c" + style.primary_color + r"\fscx100\fscy100}"
                )
            else:
                # Check for keyword coloring on non-active words
                color = _color_for_type(w.word_type, style)
                if color:
                    parts.append(r"{\c" + color + "}" + w.word + r"{\c" + style.primary_color + "}")
                else:
                    parts.append(w.word)

        text = " ".join(parts)
        # Determine timing: this word's start to next word's start (or segment end)
        start = active_word.start
        end = seg.words[i + 1].start if i + 1 < len(seg.words) else active_word.end
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")


def _generate_grouped_lines(seg: Segment, style: CaptionStyle, lines: list):
    """Grouped: show N words at a time (for Shorts/TikTok)."""
    groups = _group_words(seg.words, style.words_per_group)
    for group in groups:
        if not group:
            continue
        start = group[0].start
        end = group[-1].end

        parts = []
        for w in group:
            color = _color_for_type(w.word_type, style)
            if color:
                parts.append(r"{\c" + color + "}" + w.word + r"{\r}")
            else:
                parts.append(w.word)

        text = " ".join(parts)

        # Animations
        if style.animation == "bounce":
            # Scale up from 80% then settle at 100%
            dur_ms = int((end - start) * 1000)
            attack = min(150, dur_ms // 3)
            text = r"{\fscx80\fscy80\t(0," + str(attack) + r",\fscx105\fscy105)\t(" + str(attack) + "," + str(attack + 100) + r",\fscx100\fscy100)}" + text
        elif style.animation == "fade":
            text = r"{\fad(150,150)}" + text

        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")


def _generate_standard_lines(seg: Segment, style: CaptionStyle, lines: list):
    """Standard: full line with keyword coloring and optional fade."""
    parts = []
    for w in seg.words:
        color = _color_for_type(w.word_type, style)
        if color:
            parts.append(r"{\c" + color + "}" + w.word + r"{\r}")
        else:
            parts.append(w.word)

    text = " ".join(parts)
    if style.animation == "fade":
        text = r"{\fad(200,200)}" + text

    lines.append(f"Dialogue: 0,{_ts(seg.start)},{_ts(seg.end)},Default,,0,0,0,,{text}")


# ── SRT Generation (fallback) ─────────────────────────────────────────────────

def generate_srt(segments: list[Segment], words_per_group: int = 0) -> str:
    """Generate standard SRT from segments."""
    srt_lines = []
    idx = 1

    for seg in segments:
        if words_per_group > 0 and seg.words:
            groups = _group_words(seg.words, words_per_group)
            for group in groups:
                if not group:
                    continue
                srt_lines.append(str(idx))
                srt_lines.append(f"{_srt_ts(group[0].start)} --> {_srt_ts(group[-1].end)}")
                srt_lines.append(" ".join(w.word for w in group))
                srt_lines.append("")
                idx += 1
        else:
            srt_lines.append(str(idx))
            srt_lines.append(f"{_srt_ts(seg.start)} --> {_srt_ts(seg.end)}")
            srt_lines.append(seg.text)
            srt_lines.append("")
            idx += 1

    return "\n".join(srt_lines)


# ── Main Entry Point ──────────────────────────────────────────────────────────

def generate_captions(
    video_path: str,
    output_srt: str,
    output_ass: str,
    preset: CaptionPreset = CaptionPreset.STANDARD,
    custom_style: Optional[CaptionStyle] = None,
    whisper_method: str = "auto",
    video_width: int = 1920,
    video_height: int = 1080,
    auto_contrast: bool = True,
) -> bool:
    """
    Full caption generation pipeline:
    1. Transcribe with word-level timestamps
    2. Classify keywords (emphasis, emotion, number)
    3. Auto-adjust colors for video brightness (contrast detection)
    4. Generate ASS with animations + SRT fallback
    """
    print(f"Transcribing {video_path} (method={whisper_method})...")
    segments = transcribe(video_path, method=whisper_method)

    if not segments:
        print("No speech detected or transcription failed.")
        return False

    total_words = sum(len(s.words) for s in segments)
    print(f"Transcribed: {len(segments)} segments, {total_words} words")

    # Classify words
    for seg in segments:
        for w in seg.words:
            w.word_type = classify_word(w.word)

    emphasis_count = sum(1 for s in segments for w in s.words if w.word_type != "normal")
    print(f"Keyword detection: {emphasis_count} emphasis/emotion/number words found")

    # Get style
    style = custom_style or PRESET_STYLES.get(preset, PRESET_STYLES[CaptionPreset.STANDARD])

    # Contrast detection: auto-adjust colors for video brightness
    if auto_contrast:
        style = auto_adjust_style_for_video(style, video_path)

    # Check WCAG contrast compliance
    warnings = check_caption_contrast(style)
    for w in warnings:
        print(f"  [contrast warning] {w}")

    # Generate ASS
    ass_content = generate_ass(segments, style, video_width, video_height)
    Path(output_ass).parent.mkdir(parents=True, exist_ok=True)
    with open(output_ass, "w", encoding="utf-8") as f:
        f.write(ass_content)
    print(f"ASS subtitles saved: {output_ass}")

    # Generate SRT (fallback + compatibility)
    srt_content = generate_srt(segments, words_per_group=style.words_per_group)
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"SRT subtitles saved: {output_srt}")

    return True


def burn_captions(
    video_path: str,
    ass_path: str,
    output_path: str,
) -> bool:
    """Burn ASS captions into video using FFmpeg ass filter."""
    if not Path(ass_path).exists():
        print(f"ASS file not found: {ass_path}", file=sys.stderr)
        return False

    # FFmpeg ass filter needs colons escaped in the path
    escaped_ass = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"ass='{escaped_ass}'",
        "-c:a", "copy",
        output_path,
    ]
    print(f"Burning ASS captions into video...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        # ASS filter may fail — fall back to subtitles filter with SRT
        print(f"  ASS burn failed, trying SRT fallback...")
        srt_path = ass_path.replace(".ass", ".srt")
        if not Path(srt_path).exists():
            print(f"  No SRT fallback available", file=sys.stderr)
            return False
        escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        cmd2 = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", (
                f"subtitles='{escaped_srt}'"
                ":force_style='FontName=Arial Black,FontSize=52,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "Outline=5,Shadow=3,Bold=1,Alignment=5,MarginV=20'"
            ),
            "-c:a", "copy",
            output_path,
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
        if result2.returncode != 0:
            print(f"  SRT fallback also failed: {result2.stderr[:300]}", file=sys.stderr)
            return False

    print(f"Captioned video saved: {output_path}")
    return True


def _parse_srt(srt_path: str) -> list[dict]:
    """Parse SRT file into list of {start, end, text}."""
    entries = []
    with open(srt_path) as f:
        content = f.read()
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        timecode = lines[1]
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", timecode)
        if not m:
            continue
        g = m.groups()
        start = int(g[0])*3600 + int(g[1])*60 + int(g[2]) + int(g[3])/1000
        end = int(g[4])*3600 + int(g[5])*60 + int(g[6]) + int(g[7])/1000
        text = " ".join(lines[2:])
        entries.append({"start": start, "end": end, "text": text})
    return entries


def _group_srt_entries(entries: list[dict], words_per_group: int = 4) -> list[dict]:
    """Group word-level SRT entries into multi-word display groups."""
    if not entries:
        return []
    grouped = []
    buf_words = []
    buf_start = entries[0]["start"]
    for e in entries:
        buf_words.append(e["text"])
        if len(buf_words) >= words_per_group:
            grouped.append({
                "start": buf_start,
                "end": e["end"],
                "text": " ".join(buf_words),
            })
            buf_words = []
            buf_start = e["end"]
    if buf_words:
        grouped.append({
            "start": buf_start,
            "end": entries[-1]["end"],
            "text": " ".join(buf_words),
        })
    return grouped


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart Captions Generator")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("--preset", choices=["shorts", "standard", "karaoke", "minimal"],
                       default="standard", help="Caption preset style")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--whisper-method", choices=["auto", "local", "api"], default="auto")
    parser.add_argument("--burn", action="store_true", help="Also burn captions into video")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)

    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    preset = CaptionPreset(args.preset)
    ok = generate_captions(
        video_path=args.video,
        output_srt=str(out_dir / "captions.srt"),
        output_ass=str(out_dir / "captions.ass"),
        preset=preset,
        whisper_method=args.whisper_method,
        video_width=args.width,
        video_height=args.height,
    )

    if ok and args.burn:
        stem = Path(args.video).stem
        burn_captions(
            video_path=args.video,
            ass_path=str(out_dir / "captions.ass"),
            output_path=str(out_dir / f"{stem}_captioned.mp4"),
        )
