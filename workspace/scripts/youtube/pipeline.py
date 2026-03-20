#!/usr/bin/env python3
"""
YouTube Pipeline Orchestrator — run individual steps or the full pipeline.

Usage:
    python3 workspace/scripts/youtube/pipeline.py trends [--niche "tech"] [--region US] [--category 28]
    python3 workspace/scripts/youtube/pipeline.py source --topic "AI news" [--auto-download] [--target-duration 60]
    python3 workspace/scripts/youtube/pipeline.py edit --date 2026-03-15 [--duration 60] [--captions] [--caption-preset shorts]
    python3 workspace/scripts/youtube/pipeline.py status [--date 2026-03-15]
    python3 workspace/scripts/youtube/pipeline.py setup-check

API keys are read from environment (injected by Asta exec_tool):
    $YOUTUBE_API_KEY, $PEXELS_API_KEY, $PIXABAY_API_KEY
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote_plus
from urllib.error import HTTPError

# Add ~/.local/bin to PATH (pipx installs edge-tts, whisper there)
_local_bin = Path.home() / ".local" / "bin"
if _local_bin.is_dir() and str(_local_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_local_bin}:{os.environ.get('PATH', '')}"

# Add lib to path
LIB_DIR = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(LIB_DIR.parent))

WORKSPACE = Path(__file__).resolve().parent.parent.parent  # workspace/
YT_DIR = WORKSPACE / "youtube"

# ── Load API keys from Asta DB if not already in env ──────────────────────────
def _load_keys_from_db():
    """Inject API keys from Asta's SQLite DB into env (for CLI use outside exec_tool)."""
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "asta.db"
    if not db_path.exists():
        return
    import sqlite3
    key_map = {
        "pexels_api_key": "PEXELS_API_KEY",
        "pixabay_api_key": "PIXABAY_API_KEY",
        "youtube_api_key": "YOUTUBE_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
    }
    try:
        conn = sqlite3.connect(str(db_path))
        for db_name, env_name in key_map.items():
            if os.environ.get(env_name):
                continue
            row = conn.execute("SELECT value FROM api_keys WHERE key_name = ?", (db_name,)).fetchone()
            if row and row[0]:
                os.environ[env_name] = row[0]
        conn.close()
    except Exception:
        pass

_load_keys_from_db()


def today_dir():
    d = YT_DIR / datetime.now().strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def api_get(url, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code}: {body[:500]}", file=sys.stderr)
        return None


# ── Trends ─────────────────────────────────────────────────────────────────────

def cmd_trends(args):
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    if not yt_key:
        print("ERROR: $YOUTUBE_API_KEY not set. Add it in Settings > Keys as 'youtube_api_key'.")
        return 1

    out_dir = today_dir()
    results = {"date": datetime.now().strftime("%Y-%m-%d"), "niche": args.niche, "topics": []}

    # 1) YouTube trending in category
    print(f"=== YouTube Trending (region={args.region}, category={args.category}) ===")
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet,statistics&chart=mostPopular"
        f"&regionCode={args.region}&maxResults=20&key={yt_key}"
    )
    if args.category:
        url += f"&videoCategoryId={args.category}"
    data = api_get(url)
    if data:
        for v in data.get("items", []):
            s, st = v["snippet"], v.get("statistics", {})
            views = int(st.get("viewCount", 0))
            title = s["title"]
            tags = s.get("tags", [])[:8]
            print(f"  [{views:>12,} views] {title}")
            results["topics"].append({
                "topic": title,
                "source": "youtube_trending",
                "views": views,
                "channel": s["channelTitle"],
                "tags": tags,
            })

    # 2) Niche search (last 7 days, sorted by views)
    if args.niche:
        print(f"\n=== Niche Search: '{args.niche}' (last 7 days) ===")
        after = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        search_url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&q={quote_plus(args.niche)}&type=video"
            f"&order=viewCount&publishedAfter={after}&maxResults=15&key={yt_key}"
        )
        sdata = api_get(search_url)
        if sdata:
            ids = ",".join(
                i["id"]["videoId"] for i in sdata.get("items", [])
                if "videoId" in i.get("id", {})
            )
            if ids:
                detail_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={ids}&key={yt_key}"
                ddata = api_get(detail_url)
                if ddata:
                    for v in ddata.get("items", []):
                        s, st = v["snippet"], v.get("statistics", {})
                        views = int(st.get("viewCount", 0))
                        title = s["title"]
                        print(f"  [{views:>12,} views] {title}")
                        results["topics"].append({
                            "topic": title,
                            "source": "niche_search",
                            "views": views,
                            "channel": s["channelTitle"],
                            "tags": s.get("tags", [])[:8],
                        })

    # 3) Google Trends RSS
    print(f"\n=== Google Trends (daily, {args.region}) ===")
    try:
        import re
        req = Request(f"https://trends.google.com/trending/rss?geo={args.region}")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        titles = re.findall(r"<title>(.+?)</title>", content)[1:20]
        traffic = re.findall(r"<ht:approx_traffic>(.+?)</ht:approx_traffic>", content)
        for i, title in enumerate(titles):
            t = traffic[i] if i < len(traffic) else "?"
            print(f"  {i+1}. {title} ({t} searches)")
            results["topics"].append({
                "topic": title,
                "source": "google_trends",
                "search_volume": t,
            })
    except Exception as e:
        print(f"  Google Trends fetch failed: {e}")

    # Sort by views (YouTube items) then save
    results["topics"].sort(key=lambda x: x.get("views", 0), reverse=True)
    out_file = out_dir / "trends.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_file}")
    print(f"Total topics found: {len(results['topics'])}")
    return 0


