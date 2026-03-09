"""
get_repo_info — fetch metadata and structure overview of a GitHub repository.

Token optional for public repos; required for private repos.
"""
from __future__ import annotations

from typing import Any

try:
    from github import Github, GithubException, UnknownObjectException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for get_repo_info.

    Params:
        repo   GitHub 'owner/repo' (required)
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    repo_str = (params.get("repo") or "").strip()
    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}

    from agentic_store_mcp.secrets import get_token
    from github import Auth
    token = get_token("github_token")
    g = Github(auth=Auth.Token(token)) if token else Github()

    try:
        repo = g.get_repo(repo_str)

        # Branches (up to 20)
        branches = []
        try:
            for branch in repo.get_branches():
                branches.append(branch.name)
                if len(branches) >= 20:
                    break
        except GithubException:
            pass

        # Top contributors (up to 10)
        contributors = []
        try:
            for contributor in repo.get_contributors():
                contributors.append({
                    "login": contributor.login,
                    "contributions": contributor.contributions,
                })
                if len(contributors) >= 10:
                    break
        except GithubException:
            pass

        # Recent tags (up to 5)
        tags = []
        try:
            for tag in repo.get_tags():
                tags.append(tag.name)
                if len(tags) >= 5:
                    break
        except GithubException:
            pass

        # Languages
        languages: dict[str, int] = {}
        try:
            languages = repo.get_languages()
        except GithubException:
            pass

        return {
            "result": {
                "repo": repo_str,
                "full_name": repo.full_name,
                "description": repo.description,
                "url": repo.html_url,
                "default_branch": repo.default_branch,
                "visibility": "private" if repo.private else "public",
                "stats": {
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "open_issues": repo.open_issues_count,
                    "watchers": repo.watchers_count,
                    "size_kb": repo.size,
                },
                "primary_language": repo.language,
                "languages": languages,
                "topics": repo.get_topics(),
                "license": repo.license.name if repo.license else None,
                "created_at": str(repo.created_at)[:10] if repo.created_at else None,
                "updated_at": str(repo.updated_at)[:10] if repo.updated_at else None,
                "pushed_at": str(repo.pushed_at)[:10] if repo.pushed_at else None,
                "branches": branches,
                "recent_tags": tags,
                "top_contributors": contributors,
                "token_used": token is not None,
            },
            "error": None,
        }

    except UnknownObjectException:
        return {"result": None, "error": f"Repository not found or not accessible: {repo_str}"}
    except GithubException as e:
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
