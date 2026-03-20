# YouTube Creator — Agent Knowledge

This directory stores persistent knowledge for the YouTube Creator agent.

## Structure

- `sources/` — Raw research, scraped docs, niche analysis
- `references/` — Stable files: intro.mp4, outro.mp4, client_secret.json, youtube_tokens.json
- `notes/` — Short operator notes (this file, niche preferences, style guides)

## Setup Checklist

1. Add API keys in Asta Settings > Keys:
   - `youtube_api_key` — YouTube Data API v3
   - `pexels_api_key` — Pexels stock footage
   - `pixabay_api_key` — Pixabay stock footage

2. Install required tools:
   - `brew install ffmpeg` (required for editing)
   - `pip install openai-whisper` (optional, for captions)
   - `brew install yt-dlp` (optional, for CC YouTube downloads)

3. Place intro/outro in `references/`:
   - `references/intro.mp4`
   - `references/outro.mp4`

4. For YouTube uploads, complete OAuth setup:
   - Save `client_secret.json` to `references/`
   - Run the OAuth flow from the youtube-upload skill
   - Tokens are saved to `references/youtube_tokens.json`

## Your Niche

(Add your niche, target audience, and content style here so the agent remembers)
