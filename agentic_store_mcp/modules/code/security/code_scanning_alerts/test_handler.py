"""Tests for code_scanning_alerts."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("code_scanning_alerts_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_token():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.get_token", return_value=None):
        result = handler.run({"repo": "owner/repo"})
    assert result["error"] is not None
    assert "token" in result["error"].lower()


def test_missing_repo():
    handler = load_handler()
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"):
        result = handler.run({})
    assert result["error"] is not None


def _make_alert(number, state, rule_id, rule_name, severity, tool_name, file_path, line):
    alert = MagicMock()
    alert.number = number
    alert.state = state
    alert.html_url = f"https://github.com/owner/repo/security/code-scanning/{number}"
    alert.created_at = MagicMock()
    alert.created_at.__str__ = lambda s: "2026-01-15 10:00:00"

    rule = MagicMock()
    rule.id = rule_id
    rule.name = rule_name
    rule.severity = severity
    rule.description = f"Description for {rule_name}"
    alert.rule = rule

    tool = MagicMock()
    tool.name = tool_name
    alert.tool = tool

    loc = MagicMock()
    loc.path = file_path
    loc.start_line = line
    loc.end_line = line + 2
    instance = MagicMock()
    instance.location = loc
    alert.most_recent_instance = instance

    return alert


def test_returns_alerts():
    handler = load_handler()

    alert1 = _make_alert(1, "open", "js/sqli", "SQL Injection", "error", "CodeQL", "src/db.js", 42)
    alert2 = _make_alert(2, "open", "py/xss", "XSS", "warning", "CodeQL", "app/views.py", 10)

    mock_repo = MagicMock()
    mock_repo.get_codescan_alerts.return_value = [alert1, alert2]
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo"})

    assert result["error"] is None
    assert result["result"]["total"] == 2
    assert "CodeQL" in result["result"]["summary"]["by_tool"]


def test_tool_filter():
    handler = load_handler()

    alert_codeql = _make_alert(1, "open", "py/sqli", "SQLi", "error", "CodeQL", "app.py", 5)
    alert_semgrep = _make_alert(2, "open", "xss", "XSS", "warning", "Semgrep", "views.py", 12)

    mock_repo = MagicMock()
    mock_repo.get_codescan_alerts.return_value = [alert_codeql, alert_semgrep]
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "tool_name": "CodeQL"})

    assert result["error"] is None
    assert result["result"]["total"] == 1
    assert result["result"]["alerts"][0]["tool"] == "CodeQL"


def test_state_filter():
    handler = load_handler()

    alert_open = _make_alert(1, "open", "r1", "Rule1", "error", "CodeQL", "f.py", 1)
    alert_dismissed = _make_alert(2, "dismissed", "r2", "Rule2", "warning", "CodeQL", "g.py", 2)

    mock_repo = MagicMock()
    mock_repo.get_codescan_alerts.return_value = [alert_open, alert_dismissed]
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "state": "open"})

    assert result["error"] is None
    assert result["result"]["total"] == 1
    assert result["result"]["alerts"][0]["state"] == "open"
