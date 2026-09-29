"""Tests for update_learnings."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("update_learnings_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patches(tmp_path):
    mem = tmp_path / "memory"
    return {
        "MEMORY_DIR": mem,
        "_SESSION_FILE": mem / "session.jsonl",
    }


def test_add_learning(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({"learning": "Use Auth.Token for PyGithub 2.x"})
    assert result["error"] is None
    assert result["result"]["status"] == "added"
    content = (mem / "learnings.md").read_text()
    assert "Use Auth.Token for PyGithub 2.x" in content


def test_add_with_category_and_source(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({
            "learning": "Always patch at handler module level",
            "category": "testing",
            "source": "PyGithub mock debugging",
        })
    assert result["error"] is None
    assert result["result"]["category"] == "testing"
    content = (mem / "learnings.md").read_text()
    assert "PyGithub mock debugging" in content


def test_missing_learning():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None


def test_multiple_learnings_accumulate(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"learning": "Learning one"})
        handler.run({"learning": "Learning two"})
    content = (mem / "learnings.md").read_text()
    assert "Learning one" in content
    assert "Learning two" in content
