# Docker — AgenticStore MCP Tools

Run the MCP server as a Docker container. No Python, no `uv`, no virtual environments needed on the host.

---

## Architecture overview

```
Your AI Client (Claude Desktop / Cursor / etc.)
        │
        │  stdio (stdin/stdout)
        ▼
docker run -i --rm agentic-store-mcp   ← MCP server container
        │
        │  HTTP (JSON API)
        ▼
docker compose → searxng:8080               ← SearXNG (web search backend)
```

- The **MCP server** is launched per-connection by your AI client (stdio protocol).
- **SearXNG** runs as a persistent background service via `docker compose`.
- The two containers communicate over a shared Docker network.

---

## Part 1 — MCP server container

### 1. Build the image

```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
docker build -t agentic-store-mcp .
```

### 2. Verify

```bash
docker run --rm agentic-store-mcp --list
```

### 3. Run (basic — crawl only, no search)

```bash
docker run -i --rm agentic-store-mcp
```

> **Important:** The `-i` flag (keep stdin open) is **required**. The MCP protocol communicates over stdin/stdout. Without `-i`, the container exits immediately.

---

## Part 2 — SearXNG (web search backend)

The `agentic_web_search` tool requires a running SearXNG instance.

### 1. Start SearXNG

```bash
docker compose up -d
```

This starts SearXNG on `http://localhost:8080`. The `searxng/settings.yml` in this repo pre-configures the JSON API format required by `agentic_web_search`.

### 2. Verify SearXNG is running

```bash
# Open in browser or curl
curl "http://localhost:8080/search?q=test&format=json"
```

You should get a JSON response with search results.

### 3. Stop SearXNG

```bash
docker compose down
```

### Logs

```bash
docker compose logs -f searxng
```

---

## Part 3 — Run MCP server with web search enabled

When using `agentic_web_search`, the MCP container needs to reach SearXNG.
Join the same Docker network and point `SEARXNG_URL` at the SearXNG container hostname:

```bash
docker run -i --rm \
  --network agentic-store-mcp_default \
  -e SEARXNG_URL=http://searxng:8080 \
  agentic-store-mcp
```

The network name `agentic-store-mcp_default` is created automatically by `docker compose up`.

---

## Part 4 — Configure your AI client

### Claude Desktop

**Config location**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Web crawl only (no SearXNG needed):**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "agentic-store-mcp"]
    }
  }
}
```

**With web search (SearXNG must be running via `docker compose up -d`):**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "agentic-store-mcp_default",
        "-e", "SEARXNG_URL=http://searxng:8080",
        "agentic-store-mcp"
      ]
    }
  }
}
```

### Cursor

**Config location:** `~/.cursor/mcp.json`

**Web crawl only:**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "agentic-store-mcp"]
    }
  }
}
```

**With web search:**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "agentic-store-mcp_default",
        "-e", "SEARXNG_URL=http://searxng:8080",
        "agentic-store-mcp"
      ]
    }
  }
}
```

### Windsurf

**Config location:** `~/.codeium/windsurf/mcp_config.json`

Same pattern as Cursor above.

---

## Quick reference

| Task | Command |
|------|---------|
| Build MCP image | `docker build -t agentic-store-mcp .` |
| Rebuild after update | `git pull && docker build -t agentic-store-mcp .` |
| Start SearXNG | `docker compose up -d` |
| Stop SearXNG | `docker compose down` |
| SearXNG logs | `docker compose logs -f searxng` |
| Test MCP tools list | `docker run --rm agentic-store-mcp --list` |
| Test SearXNG API | `curl "http://localhost:8080/search?q=test&format=json"` |

---

## Passing flags to the server

All `server.py` flags work as additional `args`:

```json
"args": ["run", "-i", "--rm", "agentic-store-mcp", "--modules", "data"]
```

| Flag | Example value | Effect |
|------|---------------|--------|
| `--modules` | `code,data` | Load specific modules only |
| `--tools` | `agentic_web_search` | Load a single tool |
| `--list` | *(none)* | Print tools and exit |
