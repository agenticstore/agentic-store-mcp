"""Tests for update_change_log."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("update_change_log_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patches(tmp_path):
    mem = tmp_path / "memory"
    return {
        "MEMORY_DIR": mem,
        "_SESSION_FILE": mem / "session.jsonl",
    }


def test_add_entry_unreleased(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({"description": "Add memory module", "change_type": "feat"})
    assert result["error"] is None
    assert result["result"]["status"] == "logged"
    content = (mem / "CHANGELOG.md").read_text()
    assert "Add memory module" in content
    assert "Unreleased" in content


def test_add_entry_with_version(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({"description": "Fix auth bug", "change_type": "fix", "version": "v1.1.0"})
    assert result["error"] is None
    content = (mem / "CHANGELOG.md").read_text()
    assert "v1.1.0" in content
    assert "Fix auth bug" in content


def test_add_with_scope(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"description": "Refactor routes", "change_type": "refactor", "scope": "webapp"})
    content = (mem / "CHANGELOG.md").read_text()
    assert "webapp" in content


def test_invalid_change_type():
    handler = load_handler()
    result = handler.run({"description": "something", "change_type": "bogus"})
    assert result["error"] is not None
    assert "change_type" in result["error"].lower() or "bogus" in result["error"]


def test_missing_description():
    handler = load_handler()
    result = handler.run({"change_type": "feat"})
    assert result["error"] is not None


def test_missing_change_type():
    handler = load_handler()
    result = handler.run({"description": "something"})
    assert result["error"] is not None


def test_multiple_entries_accumulate(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"description": "First change", "change_type": "feat"})
        handler.run({"description": "Second change", "change_type": "fix"})
    content = (mem / "CHANGELOG.md").read_text()
    assert "First change" in content
    assert "Second change" in content


def test_emoji_in_entry(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"description": "New connector", "change_type": "feat"})
    content = (mem / "CHANGELOG.md").read_text()
    assert "✨" in content
