---
name: youtube-edit
description: Auto-edit YouTube videos using FFmpeg — cut clips, add captions (Whisper), add intro/outro, overlay text, merge audio, and export as 1080p MP4. Use when the user wants to edit, assemble, or render a video.
metadata: {"clawdbot":{"emoji":"🎞️","requires":{"bins":["ffmpeg","ffprobe","python3","whisper"]}}}
---

# YouTube Video Editor (FFmpeg)

Assemble and edit YouTube videos using FFmpeg. Supports cutting, concatenation, captions, intro/outro, text overlays, and audio mixing.

## Prerequisites

- **FFmpeg**: `brew install ffmpeg` (must include libass for subtitles)
- **Whisper** (for captions): `pip install openai-whisper` or use OpenAI Whisper API
- **Input files**: footage in `workspace/youtube/YYYY-MM-DD/footage/`
- **Intro/outro** (optional): user provides paths, stored in agent knowledge

## Pipeline Script

The primary way to edit videos is through the pipeline script, which handles the full edit flow:

```bash
# Standard video (3 min, 16:9)
python3 workspace/scripts/youtube/pipeline.py edit --date 2026-03-15 --captions

# YouTube Short (45s, 9:16 vertical)
python3 workspace/scripts/youtube/pipeline.py edit --date 2026-03-15 --format short --captions

# Long-form (8 min, 16:9)
python3 workspace/scripts/youtube/pipeline.py edit --date 2026-03-15 --format long --captions
```

**Format presets:**
- `short` — 45s default, 3s max clips, vertical 9:16 crop, shorts caption preset
- `standard` — 3min default, 5s max clips, standard captions
- `long` — 8min default, 8s max clips, standard captions

**Pipeline steps (14):**
1. Normalize clips to 1080p30
2. Segment & distribute clips (Ken Burns for photos, trim for video)
3. Crossfade transitions (random: fade/wipeleft/slideup/dissolve/etc.)
4. Color grading (random: cinematic/warm/cool/vibrant/moody)
5. Generate voiceover (TTS via OpenAI or edge-tts)
6. Loudnorm voiceover to -16 LUFS (YouTube standard)
7. Generate smart captions (word-level, ASS format)
8. Burn captions into video
9. Mix background music (ambient sine + voice at full vol)
10. Add subscribe CTA (red button + LIKE/SHARE, last 5s)
11. Lower thirds (opt-in with `--lower-thirds`)
12. Vertical crop for Shorts (`crop=ih*9/16:ih,scale=1080:1920`)
13. Final YouTube-optimized export (H.264/AAC, faststart)

**Photo support:** The pipeline accepts both videos (`.mp4`) and photos (`.jpg`, `.png`) in the footage folder. Photos get Ken Burns effects (zoom in/out, pan), while videos are trimmed normally.

## Core Operations

### 1. Probe clip info

```bash
# Get duration, resolution, codec of a clip
ffprobe -v quiet -print_format json -show_format -show_streams "input.mp4" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
s = d['streams'][0]
f = d['format']
print(f\"Duration: {float(f['duration']):.1f}s\")
print(f\"Resolution: {s.get('width','?')}x{s.get('height','?')}\")
print(f\"Codec: {s.get('codec_name','?')}\")
"
```

### 2. Trim a clip

```bash
# Trim clip to specific start/end time
ffmpeg -y -i "input.mp4" -ss 00:00:05 -to 00:00:15 -c copy "trimmed.mp4"
```

### 3. Scale to 1080p

```bash
# Scale video to 1920x1080, pad if aspect ratio differs
ffmpeg -y -i "input.mp4" \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
  -c:a copy "scaled.mp4"
```

### 4. Concatenate clips

```bash
# Create a concat list file
cat > /tmp/concat_list.txt << 'CLIPS'
file '/path/to/clip1.mp4'
file '/path/to/clip2.mp4'
file '/path/to/clip3.mp4'
CLIPS

# First normalize all clips to same format
for f in clip1.mp4 clip2.mp4 clip3.mp4; do
  ffmpeg -y -i "$f" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
    -r 30 -c:v libx264 -preset fast -crf 23 \
    -c:a aac -ar 44100 -ac 2 \
    "norm_${f}"
done

# Then concatenate
ffmpeg -y -f concat -safe 0 -i /tmp/concat_list.txt -c copy "merged.mp4"
```