# ── Script ─────────────────────────────────────────────────────────────────────

def cmd_script(args):
    """Generate script + metadata (delegates to model via skill — outputs template for manual or agent use)."""
    topic = args.topic
    if not topic:
        print("ERROR: --topic is required.")
        return 1

    out_dir = today_dir()
    duration_label = f"{args.duration}s short-form" if args.duration <= 60 else f"{args.duration // 60}min long-form"

    # Generate script template
    if args.duration <= 60:
        structure = """## Script Structure (Short-Form ≤60s)

[0:00-0:03] HOOK
VISUAL: (attention-grabbing opening shot)
NARRATION: "(hook line — question or shocking statement)"

[0:03-0:10] SETUP
VISUAL: (context visuals)
NARRATION: "(what this video is about)"

[0:10-0:45] BODY
VISUAL: (main content visuals — 2-3 key points)
NARRATION: "(core message)"

[0:45-0:55] PAYOFF
VISUAL: (climax or reveal shot)
NARRATION: "(surprising conclusion)"

[0:55-1:00] CTA
VISUAL: (subscribe animation / end screen)
NARRATION: "Subscribe for more!"
"""
    else:
        structure = """## Script Structure (Long-Form)

[0:00-0:30] COLD OPEN
VISUAL: (most interesting moment from the video)
NARRATION: "(teaser that hooks the viewer)"

[0:30-1:00] INTRO
VISUAL: (channel branding / topic setup)
NARRATION: "(what viewers will learn)"

[1:00-3:00] SECTION 1
VISUAL: (first main point visuals)
NARRATION: "(first key insight)"

[3:00-5:00] SECTION 2
VISUAL: (second main point visuals)
NARRATION: "(second key insight)"

[5:00-7:00] SECTION 3
VISUAL: (third main point visuals)
NARRATION: "(third key insight)"

[7:00-9:00] CLIMAX
VISUAL: (bringing it all together)
NARRATION: "(revelation / conclusion)"

[9:00-10:00] OUTRO + CTA
VISUAL: (end screen)
NARRATION: "(summary + subscribe CTA)"
"""

    script_content = f"""# Video Script: {topic}

**Target Duration**: {duration_label}
**Tone**: {args.tone}
**Date**: {datetime.now().strftime("%Y-%m-%d")}

{structure}

---

## Title Options

1. (Title option 1 — curiosity gap)
2. (Title option 2 — listicle/how-to)
3. (Title option 3 — shock/contrast)

## SEO Description

(First 2 lines are most important — shown before "Show more")
(Include main keyword 3-5 times naturally)
(Add timestamps, hashtags, credits)

## Tags

(15-30 tags, most specific first, total <500 chars)

## Thumbnail Concept

- Background: (scene description)
- Text: (max 4-5 words, large)
- Colors: (high contrast)
- Expression: (if face visible)
"""

    script_path = out_dir / "script.md"
    with open(script_path, "w") as f:
        f.write(script_content)

    # Generate metadata template
    metadata = {
        "topic": topic,
        "duration_target_seconds": args.duration,
        "tone": args.tone,
        "titles": [
            f"(Title 1 for: {topic})",
            f"(Title 2 for: {topic})",
            f"(Title 3 for: {topic})",
        ],
        "description": f"(SEO description for: {topic})",
        "tags": [topic.lower()] + topic.lower().split()[:5],
        "thumbnail_concept": "(thumbnail description)",
        "category_id": 28,
        "default_language": "en",
        "privacy": "private",
    }
    metadata_path = out_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Script template saved: {script_path}")
    print(f"Metadata template saved: {metadata_path}")
    print(f"\nNOTE: This is a template. The YouTube Creator agent will fill in the actual")
    print(f"content when you use the youtube-script skill. Edit the files or ask the agent")
    print(f"to write the script: '@YouTube Creator write a script about {topic}'")
    return 0


# ── Upload (with approval) ────────────────────────────────────────────────────

