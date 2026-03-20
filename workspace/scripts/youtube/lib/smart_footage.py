#!/usr/bin/env python3
"""
Smart Footage Selector — relevance scoring, auto-download, diversity checking.

Implements:
- TF-IDF relevance scoring between search query and clip metadata
- Duration weighting (prefer 8-15s clips)
- Source diversity (mix Pexels + Pixabay + CC YouTube)
- Visual diversity heuristic (vary search queries)
- Auto-download of top N clips
- Script-to-footage matching (Phase C)

Usage:
    from lib.smart_footage import SmartFootageSelector

    selector = SmartFootageSelector(
        pexels_key="...", pixabay_key="...", youtube_key="...",
    )
    results = selector.search("artificial intelligence", count=20)
    ranked = selector.rank(results, target_duration=60)
    selector.download(ranked[:8], output_dir="footage/")
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class Clip:
    source: str                    # pexels, pixabay, youtube_cc
    source_id: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    download_url: str = ""
    preview_url: str = ""
    license: str = ""
    attribution: str = ""
    search_query: str = ""
    media_type: str = "video"      # "video" or "photo"
    # Scoring
    relevance_score: float = 0.0
    duration_score: float = 0.0
    diversity_score: float = 0.0
    total_score: float = 0.0
    # Download state
    filename: str = ""
    downloaded: bool = False


# ── TF-IDF Relevance Scoring ──────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer."""
    return re.findall(r"[a-z0-9]+", text.lower())


# Common English stopwords that should get low IDF weight
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "both", "either", "neither", "each", "every", "all", "any", "few",
    "more", "most", "other", "some", "such", "no", "only", "own", "same",
    "than", "too", "very", "just", "about", "above", "below", "between",
    "this", "that", "these", "those", "it", "its", "he", "she", "they",
    "them", "his", "her", "their", "what", "which", "who", "how", "when",
    "where", "why", "up", "out", "off", "over", "under", "again", "then",
})


def _idf_weight(token: str) -> float:
    """Inverse document frequency heuristic: stopwords get low weight, rare terms get high weight."""
    if token in _STOPWORDS:
        return 0.1
    if len(token) <= 2:
        return 0.3
    if len(token) <= 4:
        return 0.7
    return 1.0


def _tf_idf_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """TF-IDF relevance score with proper IDF weighting between query and document."""
    if not query_tokens or not doc_tokens:
        return 0.0

    doc_set = set(doc_tokens)
    doc_len = len(doc_tokens)

    # IDF-weighted term frequency scoring
    total_weight = 0.0
    matched_weight = 0.0

    for qt in query_tokens:
        idf = _idf_weight(qt)
        total_weight += idf
        if qt in doc_set:
            # TF: count in doc / doc length, scaled by IDF
            tf = doc_tokens.count(qt) / doc_len
            matched_weight += tf * idf + (idf * 0.5)  # bonus for presence + weighted tf

    if matched_weight == 0.0:
        return 0.0

    # Normalized score: how much of the weighted query was matched
    return min(matched_weight / total_weight, 1.0) if total_weight > 0 else 0.0


def _duration_score(duration: float, target: float = 10.0) -> float:
    """Score clip duration: ideal is 8-15s, penalize very short or very long."""
    if duration <= 0:
        return 0.0
    if 8 <= duration <= 15:
        return 1.0
    elif 5 <= duration <= 20:
        return 0.8
    elif 3 <= duration <= 30:
        return 0.5
    elif duration < 3:
        return 0.2
    else:
        # Long clips are ok (can be trimmed) but not ideal
        return 0.4


# ── API Clients ────────────────────────────────────────────────────────────────

