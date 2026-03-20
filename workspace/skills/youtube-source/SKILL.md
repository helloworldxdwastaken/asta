---
name: youtube-source
description: Find and download copyright-safe stock footage from Pexels, Pixabay, and Creative Commons YouTube videos for video production. Use when the user needs footage, b-roll, or video clips for their YouTube content.
metadata: {"clawdbot":{"emoji":"🎥","requires":{"bins":["curl","python3","yt-dlp"]}}}
---

# YouTube Footage Sourcing

Find and download copyright-safe footage for YouTube video production.

## API Keys

- `$PEXELS_API_KEY` — for Pexels stock video (add as `pexels_api_key` in Settings > Keys)
- `$PIXABAY_API_KEY` — for Pixabay stock video (add as `pixabay_api_key` in Settings > Keys)

## Sources (priority order)

The smart footage engine searches both **videos** and **photos** (photos get Ken Burns effects in the edit step).

### 1. Pexels Video API

```bash
# Search for stock footage on Pexels
QUERY="nature landscape"
curl -s "https://api.pexels.com/videos/search?query=${QUERY}&per_page=10&size=medium" \
  -H "Authorization: $PEXELS_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('videos', []):
    # Find the HD file
    hd = next((f for f in v['video_files'] if f.get('quality') == 'hd' and f.get('width', 0) >= 1920), None)
    if not hd:
        hd = v['video_files'][0] if v['video_files'] else None
    if hd:
        print(f\"- ID: {v['id']} | Duration: {v['duration']}s | {v['width']}x{v['height']}\")
        print(f\"  URL: {hd['link']}\")
        print(f\"  User: {v['user']['name']} | License: Pexels (free, no attribution required)\")
        print()
"
```

### 2. Pixabay Video API

```bash
# Search for stock footage on Pixabay
QUERY="technology"
curl -s "https://pixabay.com/api/videos/?key=$PIXABAY_API_KEY&q=${QUERY}&per_page=10&min_width=1920" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('hits', []):
    lg = v.get('videos', {}).get('large', {})
    print(f\"- ID: {v['id']} | Duration: {v['duration']}s | Tags: {v['tags']}\")
    print(f\"  URL: {lg.get('url', 'N/A')}\")
    print(f\"  User: {v['user']} | License: Pixabay (free, no attribution required)\")
    print()
"
```

### 3. Creative Commons YouTube Videos (via yt-dlp)

**IMPORTANT:** Only download videos with Creative Commons license. YouTube marks CC videos with license type in the API.

```bash
# First, search YouTube for CC-licensed videos on a topic
QUERY="nature documentary"
curl -s "https://www.googleapis.com/youtube/v3/search?part=snippet&q=${QUERY}&type=video&videoLicense=creativeCommon&maxResults=10&key=$YOUTUBE_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('items', []):
    s = item['snippet']
    vid = item['id']['videoId']
    print(f\"- {s['title']}\")
    print(f\"  ID: {vid} | Channel: {s['channelTitle']}\")
    print(f\"  URL: https://youtube.com/watch?v={vid}\")
    print(f\"  License: Creative Commons BY\")
    print()
"
```

```bash
# Download a CC-licensed video (only after confirming license)
VIDEO_URL="https://youtube.com/watch?v=VIDEO_ID"
OUTPUT_DIR="workspace/youtube/$(date +%Y-%m-%d)/footage"
mkdir -p "$OUTPUT_DIR"
yt-dlp -f 'bestvideo[height<=1080]+bestaudio/best[height<=1080]' \
  --merge-output-format mp4 \
  -o "${OUTPUT_DIR}/%(title)s.%(ext)s" \
  "$VIDEO_URL"
```

## Download Workflow

```bash
# Download from Pexels
OUTPUT_DIR="workspace/youtube/$(date +%Y-%m-%d)/footage"
mkdir -p "$OUTPUT_DIR"
VIDEO_URL="https://www.pexels.com/video/..."  # URL from search results
curl -L -o "${OUTPUT_DIR}/pexels_clip_001.mp4" "$VIDEO_URL"
```

