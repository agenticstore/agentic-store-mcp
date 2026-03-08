"""
agentic_web_crawl — fetch a URL and extract a full SEO signal report.

Designed for AI agents doing SEO research, competitive analysis, and content audits.
Zero external dependencies — pure Python stdlib:
  urllib.request  — HTTP fetch
  html.parser     — HTML parsing
  urllib.parse    — URL resolution

SEO signals extracted:
  Title tag, meta description, canonical URL, robots directives
  Open Graph: og:title, og:description, og:image, og:type, og:url
  Twitter Card: twitter:card, twitter:title, twitter:description
  Keywords meta tag, heading hierarchy (h1–h6)
  Word count, internal vs external link breakdown
"""

from __future__ import annotations

import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------

_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "math"}
_BLOCK_TAGS = {
    "p", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
    "article", "section", "main", "header", "footer", "blockquote", "pre",
}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _ContentParser(HTMLParser):
    """Single-pass HTML parser that collects text, links, images, and SEO metadata."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._base_host = urllib.parse.urlsplit(base_url).netloc

        # Outputs
        self.title: str = ""
        self.canonical: str = ""
        self.meta: dict[str, str] = {}   # all <meta name/property> values keyed by name
        self.headings: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self._text_parts: list[str] = []

        # State
        self._skip_depth: int = 0
        self._current_tag: str = ""
        self._in_title: bool = False
        self._in_heading: str = ""
        self._heading_buf: list[str] = []

    # ------------------------------------------------------------------
    # HTMLParser callbacks
    # ------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)

        if self._skip_depth > 0:
            if tag in _SKIP_TAGS:
                self._skip_depth += 1
            return

        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return

        self._current_tag = tag

        if tag == "title":
            self._in_title = True

        elif tag in _HEADING_TAGS:
            self._in_heading = tag
            self._heading_buf = []

        elif tag == "meta":
            name = (attr.get("name") or attr.get("property") or "").lower()
            content = attr.get("content") or ""
            if name and content:
                self.meta[name] = content

        elif tag == "link":
            # Capture canonical URL from <link rel="canonical" href="...">
            if (attr.get("rel") or "").lower() == "canonical":
                self.canonical = (attr.get("href") or "").strip()

        elif tag == "a":
            href = (attr.get("href") or "").strip()
            if href and not href.startswith(("#", "javascript:")):
                abs_href = urllib.parse.urljoin(self.base_url, href)
                self.links.append({"url": abs_href, "text": "", "_collecting": True})

        elif tag == "img":
            src = attr.get("src") or ""
            if src:
                abs_src = urllib.parse.urljoin(self.base_url, src)
                alt = attr.get("alt") or ""
                self.images.append({"src": abs_src, "alt": alt})

        elif tag in _BLOCK_TAGS:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth > 0:
            if tag in _SKIP_TAGS:
                self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False

        elif tag in _HEADING_TAGS and self._in_heading == tag:
            text = "".join(self._heading_buf).strip()
            if text:
                self.headings.append({"level": tag, "text": text})
            self._in_heading = ""
            self._heading_buf = []
            self._text_parts.append("\n")

        elif tag in _BLOCK_TAGS:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return

        if self._in_title:
            self.title += data
            return

        if self._in_heading:
            self._heading_buf.append(data)

        # Append text to last open link
        if self.links and self.links[-1].get("_collecting"):
            self.links[-1]["text"] += data

        self._text_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        # HTMLParser in Python 3 converts entities automatically; safety net
        self.handle_data(f"&{name};")

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Strip whitespace and close any open collectors."""
        self.title = self.title.strip()
        for link in self.links:
            link.pop("_collecting", None)
            link["text"] = link["text"].strip()

    def plain_text(self) -> str:
        """Return body text with collapsed blank lines."""
        raw = "".join(self._text_parts)
        lines = [ln.rstrip() for ln in raw.splitlines()]
        cleaned: list[str] = []
        prev_blank = False
        for ln in lines:
            is_blank = not ln
            if is_blank and prev_blank:
                continue
            cleaned.append(ln)
            prev_blank = is_blank
        return "\n".join(cleaned).strip()

    def link_breakdown(self) -> dict[str, int]:
        """Return counts of internal vs external links based on host matching."""
        internal = external = 0
        for link in self.links:
            host = urllib.parse.urlsplit(link["url"]).netloc
            if host == self._base_host:
                internal += 1
            else:
                external += 1
        return {"internal": internal, "external": external}


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; AgenticStore/1.0; +https://github.com/agenticstore)"
)
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB hard cap


