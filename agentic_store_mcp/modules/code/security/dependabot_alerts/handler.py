"""
dependabot_alerts — retrieve Dependabot vulnerability alerts for a GitHub repo.

Requires GitHub token with 'security_events' or 'repo' scope.
"""
from __future__ import annotations

from typing import Any

try:
    from github import Github, GithubException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for dependabot_alerts.

    Params:
        repo      GitHub 'owner/repo' (required)
        state     Alert state: open | dismissed | fixed | auto_dismissed (default: open)
        severity  Filter by minimum severity: critical | high | medium | low (optional)
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    from agentic_store_mcp.secrets import get_token
    token = get_token("github_token")
    if not token:
        return {
            "result": None,
            "error": "GitHub token is required for Dependabot alerts. "
                     "Run: configure {action: 'set', service: 'github_token', token: 'ghp_...'} "
                     "or set the GITHUB_TOKEN environment variable.",
        }

    repo_str = (params.get("repo") or "").strip()
    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}

    state = (params.get("state") or "open").strip().lower()
    severity_filter = (params.get("severity") or "").strip().lower() or None

    from github import Auth
    g = Github(auth=Auth.Token(token))
    try:
        repo = g.get_repo(repo_str)
        raw_alerts = repo.get_dependabot_alerts(state=state)

        items = []
        for alert in raw_alerts:
            adv = alert.security_advisory
            vuln = alert.security_vulnerability

            sev = (adv.severity or "unknown").lower()
            if severity_filter:
                if SEVERITY_ORDER.get(sev, 99) > SEVERITY_ORDER.get(severity_filter, 99):
                    continue

            items.append({
                "number": alert.number,
                "state": alert.state,
                "severity": sev,
                "cve_id": adv.cve_id,
                "ghsa_id": adv.ghsa_id,
                "summary": adv.summary[:200] if adv.summary else None,
                "package": {
                    "name": vuln.package.name if vuln and vuln.package else None,
                    "ecosystem": vuln.package.ecosystem if vuln and vuln.package else None,
                    "vulnerable_range": vuln.vulnerable_version_range if vuln else None,
                    "fixed_in": vuln.first_patched_version if vuln else None,
                },
                "url": alert.html_url,
                "created_at": str(alert.created_at)[:10] if alert.created_at else None,
                "dismissed_at": str(alert.dismissed_at)[:10] if getattr(alert, "dismissed_at", None) else None,
            })

        severity_counts: dict[str, int] = {}
        for item in items:
            sev = item["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "result": {
                "repo": repo_str,
                "state_filter": state,
                "severity_filter": severity_filter,
                "total": len(items),
                "summary": severity_counts,
                "alerts": items,
                "token_used": True,
            },
            "error": None,
        }

    except GithubException as e:
        if e.status == 403:
            return {"result": None, "error": "Access denied. Ensure your token has 'security_events' or 'repo' scope, and Dependabot alerts are enabled for this repository."}
        if e.status == 404:
            return {"result": None, "error": f"Repository not found or not accessible: {repo_str}"}
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
