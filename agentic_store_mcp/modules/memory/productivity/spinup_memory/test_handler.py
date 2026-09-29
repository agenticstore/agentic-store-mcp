"""Tests for spinup_memory."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("spinup_memory_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mem_patches(tmp_path):
    mem = tmp_path / "memory"
    cp = mem / "checkpoints"
    return {
        "MEMORY_DIR": mem,
        "_FACTS_FILE": mem / "facts.json",
        "_SESSION_FILE": mem / "session.jsonl",
        "_STRATEGY_FILE": mem / "strategy.md",
        "_CHECKPOINTS_DIR": cp,
    }


def test_basic_init(tmp_path):
    handler = load_handler()
    with patch.multiple("agentic_store_mcp.memory_store", **_mem_patches(tmp_path)):
        result = handler.run({"project_name": "my-project"})
    assert result["error"] is None
    assert result["result"]["status"] == "initialized"
    assert result["result"]["project_name"] == "my-project"


def test_creates_files(tmp_path):
    handler = load_handler()
    patches = _mem_patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"project_name": "test", "stack": "Python"})
    assert (mem / "strategy.md").exists()
    assert (mem / "plan.md").exists()
    assert (mem / "milestones.md").exists()
    assert (mem / "learnings.md").exists()
    assert (mem / "CHANGELOG.md").exists()


def test_missing_project_name():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None
    assert "project_name" in result["error"]


def test_idempotent_without_reset(tmp_path):
    handler = load_handler()
    patches = _mem_patches(tmp_path)
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"project_name": "proj"})
        result = handler.run({"project_name": "proj"})
    assert result["result"]["status"] == "already_exists"


def test_reset_reinitializes(tmp_path):
    handler = load_handler()
    patches = _mem_patches(tmp_path)
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"project_name": "proj"})
        result = handler.run({"project_name": "proj", "reset": True})
    assert result["result"]["status"] == "initialized"
    assert result["result"]["reset"] is True
