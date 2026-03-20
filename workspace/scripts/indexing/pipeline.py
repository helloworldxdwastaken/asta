#!/usr/bin/env python3
"""
Index Manager Pipeline — crawl sitemaps, submit URLs to Google Indexing API,
check indexing status, and generate reports.

Usage:
    python3 workspace/scripts/indexing/pipeline.py setup-check
    python3 workspace/scripts/indexing/pipeline.py crawl --url https://example.com/sitemap.xml
    python3 workspace/scripts/indexing/pipeline.py submit --domain example.com [--limit 200] [--force]
    python3 workspace/scripts/indexing/pipeline.py status --domain example.com
    python3 workspace/scripts/indexing/pipeline.py report --domain example.com

API credentials are read from environment (injected by Asta exec_tool):
    $GOOGLE_APPLICATION_CREDENTIALS  — path to Google service account JSON file
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# ── Constants ────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parents[2]  # workspace/
INDEX_DIR = WORKSPACE / "indexing"
INDEXING_API_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"
INSPECTION_API_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
SCOPES = ["https://www.googleapis.com/auth/indexing"]
INSPECTION_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DAILY_LIMIT = 200
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ── Auth helpers ─────────────────────────────────────────────────────

def _get_credentials(scopes: list[str]):
    """Load Google service account credentials."""
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not sa_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set.")
        print("Paste your service account JSON in Asta Settings > Google tab.")
        sys.exit(1)

    sa_path = os.path.expanduser(sa_path)
    if not os.path.isfile(sa_path):
        print(f"ERROR: Service account file not found: {sa_path}")
        sys.exit(1)

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as AuthRequest

        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=scopes
        )
        creds.refresh(AuthRequest())
        return creds
    except ImportError:
        print("ERROR: google-auth package not installed.")
        print("Install it:  pip3 install google-auth")
        sys.exit(1)


def _authed_request(url: str, body: dict, scopes: list[str]) -> dict:
    """Make an authenticated POST request to a Google API."""
    creds = _get_credentials(scopes)
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        return {"error": {"code": e.code, "message": err_body}}


# ── Domain / path helpers ────────────────────────────────────────────

def _domain_from_url(url: str) -> str:
    """Extract domain from URL for directory naming."""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path.split("/")[0]


def _domain_dir(domain: str) -> Path:
    d = INDEX_DIR / domain
    d.mkdir(parents=True, exist_ok=True)
    return d


def _today_dir(domain: str) -> Path:
    d = _domain_dir(domain) / TODAY
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(path: Path) -> list | dict:
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Saved: {path}")


# ── Sitemap crawling ─────────────────────────────────────────────────

def _fetch_xml(url: str) -> ET.Element | None:
    """Fetch and parse XML from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Asta-IndexManager/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return ET.fromstring(resp.read())
    except Exception as e:
        print(f"  WARNING: Failed to fetch {url}: {e}")
        return None


def _parse_sitemap(url: str) -> list[dict]:
    """
    Parse a sitemap URL. Handles sitemap index files (recursive)
    and standard sitemap files.
    Returns list of {"url": str, "lastmod": str|None}.
    """
    root = _fetch_xml(url)
    if root is None:
        return []

    # Strip namespace for easier tag matching
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    urls = []

    # Check if this is a sitemap index
    sitemaps = root.findall(f"{ns}sitemap")
    if sitemaps:
        print(f"  Sitemap index with {len(sitemaps)} child sitemaps")
        for sm in sitemaps:
            loc = sm.find(f"{ns}loc")
            if loc is not None and loc.text:
                child_url = loc.text.strip()
                print(f"  Fetching child: {child_url}")
                urls.extend(_parse_sitemap(child_url))
        return urls

    # Standard sitemap — extract <url> entries
    entries = root.findall(f"{ns}url")
    for entry in entries:
        loc = entry.find(f"{ns}loc")
        lastmod = entry.find(f"{ns}lastmod")
        if loc is not None and loc.text:
            urls.append({
                "url": loc.text.strip(),
                "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else None,
            })

    return urls


def _diff_crawls(current: list[dict], previous: list[dict]) -> list[dict]:
    """Find new or updated URLs compared to previous crawl."""
    prev_map = {u["url"]: u.get("lastmod") for u in previous}
    diff = []
    for u in current:
        url = u["url"]
        if url not in prev_map:
            diff.append({**u, "reason": "new"})
        elif u.get("lastmod") and u["lastmod"] != prev_map.get(url):
            diff.append({**u, "reason": "updated"})
    return diff


# ── Subcommands ──────────────────────────────────────────────────────

