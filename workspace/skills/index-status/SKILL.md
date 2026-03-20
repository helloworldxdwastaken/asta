---
name: index-status
description: Check indexing status of submitted URLs using Google URL Inspection API. Also generates summary reports.
metadata: {"clawdbot":{"emoji":"\U0001F4CA","requires":{"bins":["python3"]}}}
---

# Indexing Status & Reports

Check whether submitted URLs have been indexed by Google, and generate summary reports.

## Usage

### Check status
```bash
python3 workspace/scripts/indexing/pipeline.py status --domain <DOMAIN>
```

### Generate report
```bash
python3 workspace/scripts/indexing/pipeline.py report --domain <DOMAIN>
```

## What `status` Does

1. Loads the submission history from `workspace/indexing/<domain>/submissions.json`
2. Takes the last 50 unique successfully-submitted URLs
3. Queries the Google URL Inspection API for each
4. Reports coverage state: indexed, crawled-not-indexed, not found, etc.
5. Saves results to `workspace/indexing/<domain>/YYYY-MM-DD/status.json`

## What `report` Does

1. Aggregates all data from today's crawl, diff, submissions, and status checks
2. Generates a markdown report with:
   - Sitemap stats (total URLs, new, updated)
   - Submission stats (submitted, successful, failed)
   - All-time submission history
   - Indexing status breakdown
   - Lists of new/updated URLs and any failures
3. Saves to `workspace/indexing/<domain>/YYYY-MM-DD/report.md`

## Prerequisites

- Google service account must be set (Asta Settings > Google tab)
- Service account needs `webmasters.readonly` scope access
- Previous submissions must exist (run `index-submit` first)

## Setup Check

Run this to verify everything is configured correctly:
```bash
python3 workspace/scripts/indexing/pipeline.py setup-check
```