### 5. Smart Captions (word-level highlighting)

The smart captions engine (`workspace/scripts/youtube/lib/smart_captions.py`) generates professional
captions with word-level timing, keyword coloring, and animation presets.

**Caption presets:**
- `shorts` — 1-2 words at a time, bounce animation, big centered text (TikTok/YouTube Shorts style)
- `standard` — full line, fade-in/out, clean bottom text (long-form YouTube)
- `karaoke` — full line visible, active word highlighted with color sweep
- `minimal` — small, bottom, no animation

**Keyword detection (NLP):**
- Emphasis words (amazing, shocking, secret, best, etc.) → yellow
- Emotion words (love, hate, excited, etc.) → orange-red
- Numbers → cyan
- Normal words → white

```bash
# Generate smart captions with word-level highlighting
python3 workspace/scripts/youtube/lib/smart_captions.py "input.mp4" \
  --preset shorts \
  --output-dir workspace/youtube/2026-03-15/ \
  --burn

# Or via the pipeline
python3 workspace/scripts/youtube/pipeline.py edit --date 2026-03-15 --captions --caption-preset shorts
```

**How it works:**
1. Whisper transcribes with `--word_timestamps True` (JSON mode) → word-level start/end times
2. NLP classifier tags each word as emphasis/emotion/number/normal
3. ASS subtitle generator applies preset styling:
   - `shorts`: groups 2 words, bounce animation (scale 80%→105%→100%), center screen
   - `karaoke`: shows full line, active word gets highlight color + 110% scale
   - `standard`: full line with fade + keyword coloring
4. Burns ASS into video via FFmpeg `ass` filter (richer than `subtitles` filter)

**Output files:**
- `captions.srt` — standard SRT (compatibility/fallback)
- `captions.ass` — styled ASS with animations + colors (used for burn-in)

### 6. Burn captions into video

```bash
# Burn ASS subtitles (recommended — supports animations + colors)
ffmpeg -y -i "input.mp4" -vf "ass=captions.ass" -c:a copy "captioned.mp4"

# Fallback: Burn SRT subtitles (basic white text)
ffmpeg -y -i "input.mp4" \
  -vf "subtitles=captions.srt:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=40'" \
  -c:a copy "captioned.mp4"
```

### 7. Add intro/outro

```bash
# Concatenate intro + main + outro
cat > /tmp/final_concat.txt << 'PARTS'
file '/path/to/intro.mp4'
file '/path/to/main_video.mp4'
file '/path/to/outro.mp4'
PARTS

ffmpeg -y -f concat -safe 0 -i /tmp/final_concat.txt -c copy "final_with_intro_outro.mp4"
```

### 8. Add background music

```bash
# Mix background music at lower volume with original audio
ffmpeg -y -i "video.mp4" -i "music.mp3" \
  -filter_complex "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first[out]" \
  -map 0:v -map "[out]" -c:v copy -c:a aac "with_music.mp4"
```

### 9. Add text overlay

```bash
# Add text overlay (e.g., lower-third title)
ffmpeg -y -i "input.mp4" \
  -vf "drawtext=text='Your Text Here':fontsize=48:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-th-60:enable='between(t,2,8)'" \
  -c:a copy "with_text.mp4"
```

### 10. Final export (1080p, optimized for YouTube)

```bash
# Export final video optimized for YouTube upload
ffmpeg -y -i "input.mp4" \
  -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  -r 30 \
  "output_final.mp4"
```

## Full Assembly Pipeline

The standard assembly order:

```bash
#!/bin/bash
set -e
DATE=$(date +%Y-%m-%d)
DIR="workspace/youtube/${DATE}"
FOOTAGE_DIR="${DIR}/footage"
OUTPUT="${DIR}/output.mp4"

echo "=== Step 1: Normalize all clips to 1080p30 ==="
mkdir -p "${DIR}/normalized"
for clip in "${FOOTAGE_DIR}"/*.mp4; do
  base=$(basename "$clip")
  ffmpeg -y -i "$clip" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
    -r 30 -c:v libx264 -preset fast -crf 23 \
    -c:a aac -ar 48000 -ac 2 \
    "${DIR}/normalized/${base}"
done

echo "=== Step 2: Create concat list ==="
: > /tmp/yt_concat.txt
for clip in "${DIR}/normalized"/*.mp4; do
  echo "file '${clip}'" >> /tmp/yt_concat.txt
done

echo "=== Step 3: Concatenate clips ==="
ffmpeg -y -f concat -safe 0 -i /tmp/yt_concat.txt -c copy "${DIR}/merged.mp4"

echo "=== Step 4: Trim to target duration ==="
# Default 60s for shorts; adjust as needed
TARGET_DURATION=60
ffmpeg -y -i "${DIR}/merged.mp4" -t ${TARGET_DURATION} -c copy "${DIR}/trimmed.mp4"

echo "=== Step 5: Generate captions ==="
if command -v whisper &> /dev/null; then
  whisper "${DIR}/trimmed.mp4" --model base --output_format srt --output_dir "${DIR}/"
  mv "${DIR}/trimmed.srt" "${DIR}/captions.srt" 2>/dev/null || true
else
  echo "Whisper not installed — skipping captions. Install: pip install openai-whisper"
fi

echo "=== Step 6: Burn captions (if available) ==="
if [ -f "${DIR}/captions.srt" ]; then
  ffmpeg -y -i "${DIR}/trimmed.mp4" \
    -vf "subtitles=${DIR}/captions.srt:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=40'" \
    -c:a copy "${DIR}/captioned.mp4"
  CURRENT="${DIR}/captioned.mp4"
else
  CURRENT="${DIR}/trimmed.mp4"
fi

echo "=== Step 7: Add intro/outro (if provided) ==="
# Check for intro/outro in agent knowledge
INTRO="workspace/agent-knowledge/youtube-creator/references/intro.mp4"
OUTRO="workspace/agent-knowledge/youtube-creator/references/outro.mp4"
if [ -f "$INTRO" ] || [ -f "$OUTRO" ]; then
  : > /tmp/yt_final_concat.txt
  [ -f "$INTRO" ] && echo "file '$(pwd)/${INTRO}'" >> /tmp/yt_final_concat.txt
  echo "file '$(pwd)/${CURRENT}'" >> /tmp/yt_final_concat.txt
  [ -f "$OUTRO" ] && echo "file '$(pwd)/${OUTRO}'" >> /tmp/yt_final_concat.txt
  ffmpeg -y -f concat -safe 0 -i /tmp/yt_final_concat.txt -c copy "${DIR}/with_intro_outro.mp4"
  CURRENT="${DIR}/with_intro_outro.mp4"
fi

echo "=== Step 8: Final export (YouTube-optimized) ==="
ffmpeg -y -i "$CURRENT" \
  -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  -r 30 \
  "$OUTPUT"

echo "=== Done! Output: ${OUTPUT} ==="
ffprobe -v quiet -print_format json -show_format "$OUTPUT" \
  | python3 -c "
import sys, json
f = json.load(sys.stdin)['format']
dur = float(f['duration'])
size_mb = int(f['size']) / 1024 / 1024
print(f'Duration: {dur:.1f}s | Size: {size_mb:.1f} MB')
"
```

## Premiere Pro MCP (Future)

When Premiere Pro MCP server (`hetpatel-11/Adobe_Premiere_Pro_MCP`) is available:
- Connect at `localhost` with `PREMIERE_TEMP_DIR=/tmp/premiere-mcp-bridge`
- Use for advanced editing: transitions, color grading, keyframe animations
- Falls back to FFmpeg if Premiere is not running

## Save Output

Final video: `workspace/youtube/YYYY-MM-DD/output.mp4`
Captions: `workspace/youtube/YYYY-MM-DD/captions.srt` + `captions.ass`

## Rules

- Always normalize clips to same resolution/framerate before concatenating.
- Use `-y` flag to auto-overwrite (no interactive prompts).
- Keep intermediate files until final export is confirmed good.
- If FFmpeg is not installed, tell user: `brew install ffmpeg`.
- If Whisper is not installed, skip captions and notify user.
- Target file size: under 2GB for YouTube upload (128GB max, but keep it reasonable).
