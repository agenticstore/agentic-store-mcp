"""
create_pr — open a pull request in a GitHub repository.

Two-call confirmation pattern:
  1st call (confirmed=false): returns preview, no write made.
  2nd call (confirmed=true):  executes the write, returns the new PR URL.
"""
from __future__ import annotations

from typing import Any

try:
    from github import Github, GithubException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False


def _build_preview(params: dict) -> dict:
    """Build a human-readable preview of the PR to be created — no API calls."""
    body = (params.get("body") or "").strip()
    return {
        "action": "create_pr",
        "repo": params.get("repo", ""),
        "title": (params.get("title") or "").strip(),
        "head": (params.get("head") or "").strip(),
        "base": (params.get("base") or "main").strip(),
        "draft": bool(params.get("draft", False)),
        "body_preview": body[:300] + ("…" if len(body) > 300 else ""),
    }


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for create_pr.

    Call once with confirmed=false (default) to preview.
    Call again with confirmed=true to execute.
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    repo_str = (params.get("repo") or "").strip()
    title = (params.get("title") or "").strip()
    head = (params.get("head") or "").strip()
    base = (params.get("base") or "main").strip()
    body = (params.get("body") or "").strip()
    draft = bool(params.get("draft", False))
    confirmed = bool(params.get("confirmed", False))

    # Validate
    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}
    if not title:
        return {"result": None, "error": "'title' is required"}
    if not head:
        return {"result": None, "error": "'head' (source branch) is required"}

    preview = _build_preview(params)

    if not confirmed:
        return {
            "result": {
                "status": "awaiting_confirmation",
                "preview": preview,
                "message": (
                    "Review the pull request details above. No changes have been made. "
                    "Call this tool again with confirmed=true to open the PR."
                ),
            },
            "error": None,
        }

    # Execute
    from agentic_store_mcp.secrets import get_token
    token = get_token("github_token")
    if not token:
        return {
            "result": None,
            "error": "GitHub token is required to create a pull request. "
                     "Run: configure {action: 'set', service: 'github_token', token: 'ghp_...'}",
        }

    from github import Auth
    g = Github(auth=Auth.Token(token))
    try:
        repo = g.get_repo(repo_str)

        # Resolve base to repo default branch if caller passed 'main' but repo uses 'master'
        resolved_base = base if base else repo.default_branch

        kwargs: dict[str, Any] = {
            "title": title,
            "head": head,
            "base": resolved_base,
            "draft": draft,
        }
        if body:
            kwargs["body"] = body

        pr = repo.create_pull(**kwargs)

        return {
            "result": {
                "status": "success",
                "pr_number": pr.number,
                "title": pr.title,
                "url": pr.html_url,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "draft": pr.draft,
                "state": pr.state,
            },
            "error": None,
        }

    except GithubException as e:
        if e.status == 403:
            return {"result": None, "error": "Access denied. Ensure your token has 'repo' scope."}
        if e.status == 404:
            return {"result": None, "error": f"Repository not found: {repo_str}"}
        if e.status == 422:
            data = e.data or {}
            errors = data.get("errors", [])
            if errors:
                msg = "; ".join(err.get("message", str(err)) for err in errors if isinstance(err, dict))
                return {"result": None, "error": f"Validation error: {msg}"}
            return {"result": None, "error": f"Validation error — PR may already exist or branch not found: {data}"}
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
