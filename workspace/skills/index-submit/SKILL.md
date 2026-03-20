---
name: index-submit
description: Submit URLs to Google Indexing API for indexing. Uses service account authentication. Respects 200/day rate limit.
metadata: {"clawdbot":{"emoji":"\U0001F4E4","requires":{"bins":["python3"]}}}
---

# URL Submission

Submit URLs to Google's Indexing API to request crawling and indexing.

## Usage

```bash
python3 workspace/scripts/indexing/pipeline.py submit --domain <DOMAIN> [--limit 200] [--force]
```

**Examples:**
```bash
# Submit only new/updated URLs from the latest diff
python3 workspace/scripts/indexing/pipeline.py submit --domain example.com

# Submit with a lower limit
python3 workspace/scripts/indexing/pipeline.py submit --domain example.com --limit 50

# Force-submit ALL crawled URLs (not just diff)
python3 workspace/scripts/indexing/pipeline.py submit --domain example.com --force
```

## Prerequisites

- Must run `index-crawl` first to generate crawl/diff data
- Google service account must be set (Asta Settings > Google tab)
- Service account must be added as Owner in Google Search Console
- `google-auth` Python package must be installed

## What It Does

1. Loads the diff.json (or crawl.json if --force) from today's crawl
2. Authenticates with Google via service account
3. POSTs each URL to `https://indexing.googleapis.com/v3/urlNotifications:publish`
4. Respects the 200/day rate limit (tracks submissions in submissions.json)
5. Saves results to `workspace/indexing/<domain>/YYYY-MM-DD/submit_results.json`

## Rate Limits

- Default Google quota: **200 URL notifications per day** per property
- The script tracks daily submissions and stops at the limit
- Use `--limit` to set a lower cap per run

## Notes

- Submitting a URL does NOT guarantee indexing — it requests a crawl
- Google still decides whether to index based on content quality
- Re-submitting already-indexed URLs is pointless — avoid with diff mode
