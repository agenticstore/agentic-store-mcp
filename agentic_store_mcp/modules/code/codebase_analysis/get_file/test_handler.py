"""Tests for get_file."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("get_file_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_repo():
    handler = load_handler()
    result = handler.run({"file_path": "README.md"})
    assert result["error"] is not None


def test_missing_file_path():
    handler = load_handler()
    result = handler.run({"repo": "owner/repo"})
    assert result["error"] is not None


def test_no_pygithub(monkeypatch):
    handler = load_handler()
    monkeypatch.setattr(handler, "_HAS_PYGITHUB", False)
    result = handler.run({"repo": "owner/repo", "file_path": "README.md"})
    assert result["error"] is not None
    assert "PyGithub" in result["error"]


def test_file_found():
    handler = load_handler()

    mock_contents = MagicMock()
    mock_contents.encoding = "base64"
    import base64
    mock_contents.content = base64.b64encode(b"# Hello World\n").decode()
    mock_contents.sha = "abc123def456"
    mock_contents.size = 14
    mock_contents.html_url = "https://github.com/owner/repo/blob/main/README.md"
    mock_contents.decoded_content = b"# Hello World\n"

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.get_contents.return_value = mock_contents

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "file_path": "README.md"})

    assert result["error"] is None
    assert result["result"]["file_path"] == "README.md"
    assert result["result"]["is_binary"] is False


def test_file_not_found():
    from github import UnknownObjectException
    handler = load_handler()

    mock_repo = MagicMock()
    mock_repo.get_contents.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value=None), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "file_path": "nonexistent.txt"})

    assert result["error"] is not None
    assert "not found" in result["error"].lower()


def test_directory_path():
    handler = load_handler()

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.get_contents.return_value = [MagicMock(), MagicMock()]  # list = directory

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value=None), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "file_path": "src"})

    assert result["error"] is not None
