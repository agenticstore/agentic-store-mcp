"""Tests for memory_search."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_search_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup_memory(tmp_path: Path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    cp_dir = mem_dir / "checkpoints"
    cp_dir.mkdir()

    # facts
    facts = {
        "project": {"key": "project", "value": "auth-service", "category": "facts", "created_at": "t", "updated_at": "t"},
    }
    (mem_dir / "facts.json").write_text(json.dumps(facts))

    # strategy
    (mem_dir / "strategy.md").write_text("Use JWT for auth tokens. Prefer short expiry.")

    # checkpoint
    (cp_dir / "auth-done.json").write_text(json.dumps({
        "name": "auth-done",
        "task": "Implemented JWT authentication",
        "timestamp": "2026-01-01T00:00:00Z",
    }))

    return mem_dir, mem_dir / "facts.json", mem_dir / "strategy.md", cp_dir


def test_search_finds_fact(tmp_path):
    handler = load_handler()
    mem_dir, facts_file, strategy_file, cp_dir = _setup_memory(tmp_path)
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file), \
         patch("agentic_store_mcp.memory_store._STRATEGY_FILE", strategy_file), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"query": "auth-service"})
    assert result["error"] is None
    sources = [r["source"] for r in result["result"]["results"]]
    assert "fact" in sources


def test_search_finds_strategy(tmp_path):
    handler = load_handler()
    mem_dir, facts_file, strategy_file, cp_dir = _setup_memory(tmp_path)
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file), \
         patch("agentic_store_mcp.memory_store._STRATEGY_FILE", strategy_file), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"query": "JWT"})
    assert result["error"] is None
    sources = [r["source"] for r in result["result"]["results"]]
    assert "strategy" in sources


def test_search_finds_checkpoint(tmp_path):
    handler = load_handler()
    mem_dir, facts_file, strategy_file, cp_dir = _setup_memory(tmp_path)
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file), \
         patch("agentic_store_mcp.memory_store._STRATEGY_FILE", strategy_file), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"query": "JWT authentication"})
    assert result["error"] is None
    sources = [r["source"] for r in result["result"]["results"]]
    assert "checkpoint" in sources


def test_search_no_match(tmp_path):
    handler = load_handler()
    mem_dir, facts_file, strategy_file, cp_dir = _setup_memory(tmp_path)
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file), \
         patch("agentic_store_mcp.memory_store._STRATEGY_FILE", strategy_file), \
         patch("agentic_store_mcp.memory_store._CHECKPOINTS_DIR", cp_dir):
        result = handler.run({"query": "zzz_no_match_xyz"})
    assert result["error"] is None
    assert result["result"]["total"] == 0


def test_search_missing_query():
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is not None
