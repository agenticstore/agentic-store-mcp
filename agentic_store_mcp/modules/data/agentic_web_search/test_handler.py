"""Tests for agentic_web_search handler. Zero network calls — SearXNG API mocked."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_spec = importlib.util.spec_from_file_location(
    "agentic_web_search_handler", Path(__file__).parent / "handler.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
run = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_RESULTS = [
    {
        "title": "AgenticStore MCP Tools",
        "url": "https://github.com/agenticstore/agentic-store-mcp",
        "content": "Free, open-source MCP tools for AI agents.",
        "engine": "google",
    },
    {
        "title": "Model Context Protocol",
        "url": "https://modelcontextprotocol.io",
        "content": "The open protocol for AI tool integration.",
        "engine": "bing",
    },
]


def _mock_searxng(results: list | None = None, status: int = 200):
    """Patch urllib.request.urlopen to return a fake SearXNG JSON response."""
    payload = json.dumps({"results": _SAMPLE_RESULTS if results is None else results}).encode()
    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", return_value=resp)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestRunValidation(unittest.TestCase):

    def test_missing_query(self):
        out = run({})
        self.assertIsNotNone(out["error"])
        self.assertIn("query", out["error"])

    def test_empty_query(self):
        out = run({"query": "   "})
        self.assertIsNotNone(out["error"])
        self.assertIn("query", out["error"])

    def test_invalid_max_results(self):
        out = run({"query": "test", "max_results": "not_a_number"})
        self.assertIsNotNone(out["error"])

    def test_max_results_clamped_high(self):
        with _mock_searxng():
            out = run({"query": "test", "max_results": 9999})
        self.assertIsNone(out["error"])
        # max_results is clamped at 50 — results in fixture are 2, so just check no error
        self.assertIsNotNone(out["result"])

    def test_max_results_clamped_low(self):
        with _mock_searxng():
            out = run({"query": "test", "max_results": -5})
        self.assertIsNone(out["error"])


# ---------------------------------------------------------------------------
# Successful search
# ---------------------------------------------------------------------------

class TestRunSuccess(unittest.TestCase):

    def _run(self, **kwargs):
        with _mock_searxng():
            return run({"query": "mcp tools", **kwargs})

    def test_no_error(self):
        out = self._run()
        self.assertIsNone(out["error"])

    def test_result_has_query(self):
        out = self._run()
        self.assertEqual(out["result"]["query"], "mcp tools")

    def test_result_has_results_list(self):
        out = self._run()
        self.assertIsInstance(out["result"]["results"], list)

    def test_result_count(self):
        out = self._run()
        self.assertEqual(len(out["result"]["results"]), 2)

    def test_result_fields(self):
        out = self._run()
        r = out["result"]["results"][0]
        self.assertIn("title", r)
        self.assertIn("url", r)
        self.assertIn("snippet", r)
        self.assertIn("engine", r)

    def test_result_values(self):
        out = self._run()
        r = out["result"]["results"][0]
        self.assertEqual(r["title"], "AgenticStore MCP Tools")
        self.assertEqual(r["url"], "https://github.com/agenticstore/agentic-store-mcp")
        self.assertEqual(r["snippet"], "Free, open-source MCP tools for AI agents.")
        self.assertEqual(r["engine"], "google")

    def test_total_results(self):
        out = self._run()
        self.assertEqual(out["result"]["total_results"], 2)

    def test_categories_default(self):
        out = self._run()
        self.assertEqual(out["result"]["categories"], "general")

    def test_categories_custom(self):
        out = self._run(categories="news")
        self.assertEqual(out["result"]["categories"], "news")

    def test_language_default(self):
        out = self._run()
        self.assertEqual(out["result"]["language"], "en")

    def test_language_custom(self):
        out = self._run(language="de")
        self.assertEqual(out["result"]["language"], "de")

    def test_max_results_respected(self):
        many = [{"title": f"Result {i}", "url": f"https://r{i}.com", "content": "", "engine": "g"} for i in range(20)]
        with _mock_searxng(results=many):
            out = run({"query": "test", "max_results": 5})
        self.assertEqual(len(out["result"]["results"]), 5)
        self.assertEqual(out["result"]["total_results"], 20)

    def test_empty_results_list(self):
        with _mock_searxng(results=[]):
            out = run({"query": "obscure query with no results"})
        self.assertIsNone(out["error"])
        self.assertEqual(out["result"]["results"], [])
        self.assertEqual(out["result"]["total_results"], 0)

    def test_missing_fields_in_result(self):
        """Handler should not crash if SearXNG omits optional fields."""
        sparse = [{"url": "https://example.com"}]
        with _mock_searxng(results=sparse):
            out = run({"query": "test"})
        self.assertIsNone(out["error"])
        r = out["result"]["results"][0]
        self.assertEqual(r["title"], "")
        self.assertEqual(r["snippet"], "")
        self.assertEqual(r["engine"], "")


# ---------------------------------------------------------------------------
# Network / SearXNG errors
# ---------------------------------------------------------------------------

class TestRunErrors(unittest.TestCase):

    def test_connection_refused(self):
        import urllib.error
        exc = urllib.error.URLError("[Errno 111] Connection refused")
        with patch("urllib.request.urlopen", side_effect=exc):
            out = run({"query": "test"})
        self.assertIsNotNone(out["error"])
        self.assertIn("Cannot reach SearXNG", out["error"])

    def test_http_400_json_format_hint(self):
        import urllib.error
        exc = urllib.error.HTTPError("http://localhost:8080/search", 400, "Bad Request", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            out = run({"query": "test"})
        self.assertIsNotNone(out["error"])
        self.assertIn("400", out["error"])
        self.assertIn("json", out["error"].lower())

    def test_http_500(self):
        import urllib.error
        exc = urllib.error.HTTPError("http://localhost:8080/search", 500, "Internal Server Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            out = run({"query": "test"})
        self.assertIsNotNone(out["error"])
        self.assertIn("500", out["error"])

    def test_timeout(self):
        import socket
        with patch("urllib.request.urlopen", side_effect=socket.timeout()):
            out = run({"query": "test"})
        self.assertIsNotNone(out["error"])
        self.assertIn("timed out", out["error"])

    def test_non_json_response(self):
        resp = MagicMock()
        resp.read.return_value = b"<html>Not JSON</html>"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp):
            out = run({"query": "test"})
        self.assertIsNotNone(out["error"])
        self.assertIn("non-JSON", out["error"])

    def test_custom_searxng_url_used(self):
        """SEARXNG_URL env var should override the default base URL."""
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            raise urllib.error.URLError("connection refused")

        import urllib.error
        import os
        with patch.dict(os.environ, {"SEARXNG_URL": "http://custom-host:9090"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                run({"query": "test"})

        self.assertTrue(captured[0].startswith("http://custom-host:9090"))


if __name__ == "__main__":
    unittest.main()
