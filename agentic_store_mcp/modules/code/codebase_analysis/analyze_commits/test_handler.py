"""Tests for analyze_commits."""
import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("analyze_commits_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_path():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None


def test_nonexistent_path():
    handler = load_handler()
    result = handler.run({"path": "/nonexistent/path/xyz"})
    assert result["error"] is not None


def test_not_a_git_repo(tmp_path):
    handler = load_handler()
    result = handler.run({"path": str(tmp_path)})
    assert result["error"] is not None
    assert "git" in result["error"].lower()


def test_real_repo():
    """Analyze the project's own git repo — always available in CI."""
    handler = load_handler()
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    result = handler.run({"path": str(repo_root), "max_commits": 5})
    assert result["error"] is None
    assert result["result"]["total_commits"] >= 0


def test_empty_result_on_no_matches(tmp_path):
    """If git log returns nothing (e.g. author filter matches nothing), return empty."""
    # Init a real git repo so _is_git_repo passes
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    handler = load_handler()
    result = handler.run({"path": str(tmp_path), "author": "nobody_matches_this_xyz"})
    assert result["error"] is None
    assert result["result"]["total_commits"] == 0


def test_summary_structure():
    handler = load_handler()
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    result = handler.run({"path": str(repo_root), "max_commits": 10})
    if result["result"]["total_commits"] > 0:
        assert "authors" in result["result"]["summary"]
        assert "busiest_days" in result["result"]["summary"]
        assert "date_range" in result["result"]["summary"]