def _fetch(url: str, timeout: int) -> tuple[bytes, str]:
    """Return (body_bytes, final_url). Raises ValueError on non-2xx or timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": _DEFAULT_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status < 200 or resp.status >= 300:
                raise ValueError(f"HTTP {resp.status} for {url}")
            body = resp.read(_MAX_BYTES)
            final_url = resp.url or url
        return body, final_url
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Request failed: {exc.reason}") from exc
    except socket.timeout:
        raise ValueError(f"Request timed out after {timeout}s") from None


def _detect_encoding(body: bytes, content_type: str) -> str:
    """Detect character encoding from Content-Type header or HTML meta charset tag."""
    # 1. Content-Type header charset
    m = re.search(r"charset=([^\s;]+)", content_type, re.I)
    if m:
        return m.group(1).strip('"\'')
    # 2. HTML meta charset
    snip = body[:4096].decode("latin-1", errors="replace")
    m = re.search(r'<meta[^>]+charset=["\']?([^"\';\s>]+)', snip, re.I)
    if m:
        return m.group(1)
    return "utf-8"


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

_VALID_EXTRACT = {"text", "links", "images", "metadata"}


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for agentic_web_crawl.

    Fetches a URL and returns structured SEO signals and page content.

    Params:
        url         URL to fetch (required, http/https only)
        extract     Comma-separated fields or "all": text, links, images, metadata (default: "all")
                    For SEO-only audits, use "metadata" or "metadata,links"
        timeout     Request timeout in seconds, clamped 1–60 (default: 15)
        max_links   Max links returned, clamped 1–500 (default: 50)
        max_images  Max images returned, clamped 1–200 (default: 20)

    Returns {"result": {...}, "error": None} on success or {"result": None, "error": "..."} on failure.

    The metadata block includes:
        title, description, canonical, robots, keywords, word_count,
        og_title, og_description, og_image, og_type, og_url,
        twitter_card, twitter_title, twitter_description,
        headings (h1–h6 in document order),
        link_breakdown (internal vs external counts)
    """
    url: str = (params.get("url") or "").strip()
    if not url:
        return {"result": None, "error": "url is required"}

    # Validate scheme
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return {"result": None, "error": f"Unsupported scheme '{parsed.scheme}'. Use http or https."}

    # Parse extract param
    raw_extract: str = (params.get("extract") or "all").strip().lower()
    if raw_extract == "all":
        active = _VALID_EXTRACT.copy()
    else:
        requested = {s.strip() for s in raw_extract.split(",") if s.strip()}
        unknown = requested - _VALID_EXTRACT
        if unknown:
            return {
                "result": None,
                "error": f"Unknown extract values: {sorted(unknown)}. "
                         f"Valid: {sorted(_VALID_EXTRACT)}",
            }
        active = requested

    try:
        timeout    = min(max(int(params.get("timeout")    or 15), 1), 60)
        max_links  = min(max(int(params.get("max_links")  or 50), 1), 500)
        max_images = min(max(int(params.get("max_images") or 20), 1), 200)
    except (TypeError, ValueError) as exc:
        return {"result": None, "error": f"Invalid numeric parameter: {exc}"}

    # Fetch
    try:
        body, final_url = _fetch(url, timeout)
    except ValueError as exc:
        return {"result": None, "error": str(exc)}

    # Detect encoding and decode
    encoding = _detect_encoding(body, "")
    try:
        html = body.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        html = body.decode("utf-8", errors="replace")

    # Parse
    parser = _ContentParser(final_url)
    try:
        parser.feed(html)
    except Exception as exc:
        import sys
        print(f"[agentic_web_crawl] HTML parse warning for {final_url}: {exc}", file=sys.stderr)
    parser.finalize()

    # Build result
    result: dict[str, Any] = {
        "url": final_url,
        "title": parser.title,
    }

    if "metadata" in active:
        plain = parser.plain_text()
        word_count = len(plain.split()) if plain else 0
        result["metadata"] = {
            # Core SEO
            "description":           parser.meta.get("description") or parser.meta.get("og:description") or "",
            "canonical":             parser.canonical,
            "robots":                parser.meta.get("robots") or "",
            "keywords":              parser.meta.get("keywords") or "",
            "word_count":            word_count,
            # Open Graph
            "og_title":              parser.meta.get("og:title") or "",
            "og_description":        parser.meta.get("og:description") or "",
            "og_image":              parser.meta.get("og:image") or "",
            "og_type":               parser.meta.get("og:type") or "",
            "og_url":                parser.meta.get("og:url") or "",
            # Twitter Card
            "twitter_card":          parser.meta.get("twitter:card") or "",
            "twitter_title":         parser.meta.get("twitter:title") or "",
            "twitter_description":   parser.meta.get("twitter:description") or "",
            # Structure
            "headings":              parser.headings,
            "link_breakdown":        parser.link_breakdown(),
        }

    if "text" in active:
        result["text"] = parser.plain_text()

    if "links" in active:
        result["links"] = parser.links[:max_links]
        result["links_count"] = len(parser.links)

    if "images" in active:
        result["images"] = parser.images[:max_images]
        result["images_count"] = len(parser.images)

    return {"result": result, "error": None}
