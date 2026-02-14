"""OpenClaw compatibility tools: web_search, web_fetch, memory_search, memory_get."""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.memories import load_user_memories
from app.search_web import search_web

DEFAULT_WEB_SEARCH_COUNT = 5
MAX_WEB_SEARCH_COUNT = 10
DEFAULT_WEB_FETCH_MAX_CHARS = 12_000
MAX_WEB_FETCH_CHARS_CAP = 60_000
DEFAULT_WEB_FETCH_TIMEOUT_SECONDS = 20

DEFAULT_MEMORY_RESULTS = 5
MAX_MEMORY_RESULTS = 20
DEFAULT_MEMORY_GET_LINES = 120
MAX_MEMORY_GET_LINES = 500
DEFAULT_MEMORY_SEARCH_MODE = "search"  # fast lexical-first; fallback to RAG only when needed

_BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "gateway.docker.internal",
}


def get_openclaw_web_memory_tools_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web and return structured results (title, url, description). "
                    "Compatible with OpenClaw-style skills."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "count": {"type": "integer", "description": "max results (1-10)"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_fetch",
                "description": (
                    "Fetch and extract readable content from a URL. "
                    "Supports extractMode=text|markdown and maxChars."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "extractMode": {"type": "string", "enum": ["markdown", "text"]},
                        "maxChars": {"type": "integer"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_search",
                "description": (
                    "Search user/workspace memories and RAG snippets. "
                    "Returns path, line range, snippet, and score."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "maxResults": {"type": "integer"},
                        "minScore": {"type": "number"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_get",
                "description": (
                    "Read a memory file snippet safely by path with optional from/lines."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "from": {"type": "integer"},
                        "lines": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
        },
    ]


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw.isdigit():
            return int(raw)
    return None


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        try:
            return float(raw)
        except Exception:
            return None
    return None


def parse_openclaw_compat_args(arguments_str: str | dict) -> dict:
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except Exception:
        data = {}
    out = dict(data)
    if "maxChars" not in out and "max_chars" in out:
        out["maxChars"] = out.get("max_chars")
    if "maxResults" not in out and "max_results" in out:
        out["maxResults"] = out.get("max_results")
    if "minScore" not in out and "min_score" in out:
        out["minScore"] = out.get("min_score")
    return out


async def run_web_search_compat(params: dict) -> str:
    query = (params.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required", "results": []}, indent=0)
    count = _to_int(params.get("count"))
    count = DEFAULT_WEB_SEARCH_COUNT if count is None else max(1, min(count, MAX_WEB_SEARCH_COUNT))
    results, err = search_web(query, max_results=count)
    mapped = [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "description": r.get("snippet") or "",
        }
        for r in (results or [])
        if isinstance(r, dict)
    ]
    payload = {
        "query": query,
        "provider": "ddgs",
        "count": len(mapped),
        "results": mapped,
    }
    if err:
        payload["error"] = err
    return json.dumps(payload, indent=0)


def _host_is_private_or_blocked(hostname: str) -> bool:
    h = (hostname or "").strip().lower().rstrip(".")
    if not h:
        return True
    if h in _BLOCKED_HOSTNAMES or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except Exception:
        pass
    try:
        infos = socket.getaddrinfo(h, None)
    except Exception:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return True
        except Exception:
            continue
    return False


def _extract_html_text(raw_html: str, *, extract_mode: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(raw_html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else None
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    body_text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    if extract_mode == "markdown":
        if title:
            return f"# {title}\n\n{body_text}".strip(), title
        return body_text, title
    return body_text, title


async def run_web_fetch_compat(params: dict) -> str:
    raw_url = (params.get("url") or "").strip()
    if not raw_url:
        return json.dumps({"error": "url is required"}, indent=0)
    parsed = urlparse(raw_url)
    if parsed.scheme not in ("http", "https"):
        return json.dumps({"error": "Invalid URL: must be http or https"}, indent=0)
    if _host_is_private_or_blocked(parsed.hostname or ""):
        return json.dumps({"error": "Blocked URL host for safety."}, indent=0)

    extract_mode = "text" if (params.get("extractMode") == "text") else "markdown"
    max_chars = _to_int(params.get("maxChars"))
    max_chars = (
        DEFAULT_WEB_FETCH_MAX_CHARS
        if max_chars is None
        else max(1, min(max_chars, MAX_WEB_FETCH_CHARS_CAP))
    )
    timeout_seconds = DEFAULT_WEB_FETCH_TIMEOUT_SECONDS
    max_bytes = max_chars * 8

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "text/markdown, text/html;q=0.9, */*;q=0.1",
                "User-Agent": "Asta/1.0 (+https://github.com/helloworldxdwastaken/asta)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            async with client.stream("GET", raw_url) as res:
                final_url = str(res.url)
                final_host = urlparse(final_url).hostname or ""
                if _host_is_private_or_blocked(final_host):
                    return json.dumps({"error": "Blocked redirect target host for safety."}, indent=0)
                if res.status_code >= 400:
                    return json.dumps(
                        {"error": f"Web fetch failed ({res.status_code})", "status": res.status_code},
                        indent=0,
                    )
                raw_chunks: list[bytes] = []
                total = 0
                truncated_by_size = False
                async for chunk in res.aiter_bytes():
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        left = max(0, max_bytes - (total - len(chunk)))
                        if left > 0:
                            raw_chunks.append(chunk[:left])
                        truncated_by_size = True
                        break
                    raw_chunks.append(chunk)
                raw_body = b"".join(raw_chunks)
                content_type = (res.headers.get("content-type") or "application/octet-stream").lower()

        text = raw_body.decode("utf-8", errors="replace")
        title: str | None = None
        extractor = "raw"
        if "text/html" in content_type:
            text, title = _extract_html_text(text, extract_mode=extract_mode)
            extractor = "html"
        elif "application/json" in content_type:
            try:
                text = json.dumps(json.loads(text), indent=2)
                extractor = "json"
            except Exception:
                extractor = "raw"
        elif extract_mode == "text":
            text = text

        truncated = truncated_by_size
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True
        payload = {
            "url": raw_url,
            "finalUrl": final_url,
            "status": 200,
            "contentType": content_type.split(";")[0].strip(),
            "title": title,
            "extractMode": extract_mode,
            "extractor": extractor,
            "truncated": truncated,
            "length": len(text),
            "text": text,
        }
        return json.dumps(payload, indent=0)
    except Exception as e:
        return json.dumps({"error": f"Web fetch failed: {e}"}, indent=0)


def _workspace_root() -> Path | None:
    return get_settings().workspace_path


def _collect_memory_sources(user_id: str) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    root = _workspace_root()
    if root:
        user_md = root / "USER.md"
        if user_md.is_file():
            try:
                sources.append(("USER.md", user_md.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
        memory_md = root / "MEMORY.md"
        if memory_md.is_file():
            try:
                sources.append(("MEMORY.md", memory_md.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
        memory_dir = root / "memory"
        if memory_dir.is_dir():
            for p in sorted(memory_dir.rglob("*.md"))[:200]:
                try:
                    rel = p.resolve().relative_to(root.resolve()).as_posix()
                    sources.append((rel, p.read_text(encoding="utf-8", errors="replace")))
                except Exception:
                    continue
    # Keep legacy compatibility: if workspace source is empty, include persisted user memories.
    if not any(path == "USER.md" for path, _ in sources):
        mem = load_user_memories(user_id)
        if mem.strip():
            sources.append(("USER.md", mem))
    return sources


def _query_terms(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (query or "").lower()) if len(t) >= 2][:20]


def _score_memory_source(path: str, text: str, query: str, terms: list[str]) -> dict | None:
    lines = text.splitlines()
    if not lines:
        return None
    query_l = query.lower().strip()
    best_score = 0.0
    best_line = -1
    for i, line in enumerate(lines):
        ll = line.lower()
        term_hits = sum(1 for t in terms if t in ll)
        phrase_bonus = 2 if query_l and query_l in ll else 0
        score = float(term_hits + phrase_bonus)
        if score > best_score:
            best_score = score
            best_line = i
    if best_line < 0 or best_score <= 0:
        return None
    denom = max(1.0, float(len(terms) + 2))
    normalized = min(1.0, best_score / denom)
    start = max(0, best_line - 2)
    end = min(len(lines), best_line + 3)
    snippet = "\n".join(lines[start:end]).strip()
    return {
        "path": path,
        "startLine": start + 1,
        "endLine": end,
        "snippet": snippet,
        "score": round(normalized, 4),
        "source": "memory",
    }


async def run_memory_search_compat(params: dict, user_id: str) -> str:
    query = (params.get("query") or "").strip()
    if not query:
        return json.dumps({"results": [], "error": "query is required"}, indent=0)
    max_results = _to_int(params.get("maxResults"))
    max_results = (
        DEFAULT_MEMORY_RESULTS
        if max_results is None
        else max(1, min(max_results, MAX_MEMORY_RESULTS))
    )
    min_score = _to_float(params.get("minScore"))
    min_score = 0.0 if min_score is None else max(0.0, min(min_score, 1.0))
    mode = str(params.get("mode") or get_settings().memory_search_mode or DEFAULT_MEMORY_SEARCH_MODE).strip().lower()
    if mode not in ("search", "hybrid"):
        mode = DEFAULT_MEMORY_SEARCH_MODE

    terms = _query_terms(query)
    results: list[dict] = []
    for path, text in _collect_memory_sources(user_id):
        hit = _score_memory_source(path, text, query, terms)
        if hit and hit["score"] >= min_score:
            results.append(hit)

    fallback_used = False
    include_rag = mode == "hybrid"
    if (not include_rag) and (len(results) == 0):
        # Fast default: lexical search first. If very weak/no matches, use RAG as fallback fill.
        include_rag = True
        fallback_used = True

    if include_rag:
        try:
            from app.rag.service import get_rag

            rag = get_rag()
            rag_text = (await rag.query(query, k=max_results)).strip()
            if rag_text:
                rag_chunks = [c.strip() for c in rag_text.split("\n\n") if c.strip()]
                for i, chunk in enumerate(rag_chunks[:max_results]):
                    score = max(0.4, 0.9 - i * 0.1)
                    if score < min_score:
                        continue
                    line_count = max(1, len(chunk.splitlines()))
                    results.append(
                        {
                            "path": "rag://hybrid",
                            "startLine": 1,
                            "endLine": line_count,
                            "snippet": chunk,
                            "score": round(score, 4),
                            "source": "rag",
                        }
                    )
        except Exception:
            pass

    ranked = sorted(results, key=lambda r: float(r.get("score") or 0), reverse=True)[:max_results]
    payload = {
        "results": ranked,
        "provider": "asta-compat",
        "mode": mode,
        "fallback_used": fallback_used,
        "citations": "on",
    }
    return json.dumps(payload, indent=0)


def _resolve_memory_get_path(path: str) -> tuple[Path | None, str | None]:
    root = _workspace_root()
    if not root:
        return None, "Workspace is not configured."
    raw = (path or "").strip()
    if not raw:
        return None, "path is required."
    if raw in ("user:memories/User.md", "USER.md"):
        candidate = root / "USER.md"
    elif raw == "MEMORY.md":
        candidate = root / "MEMORY.md"
    else:
        p = Path(raw)
        candidate = (root / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        candidate.relative_to(root.resolve())
    except Exception:
        return None, "path must be inside workspace."
    rel = candidate.resolve().relative_to(root.resolve()).as_posix()
    allowed = rel in ("USER.md", "MEMORY.md") or rel.startswith("memory/")
    if not allowed:
        return None, "path must be USER.md, MEMORY.md, or under memory/."
    if not candidate.is_file():
        return None, f"file not found: {rel}"
    return candidate, None


async def run_memory_get_compat(params: dict) -> str:
    path = (params.get("path") or "").strip()
    file_path, err = _resolve_memory_get_path(path)
    if err:
        return json.dumps({"path": path, "text": "", "error": err}, indent=0)
    assert file_path is not None
    from_line = _to_int(params.get("from"))
    from_line = 1 if from_line is None else max(1, from_line)
    line_count = _to_int(params.get("lines"))
    line_count = (
        DEFAULT_MEMORY_GET_LINES
        if line_count is None
        else max(1, min(line_count, MAX_MEMORY_GET_LINES))
    )
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return json.dumps({"path": path, "text": "", "error": f"read failed: {e}"}, indent=0)
    start = min(max(0, from_line - 1), len(lines))
    end = min(len(lines), start + line_count)
    text = "\n".join(lines[start:end])
    root = _workspace_root()
    rel = (
        file_path.resolve().relative_to(root.resolve()).as_posix()
        if root
        else file_path.name
    )
    payload = {
        "path": rel,
        "from": start + 1 if lines else 1,
        "lines": max(0, end - start),
        "totalLines": len(lines),
        "text": text,
    }
    return json.dumps(payload, indent=0)
