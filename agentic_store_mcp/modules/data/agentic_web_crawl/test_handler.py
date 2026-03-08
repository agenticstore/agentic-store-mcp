"""Tests for agentic_web_crawl handler. Zero network calls — all HTTP mocked."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_spec = importlib.util.spec_from_file_location("agentic_web_crawl_handler", Path(__file__).parent / "handler.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
_ContentParser = _mod._ContentParser
_detect_encoding = _mod._detect_encoding
run = _mod.run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "https://example.com"


def _make_response(body: bytes, url: str = _BASE, status: int = 200):
    resp = MagicMock()
    resp.status = status
    resp.url = url
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_fetch(html: str, url: str = _BASE, encoding: str = "utf-8"):
    body = html.encode(encoding)
    return patch(
        "urllib.request.urlopen",
        return_value=_make_response(body, url),
    )


# ---------------------------------------------------------------------------
# _ContentParser unit tests
# ---------------------------------------------------------------------------

class TestContentParser(unittest.TestCase):

    def _parse(self, html: str, base: str = _BASE) -> _ContentParser:
        p = _ContentParser(base)
        p.feed(html)
        p.finalize()
        return p

    def test_extracts_title(self):
        p = self._parse("<html><head><title>Hello World</title></head></html>")
        self.assertEqual(p.title, "Hello World")

    def test_title_stripped(self):
        p = self._parse("<title>  Padded  </title>")
        self.assertEqual(p.title, "Padded")

    def test_extracts_meta_description(self):
        p = self._parse('<meta name="description" content="A great page.">')
        self.assertEqual(p.meta["description"], "A great page.")

    def test_extracts_og_title(self):
        p = self._parse('<meta property="og:title" content="OG Title">')
        self.assertEqual(p.meta["og:title"], "OG Title")

    def test_extracts_canonical(self):
        p = self._parse('<link rel="canonical" href="https://example.com/canonical">')
        self.assertEqual(p.canonical, "https://example.com/canonical")

    def test_extracts_robots(self):
        p = self._parse('<meta name="robots" content="noindex, nofollow">')
        self.assertEqual(p.meta["robots"], "noindex, nofollow")

    def test_extracts_twitter_card(self):
        p = self._parse('<meta name="twitter:card" content="summary_large_image">')
        self.assertEqual(p.meta["twitter:card"], "summary_large_image")

    def test_extracts_og_type(self):
        p = self._parse('<meta property="og:type" content="article">')
        self.assertEqual(p.meta["og:type"], "article")

    def test_extracts_headings(self):
        p = self._parse("<h1>Top</h1><h2>Sub</h2><h3>Third</h3>")
        self.assertEqual(len(p.headings), 3)
        self.assertEqual(p.headings[0], {"level": "h1", "text": "Top"})
        self.assertEqual(p.headings[1], {"level": "h2", "text": "Sub"})
        self.assertEqual(p.headings[2], {"level": "h3", "text": "Third"})

    def test_extracts_links(self):
        p = self._parse('<a href="/about">About</a>', base="https://example.com")
        self.assertEqual(len(p.links), 1)
        self.assertEqual(p.links[0]["url"], "https://example.com/about")
        self.assertEqual(p.links[0]["text"], "About")

    def test_link_absolute_url_preserved(self):
        p = self._parse('<a href="https://other.com/page">Other</a>')
        self.assertEqual(p.links[0]["url"], "https://other.com/page")

    def test_link_fragment_skipped(self):
        p = self._parse('<a href="#section">Jump</a>')
        self.assertEqual(len(p.links), 0)

    def test_link_javascript_skipped(self):
        p = self._parse('<a href="javascript:void(0)">Click</a>')
        self.assertEqual(len(p.links), 0)

    def test_link_breakdown_internal_external(self):
        html = '<a href="/page">Internal</a><a href="https://other.com">External</a>'
        p = self._parse(html, base="https://example.com")
        breakdown = p.link_breakdown()
        self.assertEqual(breakdown["internal"], 1)
        self.assertEqual(breakdown["external"], 1)

    def test_extracts_images(self):
        p = self._parse('<img src="/logo.png" alt="Logo">')
        self.assertEqual(len(p.images), 1)
        self.assertEqual(p.images[0]["src"], "https://example.com/logo.png")
        self.assertEqual(p.images[0]["alt"], "Logo")

    def test_image_no_alt(self):
        p = self._parse('<img src="/pic.jpg">')
        self.assertEqual(p.images[0]["alt"], "")

    def test_script_content_excluded(self):
        p = self._parse("<script>var x = 'secret';</script><p>Visible</p>")
        text = p.plain_text()
        self.assertNotIn("secret", text)
        self.assertIn("Visible", text)

    def test_style_content_excluded(self):
        p = self._parse("<style>.foo { color: red; }</style><p>Text</p>")
        text = p.plain_text()
        self.assertNotIn("color", text)

    def test_nested_skip_tags(self):
        """Nested script inside noscript — both skipped."""
        p = self._parse("<noscript><script>alert(1)</script></noscript><p>OK</p>")
        self.assertNotIn("alert", p.plain_text())
        self.assertIn("OK", p.plain_text())

    def test_plain_text_collapses_blank_lines(self):
        p = self._parse("<p>A</p><p></p><p></p><p>B</p>")
        lines = [ln for ln in p.plain_text().splitlines() if ln]
        self.assertIn("A", lines)
        self.assertIn("B", lines)
        self.assertNotIn("\n\n\n", p.plain_text())

    def test_no_collecting_key_in_finalized_links(self):
        p = self._parse('<a href="/x">X</a>')
        for link in p.links:
            self.assertNotIn("_collecting", link)


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

class TestDetectEncoding(unittest.TestCase):

    def test_content_type_charset(self):
        body = b"<html></html>"
        enc = _detect_encoding(body, "text/html; charset=iso-8859-1")
        self.assertEqual(enc.lower(), "iso-8859-1")

    def test_html_meta_charset(self):
        body = b'<meta charset="windows-1252"><html></html>'
        enc = _detect_encoding(body, "text/html")
        self.assertEqual(enc.lower(), "windows-1252")

    def test_fallback_utf8(self):
        body = b"<html></html>"
        enc = _detect_encoding(body, "text/html")
        self.assertEqual(enc, "utf-8")


# ---------------------------------------------------------------------------
# run() — input validation
# ---------------------------------------------------------------------------

class TestRunValidation(unittest.TestCase):

    def test_missing_url(self):
        out = run({})
        self.assertIsNotNone(out["error"])
        self.assertIn("url", out["error"])

    def test_empty_url(self):
        out = run({"url": "   "})
        self.assertIsNotNone(out["error"])

    def test_unsupported_scheme(self):
        out = run({"url": "ftp://example.com/file"})
        self.assertIsNotNone(out["error"])
        self.assertIn("ftp", out["error"])

    def test_unknown_extract_value(self):
        out = run({"url": "https://example.com", "extract": "text,badkey"})
        self.assertIsNotNone(out["error"])
        self.assertIn("badkey", out["error"])

    def test_valid_extract_subset(self):
        html = b"<title>T</title><p>Hi</p>"
        with patch("urllib.request.urlopen", return_value=_make_response(html)):
            out = run({"url": "https://example.com", "extract": "text"})
        self.assertIsNone(out["error"])
        self.assertIn("text", out["result"])
        self.assertNotIn("links", out["result"])
        self.assertNotIn("images", out["result"])
        self.assertNotIn("metadata", out["result"])


# ---------------------------------------------------------------------------
# run() — successful fetch
# ---------------------------------------------------------------------------

class TestRunSuccess(unittest.TestCase):

    _HTML = b"""
    <html>
    <head>
      <title>Test Page</title>
      <meta name="description" content="A test description.">
      <meta name="robots" content="index, follow">
      <meta name="keywords" content="python, mcp, agents">
      <meta property="og:title" content="OG Test">
      <meta property="og:type" content="article">
      <meta property="og:url" content="https://example.com/test">
      <meta name="twitter:card" content="summary">
      <meta name="twitter:title" content="Twitter Test">
      <link rel="canonical" href="https://example.com/canonical">
    </head>
    <body>
      <h1>Main Heading</h1>
      <p>Hello, world!</p>
      <a href="/page1">Page One</a>
      <a href="https://external.com">External</a>
      <img src="/img/logo.png" alt="Logo">
      <script>console.log('ignored');</script>
    </body>
    </html>
    """

    def _run_all(self, **kwargs):
        with patch("urllib.request.urlopen", return_value=_make_response(self._HTML)):
            return run({"url": "https://example.com", **kwargs})

    def test_no_error(self):
        out = self._run_all()
        self.assertIsNone(out["error"])

    def test_title(self):
        out = self._run_all()
        self.assertEqual(out["result"]["title"], "Test Page")

    def test_url_in_result(self):
        out = self._run_all()
        self.assertEqual(out["result"]["url"], "https://example.com")

    def test_text_contains_heading(self):
        out = self._run_all()
        self.assertIn("Main Heading", out["result"]["text"])

    def test_text_contains_paragraph(self):
        out = self._run_all()
        self.assertIn("Hello, world!", out["result"]["text"])

    def test_script_not_in_text(self):
        out = self._run_all()
        self.assertNotIn("ignored", out["result"]["text"])

    # SEO metadata fields
    def test_metadata_description(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["description"], "A test description.")

    def test_metadata_canonical(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["canonical"], "https://example.com/canonical")

    def test_metadata_robots(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["robots"], "index, follow")

    def test_metadata_keywords(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["keywords"], "python, mcp, agents")

    def test_metadata_og_title(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["og_title"], "OG Test")

    def test_metadata_og_type(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["og_type"], "article")

    def test_metadata_og_url(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["og_url"], "https://example.com/test")

    def test_metadata_twitter_card(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["twitter_card"], "summary")

    def test_metadata_twitter_title(self):
        out = self._run_all()
        self.assertEqual(out["result"]["metadata"]["twitter_title"], "Twitter Test")

    def test_metadata_word_count(self):
        out = self._run_all()
        self.assertGreater(out["result"]["metadata"]["word_count"], 0)

    def test_metadata_link_breakdown(self):
        out = self._run_all()
        breakdown = out["result"]["metadata"]["link_breakdown"]
        self.assertEqual(breakdown["internal"], 1)
        self.assertEqual(breakdown["external"], 1)

    def test_metadata_headings(self):
        out = self._run_all()
        headings = out["result"]["metadata"]["headings"]
        self.assertEqual(headings[0], {"level": "h1", "text": "Main Heading"})

    def test_links_count(self):
        out = self._run_all()
        self.assertEqual(out["result"]["links_count"], 2)

    def test_links_absolute(self):
        out = self._run_all()
        urls = [ln["url"] for ln in out["result"]["links"]]
        self.assertIn("https://example.com/page1", urls)
        self.assertIn("https://external.com", urls)

    def test_images(self):
        out = self._run_all()
        self.assertEqual(len(out["result"]["images"]), 1)
        self.assertEqual(out["result"]["images"][0]["src"], "https://example.com/img/logo.png")
        self.assertEqual(out["result"]["images"][0]["alt"], "Logo")

    def test_max_links_respected(self):
        """Build HTML with 10 links, cap at 3."""
        links_html = "".join(f'<a href="/p{i}">P{i}</a>' for i in range(10))
        html = f"<html><body>{links_html}</body></html>".encode()
        with patch("urllib.request.urlopen", return_value=_make_response(html)):
            out = run({"url": "https://example.com", "max_links": 3})
        self.assertEqual(len(out["result"]["links"]), 3)
        self.assertEqual(out["result"]["links_count"], 10)

    def test_max_images_respected(self):
        imgs_html = "".join(f'<img src="/i{i}.png">' for i in range(10))
        html = f"<html><body>{imgs_html}</body></html>".encode()
        with patch("urllib.request.urlopen", return_value=_make_response(html)):
            out = run({"url": "https://example.com", "max_images": 4})
        self.assertEqual(len(out["result"]["images"]), 4)
        self.assertEqual(out["result"]["images_count"], 10)


# ---------------------------------------------------------------------------
# run() — network errors
# ---------------------------------------------------------------------------

class TestRunErrors(unittest.TestCase):

    def test_http_error_404(self):
        import urllib.error
        exc = urllib.error.HTTPError("https://example.com", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            out = run({"url": "https://example.com"})
        self.assertIsNotNone(out["error"])
        self.assertIn("404", out["error"])

    def test_url_error(self):
        import urllib.error
        exc = urllib.error.URLError("Name or service not known")
        with patch("urllib.request.urlopen", side_effect=exc):
            out = run({"url": "https://doesnotexist.invalid"})
        self.assertIsNotNone(out["error"])

    def test_timeout(self):
        import socket
        with patch("urllib.request.urlopen", side_effect=socket.timeout()):
            out = run({"url": "https://example.com", "timeout": 1})
        self.assertIsNotNone(out["error"])
        self.assertIn("timed out", out["error"])

    def test_final_url_used(self):
        """If the server redirects, the result URL should be the final URL."""
        html = b"<title>Redirected</title>"
        resp = _make_response(html, url="https://example.com/final")
        with patch("urllib.request.urlopen", return_value=resp):
            out = run({"url": "https://example.com/original"})
        self.assertEqual(out["result"]["url"], "https://example.com/final")


# ---------------------------------------------------------------------------
# run() — extract=all default
# ---------------------------------------------------------------------------

class TestRunExtractAll(unittest.TestCase):

    def test_all_keys_present(self):
        html = b"<html><head><title>T</title></head><body><p>Body</p></body></html>"
        with patch("urllib.request.urlopen", return_value=_make_response(html)):
            out = run({"url": "https://example.com"})
        result = out["result"]
        for key in ("text", "links", "images", "metadata"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_extract_metadata_only(self):
        html = b"<html><head><title>T</title></head><body><p>Body</p></body></html>"
        with patch("urllib.request.urlopen", return_value=_make_response(html)):
            out = run({"url": "https://example.com", "extract": "metadata"})
        result = out["result"]
        self.assertIn("metadata", result)
        self.assertNotIn("text", result)
        self.assertNotIn("links", result)
        self.assertNotIn("images", result)


if __name__ == "__main__":
    unittest.main()
