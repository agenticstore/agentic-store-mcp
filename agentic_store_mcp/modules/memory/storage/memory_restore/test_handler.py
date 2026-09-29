"""Tests for memory_restore."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_restore_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_checkpoint(cp_dir: Path, name: str, task: str) -> Path:
    cp_dir.mkdir(parents=True, exist_ok=True)
    path = cp_dir / f"{name}.json"
    path.write_text(json.dumps({"name": name, "task": task, "timestamp": "2026-01-01T00:00:00Z"}))
    return path


def test_restore_by_name(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    _make_checkpoint(cp_dir, "my-cp", "Write tests")
    with patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"name": "my-cp"})
    assert result["error"] is None
    assert result["result"]["checkpoint"]["task"] == "Write tests"


def test_restore_latest(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    _make_checkpoint(cp_dir, "first", "First task")
    _make_checkpoint(cp_dir, "second", "Second task")
    with patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"name": "latest"})
    assert result["error"] is None
    # latest = most recently written = second
    assert result["result"]["checkpoint"]["task"] == "Second task"


def test_restore_missing():
    handler = load_handler()
    result = handler.run({"name": "ghost"})
    assert result["error"] is not None


def test_restore_missing_name():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None


def test_restore_latest_no_checkpoints(tmp_path):
    handler = load_handler()
    cp_dir = tmp_path / "checkpoints"
    with patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"name": "latest"})
    assert result["error"] is not None
    assert "No checkpoints" in result["error"]