```bash
# Download from Pixabay
OUTPUT_DIR="workspace/youtube/$(date +%Y-%m-%d)/footage"
mkdir -p "$OUTPUT_DIR"
VIDEO_URL="https://..."  # URL from search results
curl -L -o "${OUTPUT_DIR}/pixabay_clip_001.mp4" "$VIDEO_URL"
```

## Smart Footage Selection

The smart footage engine (`workspace/scripts/youtube/lib/smart_footage.py`) automatically ranks and selects the best clips.

### How it works

1. **Multi-query search**: generates diverse search queries from your topic (e.g., "AI news" → "AI news", "AI news aerial", "artificial intelligence", "AI technology")
2. **Relevance scoring (TF-IDF)**: scores each clip's tags/title against your topic (0-1)
3. **Duration scoring**: prefers 8-15s clips (ideal for editing), penalizes very short (<3s) or very long
4. **Resolution bonus**: +0.1 for 1080p+ clips
5. **Diversity pass**: re-orders to prevent 3+ consecutive clips from same source or query
6. **Duration targeting**: selects clips totaling 2.5× your target duration (e.g., 150s for a 60s video)
7. **Auto-download**: downloads top ranked clips automatically

### Usage

```bash
# Smart search + rank + auto-download
python3 workspace/scripts/youtube/lib/smart_footage.py search "artificial intelligence" \
  --count 10 --target-duration 60 --download \
  --output-dir workspace/youtube/2026-03-15/footage \
  --manifest workspace/youtube/2026-03-15/footage_manifest.json

# Or via pipeline
python3 workspace/scripts/youtube/pipeline.py source --topic "AI news" --auto-download --target-duration 60
```

### Script-to-Footage Matching

If a script exists, the engine can match footage to each visual cue:

```bash
# Match footage to script visual cues
python3 workspace/scripts/youtube/lib/smart_footage.py match workspace/youtube/2026-03-15/script.md
```

This reads `[TIMESTAMP] VISUAL: ...` blocks from the script and finds the best clips for each scene.

## Workflow

1. Take the chosen topic from the trends step.
2. **Smart search**: auto-generates 4-6 diverse queries from the topic.
3. Searches Pexels → Pixabay → CC YouTube in parallel.
4. **Ranks all clips** by relevance × duration × resolution × diversity.
5. **Selects top clips** to reach 2.5× target duration.
6. Presents ranked results with scores for user review.
7. **Auto-downloads** selected clips (or waits for user approval).
8. Saves manifest with scores and attribution.

## Save Output

Save footage manifest to:
```
workspace/youtube/YYYY-MM-DD/footage_manifest.json
```

Format:
```json
{
  "topic": "...",
  "total_clips": 8,
  "total_duration_seconds": 150,
  "clips": [
    {
      "filename": "pexels_12345_000.mp4",
      "source": "pexels",
      "source_id": "12345",
      "title": "Technology background",
      "duration_seconds": 15,
      "resolution": "1920x1080",
      "license": "Pexels License (free)",
      "attribution": "Creator Name",
      "search_query": "AI technology",
      "relevance_score": 0.85,
      "total_score": 0.78,
      "downloaded": true
    }
  ]
}
```

## Rules

- **NEVER download copyrighted footage.** Only Pexels, Pixabay, or verified CC-licensed videos.
- If yt-dlp is not installed, tell user: `brew install yt-dlp` or `pip install yt-dlp`.
- Always verify the license before downloading from YouTube (use the `videoLicense=creativeCommon` filter).
- Aim for 2-3x the target video duration in raw footage (e.g., 120s of clips for a 60s video).
- Prefer diversity in clips — different angles, settings, and compositions.
- When a script exists, use script-to-footage matching for best results.
