"""Tests for memory_read."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_read_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_facts(mem_dir: Path, data: dict):
    import json
    (mem_dir).mkdir(parents=True, exist_ok=True)
    (mem_dir / "facts.json").write_text(json.dumps(data))


def test_read_specific_key(tmp_path):
    handler = load_handler()
    mem_dir = tmp_path / "memory"
    facts_file = mem_dir / "facts.json"
    _write_facts(mem_dir, {
        "lang": {"key": "lang", "value": "python", "category": "facts", "created_at": "t", "updated_at": "t"}
    })
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file):
        result = handler.run({"key": "lang"})
    assert result["error"] is None
    assert result["result"]["value"] == "python"


def test_read_missing_key(tmp_path):
    handler = load_handler()
    mem_dir = tmp_path / "memory"
    facts_file = mem_dir / "facts.json"
    _write_facts(mem_dir, {})
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file):
        result = handler.run({"key": "nope"})
    assert result["error"] is not None


def test_read_all(tmp_path):
    handler = load_handler()
    mem_dir = tmp_path / "memory"
    facts_file = mem_dir / "facts.json"
    _write_facts(mem_dir, {
        "a": {"key": "a", "value": 1, "category": "facts", "created_at": "t", "updated_at": "t"},
        "b": {"key": "b", "value": 2, "category": "facts", "created_at": "t", "updated_at": "t"},
    })
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", facts_file):
        result = handler.run({})
    assert result["error"] is None
    assert result["result"]["total"] == 2