def cmd_setup_check(args):
    """Verify service account credentials and API access."""
    print("=== Index Manager Setup Check ===\n")

    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not sa_path:
        print("FAIL: GOOGLE_APPLICATION_CREDENTIALS not set.")
        print("  → Go to Asta Settings > Google tab")
        print("  → Paste your service account JSON")
        return

    sa_path = os.path.expanduser(sa_path)
    if not os.path.isfile(sa_path):
        print(f"FAIL: File not found: {sa_path}")
        return

    print(f"OK: Service account file found: {sa_path}")

    # Parse the JSON to show the service account email
    try:
        with open(sa_path) as f:
            sa_data = json.load(f)
        email = sa_data.get("client_email", "unknown")
        project = sa_data.get("project_id", "unknown")
        print(f"OK: Service account: {email}")
        print(f"OK: Project: {project}")
    except Exception as e:
        print(f"FAIL: Cannot parse JSON: {e}")
        return

    # Test google-auth import
    try:
        from google.oauth2 import service_account as _sa
        print("OK: google-auth package installed")
    except ImportError:
        print("FAIL: google-auth not installed. Run: pip3 install google-auth")
        return

    # Test authentication
    try:
        creds = _get_credentials(SCOPES)
        print(f"OK: Authentication successful (token expires: {creds.expiry})")
    except Exception as e:
        print(f"FAIL: Authentication failed: {e}")
        return

    print("\n=== Setup Complete ===")
    print(f"\nIMPORTANT: Make sure {email} is added as an OWNER")
    print("in Google Search Console for your target property.")
    print("  → https://search.google.com/search-console/users")


def cmd_crawl(args):
    """Crawl sitemap and diff against previous run."""
    url = args.url
    domain = _domain_from_url(url)
    out_dir = _today_dir(domain)

    print(f"=== Crawling sitemap: {url} ===\n")
    urls = _parse_sitemap(url)
    print(f"\nFound {len(urls)} URLs")

    if not urls:
        print("No URLs found. Check the sitemap URL.")
        return

    crawl_path = out_dir / "crawl.json"
    _save_json(crawl_path, urls)

    # Find previous crawl for diff
    domain_dir = _domain_dir(domain)
    prev_dirs = sorted(
        [d for d in domain_dir.iterdir() if d.is_dir() and d.name != TODAY],
        reverse=True,
    )
    prev_crawl = []
    for pd in prev_dirs:
        prev_file = pd / "crawl.json"
        if prev_file.exists():
            prev_crawl = _load_json(prev_file)
            print(f"Previous crawl: {prev_file} ({len(prev_crawl)} URLs)")
            break

    diff = _diff_crawls(urls, prev_crawl)
    diff_path = out_dir / "diff.json"
    _save_json(diff_path, diff)

    new_count = sum(1 for d in diff if d.get("reason") == "new")
    updated_count = sum(1 for d in diff if d.get("reason") == "updated")
    print(f"\nDiff: {len(diff)} URLs ({new_count} new, {updated_count} updated)")
    print(f"\nResults saved to: {out_dir}")


def _check_indexed(url: str, domain: str) -> bool | None:
    """Check if a URL is already indexed via URL Inspection API.

    Returns True if indexed, False if not, None if check failed.
    """
    site_url = f"sc-domain:{domain}"
    body = {"inspectionUrl": url, "siteUrl": site_url}
    try:
        resp = _authed_request(INSPECTION_API_URL, body, INSPECTION_SCOPES)
    except Exception:
        return None
    if "error" in resp:
        return None
    inspection = resp.get("inspectionResult", {})
    index_status = inspection.get("indexStatusResult", {})
    verdict = index_status.get("verdict", "").upper()
    coverage = index_status.get("coverageState", "").upper()
    # PASS = indexed, SUBMITTED_AND_INDEXED is also indexed
    if verdict == "PASS" or "INDEXED" in coverage:
        return True
    return False


