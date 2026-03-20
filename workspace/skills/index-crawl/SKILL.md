---
name: index-crawl
description: Crawl a website's sitemap.xml to discover all URLs. Supports sitemap index files, nested sitemaps, and lastmod filtering. Diffs against previous crawl to find new/updated pages.
metadata: {"clawdbot":{"emoji":"\U0001F578","requires":{"bins":["python3"]}}}
---

# Sitemap Crawler

Crawl a website's sitemap to discover all indexable URLs.

## Usage

```bash
python3 workspace/scripts/indexing/pipeline.py crawl --url <SITEMAP_URL>
```

**Examples:**
```bash
python3 workspace/scripts/indexing/pipeline.py crawl --url https://example.com/sitemap.xml
python3 workspace/scripts/indexing/pipeline.py crawl --url https://example.com/sitemap_index.xml
```

## What It Does

1. Fetches the sitemap XML from the given URL
2. If it's a sitemap index, recursively fetches all child sitemaps
3. Extracts every `<loc>` URL and its `<lastmod>` timestamp
4. Compares against the previous crawl (if any) to produce a diff
5. Saves results to `workspace/indexing/<domain>/YYYY-MM-DD/`

## Output Files

- `crawl.json` — all URLs found in the sitemap
- `diff.json` — only new or updated URLs (compared to last crawl)

## Notes

- No API key needed for this step
- Works with any standard XML sitemap or sitemap index
- The diff is what gets submitted in the next step (index-submit)
