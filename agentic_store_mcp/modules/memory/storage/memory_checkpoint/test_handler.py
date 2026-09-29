"""Tests for memory_checkpoint."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_checkpoint_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_save_auto_name(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"task": "Implement auth module"})
    assert result["error"] is None
    assert result["result"]["status"] == "saved"
    assert result["result"]["name"].startswith("checkpoint_")


def test_save_named(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"task": "Auth done", "name": "auth-complete"})
    assert result["error"] is None
    assert result["result"]["name"] == "auth-complete"
    assert (cp_dir / "auth-complete.json").exists()


def test_missing_task():
    handler = load_handler()
    result = handler.run({"name": "my-cp"})
    assert result["error"] is not None
    assert "task" in result["error"]


def test_reserved_name_latest(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"task": "some task", "name": "latest"})
    assert result["error"] is not None
    assert "reserved" in result["error"]


def test_invalid_name_chars(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"task": "t", "name": "bad name!"})
    assert result["error"] is not None