def cmd_submit(args):
    """Submit URLs to Google Indexing API, skipping already-indexed URLs."""
    domain = args.domain
    limit = min(args.limit, DAILY_LIMIT)
    out_dir = _today_dir(domain)
    skip_check = args.skip_index_check

    print(f"=== Submitting URLs for {domain} (limit: {limit}) ===\n")

    # Load URLs to submit
    if args.force:
        source = out_dir / "crawl.json"
        print("Force mode: submitting ALL crawled URLs")
    else:
        source = out_dir / "diff.json"
        print("Submitting new/updated URLs from diff")

    if not source.exists():
        print(f"ERROR: {source} not found. Run 'crawl' first.")
        return

    urls = _load_json(source)
    if not urls:
        print("No URLs to submit.")
        return

    # Check daily submission count
    submissions_file = _domain_dir(domain) / "submissions.json"
    submissions = _load_json(submissions_file)
    if not isinstance(submissions, list):
        submissions = []

    today_submissions = [s for s in submissions if s.get("date") == TODAY]
    remaining = limit - len(today_submissions)
    if remaining <= 0:
        print(f"Daily limit reached ({len(today_submissions)}/{limit} submitted today).")
        return

    candidates = urls[:remaining]

    # Pre-filter: check indexing status and skip already-indexed URLs
    to_submit = []
    skipped_indexed = 0
    if skip_check:
        to_submit = candidates
        print(f"Skipping index check (--skip-index-check). {len(to_submit)} candidates.\n")
    else:
        print(f"Checking indexing status for {len(candidates)} URLs...\n")
        for entry in candidates:
            url = entry["url"] if isinstance(entry, dict) else entry
            print(f"  Checking {url} ... ", end="", flush=True)
            indexed = _check_indexed(url, domain)
            if indexed is True:
                print("ALREADY INDEXED — skipping")
                skipped_indexed += 1
            else:
                reason = "not indexed" if indexed is False else "status unknown"
                print(f"{reason} — will submit")
                to_submit.append(entry)
            time.sleep(0.3)  # Rate limit the inspection API

        if skipped_indexed:
            print(f"\nSkipped {skipped_indexed} already-indexed URLs")

    if not to_submit:
        print("\nAll URLs are already indexed. Nothing to submit.")
        return

    print(f"\nSubmitting {len(to_submit)} URLs ({len(today_submissions)} already submitted today)\n")

    results = []
    for i, entry in enumerate(to_submit, 1):
        url = entry["url"] if isinstance(entry, dict) else entry
        body = {"url": url, "type": "URL_UPDATED"}

        print(f"  [{i}/{len(to_submit)}] {url} ... ", end="", flush=True)
        resp = _authed_request(INDEXING_API_URL, body, SCOPES)

        if "error" in resp:
            status = f"error ({resp['error'].get('code', '?')})"
            print(f"FAIL: {resp['error'].get('message', '')[:100]}")
        else:
            status = "ok"
            notify_time = resp.get("urlNotificationMetadata", {}).get(
                "latestUpdate", {}
            ).get("notifyTime", "")
            print(f"OK (notified: {notify_time})")

        record = {
            "url": url,
            "date": TODAY,
            "status": status,
            "response": resp,
        }
        results.append(record)
        submissions.append(record)

        # Small delay to be respectful
        if i < len(to_submit):
            time.sleep(0.5)

    # Save results
    results_path = out_dir / "submit_results.json"
    _save_json(results_path, results)
    _save_json(submissions_file, submissions)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count
    print(f"\nDone: {ok_count} submitted, {err_count} errors, {skipped_indexed} skipped (already indexed)")
    print(f"Results: {results_path}")


def cmd_status(args):
    """Check indexing status via URL Inspection API."""
    domain = args.domain
    out_dir = _today_dir(domain)

    print(f"=== Checking indexing status for {domain} ===\n")

    # Find the most recent submission results to check
    submissions_file = _domain_dir(domain) / "submissions.json"
    if not submissions_file.exists():
        print("No submissions found. Run 'submit' first.")
        return

    submissions = _load_json(submissions_file)
    # Get unique URLs from recent submissions
    seen = set()
    urls_to_check = []
    for s in reversed(submissions):
        url = s.get("url", "")
        if url and url not in seen and s.get("status") == "ok":
            seen.add(url)
            urls_to_check.append(url)
        if len(urls_to_check) >= 50:  # Check last 50 unique submitted URLs
            break

    if not urls_to_check:
        print("No successfully submitted URLs to check.")
        return

    # Determine site URL format for GSC
    # Try both "sc-domain:" and "https://" property formats
    site_url = f"sc-domain:{domain}"
    print(f"Checking {len(urls_to_check)} URLs (property: {site_url})\n")

    results = []
    for i, url in enumerate(urls_to_check, 1):
        body = {
            "inspectionUrl": url,
            "siteUrl": site_url,
        }
        print(f"  [{i}/{len(urls_to_check)}] {url} ... ", end="", flush=True)
        resp = _authed_request(INSPECTION_API_URL, body, INSPECTION_SCOPES)

        if "error" in resp:
            coverage = "error"
            print(f"ERROR: {resp['error'].get('message', '')[:80]}")
        else:
            inspection = resp.get("inspectionResult", {})
            index_status = inspection.get("indexStatusResult", {})
            coverage = index_status.get("coverageState", "UNKNOWN")
            verdict = index_status.get("verdict", "?")
            print(f"{verdict} — {coverage}")

        results.append({
            "url": url,
            "coverage": coverage,
            "response": resp,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })

        if i < len(urls_to_check):
            time.sleep(0.5)

    status_path = out_dir / "status.json"
    _save_json(status_path, results)

    # Summary
    indexed = sum(1 for r in results if "INDEXED" in r.get("coverage", "").upper())
    not_indexed = sum(1 for r in results if "NOT_INDEXED" in r.get("coverage", "").upper() or "CRAWLED" in r.get("coverage", "").upper())
    errors = sum(1 for r in results if r.get("coverage") == "error")
    print(f"\nSummary: {indexed} indexed, {not_indexed} not yet indexed, {errors} errors")
    print(f"Results: {status_path}")


