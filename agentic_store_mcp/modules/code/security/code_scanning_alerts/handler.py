"""
code_scanning_alerts — retrieve GitHub code scanning (SARIF) alerts for a repo.

Requires GitHub token with 'security_events' or 'repo' scope.
"""
from __future__ import annotations

from typing import Any

try:
    from github import Github, GithubException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for code_scanning_alerts.

    Params:
        repo       GitHub 'owner/repo' (required)
        state      Alert state: open | dismissed | fixed (default: open)
        tool_name  Filter by tool: 'CodeQL', 'Semgrep', etc. (optional)
        severity   Filter by severity level (optional)
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    from agentic_store_mcp.secrets import get_token
    token = get_token("github_token")
    if not token:
        return {
            "result": None,
            "error": "GitHub token is required for code scanning alerts. "
                     "Run: configure {action: 'set', service: 'github_token', token: 'ghp_...'} "
                     "or set the GITHUB_TOKEN environment variable.",
        }

    repo_str = (params.get("repo") or "").strip()
    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}

    state = (params.get("state") or "open").strip().lower()
    tool_name_filter = (params.get("tool_name") or "").strip() or None
    severity_filter = (params.get("severity") or "").strip().lower() or None

    from github import Auth
    g = Github(auth=Auth.Token(token))
    try:
        repo = g.get_repo(repo_str)
        raw_alerts = repo.get_codescan_alerts()

        items = []
        for alert in raw_alerts:
            # State filter
            if alert.state != state:
                continue

            rule = alert.rule
            tool = alert.tool

            # Tool filter
            if tool_name_filter and tool_name_filter.lower() not in (tool.name or "").lower():
                continue

            # Severity filter
            alert_severity = (rule.severity or "none").lower() if rule else "none"
            if severity_filter and alert_severity != severity_filter:
                continue

            location = None
            if alert.most_recent_instance and alert.most_recent_instance.location:
                loc = alert.most_recent_instance.location
                location = {
                    "path": loc.path,
                    "start_line": loc.start_line,
                    "end_line": loc.end_line,
                }

            items.append({
                "number": alert.number,
                "state": alert.state,
                "rule": {
                    "id": rule.id if rule else None,
                    "name": rule.name if rule else None,
                    "severity": alert_severity,
                    "description": (rule.description or "")[:200] if rule else None,
                },
                "tool": tool.name if tool else None,
                "location": location,
                "url": alert.html_url,
                "created_at": str(alert.created_at)[:10] if alert.created_at else None,
            })

        tool_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        for item in items:
            t = item["tool"] or "unknown"
            tool_counts[t] = tool_counts.get(t, 0) + 1
            s = item["rule"]["severity"] or "unknown"
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "result": {
                "repo": repo_str,
                "state_filter": state,
                "tool_filter": tool_name_filter,
                "severity_filter": severity_filter,
                "total": len(items),
                "summary": {"by_tool": tool_counts, "by_severity": severity_counts},
                "alerts": items,
                "token_used": True,
            },
            "error": None,
        }

    except GithubException as e:
        if e.status == 403:
            return {"result": None, "error": "Access denied. Ensure your token has 'security_events' scope and code scanning is enabled for this repository."}
        if e.status == 404:
            return {"result": None, "error": f"Repository not found or code scanning not enabled: {repo_str}"}
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
