# agentic_web_search

Search the web using a self-hosted [SearXNG](https://github.com/searxng/searxng) instance.

SearXNG is a free, open-source metasearch engine that aggregates results from Google, Bing, DuckDuckGo, and dozens of other engines — without tracking users or requiring API keys.

## What it does

- Takes a natural-language search query
- Hits your local SearXNG instance via its JSON API
- Returns ranked results: title, URL, snippet, and source engine

Unlike `agentic_web_crawl`, this tool does **not** fetch or parse page content — it returns the search index results only. Use `agentic_web_crawl` to then fetch and read individual pages.

## Prerequisites

SearXNG must be running locally. Start it with:

```bash
docker compose up -d
```

This uses the `docker-compose.yml` in the repo root, which bundles SearXNG pre-configured with JSON API support.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query. Example: `"open source MCP tools"` |
| `categories` | string | No | `general` | SearXNG category: `general`, `news`, `images`, `science`, `it`, `map`, `music`, `social_media`, `videos` |
| `language` | string | No | `en` | Language code: `en`, `de`, `fr`, `es`, etc. |
| `max_results` | integer | No | `10` | Number of results (1–50) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_URL` | `http://localhost:8080` | Base URL of your SearXNG instance |

## Example Response

```json
{
  "result": {
    "query": "open source MCP tools",
    "categories": "general",
    "language": "en",
    "total_results": 10,
    "results": [
      {
        "title": "AgenticStore MCP Tools",
        "url": "https://github.com/agenticstore/agentic-store-mcp",
        "snippet": "Free, open-source MCP tools for AI agents — self-hosted, no account required.",
        "engine": "google"
      }
    ]
  },
  "error": null
}
```

## Troubleshooting

**`Cannot reach SearXNG at http://localhost:8080`**
SearXNG is not running. Start it: `docker compose up -d`

**`SearXNG returned HTTP 400`**
The JSON format is not enabled in your SearXNG settings. The `searxng/settings.yml` in this repo enables it by default. If you're using a custom config, add `json` to `search.formats`.

**`SearXNG returned non-JSON response`**
Usually means your SearXNG instance is returning an HTML error page. Check `docker compose logs searxng`.
