"""Tests for memory_log."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("memory_log_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_append_basic(tmp_path):
    handler = load_handler()
    session_file = tmp_path / "session.jsonl"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._SESSION_FILE", session_file):
        result = handler.run({"mode": "append", "event": "file_edited", "detail": "server.py"})
    assert result["error"] is None
    assert result["result"]["status"] == "logged"
    assert session_file.exists()


def test_append_missing_event():
    handler = load_handler()
    result = handler.run({"mode": "append"})
    assert result["error"] is not None


def test_read_empty(tmp_path):
    handler = load_handler()
    session_file = tmp_path / "session.jsonl"
    with patch("agentic_store_mcp.memory_store._SESSION_FILE", session_file):
        result = handler.run({"mode": "read"})
    assert result["error"] is None
    assert result["result"]["total"] == 0


def test_append_then_read(tmp_path):
    handler = load_handler()
    session_file = tmp_path / "session.jsonl"
    with patch("agentic_store_mcp.memory_store.MEMORY_DIR", tmp_path), \
         patch("agentic_store_mcp.memory_store._SESSION_FILE", session_file):
        handler.run({"mode": "append", "event": "start"})
        handler.run({"mode": "append", "event": "end"})
        result = handler.run({"mode": "read", "limit": 10})
    assert result["error"] is None
    assert result["result"]["total"] == 2
    assert result["result"]["entries"][0]["event"] == "start"


def test_invalid_mode():
    handler = load_handler()
    result = handler.run({"mode": "badmode"})
    assert result["error"] is not None
