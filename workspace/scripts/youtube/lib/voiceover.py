#!/usr/bin/env python3
"""
Voiceover Engine — generate narration audio from scripts using Edge-TTS (free).

Edge-TTS uses Microsoft's Azure TTS service for free via the Edge browser API.
300+ voices, 40+ languages, very high quality.

Usage:
    from lib.voiceover import generate_voiceover

    generate_voiceover(
        text="Hello world, this is a test.",
        output_path="voiceover.mp3",
        voice="en-US-GuyNeural",
    )

Install: pip install edge-tts

Voices: run `edge-tts --list-voices` for full list. Popular ones:
    en-US-GuyNeural        — male, conversational
    en-US-AriaNeural       — female, conversational
    en-US-JennyNeural      — female, warm
    en-US-ChristopherNeural — male, authoritative
    en-GB-RyanNeural       — male, British
    en-GB-SoniaNeural      — female, British
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ── Popular Voices ─────────────────────────────────────────────────────────────

VOICE_PRESETS = {
    "male": "en-US-GuyNeural",
    "female": "en-US-AriaNeural",
    "warm": "en-US-JennyNeural",
    "authoritative": "en-US-ChristopherNeural",
    "british_male": "en-GB-RyanNeural",
    "british_female": "en-GB-SoniaNeural",
    "narrator": "en-US-DavisNeural",
    "energetic": "en-US-JasonNeural",
}


# ── Core Functions ─────────────────────────────────────────────────────────────

def _check_edge_tts() -> bool:
    """Check if edge-tts is installed."""
    from shutil import which
    return which("edge-tts") is not None


def list_voices(language: str = "en") -> list[dict]:
    """List available Edge-TTS voices for a language."""
    if not _check_edge_tts():
        print("edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
        return []

    result = subprocess.run(
        ["edge-tts", "--list-voices"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return []

    voices = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip() or line.startswith("Name"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            if name.lower().startswith(language.lower()):
                gender = parts[1] if len(parts) > 1 else "?"
                voices.append({"name": name, "gender": gender})

    return voices


def generate_voiceover(
    text: str,
    output_path: str,
    voice: str = "en-US-GuyNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> bool:
    """
    Generate voiceover audio from text using Edge-TTS.

    Args:
        text: The narration text
        output_path: Where to save the MP3 file
        voice: Voice name (e.g., "en-US-GuyNeural") or preset (e.g., "male")
        rate: Speech rate adjustment (e.g., "+10%", "-20%")
        pitch: Pitch adjustment (e.g., "+5Hz", "-10Hz")
        volume: Volume adjustment (e.g., "+20%")

    Returns:
        True if successful
    """
    if not _check_edge_tts():
        print("ERROR: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
        return False

    # Resolve voice preset
    resolved_voice = VOICE_PRESETS.get(voice, voice)

    # Clean text: remove script formatting markers
    clean_text = _clean_script_text(text)

    if not clean_text.strip():
        print("ERROR: No text to narrate after cleaning.", file=sys.stderr)
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "edge-tts",
        "--voice", resolved_voice,
        "--rate", rate,
        "--pitch", pitch,
        "--volume", volume,
        "--text", clean_text,
        "--write-media", output_path,
    ]

    print(f"Generating voiceover ({resolved_voice}, rate={rate})...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("ERROR: Edge-TTS timed out after 2 minutes.", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(f"ERROR: Edge-TTS failed: {result.stderr[:500]}", file=sys.stderr)
        return False

    if Path(output_path).exists() and Path(output_path).stat().st_size > 100:
        size_kb = Path(output_path).stat().st_size / 1024
        print(f"Voiceover saved: {output_path} ({size_kb:.0f} KB)")
        return True
    else:
        print("ERROR: Edge-TTS produced no output.", file=sys.stderr)
        return False


def generate_voiceover_from_script(
    script_path: str,
    output_dir: str,
    voice: str = "en-US-GuyNeural",
    rate: str = "+0%",
    mode: str = "full",
) -> Optional[str]:
    """
    Generate voiceover from a script.md file.

    Modes:
        "full"     — extract all narration lines, generate one audio file
        "sections" — generate separate audio per script section

    Returns path to the final voiceover MP3 (or None on failure).
    """
    if not Path(script_path).exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        return None

    with open(script_path) as f:
        content = f.read()

    # Extract narration lines from script
    narrations = re.findall(
        r'NARRATION:\s*["\']?(.+?)["\']?\s*$',
        content, re.MULTILINE | re.IGNORECASE,
    )

    if not narrations:
        # Fallback: try to extract any quoted text
        narrations = re.findall(r'"([^"]{10,})"', content)

    if not narrations:
        print("ERROR: No narration found in script.", file=sys.stderr)
        return None

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if mode == "full":
        # Combine all narrations with pauses
        full_text = " ... ".join(narrations)
        output_file = str(out_path / "voiceover.mp3")
        ok = generate_voiceover(full_text, output_file, voice=voice, rate=rate)
        return output_file if ok else None

    elif mode == "sections":
        # Generate per-section
        section_files = []
        for i, narr in enumerate(narrations):
            section_file = str(out_path / f"voiceover_section_{i:03d}.mp3")
            ok = generate_voiceover(narr, section_file, voice=voice, rate=rate)
            if ok:
                section_files.append(section_file)

        if not section_files:
            return None

        # Concatenate all sections
        concat_list = out_path / "vo_concat.txt"
        with open(concat_list, "w") as f:
            for sf in section_files:
                f.write(f"file '{sf}'\n")

        combined = str(out_path / "voiceover.mp3")
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", combined],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"Combined voiceover: {combined}")
            return combined
        else:
            # Return first section as fallback
            return section_files[0] if section_files else None

    return None


def mix_voiceover_with_video(
    video_path: str,
    voiceover_path: str,
    output_path: str,
    vo_volume: float = 1.0,
    original_volume: float = 0.1,
) -> bool:
    """
    Mix voiceover audio with existing video.
    Reduces original audio volume and adds voiceover on top.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", voiceover_path,
        "-filter_complex",
        f"[0:a]volume={original_volume}[orig];[1:a]volume={vo_volume}[vo];[orig][vo]amix=inputs=2:duration=first[out]",
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path,
    ]

    print(f"Mixing voiceover (vo={vo_volume}, orig={original_volume})...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"ERROR: Mix failed: {result.stderr[:300]}", file=sys.stderr)
        return False

    print(f"Mixed output: {output_path}")
    return True


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean_script_text(text: str) -> str:
    """Remove script formatting markers, keeping only spoken text."""
    # Remove section headers
    text = re.sub(r"^\[.*?\]\s*", "", text, flags=re.MULTILINE)
    # Remove VISUAL: lines
    text = re.sub(r"^VISUAL:.*$", "", text, flags=re.MULTILINE)
    # Remove TEXT ON SCREEN: lines
    text = re.sub(r"^TEXT ON SCREEN:.*$", "", text, flags=re.MULTILINE)
    # Remove SFX: lines
    text = re.sub(r"^SFX:.*$", "", text, flags=re.MULTILINE)
    # Remove NARRATION: prefix but keep the text
    text = re.sub(r"^NARRATION:\s*", "", text, flags=re.MULTILINE)
    # Remove markdown formatting
    text = re.sub(r"[#*_~`]", "", text)
    # Remove quotes
    text = re.sub(r'["\']', "", text)
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voiceover Generator (Edge-TTS)")
    sub = parser.add_subparsers(dest="command")

    # generate from text
    p_text = sub.add_parser("text", help="Generate voiceover from text")
    p_text.add_argument("content", help="Text to narrate")
    p_text.add_argument("--output", default="voiceover.mp3", help="Output MP3 path")
    p_text.add_argument("--voice", default="male", help="Voice name or preset")
    p_text.add_argument("--rate", default="+0%", help="Speech rate (e.g., +10%, -20%)")

    # generate from script
    p_script = sub.add_parser("script", help="Generate voiceover from script.md")
    p_script.add_argument("script_path", help="Path to script.md")
    p_script.add_argument("--output-dir", default=".", help="Output directory")
    p_script.add_argument("--voice", default="male", help="Voice name or preset")
    p_script.add_argument("--rate", default="+0%", help="Speech rate")
    p_script.add_argument("--mode", choices=["full", "sections"], default="full")

    # list voices
    p_list = sub.add_parser("voices", help="List available voices")
    p_list.add_argument("--language", default="en", help="Language prefix filter")

    # mix with video
    p_mix = sub.add_parser("mix", help="Mix voiceover with video")
    p_mix.add_argument("video", help="Input video path")
    p_mix.add_argument("voiceover", help="Voiceover MP3 path")
    p_mix.add_argument("--output", default="with_voiceover.mp4", help="Output path")
    p_mix.add_argument("--vo-volume", type=float, default=1.0)
    p_mix.add_argument("--original-volume", type=float, default=0.1)

    args = parser.parse_args()

    if args.command == "text":
        generate_voiceover(args.content, args.output, voice=args.voice, rate=args.rate)
    elif args.command == "script":
        generate_voiceover_from_script(
            args.script_path, args.output_dir, voice=args.voice, rate=args.rate, mode=args.mode,
        )
    elif args.command == "voices":
        voices = list_voices(args.language)
        for v in voices:
            print(f"  {v['name']} ({v['gender']})")
        if not voices:
            print("No voices found or edge-tts not installed.")
    elif args.command == "mix":
        mix_voiceover_with_video(
            args.video, args.voiceover, args.output,
            vo_volume=args.vo_volume, original_volume=args.original_volume,
        )
    else:
        parser.print_help()
