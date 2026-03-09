"""Tests for get_repo_info."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("get_repo_info_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_repo():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None


def test_no_pygithub(monkeypatch):
    handler = load_handler()
    monkeypatch.setattr(handler, "_HAS_PYGITHUB", False)
    result = handler.run({"repo": "owner/repo"})
    assert result["error"] is not None


def _make_mock_repo():
    repo = MagicMock()
    repo.full_name = "owner/repo"
    repo.description = "A test repo"
    repo.html_url = "https://github.com/owner/repo"
    repo.default_branch = "main"
    repo.private = False
    repo.stargazers_count = 42
    repo.forks_count = 7
    repo.open_issues_count = 3
    repo.watchers_count = 42
    repo.size = 1024
    repo.language = "Python"
    repo.license = MagicMock()
    repo.license.name = "MIT License"
    repo.created_at = MagicMock()
    repo.created_at.__str__ = lambda s: "2024-01-01 00:00:00"
    repo.updated_at = MagicMock()
    repo.updated_at.__str__ = lambda s: "2026-03-01 00:00:00"
    repo.pushed_at = MagicMock()
    repo.pushed_at.__str__ = lambda s: "2026-03-09 00:00:00"

    branch = MagicMock()
    branch.name = "main"
    repo.get_branches.return_value = [branch]

    contributor = MagicMock()
    contributor.login = "alice"
    contributor.contributions = 100
    repo.get_contributors.return_value = [contributor]

    tag = MagicMock()
    tag.name = "v1.0.0"
    repo.get_tags.return_value = [tag]

    repo.get_languages.return_value = {"Python": 50000, "Shell": 1000}
    repo.get_topics.return_value = ["mcp", "ai", "tools"]

    return repo


def test_success_public_repo():
    handler = load_handler()
    mock_repo = _make_mock_repo()
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value=None), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo"})

    assert result["error"] is None
    r = result["result"]
    assert r["repo"] == "owner/repo"
    assert r["stats"]["stars"] == 42
    assert r["primary_language"] == "Python"
    assert "main" in r["branches"]
    assert r["top_contributors"][0]["login"] == "alice"
    assert r["recent_tags"] == ["v1.0.0"]
    assert r["token_used"] is False


def test_success_with_token():
    handler = load_handler()
    mock_repo = _make_mock_repo()
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo"})

    assert result["error"] is None
    assert result["result"]["token_used"] is True


def test_repo_not_found():
    from github import UnknownObjectException
    handler = load_handler()
    mock_g = MagicMock()
    mock_g.get_repo.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value=None), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/nonexistent"})

    assert result["error"] is not None
    assert "not found" in result["error"].lower()
