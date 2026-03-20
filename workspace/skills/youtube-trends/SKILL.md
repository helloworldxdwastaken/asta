---
name: youtube-trends
description: Discover trending YouTube topics using YouTube Data API v3 and Google Trends. Use when the user wants to find what's trending, discover video ideas, or research popular topics for YouTube content.
metadata: {"clawdbot":{"emoji":"📈","requires":{"bins":["curl","python3"]}}}
---

# YouTube Trends Discovery

Find today's top trending topics for YouTube content creation using the YouTube Data API v3 and Google Trends.

## API Keys

- `$YOUTUBE_API_KEY` — required, stored in Asta DB, injected automatically

If the key is missing, tell the user: "Add your YouTube Data API v3 key in Settings > Keys as `youtube_api_key`."

## Methods

### 1. YouTube Trending Videos

Fetch trending videos for a region and category:

```bash
# Get trending videos (US, default category)
curl -s "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&chart=mostPopular&regionCode=US&maxResults=20&key=$YOUTUBE_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('items', []):
    s = v['snippet']
    st = v.get('statistics', {})
    print(f\"- {s['title']}\")
    print(f\"  Channel: {s['channelTitle']} | Views: {st.get('viewCount','?')} | Published: {s['publishedAt'][:10]}\")
    print(f\"  Tags: {', '.join(s.get('tags',[])[0:5])}\")
    print()
"
```

### 2. YouTube Search (niche-specific)

Search for recent popular videos in a specific niche:

```bash
# Search for trending videos in a niche (last 7 days)
NICHE="your niche here"
AFTER=$(python3 -c "from datetime import datetime,timedelta; print((datetime.utcnow()-timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
curl -s "https://www.googleapis.com/youtube/v3/search?part=snippet&q=${NICHE}&type=video&order=viewCount&publishedAfter=${AFTER}&maxResults=15&key=$YOUTUBE_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
ids = ','.join(i['id']['videoId'] for i in data.get('items',[]) if 'videoId' in i.get('id',{}))
print(ids)
" > /tmp/yt_video_ids.txt

# Get detailed stats for those videos
IDS=$(cat /tmp/yt_video_ids.txt)
curl -s "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=${IDS}&key=$YOUTUBE_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('items', []):
    s = v['snippet']
    st = v.get('statistics', {})
    views = int(st.get('viewCount', 0))
    print(f\"- [{views:,} views] {s['title']}\")
    print(f\"  Channel: {s['channelTitle']} | Likes: {st.get('likeCount','?')}\")
    print(f\"  Tags: {', '.join(s.get('tags',[])[0:8])}\")
    print()
"
```

### 3. Google Trends (no API key needed)

Scrape Google Trends daily trending searches:

```bash
# Get today's trending searches from Google Trends (US)
curl -s "https://trends.google.com/trending/rss?geo=US" \
  | python3 -c "
import sys, re
content = sys.stdin.read()
titles = re.findall(r'<title>(.+?)</title>', content)
traffic = re.findall(r'<ht:approx_traffic>(.+?)</ht:approx_traffic>', content)
for i, title in enumerate(titles[1:20]):  # skip RSS feed title
    t = traffic[i] if i < len(traffic) else '?'
    print(f'{i+1}. {title} ({t} searches)')
"
```

### 4. Category-specific trending

YouTube video category IDs:
- 1: Film & Animation
- 2: Autos & Vehicles
- 10: Music
- 15: Pets & Animals
- 17: Sports
- 20: Gaming
- 22: People & Blogs
- 23: Comedy
- 24: Entertainment
- 25: News & Politics
- 26: Howto & Style
- 27: Education
- 28: Science & Technology

```bash
# Get trending in a specific category
CATEGORY_ID=28
curl -s "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&chart=mostPopular&regionCode=US&videoCategoryId=${CATEGORY_ID}&maxResults=15&key=$YOUTUBE_API_KEY" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('items', []):
    s = v['snippet']
    st = v.get('statistics', {})
    print(f\"- {s['title']}\")
    print(f\"  Views: {st.get('viewCount','?')} | Channel: {s['channelTitle']}\")
"
```

## Workflow

1. Ask the user for their niche/category (or use previously known niche from agent knowledge).
2. Run both YouTube trending + Google Trends in parallel.
3. Cross-reference: find topics that appear in both YouTube trending AND Google Trends.
4. Rank by: relevance to user's niche × search volume × competition gap.
5. Present top 5 topics with:
   - Topic name
   - Why it's trending (news hook, seasonal, viral moment)
   - Estimated search volume
   - Competition level (how many videos already exist)
   - Suggested angle for the user's channel

## Save Output

Save trend analysis to:
```
workspace/youtube/YYYY-MM-DD/trends.json
```

Format:
```json
{
  "date": "2026-03-15",
  "niche": "user's niche",
  "topics": [
    {
      "rank": 1,
      "topic": "Topic Name",
      "source": "youtube_trending|google_trends|both",
      "search_volume": "500K+",
      "competition": "low|medium|high",
      "suggested_angle": "..."
    }
  ]
}
```
