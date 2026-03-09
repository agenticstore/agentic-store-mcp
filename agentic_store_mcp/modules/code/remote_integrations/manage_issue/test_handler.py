"""Tests for manage_issue — covers preview path and confirmed execution path."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("manage_issue_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── Validation ───────────────────────────────────────────────────────────────

def test_missing_repo():
    handler = load_handler()
    result = handler.run({"action": "create", "title": "Bug"})
    assert result["error"] is not None

def test_missing_action():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "action": "fly"})
    assert result["error"] is not None

def test_create_missing_title():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "action": "create"})
    assert result["error"] is not None
    assert "title" in result["error"].lower()

def test_update_missing_issue_number():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "action": "update", "title": "New title"})
    assert result["error"] is not None
    assert "issue_number" in result["error"].lower()


# ─── Preview (confirmed=false) ────────────────────────────────────────────────

def test_preview_create():
    handler = load_handler()
    result = handler.run({
        "repo": "owner/repo",
        "action": "create",
        "title": "Found a bug",
        "body": "Steps to reproduce...",
        "labels": ["bug"],
    })
    assert result["error"] is None
    assert result["result"]["status"] == "awaiting_confirmation"
    preview = result["result"]["preview"]
    assert preview["action"] == "create"
    assert preview["will_create"]["title"] == "Found a bug"
    assert "bug" in preview["will_create"]["labels"]

def test_preview_close():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "action": "close", "issue_number": 42})
    assert result["error"] is None
    assert result["result"]["status"] == "awaiting_confirmation"
    assert result["result"]["preview"]["will_close"]["issue_number"] == 42

def test_preview_label():
    handler = load_handler()
    result = handler.run({
        "repo": "owner/repo",
        "action": "label",
        "issue_number": 7,
        "labels": ["wontfix"],
        "assignees": ["alice"],
    })
    assert result["error"] is None
    assert result["result"]["preview"]["will_label"]["new_labels"] == ["wontfix"]

def test_no_write_when_unconfirmed():
    """Ensure no GitHub API calls are made when confirmed=false."""
    handler = load_handler()
    mock_constructor = MagicMock()
    with patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "action": "create",
            "title": "Test",
            "confirmed": False,
        })
    assert result["error"] is None
    mock_constructor.assert_not_called()


# ─── Execution (confirmed=true) ───────────────────────────────────────────────

def test_confirmed_create():
    handler = load_handler()

    mock_issue = MagicMock()
    mock_issue.number = 99
    mock_issue.title = "Found a bug"
    mock_issue.html_url = "https://github.com/owner/repo/issues/99"
    mock_issue.state = "open"

    mock_repo = MagicMock()
    mock_repo.create_issue.return_value = mock_issue

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "action": "create",
            "title": "Found a bug",
            "body": "Steps to reproduce...",
            "confirmed": True,
        })

    assert result["error"] is None
    assert result["result"]["status"] == "success"
    assert result["result"]["issue_number"] == 99
    assert result["result"]["url"] == "https://github.com/owner/repo/issues/99"


def test_confirmed_close():
    handler = load_handler()

    mock_issue = MagicMock()
    mock_issue.number = 42
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_issue.state = "closed"

    mock_repo = MagicMock()
    mock_repo.get_issue.return_value = mock_issue

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "action": "close",
            "issue_number": 42,
            "confirmed": True,
        })

    assert result["error"] is None
    assert result["result"]["status"] == "success"
    mock_issue.edit.assert_called_once_with(state="closed")


def test_confirmed_no_token():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.get_token", return_value=None):
        result = handler.run({
            "repo": "owner/repo",
            "action": "create",
            "title": "Bug",
            "confirmed": True,
        })
    assert result["error"] is not None
    assert "token" in result["error"].lower()


def test_confirmed_403():
    from github import GithubException
    handler = load_handler()

    mock_g = MagicMock()
    mock_g.get_repo.side_effect = GithubException(403, {"message": "Forbidden"}, {})

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "action": "create",
            "title": "Bug",
            "confirmed": True,
        })

    assert result["error"] is not None
    assert "Access denied" in result["error"]
