"""Tests for update_milestones."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("update_milestones_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patches(tmp_path):
    mem = tmp_path / "memory"
    return {
        "MEMORY_DIR": mem,
        "_SESSION_FILE": mem / "session.jsonl",
    }


_TABLE_CONTENT = """\
# Milestones

| Milestone | Status |
|---|---|
| M1 Foundation | NOT STARTED |
| M2 GitHub Tools | NOT STARTED |
"""


def test_full_replace(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        result = handler.run({"content": _TABLE_CONTENT})
    assert result["error"] is None
    assert result["result"]["mode"] == "replace"
    assert "M1" in (mem / "milestones.md").read_text()


def test_inline_table_update(tmp_path):
    handler = load_handler()
    patches = _patches(tmp_path)
    mem = patches["MEMORY_DIR"]
    with patch.multiple("agentic_store_mcp.memory_store", **patches):
        (mem).mkdir(parents=True, exist_ok=True)
        (mem / "milestones.md").write_text(_TABLE_CONTENT)
        (mem / "session.jsonl").touch()
        result = handler.run({"milestone": "M1 Foundation", "status": "COMPLETE ✓"})
    assert result["error"] is None
    content = (mem / "milestones.md").read_text()
    assert "COMPLETE" in content


def test_missing_params():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None


def test_milestone_without_status(tmp_path):
    handler = load_handler()
    result = handler.run({"milestone": "M1"})
    assert result["error"] is not None
    assert "status" in result["error"]