def cmd_upload(args):
    """Upload video to YouTube — REQUIRES explicit --confirm flag."""
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    work_dir = YT_DIR / date_str

    video_path = work_dir / "output" / "output.mp4"
    metadata_path = work_dir / "metadata.json"

    if not video_path.exists():
        print(f"ERROR: No video found at {video_path}")
        print("Run the 'edit' step first.")
        return 1

    if not metadata_path.exists():
        print(f"ERROR: No metadata found at {metadata_path}")
        print("Run the 'script' step first.")
        return 1

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Show what will be uploaded
    size_mb = video_path.stat().st_size / 1024 / 1024
    print(f"=== Upload Preview ===\n")
    print(f"  Video: {video_path} ({size_mb:.1f} MB)")
    print(f"  Title: {metadata.get('titles', ['?'])[0]}")
    print(f"  Description: {metadata.get('description', '?')[:100]}...")
    print(f"  Tags: {', '.join(metadata.get('tags', [])[:10])}")
    print(f"  Privacy: {metadata.get('privacy', 'private')}")
    print(f"  Category: {metadata.get('category_id', '?')}")

    # Validate metadata
    title = metadata.get("titles", [""])[0]
    if len(title) > 100:
        print(f"\n  WARNING: Title is {len(title)} chars (max 100)")
    desc = metadata.get("description", "")
    if len(desc) > 5000:
        print(f"\n  WARNING: Description is {len(desc)} chars (max 5000)")
    tags_str = ",".join(metadata.get("tags", []))
    if len(tags_str) > 500:
        print(f"\n  WARNING: Tags total {len(tags_str)} chars (max 500)")

    # APPROVAL CHECK
    if not args.confirm:
        print(f"\n  ⛔ Upload NOT executed. To upload, re-run with --confirm:")
        print(f"  python3 workspace/scripts/youtube/pipeline.py upload --date {date_str} --confirm")
        print(f"\n  Or ask the YouTube Creator agent: 'approve and upload'")
        return 0

    # Check OAuth tokens
    tokens_path = WORKSPACE / "agent-knowledge" / "youtube-creator" / "references" / "youtube_tokens.json"
    if not tokens_path.exists():
        print(f"\nERROR: YouTube OAuth not configured.")
        print(f"Run the OAuth setup in the youtube-upload skill first.")
        return 1

    print(f"\n=== Uploading to YouTube ===")
    # Refresh access token
    with open(tokens_path) as f:
        tokens = json.load(f)

    from urllib.parse import urlencode as _urlencode
    token_data = _urlencode({
        "client_id": tokens["client_id"],
        "client_secret": tokens["client_secret"],
        "refresh_token": tokens["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = Request("https://oauth2.googleapis.com/token", data=token_data)
    try:
        with urlopen(req, timeout=15) as resp:
            token_resp = json.loads(resp.read())
        access_token = token_resp["access_token"]
    except Exception as e:
        print(f"ERROR: Failed to refresh OAuth token: {e}")
        return 1

    # Upload via resumable upload
    upload_metadata = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": metadata.get("tags", []),
            "categoryId": str(metadata.get("category_id", 28)),
            "defaultLanguage": metadata.get("default_language", "en"),
        },
        "status": {
            "privacyStatus": metadata.get("privacy", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }

    # Step 1: Initiate resumable upload
    init_req = Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(upload_metadata).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        method="POST",
    )
    try:
        with urlopen(init_req, timeout=30) as resp:
            upload_url = resp.headers.get("Location")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: Upload init failed: {e.code} {body[:500]}")
        return 1

    if not upload_url:
        print("ERROR: No upload URL returned from YouTube API")
        return 1

    # Step 2: Upload video binary
    print(f"  Uploading {size_mb:.1f} MB...")
    result = subprocess.run(
        [
            "curl", "-s", "-X", "PUT", upload_url,
            "-H", f"Authorization: Bearer {access_token}",
            "-H", "Content-Type: video/mp4",
            "--data-binary", f"@{video_path}",
        ],
        capture_output=True, text=True, timeout=600,
    )

    if result.returncode != 0:
        print(f"ERROR: Upload failed: {result.stderr[:500]}")
        return 1

    try:
        upload_result = json.loads(result.stdout)
        video_id = upload_result.get("id", "?")
        print(f"\n  Upload complete!")
        print(f"  Video ID: {video_id}")
        print(f"  URL: https://youtube.com/watch?v={video_id}")
        print(f"  Status: {upload_result.get('status', {}).get('uploadStatus', '?')}")
        print(f"  Privacy: {upload_result.get('status', {}).get('privacyStatus', '?')}")

        # Save result
        result_path = work_dir / "upload_result.json"
        with open(result_path, "w") as f:
            json.dump(upload_result, f, indent=2)
        print(f"  Saved: {result_path}")
    except json.JSONDecodeError:
        print(f"Upload response (not JSON): {result.stdout[:500]}")
        return 1

    return 0


# ── Source (Smart) ─────────────────────────────────────────────────────────────

def cmd_source(args):
    topic = args.topic
    if not topic:
        print("ERROR: --topic is required.")
        return 1

    from lib.smart_footage import SmartFootageSelector

    out_dir = today_dir()
    footage_dir = out_dir / "footage"
    footage_dir.mkdir(parents=True, exist_ok=True)

    selector = SmartFootageSelector()

    # Check for script to enable script-to-footage matching
    script_sections = None
    script_path = out_dir / "script.md"
    if script_path.exists() and args.match_script:
        print("=== Script found — enabling script-to-footage matching ===")
        with open(script_path) as f:
            script_sections = f.read().split("\n\n")

    print(f"=== Smart Footage Search: '{topic}' ===\n")
    clips = selector.search(topic, count_per_source=args.count, script_sections=script_sections)

    if not clips:
        print("No clips found. Check API keys.")
        return 1

    # Rank
    print(f"\n=== Ranking {len(clips)} clips ===")
    ranked = selector.rank(clips, topic=topic, target_duration=args.target_duration)

    # Select for duration
    selected = selector.select_for_duration(ranked, target_duration=args.target_duration)

    print(f"\n=== Top {len(selected)} clips (target: {args.target_duration}s video) ===\n")
    for i, c in enumerate(selected):
        print(f"  {i+1}. [{c.total_score:.2f}] {c.source}/{c.source_id} | {c.duration_seconds}s | {c.title[:50]}")
        print(f"     Relevance: {c.relevance_score:.2f} | Duration: {c.duration_score:.2f} | Query: {c.search_query}")

    # Download if requested
    if args.auto_download:
        print(f"\n=== Auto-downloading to {footage_dir}/ ===\n")
        downloaded = selector.download(selected, str(footage_dir))
        selector.save_manifest(downloaded, str(out_dir / "footage_manifest.json"), topic=topic)
    else:
        selector.save_manifest(selected, str(out_dir / "footage_manifest.json"), topic=topic)
        print(f"\nTo download, re-run with --auto-download")

    return 0


# ── Edit (Smart) ──────────────────────────────────────────────────────────────

def cmd_edit(args):
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    work_dir = YT_DIR / date_str
    footage_dir = work_dir / "footage"

    if not footage_dir.exists() or not list(footage_dir.glob("*.mp4")):
        print(f"ERROR: No footage found in {footage_dir}")
        print("Run the 'source' step first with --auto-download.")
        return 1

    if not _has_bin("ffmpeg"):
        print("ERROR: ffmpeg not installed. Run: brew install ffmpeg")
        return 1

    # ── Format presets ────────────────────────────────────────────────────
    fmt = getattr(args, "format", "standard")
    is_vertical = fmt == "short"
    if fmt == "short":
        if args.duration == 60:  # only override if user didn't set it
            args.duration = 45   # 45s sweet spot for Shorts
        args.max_clip_dur = min(getattr(args, "max_clip_dur", 3.0), 3.0)
        args.caption_preset = "shorts"
        print(f"=== Format: SHORT (vertical 9:16, ≤60s, fast cuts) ===")
    elif fmt == "long":
        if args.duration == 60:
            args.duration = 480  # 8 min
        args.max_clip_dur = min(getattr(args, "max_clip_dur", 8.0), 8.0)
        print(f"=== Format: LONG (16:9, 8+ min) ===")
    else:
        if args.duration == 60:
            args.duration = 180  # 3 min default for standard
        print(f"=== Format: STANDARD (16:9, 2-5 min) ===")

    from lib.video_fx import (
        parse_script_sections, match_clips_to_sections, split_clip_segments,
        apply_ken_burns, concat_with_crossfade, apply_color_grade,
        add_subscribe_overlay, add_lower_thirds, mix_with_ducking,
        generate_ambient_music, probe_duration, is_still_image,
    )

    clips = sorted(list(footage_dir.glob("*.mp4")) + list(footage_dir.glob("*.jpg")) + list(footage_dir.glob("*.png")))
    build_dir = work_dir / "build"
    build_dir.mkdir(exist_ok=True)
    output_dir = work_dir / "output"
    output_dir.mkdir(exist_ok=True)
    norm_dir = build_dir / "normalized"
    norm_dir.mkdir(exist_ok=True)
    seg_dir = build_dir / "segments"
    seg_dir.mkdir(exist_ok=True)

    agent_refs = WORKSPACE / "agent-knowledge" / "youtube-creator" / "references"
    script_path = work_dir / "script.md"

    # ── Step 1: Voiceover ─────────────────────────────────────────────────
    vo_path = None
    vo_duration = None
    if script_path.exists() and _has_bin("edge-tts"):
        print("=== Step 1: Generating voiceover from script ===")
        try:
            from lib.voiceover import generate_voiceover_from_script
            vo_path = generate_voiceover_from_script(
                script_path=str(script_path),
                output_dir=str(build_dir),
                voice=getattr(args, "voice", "male"),
                rate=getattr(args, "rate", "+0%"),
            )
            if vo_path:
                vo_duration = probe_duration(vo_path)
                print(f"  Voiceover duration: {vo_duration:.1f}s")
        except ImportError:
            print("  Voiceover library not found, skipping.")
    elif script_path.exists():
        print("=== Step 1: Skipping voiceover (edge-tts not installed) ===")

    if vo_duration:
        duration = vo_duration + 1.0
        print(f"  Video will be trimmed to {duration:.1f}s (voiceover + 1s buffer)")
    else:
        duration = args.duration
        print(f"  No voiceover — using --duration {duration}s")

    # ── Step 2: Parse script sections for scene sync ──────────────────────
    sections = []
    if script_path.exists():
        sections = parse_script_sections(str(script_path))
        if sections:
            print(f"=== Step 2: Script parsed — {len(sections)} sections for scene sync ===")
            for s in sections:
                print(f"  [{s.start_hint:.0f}s-{s.start_hint + s.duration:.0f}s] {s.title}")
        else:
            print("=== Step 2: No section timestamps found in script ===")

    # ── Step 3: Normalize clips to 1080p30 (muted) / photos to 1080p ────
    photos_count = sum(1 for c in clips if c.suffix.lower() in (".jpg", ".jpeg", ".png"))
    videos_count = len(clips) - photos_count
    print(f"=== Step 3: Normalizing {len(clips)} files ({videos_count} videos, {photos_count} photos) ===")
    for clip in clips:
        is_photo = clip.suffix.lower() in (".jpg", ".jpeg", ".png")
        if is_photo:
            # Keep as image — just scale to 1080p for Ken Burns later
            out = norm_dir / clip.with_suffix(".jpg").name
            if out.exists():
                print(f"  [skip] {clip.name}")
                continue
            cmd = [
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                str(out),
            ]
        else:
            out = norm_dir / clip.name
            if out.exists():
                print(f"  [skip] {clip.name}")
                continue
            cmd = [
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-an", str(out),
            ]
        print(f"  {'Photo' if is_photo else 'Video'}: {clip.name}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  WARNING: Failed {clip.name}: {result.stderr[:200]}")

    norm_clips = sorted(list(norm_dir.glob("*.mp4")) + list(norm_dir.glob("*.jpg")) + list(norm_dir.glob("*.png")))
    if not norm_clips:
        print("ERROR: No clips normalized.")
        return 1

    # ── Step 4: Scene-synced clip splitting + Ken Burns ───────────────────
    print(f"=== Step 4: Scene sync + Ken Burns (max {args.max_clip_dur}s/clip, min {args.min_clips} clips) ===")
    norm_paths = [str(c) for c in norm_clips]

    if sections:
        matched = match_clips_to_sections(norm_paths, sections, duration)
        print(f"  Matched {len(matched)} segments across {len(sections)} sections")
    else:
        raw_segs = split_clip_segments(norm_paths, max_dur=args.max_clip_dur, min_clips=args.min_clips)
        matched = [(s[0], s[1], s[2], "") for s in raw_segs]
        print(f"  Split into {len(matched)} segments (no script sections)")

    # Extract each segment — Ken Burns for still images, trim for videos
    kb_directions = ["zoom_in", "zoom_out", "pan_left", "pan_right"]
    segment_paths = []
    kb_count = 0
    for i, (clip, start, seg_dur, section_title) in enumerate(matched):
        seg_out = str(seg_dir / f"seg_{i:03d}.mp4")
        if Path(seg_out).exists():
            segment_paths.append(seg_out)
            continue

        if is_still_image(clip):
            # Still image → apply Ken Burns for smooth motion
            kb_dir = kb_directions[i % len(kb_directions)]
            ok = apply_ken_burns(clip, seg_out, seg_dur, direction=kb_dir)
            if ok and Path(seg_out).exists():
                segment_paths.append(seg_out)
                kb_count += 1
                continue
            # Ken Burns failed on image — create static video from image
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", clip, "-t", str(seg_dur),
                 "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                 "-r", "30", "-an", seg_out],
                capture_output=True, timeout=60,
            )
            if Path(seg_out).exists():
                segment_paths.append(seg_out)
                continue

        # Video clip → just trim the segment (no zoom/pan)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start), "-i", clip, "-t", str(seg_dur),
             "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", "-r", "30", seg_out],
            capture_output=True, timeout=60,
        )
        if Path(seg_out).exists():
            segment_paths.append(seg_out)

    print(f"  Created {len(segment_paths)} segments ({kb_count} photos with Ken Burns, {len(segment_paths) - kb_count} video cuts)")

    # ── Step 5: Crossfade transitions + concat ────────────────────────────
    print("=== Step 5: Crossfade transitions ===")
    merged = str(build_dir / "merged.mp4")
    ok = concat_with_crossfade(segment_paths, merged, crossfade_dur=0.4)
    if not ok:
        print("ERROR: Concat failed.")
        return 1

    # Trim to target duration
    trimmed = str(build_dir / "trimmed.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-i", merged, "-t", str(duration),
         "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", "-r", "30", trimmed],
        capture_output=True, timeout=120,
    )
    current = trimmed

    # ── Step 6: Color grading / LUT ──────────────────────────────────────
    print(f"=== Step 6: Color grading ({args.color_grade}) ===")
    graded = str(build_dir / "graded.mp4")
    if apply_color_grade(current, graded, style=args.color_grade):
        current = graded
        print(f"  Applied '{args.color_grade}' grade")
    else:
        print("  Color grading skipped (filter error)")

    # ── Step 7: Mix voiceover (loudnorm -16 LUFS) ────────────────────────
    if vo_path and Path(vo_path).exists():
        print("=== Step 7: Mixing voiceover ===")
        with_vo = str(build_dir / "with_voiceover.mp4")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", current, "-i", vo_path,
             "-filter_complex", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[vo]",
             "-c:v", "copy", "-map", "0:v", "-map", "[vo]",
             "-c:a", "aac", "-b:a", "192k", with_vo],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and Path(with_vo).exists():
            current = with_vo
            print("  Voiceover mixed (normalized to -16 LUFS)")
    else:
        # Add silent audio track so downstream steps work
        print("=== Step 7: Adding silent audio track ===")
        silent = str(build_dir / "with_silent.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", current,
             "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
             "-t", str(duration), "-c:v", "copy", "-c:a", "aac", "-shortest", silent],
            capture_output=True, timeout=30,
        )
        if Path(silent).exists():
            current = silent

    # ── Step 8: Smart Captions ────────────────────────────────────────────
    if args.captions:
        print(f"=== Step 8: Smart Captions (preset={args.caption_preset}) ===")
        try:
            from lib.smart_captions import generate_captions, burn_captions, CaptionPreset
            preset = CaptionPreset(args.caption_preset)
            srt_path = str(build_dir / "captions.srt")
            ass_path = str(build_dir / "captions.ass")

            ok = generate_captions(
                video_path=current, output_srt=srt_path, output_ass=ass_path,
                preset=preset, whisper_method="auto",
            )
            if ok:
                print("  Burning captions into video...")
                captioned = str(build_dir / "captioned.mp4")
                if burn_captions(video_path=current, ass_path=ass_path, output_path=captioned):
                    if Path(captioned).exists():
                        current = captioned
                        print("  Captions burned")
                else:
                    print("  Caption burn failed")
            else:
                print("  No speech detected or Whisper unavailable")
        except ImportError:
            print("  Smart captions not available, trying basic Whisper...")
            _fallback_captions(Path(current), build_dir)

    # ── Step 9: Lower thirds — disabled (clean look) ───────────────────
    # Lower thirds can be enabled by passing --lower-thirds flag
    if getattr(args, "lower_thirds", False) and sections:
        print("=== Step 9: Lower thirds ===")
        with_lt = str(build_dir / "with_lower_thirds.mp4")
        if add_lower_thirds(current, with_lt, sections, duration):
            current = with_lt
            print(f"  Added {len(sections)} section overlays")
    else:
        print("=== Step 9: Lower thirds (off) ===")

    # ── Step 10: Background music with ducking ───────────────────────────
    music_path = None
    if args.music:
        music_path = Path(args.music)
    else:
        for name in ("bgm.mp3", "bgm.m4a", "bgm.wav", "background_music.mp3"):
            candidate = agent_refs / name
            if candidate.exists():
                music_path = candidate
                break
        if not music_path:
            print("=== Step 10: Generating ambient background music ===")
            ambient = str(build_dir / "ambient_bgm.mp3")
            if generate_ambient_music(ambient, duration):
                music_path = Path(ambient)
                print(f"  Generated ambient pad ({duration:.0f}s)")
            else:
                print("  Music generation failed")

    if music_path and music_path.exists():
        print(f"=== Step 10: Mixing background music with ducking ({music_path.name}) ===")
        with_music = str(build_dir / "with_music.mp4")
        vol = getattr(args, "music_volume", 0.15)
        if mix_with_ducking(current, str(music_path), with_music, music_vol=vol):
            if Path(with_music).exists():
                current = with_music
                print("  Music mixed with auto-ducking")
        else:
            print("  Music mix failed")
    else:
        print("=== Step 10: No background music ===")

    # ── Step 11: Subscribe overlay (last 5s) ─────────────────────────────
    print("=== Step 11: Subscribe + Like overlay ===")
    with_sub = str(build_dir / "with_subscribe.mp4")
    if add_subscribe_overlay(current, with_sub, show_seconds=5.0):
        current = with_sub
        print("  Subscribe overlay added (last 5s)")
    else:
        print("  Subscribe overlay skipped")

    # ── Step 12: Intro/outro ─────────────────────────────────────────────
    intro = agent_refs / "intro.mp4"
    outro = agent_refs / "outro.mp4"
    if intro.exists() or outro.exists():
        print("=== Step 12: Adding intro/outro ===")
        final_concat = build_dir / "final_concat.txt"
        with open(final_concat, "w") as f:
            if intro.exists():
                f.write(f"file '{intro}'\n")
            f.write(f"file '{current}'\n")
            if outro.exists():
                f.write(f"file '{outro}'\n")
        with_io = str(build_dir / "with_intro_outro.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(final_concat), "-c", "copy", with_io],
            capture_output=True,
        )
        if Path(with_io).exists():
            current = with_io
    else:
        print("=== Step 12: No intro/outro (skipping) ===")

    # ── Step 13: Vertical crop for Shorts ───────────────────────────────
    if is_vertical:
        print("=== Step 13: Cropping to vertical 9:16 (1080x1920) ===")
        vertical = str(build_dir / "vertical.mp4")
        # Center crop from 1920x1080 → 608x1080, then scale to 1080x1920
        subprocess.run(
            ["ffmpeg", "-y", "-i", current,
             "-vf", "crop=ih*9/16:ih,scale=1080:1920",
             "-c:a", "copy", vertical],
            capture_output=True, timeout=180,
        )
        if Path(vertical).exists():
            current = vertical
            print("  Cropped to 1080x1920 vertical")

    # ── Step 14: Final export (YouTube-optimized) ────────────────────────
    res = "1080x1920" if is_vertical else "1920x1080"
    print(f"=== Step 14: Final export ({res}, YouTube-optimized) ===")
    output = output_dir / "output.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", current,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-profile:v", "high", "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-r", "30",
            str(output),
        ],
        capture_output=True, timeout=300,
    )

    if output.exists():
        info_r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(output)],
            capture_output=True, text=True,
        )
        if info_r.returncode == 0:
            info = json.loads(info_r.stdout).get("format", {})
            dur = float(info.get("duration", 0))
            size_mb = int(info.get("size", 0)) / 1024 / 1024
            print(f"\nDone! Output: {output}")
            print(f"Format: {fmt.upper()} {'(vertical)' if is_vertical else '(horizontal)'}")
            print(f"Duration: {dur:.1f}s | Size: {size_mb:.1f} MB")
        else:
            print(f"\nDone! Output: {output}")
    else:
        print("ERROR: Final export failed.")
        return 1

    return 0


