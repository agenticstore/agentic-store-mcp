"""Tests for create_pr — covers preview path and confirmed execution path."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("create_pr_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── Validation ───────────────────────────────────────────────────────────────

def test_missing_repo():
    handler = load_handler()
    result = handler.run({"title": "My PR", "head": "feature/x"})
    assert result["error"] is not None

def test_missing_title():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "head": "feature/x"})
    assert result["error"] is not None
    assert "title" in result["error"].lower()

def test_missing_head():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "title": "My PR"})
    assert result["error"] is not None
    assert "head" in result["error"].lower()


# ─── Preview (confirmed=false) ────────────────────────────────────────────────

def test_preview_default():
    handler = load_handler()
    result = handler.run({
        "repo": "owner/repo",
        "title": "Add new feature",
        "head": "feature/new-thing",
        "base": "main",
        "body": "This PR adds a great feature.",
    })
    assert result["error"] is None
    assert result["result"]["status"] == "awaiting_confirmation"
    preview = result["result"]["preview"]
    assert preview["title"] == "Add new feature"
    assert preview["head"] == "feature/new-thing"
    assert preview["base"] == "main"
    assert preview["draft"] is False

def test_preview_draft():
    handler = load_handler()
    result = handler.run({
        "repo": "owner/repo",
        "title": "WIP: Big refactor",
        "head": "refactor/everything",
        "draft": True,
    })
    assert result["error"] is None
    assert result["result"]["preview"]["draft"] is True

def test_no_write_when_unconfirmed():
    """Ensure no GitHub API calls when confirmed=false."""
    handler = load_handler()
    mock_constructor = MagicMock()
    with patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "title": "Test PR",
            "head": "feature/x",
            "confirmed": False,
        })
    assert result["error"] is None
    mock_constructor.assert_not_called()

def test_preview_message_present():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo", "title": "T", "head": "h"})
    assert "message" in result["result"]
    assert "confirmed=true" in result["result"]["message"]


# ─── Execution (confirmed=true) ───────────────────────────────────────────────

def test_confirmed_creates_pr():
    handler = load_handler()

    mock_pr = MagicMock()
    mock_pr.number = 17
    mock_pr.title = "Add new feature"
    mock_pr.html_url = "https://github.com/owner/repo/pull/17"
    mock_pr.head.ref = "feature/new-thing"
    mock_pr.base.ref = "main"
    mock_pr.draft = False
    mock_pr.state = "open"

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.create_pull.return_value = mock_pr

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "title": "Add new feature",
            "head": "feature/new-thing",
            "base": "main",
            "body": "Great changes.",
            "confirmed": True,
        })

    assert result["error"] is None
    assert result["result"]["status"] == "success"
    assert result["result"]["pr_number"] == 17
    assert result["result"]["url"] == "https://github.com/owner/repo/pull/17"
    mock_repo.create_pull.assert_called_once()


def test_confirmed_no_token():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.get_token", return_value=None):
        result = handler.run({
            "repo": "owner/repo",
            "title": "My PR",
            "head": "feature/x",
            "confirmed": True,
        })
    assert result["error"] is not None
    assert "token" in result["error"].lower()


def test_confirmed_422_branch_not_found():
    from github import GithubException
    handler = load_handler()

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.create_pull.side_effect = GithubException(
        422, {"message": "Validation Failed", "errors": [{"message": "head sha is not a commit"}]}, {}
    )
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "title": "PR",
            "head": "nonexistent-branch",
            "confirmed": True,
        })

    assert result["error"] is not None
    assert "422" in result["error"] or "Validation" in result["error"]


def test_confirmed_draft_pr():
    handler = load_handler()

    mock_pr = MagicMock()
    mock_pr.number = 5
    mock_pr.title = "WIP"
    mock_pr.html_url = "https://github.com/owner/repo/pull/5"
    mock_pr.head.ref = "wip/stuff"
    mock_pr.base.ref = "main"
    mock_pr.draft = True
    mock_pr.state = "open"

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.create_pull.return_value = mock_pr

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({
            "repo": "owner/repo",
            "title": "WIP",
            "head": "wip/stuff",
            "draft": True,
            "confirmed": True,
        })

    assert result["error"] is None
    assert result["result"]["draft"] is True
    # Verify draft=True was passed to create_pull
    call_kwargs = mock_repo.create_pull.call_args[1]
    assert call_kwargs.get("draft") is True