def _api_get(url: str, headers: dict = None) -> Optional[dict]:
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  API error {e.code}: {body[:300]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  API error: {e}", file=sys.stderr)
        return None


def search_pexels(query: str, api_key: str, count: int = 10) -> list[Clip]:
    """Search Pexels for stock footage."""
    data = _api_get(
        f"https://api.pexels.com/videos/search?query={quote_plus(query)}&per_page={min(count, 80)}&size=medium",
        headers={"Authorization": api_key},
    )
    if not data:
        return []

    clips = []
    for v in data.get("videos", []):
        # Find best quality file (prefer HD 1920+)
        hd = next(
            (f for f in v.get("video_files", [])
             if f.get("quality") == "hd" and f.get("width", 0) >= 1920),
            None,
        )
        if not hd:
            hd = next(
                (f for f in v.get("video_files", []) if f.get("quality") == "hd"),
                v.get("video_files", [{}])[0] if v.get("video_files") else None,
            )
        if not hd:
            continue

        # Extract tags from video URL or use query
        tags = [t.strip() for t in query.split() if len(t.strip()) > 2]

        clips.append(Clip(
            source="pexels",
            source_id=str(v["id"]),
            title=query,
            tags=tags,
            duration_seconds=v.get("duration", 0),
            width=v.get("width", hd.get("width", 0)),
            height=v.get("height", hd.get("height", 0)),
            download_url=hd.get("link", ""),
            preview_url=v.get("image", ""),
            license="Pexels License (free, no attribution required)",
            attribution=v.get("user", {}).get("name", ""),
            search_query=query,
        ))
    return clips


def search_pixabay(query: str, api_key: str, count: int = 10) -> list[Clip]:
    """Search Pixabay for stock footage."""
    data = _api_get(
        f"https://pixabay.com/api/videos/?key={api_key}&q={quote_plus(query)}"
        f"&per_page={min(count, 80)}&min_width=1280"
    )
    if not data:
        return []

    clips = []
    for v in data.get("hits", []):
        lg = v.get("videos", {}).get("large", {})
        if not lg.get("url"):
            continue

        tags = [t.strip() for t in v.get("tags", "").split(",") if t.strip()]

        clips.append(Clip(
            source="pixabay",
            source_id=str(v["id"]),
            title=v.get("tags", query),
            tags=tags,
            duration_seconds=v.get("duration", 0),
            width=lg.get("width", 0),
            height=lg.get("height", 0),
            download_url=lg["url"],
            preview_url=f"https://i.vimeocdn.com/video/{v['picture_id']}_640x360.jpg" if v.get("picture_id") else "",
            license="Pixabay License (free, no attribution required)",
            attribution=v.get("user", ""),
            search_query=query,
        ))
    return clips


def search_pexels_photos(query: str, api_key: str, count: int = 5) -> list[Clip]:
    """Search Pexels for high-res photos (for Ken Burns effect)."""
    data = _api_get(
        f"https://api.pexels.com/v1/search?query={quote_plus(query)}&per_page={min(count, 80)}&size=large",
        headers={"Authorization": api_key},
    )
    if not data:
        return []

    clips = []
    for p in data.get("photos", []):
        src = p.get("src", {})
        # Use 'large2x' (1920px wide) or 'original'
        url = src.get("large2x") or src.get("original") or src.get("large", "")
        if not url:
            continue

        tags = [t.strip() for t in query.split() if len(t.strip()) > 2]
        clips.append(Clip(
            source="pexels",
            source_id=f"photo_{p['id']}",
            title=p.get("alt", query),
            tags=tags,
            duration_seconds=5.0,  # default Ken Burns duration for photos
            width=p.get("width", 0),
            height=p.get("height", 0),
            download_url=url,
            preview_url=src.get("medium", ""),
            license="Pexels License (free, no attribution required)",
            attribution=p.get("photographer", ""),
            search_query=query,
            media_type="photo",
        ))
    return clips


def search_pixabay_photos(query: str, api_key: str, count: int = 5) -> list[Clip]:
    """Search Pixabay for high-res photos (for Ken Burns effect)."""
    data = _api_get(
        f"https://pixabay.com/api/?key={api_key}&q={quote_plus(query)}"
        f"&per_page={min(count, 80)}&min_width=1920&image_type=photo&safesearch=true"
    )
    if not data:
        return []

    clips = []
    for p in data.get("hits", []):
        url = p.get("largeImageURL", "")
        if not url:
            continue

        tags = [t.strip() for t in p.get("tags", "").split(",") if t.strip()]
        clips.append(Clip(
            source="pixabay",
            source_id=f"photo_{p['id']}",
            title=p.get("tags", query),
            tags=tags,
            duration_seconds=5.0,  # default Ken Burns duration for photos
            width=p.get("imageWidth", 0),
            height=p.get("imageHeight", 0),
            download_url=url,
            preview_url=p.get("webformatURL", ""),
            license="Pixabay License (free, no attribution required)",
            attribution=p.get("user", ""),
            search_query=query,
            media_type="photo",
        ))
    return clips


def search_youtube_cc(query: str, api_key: str, count: int = 10) -> list[Clip]:
    """Search YouTube for Creative Commons licensed videos."""
    data = _api_get(
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&q={quote_plus(query)}&type=video"
        f"&videoLicense=creativeCommon&maxResults={count}&key={api_key}"
    )
    if not data:
        return []

    clips = []
    for item in data.get("items", []):
        s = item.get("snippet", {})
        vid = item.get("id", {}).get("videoId", "")
        if not vid:
            continue

        tags = _tokenize(s.get("title", "") + " " + s.get("description", "")[:200])

        clips.append(Clip(
            source="youtube_cc",
            source_id=vid,
            title=s.get("title", ""),
            tags=tags[:15],
            download_url=f"https://youtube.com/watch?v={vid}",
            license="Creative Commons BY",
            attribution=s.get("channelTitle", ""),
            search_query=query,
        ))
    return clips


# ── Smart Footage Selector ─────────────────────────────────────────────────────

class SmartFootageSelector:
    def __init__(
        self,
        pexels_key: str = "",
        pixabay_key: str = "",
        youtube_key: str = "",
    ):
        self.pexels_key = pexels_key or os.environ.get("PEXELS_API_KEY", "")
        self.pixabay_key = pixabay_key or os.environ.get("PIXABAY_API_KEY", "")
        self.youtube_key = youtube_key or os.environ.get("YOUTUBE_API_KEY", "")

    def generate_search_queries(self, topic: str, script_sections: list[str] = None) -> list[str]:
        """Generate diverse search queries from a topic and optional script sections."""
        queries = [topic]

        # Split topic into sub-queries
        words = topic.split()
        if len(words) >= 3:
            queries.append(" ".join(words[:2]))
            queries.append(" ".join(words[-2:]))

        # Add common b-roll queries
        broll_suffixes = ["aerial", "closeup", "timelapse", "slow motion", "background"]
        queries.append(f"{topic} {broll_suffixes[0]}")

        # From script sections
        if script_sections:
            for section in script_sections[:5]:
                # Extract key visual phrases
                visual_words = re.findall(r"VISUAL:\s*(.+?)(?:\n|$)", section, re.IGNORECASE)
                for vw in visual_words:
                    clean = re.sub(r"[^a-zA-Z0-9 ]", "", vw).strip()
                    if clean and clean not in queries:
                        queries.append(clean)

        return list(dict.fromkeys(queries))  # dedupe, preserve order

    def search(
        self,
        topic: str,
        count_per_source: int = 10,
        script_sections: list[str] = None,
    ) -> list[Clip]:
        """Search all sources with diverse queries."""
        queries = self.generate_search_queries(topic, script_sections)
        all_clips: list[Clip] = []
        seen_ids: set[str] = set()

        for query in queries:
            # Pexels videos
            if self.pexels_key:
                print(f"  Pexels: '{query}'")
                for clip in search_pexels(query, self.pexels_key, count_per_source):
                    uid = f"pexels_{clip.source_id}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_clips.append(clip)

            # Pixabay videos
            if self.pixabay_key:
                print(f"  Pixabay: '{query}'")
                for clip in search_pixabay(query, self.pixabay_key, count_per_source):
                    uid = f"pixabay_{clip.source_id}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_clips.append(clip)

            # Pexels photos (first 2 queries — variety without flooding)
            if self.pexels_key and query in queries[:2]:
                print(f"  Pexels photos: '{query}'")
                for clip in search_pexels_photos(query, self.pexels_key, count=3):
                    uid = f"pexels_{clip.source_id}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_clips.append(clip)

            # Pixabay photos (first 2 queries)
            if self.pixabay_key and query in queries[:2]:
                print(f"  Pixabay photos: '{query}'")
                for clip in search_pixabay_photos(query, self.pixabay_key, count=3):
                    uid = f"pixabay_{clip.source_id}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_clips.append(clip)

            # YouTube CC (only first query to avoid rate limits)
            if self.youtube_key and query == queries[0]:
                print(f"  YouTube CC: '{query}'")
                for clip in search_youtube_cc(query, self.youtube_key, count_per_source):
                    uid = f"ytcc_{clip.source_id}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_clips.append(clip)

        print(f"\n  Total clips found: {len(all_clips)}")
        return all_clips

    def rank(
        self,
        clips: list[Clip],
        topic: str = "",
        target_duration: int = 60,
        prefer_sources: list[str] = None,
    ) -> list[Clip]:
        """Rank clips by relevance, duration, and diversity. Returns sorted list."""
        if not clips:
            return []

        query_tokens = _tokenize(topic) if topic else []

        # Score each clip
        for clip in clips:
            # 1. Relevance (0-1): how well clip metadata matches topic
            doc_tokens = _tokenize(
                " ".join(clip.tags) + " " + clip.title + " " + clip.search_query
            )
            clip.relevance_score = _tf_idf_score(query_tokens, doc_tokens) if query_tokens else 0.5

            # 2. Duration (0-1): prefer 8-15s clips
            clip.duration_score = _duration_score(clip.duration_seconds)

            # 3. Resolution bonus
            res_bonus = 0.1 if clip.width >= 1920 else 0.0

            # 4. Source preference bonus
            source_bonus = 0.0
            if prefer_sources and clip.source in prefer_sources:
                source_bonus = 0.1

            # Combined score
            clip.total_score = (
                clip.relevance_score * 0.45 +
                clip.duration_score * 0.30 +
                res_bonus +
                source_bonus +
                0.05  # base score
            )

        # Sort by total score descending
        clips.sort(key=lambda c: c.total_score, reverse=True)

        # Diversity pass: penalize consecutive clips from same source/query
        diversified = self._diversify(clips)

        return diversified

    def _diversify(self, sorted_clips: list[Clip]) -> list[Clip]:
        """Re-order to ensure diversity: no 3+ consecutive from same source or query."""
        result = []
        remaining = list(sorted_clips)

        while remaining:
            placed = False
            for i, clip in enumerate(remaining):
                # Check last 2 in result
                if len(result) >= 2:
                    last_sources = [result[-1].source, result[-2].source]
                    last_queries = [result[-1].search_query, result[-2].search_query]
                    if (clip.source in last_sources and last_sources[0] == last_sources[1] == clip.source):
                        continue  # skip, would be 3 in a row from same source
                    if (clip.search_query in last_queries and last_queries[0] == last_queries[1] == clip.search_query):
                        continue
                result.append(remaining.pop(i))
                placed = True
                break
            if not placed:
                # Can't avoid repetition, just take the next best
                result.append(remaining.pop(0))

        return result

    def select_for_duration(
        self,
        ranked_clips: list[Clip],
        target_duration: int = 60,
        multiplier: float = 2.5,
    ) -> list[Clip]:
        """Select clips to reach target_duration * multiplier total footage."""
        target_total = target_duration * multiplier
        selected = []
        total = 0.0

        for clip in ranked_clips:
            if total >= target_total:
                break
            # Skip clips with unknown duration (YouTube CC)
            if clip.duration_seconds <= 0:
                selected.append(clip)  # include anyway, duration unknown
                continue
            selected.append(clip)
            total += clip.duration_seconds

        return selected

    def download(
        self,
        clips: list[Clip],
        output_dir: str,
        max_parallel: int = 3,
    ) -> list[Clip]:
        """Download selected clips to output directory."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        downloaded = []
        for i, clip in enumerate(clips):
            ext = ".jpg" if clip.media_type == "photo" else ".mp4"
            filename = f"{clip.source}_{clip.source_id}_{i:03d}{ext}"
            filepath = out_path / filename

            if filepath.exists():
                print(f"  [skip] {filename} (exists)")
                clip.filename = filename
                clip.downloaded = True
                downloaded.append(clip)
                continue

            if clip.source == "youtube_cc":
                # Use yt-dlp for YouTube
                from shutil import which
                if not which("yt-dlp"):
                    print(f"  [skip] {clip.title[:50]} — yt-dlp not installed")
                    continue
                print(f"  [yt-dlp] {clip.title[:60]}...")
                result = subprocess.run(
                    [
                        "yt-dlp", "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                        "--merge-output-format", "mp4",
                        "-o", str(filepath),
                        clip.download_url,
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    clip.filename = filename
                    clip.downloaded = True
                    downloaded.append(clip)
                else:
                    print(f"  [fail] yt-dlp error: {result.stderr[:200]}")
            else:
                # Direct download for Pexels/Pixabay with resume support
                print(f"  [curl] {clip.source}_{clip.source_id} ({clip.duration_seconds}s)...")
                # Use -C - for resume on partial downloads
                partial = filepath.with_suffix(".mp4.part")
                dl_target = partial if not filepath.exists() else filepath
                result = subprocess.run(
                    ["curl", "-sL", "-C", "-", "-o", str(dl_target), clip.download_url],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0 and dl_target.exists() and dl_target.stat().st_size > 1000:
                    if dl_target == partial:
                        partial.rename(filepath)
                    clip.filename = filename
                    clip.downloaded = True
                    downloaded.append(clip)
                elif result.returncode == 33:
                    # curl error 33 = range error, file already complete
                    if dl_target.exists() and dl_target.stat().st_size > 1000:
                        if dl_target == partial:
                            partial.rename(filepath)
                        clip.filename = filename
                        clip.downloaded = True
                        downloaded.append(clip)
                else:
                    print(f"  [fail] Download failed for {clip.source}_{clip.source_id}")
                    partial.unlink(missing_ok=True)
                    filepath.unlink(missing_ok=True)

        print(f"\n  Downloaded: {len(downloaded)}/{len(clips)} clips")
        return downloaded

    def save_manifest(self, clips: list[Clip], output_path: str, topic: str = ""):
        """Save footage manifest JSON."""
        manifest = {
            "topic": topic,
            "total_clips": len(clips),
            "total_duration_seconds": sum(c.duration_seconds for c in clips if c.duration_seconds > 0),
            "clips": [
                {
                    "filename": c.filename,
                    "source": c.source,
                    "source_id": c.source_id,
                    "title": c.title,
                    "duration_seconds": c.duration_seconds,
                    "resolution": f"{c.width}x{c.height}" if c.width else "unknown",
                    "license": c.license,
                    "attribution": c.attribution,
                    "search_query": c.search_query,
                    "relevance_score": round(c.relevance_score, 3),
                    "total_score": round(c.total_score, 3),
                    "downloaded": c.downloaded,
                }
                for c in clips
            ],
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  Manifest saved: {output_path}")


# ── Script-to-Footage Matching (Phase C) ───────────────────────────────────────

def extract_visual_cues_from_script(script_path: str) -> list[dict]:
    """
    Parse a script file and extract visual cues for footage matching.
    Returns list of {timestamp, visual, narration, search_queries}.
    """
    if not Path(script_path).exists():
        return []

    with open(script_path) as f:
        content = f.read()

    cues = []
    # Parse [TIMESTAMP] VISUAL: ... NARRATION: ... blocks
    blocks = re.split(r"\[(\d+[:\-]\d+(?:[:\-]\d+)?(?:s)?)\]", content)

    for i in range(1, len(blocks), 2):
        timestamp = blocks[i]
        block_text = blocks[i + 1] if i + 1 < len(blocks) else ""

        visual = ""
        narration = ""

        visual_match = re.search(r"VISUAL:\s*(.+?)(?:\n|NARRATION|TEXT|SFX|$)", block_text, re.IGNORECASE | re.DOTALL)
        if visual_match:
            visual = visual_match.group(1).strip()

        narr_match = re.search(r"NARRATION:\s*[\"']?(.+?)[\"']?\s*(?:\n|TEXT|SFX|$)", block_text, re.IGNORECASE | re.DOTALL)
        if narr_match:
            narration = narr_match.group(1).strip()

        # Generate search queries from visual description
        search_queries = []
        if visual:
            # Clean and use as query
            clean_visual = re.sub(r"[^a-zA-Z0-9 ]", "", visual).strip()
            if clean_visual:
                search_queries.append(clean_visual)
            # Extract key nouns/phrases (simple approach)
            words = clean_visual.split()
            if len(words) > 3:
                search_queries.append(" ".join(words[:3]))
                search_queries.append(" ".join(words[-3:]))

        if narration and not search_queries:
            # Fallback: use narration keywords
            clean_narr = re.sub(r"[^a-zA-Z0-9 ]", "", narration).strip()
            if clean_narr:
                search_queries.append(" ".join(clean_narr.split()[:4]))

        if search_queries:
            cues.append({
                "timestamp": timestamp,
                "visual": visual,
                "narration": narration,
                "search_queries": search_queries,
            })

    return cues


def match_footage_to_script(
    script_path: str,
    selector: SmartFootageSelector,
    count_per_cue: int = 5,
) -> list[dict]:
    """
    Match footage to each visual cue in the script.
    Returns list of {timestamp, visual, clips: [Clip]}.
    """
    cues = extract_visual_cues_from_script(script_path)
    if not cues:
        print("No visual cues found in script.")
        return []

    print(f"Found {len(cues)} visual cues in script")
    results = []

    for cue in cues:
        print(f"\n  [{cue['timestamp']}] {cue['visual'][:60]}...")
        all_clips = []
        for query in cue["search_queries"][:2]:  # limit queries per cue
            clips = selector.search(query, count_per_source=count_per_cue)
            all_clips.extend(clips)

        # Rank by relevance to the visual cue
        ranked = selector.rank(all_clips, topic=cue["visual"])[:3]

        results.append({
            "timestamp": cue["timestamp"],
            "visual": cue["visual"],
            "narration": cue["narration"],
            "clips": ranked,
        })

    return results


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart Footage Selector")
    sub = parser.add_subparsers(dest="command")

    # search + rank
    p_search = sub.add_parser("search", help="Search and rank footage")
    p_search.add_argument("topic", help="Topic to search for")
    p_search.add_argument("--count", type=int, default=10, help="Results per source")
    p_search.add_argument("--target-duration", type=int, default=60, help="Target video duration")
    p_search.add_argument("--download", action="store_true", help="Auto-download top clips")
    p_search.add_argument("--output-dir", default="footage", help="Download directory")
    p_search.add_argument("--manifest", default="footage_manifest.json", help="Manifest output path")

    # match to script
    p_match = sub.add_parser("match", help="Match footage to script visual cues")
    p_match.add_argument("script", help="Path to script.md")
    p_match.add_argument("--count", type=int, default=5, help="Clips per cue")

    args = parser.parse_args()

    if args.command == "search":
        selector = SmartFootageSelector()
        print(f"=== Searching for: '{args.topic}' ===\n")
        clips = selector.search(args.topic, count_per_source=args.count)
        ranked = selector.rank(clips, topic=args.topic, target_duration=args.target_duration)
        selected = selector.select_for_duration(ranked, target_duration=args.target_duration)

        print(f"\n=== Top {len(selected)} clips (target: {args.target_duration}s × 2.5 = {args.target_duration * 2.5}s) ===\n")
        for i, c in enumerate(selected):
            print(f"  {i+1}. [{c.total_score:.2f}] {c.source}/{c.source_id} | {c.duration_seconds}s | {c.title[:50]}")
            print(f"     Relevance: {c.relevance_score:.2f} | Duration: {c.duration_score:.2f} | Query: {c.search_query}")

        if args.download:
            print(f"\n=== Downloading to {args.output_dir}/ ===\n")
            downloaded = selector.download(selected, args.output_dir)
            selector.save_manifest(downloaded, args.manifest, topic=args.topic)
        else:
            selector.save_manifest(selected, args.manifest, topic=args.topic)

    elif args.command == "match":
        selector = SmartFootageSelector()
        results = match_footage_to_script(args.script, selector, count_per_cue=args.count)
        for r in results:
            print(f"\n  [{r['timestamp']}] {r['visual'][:60]}")
            for c in r["clips"]:
                print(f"    → [{c.total_score:.2f}] {c.source}/{c.source_id} | {c.duration_seconds}s")