def _fallback_captions(video_path, work_dir):
    """Fallback: basic Whisper SRT generation."""
    if _has_bin("whisper"):
        subprocess.run(
            ["whisper", str(video_path), "--model", "base", "--output_format", "srt", "--output_dir", str(work_dir)],
            capture_output=True,
        )
        whisper_out = work_dir / f"{video_path.stem}.srt"
        captions_file = work_dir / "captions.srt"
        if whisper_out.exists():
            whisper_out.rename(captions_file)
    else:
        print("  Whisper not installed — skipping captions. Install: pip install openai-whisper")


# ── Status ─────────────────────────────────────────────────────────────────────

def cmd_status(args):
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    work_dir = YT_DIR / date_str

    if not work_dir.exists():
        print(f"No pipeline data for {date_str}")
        return 0

    print(f"=== YouTube Pipeline Status: {date_str} ===\n")

    steps = [
        ("Trends", work_dir / "trends.json"),
        ("Footage Manifest", work_dir / "footage_manifest.json"),
        ("Script", work_dir / "script.md"),
        ("Metadata", work_dir / "metadata.json"),
        ("Voiceover", work_dir / "build" / "voiceover.mp3"),
        ("Captions (SRT)", work_dir / "build" / "captions.srt"),
        ("Captions (ASS)", work_dir / "build" / "captions.ass"),
        ("Output Video", work_dir / "output" / "output.mp4"),
        ("Upload Result", work_dir / "upload_result.json"),
    ]

    for name, path in steps:
        if path.exists():
            size = path.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} bytes"
            print(f"  [done] {name}: {path.name} ({size_str})")
        else:
            print(f"  [    ] {name}: not yet")

    # Footage count
    footage_dir = work_dir / "footage"
    if footage_dir.exists():
        clips = list(footage_dir.glob("*.mp4"))
        print(f"\n  Footage clips: {len(clips)}")

    return 0


