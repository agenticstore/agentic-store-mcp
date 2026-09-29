"""Tests for memory_write."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_write_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_write_basic(tmp_path):
    handler = load_handler()
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path / "memory"), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", tmp_path / "memory" / "facts.json"):
        result = handler.run({"key": "lang", "value": "python"})
    assert result["error"] is None
    assert result["result"]["status"] == "written"
    assert result["result"]["key"] == "lang"


def test_write_missing_key():
    handler = load_handler()
    result = handler.run({"value": "oops"})
    assert result["error"] is not None
    assert "key" in result["error"]


def test_write_missing_value():
    handler = load_handler()
    result = handler.run({"key": "k"})
    assert result["error"] is not None
    assert "value" in result["error"]


def test_write_with_category(tmp_path):
    handler = load_handler()
    mem_dir = tmp_path / "memory"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", mem_dir), \
         patch("agentic_store_mcp.memory_store._FACTS_FILE", mem_dir / "facts.json"):
        result = handler.run({"key": "style", "value": "concise", "category": "preferences"})
    assert result["error"] is None
    assert result["result"]["category"] == "preferences"
