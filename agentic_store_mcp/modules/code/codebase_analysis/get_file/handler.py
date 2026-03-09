"""
get_file — fetch content of a specific file from a GitHub repository.

Token optional for public repos; required for private repos.
"""
from __future__ import annotations

import base64
from typing import Any

try:
    from github import Github, GithubException, UnknownObjectException
    _HAS_PYGITHUB = True
except ImportError:
    _HAS_PYGITHUB = False


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for get_file.

    Params:
        repo       GitHub 'owner/repo' (required)
        file_path  Path to the file in the repo (required)
        ref        Branch, tag, or commit SHA (default: repo's default branch)
    """
    if not _HAS_PYGITHUB:
        return {"result": None, "error": "PyGithub not installed. Run: uv sync"}

    repo_str = (params.get("repo") or "").strip()
    file_path = (params.get("file_path") or "").strip()
    ref = (params.get("ref") or "").strip() or None

    if not repo_str:
        return {"result": None, "error": "'repo' is required (format: owner/repo)"}
    if not file_path:
        return {"result": None, "error": "'file_path' is required"}

    from agentic_store_mcp.secrets import get_token
    from github import Auth
    token = get_token("github_token")
    g = Github(auth=Auth.Token(token)) if token else Github()

    try:
        repo = g.get_repo(repo_str)
        kwargs = {"ref": ref} if ref else {}
        contents = repo.get_contents(file_path, **kwargs)

        # get_contents can return a list if path is a directory
        if isinstance(contents, list):
            return {
                "result": None,
                "error": f"'{file_path}' is a directory, not a file. Use search_code or get_repo_info to explore directories.",
            }

        # Decode content
        if contents.encoding == "base64":
            try:
                text = base64.b64decode(contents.content).decode("utf-8")
            except (UnicodeDecodeError, Exception):
                text = None  # binary file
        else:
            text = contents.decoded_content.decode("utf-8", errors="replace") if contents.decoded_content else None

        return {
            "result": {
                "repo": repo_str,
                "file_path": file_path,
                "ref": ref or repo.default_branch,
                "sha": contents.sha[:12],
                "size_bytes": contents.size,
                "url": contents.html_url,
                "encoding": contents.encoding,
                "is_binary": text is None,
                "content": text,
                "token_used": token is not None,
            },
            "error": None,
        }

    except UnknownObjectException:
        return {"result": None, "error": f"File not found: '{file_path}' in {repo_str} (ref: {ref or 'default'})"}
    except GithubException as e:
        return {"result": None, "error": f"GitHub API error: {e.status} {e.data}"}
