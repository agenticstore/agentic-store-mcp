"""
manage_issue — create, update, close, or triage GitHub issues.

Two-call confirmation pattern:
  1st call (confirmed=false): returns preview, no write made.
  2nd call (confirmed=true):  executes the write, returns result.
"""
from __future__ import annotations

from typing import Any

try:
    from github import Github, GithubException, UnknownObjectException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False

VALID_ACTIONS = {"create", "update", "close", "label"}


def _validate(params: dict) -> str | None:
    """Return an error string if params are invalid, else None."""
    action = params.get("action", "")
    if action not in VALID_ACTIONS:
        return f"Invalid action '{action}'. Valid actions: {', '.join(sorted(VALID_ACTIONS))}"
    if action == "create" and not (params.get("title") or "").strip():
        return "'title' is required for action 'create'"
    if action in ("update", "close", "label") and not params.get("issue_number"):
        return f"'issue_number' is required for action '{action}'"
    return None


def _build_preview(params: dict) -> dict:
    """Build a human-readable preview of the intended action — no API calls."""
    action = params.get("action", "")
    repo = params.get("repo", "")
    issue_number = params.get("issue_number")
    title = (params.get("title") or "").strip()
    body = (params.get("body") or "").strip()
    labels = params.get("labels") or []
    assignees = params.get("assignees") or []

    base: dict[str, Any] = {
        "action": action,
        "repo": repo,
    }

    if action == "create":
        base["will_create"] = {
            "title": title,
            "body_preview": body[:200] + ("…" if len(body) > 200 else ""),
            "labels": labels,
            "assignees": assignees,
        }
    elif action == "update":
        changes: dict[str, Any] = {"issue_number": issue_number}
        if title:
            changes["new_title"] = title
        if body:
            changes["new_body_preview"] = body[:200] + ("…" if len(body) > 200 else "")
        base["will_update"] = changes
    elif action == "close":
        base["will_close"] = {"issue_number": issue_number}
    elif action == "label":
        base["will_label"] = {
            "issue_number": issue_number,
            "new_labels": labels,
            "new_assignees": assignees,
        }

    return base


def _execute(params: dict, g: Any) -> dict:
    """Execute the write against GitHub API."""
    action = params["action"]
    repo_obj = g.get_repo(params["repo"])

    if action == "create":
        kwargs: dict[str, Any] = {"title": params["title"].strip()}
        if params.get("body"):
            kwargs["body"] = params["body"]
        if params.get("labels"):
            kwargs["labels"] = params["labels"]
        if params.get("assignees"):
            kwargs["assignees"] = params["assignees"]
        issue = repo_obj.create_issue(**kwargs)
        return {
            "issue_number": issue.number,
            "title": issue.title,
            "url": issue.html_url,
            "state": issue.state,
        }

    issue = repo_obj.get_issue(number=int(params["issue_number"]))

    if action == "update":
        edit_kwargs: dict[str, Any] = {}
        if params.get("title"):
            edit_kwargs["title"] = params["title"].strip()
        if params.get("body"):
            edit_kwargs["body"] = params["body"]
        if edit_kwargs:
            issue.edit(**edit_kwargs)
        return {
            "issue_number": issue.number,
            "title": issue.title,
            "url": issue.html_url,
            "state": issue.state,
        }

    if action == "close":
        issue.edit(state="closed")
        return {
            "issue_number": issue.number,
            "url": issue.html_url,
            "state": "closed",
        }

    if action == "label":
        edit_kwargs = {}
        if params.get("labels") is not None:
            edit_kwargs["labels"] = params["labels"]
        if params.get("assignees") is not None:
            edit_kwargs["assignees"] = params["assignees"]
        if edit_kwargs:
            issue.edit(**edit_kwargs)
        return {
            "issue_number": issue.number,
            "url": issue.html_url,
            "labels": [lbl.name for lbl in issue.labels],
            "assignees": [a.login for a in issue.assignees],
        }

    raise ValueError(f"Unhandled action: {action}")


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for manage_issue.

    Call once with confirmed=false (default) to preview.
    Call again with confirmed=true to execute.
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    repo_str = (params.get("repo") or "").strip()
    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}

    err = _validate(params)
    if err:
        return {"result": None, "error": err}

    confirmed = bool(params.get("confirmed", False))
    preview = _build_preview(params)

    if not confirmed:
        return {
            "result": {
                "status": "awaiting_confirmation",
                "preview": preview,
                "message": (
                    "Review the preview above. No changes have been made. "
                    "Call this tool again with confirmed=true to execute."
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
            "error": "GitHub token is required for write operations. "
                     "Run: configure {action: 'set', service: 'github_token', token: 'ghp_...'}",
        }

    from github import Auth
    g = Github(auth=Auth.Token(token))
    try:
        result = _execute(params, g)
        return {
            "result": {"status": "success", "action": params["action"], **result},
            "error": None,
        }
    except UnknownObjectException:
        issue_num = params.get("issue_number")
        return {"result": None, "error": f"Issue #{issue_num} not found in {repo_str}"}
    except GithubException as e:
        if e.status == 403:
            return {"result": None, "error": "Access denied. Ensure your token has 'repo' scope."}
        if e.status == 422:
            return {"result": None, "error": f"Validation error: {e.data}"}
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
