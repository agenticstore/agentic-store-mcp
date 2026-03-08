# agentic_web_search

> Fetch any URL and extract a full SEO signal report for AI agents. No API key required — pure Python stdlib.

Designed for agents doing **SEO research**, **competitive analysis**, and **content audits**. Sends a single HTTP GET, parses the HTML, and returns every SEO signal an agent needs to evaluate or compare a page.

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `url` | `string` | Yes | URL to fetch. Must use `http` or `https`. |
| `extract` | `string` | No | Comma-separated: `text`, `links`, `images`, `metadata`. Default: `"all"`. For SEO audits use `"metadata"` or `"metadata,links"`. |
| `timeout` | `integer` | No | Request timeout in seconds (1–60). Default: `15` |
| `max_links` | `integer` | No | Max links to return (1–500). Default: `50` |
| `max_images` | `integer` | No | Max images to return (1–200). Default: `20` |

## Required Setup

No API keys required. Uses only Python's standard library (`urllib`, `html.parser`).

## SEO Signals Extracted

### `metadata` ← primary SEO block

| Field | Source tag |
|-------|-----------|
| `description` | `<meta name="description">` or `og:description` fallback |
| `canonical` | `<link rel="canonical">` |
| `robots` | `<meta name="robots">` |
| `keywords` | `<meta name="keywords">` |
| `word_count` | Word count of visible body text |
| `og_title` | `<meta property="og:title">` |
| `og_description` | `<meta property="og:description">` |
| `og_image` | `<meta property="og:image">` |
| `og_type` | `<meta property="og:type">` |
| `og_url` | `<meta property="og:url">` |
| `twitter_card` | `<meta name="twitter:card">` |
| `twitter_title` | `<meta name="twitter:title">` |
| `twitter_description` | `<meta name="twitter:description">` |
| `headings` | All `<h1>`–`<h6>` in document order |
| `link_breakdown` | `{ "internal": N, "external": N }` |

### `text`

Clean readable body text. Scripts, styles, and hidden elements stripped. Block elements produce line breaks. Consecutive blank lines collapsed.

### `links`

All `<a href>` links resolved to absolute URLs. Fragments (`#`) and `javascript:` hrefs excluded. `links_count` reflects total before `max_links` truncation.

```json
{ "url": "https://example.com/about", "text": "About Us" }
```

### `images`

All `<img src>` elements resolved to absolute URLs. `images_count` reflects total before `max_images` truncation.

```json
{ "src": "https://example.com/logo.png", "alt": "Company Logo" }
```

## Examples

### Example 1: Full SEO audit

Input:
```json
{ "url": "https://example.com/article" }
```

Output:
```json
{
  "url": "https://example.com/article",
  "title": "10 Python Tips Every Developer Should Know",
  "metadata": {
    "description": "A practical guide to Python best practices.",
    "canonical": "https://example.com/article",
    "robots": "index, follow",
    "keywords": "python, tips, developers",
    "word_count": 1240,
    "og_title": "10 Python Tips",
    "og_description": "A practical guide to Python best practices.",
    "og_image": "https://example.com/img/hero.png",
    "og_type": "article",
    "og_url": "https://example.com/article",
    "twitter_card": "summary_large_image",
    "twitter_title": "10 Python Tips",
    "twitter_description": "A practical guide.",
    "headings": [
      { "level": "h1", "text": "10 Python Tips Every Developer Should Know" },
      { "level": "h2", "text": "1. Use List Comprehensions" }
    ],
    "link_breakdown": { "internal": 8, "external": 3 }
  },
  "text": "10 Python Tips...",
  "links": [ { "url": "https://example.com/next", "text": "Next Article" } ],
  "links_count": 11,
  "images": [ { "src": "https://example.com/img/hero.png", "alt": "Hero" } ],
  "images_count": 2
}
```

### Example 2: Metadata-only (fastest SEO check)

```json
{
  "url": "https://example.com/article",
  "extract": "metadata"
}
```

### Example 3: Competitor link analysis

```json
{
  "url": "https://competitor.com",
  "extract": "metadata,links",
  "max_links": 200
}
```

### Example 4: Batch SEO audit (agent pattern)

```
For each URL in this list, call agentic_web_search with extract="metadata"
and return a table of: title, description length, canonical, h1, word_count,
og_type, twitter_card, robots.
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Unsupported scheme 'ftp'` | Non-http(s) URL | Use `http://` or `https://` |
| `HTTP 403` | Server blocks automated requests | Some sites block crawlers |
| `HTTP 404` | Page not found | Check the URL |
| `Request timed out` | Server too slow | Increase `timeout` |
| `Unknown extract values` | Typo in `extract` | Valid: `text`, `links`, `images`, `metadata` |

## Known Limitations

- **JavaScript-rendered content**: Only static HTML is parsed. SPAs requiring JS execution return a partial or empty body.
- **Login-gated pages**: No cookie or session support.
- **5 MB cap**: Responses larger than 5 MB are truncated.
- **Redirects**: Followed automatically. `url` in the result reflects the final URL after redirects.
