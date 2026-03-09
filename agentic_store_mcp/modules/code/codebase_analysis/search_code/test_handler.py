"""Tests for search_code."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("search_code_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_pattern():
    handler = load_handler()
    result = handler.run({"path": "/tmp"})
    assert result["error"] is not None


def test_both_path_and_repo():
    handler = load_handler()
    result = handler.run({"pattern": "foo", "path": "/tmp", "repo": "owner/repo"})
    assert result["error"] is not None


def test_neither_path_nor_repo():
    handler = load_handler()
    result = handler.run({"pattern": "foo"})
    assert result["error"] is not None


def test_local_search_finds_matches(tmp_path):
    (tmp_path / "hello.py").write_text("def hello_world():\n    pass\n")
    (tmp_path / "other.py").write_text("x = 1\n")

    handler = load_handler()
    result = handler.run({"pattern": "hello_world", "path": str(tmp_path)})
    assert result["error"] is None
    assert result["result"]["mode"] == "local"
    assert result["result"]["total"] >= 1
    files = [item["file"] for item in result["result"]["items"]]
    assert any("hello.py" in f for f in files)


def test_local_search_no_matches(tmp_path):
    (tmp_path / "empty.py").write_text("x = 1\n")
    handler = load_handler()
    result = handler.run({"pattern": "zzz_no_match_xyz", "path": str(tmp_path)})
    assert result["error"] is None
    assert result["result"]["total"] == 0


def test_local_search_extension_filter(tmp_path):
    (tmp_path / "match.py").write_text("target_fn()\n")
    (tmp_path / "match.js").write_text("target_fn()\n")
    handler = load_handler()
    result = handler.run({"pattern": "target_fn", "path": str(tmp_path), "file_extension": "py"})
    assert result["error"] is None
    for item in result["result"]["items"]:
        assert item["file"].endswith(".py")


def test_local_invalid_regex(tmp_path):
    handler = load_handler()
    result = handler.run({"pattern": "[invalid(regex", "path": str(tmp_path)})
    assert result["error"] is not None


def test_github_mode_no_pygithub(monkeypatch):
    handler = load_handler()
    monkeypatch.setattr(handler, "_HAS_PYGITHUB", False)
    result = handler.run({"pattern": "foo", "repo": "owner/repo"})
    assert result["error"] is not None
    assert "PyGithub" in result["error"]


def test_github_mode_mocked():
    handler = load_handler()

    mock_item = MagicMock()
    mock_item.repository.full_name = "owner/repo"
    mock_item.path = "src/main.py"
    mock_item.html_url = "https://github.com/owner/repo/blob/main/src/main.py"
    mock_item.sha = "abc123def456"

    mock_g = MagicMock()
    mock_g.search_code.return_value = [mock_item]

    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "_github_search", return_value=([{
             "repo": "owner/repo",
             "file": "src/main.py",
             "url": "https://github.com/owner/repo/blob/main/src/main.py",
             "sha": "abc123def4",
         }], True)):
        result = handler.run({"pattern": "foo", "repo": "owner/repo"})

    assert result["error"] is None
    assert result["result"]["mode"] == "github"
    assert result["result"]["total"] == 1
