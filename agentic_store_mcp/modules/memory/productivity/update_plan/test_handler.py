"""Tests for update_plan."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("update_plan_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patches(tmp_path):
    mem = tmp_path / "memory"
    return {
        "MEMORY_DIR": mem,
        "_SESSION_FILE": mem / "session.jsonl",
    }


def test_write_plan(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({"content": "# My Plan\n\n- Step 1\n"})
    assert result["error"] is None
    assert result["result"]["status"] == "updated"
    assert (mem / "plan.md").read_text().startswith("# My Plan")


def test_append_plan(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        handler.run({"content": "# Plan\n"})
        result = handler.run({"content": "## Phase 2\n", "append": True})
    assert result["error"] is None
    content = (mem / "plan.md").read_text()
    assert "# Plan" in content
    assert "## Phase 2" in content


def test_missing_content():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None
