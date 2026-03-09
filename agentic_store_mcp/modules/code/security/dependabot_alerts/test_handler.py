"""Tests for dependabot_alerts."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("dependabot_alerts_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_pygithub(monkeypatch):
    handler = load_handler()
    monkeypatch.setattr(handler, "_HAS_PYGITHUB", False)
    result = handler.run({"repo": "owner/repo"})
    assert result["error"] is not None


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


def _make_alert(number, state, severity, cve_id, pkg_name, ecosystem, vuln_range, fixed_in, html_url):
    alert = MagicMock()
    alert.number = number
    alert.state = state
    alert.html_url = html_url
    alert.created_at = MagicMock()
    alert.created_at.__str__ = lambda s: "2026-01-15 10:00:00"
    alert.dismissed_at = None

    adv = MagicMock()
    adv.severity = severity
    adv.cve_id = cve_id
    adv.ghsa_id = f"GHSA-test-{number:04d}"
    adv.summary = f"Test vulnerability {number}"
    alert.security_advisory = adv

    vuln = MagicMock()
    pkg = MagicMock()
    pkg.name = pkg_name
    pkg.ecosystem = ecosystem
    vuln.package = pkg
    vuln.vulnerable_version_range = vuln_range
    vuln.first_patched_version = fixed_in
    alert.security_vulnerability = vuln

    return alert


def test_returns_alerts():
    handler = load_handler()

    alert1 = _make_alert(1, "open", "high", "CVE-2024-0001", "requests", "pip", "<2.28.0", "2.28.0", "https://gh.com/1")
    alert2 = _make_alert(2, "open", "medium", None, "lodash", "npm", "<4.17.21", "4.17.21", "https://gh.com/2")

    mock_repo = MagicMock()
    mock_repo.get_dependabot_alerts.return_value = [alert1, alert2]

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo"})

    assert result["error"] is None
    assert result["result"]["total"] == 2
    assert result["result"]["token_used"] is True
    assert "high" in result["result"]["summary"]


def test_severity_filter():
    handler = load_handler()

    alert_high = _make_alert(1, "open", "high", "CVE-2024-0001", "pkg", "pip", "<1.0", "1.0", "https://gh.com/1")
    alert_low = _make_alert(2, "open", "low", None, "other", "npm", "<2.0", "2.0", "https://gh.com/2")

    mock_repo = MagicMock()
    mock_repo.get_dependabot_alerts.return_value = [alert_high, alert_low]
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo", "severity": "high"})

    assert result["error"] is None
    # Only high severity should be returned (low filtered out)
    assert result["result"]["total"] == 1
    assert result["result"]["alerts"][0]["severity"] == "high"


def test_403_error():
    from github import GithubException
    handler = load_handler()

    mock_repo = MagicMock()
    mock_repo.get_dependabot_alerts.side_effect = GithubException(403, {"message": "Forbidden"}, {})
    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    mock_constructor = MagicMock(return_value=mock_g)
    with patch("agentic_store_mcp.secrets.get_token", return_value="ghp_test"), \
         patch.object(handler, "Github", mock_constructor):
        result = handler.run({"repo": "owner/repo"})

    assert result["error"] is not None
    assert "403" in result["error"] or "Access denied" in result["error"]