# ── Setup Check ────────────────────────────────────────────────────────────────

def cmd_setup_check(args):
    print("=== YouTube Pipeline Setup Check ===\n")

    keys = {
        "YOUTUBE_API_KEY": "YouTube Data API v3 (trends + upload)",
        "PEXELS_API_KEY": "Pexels stock footage",
        "PIXABAY_API_KEY": "Pixabay stock footage",
        "OPENAI_API_KEY": "Whisper API (optional, for captions)",
    }
    print("API Keys:")
    for key, desc in keys.items():
        val = os.environ.get(key)
        status = "set" if val else "MISSING"
        print(f"  [{status:>7}] {key} — {desc}")

    print("\nBinaries:")
    bins = {
        "ffmpeg": "Video editing (required)",
        "ffprobe": "Video analysis (required)",
        "yt-dlp": "CC YouTube downloads (optional)",
        "whisper": "Caption generation (optional)",
    }
    for b, desc in bins.items():
        status = "found" if _has_bin(b) else "MISSING"
        print(f"  [{status:>7}] {b} — {desc}")

    print("\nBinaries (voiceover):")
    vo_bins = {
        "edge-tts": "Edge-TTS voiceover (free). Install: pip install edge-tts",
    }
    for b, desc in vo_bins.items():
        status = "found" if _has_bin(b) else "MISSING"
        print(f"  [{status:>7}] {b} — {desc}")

    print("\nSmart Engines:")
    engines = [
        ("lib.smart_captions", "Word-level captions with ASS animations + contrast detection"),
        ("lib.smart_footage", "TF-IDF footage ranking + auto-download + resume"),
        ("lib.voiceover", "Edge-TTS voiceover generation"),
    ]
    for mod, desc in engines:
        try:
            __import__(mod)
            print(f"  [  ready] {mod} — {desc}")
        except ImportError:
            print(f"  [missing] {mod} — {desc}")

    print("\nYouTube OAuth:")
    tokens_file = WORKSPACE / "agent-knowledge" / "youtube-creator" / "references" / "youtube_tokens.json"
    if tokens_file.exists():
        print(f"  [  ready] {tokens_file}")
    else:
        print(f"  [not set] YouTube OAuth tokens not configured (needed for uploads)")

    print("\nIntro/Outro:")
    for name in ["intro.mp4", "outro.mp4"]:
        path = WORKSPACE / "agent-knowledge" / "youtube-creator" / "references" / name
        if path.exists():
            print(f"  [  found] {path}")
        else:
            print(f"  [missing] {name} — place in {path.parent}/")

    return 0


