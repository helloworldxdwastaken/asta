#!/usr/bin/env python3
"""
Video effects engine for YouTube pipeline.

Features:
  - Ken Burns (zoom/pan on clips)
  - Crossfade transitions between clips
  - Cinematic LUT / color grading
  - Subscribe + Like overlay (last 5s)
  - Lower thirds (section title overlays)
  - Scene-synced editing (match clips to script sections)
  - Audio ducking (lower music during speech)
  - Clip splitting (max N seconds per segment)
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ── Constants ────────────────────────────────────────────────────────────────

MAX_CLIP_DURATION = 5.0       # seconds — max before cutting to next clip
MIN_CLIPS = 5                 # minimum unique clips per video
CROSSFADE_DURATION = 0.5      # seconds — transition overlap
SUBSCRIBE_DURATION = 5.0      # seconds — how long the subscribe overlay shows
FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"


# ── Probe helpers ────────────────────────────────────────────────────────────

def probe_duration(path: str) -> float:
    """Get video duration in seconds."""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    return 0.0


def probe_resolution(path: str) -> tuple[int, int]:
    """Get video width, height."""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        for s in json.loads(r.stdout).get("streams", []):
            if s.get("codec_type") == "video":
                return int(s.get("width", 1920)), int(s.get("height", 1080))
    return 1920, 1080


# ── Script parsing ───────────────────────────────────────────────────────────

@dataclass
class ScriptSection:
    title: str
    start_hint: float       # from timestamp e.g. 0:08
    narration: str
    visual_cue: str
    duration: float = 0.0   # filled in later from voiceover timing


def parse_script_sections(script_path: str) -> list[ScriptSection]:
    """Parse script.md into sections with timestamps and visual cues."""
    text = Path(script_path).read_text()
    sections = []

    # Match ### Section N: Title (start - end)
    pattern = r"###\s+(.+?)\s*\((\d+):(\d+)\s*-\s*(\d+):(\d+)\)"
    for m in re.finditer(pattern, text):
        title = m.group(1).strip()
        start = int(m.group(2)) * 60 + int(m.group(3))
        end = int(m.group(4)) * 60 + int(m.group(5))

        # Find content after this header until next ### or end
        pos = m.end()
        next_h = re.search(r"\n###\s", text[pos:])
        block = text[pos:pos + next_h.start()] if next_h else text[pos:]

        visual = ""
        narration = ""
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("[VISUAL:"):
                visual = line.replace("[VISUAL:", "").rstrip("]").strip()
            elif line.startswith("NARRATION:"):
                narration = line.replace("NARRATION:", "").strip().strip('"')

        sections.append(ScriptSection(
            title=title,
            start_hint=float(start),
            narration=narration,
            visual_cue=visual,
            duration=float(end - start),
        ))

    return sections


# ── Ken Burns effect ─────────────────────────────────────────────────────────

def ken_burns_filter(clip_duration: float, direction: str = "random") -> str:
    """
    Generate ffmpeg zoompan filter string for Ken Burns effect.
    Directions: zoom_in, zoom_out, pan_left, pan_right, random.
    """
    if direction == "random":
        direction = random.choice(["zoom_in", "zoom_out", "pan_left", "pan_right"])

    fps = 30
    total_frames = int(clip_duration * fps)
    # zoompan outputs at 10fps by default, we oversample to 30
    d = max(total_frames, 1)

    if direction == "zoom_in":
        return f"zoompan=z='min(zoom+0.0008,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=1920x1080:fps={fps}"
    elif direction == "zoom_out":
        return f"zoompan=z='if(eq(on,1),1.15,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=1920x1080:fps={fps}"
    elif direction == "pan_left":
        return f"zoompan=z='1.08':x='if(eq(on,1),iw*0.08,max(x-0.5,0))':y='ih/2-(ih/zoom/2)':d={d}:s=1920x1080:fps={fps}"
    elif direction == "pan_right":
        return f"zoompan=z='1.08':x='if(eq(on,1),0,min(x+0.5,iw*0.08))':y='ih/2-(ih/zoom/2)':d={d}:s=1920x1080:fps={fps}"
    return ""


def is_still_image(input_path: str) -> bool:
    """Check if input is a still image (jpg/png) or a very short single-frame video."""
    ext = Path(input_path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"):
        return True
    # Check if video has only 1 frame or is < 0.1s
    dur = probe_duration(input_path)
    return dur < 0.1


def apply_ken_burns(input_path: str, output_path: str, duration: float,
                    direction: str = "random") -> bool:
    """Apply Ken Burns effect — ONLY for still images, not video clips."""
    if not is_still_image(input_path):
        return False  # caller should use the clip as-is
    filt = ken_burns_filter(duration, direction)
    if not filt:
        return False
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(duration),
        "-vf", filt,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an", output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0


# ── Clip splitting ───────────────────────────────────────────────────────────

def split_clip_segments(clips: list[str], max_dur: float = MAX_CLIP_DURATION,
                        min_clips: int = MIN_CLIPS) -> list[tuple[str, float, float]]:
    """
    Split clips into segments of max_dur seconds.
    Returns list of (clip_path, start_time, segment_duration).
    Ensures at least min_clips segments.
    """
    segments = []
    for clip in clips:
        dur = probe_duration(clip)
        if dur <= 0:
            continue
        if dur <= max_dur:
            segments.append((clip, 0.0, dur))
        else:
            t = 0.0
            while t < dur:
                seg_dur = min(max_dur, dur - t)
                if seg_dur < 1.0 and segments:
                    break  # skip tiny tail
                segments.append((clip, t, seg_dur))
                t += seg_dur

    # If we still have fewer than min_clips, duplicate some
    if len(segments) < min_clips and segments:
        while len(segments) < min_clips:
            # Pick random clip and re-use a different segment start
            src = random.choice(segments)
            segments.append(src)
        random.shuffle(segments)

    return segments


def match_clips_to_sections(
    clips: list[str],
    sections: list[ScriptSection],
    total_duration: float,
) -> list[tuple[str, float, float, str]]:
    """
    Distribute clips across script sections proportionally.
    Returns list of (clip_path, start_in_clip, segment_duration, section_title).
    """
    if not sections:
        # No sections — fall back to even split
        segs = split_clip_segments(clips)
        return [(s[0], s[1], s[2], "") for s in segs]

    # Calculate section durations proportionally
    total_script_dur = sum(s.duration for s in sections) or total_duration
    result = []
    clip_idx = 0
    clip_pool = clips * 3  # repeat pool to have enough

    for section in sections:
        section_dur = (section.duration / total_script_dur) * total_duration
        filled = 0.0
        while filled < section_dur and clip_idx < len(clip_pool):
            clip = clip_pool[clip_idx]
            clip_dur = probe_duration(clip)
            if clip_dur <= 0:
                clip_idx += 1
                continue

            # How much of this clip to use
            remaining = section_dur - filled
            seg_dur = min(MAX_CLIP_DURATION, clip_dur, remaining)
            if seg_dur < 0.5:
                break

            # Random start point if clip is longer than segment
            max_start = max(0, clip_dur - seg_dur)
            start = random.uniform(0, max_start) if max_start > 0.5 else 0.0

            result.append((clip, start, seg_dur, section.title))
            filled += seg_dur
            clip_idx += 1

    return result


# ── Crossfade transitions ───────────────────────────────────────────────────

def concat_with_crossfade(
    segment_paths: list[str],
    output_path: str,
    crossfade_dur: float = CROSSFADE_DURATION,
) -> bool:
    """
    Concatenate clips with crossfade transitions.
    Falls back to simple concat if xfade fails.
    """
    if len(segment_paths) < 2:
        if segment_paths:
            import shutil
            shutil.copy2(segment_paths[0], output_path)
            return True
        return False

    # Build xfade filter chain
    # [0][1]xfade=transition=fade:duration=0.5:offset=T1[v01];[v01][2]xfade=...
    inputs = []
    for p in segment_paths:
        inputs.extend(["-i", p])

    durations = [probe_duration(p) for p in segment_paths]
    transitions = ["fade", "fadeblack", "smoothleft", "smoothright", "circlecrop", "dissolve"]

    filter_parts = []
    offset = durations[0] - crossfade_dur if durations[0] > crossfade_dur else durations[0] * 0.8

    if len(segment_paths) == 2:
        t = random.choice(transitions)
        filter_parts.append(f"[0:v][1:v]xfade=transition={t}:duration={crossfade_dur:.2f}:offset={offset:.2f}[vout]")
    else:
        # Chain: [0][1]xfade→[v01], [v01][2]xfade→[v02], ...
        prev_label = "0:v"
        cumulative_offset = 0.0
        for i in range(1, len(segment_paths)):
            t = random.choice(transitions)
            out_label = "vout" if i == len(segment_paths) - 1 else f"v{i:02d}"
            cumulative_offset += durations[i - 1] - crossfade_dur
            if cumulative_offset < 0:
                cumulative_offset = 0.1
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={t}:duration={crossfade_dur:.2f}:offset={cumulative_offset:.2f}[{out_label}]"
            )
            prev_label = out_label

    filter_str = ";".join(filter_parts)
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-r", "30", "-an",
        output_path,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode == 0:
        return True

    # Fallback: simple concat
    print(f"  Crossfade failed, falling back to concat: {r.stderr[:200]}")
    concat_file = Path(output_path).parent / "concat_fallback.txt"
    with open(concat_file, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p}'\n")
    r2 = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-c", "copy", output_path],
        capture_output=True, timeout=120,
    )
    return r2.returncode == 0


# ── Cinematic color grading ──────────────────────────────────────────────────

def apply_color_grade(input_path: str, output_path: str,
                      style: str = "cinematic") -> bool:
    """
    Apply color grading via ffmpeg eq/curves/colorbalance filters.
    Styles: cinematic, warm, cool, vibrant, moody
    """
    grades = {
        "cinematic": (
            "eq=contrast=1.1:brightness=0.02:saturation=1.15,"
            "colorbalance=rs=0.05:gs=-0.02:bs=-0.05:rh=0.03:gh=0.0:bh=-0.02,"
            "curves=m='0/0 0.25/0.20 0.5/0.52 0.75/0.82 1/1'"
        ),
        "warm": (
            "eq=contrast=1.05:saturation=1.2,"
            "colorbalance=rs=0.08:gs=0.02:bs=-0.06:rh=0.05:gh=0.01:bh=-0.04"
        ),
        "cool": (
            "eq=contrast=1.08:saturation=1.1,"
            "colorbalance=rs=-0.04:gs=0.0:bs=0.08:rh=-0.03:gh=0.01:bh=0.05"
        ),
        "vibrant": (
            "eq=contrast=1.15:saturation=1.35:brightness=0.01,"
            "unsharp=5:5:0.5:5:5:0.0"
        ),
        "moody": (
            "eq=contrast=1.2:brightness=-0.03:saturation=0.85,"
            "colorbalance=rs=0.02:gs=-0.03:bs=0.0:rh=0.0:gh=-0.02:bh=0.03,"
            "curves=m='0/0 0.15/0.10 0.5/0.48 0.85/0.82 1/0.95'"
        ),
    }

    filt = grades.get(style, grades["cinematic"])
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", filt,
        "-c:a", "copy",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return r.returncode == 0


# ── Subscribe / Like overlay ────────────────────────────────────────────────

def add_subscribe_overlay(
    input_path: str,
    output_path: str,
    show_seconds: float = SUBSCRIBE_DURATION,
) -> bool:
    """
    Add a 'Subscribe' + bell icon overlay in the last N seconds.
    Uses drawtext + drawbox for a clean animated look.
    """
    total_dur = probe_duration(input_path)
    if total_dur <= 0:
        return False

    start = max(0, total_dur - show_seconds)

    # Clean subscribe button — no emojis (ffmpeg can't render them reliably)
    subscribe_filter = (
        # Semi-transparent dark overlay bar at bottom
        f"drawbox=x=0:y=ih-80:w=iw:h=80:color=black@0.6:t=fill"
        f":enable='between(t,{start:.2f},{total_dur:.2f})',"
        # Red subscribe button
        f"drawbox=x=iw/2-85:y=ih-65:w=170:h=40:color=0xFF0000@0.95:t=fill"
        f":enable='between(t,{start:.2f},{total_dur:.2f})',"
        # SUBSCRIBE text
        f"drawtext=text='SUBSCRIBE'"
        f":fontfile={FONT_PATH}:fontsize=20:fontcolor=white"
        f":x=(w-text_w)/2:y=h-56"
        f":enable='between(t,{start:.2f},{total_dur:.2f})',"
        # Like text on left
        f"drawtext=text='LIKE'"
        f":fontfile={FONT_PATH}:fontsize=16:fontcolor=white@0.9"
        f":x=w/2-160:y=h-52"
        f":enable='between(t,{start:.2f},{total_dur:.2f})',"
        # Share text on right
        f"drawtext=text='SHARE'"
        f":fontfile={FONT_PATH}:fontsize=16:fontcolor=white@0.9"
        f":x=w/2+115:y=h-52"
        f":enable='between(t,{start:.2f},{total_dur:.2f})'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", subscribe_filter,
        "-c:a", "copy",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0


# ── Lower thirds ────────────────────────────────────────────────────────────

def add_lower_thirds(
    input_path: str,
    output_path: str,
    sections: list[ScriptSection],
    total_duration: float,
) -> bool:
    """
    Add section title overlays (lower third style) at the start of each section.
    Shows for 3 seconds with fade in/out.
    """
    if not sections:
        return False

    filters = []
    total_script_dur = sum(s.duration for s in sections) or total_duration

    cumulative = 0.0
    for section in sections:
        section_dur = (section.duration / total_script_dur) * total_duration
        start = cumulative
        end = start + min(3.0, section_dur * 0.6)

        # Clean title (remove "Section N: " prefix if present)
        title = re.sub(r"^Section \d+:\s*", "", section.title).strip()
        if not title:
            cumulative += section_dur
            continue

        # Escape for ffmpeg
        title = title.replace("'", "\u2019").replace(":", "\\:").replace(",", "\\,")

        # Semi-transparent bar
        filters.append(
            f"drawbox=x=0:y=ih-130:w=iw*0.45:h=50:color=black@0.65:t=fill"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
        # Accent stripe
        filters.append(
            f"drawbox=x=0:y=ih-130:w=4:h=50:color=#4A9EFF@0.9:t=fill"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
        # Text
        filters.append(
            f"drawtext=text='{title}'"
            f":fontfile={FONT_PATH}:fontsize=24:fontcolor=white"
            f":x=20:y=h-118"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
        cumulative += section_dur

    if not filters:
        return False

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0


# ── Audio ducking ────────────────────────────────────────────────────────────

def mix_with_ducking(
    video_path: str,
    music_path: str,
    output_path: str,
    voice_vol: float = 1.0,
    music_vol: float = 0.15,
    duck_level: float = 0.05,
) -> bool:
    """
    Mix voiceover + background music.
    Music plays at music_vol underneath the voice.
    Voice stays at full volume, music fades in/out at start/end.
    """
    vid_dur = probe_duration(video_path)
    if vid_dur <= 0:
        return False

    # Simple mix: voice at full volume, music underneath with fade in/out
    fade_out_start = max(0, vid_dur - 3)
    filter_complex = (
        f"[0:a]volume={voice_vol}[voice];"
        f"[1:a]atrim=start=0:end={vid_dur:.2f},"
        f"afade=t=in:d=2,afade=t=out:st={fade_out_start:.2f}:d=3,"
        f"volume={music_vol}[music];"
        f"[voice][music]amix=inputs=2:duration=first:normalize=0[out]"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode == 0


# ── Background music generator ──────────────────────────────────────────────

def generate_ambient_music(output_path: str, duration: float) -> bool:
    """
    Generate a more pleasant ambient background track.
    Uses layered sine waves in a musical chord (Cmaj7: C3, E3, G3, B3)
    with slow volume modulation for a pad-like feel.
    """
    dur = int(duration) + 3
    # Musical frequencies: C3=130.8, E3=164.8, G3=196.0, B3=246.9
    # Add tremolo for movement
    filter_complex = (
        f"sine=frequency=130.8:duration={dur},tremolo=f=0.3:d=0.4[s1];"
        f"sine=frequency=164.8:duration={dur},tremolo=f=0.2:d=0.3[s2];"
        f"sine=frequency=196.0:duration={dur},tremolo=f=0.25:d=0.35[s3];"
        f"sine=frequency=246.9:duration={dur},tremolo=f=0.15:d=0.25[s4];"
        f"[s1]volume=0.12[v1];[s2]volume=0.08[v2];[s3]volume=0.06[v3];[s4]volume=0.04[v4];"
        f"[v1][v2][v3][v4]amix=inputs=4:duration=first,"
        f"afade=t=in:d=2,afade=t=out:st={dur-3}:d=3,"
        f"lowpass=f=2000,highpass=f=80"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=130.8:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=164.8:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=196.0:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=246.9:duration={dur}",
        "-filter_complex", filter_complex,
        "-c:a", "libmp3lame", "-b:a", "192k",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0
