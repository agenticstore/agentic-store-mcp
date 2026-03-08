# AgenticData

> Tools for fetching, searching, and analyzing data from the web.

## Tools

| Tool | Description | Required Setup |
|------|-------------|----------------|
| [`agentic_web_crawl`](agentic_web_crawl/README.md) | Fetch any URL and extract page content, SEO signals, headings, links, and images | None |
| [`agentic_web_search`](agentic_web_search/README.md) | Search the web via a self-hosted SearXNG instance; returns ranked results with title, URL, snippet | SearXNG running (`docker compose up -d`) |

## Required API Keys

No API keys required. `agentic_web_search` requires a locally running SearXNG instance — no external accounts needed.

## Quick Setup

**Python (all AgenticData tools):**
```bash
uvx agentic-store-mcp --modules data
```

**With SearXNG (for web search):**
```bash
# 1. Start SearXNG
docker compose up -d

# 2. Run MCP server (Python)
SEARXNG_URL=http://localhost:8080 uvx agentic-store-mcp --modules data

# 2. OR run MCP server (Docker)
docker build -t agentic-store-mcp .
docker run -i --rm \
  --network agentic-store-mcp_default \
  -e SEARXNG_URL=http://searxng:8080 \
  agentic-store-mcp --modules data
```

**Client config (Claude Desktop / Cursor / Windsurf):**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "uvx",
      "args": ["agentic-store-mcp", "--modules", "data"],
      "env": {
        "SEARXNG_URL": "http://localhost:8080"
      }
    }
  }
}
```