# ── Voiceover ──────────────────────────────────────────────────────────────────

def cmd_voiceover(args):
    """Generate voiceover from script using Edge-TTS."""
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    work_dir = YT_DIR / date_str

    script_path = work_dir / "script.md"
    if not script_path.exists():
        print(f"ERROR: No script found at {script_path}")
        print("Run the 'script' step first.")
        return 1

    try:
        from lib.voiceover import generate_voiceover_from_script, mix_voiceover_with_video
    except ImportError:
        print("ERROR: voiceover library not found.")
        return 1

    if not _has_bin("edge-tts"):
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return 1

    output_dir = work_dir / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"=== Generating voiceover from script ===")
    vo_path = generate_voiceover_from_script(
        script_path=str(script_path),
        output_dir=str(output_dir),
        voice=args.voice,
        rate=args.rate,
        mode=args.mode,
    )

    if not vo_path:
        print("ERROR: Voiceover generation failed.")
        return 1

    # Optionally mix with existing video
    video_path = output_dir / "output.mp4"
    if args.mix and video_path.exists():
        print(f"\n=== Mixing voiceover with {video_path.name} ===")
        mixed = output_dir / "output_with_vo.mp4"
        ok = mix_voiceover_with_video(
            video_path=str(video_path),
            voiceover_path=vo_path,
            output_path=str(mixed),
        )
        if ok:
            print(f"Mixed output: {mixed}")
    elif args.mix:
        print(f"No output.mp4 found to mix with. Run 'edit' first, then 'voiceover --mix'.")

    return 0