def cmd_report(args):
    """Generate a markdown summary report."""
    domain = args.domain
    out_dir = _today_dir(domain)
    domain_dir = _domain_dir(domain)

    print(f"=== Generating report for {domain} ===\n")

    # Gather data
    crawl = _load_json(out_dir / "crawl.json") if (out_dir / "crawl.json").exists() else []
    diff = _load_json(out_dir / "diff.json") if (out_dir / "diff.json").exists() else []
    results = _load_json(out_dir / "submit_results.json") if (out_dir / "submit_results.json").exists() else []
    status = _load_json(out_dir / "status.json") if (out_dir / "status.json").exists() else []
    submissions = _load_json(domain_dir / "submissions.json") if (domain_dir / "submissions.json").exists() else []

    # Build report
    lines = [
        f"# Index Manager Report — {domain}",
        f"**Date**: {TODAY}",
        "",
        "## Sitemap Crawl",
        f"- Total URLs in sitemap: **{len(crawl)}**",
        f"- New URLs (not in previous crawl): **{sum(1 for d in diff if d.get('reason') == 'new')}**",
        f"- Updated URLs (lastmod changed): **{sum(1 for d in diff if d.get('reason') == 'updated')}**",
        "",
        "## Submissions (Today)",
        f"- URLs submitted: **{len(results)}**",
        f"- Successful: **{sum(1 for r in results if r.get('status') == 'ok')}**",
        f"- Failed: **{sum(1 for r in results if r.get('status') != 'ok')}**",
        "",
        "## Submissions (All Time)",
        f"- Total submissions: **{len(submissions)}**",
        f"- Unique URLs: **{len(set(s.get('url', '') for s in submissions))}**",
        "",
    ]

    if status:
        indexed = sum(1 for s in status if "INDEXED" in s.get("coverage", "").upper())
        not_indexed = len(status) - indexed
        lines.extend([
            "## Indexing Status",
            f"- Checked: **{len(status)}** URLs",
            f"- Indexed: **{indexed}**",
            f"- Not yet indexed: **{not_indexed}**",
            "",
        ])

    if diff:
        lines.append("## New/Updated URLs")
        for d in diff[:20]:
            reason = d.get("reason", "")
            lines.append(f"- [{reason}] {d['url']}")
        if len(diff) > 20:
            lines.append(f"- ... and {len(diff) - 20} more")
        lines.append("")

    if results:
        failed = [r for r in results if r.get("status") != "ok"]
        if failed:
            lines.append("## Failed Submissions")
            for r in failed[:10]:
                err = r.get("response", {}).get("error", {}).get("message", "unknown")[:80]
                lines.append(f"- {r['url']} — {err}")
            lines.append("")

    report_text = "\n".join(lines)
    report_path = out_dir / "report.md"
    report_path.write_text(report_text)
    print(report_text)
    print(f"\nReport saved: {report_path}")


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Index Manager — Google Search Console URL indexing pipeline"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # setup-check
    sub.add_parser("setup-check", help="Verify credentials and API access")

    # crawl
    p_crawl = sub.add_parser("crawl", help="Crawl sitemap and diff against previous run")
    p_crawl.add_argument("--url", required=True, help="Sitemap URL (e.g. https://example.com/sitemap.xml)")

    # submit
    p_submit = sub.add_parser("submit", help="Submit URLs to Google Indexing API")
    p_submit.add_argument("--domain", required=True, help="Domain (e.g. example.com)")
    p_submit.add_argument("--limit", type=int, default=200, help="Max URLs to submit (default: 200)")
    p_submit.add_argument("--force", action="store_true", help="Submit all crawled URLs, not just diff")
    p_submit.add_argument("--skip-index-check", action="store_true", dest="skip_index_check", help="Skip checking if URLs are already indexed")

    # status
    p_status = sub.add_parser("status", help="Check indexing status of submitted URLs")
    p_status.add_argument("--domain", required=True, help="Domain (e.g. example.com)")

    # report
    p_report = sub.add_parser("report", help="Generate summary report")
    p_report.add_argument("--domain", required=True, help="Domain (e.g. example.com)")

    args = parser.parse_args()

    commands = {
        "setup-check": cmd_setup_check,
        "crawl": cmd_crawl,
        "submit": cmd_submit,
        "status": cmd_status,
        "report": cmd_report,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
