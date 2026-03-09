"""Tests for configure tool."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("configure_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_list_empty():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.list_tokens", return_value=[]):
        result = handler.run({"action": "list"})
    assert result["error"] is None
    assert result["result"]["services"] == []
    assert result["result"]["count"] == 0


def test_set_and_get():
    handler = load_handler()
    stored = {}

    def fake_set(service, token):
        stored[service] = token

    def fake_get(service):
        return stored.get(service)

    with patch("agentic_store_mcp.secrets.set_token", side_effect=fake_set), \
         patch("agentic_store_mcp.secrets.get_token", side_effect=fake_get):

        result = handler.run({"action": "set", "service": "github_token", "token": "ghp_test123"})
        assert result["error"] is None
        assert result["result"]["status"] == "saved"

        result = handler.run({"action": "get", "service": "github_token"})
        assert result["error"] is None
        assert result["result"]["found"] is True
        assert result["result"]["value"] == "ghp_test123"


def test_get_missing():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.get_token", return_value=None):
        result = handler.run({"action": "get", "service": "nonexistent"})
    assert result["error"] is None
    assert result["result"]["found"] is False


def test_remove():
    removed = []
    with patch("agentic_store_mcp.secrets.remove_token", side_effect=removed.append):
        handler = load_handler()
        result = handler.run({"action": "remove", "service": "github_token"})
    assert result["error"] is None
    assert result["result"]["status"] == "removed"
    assert "github_token" in removed


def test_invalid_action():
    handler = load_handler()
    result = handler.run({"action": "explode"})
    assert result["error"] is not None
    assert result["result"] is None


def test_set_missing_token():
    handler = load_handler()
    result = handler.run({"action": "set", "service": "github_token"})
    assert result["error"] is not None


def test_set_missing_service():
    handler = load_handler()
    result = handler.run({"action": "get"})
    assert result["error"] is not None
