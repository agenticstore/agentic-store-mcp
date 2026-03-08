"""
agentic_web_search — search the web using a self-hosted SearXNG instance.

SearXNG is a free, open-source metasearch engine that aggregates results from
multiple search engines without tracking users.

Run SearXNG locally (required):
    docker compose up -d       # from the agentic-store-mcp directory

Configuration:
    SEARXNG_URL   Base URL of your SearXNG instance (default: http://localhost:8080)

Zero extra Python dependencies — pure stdlib (urllib, json).
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_DEFAULT_SEARXNG_URL = "http://localhost:8080"
_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; AgenticStore/1.0; +https://github.com/agenticstore)"
)
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for agentic_web_search.

    Sends a query to a self-hosted SearXNG instance and returns structured
    search results with title, URL, and snippet for each result.

    Params:
        query        Search query string (required)
        categories   SearXNG category: general, news, images, science, etc. (default: "general")
        language     Language code for results, e.g. "en", "de", "fr" (default: "en")
        max_results  Number of results to return, clamped 1–50 (default: 10)

    Environment:
        SEARXNG_URL  Base URL of the SearXNG instance (default: http://localhost:8080)

    Returns {"result": {...}, "error": None} on success or {"result": None, "error": "..."} on failure.
    """
    query: str = (params.get("query") or "").strip()
    if not query:
        return {"result": None, "error": "query is required"}

    try:
        max_results = min(max(int(params.get("max_results") or 10), 1), 50)
    except (TypeError, ValueError) as exc:
        return {"result": None, "error": f"Invalid max_results: {exc}"}

    categories: str = (params.get("categories") or "general").strip()
    language: str = (params.get("language") or "en").strip()

    base_url = (os.getenv("SEARXNG_URL") or _DEFAULT_SEARXNG_URL).rstrip("/")

    qs = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "categories": categories,
        "language": language,
    })
    url = f"{base_url}/search?{qs}"

    req = urllib.request.Request(url, headers={"User-Agent": _DEFAULT_UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(_MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            return {
                "result": None,
                "error": (
                    f"SearXNG returned HTTP 400 from {base_url}. "
                    "The JSON format may not be enabled — check searxng/settings.yml "
                    "and ensure 'json' is listed under search.formats."
                ),
            }
        return {"result": None, "error": f"HTTP {exc.code} from SearXNG at {base_url}"}
    except urllib.error.URLError as exc:
        return {
            "result": None,
            "error": (
                f"Cannot reach SearXNG at {base_url}: {exc.reason}. "
                "Is it running? Try: docker compose up -d"
            ),
        }
    except socket.timeout:
        return {"result": None, "error": f"SearXNG timed out (15s) at {base_url}"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return {"result": None, "error": f"SearXNG returned non-JSON response: {exc}"}

    raw_results: list[dict[str, Any]] = data.get("results") or []
    results = [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("content") or "",
            "engine": r.get("engine") or "",
        }
        for r in raw_results[:max_results]
    ]

    return {
        "result": {
            "query": query,
            "categories": categories,
            "language": language,
            "total_results": len(raw_results),
            "results": results,
        },
        "error": None,
    }
