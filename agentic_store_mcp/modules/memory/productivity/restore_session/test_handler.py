"""Tests for restore_session."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("restore_session_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    cp_dir = mem / "checkpoints"
    cp_dir.mkdir()

    facts = {
        "project_name": {"key": "project_name", "value": "test-proj", "category": "project",
                          "created_at": "t", "updated_at": "t"},
    }
    (mem / "facts.json").write_text(json.dumps(facts))
    (mem / "plan.md").write_text("# Plan\n\n- Phase 1\n")
    (mem / "milestones.md").write_text("# Milestones\n\n| M1 | COMPLETE |\n")
    (mem / "learnings.md").write_text("# Learnings\n\n## [arch] 2026-01-01\nUse UTC always.\n")
    (mem / "CHANGELOG.md").write_text("# Changelog\n\n## v1.0\n- feat: init\n")
    (mem / "session.jsonl").write_text("")

    cp = {"name": "my-cp", "task": "Build auth", "next_steps": ["Write tests"], "timestamp": "2026-01-01T00:00:00Z"}
    (cp_dir / "my-cp.json").write_text(json.dumps(cp))

    return mem, cp_dir


def _patches(mem, cp_dir):
    return {
        "MEMORY_DIR": mem,
        "_FACTS_FILE": mem / "facts.json",
        "_SESSION_FILE": mem / "session.jsonl",
        "_STRATEGY_FILE": mem / "strategy.md",
        "_CHECKPOINTS_DIR": cp_dir,
    }


def test_restore_all_sections(tmp_path):
    handler = load_handler()
    mem, cp_dir = _setup(tmp_path)
    with patch.multiple("agentic_store_mcp.memory_store", **_patches(mem, cp_dir)):
        result = handler.run({"checkpoint": "my-cp"})
    assert result["error"] is None
    ctx = result["result"]["context"]
    assert ctx["checkpoint"]["task"] == "Build auth"
    assert ctx["plan"] is not None
    assert ctx["milestones"] is not None
    assert "project_name" in ctx["facts"]


def test_restore_subset(tmp_path):
    handler = load_handler()
    mem, cp_dir = _setup(tmp_path)
    with patch.multiple("agentic_store_mcp.memory_store", **_patches(mem, cp_dir)):
        result = handler.run({"checkpoint": "my-cp", "include": ["checkpoint", "facts"]})
    assert result["error"] is None
    ctx = result["result"]["context"]
    assert "checkpoint" in ctx
    assert "facts" in ctx
    assert "plan" not in ctx
    assert "milestones" not in ctx


def test_invalid_include():
    handler = load_handler()
    result = handler.run({"include": ["bogus"]})
    assert result["error"] is not None
    assert "bogus" in result["error"]


def test_summary_fields(tmp_path):
    handler = load_handler()
    mem, cp_dir = _setup(tmp_path)
    with patch.multiple("agentic_store_mcp.memory_store", **_patches(mem, cp_dir)):
        result = handler.run({"checkpoint": "my-cp"})
    summary = result["result"]["summary"]
    assert summary["task"] == "Build auth"
    assert summary["next_steps"] == ["Write tests"]
