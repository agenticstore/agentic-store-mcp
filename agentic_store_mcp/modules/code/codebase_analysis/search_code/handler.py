"""
search_code — search for patterns across a local directory or GitHub repo.

Local mode: regex walk of local files (no token required).
GitHub mode: GitHub code search API (token optional for public repos).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    from github import Github, GithubException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".jpg", ".jpeg",
                   ".png", ".gif", ".ico", ".svg", ".woff", ".woff2", ".pdf",
                   ".zip", ".tar", ".gz", ".parquet", ".pkl", ".bin"}
MAX_FILE_SIZE = 500 * 1024  # 500 KB


def _local_search(pattern: str, path: str, file_extension: str | None, max_results: int) -> list[dict]:
    """Grep-style walk of a local directory."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e

    root = Path(path)
    results = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if len(results) >= max_results:
                break
            fp = Path(dirpath) / filename
            if fp.suffix.lower() in SKIP_EXTENSIONS:
                continue
            if file_extension and fp.suffix.lower() != f".{file_extension.lstrip('.')}":
                continue
            try:
                if fp.stat().st_size > MAX_FILE_SIZE:
                    continue
                content = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append({
                        "file": str(fp.relative_to(root)),
                        "line": i,
                        "match": line.strip()[:200],
                    })
                    if len(results) >= max_results:
                        break

    return results


def _github_search(pattern: str, repo: str, file_extension: str | None, max_results: int) -> tuple[list[dict], bool]:
    """GitHub code search API."""
    from agentic_store_mcp.secrets import get_token
    from github import Auth
    token = get_token("github_token")
    g = Github(auth=Auth.Token(token)) if token else Github()

    query = pattern
    if repo:
        query += f" repo:{repo}"
    if file_extension:
        query += f" extension:{file_extension.lstrip('.')}"

    try:
        results_raw = g.search_code(query)
        items = []
        for item in results_raw[:max_results]:
            items.append({
                "repo": item.repository.full_name,
                "file": item.path,
                "url": item.html_url,
                "sha": item.sha[:12],
            })
        return items, token is not None
    except GithubException as e:
        raise RuntimeError(f"GitHub API error: {e.status} {e.data}") from e


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for search_code.

    Params:
        pattern        Search pattern — regex (local) or keyword (GitHub)
        path           Local directory to search (local mode)
        repo           GitHub 'owner/repo' (GitHub mode)
        file_extension Filter by extension e.g. 'py', 'ts'
        max_results    Max results (default 50)
    """
    pattern = (params.get("pattern") or "").strip()
    if not pattern:
        return {"result": None, "error": "'pattern' is required"}

    path = (params.get("path") or "").strip()
    repo = (params.get("repo") or "").strip()
    file_extension = (params.get("file_extension") or "").strip() or None
    max_results = int(params.get("max_results") or 50)

    if not path and not repo:
        return {"result": None, "error": "Either 'path' (local directory) or 'repo' (GitHub owner/repo) is required"}

    if path and repo:
        return {"result": None, "error": "Provide either 'path' or 'repo', not both"}

    if path:
        root = Path(path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return {"result": None, "error": f"Path does not exist or is not a directory: {path}"}
        try:
            items = _local_search(pattern, str(root), file_extension, max_results)
        except ValueError as e:
            return {"result": None, "error": str(e)}

        return {
            "result": {
                "mode": "local",
                "pattern": pattern,
                "path": str(root),
                "total": len(items),
                "truncated": len(items) >= max_results,
                "items": items,
            },
            "error": None,
        }

    # GitHub mode
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    try:
        items, token_used = _github_search(pattern, repo, file_extension, max_results)
    except RuntimeError as e:
        return {"result": None, "error": str(e)}

    return {
        "result": {
            "mode": "github",
            "pattern": pattern,
            "repo": repo,
            "total": len(items),
            "truncated": len(items) >= max_results,
            "token_used": token_used,
            "items": items,
        },
        "error": None,
    }
