---
name: youtube-script
description: Write YouTube video scripts, generate viral titles, SEO descriptions, tags, and thumbnail concepts. Use when the user needs a video script, title ideas, YouTube SEO metadata, or content planning for their YouTube channel.
metadata: {"clawdbot":{"emoji":"✍️","requires":{"bins":["python3"]}}}
---

# YouTube Script & Metadata Writer

Write engaging video scripts and YouTube-optimized metadata (titles, descriptions, tags, thumbnail concepts).

## Workflow

### 1. Gather Context

Before writing, collect:
- **Topic** (from trends step or user input)
- **Target duration** (default: 60 seconds for Shorts, 8-12 minutes for long-form)
- **Tone** (educational, entertaining, dramatic, conversational, etc.)
- **Niche/audience** (from agent knowledge or ask the user)
- **Available footage** (from footage_manifest.json if sourcing was done)

### 2. Write the Script

Structure for **short-form** (≤60s):
```
HOOK (0-3s): Attention-grabbing opening line or question
SETUP (3-10s): Context — what this video is about
BODY (10-45s): Main content — 2-3 key points with visuals
PAYOFF (45-55s): Climax or surprising reveal
CTA (55-60s): Subscribe / like / comment prompt
```

Structure for **long-form** (8-12 min):
```
COLD OPEN (0-30s): Start with the most interesting moment
INTRO (30s-1m): Context + what viewers will learn
SECTION 1 (1-3m): First main point
SECTION 2 (3-5m): Second main point
SECTION 3 (5-7m): Third main point
CLIMAX (7-9m): Bring it all together / reveal
OUTRO (9-10m): Summary + CTA
END SCREEN (last 20s): Subscribe + suggested videos
```

Script format:
```
[TIMESTAMP] VISUAL: Description of what's on screen
NARRATION: "What the voiceover says"
TEXT ON SCREEN: Any overlay text
SFX: Sound effects or music cues
```

### 3. Generate Titles (3 options)

Create 3 title options using these viral patterns:
- **Curiosity gap**: "I Tried X for 30 Days — Here's What Happened"
- **Listicle**: "7 Things About X That Will Blow Your Mind"
- **How-to**: "How to X (Step-by-Step Guide)"
- **Shock/contrast**: "Why X Is Actually Y"
- **Challenge**: "Can X Really Do Y?"

Rules:
- Under 60 characters (ideal for CTR)
- Include the main keyword naturally
- Capitalize key words (Title Case)
- Use numbers when possible
- Include emotional trigger words (amazing, shocking, simple, free, secret)

### 4. Write SEO Description

Structure:
```
[First 2 lines — most important, shown before "Show more"]
Hook line that includes the main keyword.
Brief summary of what the video covers.

[Full description]
Detailed overview of the video content (150-300 words).
Include target keywords naturally 3-5 times.
Include relevant links and resources.

TIMESTAMPS:
0:00 - Introduction
0:30 - Section 1
...

#hashtag1 #hashtag2 #hashtag3

LINKS:
[Relevant links]

CREDITS:
Footage: Pexels / Pixabay (attribution if needed)
Music: [source]
```

### 5. Generate Tags

```python
# Generate tag list
tags = [
    "main keyword",
    "main keyword variation 1",
    "main keyword variation 2",
    "niche keyword 1",
    "niche keyword 2",
    "broader topic 1",
    "broader topic 2",
    "trending related term",
    # 15-30 tags total, most specific first
]
```

Rules:
- 15-30 tags per video
- First 5 tags = most important keywords
- Mix of specific and broad terms
- Include common misspellings of key terms
- Include competitor/related channel topics
- Total tag character limit: 500 characters

### 6. Thumbnail Concept

Describe a thumbnail concept:
- Background image/scene
- Text overlay (max 4-5 words, large font)
- Colors (high contrast, bright)
- Face/expression (if applicable)
- Layout (rule of thirds)

## Voice/Tone Guidelines

Match the user's preferred tone. Default to:
- **Conversational** but authoritative
- **Short sentences** — easy to read aloud
- **Active voice** — "This changes everything" not "Everything is changed by this"
- **Questions** — engage the viewer: "But here's the thing..."
- **Transitions** — "Now here's where it gets interesting..."

## Save Output

Save script and metadata to:
```
workspace/youtube/YYYY-MM-DD/script.md    — the full script
workspace/youtube/YYYY-MM-DD/metadata.json — structured metadata
```

metadata.json format:
```json
{
  "topic": "...",
  "duration_target_seconds": 60,
  "titles": [
    "Title Option 1",
    "Title Option 2",
    "Title Option 3"
  ],
  "description": "Full YouTube description...",
  "tags": ["tag1", "tag2", "..."],
  "thumbnail_concept": "...",
  "category_id": 28,
  "default_language": "en",
  "privacy": "private"
}
```

## Rules

- Scripts must match available footage when footage has already been sourced.
- Never promise specific view counts or performance.
- Always set initial privacy to "private" — user publishes manually or via approval.
- Include attribution for stock footage in the description.