# ── Cron Schedule ──────────────────────────────────────────────────────────────

def cmd_schedule(args):
    """
    Register a daily YouTube pipeline cron job via Asta's cron system.
    Creates a cron entry that runs: trends → (waits for user) or full pipeline.
    """
    import sqlite3

    db_path = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "asta.db"
    if not db_path.exists():
        print(f"ERROR: Asta database not found at {db_path}")
        return 1

    if args.remove:
        # Remove existing YouTube cron
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM cron_jobs WHERE name LIKE 'youtube_%'")
        conn.commit()
        conn.close()
        print("YouTube cron jobs removed.")
        return 0

    if args.list:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT name, schedule, prompt, enabled FROM cron_jobs WHERE name LIKE 'youtube_%'").fetchall()
        conn.close()
        if rows:
            print("=== YouTube Cron Jobs ===\n")
            for name, schedule, prompt, enabled in rows:
                status = "ON" if enabled else "OFF"
                print(f"  [{status}] {name}: {schedule}")
                print(f"       Prompt: {prompt[:80]}...")
        else:
            print("No YouTube cron jobs configured.")
        return 0

    # Create cron job
    cron_schedule = args.cron or "0 9 * * *"  # default: 9am daily
    niche = args.niche or "tech"

    prompt = (
        f"@YouTube Creator Find today's trending topics in the '{niche}' niche. "
        f"Show me the top 5 and recommend the best one for a video."
    )

    if args.full_auto:
        prompt = (
            f"@YouTube Creator Run the full YouTube pipeline for the '{niche}' niche: "
            f"find trends, pick the best topic, source footage, write a script, "
            f"and edit the video. Save everything to today's folder. "
            f"Do NOT upload — just prepare everything for my review."
        )

    conn = sqlite3.connect(str(db_path))
    # Check if exists
    existing = conn.execute("SELECT id FROM cron_jobs WHERE name = 'youtube_daily'").fetchone()
    if existing:
        conn.execute(
            "UPDATE cron_jobs SET schedule = ?, prompt = ?, enabled = 1 WHERE name = 'youtube_daily'",
            (cron_schedule, prompt),
        )
        print(f"Updated YouTube daily cron: {cron_schedule}")
    else:
        conn.execute(
            "INSERT INTO cron_jobs (name, schedule, prompt, enabled, user_id) VALUES (?, ?, ?, 1, 'default')",
            ("youtube_daily", cron_schedule, prompt),
        )
        print(f"Created YouTube daily cron: {cron_schedule}")

    conn.commit()
    conn.close()

    print(f"  Schedule: {cron_schedule}")
    print(f"  Niche: {niche}")
    print(f"  Mode: {'full auto (no upload)' if args.full_auto else 'trends only (you pick the topic)'}")
    print(f"\n  The cron will run as the YouTube Creator agent.")
    return 0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _has_bin(name):
    from shutil import which
    return which(name) is not None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube Pipeline Orchestrator")
    sub = parser.add_subparsers(dest="command")

    # trends
    p_trends = sub.add_parser("trends", help="Find trending topics")
    p_trends.add_argument("--niche", default="", help="Your niche/topic")
    p_trends.add_argument("--region", default="US", help="Region code (default: US)")
    p_trends.add_argument("--category", default="", help="YouTube category ID")

    # script
    p_script = sub.add_parser("script", help="Generate script + metadata template")
    p_script.add_argument("--topic", required=True, help="Video topic")
    p_script.add_argument("--duration", type=int, default=60, help="Target duration in seconds")
    p_script.add_argument("--tone", default="conversational", help="Tone (conversational, educational, dramatic)")

    # upload (with approval)
    p_upload = sub.add_parser("upload", help="Upload video to YouTube (requires --confirm)")
    p_upload.add_argument("--date", default="", help="Date folder (YYYY-MM-DD, default: today)")
    p_upload.add_argument("--confirm", action="store_true", help="REQUIRED — confirm you want to upload")

    # source (smart)
    p_source = sub.add_parser("source", help="Smart footage search + rank + download")
    p_source.add_argument("--topic", required=True, help="Topic to search for")
    p_source.add_argument("--count", type=int, default=10, help="Results per source per query")
    p_source.add_argument("--target-duration", type=int, default=60, help="Target video duration")
    p_source.add_argument("--auto-download", action="store_true", help="Auto-download top ranked clips")
    p_source.add_argument("--match-script", action="store_true", help="Match footage to script visual cues")

    # edit (smart)
    p_edit = sub.add_parser("edit", help="Auto-edit video with all effects")
    p_edit.add_argument("--date", default="", help="Date folder (YYYY-MM-DD, default: today)")
    p_edit.add_argument("--duration", type=int, default=60, help="Target duration in seconds")
    p_edit.add_argument("--captions", action="store_true", help="Generate smart captions")
    p_edit.add_argument("--caption-preset", default="shorts",
                       choices=["shorts", "standard", "karaoke", "minimal"],
                       help="Caption style preset")
    p_edit.add_argument("--music", default="", help="Path to background music file")
    p_edit.add_argument("--music-volume", type=float, default=0.15, help="Background music volume (0-1)")
    p_edit.add_argument("--color-grade", default="cinematic",
                       choices=["cinematic", "warm", "cool", "vibrant", "moody"],
                       help="Color grading style")
    p_edit.add_argument("--max-clip-dur", type=float, default=5.0, help="Max seconds per clip before cutting")
    p_edit.add_argument("--min-clips", type=int, default=5, help="Minimum unique clips")
    p_edit.add_argument("--format", default="standard",
                       choices=["short", "standard", "long"],
                       help="Video format: short (≤60s vertical 9:16), standard (2-5min 16:9), long (8-15min 16:9)")
    p_edit.add_argument("--lower-thirds", action="store_true", help="Show section title overlays")

    # voiceover
    p_vo = sub.add_parser("voiceover", help="Generate voiceover from script (Edge-TTS)")
    p_vo.add_argument("--date", default="", help="Date folder (YYYY-MM-DD, default: today)")
    p_vo.add_argument("--voice", default="male", help="Voice: male, female, warm, narrator, or full name")
    p_vo.add_argument("--rate", default="+0%", help="Speech rate, e.g. +10pct or -20pct")
    p_vo.add_argument("--mode", choices=["full", "sections"], default="full", help="full=one file, sections=per-section")
    p_vo.add_argument("--mix", action="store_true", help="Mix voiceover with output.mp4")

    # schedule
    p_sched = sub.add_parser("schedule", help="Set up daily YouTube cron job")
    p_sched.add_argument("--cron", default="", help="Cron schedule (default: '0 9 * * *' = 9am daily)")
    p_sched.add_argument("--niche", default="", help="Your niche/topic")
    p_sched.add_argument("--full-auto", action="store_true", help="Full pipeline (not just trends)")
    p_sched.add_argument("--remove", action="store_true", help="Remove YouTube cron jobs")
    p_sched.add_argument("--list", action="store_true", help="List YouTube cron jobs")

    # status
    p_status = sub.add_parser("status", help="Check pipeline status for a date")
    p_status.add_argument("--date", default="", help="Date (YYYY-MM-DD, default: today)")

    # setup-check
    sub.add_parser("setup-check", help="Check if all dependencies are installed")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmd_map = {
        "trends": cmd_trends,
        "script": cmd_script,
        "source": cmd_source,
        "edit": cmd_edit,
        "voiceover": cmd_voiceover,
        "upload": cmd_upload,
        "schedule": cmd_schedule,
        "status": cmd_status,
        "setup-check": cmd_setup_check,
    }
    return cmd_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
